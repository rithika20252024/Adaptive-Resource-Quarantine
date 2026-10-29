"""Live owned-workload trials; unmeasured application state loss is explicit."""
import time
from arq.core.anomaly_scorer import AnomalyScorer
from arq.core.monitor import ProcessMonitor
from arq.core.process_model import ProcessProfile
from arq.core.quarantine_controller import QuarantineController
from arq.core.restoration_engine import RestorationEngine
from arq.evaluation.metrics import BenchmarkResult
from arq.simulation.noisy_neighbor import LatencyProbeService
from arq.simulation.workloads import WorkloadSimulator


class BenchmarkRunner:
    def __init__(self,trial_duration_s=6):
        import math
        if not math.isfinite(trial_duration_s) or trial_duration_s<=0:raise ValueError('Positive finite duration required')
        self.trial_duration_s=trial_duration_s

    def _run(self,strategy):
        monitor=ProcessMonitor()
        if not monitor.capabilities()['native_telemetry']:raise RuntimeError('Native telemetry required')
        probe=LatencyProbeService(request_rate_hz=50)
        controller=QuarantineController(soft_threshold=.55,hard_threshold=.75)
        restoration=RestorationEngine(controller,hysteresis_cycles=2,auto_terminate_persistent=False)
        scorer=AnomalyScorer(cpu_threshold=60,burst_tolerance_cycles=1)
        burner=WorkloadSimulator.start_cpu_burner()
        profile=ProcessProfile(burner.pid,name='benchmark_owned_child')
        peak_cpu=0.;peak_rss=0.;observations=0
        start=time.monotonic()
        try:
            probe.start()
            while time.monotonic()-start<self.trial_duration_s:
                m=monitor.sample_process(burner.pid)
                if m:
                    observations+=1;peak_cpu=max(peak_cpu,m.cpu_percent);peak_rss=max(peak_rss,m.memory_rss_mb)
                    if strategy=='static' and m.cpu_percent>60:burner.stop()
                    elif strategy=='adaptive':restoration.process_cycle(profile,scorer.evaluate(profile,m))
                time.sleep(.1)
            duration=time.monotonic()-start
            survived=burner.process.is_alive()
        finally:
            controller.cleanup_all()
            burner.stop()
            latencies=probe.stop_and_collect()
        if not observations or not latencies:raise RuntimeError('No usable telemetry or latency observations collected')
        stats=LatencyProbeService.compute_stats(latencies)
        names={'unprotected':'Unprotected baseline','static':'Static termination','adaptive':'Adaptive quarantine'}
        return BenchmarkResult(names[strategy],duration,len(latencies),stats['mean'],stats['median'],stats['p95'],stats['p99'],len(latencies)/duration,survived,None,None,peak_cpu,peak_rss)

    def run_unprotected(self):return self._run('unprotected')
    def run_static_kill(self):return self._run('static')
    def run_adaptive_quarantine(self):return self._run('adaptive')
    def run_all(self):return [self.run_unprotected(),self.run_static_kill(),self.run_adaptive_quarantine()]
