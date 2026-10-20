"""Multi-dimensional anomaly scoring engine with EWMA smoothing and dominant vector boost."""

import math
from typing import Tuple

from arq.core.process_model import ProcessMetrics, ProcessProfile


class AnomalyScorer:
    """Evaluates multi-dimensional telemetry vectors against adaptive resource baselines.

    Implements sigmoidal CPU scaling, memory growth rate and absolute footprint penalties,
    disk I/O saturation metrics, burst transient suppression, and dominant vector boost
    to isolate pathological processes accurately.
    """

    def __init__(
        self,
        cpu_threshold: float = 75.0,
        mem_growth_threshold: float = 50.0,
        mem_abs_threshold: float = 1024.0,
        io_threshold: float = 10000.0,
        alpha_ewma: float = 0.25,
        burst_tolerance_cycles: int = 3,
        weights: Tuple[float, float, float, float] = (0.40, 0.35, 0.15, 0.10),
        scale: float = 10.0,
        anomaly_cycle_threshold: float = 0.50,
    ) -> None:
        """Initialize the AnomalyScorer.

        Args:
            cpu_threshold: CPU percentage inflection threshold for the sigmoid curve.
            mem_growth_threshold: Memory expansion rate in MB/s representing a critical leak.
            mem_abs_threshold: Absolute resident memory size in MB considered heavy consumption.
            io_threshold: Aggregate disk read + write throughput in KB/s representing saturation.
            alpha_ewma: Smoothing factor for exponentially weighted moving averages [0.0, 1.0].
            burst_tolerance_cycles: Number of initial anomalous cycles permitted before full score.
            weights: Tuple of (w_cpu, w_mem, w_io, w_burst) weights summing to 1.0.
            scale: Sigmoidal curvature scaling denominator.
            anomaly_cycle_threshold: Score cutoff for designating an observation cycle anomalous.
        """
        self.cpu_threshold: float = cpu_threshold
        self.mem_growth_threshold: float = mem_growth_threshold
        self.mem_abs_threshold: float = mem_abs_threshold
        self.io_threshold: float = io_threshold
        self.alpha_ewma: float = alpha_ewma
        self.burst_tolerance_cycles: int = burst_tolerance_cycles
        self.weights: Tuple[float, float, float, float] = weights
        self.scale: float = scale
        self.anomaly_cycle_threshold: float = anomaly_cycle_threshold

    def evaluate(self, profile: ProcessProfile, metrics: ProcessMetrics) -> float:
        """Evaluate process telemetry against historical profile and compute composite anomaly score.

        Execution steps:
        1. Update EWMA baselines on profile (ewma_cpu, ewma_mem, ewma_io).
        2. CPU scoring: Sigmoidal S_cpu = 1 / (1 + exp(-(cpu - threshold) / scale)).
        3. Memory scoring: S_mem = max(growth_rate / threshold, 0.7 * rss / abs_threshold), capped at 1.0.
        4. I/O scoring: S_io = min(1.0, total_io / threshold).
        5. Burst scoring: S_burst = min(1.0, |cpu - ewma_cpu| / 80.0).
        6. Composite scoring: raw = w_cpu * S_cpu + w_mem * S_mem + w_io * S_io + w_burst * S_burst.
        7. Dominant vector boost: raw = max(raw, max(S_cpu, S_mem_growth, S_io) * 0.85).
        8. Burst suppression: if consecutive_anomalous_cycles < burst_tolerance and raw < 0.90, scale by 0.65.
        9. Update cycle counters, record score, and return clamped effective score in [0.0, 1.0].

        Args:
            profile: The persistent ProcessProfile tracking the process.
            metrics: The latest sampled ProcessMetrics instance.

        Returns:
            Effective composite anomaly score clamped between 0.0 (benign) and 1.0 (critical).
        """
        total_io = max(0.0, metrics.io_read_kb_s + metrics.io_write_kb_s)

        # 1. Update EWMA baselines on profile
        if not profile.recent_metrics and profile.ewma_cpu == 0.0:
            profile.ewma_cpu = metrics.cpu_percent
            profile.ewma_mem = metrics.memory_rss_mb
            profile.ewma_io = total_io
        else:
            profile.ewma_cpu = (
                self.alpha_ewma * metrics.cpu_percent
                + (1.0 - self.alpha_ewma) * profile.ewma_cpu
            )
            profile.ewma_mem = (
                self.alpha_ewma * metrics.memory_rss_mb
                + (1.0 - self.alpha_ewma) * profile.ewma_mem
            )
            profile.ewma_io = (
                self.alpha_ewma * total_io
                + (1.0 - self.alpha_ewma) * profile.ewma_io
            )

        # 2. CPU scoring: sigmoidal S_cpu = 1 / (1 + exp(-(cpu - threshold) / scale))
        z = - (metrics.cpu_percent - self.cpu_threshold) / self.scale
        # Guard against math overflow in exp
        z_clamped = max(-60.0, min(60.0, z))
        s_cpu = 1.0 / (1.0 + math.exp(z_clamped))

        # 3. Memory scoring: S_mem = max(growth_rate / threshold, 0.7 * rss / abs_threshold), capped at 1.0
        s_mem_growth = min(1.0, max(0.0, metrics.memory_growth_mb_s / self.mem_growth_threshold))
        s_mem_abs = min(1.0, max(0.0, 0.7 * (metrics.memory_rss_mb / self.mem_abs_threshold)))
        s_mem = min(1.0, max(s_mem_growth, s_mem_abs))

        # 4. IO scoring: S_io = min(1.0, total_io / threshold)
        s_io = min(1.0, max(0.0, total_io / self.io_threshold))

        # 5. Burst scoring: S_burst = min(1.0, |cpu - ewma_cpu| / 80.0)
        s_burst = min(1.0, max(0.0, abs(metrics.cpu_percent - profile.ewma_cpu) / 80.0))

        # 6. Composite calculation
        w_cpu, w_mem, w_io, w_burst = self.weights
        raw = (w_cpu * s_cpu) + (w_mem * s_mem) + (w_io * s_io) + (w_burst * s_burst)

        # 7. Dominant vector boost: raw = max(raw, max(S_cpu, S_mem_growth, S_io) * 0.85)
        dominant_vector = max(s_cpu, s_mem_growth, s_io)
        raw = max(raw, dominant_vector * 0.85)

        # 8. Burst suppression: if consecutive_anomalous_cycles < burst_tolerance AND raw < 0.90, multiply by 0.65
        if profile.consecutive_anomalous_cycles < self.burst_tolerance_cycles and raw < 0.90:
            raw *= 0.65

        # 9. Effective score clamped to [0.0, 1.0]
        effective_score = max(0.0, min(1.0, raw))

        # Update cycle counters
        if effective_score >= self.anomaly_cycle_threshold:
            profile.consecutive_anomalous_cycles += 1
            profile.consecutive_normal_cycles = 0
        else:
            profile.consecutive_normal_cycles += 1
            profile.consecutive_anomalous_cycles = 0

        # Update metrics history & record score
        profile.update_metrics(metrics)
        profile.record_score(effective_score)

        return effective_score
