"""
Multi-Dimensional Composite Anomaly Scoring Engine.
Calculates continuous anomaly scores across CPU, Memory growth, I/O rates,
and distinguishes transient application bursts from sustained malicious resource exhaustion.
"""

import math
from typing import Dict, Tuple
from arq.core.process_model import ProcessMetrics, ProcessProfile, QuarantineStage

class AnomalyScorer:
    """
    Computes normalized anomaly score S in [0.0, 1.0] using multi-vector telemetry,
    EWMA baseline tracking, and transient burst suppression.
    """
    def __init__(
        self,
        cpu_threshold: float = 75.0,        # CPU % indicating elevated strain
        mem_growth_threshold: float = 50.0, # MB/s growth rate indicating memory leak
        mem_abs_threshold: float = 1024.0,  # Absolute RSS threshold (1 GB)
        io_threshold: float = 10000.0,      # KB/s I/O rate threshold (10 MB/s)
        alpha_ewma: float = 0.25,           # Smoothing factor for EWMA baseline
        burst_tolerance_cycles: int = 3,    # Ignore transient spikes under N cycles
        weights: Tuple[float, float, float, float] = (0.40, 0.35, 0.15, 0.10) # CPU, Mem, I/O, Burst
    ):
        self.cpu_threshold = cpu_threshold
        self.mem_growth_threshold = mem_growth_threshold
        self.mem_abs_threshold = mem_abs_threshold
        self.io_threshold = io_threshold
        self.alpha_ewma = alpha_ewma
        self.burst_tolerance_cycles = burst_tolerance_cycles
        
        # Normalize weights
        total_w = sum(weights)
        self.w_cpu = weights[0] / total_w
        self.w_mem = weights[1] / total_w
        self.w_io = weights[2] / total_w
        self.w_burst = weights[3] / total_w

    def evaluate(self, profile: ProcessProfile, metrics: ProcessMetrics) -> float:
        """
        Evaluate current metrics against profile history and calculate composite anomaly score.
        """
        profile.update_metrics(metrics)

        # 1. Update EWMA Baselines
        if profile.ewma_cpu == 0.0:
            profile.ewma_cpu = metrics.cpu_percent
            profile.ewma_mem = metrics.memory_rss_mb
            profile.ewma_io = metrics.io_read_kb_s + metrics.io_write_kb_s
        else:
            profile.ewma_cpu = (self.alpha_ewma * metrics.cpu_percent) + ((1.0 - self.alpha_ewma) * profile.ewma_cpu)
            profile.ewma_mem = (self.alpha_ewma * metrics.memory_rss_mb) + ((1.0 - self.alpha_ewma) * profile.ewma_mem)
            profile.ewma_io = (self.alpha_ewma * (metrics.io_read_kb_s + metrics.io_write_kb_s)) + ((1.0 - self.alpha_ewma) * profile.ewma_io)

        # 2. Individual Vector Anomaly Functions (Sigmoidal / Saturating)
        # CPU Vector
        s_cpu = self._compute_sigmoid_score(metrics.cpu_percent, self.cpu_threshold, scale=15.0)
        
        # Memory Vector (Growth Rate + Absolute Footprint)
        s_mem_growth = min(1.0, metrics.memory_growth_mb_s / self.mem_growth_threshold) if self.mem_growth_threshold > 0 else 0.0
        s_mem_abs = min(1.0, metrics.memory_rss_mb / self.mem_abs_threshold) if self.mem_abs_threshold > 0 else 0.0
        s_mem = max(s_mem_growth, s_mem_abs * 0.7)

        # I/O Vector
        total_io = metrics.io_read_kb_s + metrics.io_write_kb_s
        s_io = min(1.0, total_io / self.io_threshold) if self.io_threshold > 0 else 0.0

        # Burst Dynamics & Volatility Vector
        # If variance between instantaneous CPU and EWMA is huge, but cycle count is low, it's a burst!
        cpu_diff = abs(metrics.cpu_percent - profile.ewma_cpu)
        s_burst = min(1.0, cpu_diff / 80.0)

        # 3. Composite Anomaly Score with Dominant Vector Consideration
        # Allows multi-metric sensitivity while capturing single runaway vectors (pure CPU burners, memory leaks)
        weighted_score = (self.w_cpu * s_cpu) + (self.w_mem * s_mem) + (self.w_io * s_io) + (self.w_burst * s_burst)
        dominant_vector = max(s_cpu, s_mem_growth, s_io)
        raw_score = max(weighted_score, dominant_vector * 0.85)

        # 4. Burst Suppression Filter
        # If raw score is high, increment anomalous cycle counter; else decrement
        if raw_score >= 0.55:
            profile.consecutive_anomalous_cycles += 1
            profile.consecutive_normal_cycles = 0
        else:
            profile.consecutive_normal_cycles += 1
            profile.consecutive_anomalous_cycles = max(0, profile.consecutive_anomalous_cycles - 1)

        # If it's a transient spike (within burst tolerance window), suppress severe quarantine
        if profile.consecutive_anomalous_cycles < self.burst_tolerance_cycles and raw_score < 0.90:
            effective_score = raw_score * 0.65  # Dampen score to avoid premature quarantine
        else:
            effective_score = raw_score

        effective_score = round(max(0.0, min(1.0, effective_score)), 3)
        profile.record_score(effective_score)
        return effective_score

    def _compute_sigmoid_score(self, value: float, threshold: float, scale: float = 10.0) -> float:
        """
        Sigmoidal transfer function mapping continuous metrics to [0, 1].
        Centering at threshold ensures smooth transition rather than cliff-edge.
        """
        if value <= 0:
            return 0.0
        z = (value - threshold) / max(scale, 1.0)
        return 1.0 / (1.0 + math.exp(-z))
