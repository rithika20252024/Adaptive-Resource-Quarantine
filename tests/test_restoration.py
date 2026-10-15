"""
Unit tests for Dynamic Restoration Engine and Hysteresis.
"""

import multiprocessing
import os
import time
import unittest
from arq.core.process_model import ProcessProfile, QuarantineStage
from arq.core.quarantine_controller import QuarantineController
from arq.core.restoration_engine import RestorationEngine

def dummy_worker():
    while True:
        time.sleep(0.1)

class TestRestorationEngine(unittest.TestCase):
    def setUp(self):
        self.child = multiprocessing.Process(target=dummy_worker)
        self.child.start()
        self.controller = QuarantineController()
        self.restoration = RestorationEngine(self.controller, hysteresis_cycles=2, recovery_score_threshold=0.35)
        self.profile = ProcessProfile(pid=self.child.pid, name="test_child")

    def tearDown(self):
        self.controller.cleanup_all()
        if self.child.is_alive():
            self.child.terminate()
            self.child.join(timeout=1.0)

    def test_escalation_to_soft_and_hard(self):
        # Soft escalation
        stage, text = self.restoration.process_cycle(self.profile, current_score=0.70)
        self.assertEqual(stage, QuarantineStage.SOFT_QUARANTINE)

        # Hard escalation
        stage, text = self.restoration.process_cycle(self.profile, current_score=0.90)
        self.assertEqual(stage, QuarantineStage.HARD_QUARANTINE)

    def test_hysteresis_step_down(self):
        # Escalate to SOFT
        self.restoration.process_cycle(self.profile, current_score=0.70)
        self.assertEqual(self.profile.stage, QuarantineStage.SOFT_QUARANTINE)

        # Cycle 1 with low score: should NOT step down yet (hysteresis = 2)
        self.profile.consecutive_normal_cycles = 1
        stage, text = self.restoration.process_cycle(self.profile, current_score=0.10)
        self.assertEqual(stage, QuarantineStage.SOFT_QUARANTINE)

        # Cycle 2 with low score: now reaches hysteresis target (2), should step down to WATCHLIST
        self.profile.consecutive_normal_cycles = 2
        stage, text = self.restoration.process_cycle(self.profile, current_score=0.10)
        self.assertEqual(stage, QuarantineStage.WATCHLIST)

if __name__ == "__main__":
    unittest.main()
