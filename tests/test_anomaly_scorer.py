"""
Unit tests for Anomaly Scoring Engine.
"""

import unittest
from arq.core.process_model import ProcessProfile, ProcessMetrics
from arq.core.anomaly_scorer import AnomalyScorer

class TestAnomalyScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = AnomalyScorer(cpu_threshold=70.0, burst_tolerance_cycles=2)

    def test_normal_metrics_score_low(self):
        profile = ProcessProfile(pid=100, name="test_normal")
        m = ProcessMetrics(pid=100, name="test_normal", cpu_percent=5.0, memory_rss_mb=25.0)
        score = self.scorer.evaluate(profile, m)
        self.assertLess(score, 0.40)

    def test_sustained_high_cpu_score_high(self):
        profile = ProcessProfile(pid=101, name="test_burner")
        m = ProcessMetrics(pid=101, name="test_burner", cpu_percent=98.0, memory_rss_mb=40.0)
        
        # Feed sustained high CPU cycles
        scores = [self.scorer.evaluate(profile, m) for _ in range(4)]
        self.assertGreaterEqual(scores[-1], 0.60)

    def test_burst_tolerance_dampening(self):
        # A single sudden spike should be dampened below 0.65
        profile = ProcessProfile(pid=102, name="test_spike")
        m_normal = ProcessMetrics(pid=102, name="test_spike", cpu_percent=5.0, memory_rss_mb=20.0)
        self.scorer.evaluate(profile, m_normal)
        
        m_burst = ProcessMetrics(pid=102, name="test_spike", cpu_percent=85.0, memory_rss_mb=20.0)
        first_burst_score = self.scorer.evaluate(profile, m_burst)
        self.assertLess(first_burst_score, 0.65)

if __name__ == "__main__":
    unittest.main()
