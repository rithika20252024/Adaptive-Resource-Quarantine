"""Guard external-dataset provenance and prevent accidental live promotion."""
import csv
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from arq.evaluation.kaggle_cryptojacking import FEATURES, FILES, partition, read_archive
from arq.core.ml_policy import validate_candidate


class KaggleStudyTests(unittest.TestCase):
    def test_archive_rejects_bad_rows_and_contradictory_vectors(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'data.zip'
            header=list(FEATURES)+['timestamp','system_hostname','mem_total']
            with zipfile.ZipFile(path,'w') as z:
                for name,label in FILES.items():
                    stream=io.StringIO();writer=csv.writer(stream);writer.writerow(header)
                    base={k:1 for k in FEATURES};base.update(mem_used=10,mem_total=100,timestamp='2020-01-01 00:00:00',system_hostname='host')
                    writer.writerow([base[k] for k in header])  # Contradiction across source labels.
                    base['cpu_user']=5+label
                    writer.writerow([base[k] for k in header])
                    writer.writerow([base[k] for k in header])  # Exact duplicate.
                    writer.writerow(['invalid'])  # Shifted / malformed CSV.
                    base['cpu_user']='nan';writer.writerow([base[k] for k in header])
                    z.writestr(name,stream.getvalue())
            rows,audit=read_archive(path)
            self.assertEqual(len(rows),2)
            self.assertEqual({r['label'] for r in rows},{0,1})
            self.assertEqual(audit['rejected']['column_count'],2)
            self.assertEqual(audit['rejected']['invalid_value_or_timestamp'],2)
            self.assertEqual(audit['contradictory_vectors_removed'],1)

    def test_time_splits_have_gaps_and_no_vector_overlap(self):
        rows=[]
        for label in (0,1):
            for i in range(100):
                rows.append(dict(host='host'+str(label),label=label,
                                 timestamp=(datetime(2020,1,1)+timedelta(seconds=i)).isoformat(),x=(label,i)))
        parts,purged=partition(rows,purge=2)
        self.assertEqual(purged,16)
        for host in ('host0','host1'):
            ts=[[r['timestamp'] for r in parts[s] if r['host']==host] for s in ('train','calibration','test')]
            self.assertLess(max(ts[0]),min(ts[1]));self.assertLess(max(ts[1]),min(ts[2]))
        sets=[{r['x'] for r in parts[s]} for s in parts]
        self.assertTrue(all(not a&b for i,a in enumerate(sets) for b in sets[i+1:]))

    def test_small_host_and_zero_purge_rejected(self):
        with self.assertRaises(ValueError):partition([],purge=0)
        with self.assertRaises(ValueError):partition([dict(host='x',timestamp='2020',label=0,x=(0,))])

    def test_external_model_report_cannot_pass_live_gate(self):
        with tempfile.TemporaryDirectory() as d:
            report=Path(d)/'report.json';report.write_text(json.dumps({'schema':'arq.external_host_telemetry.v1','deployment_eligible':False}))
            with self.assertRaisesRegex(ValueError,'does not match'):
                validate_candidate(Path(d)/'model.joblib',report)


if __name__=='__main__':unittest.main()
