import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from arq.core.ml_policy import MLAssistedPolicy, validate_candidate
from arq.core.guarded_controller import GuardedController
from arq.core.process_model import ProcessProfile, QuarantineStage
from arq.core.monitor import RUsageInfoV2, ProcessMonitor
from arq.evaluation.labelled import confusion,load_labelled,evaluate
from arq.core.ml_pipeline import FEATURE_NAMES


def dataset(path):
    rows=[]
    for split in ['train','calibration','test']:
        for group in range(3):
            for i in range(30):
                label=int(split=='test' and group==2)
                r={k:float((i%7)+group+1+label*100) for k in FEATURE_NAMES}
                r.update(split=split,label=label,run_id=f'{split}-{group}',sample_index=i,scenario='stress' if label else 'normal')
                rows.append(r)
    path.write_text('\n'.join(json.dumps(r) for r in rows))
    return rows

class EvaluationTests(unittest.TestCase):
    def test_confusion(self):
        m=confusion([0,0,1,1],[False,True,True,False])
        self.assertEqual([m[k] for k in ['tp','fp','tn','fn']],[1,1,1,1])
        self.assertEqual(m['false_positive_rate'],.5)
        self.assertIsNone(confusion([0],[False])['precision'])

    def test_run_leakage_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.jsonl';rows=dataset(p);rows[-1]['run_id']=rows[0]['run_id']
            p.write_text('\n'.join(json.dumps(r) for r in rows))
            with self.assertRaises(ValueError):load_labelled(p)

    def test_evaluate_and_tamper_gate(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.jsonl';dataset(p)
            r=evaluate(p,Path(t)/'result',repeats=2)
            self.assertEqual(len(r['model_fit_trials']),2)
            self.assertEqual(r['group_counts']['test'],3)
            self.assertTrue((Path(t)/'result/evaluated_model.joblib').exists())
            # Dataset too small to authorize actuation even if metrics look good.
            with self.assertRaises(ValueError):validate_candidate(Path(t)/'result/evaluated_model.joblib',Path(t)/'result/evaluation.json')

    def test_acceptance_binds_hash(self):
        with tempfile.TemporaryDirectory() as t:
            model=Path(t)/'model';model.write_bytes(b'example')
            report=Path(t)/'report.json'
            r=dict(schema=1,evaluated_at=__import__('time').time(),candidate_sha256=hashlib.sha256(b'example').hexdigest(),test_normal=100,test_anomalous=100,group_counts={'test':3},candidate_metrics={'precision':.95,'recall':.95,'false_positive_rate':.01},candidate_by_scenario={'x':{'tp':95,'fn':5,'recall':.95}})
            report.write_text(json.dumps(r));validate_candidate(model,report)
            model.write_bytes(b'changed')
            with self.assertRaises(ValueError):validate_candidate(model,report)

    def test_assistance_is_opt_in_and_corroborated(self):
        with self.assertRaises(ValueError):MLAssistedPolicy('assist')
        p=MLAssistedPolicy('assist',True,consecutive=2)
        self.assertEqual(p.decide('x',.45,True)[0],.45)
        self.assertEqual(p.decide('x',.45,True)[0],.65)
        self.assertEqual(p.decide('x',.9,False)[0],.9)
        self.assertEqual(p.decide('y',.1,True)[0],.1)
        self.assertEqual(MLAssistedPolicy().decide('x',.4,True)[0],.4)
        p.expires=0
        self.assertEqual(p.decide('x',.45,True)[0],.45)

    def test_guard_denies_unmanaged_and_dry_run(self):
        from types import SimpleNamespace
        c=GuardedController();profile=ProcessProfile(12345)
        try:
            with patch('arq.core.quarantine_controller.os.kill') as kill:
                self.assertEqual(c.apply_stage(profile,QuarantineStage.SOFT_QUARANTINE),'denied_unmanaged_or_exited')
                c.register(SimpleNamespace(pid=12345,process=SimpleNamespace(is_alive=lambda:True)))
                self.assertEqual(c.apply_stage(profile,QuarantineStage.SOFT_QUARANTINE),'dry_run')
                self.assertEqual(c.apply_stage(profile,QuarantineStage.TERMINATED),'denied_termination')
                kill.assert_not_called()
        finally:c.close()

    def test_macos_buffer_matches_requested_flavor(self):
        import ctypes
        self.assertEqual(ctypes.sizeof(RUsageInfoV2),160)

    def test_unsupported_telemetry_is_missing(self):
        m=ProcessMonitor();m._is_linux=False;m._is_macos=False
        self.assertIsNone(m.sample_process(12345))
        self.assertFalse(m.capabilities()['native_telemetry'])

    def test_web_can_run_without_ml_and_defaults_dry_run(self):
        from arq.web.server import ARQDashboardState
        state=ARQDashboardState(model_path='/missing/model.joblib')
        try:
            self.assertFalse(state.controller.enforce)
            self.assertEqual(state.ml_policy.mode,'shadow')
            state.cycle()
        finally:state.controller.close()

    def test_linux_parser_and_pid_reuse(self):
        import io
        m=ProcessMonitor();m._is_linux=True;m._is_macos=False;m._clk_tck=100
        rest=['0']*40;rest[0]='S';rest[11]='10';rest[12]='5';rest[19]='100'
        def open_file(name,*args,**kw):
            if name.endswith('/stat'):return io.StringIO('12 (name with spaces) '+' '.join(rest))
            if name.endswith('/status'):return io.StringIO('VmRSS: 1024 kB\nVmSize: 2048 kB\nThreads: 2\n')
            return io.StringIO('read_bytes: 1024\nwrite_bytes: 2048\n')
        with patch('builtins.open',side_effect=open_file),patch('arq.core.monitor.time.monotonic',side_effect=[1,2,3]):
            first=m.sample_process(12);rest[11]='110';second=m.sample_process(12)
            self.assertEqual(second.cpu_percent,100)
            rest[19]='200';rest[11]='1';third=m.sample_process(12)
            self.assertEqual(third.cpu_percent,0)
            self.assertEqual(first.memory_rss_mb,1)

    def test_guard_lease_expires_and_releases(self):
        import time
        c=GuardedController(enforce=True,lease_s=.02)
        try:
            with patch.object(c,'cleanup_all') as release:
                time.sleep(.3)
                self.assertFalse(c.enforce)
                release.assert_called()
        finally:c.close()

    def test_native_cpu_delta_against_child_process_clock(self):
        import subprocess,sys,time
        m=ProcessMonitor()
        if not m.capabilities()['native_telemetry']:self.skipTest('No native telemetry')
        code='import sys,time\nprint("ready",flush=True)\nsys.stdin.readline()\na=time.process_time()\nwhile time.process_time()-a<.25: pass\nprint(time.process_time()-a,flush=True)\nsys.stdin.readline()'
        child=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        try:
            child.stdout.readline();m.sample_process(child.pid)
            before=m._last_sample_time[child.pid]
            child.stdin.write('go\n');child.stdin.flush()
            reported=float(child.stdout.readline())
            second=m.sample_process(child.pid)
            measured=second.cpu_percent/100*(m._last_sample_time[child.pid]-before)
            self.assertGreater(measured/reported,.7)
            self.assertLess(measured/reported,1.3)
        finally:
            child.terminate();child.communicate(timeout=2)

    def test_support_candidate_scores_outside_training_support(self):
        import numpy as np
        from arq.core.support_detector import SupportAwareIsolationForest
        data=np.asarray([[i%5+1]*7 for i in range(30)],dtype=float)
        model=SupportAwareIsolationForest().fit(data)
        scores=model.decision_function([[2]*7,[10000]*7])
        self.assertLess(scores[1],scores[0])

    def test_benchmark_report_does_not_invent_state_loss(self):
        from arq.evaluation.metrics import BenchmarkResult
        from arq.evaluation.report_generator import ReportGenerator
        r=BenchmarkResult('example',1,1,1,1,1,1,1,True,None,None,1,1)
        self.assertIsNone(r.to_dict()['state_loss_pct'])
        text=ReportGenerator.format_markdown([r])
        self.assertIn('Not measured',text)
        self.assertNotIn('70%',text)

    def test_http_status_and_denied_control_are_truthful(self):
        import os,threading,urllib.request
        from arq.web.server import ARQDashboardState,DashboardRequestHandler,ThreadingHTTPServer
        state=ARQDashboardState(model_path='/missing/model.joblib')
        DashboardRequestHandler.state=state
        server=ThreadingHTTPServer(('127.0.0.1',0),DashboardRequestHandler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            state.cycle();url='http://127.0.0.1:'+str(server.server_port)
            data=json.load(urllib.request.urlopen(url+'/api/status'))
            self.assertFalse(data['enforcement_enabled'])
            req=urllib.request.Request(url+'/api/quarantine',data=json.dumps({'pid':os.getpid()}).encode(),headers={'Content-Type':'application/json'})
            result=json.load(urllib.request.urlopen(req))
            self.assertFalse(result['success'])
            self.assertEqual(result['actuation'],'denied_unmanaged_or_exited')
        finally:
            server.shutdown();server.server_close();thread.join();state.controller.close()

    def test_missing_telemetry_does_not_make_a_healthy_decision(self):
        import os
        from arq.web.server import ARQDashboardState
        state=ARQDashboardState(model_path='/missing/model.joblib')
        try:
            state.profiles[os.getpid()]=ProcessProfile(os.getpid())
            with patch.object(state.monitor,'sample_process',return_value=None):state.cycle()
            self.assertEqual(state.history[-1]['processes'][0]['telemetry_status'],'unavailable')
            self.assertEqual(state.controller.audit[-1]['status'],'denied_unmanaged_or_exited')
        finally:state.controller.close()

    def test_live_guard_only_actuates_its_registered_child(self):
        import signal,time
        if not hasattr(signal,'SIGSTOP'):self.skipTest('POSIX signals unavailable')
        from arq.simulation.workloads import WorkloadSimulator
        handle=WorkloadSimulator.start_cpu_burner()
        c=GuardedController(enforce=True)
        profile=ProcessProfile(handle.pid)
        try:
            c.register(handle)
            self.assertEqual(c.apply_stage(profile,QuarantineStage.SOFT_QUARANTINE),'requested')
            time.sleep(.15)
            self.assertEqual(profile.enforced_duty_cycle,.4)
            self.assertIn(handle.pid,c._throttlers)
        finally:
            c.close();handle.stop()
        self.assertFalse(c._throttlers)
        self.assertFalse(handle.process.is_alive())
