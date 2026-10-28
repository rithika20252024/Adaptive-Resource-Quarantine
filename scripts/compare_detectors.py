import json
import numpy as np

from arq.core.anomaly_scorer import AnomalyScorer
from arq.core.ml_training import load_isolation_forest
from arq.core.ml_pipeline import FEATURE_NAMES
from arq.core.process_model import ProcessMetrics, ProcessProfile

DATA = "data/normal_live.jsonl"

with open(DATA, encoding="utf-8") as f:
    rows = [json.loads(line) for line in f if line.strip()]

X = np.asarray([
    [float(row[key]) for key in FEATURE_NAMES]
    for row in rows
])
baseline = np.median(X, axis=0)

models = {
    "Original IF": load_isolation_forest(
        "models/arq/isolation_forest.joblib"
    ),
    "Candidate IF": load_isolation_forest(
        "models/arq-live-test/isolation_forest.joblib"
    ),
}

scenarios = {
    "Baseline": {},
    "High CPU": {"cpu_percent": 100},
    "Rapid memory growth": {"memory_growth_mb_s": 10},
    "Large memory footprint": {
        "memory_rss_mb": 1000,
        "memory_vms_mb": 2000,
    },
    "High disk I/O": {
        "io_read_kb_s": 5000,
        "io_write_kb_s": 5000,
    },
    "High thread count": {"num_threads": 100},
    "Combined stress": {
        "cpu_percent": 100,
        "memory_rss_mb": 1000,
        "memory_vms_mb": 2000,
        "memory_growth_mb_s": 10,
        "io_read_kb_s": 5000,
        "io_write_kb_s": 5000,
        "num_threads": 100,
    },
}

print("Isolation Forest results use each model's own calibration threshold.")
print("Rule scores are raw composite scores, not probabilities.\n")

for scenario, changes in scenarios.items():
    sample = baseline.copy()
    for feature, value in changes.items():
        sample[FEATURE_NAMES.index(feature)] = value

    metrics = ProcessMetrics(
        pid=900001,
        name="offline_test",
        **dict(zip(FEATURE_NAMES, sample.tolist())),
    )

    # Fresh profile per scenario, then repeated evaluations to show
    # the scorer's burst-suppression / EWMA behavior.
    profile = ProcessProfile(pid=900001, name="offline_test")
    rule_scores = []
    scorer = AnomalyScorer()
    for _ in range(5):
        rule_scores.append(scorer.evaluate(profile, metrics))

    print(f"{scenario}:")
    for name, artifact in models.items():
        score = -float(artifact["model"].decision_function([sample])[0])
        threshold = float(artifact["calibration_threshold"])
        print(
            f"  {name:12} score={score: .5f} "
            f"threshold={threshold:.5f} "
            f"flagged={'YES' if score > threshold else 'NO'}"
        )
    print(
        f"  {'Rule scorer':12} score={rule_scores[-1]:.5f} "
        f"(fifth cycle; threshold context: "
        f"{scorer.anomaly_cycle_threshold:.2f})\n"
    )
