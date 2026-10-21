"""Graduated quarantine enforcement via dynamic duty-cycle throttling and scheduling niceness."""

import logging
import os
import signal
import subprocess
import threading
import time
from typing import Dict, Optional

from arq.core.process_model import ProcessProfile, QuarantineStage

logger = logging.getLogger(__name__)


class DutyCycleThrottler:
    """Regulates process execution duty cycle using high-frequency SIGSTOP and SIGCONT pulsing.

    A dedicated daemon thread switches the target process between active execution
    and suspended state to cap CPU consumption at a deterministic percentage.
    """

    def __init__(
        self,
        pid: int,
        target_ratio: float = 0.30,
        period_s: float = 0.10,
    ) -> None:
        """Initialize duty cycle throttler for a process.

        Args:
            pid: The process ID to throttle.
            target_ratio: Fraction of the cycle during which process is active (0.01 - 1.0).
            period_s: Duration in seconds of one full stop/cont cycle.
        """
        self.pid: int = pid
        self.target_ratio: float = max(0.01, min(1.0, float(target_ratio)))
        self.period_s: float = period_s
        self._stop_event: threading.Event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()

    def start(self) -> None:
        """Launch background daemon thread to perform pulse throttling."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name=f"DutyCycleThrottler-{self.pid}",
                daemon=True,
            )
            self._thread.start()

    def update_ratio(self, new_ratio: float) -> None:
        """Update duty cycle ratio dynamically without stopping the thread.

        Args:
            new_ratio: New active fraction in [0.01, 1.0].
        """
        self.target_ratio = max(0.01, min(1.0, float(new_ratio)))

    def stop(self) -> None:
        """Stop throttling and guarantee the process is resumed via SIGCONT."""
        self._stop_event.set()
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                self._thread.join(timeout=max(0.5, self.period_s * 2))
                self._thread = None

        # Always ensure target process is resumed upon leaving throttled state
        try:
            os.kill(self.pid, signal.SIGCONT)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def _run(self) -> None:
        """Internal execution loop pulsing SIGCONT and SIGSTOP."""
        try:
            while not self._stop_event.is_set():
                ratio = max(0.01, min(1.0, self.target_ratio))
                run_time = self.period_s * ratio
                stop_time = self.period_s * (1.0 - ratio)

                # Active execution slice: resume process
                try:
                    os.kill(self.pid, signal.SIGCONT)
                except (ProcessLookupError, PermissionError, OSError):
                    break

                if self._stop_event.wait(run_time):
                    break

                # Suspended slice: halt process
                if stop_time > 0.001:
                    try:
                        os.kill(self.pid, signal.SIGSTOP)
                    except (ProcessLookupError, PermissionError, OSError):
                        break

                    if self._stop_event.wait(stop_time):
                        break
        finally:
            # Safety measure: resume process on loop termination
            try:
                os.kill(self.pid, signal.SIGCONT)
            except (ProcessLookupError, PermissionError, OSError):
                pass


class QuarantineController:
    """Manages graduated process isolation stages, process priorities, and duty cycle throttlers."""

    def __init__(
        self,
        soft_threshold: float = 0.65,
        hard_threshold: float = 0.85,
    ) -> None:
        """Initialize the QuarantineController.

        Args:
            soft_threshold: Anomaly score boundary triggering SOFT_QUARANTINE.
            hard_threshold: Anomaly score boundary triggering HARD_QUARANTINE.
        """
        self.soft_threshold: float = soft_threshold
        self.hard_threshold: float = hard_threshold
        self._throttlers: Dict[int, DutyCycleThrottler] = {}
        self._lock: threading.Lock = threading.Lock()

    def _set_nice_priority(self, pid: int, priority: int) -> bool:
        """Set process nice scheduling priority via os.setpriority or renice command fallback.

        Args:
            pid: The process ID.
            priority: Nice value (-20 to 19).

        Returns:
            True if priority update succeeded, False otherwise.
        """
        # Primary: native os.setpriority
        try:
            if hasattr(os, "setpriority") and hasattr(os, "PRIO_PROCESS"):
                os.setpriority(os.PRIO_PROCESS, pid, priority)
                return True
        except (PermissionError, OSError) as exc:
            logger.debug("os.setpriority failed for pid %d with %s", pid, exc)

        # Fallback: renice executable
        try:
            res = subprocess.run(
                ["renice", str(priority), "-p", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            return res.returncode == 0
        except (subprocess.SubprocessError, OSError, FileNotFoundError) as exc:
            logger.debug("renice subprocess failed for pid %d with %s", pid, exc)
            return False

    def apply_stage(
        self,
        profile: ProcessProfile,
        new_stage: QuarantineStage,
        reason: str = "",
    ) -> None:
        """Transition a process profile to a new quarantine stage and enforce corresponding controls.

        - SOFT_QUARANTINE: Renices process to +10, starts throttler at 40% duty cycle.
        - HARD_QUARANTINE: Renices process to +19, starts or updates throttler to 15% duty cycle.
        - NORMAL / WATCHLIST: Stops throttler, resets process priority to 0.
        - TERMINATED: Stops throttler, issues graceful SIGTERM, followed by SIGKILL.

        Args:
            profile: Target ProcessProfile to modify and enforce.
            new_stage: Target QuarantineStage to apply.
            reason: Explanation or diagnostic reason for the transition.
        """
        old_stage = profile.stage
        profile.stage = new_stage
        if reason:
            profile.quarantine_reason = reason

        # Maintain quarantine timing
        if new_stage in (QuarantineStage.SOFT_QUARANTINE, QuarantineStage.HARD_QUARANTINE):
            if profile.quarantine_start_time == 0.0:
                profile.quarantine_start_time = time.time()
        elif new_stage == QuarantineStage.NORMAL:
            profile.quarantine_start_time = 0.0

        pid = profile.pid

        with self._lock:
            if new_stage == QuarantineStage.SOFT_QUARANTINE:
                self._set_nice_priority(pid, 10)
                if pid in self._throttlers:
                    self._throttlers[pid].update_ratio(0.40)
                else:
                    throttler = DutyCycleThrottler(pid, target_ratio=0.40)
                    throttler.start()
                    self._throttlers[pid] = throttler
                profile.enforced_duty_cycle = 0.40

            elif new_stage == QuarantineStage.HARD_QUARANTINE:
                self._set_nice_priority(pid, 19)
                if pid in self._throttlers:
                    self._throttlers[pid].update_ratio(0.15)
                else:
                    throttler = DutyCycleThrottler(pid, target_ratio=0.15)
                    throttler.start()
                    self._throttlers[pid] = throttler
                profile.enforced_duty_cycle = 0.15

            elif new_stage in (QuarantineStage.NORMAL, QuarantineStage.WATCHLIST):
                if pid in self._throttlers:
                    self._throttlers[pid].stop()
                    del self._throttlers[pid]
                self._set_nice_priority(pid, 0)
                profile.enforced_duty_cycle = 1.0

            elif new_stage == QuarantineStage.TERMINATED:
                if pid in self._throttlers:
                    self._throttlers[pid].stop()
                    del self._throttlers[pid]
                profile.enforced_duty_cycle = 0.0

                # Attempt SIGTERM first, followed by SIGKILL if process remains
                try:
                    os.kill(pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    pass

                time.sleep(0.5)

                try:
                    os.kill(pid, 0)
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass

        logger.info(
            "PID %d stage transitioned from %s to %s (duty_cycle=%.2f, reason='%s')",
            pid,
            old_stage.name,
            new_stage.name,
            profile.enforced_duty_cycle,
            profile.quarantine_reason,
        )

    def cleanup_all(self) -> None:
        """Stop all active throttlers and ensure all tracked processes are resumed with SIGCONT."""
        with self._lock:
            active_pids = list(self._throttlers.keys())
            for pid in active_pids:
                throttler = self._throttlers.pop(pid, None)
                if throttler is not None:
                    throttler.stop()
                try:
                    os.kill(pid, signal.SIGCONT)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
