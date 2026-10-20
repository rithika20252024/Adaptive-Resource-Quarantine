"""Data models and abstractions for process telemetry and quarantine profiling."""

from dataclasses import dataclass, field
from enum import IntEnum
import time
from typing import List


class QuarantineStage(IntEnum):
    """Quarantine lifecycle stages for managed processes."""

    NORMAL = 0
    WATCHLIST = 1
    SOFT_QUARANTINE = 2
    HARD_QUARANTINE = 3
    TERMINATED = 4


@dataclass
class ProcessMetrics:
    """Instantaneous snapshot of process telemetry and resource consumption.

    Attributes:
        pid: Process identifier.
        name: Name or executable command of the process.
        cpu_percent: Estimated CPU utilization percentage over the measurement interval.
        memory_rss_mb: Resident Set Size in megabytes.
        memory_vms_mb: Virtual Memory Size in megabytes.
        memory_growth_mb_s: Rate of RSS change in megabytes per second.
        io_read_kb_s: Disk read rate in kilobytes per second.
        io_write_kb_s: Disk write rate in kilobytes per second.
        num_threads: Number of active threads in the process.
        timestamp: Epoch timestamp when the metric snapshot was taken.
    """

    pid: int
    name: str = ""
    cpu_percent: float = 0.0
    memory_rss_mb: float = 0.0
    memory_vms_mb: float = 0.0
    memory_growth_mb_s: float = 0.0
    io_read_kb_s: float = 0.0
    io_write_kb_s: float = 0.0
    num_threads: int = 1
    timestamp: float = field(default_factory=time.time)


class ProcessProfile:
    """Stateful profile tracking process metrics history, anomaly baselines, and quarantine status.

    Maintains moving averages (EWMA) of resource consumption, historical metric snapshots,
    anomaly score progressions, and current enforcement controls.
    """

    def __init__(
        self,
        pid: int,
        name: str = "",
        stage: QuarantineStage = QuarantineStage.NORMAL,
    ) -> None:
        """Initialize a process profile.

        Args:
            pid: The operating system process ID.
            name: Descriptive process or binary name.
            stage: Initial quarantine stage (defaults to NORMAL).
        """
        self.pid: int = pid
        self.name: str = name
        self.stage: QuarantineStage = stage
        self.ewma_cpu: float = 0.0
        self.ewma_mem: float = 0.0
        self.ewma_io: float = 0.0
        self.consecutive_anomalous_cycles: int = 0
        self.consecutive_normal_cycles: int = 0
        self.current_score: float = 0.0
        self.score_history: List[float] = []
        self.recent_metrics: List[ProcessMetrics] = []
        self.quarantine_reason: str = ""
        self.enforced_duty_cycle: float = 1.0
        self.quarantine_start_time: float = 0.0

    def update_metrics(self, metrics: ProcessMetrics) -> None:
        """Append a new telemetry metric, maintaining a rolling window of up to 10 entries.

        Args:
            metrics: The latest sampled ProcessMetrics instance.
        """
        self.recent_metrics.append(metrics)
        if len(self.recent_metrics) > 10:
            self.recent_metrics.pop(0)

    def record_score(self, score: float) -> None:
        """Record an anomaly score, maintaining a rolling history of up to 50 scores.

        Args:
            score: The composite anomaly score, clamped to [0.0, 1.0].
        """
        self.current_score = score
        self.score_history.append(score)
        if len(self.score_history) > 50:
            self.score_history.pop(0)

    def is_quarantined(self) -> bool:
        """Determine whether the process is currently subject to active quarantine constraints.

        Returns:
            True if in SOFT_QUARANTINE or HARD_QUARANTINE stage, False otherwise.
        """
        return self.stage in (
            QuarantineStage.SOFT_QUARANTINE,
            QuarantineStage.HARD_QUARANTINE,
        )

    def __repr__(self) -> str:
        return (
            f"ProcessProfile(pid={self.pid}, name='{self.name}', "
            f"stage={self.stage.name}, score={self.current_score:.3f}, "
            f"duty_cycle={self.enforced_duty_cycle:.2f})"
        )
