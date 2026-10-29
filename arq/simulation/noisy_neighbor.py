"""
Noisy Neighbor Benchmark Environment.
Runs a latency-sensitive benign foreground service alongside aggressive resource consumers,
measuring latency distributions (median, P95, P99) and request throughput degradation.
"""

import multiprocessing
import statistics
import time
from typing import Dict, List


def latency_probe_worker(stop_event, results_queue, request_rate_hz: int = 40) -> None:
    """
    Simulates a latency-critical microservice receiving requests at a regular cadence.
    Measures processing delay for each synthetic transaction.
    """
    interval = 1.0 / max(request_rate_hz, 1)
    latencies: List[float] = []

    while not stop_event.is_set():
        t0 = time.perf_counter()

        # Synthetic computational work unit (e.g. JSON parse, checksum, matrix step)
        acc = 0.0
        for i in range(1200):
            acc += (i * 0.314159) ** 0.5

        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000.0
        latencies.append(latency_ms)

        # Sleep remainder of target interval
        elapsed = t1 - t0
        rem = interval - elapsed
        if rem > 0:
            time.sleep(rem)

    results_queue.put(latencies)


class LatencyProbeService:
    """Manages execution and telemetry gathering for the benign foreground service."""

    def __init__(self, request_rate_hz: int = 40):
        self.request_rate_hz = request_rate_hz
        self.stop_event = multiprocessing.Event()
        self.results_queue = multiprocessing.Queue()
        self.process = multiprocessing.Process(
            target=latency_probe_worker,
            args=(self.stop_event, self.results_queue, self.request_rate_hz),
            name="benign_service"
        )

    def start(self) -> None:
        self.process.start()

    @property
    def pid(self) -> int:
        return self.process.pid or 0

    def stop_and_collect(self) -> List[float]:
        import queue
        self.stop_event.set()
        latencies = []
        if self.process.pid is not None:
            try:
                latencies = self.results_queue.get(timeout=3.0)
            except queue.Empty:
                pass
            self.process.join(timeout=1.0)
            if self.process.is_alive():
                self.process.terminate(); self.process.join(timeout=1.0)
            if self.process.is_alive():
                self.process.kill(); self.process.join(timeout=1.0)
        self.results_queue.close()
        self.results_queue.join_thread()
        return latencies

    @staticmethod
    def compute_stats(latencies: List[float]) -> Dict[str, float]:
        if not latencies:
            return {
                "count": 0,
                "mean": 0.0,
                "median": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "max": 0.0
            }
        sorted_l = sorted(latencies)
        n = len(sorted_l)
        p95_idx = __import__("math").ceil(0.95 * n) - 1
        p99_idx = __import__("math").ceil(0.99 * n) - 1
        return {
            "count": n,
            "mean": round(statistics.mean(sorted_l), 3),
            "median": round(statistics.median(sorted_l), 3),
            "p95": round(sorted_l[min(p95_idx, n - 1)], 3),
            "p99": round(sorted_l[min(p99_idx, n - 1)], 3),
            "max": round(max(sorted_l), 3)
        }
