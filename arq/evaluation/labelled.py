"""Held-out, run-disjoint detector evaluation. Labels are supplied, not inferred."""
import hashlib
import json
import math
import time
from pathlib import Path
from collections import defaultdict
from statistics import mean, stdev
from arq.core.ml_pipeline import FEATURE_NAMES, extract_features
from arq.core.process_model import ProcessMetrics, ProcessProfile
from arq.core.anomaly_scorer import AnomalyScorer


def confusion(labels, predicted):
    if len(labels) != len(predicted) or not labels:
        raise ValueError('Nonempty aligned labels and predictions required')
    tp=sum(y==1 and p for y,p in zip(labels,predicted))
    fp=sum(y==0 and p for y,p in zip(labels,predicted))
    tn=sum(y==0 and not p for y,p in zip(labels,predicted))
    fn=sum(y==1 and not p for y,p in zip(labels,predicted))
    ratio=lambda a,b: a/b if b else None
    precision=ratio(tp,tp+fp);recall=ratio(tp,tp+fn)
    return dict(tp=tp,fp=fp,tn=tn,fn=fn,precision=precision,recall=recall,
                f1=ratio(2*tp,2*tp+fp+fn),false_positive_rate=ratio(fp,fp+tn),
                false_negative_rate=ratio(fn,fn+tp))


def load_labelled(path):
    records=[]; group_splits={}; indices=set()
    with open(path) as f:
        for line_no,line in enumerate(f,1):
            if not line.strip():continue
            r=json.loads(line)
            if r.get('split') not in {'train','calibration','test'}:
                raise ValueError(f'Line {line_no}: require train/calibration/test split')
            if type(r.get('label')) is not int or r['label'] not in {0,1}:
                raise ValueError('Labels must be integer 0 (normal) or 1 (anomalous)')
            if not isinstance(r.get('run_id'),str) or not r['run_id']:
                raise ValueError('Each observation needs a nonempty run_id')
            if not isinstance(r.get('scenario'),str) or not r['scenario']:
                raise ValueError('Each observation needs a scenario')
            if type(r.get('sample_index')) is not int or r['sample_index']<0:
                raise ValueError('Require nonnegative sample_index')
            key=(r['run_id'],r['sample_index'])
            if key in indices:raise ValueError('Duplicate sample within run')
            indices.add(key)
            old=group_splits.setdefault(r['run_id'],r['split'])
            if old!=r['split']:raise ValueError('Run leakage across data partitions')
            if r['split']!='test' and r['label']!=0:
                raise ValueError('Train and calibration partitions must contain normal examples only')
            vals=[float(r[k]) for k in FEATURE_NAMES]
            if any(not math.isfinite(x) or x<0 for x in vals):
                raise ValueError('Features must be finite and nonnegative')
            records.append(r)
    for split in ['train','calibration','test']:
        if sum(r['split']==split for r in records)<20:
            raise ValueError('Each partition requires at least 20 observations')
    if {r['label'] for r in records if r['split']=='test'}!={0,1}:
        raise ValueError('Test partition must contain both labels')
    return records


def evaluate(path, output_dir, repeats=5, seed=42, detector="isolation_forest"):
    import joblib
    import numpy as np
    from sklearn.ensemble import IsolationForest
    if not isinstance(repeats,int) or repeats<2:raise ValueError('At least two model-fit repeats required')
    if detector not in {'isolation_forest','support_if'}:raise ValueError('Unknown detector')
    rows=load_labelled(path)
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    subset=lambda s:[r for r in rows if r['split']==s]
    matrix=lambda rs:np.asarray([[r[k] for k in FEATURE_NAMES] for r in rs],dtype=float)
    training,calibration,test=[subset(s) for s in ['train','calibration','test']]
    labels=[r['label'] for r in test]
    scorer=AnomalyScorer();profiles={};rule=[]
    # Score in run/sample order, then retain input-order comparison alignment.
    scored={}
    for r in sorted(test,key=lambda r:(r['run_id'],r['sample_index'])):
        prof=profiles.setdefault(r['run_id'],ProcessProfile(1))
        m=ProcessMetrics(1,**{k:r[k] for k in FEATURE_NAMES})
        scored[(r['run_id'],r['sample_index'])]=scorer.evaluate(prof,m)>=.5
    rule=[scored[(r['run_id'],r['sample_index'])] for r in test]
    trials=[];first_prediction=None
    for i in range(repeats):
        if detector=='support_if':
            from arq.core.support_detector import SupportAwareIsolationForest
            model=SupportAwareIsolationForest(random_state=seed+i)
        else:
            model=IsolationForest(n_estimators=100,contamination=.05,random_state=seed+i,n_jobs=1)
        model.fit(matrix(training))
        threshold=float(np.quantile(-model.decision_function(matrix(calibration)),.95))
        prediction=(-model.decision_function(matrix(test))>threshold).tolist()
        trials.append({'seed':seed+i,'metrics':confusion(labels,prediction),
                       'agreement_with_rule':sum(a==b for a,b in zip(rule,prediction))/len(test)})
        if i==0:
            first_prediction=prediction
            artifact={'model':model,'feature_names':list(FEATURE_NAMES),'calibration_threshold':threshold}
            joblib.dump(artifact,out/'evaluated_model.joblib')
    by_scenario={}
    for scenario in sorted({r['scenario'] for r in test}):
        idx=[i for i,r in enumerate(test) if r['scenario']==scenario]
        by_scenario[scenario]=confusion([labels[i] for i in idx],[first_prediction[i] for i in idx])
    summary={}
    for key in ['precision','recall','f1','false_positive_rate','false_negative_rate']:
        vals=[t['metrics'][key] for t in trials if t['metrics'][key] is not None]
        summary[key]={'mean':mean(vals) if vals else None,'sample_std':stdev(vals) if len(vals)>1 else None}
    report={'schema':1,'evaluated_at':time.time(),'detector':detector,'dataset_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'candidate_sha256':hashlib.sha256((out/'evaluated_model.joblib').read_bytes()).hexdigest(),
            'partition_counts':{s:len(subset(s)) for s in ['train','calibration','test']},
            'group_counts':{s:len({r['run_id'] for r in subset(s)}) for s in ['train','calibration','test']},
            'test_normal':labels.count(0),'test_anomalous':labels.count(1),
            'rule_metrics':confusion(labels,rule),'candidate_metrics':trials[0]['metrics'],
            'candidate_by_scenario':by_scenario,'model_fit_trials':trials,'summary':summary,
            'agreement':{'both_anomalous':sum(a and b for a,b in zip(rule,first_prediction)),
                         'rule_only':sum(a and not b for a,b in zip(rule,first_prediction)),
                         'ml_only':sum(b and not a for a,b in zip(rule,first_prediction)),
                         'both_normal':sum(not a and not b for a,b in zip(rule,first_prediction))},
            'limitations':['Repeated fits use the same held-out runs; they are not independent workload trials.',
                            'Supplied labels and workload representativeness require human verification.',
                            'No guarantee for unobserved workloads or cross-host generalization.']}
    (out/'evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
