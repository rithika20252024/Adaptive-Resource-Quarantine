"""Randomized-order repeated live trials. Existing state-loss fields are unverified."""
import json
import math
import platform
import random
from pathlib import Path
from statistics import mean, stdev
from arq.evaluation.benchmark_runner import BenchmarkRunner


def run_repeated(repeats=3,duration=2,seed=42,output='output/validation/repeated-benchmark.json'):
    if repeats<2 or not math.isfinite(duration) or duration<=0:raise ValueError('Need >=2 repeats and positive duration')
    runner=BenchmarkRunner(duration)
    strategies={'unprotected':runner.run_unprotected,'static_termination':runner.run_static_kill,'adaptive':runner.run_adaptive_quarantine}
    rng=random.Random(seed);trials=[]
    for trial in range(repeats):
        order=list(strategies);rng.shuffle(order)
        for position,name in enumerate(order):
            d=strategies[name]().to_dict()
            # These values were constants/assumptions in the legacy runner.
            for field in ['state_loss_pct','recovery_time_s']:d.pop(field,None)
            trials.append({'trial':trial,'order':position,'strategy':name,**d,'strategy_label':d['strategy']})
            trials[-1]['strategy']=name
    summary={}
    for name in strategies:
        values=[r for r in trials if r['strategy']==name]
        summary[name]={k:{'mean':mean(r[k] for r in values),'sample_std':stdev(r[k] for r in values)} for k in ['p95_latency_ms','p99_latency_ms','throughput_rps']}
    result={'platform':platform.platform(),'python':platform.python_version(),'seed':seed,
            'duration_per_trial_s':duration,'trials':trials,'summary':summary,
            'limitations':['Local short-run measurements; no cross-host or production guarantee.',
                            'Latency probe measures synthetic work-unit processing time, not end-to-end service latency.',
                            'No measured application state-loss, completion or recovery-time claim.',
                            'Legacy policy benchmark; new bracketed probe is not exercised here.']}
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n')
    return result
