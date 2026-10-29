"""Collect bounded, scenario-labelled owned-child telemetry; not a representative dataset."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from arq.core.monitor import ProcessMonitor
from arq.core.ml_pipeline import FEATURE_NAMES

PROGRAMS={
'idle': 'import time\nwhile True: time.sleep(.1)',
'benign_burst': 'import time\nwhile True:\n sum(i*i for i in range(1000)); time.sleep(.02)',
'sustained_cpu': 'while True: sum(i*i for i in range(10000))',
'io_stress': 'import tempfile,os\nf=tempfile.TemporaryFile()\npayload=b"x"*1048576\nwhile True:\n f.seek(0);f.write(payload);f.flush();os.fsync(f.fileno());f.seek(0);f.read()',
'bounded_memory_growth': 'import time\na=[]\nfor i in range(32):\n a.append(bytearray(1024*1024)); time.sleep(.08)\ntime.sleep(20)',
}


def collect(output,duration=2,interval=.1,runs=2):
    if duration<=0 or interval<=0 or duration/interval<20 or runs<1:
        raise ValueError('Require positive intervals, >=20 samples/session, runs>=1')
    monitor=ProcessMonitor()
    if not monitor.capabilities()['native_telemetry']:raise RuntimeError('Native telemetry unavailable')
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    counts={}
    with dest.open('w') as f:
        for split in ['train','calibration','test']:
            for scenario,program in PROGRAMS.items():
                label=int(scenario in {'sustained_cpu','bounded_memory_growth','io_stress'})
                if split!='test' and label:continue
                for run in range(runs):
                    child=subprocess.Popen([sys.executable,'-c',program],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    try:
                        time.sleep(.15);monitor.sample_process(child.pid)
                        for index in range(round(duration/interval)):
                            time.sleep(interval)
                            if child.poll() is not None:raise RuntimeError('Controlled child exited early')
                            m=monitor.sample_process(child.pid)
                            if m is None:raise RuntimeError('Telemetry unavailable; not labelling missing data normal')
                            row={k:max(0,getattr(m,k)) for k in FEATURE_NAMES}
                            row.update(split=split,label=label,run_id=f'{split}-{scenario}-{run}',scenario=scenario,sample_index=index,provenance='controlled_scenario_not_representative')
                            f.write(json.dumps(row)+'\n');counts[split]=counts.get(split,0)+1
                    finally:
                        if child.poll() is None:child.terminate()
                        try:child.wait(timeout=2)
                        except subprocess.TimeoutExpired:child.kill();child.wait()
    return counts

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',default='output/validation/controlled-labels.jsonl');p.add_argument('--duration',type=float,default=2);p.add_argument('--interval',type=float,default=.1);p.add_argument('--runs',type=int,default=2)
    a=p.parse_args();print(json.dumps(collect(a.output,a.duration,a.interval,a.runs),indent=2))
