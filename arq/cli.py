"""
Adaptive Resource Quarantine - Unified Command Line Interface.
Provides CLI subcommands:
- `benchmark`: Executes comparative evaluation across isolation strategies.
- `demo`: Live interactive demonstration of anomaly detection and adaptive quarantine.
- `monitor`: Continuous terminal telemetry monitor.
- `web`: Launches real-time web dashboard.

"""

import argparse
import os
import sys
import time

def cmd_pptx(args):
    from presentation.generate_review1_pptx import build_presentation
    out_path = args.output or os.path.join(os.path.dirname(__file__), "..", "presentation", "Adaptive_Resource_Quarantine_Review_1.pptx")
    out_path = os.path.abspath(out_path)
    build_presentation(out_path)

def cmd_benchmark(args):
    print("=" * 70)
    print(" ADAPTIVE RESOURCE QUARANTINE - COMPARATIVE BENCHMARK")
    print(" Evaluating: Unprotected vs Static Kill vs Adaptive Quarantine")
    print("=" * 70)
    from arq.evaluation.benchmark_runner import BenchmarkRunner
    from arq.evaluation.report_generator import ReportGenerator

    runner = BenchmarkRunner(trial_duration_s=args.duration)
    print("\n[1/3] Running Unprotected Baseline trial...")
    r1 = runner.run_unprotected()
    print(f"      Done: P95={r1.p95_latency_ms:.2f}ms, P99={r1.p99_latency_ms:.2f}ms")

    print("\n[2/3] Running Static Kill (CFS/OOM) trial...")
    r2 = runner.run_static_kill()
    print(f"      Done: P95={r2.p95_latency_ms:.2f}ms, State Loss={r2.state_loss_rate_pct:.0f}%")

    print("\n[3/3] Running Adaptive Resource Quarantine trial...")
    r3 = runner.run_adaptive_quarantine()
    print(f"      Done: P95={r3.p95_latency_ms:.2f}ms, State Loss={r3.state_loss_rate_pct:.0f}%")

    results = [r1, r2, r3]
    print("\n" + ReportGenerator.format_ascii_table(results) + "\n")
    if args.markdown:
        md = ReportGenerator.format_markdown(results)
        print(md)

def cmd_demo(args):
    print("=" * 70)
    print(" ADAPTIVE RESOURCE QUARANTINE - LIVE DEMO")
    print(" Demonstrating closed-loop detection, throttling, and auto-restoration")
    print("=" * 70)
    from arq.core.process_model import ProcessProfile, QuarantineStage
    from arq.core.monitor import ProcessMonitor
    from arq.core.anomaly_scorer import AnomalyScorer
    from arq.core.quarantine_controller import QuarantineController
    from arq.core.restoration_engine import RestorationEngine
    from arq.simulation.workloads import WorkloadSimulator

    print("[*] Spawning test CPU burner process...")
    burner = WorkloadSimulator.start_cpu_burner()
    pid = burner.pid
    print(f"[*] Target PID: {pid}")

    monitor = ProcessMonitor([pid])
    scorer = AnomalyScorer(cpu_threshold=60.0, burst_tolerance_cycles=1)
    controller = QuarantineController(soft_threshold=0.55, hard_threshold=0.75)
    restoration = RestorationEngine(controller, hysteresis_cycles=2, persistence_timeout_s=10.0)
    profile = ProcessProfile(pid=pid, name="burner_demo")

    try:
        print("\nPhase 1: Detecting Rogue Anomaly & Applying Quarantine")
        for step in range(8):
            m = monitor.sample_process(pid)
            if m:
                score = scorer.evaluate(profile, m)
                stage, action = restoration.process_cycle(profile, score)
                print(f" [Step {step+1:02d}] CPU: {m.cpu_percent:5.1f}% | Anomaly Score: {score:.2f} | Stage: {stage.name:<16} | Action: {action}")
            time.sleep(0.4)

        print("\nPhase 2: Workload Behavior Normalizes (Simulating process settling)")
        # Stop burner
        burner.stop()

        # Monitor settling down
        for step in range(8):
            # Simulated low activity metrics for de-quarantine demo
            from arq.core.process_model import ProcessMetrics
            m_low = ProcessMetrics(pid=pid, name="burner_demo", cpu_percent=2.5, memory_rss_mb=12.0)
            score = scorer.evaluate(profile, m_low)
            stage, action = restoration.process_cycle(profile, score)
            print(f" [Step {step+9:02d}] CPU: {m_low.cpu_percent:5.1f}% | Anomaly Score: {score:.2f} | Stage: {stage.name:<16} | Action: {action}")
            time.sleep(0.4)

        print("\n[✓] Demo complete! Notice how the process was safely stepped down and restored without SIGKILL.")
    finally:
        controller.cleanup_all()
        burner.stop()

def cmd_web(args):
    from arq.web.server import run_server
    run_server(port=args.port)

def main():
    parser = argparse.ArgumentParser(description="Adaptive Resource Quarantine (ARQ) CLI")
    subparsers = parser.add_subparsers(dest="command")

    # benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run comparative performance benchmark")
    p_bench.add_argument("--duration", type=float, default=4.0, help="Duration in seconds per trial")
    p_bench.add_argument("--markdown", action="store_true", help="Print Markdown table output")

    # demo
    p_demo = subparsers.add_parser("demo", help="Run interactive quarantine & restoration demonstration")

    # web
    p_web = subparsers.add_parser("web", help="Launch real-time web dashboard")
    p_web.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")

    # pptx
    p_pptx = subparsers.add_parser("pptx", help="Generate Review 1 PowerPoint presentation")
    p_pptx.add_argument("--output", type=str, default="", help="Custom output path for .pptx")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "demo":
        cmd_demo(args)
    elif args.command == "web":
        cmd_web(args)
    elif args.command == "pptx":
        cmd_pptx(args)

if __name__ == "__main__":
    main()
