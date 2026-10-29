"""Conservative opt-in ML assistance; a model never authorizes recovery or kill."""
import hashlib
import json
import math
import time
from collections import defaultdict
from pathlib import Path


def validate_candidate(model_path, report_path):
    r=json.loads(Path(report_path).read_text())
    if r.get('schema')!=1 or hashlib.sha256(Path(model_path).read_bytes()).hexdigest()!=r.get('candidate_sha256'):
        raise ValueError('Model does not match evaluation report')
    age=time.time()-float(r.get('evaluated_at',0))
    if not math.isfinite(age) or age<0 or age>7*86400:raise ValueError('Evaluation is stale or has an invalid date')
    m=r['candidate_metrics']
    for key in ['precision','recall','false_positive_rate']:
        if m.get(key) is None or not math.isfinite(m[key]) or not 0<=m[key]<=1:raise ValueError('Incomplete metrics')
    if (r['test_normal']<100 or r['test_anomalous']<100 or
        r['group_counts']['test']<3 or m['precision']<.9 or m['recall']<.9 or m['false_positive_rate']>.05):
        raise ValueError('Candidate does not meet assistance acceptance criteria')
    for scenario, metrics in r['candidate_by_scenario'].items():
        if metrics['tp']+metrics['fn'] and (metrics['recall'] is None or metrics['recall']<.8):
            raise ValueError('Candidate misses required scenario: '+scenario)
    return r


class MLAssistedPolicy:
    def __init__(self, mode='shadow', validated=False, consecutive=3, ttl_s=3600):
        if mode not in {'shadow','assist'} or consecutive<1 or ttl_s<=0:raise ValueError('Invalid assistance policy')
        if mode=='assist' and not validated:raise ValueError('Assistance requires validated candidate')
        self.mode=mode;self.validated=validated;self.consecutive=consecutive
        self.expires=time.monotonic()+ttl_s;self.counts=defaultdict(int)

    def decide(self, identity, rule_score, ml_anomaly):
        if not math.isfinite(rule_score) or not 0<=rule_score<=1:raise ValueError('Invalid rule score')
        active=self.mode=='assist' and self.validated and time.monotonic()<self.expires
        # False/missing ML resets the streak. ML cannot reduce rule severity.
        self.counts[identity]=self.counts[identity]+1 if active and ml_anomaly is True else 0
        if active and self.counts[identity]>=self.consecutive and rule_score>=.40:
            return max(rule_score,.65),'ml_corroborated_soft_restriction'
        return rule_score, 'shadow_or_uncorroborated'
