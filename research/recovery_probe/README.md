# Local recovery-verification experiment

This extension tests a specific ARQ failure mode: a CPU restriction can make a still-demanding process appear recovered. It remains an opt-in research module. Prepared for repository publication at the user request on 30 October 2026. No patent filing has been performed.

## Reproduce

From the project root, using Python 3.10 or later:

```sh
python -m unittest tests.test_recovery_probe -v
PYTHONPATH=. python research/recovery_probe/evaluate.py
```

No new dependencies are required. The script writes `results/synthetic-comparison.json` and compares the actual legacy scorer/restoration engine, with a simulated actuator, against the new runner. The workload model is `observed CPU = min(demand, duty)`. Latency is a constructed per-window value with seeded small noise; the repeated latency samples are not independent request measurements. The scenarios exercise policy behavior; they are not empirical evidence of classifier accuracy.

## Synthetic results

100 seeded trials per scenario, 500 total:

| Constructed scenario | Legacy relaxed restriction | New probe relaxed restriction |
|---|---:|---:|
| Demand subsided, stable protected service | 100/100 | 100/100 |
| High demand hidden by existing restriction | 100/100 | 0/100 |
| Release raises protected-service latency | 100/100 | 0/100 |
| Restricted-control latency drifts | 100/100 | 0/100 |
| Offered workload rate changes | 100/100 | 0/100 |

Legacy receives only its original CPU telemetry, while the new runner receives added protected-service observations; this is a comparison of complete policies with different inputs, not an equal-information algorithm ranking. Removing the normalized-demand check makes the new policy relax in 100/100 hidden-demand cases in this model. Raw trials and that ablation are retained in JSON. Do not interpret these constructed outcomes as real-world precision/recall or guaranteed safe recovery.

## Live integration contract

`RecoveryProbe.run(identity, base, candidate, apply, observe)` accepts an allocation callback and a window-measurement callback. A `Window` must carry the same process-incarnation identity, measured duty, observation duration, CPU seconds and protected-service latency samples plus offered load. Do not substitute a nominal duty for measured actuation without marking that measurement limitation. `ExistingThrottlerAdapter.apply` changes a currently active ARQ throttler; use an external session lock to exclude the legacy restoration loop and other writers throughout the experiment.

Supply a watchdog, bounded sampler, process-identity verification, actual actuation measurement, sampling warm-up and an external repeated-probe budget before live use. This prototype does not implement those deployment components and is not enabled in the dashboard.

See `TECHNICAL_DISCLOSURE.md` for the exact method, claim skeleton and limits, and `PRIOR_ART_COMPARISON.md` for overlap and outstanding search work. New test logs cover ordinary recovery, hidden demand, absolute/relative protected latency, drift, invalid input, budget refusal, callback failures, rollback and the throttler bridge.

## Validation status on this host

32 tests passed across scorer, optional inference interface, quarantine, restoration and the new probe modules (including 12 new probe tests). Full-suite success is not claimed: ML training could not import optional `joblib`, and the unchanged macOS monitor test process exited with signal 11. Module-specific logs and return codes are retained in `results/`. Resolve and validate native telemetry before any live integration.
