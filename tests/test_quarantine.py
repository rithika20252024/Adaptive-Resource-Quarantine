"""
Unit tests for Quarantine Controller and Duty Cycle logic.
"""

import multiprocessing
import os
import time
import unittest
from arq.core.process_model import ProcessProfile, QuarantineStage
from arq.core.quarantine_controller import QuarantineController

def dummy_worker():
    while True:
        time.sleep(0.1)

class TestQuarantineController(unittest.TestCase):
    def setUp(self):
        self.child = multiprocessing.Process(target=dummy_worker)
        self.child.start()
        self.controller = QuarantineController()
        self.profile = ProcessProfile(pid=self.child.pid, name="child_proc")

    def tearDown(self):
        self.controller.cleanup_all()
        if self.child.is_alive():
            self.child.terminate()
            self.child.join(timeout=1.0)

    def test_stage_transitions(self):
        # Soft quarantine
        changed = self.controller.apply_stage(self.profile, QuarantineStage.SOFT_QUARANTINE, reason="Test soft")
        self.assertTrue(changed)
        self.assertEqual(self.profile.stage, QuarantineStage.SOFT_QUARANTINE)
        self.assertEqual(self.profile.enforced_duty_cycle, 0.40)

        # Re-applying same stage should return False
        changed2 = self.controller.apply_stage(self.profile, QuarantineStage.SOFT_QUARANTINE)
        self.assertFalse(changed2)

        # Hard quarantine
        changed3 = self.controller.apply_stage(self.profile, QuarantineStage.HARD_QUARANTINE, reason="Test hard")
        self.assertTrue(changed3)
        self.assertEqual(self.profile.stage, QuarantineStage.HARD_QUARANTINE)
        self.assertEqual(self.profile.enforced_duty_cycle, 0.15)

        # Restoration to NORMAL
        changed4 = self.controller.apply_stage(self.profile, QuarantineStage.NORMAL)
        self.assertTrue(changed4)
        self.assertEqual(self.profile.stage, QuarantineStage.NORMAL)
        self.assertEqual(self.profile.enforced_duty_cycle, 1.0)

if __name__ == "__main__":
    unittest.main()
