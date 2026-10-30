"""Explicit inputs and actionable setup for exploratory detector scripts."""
import argparse
import json
import math
from pathlib import Path

from arq.core.ml_pipeline import FEATURE_NAMES

ROOT=Path(__file__).resolve().parents[2]
SETUP='''Git does not include generated telemetry and model files.
From the repository root, collect and evaluate compatible process telemetry:
  PYTHONPATH=. python scripts/collect_labelled.py
  python -m arq.cli evaluate-labelled --data output/validation/controlled-labels.jsonl --output-dir output/validation/controlled-evaluation --repeats 3 --detector isolation_forest
  python -m arq.cli evaluate-labelled --data output/validation/controlled-labels.jsonl --output-dir output/validation/support-candidate --repeats 3 --detector support_if
Then rerun this script with its defaults.
These are controlled smoke scenarios, not representative deployment data.
For older artifacts, pass --data, --original and --candidate explicitly.'''


def parse_inputs(description, argv=None):
    parser=argparse.ArgumentParser(description=description)
    parser.add_argument('--data',type=Path,default=ROOT/'output/validation/controlled-labels.jsonl')
    parser.add_argument('--original',type=Path,default=ROOT/'output/validation/controlled-evaluation/evaluated_model.joblib')
    parser.add_argument('--candidate',type=Path,default=ROOT/'output/validation/support-candidate/evaluated_model.joblib')
    args=parser.parse_args(argv)
    missing=[str(p) for p in (args.data,args.original,args.candidate) if not p.is_file()]
    if missing:parser.error('Missing required inputs:\n  '+'\n  '.join(missing)+'\n\n'+SETUP)
    return args


def normal_matrix(path):
    """Use only supplied normal labels; never mix labelled attack rows into baseline."""
    import numpy as np
    rows=[];label_mode=None
    with Path(path).open(encoding='utf-8') as stream:
        for line_no,line in enumerate(stream,1):
            if not line.strip():continue
            try:
                row=json.loads(line)
                labelled='label' in row
                if label_mode is None:label_mode=labelled
                if label_mode!=labelled:raise ValueError('Mixed labelled and unlabelled records')
                if labelled and (type(row['label']) is not int or row['label'] not in (0,1)):
                    raise ValueError('Labels must be integer 0 or 1')
                values=[float(row[k]) for k in FEATURE_NAMES]
                if any(not math.isfinite(v) or v<0 for v in values):raise ValueError('Invalid feature value')
                if not labelled or row['label']==0:rows.append(values)
            except (KeyError,TypeError,ValueError) as exc:
                raise ValueError(f'Invalid telemetry on line {line_no}: {exc}') from exc
    if not rows:raise ValueError('No normal process observations available')
    return np.asarray(rows,dtype=float)
