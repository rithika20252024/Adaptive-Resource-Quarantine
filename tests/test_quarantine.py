import unittest
from arq.core.process_model import ProcessProfile, QuarantineStage
from arq.core.quarantine_controller import QuarantineController

class TestQuarantineController(unittest.TestCase):
    def setUp(self):
        self.controller = QuarantineController()
        self.profile = ProcessProfile(pid=99999, name="test")

    def test_initial_stage_is_normal(self):
        self.assertEqual(self.profile.stage, QuarantineStage.NORMAL)

    def test_apply_watchlist(self):
        self.controller.apply_stage(self.profile, QuarantineStage.WATCHLIST, reason="test")
        self.assertEqual(self.profile.stage, QuarantineStage.WATCHLIST)
        self.assertEqual(self.profile.quarantine_reason, "test")

    def test_apply_soft_quarantine(self):
        self.controller.apply_stage(self.profile, QuarantineStage.SOFT_QUARANTINE)
        self.assertEqual(self.profile.stage, QuarantineStage.SOFT_QUARANTINE)
        self.assertAlmostEqual(self.profile.enforced_duty_cycle, 0.40)

    def test_apply_hard_quarantine(self):
        self.controller.apply_stage(self.profile, QuarantineStage.HARD_QUARANTINE)
        self.assertEqual(self.profile.stage, QuarantineStage.HARD_QUARANTINE)
        self.assertAlmostEqual(self.profile.enforced_duty_cycle, 0.15)

    def test_release_to_normal(self):
        self.controller.apply_stage(self.profile, QuarantineStage.HARD_QUARANTINE)
        self.controller.apply_stage(self.profile, QuarantineStage.NORMAL)
        self.assertEqual(self.profile.stage, QuarantineStage.NORMAL)
        self.assertAlmostEqual(self.profile.enforced_duty_cycle, 1.0)

    def tearDown(self):
        self.controller.cleanup_all()

if __name__ == "__main__":
    unittest.main()
