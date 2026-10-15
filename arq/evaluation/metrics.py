"""
Performance evaluation metrics definitions.
Fulfills Project Objective 6: evaluating CPU, Memory, Response Time, I/O, Recovery Time, and State Loss.
"""

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class BenchmarkResult:
    """
    Summary of evaluation metrics for a specific isolation strategy.
    """
    strategy_name: str
    duration_s: float
    total_requests: int
    mean_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_rps: float
    target_process_completed: bool
    state_loss_rate_pct: float
    recovery_time_s: float
    peak_cpu_percent: float
    peak_memory_mb: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy_name,
            "duration_s": round(self.duration_s, 2),
            "requests": self.total_requests,
            "mean_latency_ms": self.mean_latency_ms,
            "median_latency_ms": self.median_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "throughput_rps": round(self.throughput_rps, 1),
            "process_survived": self.target_process_completed,
            "state_loss_pct": self.state_loss_rate_pct,
            "recovery_time_s": round(self.recovery_time_s, 2),
            "peak_cpu_pct": round(self.peak_cpu_percent, 1),
            "peak_mem_mb": round(self.peak_memory_mb, 1)
        }
