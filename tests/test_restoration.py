import unittest
from arq.core.process_model import ProcessProfile, ProcessMetrics, QuarantineStage
from arq.core.quarantine_controller import QuarantineController
from arq.core.restoration_engine import RestorationEngine
from arq.core.anomaly_scorer import AnomalyScorer

class TestRestorationEngine(unittest.TestCase):
    def setUp(self):
        self.controller = QuarantineController()
        self.restoration = RestorationEngine(self.controller, hysteresis_cycles=2)
        self.scorer = AnomalyScorer(cpu_threshold=60.0, burst_tolerance_cycles=1)
        self.profile = ProcessProfile(pid=99999, name="test")

    def test_escalation_on_high_score(self):
        stage, action = self.restoration.process_cycle(self.profile, 0.70)
        self.assertIn(stage, [QuarantineStage.WATCHLIST, QuarantineStage.SOFT_QUARANTINE])

    def test_stays_normal_on_low_score(self):
        stage, action = self.restoration.process_cycle(self.profile, 0.10)
        self.assertEqual(stage, QuarantineStage.NORMAL)

    def test_recovery_requires_hysteresis(self):
        # Escalate first
        self.restoration.process_cycle(self.profile, 0.90)
        self.restoration.process_cycle(self.profile, 0.90)
        # Now try recovery - should need multiple low cycles
        self.restoration.process_cycle(self.profile, 0.10)
        # After 1 cycle it may not fully recover yet
        stage, _ = self.restoration.process_cycle(self.profile, 0.10)
        # With hysteresis=2, should step down after 2 low cycles
        self.assertNotEqual(stage, QuarantineStage.HARD_QUARANTINE)

    def tearDown(self):
        self.controller.cleanup_all()

if __name__ == "__main__":
    unittest.main()
