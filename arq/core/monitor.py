"""Cross-platform process telemetry monitor supporting macOS libproc and Linux /proc."""

import ctypes
import ctypes.util
import os
import subprocess
import sys
import time
from typing import Dict, Iterable, List, Optional, Set, Tuple

from arq.core.process_model import ProcessMetrics

# ============================================================================
# macOS libproc / Mach Structures & Bindings
# ============================================================================

PROC_PIDTASKINFO = 4
RUSAGE_INFO_V4 = 4


class MachTimebaseInfo(ctypes.Structure):
    """Mach timebase info struct for tick-to-nanosecond conversion."""

    _fields_ = [
        ("numer", ctypes.c_uint32),
        ("denom", ctypes.c_uint32),
    ]


class ProcPidTaskInfo(ctypes.Structure):
    """macOS proc_pidtaskinfo struct providing process resource metrics."""

    _fields_ = [
        ("pti_virtual_size", ctypes.c_uint64),
        ("pti_resident_size", ctypes.c_uint64),
        ("pti_total_user", ctypes.c_uint64),
        ("pti_total_system", ctypes.c_uint64),
        ("pti_threads_user", ctypes.c_uint64),
        ("pti_threads_system", ctypes.c_uint64),
        ("pti_policy", ctypes.c_int32),
        ("pti_faults", ctypes.c_int32),
        ("pti_pageins", ctypes.c_int32),
        ("pti_cow_faults", ctypes.c_int32),
        ("pti_messages_sent", ctypes.c_int32),
        ("pti_messages_received", ctypes.c_int32),
        ("pti_syscalls_mach", ctypes.c_int32),
        ("pti_syscalls_unix", ctypes.c_int32),
        ("pti_csw", ctypes.c_int32),
        ("pti_threadnum", ctypes.c_int32),
        ("pti_numrunning", ctypes.c_int32),
        ("pti_priority", ctypes.c_int32),
    ]


class RUsageInfoV4(ctypes.Structure):
    """macOS rusage_info_v4 struct providing disk I/O metrics."""

    _fields_ = [
        ("ri_uuid", ctypes.c_uint8 * 16),
        ("ri_user_time", ctypes.c_uint64),
        ("ri_system_time", ctypes.c_uint64),
        ("ri_pkg_idle_wkups", ctypes.c_uint64),
        ("ri_interrupt_wkups", ctypes.c_uint64),
        ("ri_pageins", ctypes.c_uint64),
        ("ri_wired_size", ctypes.c_uint64),
        ("ri_resident_size", ctypes.c_uint64),
        ("ri_phys_footprint", ctypes.c_uint64),
        ("ri_proc_start_abstime", ctypes.c_uint64),
        ("ri_proc_exit_abstime", ctypes.c_uint64),
        ("ri_child_user_time", ctypes.c_uint64),
        ("ri_child_system_time", ctypes.c_uint64),
        ("ri_child_pkg_idle_wkups", ctypes.c_uint64),
        ("ri_child_interrupt_wkups", ctypes.c_uint64),
        ("ri_child_pageins", ctypes.c_uint64),
        ("ri_child_elapsed_abstime", ctypes.c_uint64),
        ("ri_diskio_bytesread", ctypes.c_uint64),
        ("ri_diskio_byteswritten", ctypes.c_uint64),
    ]


# ============================================================================
# Monitor Implementation
# ============================================================================

class ProcessMonitor:
    """Telemetric process monitor extracting granular resource utilization across platforms.

    Supports native C-library calls (libproc, mach_timebase_info) on macOS and
    pseudo-filesystem inspection (/proc/<pid>/stat, status, io) on Linux, with
    graceful degradation fallbacks.
    """

    def __init__(self, target_pids: Optional[Iterable[int]] = None) -> None:
        """Initialize the telemetry monitor.

        Args:
            target_pids: Optional initial set of target PIDs to monitor.
        """
        self.target_pids: Set[int] = set(target_pids) if target_pids is not None else set()

        # Telemetry delta tracking state per PID
        self._last_sample_time: Dict[int, float] = {}
        self._last_cpu_ns: Dict[int, float] = {}       # macOS CPU time in nanoseconds
        self._last_cpu_ticks: Dict[int, int] = {}      # Linux CPU time in clock ticks
        self._last_rss: Dict[int, float] = {}          # RSS in MB
        self._last_io: Dict[int, Tuple[int, int]] = {} # (read_bytes, write_bytes)

        # Platform subsystem initialization
        self._is_macos = sys.platform == "darwin"
        self._is_linux = sys.platform.startswith("linux")

        self._libc: Optional[ctypes.CDLL] = None
        self._libproc: Optional[ctypes.CDLL] = None
        self._timebase_factor: float = 1.0  # nanoseconds per mach tick

        if self._is_macos:
            self._init_macos_bindings()
        elif self._is_linux:
            self._clk_tck = (
                os.sysconf(os.sysconf_names["SC_CLK_TCK"])
                if hasattr(os, "sysconf") and "SC_CLK_TCK" in os.sysconf_names
                else 100
            )

    def _init_macos_bindings(self) -> None:
        """Load and bind macOS C libraries for process telemetry."""
        try:
            libc_path = ctypes.util.find_library("c")
            self._libc = ctypes.CDLL(libc_path or "/usr/lib/libc.dylib")

            libproc_path = ctypes.util.find_library("proc")
            self._libproc = ctypes.CDLL(libproc_path or "/usr/lib/libproc.dylib")

            # Setup mach_timebase_info
            self._libc.mach_timebase_info.argtypes = [ctypes.POINTER(MachTimebaseInfo)]
            self._libc.mach_timebase_info.restype = ctypes.c_int
            tb = MachTimebaseInfo()
            if self._libc.mach_timebase_info(ctypes.byref(tb)) == 0 and tb.denom != 0:
                self._timebase_factor = float(tb.numer) / float(tb.denom)

            # Setup libproc bindings
            self._libproc.proc_pidinfo.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_uint64,
                ctypes.c_void_p,
                ctypes.c_int,
            ]
            self._libproc.proc_pidinfo.restype = ctypes.c_int

            self._libproc.proc_name.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint32,
            ]
            self._libproc.proc_name.restype = ctypes.c_int

            if hasattr(self._libproc, "proc_pid_rusage"):
                self._libproc.proc_pid_rusage.argtypes = [
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_void_p,
                ]
                self._libproc.proc_pid_rusage.restype = ctypes.c_int
        except Exception:
            # Fall back if bindings fail
            self._libc = None
            self._libproc = None

    def _clear_pid_state(self, pid: int) -> None:
        """Clear cached history for a process that has exited or is no longer accessible."""
        self._last_sample_time.pop(pid, None)
        self._last_cpu_ns.pop(pid, None)
        self._last_cpu_ticks.pop(pid, None)
        self._last_rss.pop(pid, None)
        self._last_io.pop(pid, None)

    def sample_process(self, pid: int) -> Optional[ProcessMetrics]:
        """Sample resource metrics for a single process.

        Calculates CPU utilization, memory growth rate, and disk I/O rates
        based on elapsed time since the previous sample.

        Args:
            pid: The process ID to inspect.

        Returns:
            A populated ProcessMetrics instance, or None if the process does not exist
            or could not be inspected.
        """
        if self._is_macos and self._libproc is not None:
            return self._sample_macos(pid)
        elif self._is_linux:
            return self._sample_linux(pid)
        else:
            return self._sample_fallback(pid)

    def sample_all(self, pids: Optional[Iterable[int]] = None) -> List[ProcessMetrics]:
        """Sample telemetry for a collection of processes.

        Args:
            pids: Target process IDs. If omitted, uses registered target_pids.

        Returns:
            A list of ProcessMetrics for all successfully sampled processes.
        """
        targets = self.target_pids if pids is None else pids
        results: List[ProcessMetrics] = []
        for pid in targets:
            metrics = self.sample_process(pid)
            if metrics is not None:
                results.append(metrics)
        return results

    # ------------------------------------------------------------------------
    # macOS Implementation (libproc & mach_timebase_info)
    # ------------------------------------------------------------------------

    def _sample_macos(self, pid: int) -> Optional[ProcessMetrics]:
        """Collect metrics on macOS using libproc and Mach kernel APIs."""
        task_info = ProcPidTaskInfo()
        ret = self._libproc.proc_pidinfo(
            ctypes.c_int(pid),
            ctypes.c_int(PROC_PIDTASKINFO),
            ctypes.c_uint64(0),
            ctypes.byref(task_info),
            ctypes.c_int(ctypes.sizeof(task_info)),
        )

        if ret <= 0:
            self._clear_pid_state(pid)
            return None

        now = time.time()

        # Resolve process name
        name_buf = ctypes.create_string_buffer(256)
        name_ret = self._libproc.proc_name(ctypes.c_int(pid), name_buf, ctypes.c_uint32(256))
        name = name_buf.value.decode("utf-8", errors="ignore") if name_ret > 0 else f"proc_{pid}"

        # CPU calculation: convert Mach absolute time ticks to nanoseconds
        raw_ticks = task_info.pti_total_user + task_info.pti_total_system
        current_cpu_ns = float(raw_ticks) * self._timebase_factor

        # Memory calculation: bytes to megabytes
        vms_mb = float(task_info.pti_virtual_size) / (1024.0 * 1024.0)
        rss_mb = float(task_info.pti_resident_size) / (1024.0 * 1024.0)
        num_threads = int(task_info.pti_threadnum)

        # Disk I/O calculation via proc_pid_rusage
        read_bytes = 0
        write_bytes = 0
        if hasattr(self._libproc, "proc_pid_rusage"):
            rinfo = RUsageInfoV4()
            ru_ret = self._libproc.proc_pid_rusage(
                ctypes.c_int(pid),
                ctypes.c_int(RUSAGE_INFO_V4),
                ctypes.byref(rinfo),
            )
            if ru_ret == 0:
                read_bytes = int(rinfo.ri_diskio_bytesread)
                write_bytes = int(rinfo.ri_diskio_byteswritten)

        # Delta computations
        cpu_percent = 0.0
        mem_growth_mb_s = 0.0
        io_read_kb_s = 0.0
        io_write_kb_s = 0.0

        if pid in self._last_sample_time:
            delta_time = now - self._last_sample_time[pid]
            if delta_time > 0:
                delta_cpu_ns = max(0.0, current_cpu_ns - self._last_cpu_ns.get(pid, current_cpu_ns))
                cpu_percent = (delta_cpu_ns / (delta_time * 1e9)) * 100.0

                prev_rss = self._last_rss.get(pid, rss_mb)
                mem_growth_mb_s = (rss_mb - prev_rss) / delta_time

                prev_read, prev_write = self._last_io.get(pid, (read_bytes, write_bytes))
                delta_read_kb = max(0.0, float(read_bytes - prev_read) / 1024.0)
                delta_write_kb = max(0.0, float(write_bytes - prev_write) / 1024.0)
                io_read_kb_s = delta_read_kb / delta_time
                io_write_kb_s = delta_write_kb / delta_time

        # Update cache
        self._last_sample_time[pid] = now
        self._last_cpu_ns[pid] = current_cpu_ns
        self._last_rss[pid] = rss_mb
        self._last_io[pid] = (read_bytes, write_bytes)

        return ProcessMetrics(
            pid=pid,
            name=name,
            cpu_percent=cpu_percent,
            memory_rss_mb=rss_mb,
            memory_vms_mb=vms_mb,
            memory_growth_mb_s=mem_growth_mb_s,
            io_read_kb_s=io_read_kb_s,
            io_write_kb_s=io_write_kb_s,
            num_threads=num_threads,
            timestamp=now,
        )

    # ------------------------------------------------------------------------
    # Linux Implementation (/proc/<pid>/stat, status, io)
    # ------------------------------------------------------------------------

    def _sample_linux(self, pid: int) -> Optional[ProcessMetrics]:
        """Collect metrics on Linux by parsing /proc filesystems."""
        stat_path = f"/proc/{pid}/stat"
        status_path = f"/proc/{pid}/status"
        io_path = f"/proc/{pid}/io"

        try:
            with open(stat_path, "r", encoding="utf-8") as f:
                stat_content = f.read()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            self._clear_pid_state(pid)
            return None

        now = time.time()

        # Parse /proc/<pid>/stat
        # format: pid (comm) state ppid pgrp ...
        rparen = stat_content.rfind(")")
        lparen = stat_content.find("(")
        if lparen == -1 or rparen == -1:
            self._clear_pid_state(pid)
            return None

        name = stat_content[lparen + 1:rparen]
        rest = stat_content[rparen + 2:].split()

        try:
            # utime is field 14, stime is field 15 (1-based indices)
            # In 'rest', index 0 is field 3 (state), so:
            # utime index is 14 - 3 = 11
            # stime index is 15 - 3 = 12
            utime = int(rest[11])
            stime = int(rest[12])
            current_ticks = utime + stime
        except (IndexError, ValueError):
            self._clear_pid_state(pid)
            return None

        # Parse /proc/<pid>/status for RSS, VMS, and thread count
        rss_mb = 0.0
        vms_mb = 0.0
        num_threads = 1
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss_mb = float(line.split()[1]) / 1024.0
                    elif line.startswith("VmSize:"):
                        vms_mb = float(line.split()[1]) / 1024.0
                    elif line.startswith("Threads:"):
                        num_threads = int(line.split()[1])
        except (FileNotFoundError, IOError):
            pass

        # Parse /proc/<pid>/io for disk reads and writes
        read_bytes = 0
        write_bytes = 0
        try:
            with open(io_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("read_bytes:"):
                        read_bytes = int(line.split()[1])
                    elif line.startswith("write_bytes:"):
                        write_bytes = int(line.split()[1])
        except (FileNotFoundError, IOError, PermissionError):
            pass

        # Delta calculations
        cpu_percent = 0.0
        mem_growth_mb_s = 0.0
        io_read_kb_s = 0.0
        io_write_kb_s = 0.0

        if pid in self._last_sample_time:
            delta_time = now - self._last_sample_time[pid]
            if delta_time > 0:
                prev_ticks = self._last_cpu_ticks.get(pid, current_ticks)
                delta_ticks = max(0, current_ticks - prev_ticks)
                delta_cpu_s = float(delta_ticks) / float(self._clk_tck)
                cpu_percent = (delta_cpu_s / delta_time) * 100.0

                prev_rss = self._last_rss.get(pid, rss_mb)
                mem_growth_mb_s = (rss_mb - prev_rss) / delta_time

                prev_read, prev_write = self._last_io.get(pid, (read_bytes, write_bytes))
                delta_read_kb = max(0.0, float(read_bytes - prev_read) / 1024.0)
                delta_write_kb = max(0.0, float(write_bytes - prev_write) / 1024.0)
                io_read_kb_s = delta_read_kb / delta_time
                io_write_kb_s = delta_write_kb / delta_time

        # Update cache
        self._last_sample_time[pid] = now
        self._last_cpu_ticks[pid] = current_ticks
        self._last_rss[pid] = rss_mb
        self._last_io[pid] = (read_bytes, write_bytes)

        return ProcessMetrics(
            pid=pid,
            name=name,
            cpu_percent=cpu_percent,
            memory_rss_mb=rss_mb,
            memory_vms_mb=vms_mb,
            memory_growth_mb_s=mem_growth_mb_s,
            io_read_kb_s=io_read_kb_s,
            io_write_kb_s=io_write_kb_s,
            num_threads=num_threads,
            timestamp=now,
        )

    # ------------------------------------------------------------------------
    # Fallback Implementation
    # ------------------------------------------------------------------------

    def _sample_fallback(self, pid: int) -> Optional[ProcessMetrics]:
        """Fallback process inspection when specialized kernel interfaces are unavailable."""
        try:
            # Check if process is alive
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError, OSError):
            self._clear_pid_state(pid)
            return None

        # Resolve process name via ps command fallback
        name = f"proc_{pid}"
        try:
            res = subprocess.run(
                ["ps", "-p", str(pid), "-o", "comm="],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1,
            )
            if res.returncode == 0 and res.stdout.strip():
                name = os.path.basename(res.stdout.strip())
        except Exception:
            pass

        now = time.time()
        self._last_sample_time[pid] = now

        return ProcessMetrics(
            pid=pid,
            name=name,
            cpu_percent=0.0,
            memory_rss_mb=0.0,
            memory_vms_mb=0.0,
            memory_growth_mb_s=0.0,
            io_read_kb_s=0.0,
            io_write_kb_s=0.0,
            num_threads=1,
            timestamp=now,
        )
