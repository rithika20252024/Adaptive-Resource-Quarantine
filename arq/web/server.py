"""
Lightweight Web Dashboard Server.
Pure Python standard library HTTP server providing real-time telemetry,
interactive quarantine control, and visualization without external dependencies.
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import json
import os
import signal
import sys
import threading
import time
from urllib.parse import urlparse, parse_qs
from arq.core.process_model import ProcessProfile, QuarantineStage
from arq.core.monitor import ProcessMonitor
from arq.core.anomaly_scorer import AnomalyScorer
from arq.core.quarantine_controller import QuarantineController
from arq.core.restoration_engine import RestorationEngine
from arq.simulation.workloads import WorkloadSimulator

class ARQDashboardState:
    def __init__(self):
        self.monitor = ProcessMonitor()
        self.scorer = AnomalyScorer()
        self.controller = QuarantineController()
        self.restoration = RestorationEngine(self.controller)
        self.profiles = {}
        self.simulated_workloads = {}
        self.lock = threading.Lock()
        self.history = []

    def add_simulated(self, w_type: str):
        with self.lock:
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

    def stop_simulated(self, pid: int):
        with self.lock:
            if pid in self.simulated_workloads:
                self.simulated_workloads[pid].stop()
                del self.simulated_workloads[pid]
            if pid in self.profiles:
                self.controller.apply_stage(self.profiles[pid], QuarantineStage.NORMAL)
                del self.profiles[pid]

    def cycle(self):
        with self.lock:
            now = time.time()
            # If no simulated, track current python process or self
            target_pids = list(self.profiles.keys())
            if not target_pids:
                target_pids = [os.getpid()]
                if os.getpid() not in self.profiles:
                    self.profiles[os.getpid()] = ProcessProfile(pid=os.getpid(), name="arq_daemon")

            snapshot = []
            for pid in target_pids:
                m = self.monitor.sample_process(pid)
                if m and pid in self.profiles:
                    prof = self.profiles[pid]
                    score = self.scorer.evaluate(prof, m)
                    stage, action = self.restoration.process_cycle(prof, score)
                    snapshot.append({
                        "pid": pid,
                        "name": m.name,
                        "cpu_pct": m.cpu_percent,
                        "mem_rss_mb": m.memory_rss_mb,
                        "io_kb_s": m.io_read_kb_s + m.io_write_kb_s,
                        "score": score,
                        "stage": prof.stage.name,
                        "duty_cycle": prof.enforced_duty_cycle,
                        "action": action
                    })
            if snapshot:
                self.history.append({"time": round(now, 1), "processes": snapshot})
                if len(self.history) > 60:
                    self.history.pop(0)

class DashboardRequestHandler(SimpleHTTPRequestHandler):
    state: ARQDashboardState = None

    def __init__(self, *args, **kwargs):
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        super().__init__(*args, directory=static_dir, **kwargs)

    def handle(self):
        """Override to silently handle broken pipe / connection reset errors."""
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # Client disconnected early — totally normal for browsers

    def log_message(self, format, *args):
        """Suppress noisy log output for broken connections."""
        # Only log if the response was actually sent successfully
        try:
            super().log_message(format, *args)
        except Exception:
            pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
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
                        "reason": prof.quarantine_reason
                    })
                payload = {
                    "processes": procs,
                    "history": self.state.history[-20:]
                }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

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
                    self.state.controller.apply_stage(prof, QuarantineStage.SOFT_QUARANTINE, reason="Manual admin trigger")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))

        elif parsed.path == "/api/release":
            pid = int(data.get("pid", 0))
            with self.state.lock:
                if pid in self.state.profiles:
                    prof = self.state.profiles[pid]
                    self.state.controller.apply_stage(prof, QuarantineStage.NORMAL, reason="Manual admin release")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a new thread to avoid blocking on slow clients."""
    daemon_threads = True

def run_server(port: int = 8080):
    state = ARQDashboardState()
    DashboardRequestHandler.state = state

    # Background telemetry loop
    def background_loop():
        while True:
            state.cycle()
            time.sleep(0.5)

    t = threading.Thread(target=background_loop, daemon=True)
    t.start()

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
