"""Offline Kaggle server-telemetry study; never a live ARQ model adapter.

The source has disjoint normal/attack hosts and dates. Labels are file-derived,
so measured discrimination is confounded with collection domain.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import platform
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

SOURCE = 'https://www.kaggle.com/datasets/keshanijayasinghe/cryptojacking-attack-timeseries-dataset'
FEATURES = ('cpu_user', 'cpu_system', 'cpu_idle', 'cpu_iowait', 'cpu_nice',
            'cpu_irq', 'cpu_softirq', 'load_min1', 'load_min5', 'load_min15',
            'mem_percent', 'mem_active', 'mem_available', 'mem_free', 'mem_used',
            'mem_cached', 'mem_buffers', 'mem_inactive', 'memswap_percent',
            'processcount_running', 'processcount_sleeping', 'processcount_thread',
            'processcount_total')
FILES = {'final-normal-data-set.csv': 0, 'final-anormal-data-set.csv': 1}
LIMITATIONS = [
    'Normal and attack records come from disjoint host identities and collection dates; class and domain are confounded.',
    'Chronological partitions within a host do not establish unseen-host attack generalization.',
    'The single attack host prevents a meaningful host-disjoint train/test attack study.',
    'Labels are inferred from publisher file names, not independently verified per-observation ground truth.',
    'These host-level features and units are incompatible with the seven-feature ARQ process model.',
    'Neither model is eligible for ARQ enforcement; this study does not measure quarantine or recovery.',
    'Repeated seeds share test observations; they are not independent collection experiments.',
]


def read_archive(path):
    """Validate CSV shape, timestamps and physical ranges before accepting rows."""
    rows = []
    audit = {'source_rows': {}, 'rejected': Counter(), 'file_sha256': {}}
    with zipfile.ZipFile(path) as archive:
        for filename, label in FILES.items():
            data = archive.read(filename)
            audit['file_sha256'][filename] = hashlib.sha256(data).hexdigest()
            reader = csv.reader(io.StringIO(data.decode('utf-8-sig')))
            header = next(reader)
            required = set(FEATURES) | {'timestamp', 'system_hostname', 'mem_total'}
            if len(header) != len(set(header)) or not required <= set(header):
                raise ValueError('Missing or duplicated required CSV columns')
            count = 0
            for line, values in enumerate(reader, 2):
                count += 1
                if len(values) != len(header):
                    audit['rejected']['column_count'] += 1
                    continue
                row = dict(zip(header, values))
                try:
                    stamp = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
                    x = tuple(float(row[k]) for k in FEATURES)
                    total = float(row['mem_total'])
                    if any(not math.isfinite(v) or v < 0 for v in x):
                        raise ValueError('Invalid numeric feature')
                    if not math.isfinite(total) or total <= 0 or float(row['mem_used']) > total:
                        raise ValueError('Invalid memory accounting')
                    for key in FEATURES:
                        if (key.startswith('cpu_') or key.endswith('_percent')) and float(row[key]) > 100:
                            raise ValueError('Invalid percent')
                    if not row['system_hostname'] or row['system_hostname'].replace('.', '').isdigit():
                        raise ValueError('Invalid hostname')
                except (ValueError, OverflowError):
                    audit['rejected']['invalid_value_or_timestamp'] += 1
                    continue
                rows.append({'x': x, 'label': label, 'host': row['system_hostname'],
                             'timestamp': stamp.isoformat(), 'source': filename, 'line': line})
            audit['source_rows'][filename] = count
    # Keep the earliest copy of a feature vector and remove contradictory vectors.
    rows.sort(key=lambda r: (r['timestamp'], r['host'], r['line']))
    seen = {}; contradictory = set(); unique = []
    for row in rows:
        key = row['x']
        if key in seen:
            if seen[key] != row['label']:
                contradictory.add(key)
            audit['rejected']['duplicate_feature_vector'] += 1
            continue
        seen[key] = row['label']; unique.append(row)
    rows = [r for r in unique if r['x'] not in contradictory]
    audit['contradictory_vectors_removed'] = len(contradictory)
    audit['usable_rows'] = len(rows)
    audit['host_labels'] = {h: dict(Counter(str(r['label']) for r in rows if r['host'] == h))
                            for h in sorted({r['host'] for r in rows})}
    audit['rejected'] = dict(audit['rejected'])
    return rows, audit


def partition(rows, purge=100):
    """Per-host chronological 60/20/20 split with two purged boundary gaps."""
    if purge < 1:
        raise ValueError('A positive boundary purge is required')
    groups = defaultdict(list)
    for r in rows:
        groups[r['host']].append(r)
    splits = {s: [] for s in ('train', 'calibration', 'test')}; removed = 0
    for host, group in sorted(groups.items()):
        group.sort(key=lambda r: r['timestamp'])
        # The same timestamp cannot be split between partitions.
        times = sorted({r['timestamp'] for r in group})
        if len(times) < 5 * purge + 10:
            raise ValueError('Insufficient chronological groups for '+host)
        a, b = int(.6 * len(times)), int(.8 * len(times))
        assignment = {t: ('train' if i < a-purge else 'calibration' if a+purge <= i < b-purge
                          else 'test' if i >= b+purge else None) for i,t in enumerate(times)}
        for row in group:
            split = assignment[row['timestamp']]
            if split: splits[split].append(row)
            else: removed += 1
    for split, values in splits.items():
        if len(values) < 20 or {r['label'] for r in values} != {0,1}:
            raise ValueError('Each partition needs both classes and sufficient rows: '+split)
    return splits, removed


def run(archive_path, output_dir, repeats=3, seed=42, purge=100):
    import joblib
    import numpy as np
    import sklearn
    from sklearn.ensemble import ExtraTreesClassifier, IsolationForest
    from sklearn.metrics import average_precision_score, roc_auc_score
    from arq.evaluation.labelled import confusion
    if repeats < 2:
        raise ValueError('Use at least two fit seeds')
    started = time.monotonic()
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    rows, audit = read_archive(archive_path)
    splits, purged = partition(rows, purge)
    X = {s: np.asarray([r['x'] for r in rs], dtype=float) for s,rs in splits.items()}
    Y = {s: np.asarray([r['label'] for r in rs], dtype=int) for s,rs in splits.items()}
    active = np.ptp(X['train'], axis=0) > 0  # Learned only on training data.
    names = [f for f,keep in zip(FEATURES,active) if keep]
    X = {s: values[:,active] for s,values in X.items()}
    if not names: raise ValueError('No varying training features')
    result = {'schema': 'arq.external_host_telemetry.v1', 'source': SOURCE, 'license': 'CC0 (Kaggle data card)',
              'archive_sha256': hashlib.sha256(Path(archive_path).read_bytes()).hexdigest(),
              'audit': audit, 'purged_rows': purged, 'boundary_purge_timestamps_each_side': purge,
              'split_method': '60/20/20 chronological within each host, duplicate vectors removed before splitting',
              'partitions': {s: {'rows':len(rs),'labels':dict(Counter(str(r['label']) for r in rs)),
                                'hosts':dict(Counter(r['host'] for r in rs)),
                                'first_timestamp':min(r['timestamp'] for r in rs),
                                'last_timestamp':max(r['timestamp'] for r in rs)} for s,rs in splits.items()},
              'feature_names':names, 'excluded_constant_features':[f for f,keep in zip(FEATURES,active) if not keep],
              'excluded_metadata':'timestamp, hostname, OS strings, source filename, labels, cumulative counters, static hardware identity',
              'models':{}, 'deployment_eligible':False, 'limitations':LIMITATIONS,
              'environment':{'python':platform.python_version(),'platform':platform.platform(),
                             'numpy':np.__version__,'sklearn':sklearn.__version__,'joblib':joblib.__version__}}
    for kind in ('isolation_forest', 'extra_trees'):
        trials=[]
        for i in range(repeats):
            tick=time.monotonic()
            if kind == 'isolation_forest':
                model=IsolationForest(n_estimators=200, max_samples=2048, contamination='auto',random_state=seed+i,n_jobs=2)
                model.fit(X['train'][Y['train']==0])
                normal_cal=X['calibration'][Y['calibration']==0]
                threshold=float(np.quantile(-model.decision_function(normal_cal),.95))
                scores=-model.decision_function(X['test'])
            else:
                model=ExtraTreesClassifier(n_estimators=200,min_samples_leaf=5,max_features='sqrt',class_weight='balanced',random_state=seed+i,n_jobs=2)
                model.fit(X['train'],Y['train'])
                threshold=.5  # Fixed before test evaluation; no test-set tuning.
                scores=model.predict_proba(X['test'])[:,1]
            predicted=scores>threshold
            metrics=confusion(Y['test'].tolist(),predicted.tolist())
            metrics['accuracy']=float(np.mean(predicted==Y['test']))
            metrics['roc_auc']=float(roc_auc_score(Y['test'],scores))
            metrics['average_precision']=float(average_precision_score(Y['test'],scores))
            trial={'seed':seed+i,'threshold':threshold,'metrics':metrics,'fit_and_score_s':time.monotonic()-tick}
            trials.append(trial)
            if i==0:
                artifact={'schema':'arq.external_host_telemetry.v1','model':model,'feature_names':names,
                          'threshold':threshold,'score_kind':'negative_decision_function' if kind=='isolation_forest' else 'positive_class_probability',
                          'deployment_eligible':False,'source':SOURCE}
                target=out/(kind+'.joblib');joblib.dump(artifact,target)
                trial['model_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
                trial['by_host']={h:confusion([r['label'] for r in splits['test'] if r['host']==h],
                                             [bool(p) for p,r in zip(predicted,splits['test']) if r['host']==h])
                                  for h in sorted({r['host'] for r in splits['test']})}
                with gzip.open(out/(kind+'-test-predictions.csv.gz'),'wt',newline='') as stream:
                    writer=csv.writer(stream);writer.writerow(['source','line','host','timestamp','label','score','predicted'])
                    writer.writerows((r['source'],r['line'],r['host'],r['timestamp'],r['label'],float(v),int(p))
                                     for r,v,p in zip(splits['test'],scores,predicted))
            print(kind,seed+i,json.dumps(metrics),flush=True)
        result['models'][kind]={'trials':trials,'summary':{k:{'mean':float(np.mean([t['metrics'][k] for t in trials])),
                      'sample_std':float(np.std([t['metrics'][k] for t in trials],ddof=1))}
                      for k in ['accuracy','precision','recall','f1','false_positive_rate','roc_auc','average_precision']
                      if all(t['metrics'][k] is not None for t in trials)}}
    result['elapsed_s']=time.monotonic()-started
    (out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
    # Manifest records row provenance and exact splits; it is not a deployment report.
    with gzip.open(out/'split-manifest.csv.gz','wt',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['split','source','line','host','timestamp','label'])
        for s,rs in splits.items():writer.writerows((s,r['source'],r['line'],r['host'],r['timestamp'],r['label']) for r in rs)
    print('Completed:',out/'evaluation.json',flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--repeats',type=int,default=3);parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--purge',type=int,default=100)
    args=parser.parse_args();run(args.archive,args.output,args.repeats,args.seed,args.purge)

if __name__=='__main__':main()
