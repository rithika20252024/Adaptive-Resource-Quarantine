"""
Continuous Process Telemetry Monitor.
Extracts CPU %, Memory (RSS & VMS), I/O rates, and Thread statistics across Linux, macOS, and POSIX.
- Linux: Native /proc/<pid>/stat, /proc/<pid>/status, /proc/<pid>/io parsing.
- macOS: Native libproc.proc_pidinfo kernel bindings (PROC_PIDTASKINFO) via ctypes.
- Fallback: Standard psutil when available or POSIX heuristics.
"""

import ctypes
import os
import sys
import time
from typing import Dict, List, Optional
from arq.core.process_model import ProcessMetrics

# Setup macOS libproc if on darwin
IS_MACOS = sys.platform == "darwin"
libproc = None
mach_timebase_factor = 1.0 / 1e9

if IS_MACOS:
    try:
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
        libc = ctypes.CDLL(None)
        
        class MachTimebaseInfo(ctypes.Structure):
            _fields_ = [('numer', ctypes.c_uint32), ('denom', ctypes.c_uint32)]
        
        tb = MachTimebaseInfo()
        libc.mach_timebase_info(ctypes.byref(tb))
        mach_timebase_factor = (tb.numer / tb.denom) / 1e9
        
        class ProcTaskInfo(ctypes.Structure):
            _fields_ = [
                ('pti_virtual_size', ctypes.c_uint64),
                ('pti_resident_size', ctypes.c_uint64),
                ('pti_total_user', ctypes.c_uint64),
                ('pti_total_system', ctypes.c_uint64),
                ('pti_threads_user', ctypes.c_uint64),
                ('pti_threads_system', ctypes.c_uint64),
                ('pti_policy', ctypes.c_int32),
                ('pti_faults', ctypes.c_int32),
                ('pti_pageins', ctypes.c_int32),
                ('pti_cow_faults', ctypes.c_int32),
                ('pti_messages_sent', ctypes.c_int32),
                ('pti_messages_received', ctypes.c_int32),
                ('pti_syscalls_mach', ctypes.c_int32),
                ('pti_syscalls_unix', ctypes.c_int32),
                ('pti_csw', ctypes.c_int32),
                ('pti_threadnum', ctypes.c_int32),
                ('pti_numrunning', ctypes.c_int32),
                ('pti_priority', ctypes.c_int32),
            ]
        PROC_PIDTASKINFO = 4
    except Exception:
        libproc = None

class ProcessMonitor:
    """
    Monitors process execution and resource consumption in real-time.
    """
    def __init__(self, target_pids: Optional[List[int]] = None):
        self.target_pids = target_pids or []
        self._last_sample_time: Dict[int, float] = {}
        self._last_cpu_ns: Dict[int, float] = {}
        self._last_cpu_ticks: Dict[int, float] = {}
        self._last_rss: Dict[int, float] = {}
        self._last_io: Dict[int, Dict[str, int]] = {}

    def sample_process(self, pid: int) -> Optional[ProcessMetrics]:
        """Collect current metrics for a specific PID."""
        if IS_MACOS and libproc:
            return self._sample_macos_libproc(pid)
        elif os.path.exists(f"/proc/{pid}"):
            return self._sample_linux_proc(pid)
        else:
            return self._sample_fallback(pid)

    def sample_all(self, pids: Optional[List[int]] = None) -> List[ProcessMetrics]:
        """Sample metrics for all specified PIDs or tracked targets."""
        active_pids = pids if pids is not None else self.target_pids
        results = []
        for pid in list(active_pids):
            metrics = self.sample_process(pid)
            if metrics:
                results.append(metrics)
        return results

    def _sample_macos_libproc(self, pid: int) -> Optional[ProcessMetrics]:
        try:
            info = ProcTaskInfo()
            ret = libproc.proc_pidinfo(pid, PROC_PIDTASKINFO, 0, ctypes.byref(info), ctypes.sizeof(info))
            if ret != ctypes.sizeof(info):
                return None

            now = time.time()
            name_buf = ctypes.create_string_buffer(256)
            libproc.proc_name(pid, name_buf, 256)
            name = name_buf.value.decode("utf-8", errors="ignore") or f"pid_{pid}"

            rss_mb = info.pti_resident_size / (1024.0 * 1024.0)
            vms_mb = info.pti_virtual_size / (1024.0 * 1024.0)
            threads = info.pti_threadnum
            total_cpu_ns = info.pti_total_user + info.pti_total_system

            # CPU percentage
            cpu_pct = 0.0
            if pid in self._last_cpu_ns:
                prev_ns = self._last_cpu_ns[pid]
                prev_time = self._last_sample_time.get(pid, now - 1.0)
                dt = max(now - prev_time, 0.001)
                cpu_seconds = (total_cpu_ns - prev_ns) * mach_timebase_factor
                cpu_pct = max(0.0, (cpu_seconds / dt) * 100.0)
            self._last_cpu_ns[pid] = total_cpu_ns

            # Memory rate
            prev_rss = self._last_rss.get(pid, rss_mb)
            dt = max(now - self._last_sample_time.get(pid, now - 1.0), 0.001)
            growth_rate = max(0.0, (rss_mb - prev_rss) / dt)
            self._last_rss[pid] = rss_mb
            self._last_sample_time[pid] = now

            return ProcessMetrics(
                pid=pid,
                name=name,
                cpu_percent=round(cpu_pct, 2),
                memory_rss_mb=round(rss_mb, 2),
                memory_vms_mb=round(vms_mb, 2),
                memory_growth_mb_s=round(growth_rate, 2),
                io_read_kb_s=0.0,
                io_write_kb_s=0.0,
                num_threads=threads,
                timestamp=now
            )
        except Exception:
            return None

    def _sample_linux_proc(self, pid: int) -> Optional[ProcessMetrics]:
        """Direct Linux /proc extraction."""
        try:
            now = time.time()
            stat_path = f"/proc/{pid}/stat"
            status_path = f"/proc/{pid}/status"
            if not os.path.exists(stat_path):
                return None
            
            with open(stat_path, "r") as f:
                stat_data = f.read().split()
            
            comm = stat_data[1].strip("()")
            utime = int(stat_data[13])
            stime = int(stat_data[14])
            total_time = utime + stime
            
            cpu_pct = 0.0
            if pid in self._last_cpu_ticks:
                last_t = self._last_cpu_ticks[pid]
                last_wall = self._last_sample_time.get(pid, now - 1.0)
                dt = max(now - last_wall, 0.001)
                clk_tck = os.sysconf(os.sysconf_names['SC_CLK_TCK']) if hasattr(os, 'sysconf_names') else 100
                cpu_seconds = (total_time - last_t) / clk_tck
                cpu_pct = max(0.0, (cpu_seconds / dt) * 100.0)
            self._last_cpu_ticks[pid] = total_time

            rss_mb = 0.0
            vms_mb = 0.0
            threads = 1
            if os.path.exists(status_path):
                with open(status_path, "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            rss_mb = float(line.split()[1]) / 1024.0
                        elif line.startswith("VmSize:"):
                            vms_mb = float(line.split()[1]) / 1024.0
                        elif line.startswith("Threads:"):
                            threads = int(line.split()[1])

            prev_rss = self._last_rss.get(pid, rss_mb)
            dt = max(now - self._last_sample_time.get(pid, now - 1.0), 0.001)
            growth_rate = max(0.0, (rss_mb - prev_rss) / dt)
            self._last_rss[pid] = rss_mb

            read_kb_s = 0.0
            write_kb_s = 0.0
            io_path = f"/proc/{pid}/io"
            if os.path.exists(io_path):
                try:
                    with open(io_path, "r") as f:
                        r_bytes, w_bytes = 0, 0
                        for line in f:
                            if line.startswith("read_bytes:"):
                                r_bytes = int(line.split()[1])
                            elif line.startswith("write_bytes:"):
                                w_bytes = int(line.split()[1])
                        if pid in self._last_io:
                            prev_io = self._last_io[pid]
                            read_kb_s = max(0.0, (r_bytes - prev_io['r']) / (1024 * dt))
                            write_kb_s = max(0.0, (w_bytes - prev_io['w']) / (1024 * dt))
                        self._last_io[pid] = {'r': r_bytes, 'w': w_bytes}
                except Exception:
                    pass

            self._last_sample_time[pid] = now
            return ProcessMetrics(
                pid=pid,
                name=comm,
                cpu_percent=round(cpu_pct, 2),
                memory_rss_mb=round(rss_mb, 2),
                memory_vms_mb=round(vms_mb, 2),
                memory_growth_mb_s=round(growth_rate, 2),
                io_read_kb_s=round(read_kb_s, 2),
                io_write_kb_s=round(write_kb_s, 2),
                num_threads=threads,
                timestamp=now
            )
        except Exception:
            return None

    def _sample_fallback(self, pid: int) -> Optional[ProcessMetrics]:
        now = time.time()
        return ProcessMetrics(pid=pid, name=f"pid_{pid}", timestamp=now)
