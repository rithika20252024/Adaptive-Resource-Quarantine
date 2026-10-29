# ARQ: bracketed verification before relaxing CPU quarantine

Research disclosure draft — 30 October 2026. Not a patent filing or a finding of novelty.

## Problem and implemented distinction

A restricted process can show low CPU usage because the controller denied it execution time. Four low anomaly readings therefore cannot, by themselves, establish that its resource demand has subsided. In the existing implementation, `RestorationEngine` makes step-down decisions from scores observed while the restrictions remain active.

The new opt-in `RecoveryProbe` tests one proposed increase in CPU duty allocation. For each of two rounds it collects a restricted control window A, a temporary release window B, and a second restricted window A. It restores the original allocation before evaluating the result and commits the proposed allocation only after every round passes. This is an experimental verification protocol, not a claim that probing or feedback control is new.

The decision requires all of the following:

1. Observations identify the same process incarnation, contain sufficient protected-service latency samples, and report finite, healthy measurements.
2. Reported actuation and observation duration agree with the requested experiment.
3. Protected-service p95 remains within the configured absolute SLO.
4. Offered request rate remains within a drift bound across all three windows.
5. Before/after restricted-control latency is stable; otherwise the result is inconclusive.
6. Probe p95 does not exceed the median of the two restricted-control p95 values by more than the configured increase allowance.
7. CPU seconds consumed in the release window, divided by its duration and duty allocation, remain below the demand threshold. Saturated use of the larger grant is evidence against recovery.
8. The nominal additional CPU-grant reservation for the complete experiment fits the per-call budget.

Defaults: 0.5 s windows, two rounds, 0.30 nominal additional core-seconds, 20 ms SLO, 2 ms relative latency allowance, 1 ms control-drift allowance, 10% offered-load drift, demand ratio at most 0.70, and at least 20 latency samples per window. These are research configuration choices, not validated universal constants.

## Architecture and implementation status

`arq/core/recovery_probe.py` contains the policy, window contract, decision trace and transactional experiment runner. `ExistingThrottlerAdapter` connects allocation changes to an existing quarantined ARQ duty-cycle throttler. It updates the actual throttler and profile allocation while retaining the existing stage and niceness. This permits a verified allocation step without claiming that the entire application has recovered.

The module is opt-in. It is **not wired into the dashboard or default restoration loop**. No ML model controls this decision. A live integration must serialize this runner against ordinary restoration and cleanup, supply trustworthy same-window measurements and verify process creation identity. The test adapter exercises this bridge without sending signals to user processes.

## Failure handling

The original duty is reapplied in a `finally` block on success, rejection and observation failure, before any final commit. Failure to restore raises an exception rather than returning success. If the final allocation command fails, restoration is attempted again and the exception propagates. Budget rejection occurs before actuation. The trace records phases and measurements.

This does not survive controller death, OS signal delivery failure or a callback that never returns. It requires an independent watchdog for those cases. The reservation bounds nominal requested additional allocation, not real-time CPU consumption; timing validation occurs after observation and cannot undo an overlong window. Repeated calls require an external cumulative budget/cooldown. A low normalized CPU measurement can also arise from contention or blocking, so the test does not prove latent demand or causality. Memory, I/O demand, multicore CPU normalization and application data integrity are outside this prototype's contract.

## Candidate claim skeleton for professional review

A computer-implemented process-quarantine restoration method comprising: retaining a restricted CPU allocation for an identified process incarnation; reserving a nominal additional execution allowance for a proposed relaxed allocation; collecting successive restricted, relaxed and restricted observation windows; returning to the restricted allocation before evaluating the windows; rejecting the proposal when observation validity, offered-load stability, restricted-control stability, protected-service latency or grant-normalized CPU-consumption conditions fail; and applying the relaxed allocation only after the required complete window groups pass, while recording their observations and decision.

Possible dependent limitations: (a) repeated brackets under the same policy; (b) both absolute and relative protected-latency checks; (c) process-incarnation and actuation agreement checks; (d) fail-closed handling of missing measurements; (e) restoring the original allocation on exceptions before any success result.

These limitations describe implemented behavior. They are **not established novel or non-obvious claims**. Transactional cleanup, intervention experiments, admission budgets and feedback thresholds are individually familiar. A patent agent must assess whether the specific combination has an inventive technical interaction beyond ordinary engineering.

## Technical effect to investigate

Avoid releasing an allocation restriction merely because its own operation depressed observed CPU use, while checking impact on a protected workload. The present evidence establishes behavior under explicitly constructed scenarios and regression tests. It does not establish hardware latency improvement, reliable anomaly classification, production safety, state preservation or generalization.

## Disclosure and authorship record

Base inspected: public repository `vaishnavikarri08-crypto/adaptive-resource-quarantine`, commit `40e3d28`. Git commit dates do not establish the first public availability date. Existing public content and any earlier patent filing must be reviewed separately. New files were developed locally with AI assistance. Repository publication was subsequently requested on 30 October 2026; retain the publication commit and date as disclosure evidence. Do not list human inventors based solely on repository ownership or AI-produced claim text; record the actual human conception and obtain institutional/agent review.
