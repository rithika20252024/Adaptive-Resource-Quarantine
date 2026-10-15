"""
Dynamic Restoration & Safe De-Quarantine Engine.
Implements closed-loop re-evaluation inside quarantine, hysteresis-backed de-escalation,
and persistent abuse termination safeguards.
"""

import time
from typing import Tuple
from arq.core.process_model import ProcessProfile, QuarantineStage
from arq.core.quarantine_controller import QuarantineController

class RestorationEngine:
    """
    Evaluates processes undergoing quarantine, gradually restoring resources
    as behavioral telemetry returns to baseline, or triggering terminal action
    if the process persistently refuses to yield.
    """
    def __init__(
        self,
        controller: QuarantineController,
        recovery_score_threshold: float = 0.40,  # Score must drop below this to qualify as normal
        hysteresis_cycles: int = 4,              # Consecutive normal cycles required before step-down
        persistence_timeout_s: float = 25.0,     # Max time in HARD_QUARANTINE before termination
        auto_terminate_persistent: bool = True   # Automatically kill if persistent
    ):
        self.controller = controller
        self.recovery_score_threshold = recovery_score_threshold
        self.hysteresis_cycles = hysteresis_cycles
        self.persistence_timeout_s = persistence_timeout_s
        self.auto_terminate_persistent = auto_terminate_persistent

    def process_cycle(self, profile: ProcessProfile, current_score: float) -> Tuple[QuarantineStage, str]:
        """
        Closed-loop arbitration logic: determines whether to escalate, step down, restore, or terminate.
        """
        stage = profile.stage
        now = time.time()

        # Check for persistent unrecoverable state
        if stage == QuarantineStage.HARD_QUARANTINE and profile.quarantine_start_time:
            time_in_quarantine = now - profile.quarantine_start_time
            if time_in_quarantine > self.persistence_timeout_s and current_score >= 0.85:
                if self.auto_terminate_persistent:
                    self.controller.apply_stage(profile, QuarantineStage.TERMINATED, reason="Persistent exhaustion exceeded timeout")
                    return QuarantineStage.TERMINATED, f"Terminated after {time_in_quarantine:.1f}s persistent exhaustion"
                else:
                    self.controller.apply_stage(profile, QuarantineStage.TERMINATION_PENDING, reason="Flagged for manual termination")
                    return QuarantineStage.TERMINATION_PENDING, "Persistent exhaustion flagged"

        # Escalation Logic (if score is rising)
        if current_score >= self.controller.hard_threshold:
            profile.consecutive_normal_cycles = 0
            if stage != QuarantineStage.HARD_QUARANTINE:
                self.controller.apply_stage(profile, QuarantineStage.HARD_QUARANTINE, reason=f"Severe anomaly score {current_score:.2f}")
                return QuarantineStage.HARD_QUARANTINE, f"Escalated to HARD_QUARANTINE (Score: {current_score:.2f})"
            return stage, "Maintained in HARD_QUARANTINE"

        elif current_score >= self.controller.soft_threshold:
            profile.consecutive_normal_cycles = 0
            if stage < QuarantineStage.SOFT_QUARANTINE:
                self.controller.apply_stage(profile, QuarantineStage.SOFT_QUARANTINE, reason=f"Moderate anomaly score {current_score:.2f}")
                return QuarantineStage.SOFT_QUARANTINE, f"Quarantined to SOFT_QUARANTINE (Score: {current_score:.2f})"
            elif stage == QuarantineStage.HARD_QUARANTINE and profile.consecutive_normal_cycles >= self.hysteresis_cycles:
                # Step down from hard to soft
                self.controller.apply_stage(profile, QuarantineStage.SOFT_QUARANTINE, reason="Behavior improved slightly")
                profile.consecutive_normal_cycles = 0
                return QuarantineStage.SOFT_QUARANTINE, "De-escalated to SOFT_QUARANTINE"
            return stage, "Maintained in SOFT_QUARANTINE"

        # Restoration / Step-Down Logic (Score is low and recovering)
        elif current_score < self.recovery_score_threshold:
            if stage == QuarantineStage.HARD_QUARANTINE:
                if profile.consecutive_normal_cycles >= self.hysteresis_cycles:
                    self.controller.apply_stage(profile, QuarantineStage.SOFT_QUARANTINE, reason="Recovering: stepping down to SOFT")
                    profile.consecutive_normal_cycles = 0
                    return QuarantineStage.SOFT_QUARANTINE, "Stepped down from HARD to SOFT"
                else:
                    return stage, f"Verifying recovery stability ({profile.consecutive_normal_cycles}/{self.hysteresis_cycles})"

            elif stage == QuarantineStage.SOFT_QUARANTINE:
                if profile.consecutive_normal_cycles >= self.hysteresis_cycles:
                    self.controller.apply_stage(profile, QuarantineStage.WATCHLIST, reason="Recovered: stepping down to WATCHLIST")
                    profile.consecutive_normal_cycles = 0
                    return QuarantineStage.WATCHLIST, "Stepped down from SOFT to WATCHLIST"
                else:
                    return stage, f"Verifying recovery stability ({profile.consecutive_normal_cycles}/{self.hysteresis_cycles})"

            elif stage == QuarantineStage.WATCHLIST:
                if profile.consecutive_normal_cycles >= self.hysteresis_cycles:
                    self.controller.apply_stage(profile, QuarantineStage.NORMAL, reason="Fully restored to normal execution")
                    profile.consecutive_normal_cycles = 0
                    return QuarantineStage.NORMAL, "Fully Restored to NORMAL execution"
                else:
                    return stage, f"Verifying final baseline stability ({profile.consecutive_normal_cycles}/{self.hysteresis_cycles})"

        return stage, "Steady state"
