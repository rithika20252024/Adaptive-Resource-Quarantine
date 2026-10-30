import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from arq.evaluation.script_inputs import normal_matrix,parse_inputs
from arq.core.ml_pipeline import FEATURE_NAMES


class ScriptInputTests(unittest.TestCase):
    def test_missing_files_explain_reproduction(self):
        with tempfile.TemporaryDirectory() as d:
            err=io.StringIO()
            with contextlib.redirect_stderr(err),self.assertRaises(SystemExit) as raised:
                parse_inputs('test',['--data',d+'/data','--original',d+'/a','--candidate',d+'/b'])
            self.assertEqual(raised.exception.code,2)
            self.assertIn('collect_labelled.py',err.getvalue())
            self.assertIn('Missing required inputs',err.getvalue())

    def test_explicit_paths_accepted_without_loading_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            paths=[Path(d)/str(i) for i in range(3)]
            for p in paths:p.touch()
            args=parse_inputs('test',['--data',str(paths[0]),'--original',str(paths[1]),'--candidate',str(paths[2])])
            self.assertEqual(args.candidate,paths[2])

    def test_labelled_attacks_excluded_from_normal_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'rows.jsonl'
            normal={k:1 for k in FEATURE_NAMES};normal['label']=0
            attack={k:999 for k in FEATURE_NAMES};attack['label']=1
            p.write_text(json.dumps(normal)+'\n'+json.dumps(attack)+'\n')
            X=normal_matrix(p);self.assertEqual(X.shape,(1,7));self.assertTrue((X==1).all())

    def test_mixed_labels_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'rows.jsonl';r={k:1 for k in FEATURE_NAMES}
            p.write_text(json.dumps(r)+'\n'+json.dumps(dict(r,label=0))+'\n')
            with self.assertRaisesRegex(ValueError,'Mixed labelled'):normal_matrix(p)

    def test_invalid_or_empty_normal_data_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'rows.jsonl';r={k:1 for k in FEATURE_NAMES};r['cpu_percent']=float('nan')
            p.write_text(json.dumps(r)+'\n')
            with self.assertRaisesRegex(ValueError,'Invalid feature'):normal_matrix(p)
            r['cpu_percent']=1;r['label']=1;p.write_text(json.dumps(r)+'\n')
            with self.assertRaisesRegex(ValueError,'No normal'):normal_matrix(p)
