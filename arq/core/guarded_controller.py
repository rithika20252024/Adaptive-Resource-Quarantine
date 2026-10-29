"""Actuate only registered live child handles; dry-run is the default."""
import os
import threading
import time
from collections import deque
from arq.core.quarantine_controller import QuarantineController
from arq.core.process_model import QuarantineStage


class GuardedController(QuarantineController):
    def __init__(self, enforce=False, allow_termination=False, lease_s=5):
        super().__init__()
        if lease_s<=0:raise ValueError('lease_s must be positive')
        self.enforce=enforce;self.allow_termination=allow_termination
        self.managed={};self._profiles={};self.audit=deque(maxlen=1000);self.lease_s=lease_s
        self._guard=threading.RLock();self._heartbeat=time.monotonic()
        self._closed=threading.Event()
        self._watch=threading.Thread(target=self._watchdog,daemon=True)
        self._watch.start()

    def register(self, handle):
        if handle.pid<=1 or handle.pid==os.getpid() or not handle.process.is_alive():
            raise ValueError('Only live explicitly managed children may be registered')
        with self._guard:self.managed[handle.pid]=handle

    def heartbeat(self):self._heartbeat=time.monotonic()

    def _set_nice_priority(self,pid,priority):
        # Avoid irreversibly lowering scheduling priority without restore permission.
        return False

    def apply_stage(self,profile,new_stage,reason=''):
        with self._guard:
            self._profiles[profile.pid] = profile
            handle=self.managed.get(profile.pid)
            allowed=handle is not None and handle.pid==profile.pid and handle.process.is_alive()
            if not allowed:status='denied_unmanaged_or_exited'
            elif new_stage==QuarantineStage.TERMINATED and not self.allow_termination:status='denied_termination'
            elif not self.enforce:status='dry_run'
            elif not hasattr(__import__('signal'),'SIGSTOP'):status='unsupported_platform'
            else:
                status='requested'
                super().apply_stage(profile,new_stage,reason)
            self.audit.append({'pid':profile.pid,'proposed_stage':new_stage.name,'status':status,'reason':reason})
            return status

    def _watchdog(self):
        while not self._closed.wait(.2):
            if time.monotonic()-self._heartbeat>self.lease_s:
                with self._guard:
                    self.cleanup_all()
                    self.audit.append({'status':'lease_expired_restrictions_released'})
                    # Lease expiry disables further actuation until explicit restart.
                    self.enforce=False
                    for profile in self._profiles.values():
                        profile.enforced_duty_cycle=1.0
                        if profile.is_quarantined():profile.stage=QuarantineStage.WATCHLIST

    def close(self):
        self._closed.set();self._watch.join(timeout=1)
        with self._guard:self.cleanup_all()
