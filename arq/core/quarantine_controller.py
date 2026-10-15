"""
Adaptive Quarantine Controller.
Enforces multi-stage graduated resource constraints:
- Stage 1: Watchlist (monitoring frequency elevation)
- Stage 2: Soft Quarantine (nice +10, 40% CPU duty cycle, background I/O)
- Stage 3: Hard Quarantine (nice +19, 15% CPU duty cycle, aggressive throttling)
- Dynamic restoration and POSIX signal pulsing (SIGSTOP/SIGCONT) or cgroup limits.
"""

import os
import signal
import subprocess
import threading
import time
from typing import Dict, Optional
from arq.core.process_model import ProcessProfile, QuarantineStage

class DutyCycleThrottler:
    """
    Simulates / enforces fine-grained CPU duty-cycle throttling using precise POSIX SIGSTOP/SIGCONT pulsing.
    Provides sub-second CPU rate limiting without requiring root cgroup access.
    """
    def __init__(self, pid: int, target_ratio: float = 0.30, period_s: float = 0.10):
        self.pid = pid
        self.target_ratio = max(0.05, min(0.95, target_ratio)) # e.g. 0.20 = 20% CPU allowed
        self.period_s = period_s
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def update_ratio(self, new_ratio: float):
        self.target_ratio = max(0.05, min(0.95, new_ratio))

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.3)
        # Ensure process is resumed when throttler stops!
        try:
            os.kill(self.pid, signal.SIGCONT)
        except (ProcessLookupError, PermissionError):
            pass

    def _run(self):
        while self.running:
            try:
                # Active window
                run_time = self.period_s * self.target_ratio
                os.kill(self.pid, signal.SIGCONT)
                time.sleep(run_time)

                # Paused window
                pause_time = self.period_s * (1.0 - self.target_ratio)
                os.kill(self.pid, signal.SIGSTOP)
                time.sleep(pause_time)
            except (ProcessLookupError, PermissionError):
                break
        try:
            os.kill(self.pid, signal.SIGCONT)
        except Exception:
            pass


class QuarantineController:
    """
    Manages graduated process isolation, applying appropriate containment vectors
    based on the current anomaly severity.
    """
    def __init__(self, soft_threshold: float = 0.65, hard_threshold: float = 0.85):
        self.soft_threshold = soft_threshold
        self.hard_threshold = hard_threshold
        self._throttlers: Dict[int, DutyCycleThrottler] = {}
        self._original_nices: Dict[int, int] = {}

    def apply_stage(self, profile: ProcessProfile, target_stage: QuarantineStage, reason: str = "") -> bool:
        """
        Transition process to the desired quarantine stage and apply actuators.
        """
        if profile.stage == target_stage:
            return False

        old_stage = profile.stage
        pid = profile.pid
        profile.stage = target_stage
        profile.quarantine_reason = reason

        # 1. NORMAL / RESTORED
        if target_stage in (QuarantineStage.NORMAL, QuarantineStage.RELEASED):
            self._stop_throttling(pid)
            self._restore_nice(pid, profile)
            if profile.quarantine_start_time:
                duration = time.time() - profile.quarantine_start_time
                profile.quarantine_total_duration += duration
                profile.quarantine_start_time = None
            profile.enforced_duty_cycle = 1.0
            return True

        # 2. WATCHLIST
        elif target_stage == QuarantineStage.WATCHLIST:
            # No hard throttling yet; increased telemetry
            self._stop_throttling(pid)
            profile.enforced_duty_cycle = 1.0
            return True

        # 3. SOFT QUARANTINE
        elif target_stage == QuarantineStage.SOFT_QUARANTINE:
            if not profile.quarantine_start_time:
                profile.quarantine_start_time = time.time()
            self._save_nice(pid, profile)
            self._set_nice(pid, 10)
            self._start_or_update_throttler(pid, target_ratio=0.40)
            profile.enforced_duty_cycle = 0.40
            return True

        # 4. HARD QUARANTINE
        elif target_stage == QuarantineStage.HARD_QUARANTINE:
            if not profile.quarantine_start_time:
                profile.quarantine_start_time = time.time()
            self._save_nice(pid, profile)
            self._set_nice(pid, 19)
            self._start_or_update_throttler(pid, target_ratio=0.15)
            profile.enforced_duty_cycle = 0.15
            return True

        # 5. TERMINATED
        elif target_stage == QuarantineStage.TERMINATED:
            self._stop_throttling(pid)
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            return True

        return False

    def _save_nice(self, pid: int, profile: ProcessProfile):
        if pid not in self._original_nices:
            try:
                current_nice = os.getpriority(os.PRIO_PROCESS, pid)
                self._original_nices[pid] = current_nice
                profile.original_nice = current_nice
            except Exception:
                self._original_nices[pid] = 0

    def _set_nice(self, pid: int, nice_val: int):
        try:
            os.setpriority(os.PRIO_PROCESS, pid, nice_val)
        except Exception:
            # Fallback to renice command
            try:
                subprocess.run(["renice", str(nice_val), "-p", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def _restore_nice(self, pid: int, profile: ProcessProfile):
        orig = self._original_nices.pop(pid, profile.original_nice)
        self._set_nice(pid, orig)

    def _start_or_update_throttler(self, pid: int, target_ratio: float):
        if pid in self._throttlers:
            self._throttlers[pid].update_ratio(target_ratio)
        else:
            t = DutyCycleThrottler(pid, target_ratio=target_ratio)
            t.start()
            self._throttlers[pid] = t

    def _stop_throttling(self, pid: int):
        if pid in self._throttlers:
            self._throttlers[pid].stop()
            del self._throttlers[pid]

    def cleanup_all(self):
        """Clean up all running throttlers and release processes."""
        for pid in list(self._throttlers.keys()):
            self._stop_throttling(pid)
