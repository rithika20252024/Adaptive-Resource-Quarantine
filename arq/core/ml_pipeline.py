"""Optional ML anomaly detection for ARQ.

The existing EWMA scorer remains the fallback. ML dependencies are optional.
Models must be trained on representative telemetry before being used.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from arq.core.process_model import ProcessMetrics


FEATURE_NAMES = (
    "cpu_percent",
    "memory_rss_mb",
    "memory_vms_mb",
    "memory_growth_mb_s",
    "io_read_kb_s",
    "io_write_kb_s",
    "num_threads",
)


def extract_features(metrics: ProcessMetrics) -> List[float]:
    """Convert a telemetry snapshot into a finite, non-negative feature vector."""
    values = [
        metrics.cpu_percent,
        metrics.memory_rss_mb,
        metrics.memory_vms_mb,
        metrics.memory_growth_mb_s,
        metrics.io_read_kb_s,
        metrics.io_write_kb_s,
        float(metrics.num_threads),
    ]

    result = []
    for value in values:
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Telemetry features must be finite numbers.")
        result.append(max(0.0, value))

    return result


def _clamp_score(score: float) -> float:
    score = float(score)
    if not math.isfinite(score):
        raise ValueError("Anomaly score must be finite.")
    return max(0.0, min(1.0, score))


def combine_scores(
    rule_score: float,
    isolation_forest_score: Optional[float] = None,
    sequence_score: Optional[float] = None,
    rule_weight: float = 0.50,
    isolation_weight: float = 0.25,
    sequence_weight: float = 0.25,
) -> float:
    """Combine available normalized scores, renormalizing available weights.

    ML scores must already be calibrated to [0, 1], where larger means
    more anomalous. Missing ML models do not disable the rule-based detector.
    """
    weights = (rule_weight, isolation_weight, sequence_weight)
    if any(not math.isfinite(float(w)) or w < 0 for w in weights):
        raise ValueError("Weights must be finite and non-negative.")

    components = [(rule_score, rule_weight)]
    if isolation_forest_score is not None:
        components.append((isolation_forest_score, isolation_weight))
    if sequence_score is not None:
        components.append((sequence_score, sequence_weight))

    total_weight = sum(weight for _, weight in components)
    if total_weight <= 0:
        raise ValueError("At least one available score must have positive weight.")

    return _clamp_score(
        sum(_clamp_score(score) * weight for score, weight in components)
        / total_weight
    )


class HybridMLDetector:
    """Optional detector combining Isolation Forest and sequence reconstruction.

    Pass already-trained model objects. No model is loaded or trained implicitly.
    This makes inference predictable and prevents accidental training during
    live monitoring.
    """

    def __init__(
        self,
        isolation_forest: Any = None,
        sequence_model: Any = None,
        sequence_length: int = 10,
    ) -> None:
        if sequence_length < 2:
            raise ValueError("sequence_length must be at least 2.")
        self.isolation_forest = isolation_forest
        self.sequence_model = sequence_model
        self.sequence_length = sequence_length
        self.history: Dict[int, List[List[float]]] = {}

    def score(self, metrics: ProcessMetrics) -> Dict[str, Optional[float]]:
        features = extract_features(metrics)
        result: Dict[str, Optional[float]] = {
            "isolation_forest": None,
            "sequence": None,
            "ml_score": None,
        }

        if self.isolation_forest is not None:
            # IsolationForest decision_function: lower values are more unusual.
            # This monotonic mapping is a heuristic, not a calibrated probability.
            raw = float(self.isolation_forest.decision_function([features])[0])
            result["isolation_forest"] = _clamp_score(0.5 - raw)

        if self.sequence_model is not None:
            history = self.history.setdefault(metrics.pid, [])
            history.append(features)
            if len(history) > self.sequence_length:
                del history[:-self.sequence_length]

            if len(history) == self.sequence_length:
                try:
                    import torch
                except ImportError as exc:
                    raise RuntimeError(
                        "Sequence scoring requires the optional PyTorch dependency."
                    ) from exc

                self.sequence_model.eval()
                with torch.no_grad():
                    sequence = torch.tensor(
                        [history], dtype=torch.float32
                    )
                    reconstructed = self.sequence_model(sequence)
                    error = torch.mean(
                        (reconstructed - sequence) ** 2
                    ).item()

                # Raw reconstruction error is not calibrated. This simple
                # bounded transform is only a provisional score until a
                # threshold is learned from held-out normal training data.
                result["sequence"] = _clamp_score(error / (1.0 + error))

        available = [
            score for score in (
                result["isolation_forest"], result["sequence"]
            )
            if score is not None
        ]
        if available:
            result["ml_score"] = sum(available) / len(available)

        return result
