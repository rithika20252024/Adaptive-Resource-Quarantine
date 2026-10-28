from arq.core.anomaly_scorer import AnomalyScorer
from arq.core.process_model import ProcessMetrics, ProcessProfile

scenarios = {
    "Normal baseline": {
        "cpu_percent": 5,
        "memory_rss_mb": 50,
        "memory_vms_mb": 100,
        "memory_growth_mb_s": 0,
        "io_read_kb_s": 0,
        "io_write_kb_s": 0,
        "num_threads": 1,
    },
    "High CPU": {"cpu_percent": 100},
    "Rapid memory growth": {"memory_growth_mb_s": 10},
    "Large memory footprint": {"memory_rss_mb": 1000},
    "High disk I/O": {"io_read_kb_s": 5000, "io_write_kb_s": 5000},
    "High thread count": {"num_threads": 100},
}

defaults = {
    "cpu_percent": 5,
    "memory_rss_mb": 50,
    "memory_vms_mb": 100,
    "memory_growth_mb_s": 0,
    "io_read_kb_s": 0,
    "io_write_kb_s": 0,
    "num_threads": 1,
}

print("Rule scorer feature-isolation evaluation")
print("Cycle threshold: 0.50")
print("Each scenario starts with a fresh process profile.\n")

for name, changes in scenarios.items():
    values = defaults.copy()
    values.update(changes)

    scorer = AnomalyScorer()
    profile = ProcessProfile(pid=900001, name="offline_test")
    scores = []

    for _ in range(5):
        metrics = ProcessMetrics(
            pid=900001,
            name="offline_test",
            **values,
        )
        scores.append(scorer.evaluate(profile, metrics))

    print(
        f"{name:24} "
        f"first={scores[0]:.3f} "
        f"fifth={scores[-1]:.3f} "
        f"above_0.50={'YES' if scores[-1] >= 0.50 else 'NO'}"
    )
