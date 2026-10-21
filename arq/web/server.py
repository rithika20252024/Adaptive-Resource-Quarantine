"""Web dashboard server using Python standard library only.

Provides real-time telemetry streaming, interactive quarantine actuators,
and anomaly monitoring over HTTP.
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os
from socketserver import ThreadingMixIn
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from arq.core.anomaly_scorer import AnomalyScorer
from arq.core.monitor import ProcessMonitor
from arq.core.process_model import ProcessProfile, QuarantineStage
from arq.core.quarantine_controller import QuarantineController
from arq.core.restoration_engine import RestorationEngine


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server using daemon threads to prevent hang on shutdown."""

    daemon_threads = True


class ARQDashboardState:
    """State manager for telemetry monitoring, process profiles, and simulated workloads."""

    def __init__(self) -> None:
        self.monitor = ProcessMonitor()
        self.scorer = AnomalyScorer()
        self.controller = QuarantineController()
        self.restoration = RestorationEngine(self.controller)
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
            try:
                from arq.simulation.workloads import WorkloadSimulator
            except ImportError:
                return None

            if w_type == "cpu":
                h = WorkloadSimulator.start_cpu_burner()
            elif w_type == "mem":
                h = WorkloadSimulator.start_memory_leaker()
            elif w_type == "burst":
                h = WorkloadSimulator.start_transient_burst()
            else:
                return None

            self.simulated_workloads[h.pid] = h
            self.profiles[h.pid] = ProcessProfile(pid=h.pid, name=h.name)
            return h.pid

    def stop_simulated(self, pid: int) -> bool:
        """Stop a simulated workload and cleanup its profile.

        Args:
            pid: Process ID to terminate and release.
        """
        with self.lock:
            if pid in self.simulated_workloads:
                try:
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
                    stage, action = self.restoration.process_cycle(prof, score)
                    snapshot.append({
                        "pid": pid,
                        "name": m.name or prof.name,
                        "cpu_pct": m.cpu_percent,
                        "mem_rss_mb": m.memory_rss_mb,
                        "io_kb_s": m.io_read_kb_s + m.io_write_kb_s,
                        "score": score,
                        "stage": prof.stage.name,
                        "duty_cycle": prof.enforced_duty_cycle,
                        "action": action,
                    })

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
                    procs = []
                    for pid, prof in self.state.profiles.items():
                        m = prof.recent_metrics[-1] if prof.recent_metrics else None
                        procs.append({
                            "pid": pid,
                            "name": prof.name,
                            "cpu_pct": m.cpu_percent if m else 0.0,
                            "mem_mb": m.memory_rss_mb if m else 0.0,
                            "score": prof.current_score,
                            "stage": prof.stage.name,
                            "duty_cycle": prof.enforced_duty_cycle,
                            "reason": prof.quarantine_reason,
                        })
                    payload = {
                        "processes": procs,
                        "history": self.state.history[-20:],
                    }

            self.wfile.write(json.dumps(payload).encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self) -> None:
        """Handle POST actions for simulating, stopping, quarantining, and releasing processes."""
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

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
            self.wfile.write(json.dumps({"success": True, "pid": pid}).encode("utf-8"))

        elif parsed.path == "/api/stop":
            pid = int(data.get("pid", 0))
            self.state.stop_simulated(pid)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))

        elif parsed.path == "/api/quarantine":
            pid = int(data.get("pid", 0))
            with self.state.lock:
                if pid in self.state.profiles:
                    prof = self.state.profiles[pid]
                    self.state.controller.apply_stage(
                        prof, QuarantineStage.SOFT_QUARANTINE, reason="Manual admin trigger"
                    )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))

        elif parsed.path == "/api/release":
            pid = int(data.get("pid", 0))
            with self.state.lock:
                if pid in self.state.profiles:
                    prof = self.state.profiles[pid]
                    self.state.controller.apply_stage(
                        prof, QuarantineStage.NORMAL, reason="Manual admin release"
                    )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()


def run_server(port: int = 8080) -> None:
    """Start the ARQ dashboard web server with background telemetry cycles.

    Args:
        port: TCP port to listen on.
    """
    state = ARQDashboardState()
    DashboardRequestHandler.state = state

    def background_loop() -> None:
        while True:
            try:
                state.cycle()
            except Exception:
                pass
            time.sleep(0.5)

    bg_thread = threading.Thread(target=background_loop, daemon=True)
    bg_thread.start()

    server = ThreadingHTTPServer(("0.0.0.0", port), DashboardRequestHandler)
    print(f"Adaptive Resource Quarantine Dashboard live on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
        server.server_close()
        state.controller.cleanup_all()


if __name__ == "__main__":
    run_server(8080)
