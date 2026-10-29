import unittest
from dataclasses import replace
from arq.core.recovery_probe import RecoveryProbe, ProbePolicy, Window, ExistingThrottlerAdapter


class TestRecoveryProbe(unittest.TestCase):
    def run_case(self, demand=.2, latency=10, mutate=None, policy=None):
        applied, windows = [], []
        def observe(duty, duration):
            phase = len(windows) % 3
            w = Window('42:created-123', duty, duration,
                       min(demand, duty)*duration, (latency if phase == 1 else 10,)*30, 100)
            if mutate:
                w = mutate(w, phase)
            windows.append(w)
            return w
        result = RecoveryProbe(policy or ProbePolicy()).run(
            '42:created-123', .15, .4, applied.append, observe)
        return result, applied

    def test_recovered_demand_commits_after_two_complete_brackets(self):
        r, a = self.run_case()
        self.assertTrue(r.accepted)
        self.assertEqual(a, [.15,.4,.15,.15,.4,.15,.15,.4])
        self.assertEqual(len(r.trace), 6)

    def test_throttled_cpu_is_not_recovery(self):
        r, a = self.run_case(demand=1)
        self.assertEqual(r.reason, 'restriction_masked_demand')
        self.assertEqual(a[-1], .15)

    def test_protected_harm_rejects_even_below_absolute_slo(self):
        self.assertEqual(self.run_case(latency=13)[0].reason,
                         'release_harms_protected_service')

    def test_absolute_slo_rejects(self):
        self.assertEqual(self.run_case(latency=21)[0].reason, 'protected_slo_exceeded')

    def test_drift_is_inconclusive(self):
        r, _ = self.run_case(mutate=lambda w,p: replace(w,latencies_ms=(12,)*30) if p==2 else w)
        self.assertEqual(r.reason, 'control_drift')

    def test_load_drift_is_inconclusive(self):
        r, _ = self.run_case(mutate=lambda w,p: replace(w,request_rate=120) if p==1 else w)
        self.assertEqual(r.reason, 'offered_load_changed')

    def test_budget_blocks_actuation(self):
        r, a = self.run_case(policy=ProbePolicy(extra_cpu_budget_s=.1))
        self.assertEqual(r.reason, 'budget_exceeded')
        self.assertEqual(a, [])

    def test_invalid_observations_fail_closed(self):
        for change in ({'identity':'reused-pid'}, {'latencies_ms':()},
                       {'cpu_seconds':float('nan')}, {'duty':.8},
                       {'duration_s':2}, {'healthy':False}, {'request_rate':0}):
            with self.subTest(change=change):
                r,a=self.run_case(mutate=lambda w,p:replace(w,**change))
                self.assertFalse(r.accepted)
                self.assertEqual(a[-1],.15)

    def test_sampler_exception_restores(self):
        applied=[]
        def broken(*args): raise RuntimeError('sample failed')
        with self.assertRaises(RuntimeError):
            RecoveryProbe().run('x',.15,.4,applied.append,broken)
        self.assertEqual(applied[-1],.15)

    def test_commit_failure_restores(self):
        applied=[]
        def apply(d):
            applied.append(d)
            if len(applied)==8: raise RuntimeError('commit failure')
        def observe(d,t): return Window('x',d,t,.01,(10,)*30,100)
        with self.assertRaises(RuntimeError):
            RecoveryProbe().run('x',.15,.4,apply,observe)
        self.assertEqual(applied[-1],.15)

    def test_invalid_policy(self):
        for kw in ({'rounds':0},{'window_s':float('nan')},{'min_requests':1}):
            with self.assertRaises(ValueError): ProbePolicy(**kw)

    def test_adapter_updates_actual_throttler(self):
        import threading
        from types import SimpleNamespace
        ratios=[]
        controller=SimpleNamespace(_lock=threading.Lock(),_throttlers={42:SimpleNamespace(update_ratio=ratios.append)})
        profile=SimpleNamespace(pid=42,is_quarantined=lambda:True,enforced_duty_cycle=.15)
        ExistingThrottlerAdapter(controller,profile).apply(.4)
        self.assertEqual(ratios,[.4])
        self.assertEqual(profile.enforced_duty_cycle,.4)
        controller._throttlers.clear()
        with self.assertRaises(RuntimeError): ExistingThrottlerAdapter(controller,profile).apply(.4)
