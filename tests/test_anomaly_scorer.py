import unittest
from arq.core.process_model import ProcessProfile, ProcessMetrics, QuarantineStage
from arq.core.anomaly_scorer import AnomalyScorer

class TestAnomalyScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = AnomalyScorer()
        self.profile = ProcessProfile(pid=1000, name="test_proc")

    def test_low_usage_returns_low_score(self):
        m = ProcessMetrics(pid=1000, name="test_proc", cpu_percent=5.0, memory_rss_mb=50.0)
        score = self.scorer.evaluate(self.profile, m)
        self.assertLess(score, 0.3)

    def test_high_cpu_returns_high_score(self):
        m = ProcessMetrics(pid=1000, name="test_proc", cpu_percent=98.0, memory_rss_mb=50.0)
        # Need multiple cycles to overcome burst suppression
        for _ in range(5):
            score = self.scorer.evaluate(self.profile, m)
        self.assertGreater(score, 0.5)

    def test_score_range(self):
        m = ProcessMetrics(pid=1000, name="test_proc", cpu_percent=50.0)
        score = self.scorer.evaluate(self.profile, m)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_burst_suppression(self):
        m_high = ProcessMetrics(pid=1000, name="test_proc", cpu_percent=95.0)
        score1 = self.scorer.evaluate(self.profile, m_high)
        # First cycle should be suppressed
        self.assertLess(score1, 0.9)

    def test_ewma_tracking(self):
        m = ProcessMetrics(pid=1000, name="test_proc", cpu_percent=80.0, memory_rss_mb=100.0)
        self.scorer.evaluate(self.profile, m)
        self.assertGreater(self.profile.ewma_cpu, 0.0)

if __name__ == "__main__":
    unittest.main()
