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
from typing import List, Dict

def cpu_burner_worker(stop_event, intensity: float = 1.0):
    """Monopolize CPU core using mathematical computation."""
    while not stop_event.is_set():
        # Busy loop
        val = 0.0
        for i in range(10000):
            val += math.sin(i) * math.cos(i)

def memory_leaker_worker(stop_event, chunk_mb: int = 15, interval_s: float = 0.5, max_mb: int = 500):
    """Continuously allocate and retain memory chunks."""
    chunks = []
    total_allocated = 0
    while not stop_event.is_set():
        if total_allocated < max_mb:
            # Allocate chunk
            chunk = bytearray(chunk_mb * 1024 * 1024)
            # Touch pages to force physical RSS allocation
            for idx in range(0, len(chunk), 4096):
                chunk[idx] = 1
            chunks.append(chunk)
            total_allocated += chunk_mb
        time.sleep(interval_s)

def io_storm_worker(stop_event, block_size_kb: int = 64, iterations_per_cycle: int = 50):
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
            os.rmdir(temp_dir)
        except Exception:
            pass

def transient_burst_worker(stop_event, burst_seconds: float = 3.0, idle_seconds: float = 5.0):
    """Simulates realistic application bursting (e.g. gcc compilation, code linters)."""
    while not stop_event.is_set():
        # Phase 1: Heavy burst
        t_end = time.time() + burst_seconds
        while time.time() < t_end and not stop_event.is_set():
            v = math.sqrt(1234567.89) * math.atan(45.67)
        # Phase 2: Natural idle
        t_idle = time.time() + idle_seconds
        while time.time() < t_idle and not stop_event.is_set():
            time.sleep(0.1)

class WorkloadHandle:
    """Represents a running simulated workload subprocess."""
    def __init__(self, process: multiprocessing.Process, stop_event, name: str):
        self.process = process
        self.stop_event = stop_event
        self.name = name

    @property
    def pid(self) -> int:
        return self.process.pid or 0

    def stop(self):
        self.stop_event.set()
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=1.0)


class WorkloadSimulator:
    """Factory for spinning up isolated stress workloads."""
    @staticmethod
    def start_cpu_burner(name: str = "cpu_burner") -> WorkloadHandle:
        stop_evt = multiprocessing.Event()
        p = multiprocessing.Process(target=cpu_burner_worker, args=(stop_evt,), name=name)
        p.start()
        return WorkloadHandle(p, stop_evt, name)

    @staticmethod
    def start_memory_leaker(name: str = "mem_leaker", chunk_mb: int = 15, max_mb: int = 400) -> WorkloadHandle:
        stop_evt = multiprocessing.Event()
        p = multiprocessing.Process(target=memory_leaker_worker, args=(stop_evt, chunk_mb, 0.4, max_mb), name=name)
        p.start()
        return WorkloadHandle(p, stop_evt, name)

    @staticmethod
    def start_io_storm(name: str = "io_storm") -> WorkloadHandle:
        stop_evt = multiprocessing.Event()
        p = multiprocessing.Process(target=io_storm_worker, args=(stop_evt,), name=name)
        p.start()
        return WorkloadHandle(p, stop_evt, name)

    @staticmethod
    def start_transient_burst(name: str = "burst_workload", burst_seconds: float = 2.5) -> WorkloadHandle:
        stop_evt = multiprocessing.Event()
        p = multiprocessing.Process(target=transient_burst_worker, args=(stop_evt, burst_seconds, 6.0), name=name)
        p.start()
        return WorkloadHandle(p, stop_evt, name)
