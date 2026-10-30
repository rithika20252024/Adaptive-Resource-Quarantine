import unittest
from types import SimpleNamespace
from unittest.mock import patch
from arq.core.process_model import ProcessProfile,ProcessMetrics
from arq.web.server import ARQDashboardState


class DashboardDecisionTests(unittest.TestCase):
    def run_cycle(self,rule,model=None):
        state=ARQDashboardState(model_path='/missing')
        pid=600001
        state.profiles[pid]=ProcessProfile(pid,name='controlled_fixture')
        state.controller.register(SimpleNamespace(pid=pid,process=SimpleNamespace(is_alive=lambda:True)))
        state.ml_artifact=model
        try:
            m=ProcessMetrics(pid,cpu_percent=100,memory_rss_mb=8,num_threads=1)
            with patch.object(state.monitor,'sample_process',return_value=m),patch.object(state.scorer,'evaluate',return_value=rule),patch('arq.core.quarantine_controller.QuarantineController.apply_stage') as actuate:
                state.cycle();row=state.history[-1]['processes'][0];actuate.assert_not_called()
            return row
        finally:state.controller.close()

    def test_high_rule_proposal_visible_without_dry_run_actuation(self):
        row=self.run_cycle(.79)
        self.assertEqual(row['policy_stage'],'SOFT_QUARANTINE')
        self.assertEqual(row['stage'],'NORMAL')
        self.assertEqual(row['control_status'],'dry_run')
        self.assertEqual(row['duty_cycle'],1)
        self.assertTrue(row['managed'])

    def test_shadow_flag_does_not_escalate_low_rule(self):
        row=self.run_cycle(.02,{'model':SimpleNamespace(decision_function=lambda x:[-5]),'calibration_threshold':1})
        self.assertTrue(row['ml_anomaly'])
        self.assertEqual(row['ml_margin'],4)
        self.assertEqual(row['ml_raw_score'],5)
        self.assertEqual(row['ml_threshold'],1)
        self.assertEqual(row['policy_stage'],'NORMAL')
        self.assertEqual(row['decision_score'],.02)

    def test_failed_ml_inference_does_not_leave_partial_scores(self):
        row=self.run_cycle(.79,{'model':SimpleNamespace(decision_function=lambda x:[float('nan')]),'calibration_threshold':1})
        for key in ['ml_score','ml_raw_score','ml_threshold','ml_margin','ml_anomaly']:self.assertIsNone(row[key])
        self.assertEqual(row['policy_stage'],'SOFT_QUARANTINE')
