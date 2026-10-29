"""
Workload & Attack Simulator.
Generates controllable resource exhaustion patterns and co-located latency-sensitive workloads
for benchmarking and demonstrating the effectiveness of Adaptive Resource Quarantine.
"""

import math
import multiprocessing
import os
import tempfile
import time
from typing import List, Optional


def cpu_burner_worker(stop_event, intensity: float = 1.0) -> None:
    """Monopolize CPU core using mathematical computation."""
    while not stop_event.is_set():
        val = 0.0
        for i in range(10000):
            val += math.sin(i) * math.cos(i)
        if 0.0 < intensity < 1.0:
            time.sleep((1.0 - intensity) * 0.005)


def memory_leaker_worker(
    stop_event,
    chunk_mb: int = 15,
    interval_s: float = 0.5,
    max_mb: int = 500
) -> None:
    """Continuously allocate and retain memory chunks."""
    chunks: List[bytearray] = []
    total_allocated = 0
    while not stop_event.is_set():
        if total_allocated < max_mb:
            chunk = bytearray(chunk_mb * 1024 * 1024)
            # Touch pages to force physical RSS allocation
            for idx in range(0, len(chunk), 4096):
                chunk[idx] = 1
            chunks.append(chunk)
            total_allocated += chunk_mb
        time.sleep(interval_s)


def io_storm_worker(
    stop_event,
    block_size_kb: int = 64,
    iterations_per_cycle: int = 50
) -> None:
    """Continuously write and read temporary blocks on disk."""
    temp_dir = tempfile.mkdtemp(prefix="arq_io_")
    test_file = os.path.join(temp_dir, "test.dat")
    payload = b"X" * (block_size_kb * 1024)
    try:
        while not stop_event.is_set():
            with open(test_file, "wb") as f:
                for _ in range(iterations_per_cycle):
                    f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            with open(test_file, "rb") as f:
                while f.read(block_size_kb * 1024):
                    pass
            time.sleep(0.05)
    finally:
        try:
            if os.path.exists(test_file):
                os.remove(test_file)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception:
            pass


def transient_burst_worker(
    stop_event,
    burst_seconds: float = 3.0,
    idle_seconds: float = 5.0
) -> None:
    """Simulates realistic application bursting (e.g. compilation, code linters)."""
    while not stop_event.is_set():
        # Phase 1: Heavy burst
        t_end = time.time() + burst_seconds
        while time.time() < t_end and not stop_event.is_set():
            _ = math.sqrt(1234567.89) * math.atan(45.67)
        # Phase 2: Natural idle
        t_idle = time.time() + idle_seconds
        while time.time() < t_idle and not stop_event.is_set():
            time.sleep(0.1)


class WorkloadHandle:
    """Represents a running simulated workload subprocess."""

    def __init__(self, process: multiprocessing.Process, stop_event, name: str = "workload"):
        self.process = process
        self.stop_event = stop_event
        self.name = name

    @property
    def pid(self) -> int:
        return self.process.pid or 0

    def stop(self, timeout: float = 1.0) -> None:
        import signal
        if self.process.is_alive():
            try: os.kill(self.pid, signal.SIGCONT)
            except (OSError, AttributeError): pass
        self.stop_event.set()
        self.process.join(timeout=timeout)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=timeout)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(timeout=timeout)



class WorkloadSimulator:
    """Factory for spinning up isolated stress workloads."""

    @staticmethod
    def start_cpu_burner(name: str = "cpu_burner", intensity: float = 1.0) -> WorkloadHandle:
        stop_evt = multiprocessing.Event()
        p = multiprocessing.Process(
            target=cpu_burner_worker,
            args=(stop_evt, intensity),
            name=name
        )
        p.start()
        return WorkloadHandle(p, stop_evt, name)

    @staticmethod
    def start_memory_leaker(
        name: str = "mem_leaker",
        chunk_mb: int = 15,
        interval_s: float = 0.5,
        max_mb: int = 500
    ) -> WorkloadHandle:
        stop_evt = multiprocessing.Event()
        p = multiprocessing.Process(
            target=memory_leaker_worker,
            args=(stop_evt, chunk_mb, interval_s, max_mb),
            name=name
        )
        p.start()
        return WorkloadHandle(p, stop_evt, name)

    @staticmethod
    def start_io_storm(
        name: str = "io_storm",
        block_size_kb: int = 64,
        iterations_per_cycle: int = 50
    ) -> WorkloadHandle:
        stop_evt = multiprocessing.Event()
        p = multiprocessing.Process(
            target=io_storm_worker,
            args=(stop_evt, block_size_kb, iterations_per_cycle),
            name=name
        )
        p.start()
        return WorkloadHandle(p, stop_evt, name)

    @staticmethod
    def start_transient_burst(
        name: str = "burst_workload",
        burst_seconds: float = 3.0,
        idle_seconds: float = 5.0
    ) -> WorkloadHandle:
        stop_evt = multiprocessing.Event()
        p = multiprocessing.Process(
            target=transient_burst_worker,
            args=(stop_evt, burst_seconds, idle_seconds),
            name=name
        )
        p.start()
        return WorkloadHandle(p, stop_evt, name)
