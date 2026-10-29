"""Opt-in bracketed recovery verification; not a proof of causality or safety.

Caller supplies serialized actuation and same-window observations for one stable
process identity. No production/default restoration path is changed.
"""
from dataclasses import dataclass
import math
from statistics import median
from typing import Callable, Tuple


@dataclass(frozen=True)
class Window:
    identity: str                 # include PID + process creation identity
    duty: float                   # effective duty measured by the adapter
    duration_s: float
    cpu_seconds: float            # one-core CPU demand contract
    latencies_ms: Tuple[float, ...]
    request_rate: float
    healthy: bool = True

    @property
    def p95(self):
        values = sorted(self.latencies_ms)
        return values[math.ceil(.95 * len(values)) - 1]


@dataclass(frozen=True)
class ProbePolicy:
    window_s: float = .5
    rounds: int = 2
    extra_cpu_budget_s: float = .30
    slo_ms: float = 20.0
    max_latency_increase_ms: float = 2.0
    max_control_drift_ms: float = 1.0
    max_load_drift: float = .10
    max_normalized_demand: float = .70
    min_requests: int = 20

    def __post_init__(self):
        positive = (self.window_s, self.extra_cpu_budget_s, self.slo_ms,
                    self.max_latency_increase_ms, self.max_control_drift_ms,
                    self.max_load_drift, self.max_normalized_demand)
        if any(not math.isfinite(x) or x <= 0 for x in positive):
            raise ValueError('Policy bounds must be finite and positive')
        if (not isinstance(self.rounds, int) or self.rounds < 1 or
                not isinstance(self.min_requests, int) or self.min_requests < 2):
            raise ValueError('Invalid rounds or sample count')
        if self.max_load_drift >= 1 or self.max_normalized_demand > 1:
            raise ValueError('Invalid fractional bound')


@dataclass(frozen=True)
class ProbeResult:
    accepted: bool
    reason: str
    final_duty: float
    reserved_extra_cpu_s: float
    trace: tuple


class RecoveryProbe:
    """Serialized A-B-A experiment with restore-before-commit semantics.

    A=existing restriction, B=one proposed relaxation. Every B window is
    bracketed by A windows. Require low grant-normalized CPU consumption,
    stable offered load and control latency, and protected-service SLO slack.
    A budget reserves incremental *nominal granted* one-core time, not a
    real-time enforcement guarantee. Caller must impose an external watchdog
    if callbacks/OS scheduling can stall. Exceptions propagate after rollback.
    """
    def __init__(self, policy=ProbePolicy()):
        self.policy = policy

    def run(self, identity: str, base: float, candidate: float,
            apply: Callable[[float], None],
            observe: Callable[[float, float], Window]) -> ProbeResult:
        p = self.policy
        if not identity or not (0 < base < candidate <= 1):
            raise ValueError('Require identity and 0 < base < candidate <= 1')
        reserve = (candidate - base) * p.window_s * p.rounds
        trace = []
        if reserve > p.extra_cpu_budget_s + 1e-12:
            return ProbeResult(False, 'budget_exceeded', base, 0, ())

        def take(duty, label):
            apply(duty)
            w = observe(duty, p.window_s)
            trace.append({'phase': label, 'window': w.__dict__})
            if w.identity != identity:
                return None, 'identity_changed'
            nums = (w.duty, w.duration_s, w.cpu_seconds, w.request_rate,
                    *w.latencies_ms)
            if (not all(math.isfinite(x) for x in nums) or
                    not w.healthy or len(w.latencies_ms) < p.min_requests or
                    any(x < 0 for x in w.latencies_ms) or
                    w.cpu_seconds < 0 or w.request_rate <= 0):
                return None, 'invalid_or_insufficient_observation'
            if (abs(w.duty-duty) > .005 or
                    abs(w.duration_s-p.window_s) > p.window_s*.10 or
                    w.cpu_seconds > w.duration_s * 1.05):
                return None, 'actuation_or_timing_mismatch'
            if w.p95 > p.slo_ms:
                return None, 'protected_slo_exceeded'
            return w, ''

        reason = 'verified_step'
        try:
            for _ in range(p.rounds):
                before, error = take(base, 'control_before')
                if error:
                    reason = error
                    break
                trial, error = take(candidate, 'release_probe')
                if error:
                    reason = error
                    break
                # Revoke B before any positive decision or post-control sample.
                after, error = take(base, 'control_after')
                if error:
                    reason = error
                    break
                rates = [w.request_rate for w in (before, trial, after)]
                if max(rates)/min(rates)-1 > p.max_load_drift:
                    reason = 'offered_load_changed'
                    break
                if abs(before.p95-after.p95) > p.max_control_drift_ms:
                    reason = 'control_drift'
                    break
                control = median((before.p95, after.p95))
                if trial.p95-control > p.max_latency_increase_ms:
                    reason = 'release_harms_protected_service'
                    break
                demand = trial.cpu_seconds / (trial.duration_s * trial.duty)
                if demand > p.max_normalized_demand:
                    reason = 'restriction_masked_demand'
                    break
        finally:
            # Rollback failure must raise; never return a false success.
            apply(base)
        if reason == 'verified_step':
            try:
                apply(candidate)
            except BaseException:
                apply(base)
                raise
            return ProbeResult(True, reason, candidate, reserve, tuple(trace))
        return ProbeResult(False, reason, base, reserve, tuple(trace))


class ExistingThrottlerAdapter:
    """Opt-in bridge to an already quarantined ARQ process.

    Run under the same external lock as restoration/cleanup; the legacy engine
    must not act concurrently. Keeps stage and niceness unchanged. A successful
    result authorizes only a duty relaxation, not full application recovery.
    Identity checks and measurements are the observe callback's responsibility.
    """
    def __init__(self, controller, profile):
        self.controller, self.profile = controller, profile

    def apply(self, duty):
        with self.controller._lock:
            throttler = self.controller._throttlers.get(self.profile.pid)
            if throttler is None or not self.profile.is_quarantined():
                raise RuntimeError('An active quarantined throttler is required')
            throttler.update_ratio(duty)
            self.profile.enforced_duty_cycle = duty
