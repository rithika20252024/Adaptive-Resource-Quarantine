import json
import numpy as np

from arq.core.ml_training import load_isolation_forest
from arq.core.ml_pipeline import FEATURE_NAMES

DATA = "data/normal_live.jsonl"
MODELS = {
    "Original": "models/arq/isolation_forest.joblib",
    "Candidate": "models/arq-live-test/isolation_forest.joblib",
}

with open(DATA, encoding="utf-8") as f:
    rows = [json.loads(line) for line in f if line.strip()]

X = np.asarray([
    [float(row[key]) for key in FEATURE_NAMES]
    for row in rows
])

baseline = np.median(X, axis=0)

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

artifacts = {
    name: load_isolation_forest(path)
    for name, path in MODELS.items()
}

print(f"Normal observations: {len(X)}")
print("\nNormal telemetry flag rates:")

for name, artifact in artifacts.items():
    model = artifact["model"]
    threshold = float(artifact["calibration_threshold"])
    scores = -model.decision_function(X)
    flagged = int(np.sum(scores > threshold))
    print(
        f"  {name:10}: {flagged}/{len(X)} "
        f"({100 * flagged / len(X):.1f}%)"
    )

print("\nSynthetic scenario results:")
for scenario, changes in scenarios.items():
    sample = baseline.copy()

    for feature, value in changes.items():
        sample[FEATURE_NAMES.index(feature)] = value

    print(f"\n{scenario}:")
    for name, artifact in artifacts.items():
        score = -float(
            artifact["model"].decision_function([sample])[0]
        )
        threshold = float(artifact["calibration_threshold"])
        print(
            f"  {name:10}: score={score: .5f}, "
            f"threshold={threshold:.5f}, "
            f"flagged={'YES' if score > threshold else 'NO'}"
        )

print(
    "\nNote: synthetic scenarios are exploratory tests, not "
    "proof of real-world detection accuracy."
)
