import math
import unittest

from arq.core.ml_pipeline import (
    HybridMLDetector,
    combine_scores,
    extract_features,
)
from arq.core.process_model import ProcessMetrics


class TestMLPipeline(unittest.TestCase):
    def test_feature_extraction(self):
        metrics = ProcessMetrics(
            pid=123,
            cpu_percent=40,
            memory_rss_mb=200,
            memory_vms_mb=300,
            memory_growth_mb_s=2,
            io_read_kb_s=10,
            io_write_kb_s=20,
            num_threads=4,
        )
        features = extract_features(metrics)
        self.assertEqual(len(features), 7)
        self.assertEqual(features[0], 40)
        self.assertEqual(features[-1], 4)

    def test_non_finite_feature_rejected(self):
        metrics = ProcessMetrics(pid=123, cpu_percent=float("nan"))
        with self.assertRaises(ValueError):
            extract_features(metrics)

    def test_rule_score_fallback(self):
        self.assertAlmostEqual(combine_scores(0.8), 0.8)

    def test_hybrid_score(self):
        score = combine_scores(0.8, 0.4, 0.6)
        self.assertAlmostEqual(score, 0.65)

    def test_score_is_clamped(self):
        self.assertEqual(combine_scores(1.5), 1.0)
        self.assertEqual(combine_scores(-1.0), 0.0)

    def test_invalid_weights_rejected(self):
        with self.assertRaises(ValueError):
            combine_scores(0.5, rule_weight=-1)

    def test_detector_without_models(self):
        detector = HybridMLDetector()
        result = detector.score(ProcessMetrics(pid=123, cpu_percent=25))
        self.assertIsNone(result["isolation_forest"])
        self.assertIsNone(result["sequence"])
        self.assertIsNone(result["ml_score"])


if __name__ == "__main__":
    unittest.main()
