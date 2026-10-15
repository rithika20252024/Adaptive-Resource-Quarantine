"""
Data models and state representations for processes under monitoring and quarantine.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Dict, Optional
import time

class QuarantineStage(IntEnum):
    """
    Graduated lifecycle states of a monitored process.
    """
    NORMAL = 0             # Baseline execution; standard OS priority
    WATCHLIST = 1          # Minor behavioral deviation; heightened telemetry
    SOFT_QUARANTINE = 2    # Moderate throttle: nice +10, 40% CPU duty limit, low I/O
    HARD_QUARANTINE = 3    # Severe throttle: nice +19, 15% CPU duty limit, aggressive delay
    TERMINATION_PENDING = 4# Persistence timeout exceeded; flagged for admin/safe kill
    TERMINATED = 5         # Process terminated due to unresolvable malicious runaway
    RELEASED = 6           # Successfully recovered back to normal operations

@dataclass
class ProcessMetrics:
    """
    Point-in-time telemetry snapshot for a specific process.
    """
    pid: int
    name: str
    cpu_percent: float = 0.0          # Instantaneous CPU utilization (%)
    memory_rss_mb: float = 0.0        # Resident Set Size in MegaBytes
    memory_vms_mb: float = 0.0        # Virtual Memory Size in MegaBytes
    memory_growth_mb_s: float = 0.0   # Rate of RSS growth (MB/s)
    io_read_kb_s: float = 0.0         # Disk read throughput (KB/s)
    io_write_kb_s: float = 0.0        # Disk write throughput (KB/s)
    num_threads: int = 1              # Thread count
    timestamp: float = field(default_factory=time.time)

@dataclass
class ProcessProfile:
    """
    Long-term behavioral profile and tracking state for an individual process.
    """
    pid: int
    name: str
    create_time: float = field(default_factory=time.time)
    stage: QuarantineStage = QuarantineStage.NORMAL
    
    # Anomaly Scoring History
    current_score: float = 0.0
    score_history: List[float] = field(default_factory=list)
    recent_metrics: List[ProcessMetrics] = field(default_factory=list)
    
    # Moving Average Baselines (EWMA)
    ewma_cpu: float = 0.0
    ewma_mem: float = 0.0
    ewma_io: float = 0.0
    
    # Adaptive State Machine Counters
    consecutive_anomalous_cycles: int = 0
    consecutive_normal_cycles: int = 0
    quarantine_start_time: Optional[float] = None
    quarantine_total_duration: float = 0.0
    quarantine_reason: str = ""
    
    # State flags
    is_whitelisted: bool = False
    original_nice: int = 0
    enforced_duty_cycle: float = 1.0  # 1.0 = unrestricted (100%), 0.2 = 20% CPU duty cycle

    def update_metrics(self, metric: ProcessMetrics, max_history: int = 30):
        """Append metric and maintain sliding window."""
        self.recent_metrics.append(metric)
        if len(self.recent_metrics) > max_history:
            self.recent_metrics.pop(0)

    def record_score(self, score: float, max_history: int = 50):
        """Record anomaly score and maintain history."""
        self.current_score = score
        self.score_history.append(score)
        if len(self.score_history) > max_history:
            self.score_history.pop(0)

    def is_quarantined(self) -> bool:
        return self.stage in (QuarantineStage.SOFT_QUARANTINE, QuarantineStage.HARD_QUARANTINE)
