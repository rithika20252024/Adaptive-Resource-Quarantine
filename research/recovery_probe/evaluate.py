"""Deterministic synthetic evaluation; no hardware performance claims."""
import json
import random
from dataclasses import replace
from pathlib import Path
from arq.core.recovery_probe import RecoveryProbe, Window
from arq.core.process_model import ProcessProfile, ProcessMetrics, QuarantineStage
from arq.core.restoration_engine import RestorationEngine
from arq.core.anomaly_scorer import AnomalyScorer

class SimulatedController:
    soft_threshold=.65
    hard_threshold=.85
    def apply_stage(self, profile, stage, reason=''):
        profile.stage=stage


def legacy(demand):
    profile=ProcessProfile(42,stage=QuarantineStage.HARD_QUARANTINE)
    engine=RestorationEngine(SimulatedController(),hysteresis_cycles=4)
    scorer=AnomalyScorer()
    for _ in range(4):
        score=scorer.evaluate(profile,ProcessMetrics(42,cpu_percent=100*min(.15,demand)))
        engine.process_cycle(profile,score)
    return profile.stage < QuarantineStage.HARD_QUARANTINE


def scenario(kind, seed, ablation='full'):
    rng=random.Random(seed)
    demand=rng.uniform(.08,.20) if kind!='masked_demand' else rng.uniform(.8,1)
    count=0
    applied=[]
    def observe(duty,t):
        nonlocal count
        phase=count%3
        count+=1
        latency=10+rng.uniform(-.15,.15)
        if kind=='protected_harm' and phase==1: latency+=3.5
        if kind=='control_drift' and phase==2: latency+=1.5
        rate=120 if kind=='load_change' and phase==1 else 100
        w=Window('42:birth',duty,t,min(demand,duty)*t,(latency,)*30,rate)
        if ablation=='no_demand_check':
            w=replace(w,cpu_seconds=.05*t)
        return w
    result=RecoveryProbe().run('42:birth',.15,.4,applied.append,observe)
    return {'scenario':kind,'seed':seed,'demand_one_core':demand,
            'legacy_relaxed':legacy(demand),'probe_relaxed':result.accepted,
            'reason':result.reason,'final_duty':result.final_duty,
            'reserved_nominal_extra_cpu_s':result.reserved_extra_cpu_s}

rows=[scenario(kind,seed) for kind in ('recovered','masked_demand','protected_harm','control_drift','load_change') for seed in range(100)]
summary=[]
for kind in dict.fromkeys(r['scenario'] for r in rows):
    group=[r for r in rows if r['scenario']==kind]
    summary.append({'scenario':kind,'trials':len(group),
                    'legacy_relaxations':sum(r['legacy_relaxed'] for r in group),
                    'probe_relaxations':sum(r['probe_relaxed'] for r in group)})
out={'method':'Synthetic deterministic one-core min(demand,duty) model; constant within-window latency with seeded noise, not an OS benchmark or independent validation',
     'summary':summary,'trials':rows,
     'ablation_masked_demand_no_demand_check':[scenario('masked_demand',s,'no_demand_check') for s in range(100)]}
p=Path(__file__).parent/'results'/'synthetic-comparison.json'
p.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(summary,indent=2))
