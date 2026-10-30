"""Web dashboard server using Python standard library only.

Provides real-time telemetry streaming, interactive quarantine actuators,
and anomaly monitoring over HTTP.
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import math
import os
from socketserver import ThreadingMixIn
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from arq.core.anomaly_scorer import AnomalyScorer
from arq.core.monitor import ProcessMonitor
from arq.core.process_model import ProcessProfile, QuarantineStage
from arq.core.ml_pipeline import extract_features
from arq.core.guarded_controller import GuardedController
from arq.core.ml_policy import MLAssistedPolicy, validate_candidate
from arq.core.restoration_engine import RestorationEngine


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server using daemon threads to prevent hang on shutdown."""

    daemon_threads = True


class ARQDashboardState:
    """State manager for telemetry monitoring, process profiles, and simulated workloads."""

    def __init__(self, enforce=False, ml_mode='shadow', model_path=None, validation_path=None, allow_termination=False) -> None:
        self.monitor = ProcessMonitor()
        self.scorer = AnomalyScorer()
        # Shadow mode: ML scores are recorded but never control quarantine.
        self.ml_artifact = None
        self.ml_load_error = None
        model_path = model_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "models", "arq", "isolation_forest.joblib",
        )
        if os.path.isfile(model_path):
            try:
                from arq.core.ml_training import load_isolation_forest
                self.ml_artifact = load_isolation_forest(model_path)
            except Exception as exc:
                # Keep the dashboard operational if the optional model is invalid.
                self.ml_load_error = str(exc)
        if ml_mode == 'assist':
            if self.ml_artifact is None or not validation_path:
                raise ValueError('ML assistance requires a model and validation report')
            validate_candidate(model_path, validation_path)
        self.ml_policy = MLAssistedPolicy(ml_mode, validated=ml_mode == 'assist')
        self.controller = GuardedController(enforce=enforce, allow_termination=allow_termination)
        self.restoration = RestorationEngine(self.controller, auto_terminate_persistent=allow_termination)
        self.profiles: Dict[int, ProcessProfile] = {}
        self.simulated_workloads: Dict[int, Any] = {}
        self.lock = threading.Lock()
        self.history: List[Dict[str, Any]] = []

    def add_simulated(self, w_type: str) -> Optional[int]:
        """Spawn a simulated anomalous workload.

        Args:
            w_type: 'cpu', 'mem', or 'burst'.

        Returns:
            PID of spawned workload, or None on error.
        """
        with self.lock:
            if len(self.simulated_workloads) >= 8:
                return None
            try:
                from arq.simulation.workloads import WorkloadSimulator
            except ImportError:
                return None

            if w_type == "cpu":
                h = WorkloadSimulator.start_cpu_burner()
            elif w_type == "mem":
                h = WorkloadSimulator.start_memory_leaker(max_mb=64)
            elif w_type == "burst":
                h = WorkloadSimulator.start_transient_burst()
            else:
                return None

            self.controller.register(h)
            self.simulated_workloads[h.pid] = h
            self.profiles[h.pid] = ProcessProfile(pid=h.pid, name=h.name)
            return h.pid

    def stop_simulated(self, pid: int) -> bool:
        """Stop a simulated workload and cleanup its profile.

        Args:
            pid: Process ID to terminate and release.
        """
        with self.lock:
            if pid not in self.simulated_workloads:
                return False
            if pid in self.simulated_workloads:
                try:
                    if pid in self.profiles:
                        self.controller.apply_stage(self.profiles[pid], QuarantineStage.NORMAL)
                    self.simulated_workloads[pid].stop()
                except Exception:
                    pass
                del self.simulated_workloads[pid]

            if pid in self.profiles:
                try:
                    self.controller.apply_stage(self.profiles[pid], QuarantineStage.NORMAL)
                except Exception:
                    pass
                del self.profiles[pid]
            return True

    def cycle(self) -> None:
        """Sample all profiles, evaluate anomaly scores, run restoration, and append history."""
        with self.lock:
            self.controller.heartbeat()
            now = time.time()
            target_pids = list(self.profiles.keys())
            if not target_pids:
                self_pid = os.getpid()
                target_pids = [self_pid]
                if self_pid not in self.profiles:
                    self.profiles[self_pid] = ProcessProfile(pid=self_pid, name="arq_daemon")

            snapshot = []
            for pid in target_pids:
                try:
                    m = self.monitor.sample_process(pid)
                except Exception:
                    m = None

                if m and pid in self.profiles:
                    prof = self.profiles[pid]
                    score = self.scorer.evaluate(prof, m)

                    # Shadow-only ML inference: never pass this score to
                    # RestorationEngine or QuarantineController.
                    ml_score = None
                    ml_anomaly = None
                    raw_anomaly = None
                    threshold = None
                    if self.ml_artifact is not None:
                        try:
                            features = extract_features(m)
                            model = self.ml_artifact["model"]
                            raw_anomaly = -float(
                                model.decision_function([features])[0]
                            )
                            if not math.isfinite(raw_anomaly):
                                raise ValueError('Non-finite model output')
                            threshold = float(
                                self.ml_artifact["calibration_threshold"]
                            )
                            if not math.isfinite(threshold):
                                raise ValueError('Non-finite model threshold')
                            temperature = max(abs(threshold), 1e-6)
                            x = max(-60.0, min(
                                60.0, (raw_anomaly - threshold) / temperature
                            ))
                            ml_score = 1.0 / (1.0 + math.exp(-x))
                            ml_anomaly = raw_anomaly > threshold
                        except Exception as exc:
                            self.ml_load_error = str(exc)
                            ml_score = ml_anomaly = raw_anomaly = threshold = None

                    identity = str(pid) + ':' + self.monitor._last_identity.get(pid, 'unknown')
                    decision_score, ml_reason = self.ml_policy.decide(identity, score, ml_anomaly)
                    previous_audit = self.controller.audit[-1] if self.controller.audit else None
                    stage, policy_reason = self.restoration.process_cycle(prof, decision_score)
                    latest_action = self.controller.audit[-1] if self.controller.audit else None
                    changed = latest_action is not previous_audit and latest_action and latest_action.get('pid') == pid
                    control_status = latest_action['status'] if changed else ('dry_run' if not self.controller.enforce else 'no_new_request')
                    action = control_status + '; ' + policy_reason
                    snapshot.append({
                        "pid": pid,
                        "telemetry_status": "ok",
                        "name": m.name or prof.name,
                        "cpu_pct": m.cpu_percent,
                        "mem_rss_mb": m.memory_rss_mb,
                        "io_kb_s": m.io_read_kb_s + m.io_write_kb_s,
                        "score": score,
                        "ml_score": ml_score,
                        "ml_raw_score": raw_anomaly,
                        "ml_threshold": threshold,
                        "ml_margin": raw_anomaly - threshold if raw_anomaly is not None and threshold is not None else None,
                        "ml_anomaly": ml_anomaly,
                        "ml_mode": self.ml_policy.mode,
                        "decision_score": decision_score,
                        "ml_reason": ml_reason,
                        "policy_stage": stage.name,
                        "policy_reason": policy_reason,
                        "control_status": control_status,
                        "managed": pid in self.controller.managed,
                        "stage": prof.stage.name,
                        "duty_cycle": prof.enforced_duty_cycle,
                        "action": action,
                    })

                elif pid in self.profiles:
                    self.controller.apply_stage(self.profiles[pid], QuarantineStage.WATCHLIST, reason='Telemetry unavailable; release restrictions without declaring recovery')
                    snapshot.append({'pid':pid, 'telemetry_status':'unavailable'})

            if snapshot:
                self.history.append({"time": round(now, 1), "processes": snapshot})
                if len(self.history) > 60:
                    self.history.pop(0)


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for ARQ static dashboard assets and JSON REST API."""

    state: Optional[ARQDashboardState] = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        super().__init__(*args, directory=static_dir, **kwargs)

    def handle(self) -> None:
        """Handle incoming requests and suppress broken pipe errors cleanly."""
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, format: str, *args: Any) -> None:
        """Wrap server logging in try/except to prevent console noise on disconnects."""
        try:
            super().log_message(format, *args)
        except Exception:
            pass

    def do_GET(self) -> None:
        """Handle GET requests: /api/status or static file serving."""
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()

            if self.state is None:
                payload = {"processes": [], "history": []}
            else:
                with self.state.lock:
                    latest_by_pid = {}
                    for entry in reversed(self.state.history):
                        for item in entry.get("processes", []):
                            latest_by_pid.setdefault(item.get("pid"), item)

                    procs = []
                    for pid, prof in self.state.profiles.items():
                        m = prof.recent_metrics[-1] if prof.recent_metrics else None
                        latest = latest_by_pid.get(pid, {})
                        procs.append({
                            "pid": pid,
                            "telemetry_status": latest.get("telemetry_status", "unavailable"),
                            "name": prof.name,
                            "cpu_pct": m.cpu_percent if m else 0.0,
                            "mem_mb": m.memory_rss_mb if m else 0.0,
                            "score": prof.current_score,
                            "ml_score": latest.get("ml_score"),
                            "ml_raw_score": latest.get("ml_raw_score"),
                            "ml_threshold": latest.get("ml_threshold"),
                            "ml_margin": latest.get("ml_margin"),
                            "policy_stage": latest.get("policy_stage"),
                            "policy_reason": latest.get("policy_reason"),
                            "control_status": latest.get("control_status", "not_sampled"),
                            "managed": pid in self.state.controller.managed,
                            "ml_anomaly": latest.get("ml_anomaly"),
                            "ml_mode": latest.get("ml_mode", "shadow"),
                            "stage": prof.stage.name,
                            "duty_cycle": prof.enforced_duty_cycle,
                            "reason": prof.quarantine_reason,
                        })
                    payload = {
                        "processes": procs,
                        "history": self.state.history[-20:],
                        "capabilities": self.state.monitor.capabilities(),
                        "enforcement_enabled": self.state.controller.enforce,
                        "ml_mode": self.state.ml_policy.mode,
                        "ml_model_loaded": self.state.ml_artifact is not None,
                        "ml_load_error": self.state.ml_load_error,
                        "actuator_errors": {pid:t.last_error for pid,t in self.state.controller._throttlers.items() if getattr(t,"last_error",None)},
                        "actuation_audit": list(self.state.controller.audit)[-20:],
                    }

            self.wfile.write(json.dumps(payload).encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self) -> None:
        """Handle POST actions for simulating, stopping, quarantining, and releasing processes."""
        parsed = urlparse(self.path)
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            self.send_error(403, 'Cross-origin control denied');return
        if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            self.send_error(415, 'JSON required');return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self.send_error(400, 'Invalid content length');return
        if length < 0 or length > 16384:
            self.send_error(413, 'Invalid body size');return
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except (ValueError, UnicodeError):
            self.send_error(400, 'Invalid JSON');return
        if not isinstance(data, dict):
            self.send_error(400, 'JSON object required');return
        if parsed.path in {'/api/stop','/api/quarantine','/api/release'} and (type(data.get('pid')) is not int or data['pid']<=1):
            self.send_error(400, 'Positive process ID required');return

        if self.state is None:
            self.send_response(503)
            self.end_headers()
            return

        if parsed.path == "/api/simulate":
            w_type = data.get("type", "cpu")
            pid = self.state.add_simulated(w_type)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": pid is not None, "pid": pid}).encode("utf-8"))

        elif parsed.path == "/api/stop":
            pid = int(data.get("pid", 0))
            stopped = self.state.stop_simulated(pid)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": stopped}).encode("utf-8"))

        elif parsed.path == "/api/quarantine":
            pid = int(data.get("pid", 0))
            outcome = 'denied_unknown_process'
            with self.state.lock:
                if pid in self.state.profiles:
                    prof = self.state.profiles[pid]
                    outcome = self.state.controller.apply_stage(
                        prof, QuarantineStage.SOFT_QUARANTINE, reason="Manual admin trigger"
                    )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": outcome == "requested", "actuation": outcome}).encode("utf-8"))

        elif parsed.path == "/api/release":
            pid = int(data.get("pid", 0))
            outcome = 'denied_unknown_process'
            with self.state.lock:
                if pid in self.state.profiles:
                    prof = self.state.profiles[pid]
                    outcome = self.state.controller.apply_stage(
                        prof, QuarantineStage.NORMAL, reason="Manual admin release"
                    )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": outcome == "requested", "actuation": outcome}).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()


def run_server(port: int = 8080, enforce=False, ml_mode='shadow', model_path=None, validation_path=None, allow_termination=False) -> None:
    """Start the ARQ dashboard web server with background telemetry cycles.

    Args:
        port: TCP port to listen on.
    """
    state = ARQDashboardState(enforce, ml_mode, model_path, validation_path, allow_termination)
    DashboardRequestHandler.state = state

    stopping = threading.Event()
    def background_loop() -> None:
        while not stopping.is_set():
            try:
                state.cycle()
            except Exception:
                pass
            stopping.wait(0.5)

    bg_thread = threading.Thread(target=background_loop, daemon=True)
    bg_thread.start()

    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardRequestHandler)
    print(f"Adaptive Resource Quarantine Dashboard live on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
    finally:
        stopping.set()
        bg_thread.join(timeout=2)
        server.server_close()
        state.controller.close()
        for handle in list(state.simulated_workloads.values()):
            handle.stop()


if __name__ == "__main__":
    run_server(8080)
