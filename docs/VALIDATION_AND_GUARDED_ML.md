# Evaluation, portability and guarded ML assistance

Implemented 30 October 2026. These changes implement the missing tooling and an opt-in control path; they do not eliminate the need for representative data or platform validation.

## What changed

- **Labelled evaluation:** `arq/evaluation/labelled.py` requires explicit labels, scenarios, run IDs, sample indices and train/calibration/test partitions. A run cannot cross partitions. Training and calibration accept normal observations only. Test data must include both classes. Invalid or duplicate observations fail validation.
- **Metrics:** confusion matrices, precision, recall, F1, false-positive/negative rates, per-scenario results and rule/ML agreement counts. Undefined metrics remain null, not zero.
- **Repeated model fits:** reproducible seeds, all per-fit metrics, means and sample standard deviations. These repeated fits reuse held-out runs; they are not independent workload trials.
- **Repeated live benchmarks:** randomized strategy order, raw trial records, environment metadata and mean/sample standard deviation for latency and throughput. CPU/memory peaks are sampled; process survival is observed before cleanup. State loss and recovery time are explicitly unmeasured, not assigned 0% or 100%. Queue collection and child cleanup were corrected.
- **Candidate detector:** an optional Isolation Forest plus a robust training-support envelope addresses the inability of trees to extrapolate beyond observed split points. Median/IQR statistics are learned on training data, with unit floors; the decision threshold is learned on separate normal calibration runs. This is a heuristic score, not a probability or established novel invention.
- **Assisted enforcement:** optional `--ml-mode assist` requires a matching evaluation report. The default remains shadow mode. A corroborating ML flag must persist for three observations and the rule score must already reach watchlist severity. ML can raise the decision to soft restriction; it cannot reduce rule severity, authorize restoration or independently reach hard quarantine/termination.
- **Operational guard:** the dashboard defaults to dry-run, binds to loopback, restricts actuation to registered live child handles and disables priority changes that might not be reversible. Automatic termination requires a separate flag. A five-second in-process heartbeat lease releases restrictions and disables further actuation after expiry. It is not an independent supervisor and does not survive SIGKILL or machine failure.
- **Truthful status:** dry-run/denied actions, backend capabilities, actuator errors and unavailable telemetry are exposed. Missing measurements do not become healthy zero observations. Missing dashboard telemetry releases a managed restriction to watchlist without declaring recovery. The hard-coded dashboard gain and fixed benchmark superiority statement were removed.
- **Platform repair:** the macOS rusage request now matches its 160-byte v2 buffer, avoiding the previous v4 overwrite. Mach CPU counters retain their timebase conversion, verified against a child's process clock. Elapsed-time calculations use a monotonic clock. Linux process-start ticks and macOS start identity reset PID caches on reuse. Unsupported backends return missing observations. Linux parser fixtures pass; a Linux/macOS CI matrix is configured but its remote runs have not been executed by this task.

## Install and run

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-evaluation.txt
.venv/bin/python -m unittest discover -s tests -v

# Controlled idle, benign burst, CPU, bounded-memory and I/O sessions.
PYTHONPATH=. .venv/bin/python scripts/collect_labelled.py \
  --output output/validation/controlled-labels.jsonl

.venv/bin/python -m arq.cli evaluate-labelled \
  --data output/validation/controlled-labels.jsonl \
  --output-dir output/validation/labelled --repeats 5

.venv/bin/python -m arq.cli evaluate-labelled \
  --data output/validation/controlled-labels.jsonl \
  --output-dir output/validation/support-candidate --repeats 5 \
  --detector support_if

.venv/bin/python -m arq.cli benchmark-repeat --repeats 3 --duration 2
.venv/bin/python -m arq.cli web                  # dry-run, shadow mode
.venv/bin/python -m arq.cli web --enforce-managed # spawned children only
```

For a representative external dataset, provide one JSON object per line with the seven telemetry features plus `label` (integer 0/1), `run_id`, `sample_index`, `scenario`, and `split` (`train`, `calibration`, `test`). Labels must describe an agreed workload policy; resource-intensive does not automatically mean malicious. Keep independent process sessions in different partitions. The collector's scenario labels are a controlled-test convention, not human-reviewed incident labels.

## Assistance acceptance gate

Use a trusted model and evaluation report produced by this project:

```sh
.venv/bin/python -m arq.cli web --enforce-managed --ml-mode assist \
  --ml-model output/validation/labelled/evaluated_model.joblib \
  --ml-validation output/validation/labelled/evaluation.json
```

Startup refuses assistance unless the model SHA256 matches the report, the evaluation is no older than seven days, test data contains at least 100 normal and 100 anomalous observations in at least three held-out runs, observed precision/recall reach 0.90, false-positive rate is at most 0.05 and every anomalous scenario reaches recall 0.80. Assistance expires after one hour and then falls back to rule decisions. Missing inference resets the corroboration streak. These are configurable-code acceptance requirements, not proof of statistical safety or dataset quality. Report metadata must be trusted; there is no signing authority. Only load trusted joblib files because they contain executable pickle data.

The small supplied smoke dataset is intentionally insufficient for this gate. Do not edit a report to bypass it. Larger representative, untouched workloads and independent review remain necessary. Evaluating multiple candidates on the same test data makes their comparison exploratory; use a new untouched test set before deployment.

## Current retained evidence

`output/validation` contains the full regression log, a 180-observation controlled collection (40 training, 40 calibration, 100 test observations), three repeated fits of each detector, a candidate-acceptance rejection record and nine live benchmark trials (three strategies, three one-second repeats). They are local smoke evidence, not production performance claims. Raw collection and joblib artifacts are kept local/inside the downloadable bundle and remain ignored by Git by default.

The previous combined academic PDF is a historical snapshot from before these changes; its 32-test total and telemetry-crash limitation have been superseded by the current validation log. The prior patentability assessment remains unresolved. This implementation does not establish novelty or a patent grant.
