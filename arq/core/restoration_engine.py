"""Automated hysteresis-based restoration engine for process quarantine management.

Evaluates processes undergoing quarantine, gradually restoring resources as behavioral
telemetry returns to baseline, or triggering terminal action if the process persistently
refuses to yield.
"""

import time
from typing import Dict, Optional, Tuple

from arq.core.process_model import ProcessProfile, QuarantineStage
from arq.core.quarantine_controller import QuarantineController


class RestorationEngine:
    """Evaluates processes undergoing quarantine, applying hysteresis-backed restoration

    or persistent abuse termination safeguards.
    """

    def __init__(
        self,
        controller: QuarantineController,
        hysteresis_cycles: int = 4,
        recovery_threshold: float = 0.40,
        persistence_timeout_s: float = 30.0,
        recovery_score_threshold: Optional[float] = None,
        auto_terminate_persistent: bool = True,
    ) -> None:
        """Initialize the restoration engine.

        Args:
            controller: The QuarantineController instance managing process actuators.
            hysteresis_cycles: Consecutive recovery cycles required before stepping down.
            recovery_threshold: Anomaly score threshold below which a process is recovering.
            persistence_timeout_s: Maximum seconds in HARD_QUARANTINE before termination.
            recovery_score_threshold: Optional alias for recovery_threshold.
            auto_terminate_persistent: Whether to automatically terminate persistent offenders.
        """
        self.controller = controller
        self.hysteresis_cycles = hysteresis_cycles
        self.recovery_threshold = (
            recovery_score_threshold
            if recovery_score_threshold is not None
            else recovery_threshold
        )
        self.recovery_score_threshold = self.recovery_threshold
        self.persistence_timeout_s = persistence_timeout_s
        self.auto_terminate_persistent = auto_terminate_persistent
        self._recovery_counters: Dict[int, int] = {}

    def get_recovery_count(self, pid: int) -> int:
        """Return the current consecutive recovery cycle count for a process."""
        return self._recovery_counters.get(pid, 0)

    def reset_recovery_count(self, pid: int) -> None:
        """Reset the consecutive recovery cycle count for a process."""
        self._recovery_counters[pid] = 0

    def process_cycle(
        self,
        profile: ProcessProfile,
        score: Optional[float] = None,
        current_score: Optional[float] = None,
    ) -> Tuple[QuarantineStage, str]:
        """Closed-loop arbitration logic: determines whether to escalate, step down, restore, or terminate.

        Args:
            profile: The ProcessProfile of the monitored process.
            score: Current composite anomaly score [0.0, 1.0].
            current_score: Optional keyword alias for score.

        Returns:
            Tuple of (new_stage, action_description_string).
        """
        if score is None and current_score is not None:
            score = current_score
        elif score is None:
            score = getattr(profile, "current_score", 0.0)

        pid = profile.pid
        hard_threshold = getattr(self.controller, "hard_threshold", 0.85)
        soft_threshold = getattr(self.controller, "soft_threshold", 0.65)
        watchlist_threshold = 0.40

        # Persistence timeout check in HARD_QUARANTINE
        if profile.stage == QuarantineStage.HARD_QUARANTINE and profile.quarantine_start_time > 0:
            time_in_quarantine = time.time() - profile.quarantine_start_time
            if time_in_quarantine > self.persistence_timeout_s and score >= hard_threshold:
                if self.auto_terminate_persistent:
                    self.controller.apply_stage(
                        profile,
                        QuarantineStage.TERMINATED,
                        reason="Persistent abuse exceeded timeout",
                    )
                    self._recovery_counters[pid] = 0
                    if hasattr(profile, "consecutive_normal_cycles"):
                        profile.consecutive_normal_cycles = 0
                    return QuarantineStage.TERMINATED, "terminated (persistent abuse)"
                else:
                    return profile.stage, "persistent abuse flagged"

        # Check for already terminated processes
        if profile.stage == QuarantineStage.TERMINATED:
            return QuarantineStage.TERMINATED, "terminated (persistent abuse)"

        # Escalation: Hard Quarantine (score >= hard_threshold)
        if score >= hard_threshold:
            self._recovery_counters[pid] = 0
            if hasattr(profile, "consecutive_normal_cycles"):
                profile.consecutive_normal_cycles = 0
            if profile.stage < QuarantineStage.HARD_QUARANTINE:
                self.controller.apply_stage(
                    profile,
                    QuarantineStage.HARD_QUARANTINE,
                    reason=f"Severe anomaly score {score:.2f}",
                )
            return QuarantineStage.HARD_QUARANTINE, "nice +19, 15% duty cycle"

        # Escalation: Soft Quarantine (score >= soft_threshold)
        if score >= soft_threshold:
            self._recovery_counters[pid] = 0
            if hasattr(profile, "consecutive_normal_cycles"):
                profile.consecutive_normal_cycles = 0
            if profile.stage < QuarantineStage.SOFT_QUARANTINE:
                self.controller.apply_stage(
                    profile,
                    QuarantineStage.SOFT_QUARANTINE,
                    reason=f"Moderate anomaly score {score:.2f}",
                )
                return QuarantineStage.SOFT_QUARANTINE, "nice +10, 40% duty cycle"
            elif profile.stage == QuarantineStage.HARD_QUARANTINE:
                return profile.stage, "nice +19, 15% duty cycle"
            return profile.stage, "nice +10, 40% duty cycle"

        # Escalation: Watchlist (score >= watchlist_threshold)
        if score >= watchlist_threshold:
            self._recovery_counters[pid] = 0
            if hasattr(profile, "consecutive_normal_cycles"):
                profile.consecutive_normal_cycles = 0
            if profile.stage < QuarantineStage.WATCHLIST:
                self.controller.apply_stage(
                    profile,
                    QuarantineStage.WATCHLIST,
                    reason=f"Behavioral elevation score {score:.2f}",
                )
                return QuarantineStage.WATCHLIST, "elevated monitoring"
            elif profile.stage == QuarantineStage.HARD_QUARANTINE:
                return profile.stage, "nice +19, 15% duty cycle"
            elif profile.stage == QuarantineStage.SOFT_QUARANTINE:
                return profile.stage, "nice +10, 40% duty cycle"
            return profile.stage, "elevated monitoring"

        # De-escalation logic: score < recovery_threshold
        current_profile_cycles = getattr(profile, "consecutive_normal_cycles", 0)
        current_counter = self._recovery_counters.get(pid, 0)
        if current_profile_cycles > current_counter:
            new_count = current_profile_cycles
        else:
            new_count = current_counter + 1

        self._recovery_counters[pid] = new_count
        if hasattr(profile, "consecutive_normal_cycles"):
            profile.consecutive_normal_cycles = new_count

        # Normal baseline
        if profile.stage == QuarantineStage.NORMAL:
            return QuarantineStage.NORMAL, "monitoring"

        # Check consecutive cycles against hysteresis threshold
        if new_count >= self.hysteresis_cycles:
            self._recovery_counters[pid] = 0
            if hasattr(profile, "consecutive_normal_cycles"):
                profile.consecutive_normal_cycles = 0

            if profile.stage == QuarantineStage.HARD_QUARANTINE:
                self.controller.apply_stage(
                    profile,
                    QuarantineStage.SOFT_QUARANTINE,
                    reason="Hysteresis recovery: stepping down to SOFT",
                )
                return QuarantineStage.SOFT_QUARANTINE, "stepping down"

            elif profile.stage == QuarantineStage.SOFT_QUARANTINE:
                self.controller.apply_stage(
                    profile,
                    QuarantineStage.WATCHLIST,
                    reason="Hysteresis recovery: stepping down to WATCHLIST",
                )
                return QuarantineStage.WATCHLIST, "stepping down"

            elif profile.stage == QuarantineStage.WATCHLIST:
                self.controller.apply_stage(
                    profile,
                    QuarantineStage.NORMAL,
                    reason="Hysteresis recovery: fully restored to NORMAL",
                )
                return QuarantineStage.NORMAL, "fully restored"

        # Under recovery threshold but not yet reached hysteresis cycles
        if profile.stage == QuarantineStage.HARD_QUARANTINE:
            return profile.stage, "nice +19, 15% duty cycle"
        elif profile.stage == QuarantineStage.SOFT_QUARANTINE:
            return profile.stage, "nice +10, 40% duty cycle"
        elif profile.stage == QuarantineStage.WATCHLIST:
            return profile.stage, "elevated monitoring"

        return profile.stage, "monitoring"
