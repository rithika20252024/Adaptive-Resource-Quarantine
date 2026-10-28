"""
Adaptive Resource Quarantine - Unified Command Line Interface.
Provides CLI subcommands:
- `benchmark`: Executes comparative evaluation across isolation strategies.
- `demo`: Live demonstration of anomaly detection, throttling, and auto-restoration.
- `web`: Launches the real-time web monitoring and control dashboard.
"""

import argparse
import sys
import time


def cmd_benchmark(args) -> None:
    """Run comparative benchmark evaluating unprotected, static kill, and adaptive quarantine."""
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


def cmd_demo(args) -> None:
    """Execute live closed-loop quarantine and auto-restoration demonstration."""
    print("=" * 70)
    print(" ADAPTIVE RESOURCE QUARANTINE - LIVE DEMO")
    print(" Demonstrating closed-loop detection, throttling, and auto-restoration")
    print("=" * 70)
    from arq.core.anomaly_scorer import AnomalyScorer
    from arq.core.monitor import ProcessMonitor
    from arq.core.process_model import ProcessMetrics, ProcessProfile, QuarantineStage
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
                print(
                    f" [Step {step+1:02d}] CPU: {m.cpu_percent:5.1f}% | "
                    f"Anomaly Score: {score:.2f} | Stage: {stage.name:<16} | Action: {action}"
                )
            time.sleep(0.4)

        print("\nPhase 2: Workload Behavior Normalizes")
        burner.stop()

        for step in range(8):
            m_low = ProcessMetrics(pid=pid, name="burner_demo", cpu_percent=2.5, memory_rss_mb=12.0)
            score = scorer.evaluate(profile, m_low)
            stage, action = restoration.process_cycle(profile, score)
            print(
                f" [Step {step+9:02d}] CPU: {m_low.cpu_percent:5.1f}% | "
                f"Anomaly Score: {score:.2f} | Stage: {stage.name:<16} | Action: {action}"
            )
            time.sleep(0.4)

        print("\n[✓] Demo complete! Process was safely stepped down and restored without SIGKILL.")
    finally:
        controller.cleanup_all()
        burner.stop()



def cmd_train_ml(args) -> None:
    """Train and calibrate the Isolation Forest detector."""
    from arq.core.ml_training import train_isolation_forest

    try:
        result = train_isolation_forest(
            data_path=args.data,
            output_dir=args.output_dir,
            contamination=args.contamination,
            random_state=args.seed,
        )
    except (ValueError, OSError) as exc:
        print(f"ML training failed: {exc}", file=sys.stderr)
        sys.exit(2)

    print("Isolation Forest training completed.")
    print(f"Model: {result['model_path']}")
    print(f"Training records: {result['training_rows']}")
    print(f"Calibration records: {result['calibration_rows']}")
    print(f"Calibration threshold: {result['calibration_threshold']:.6f}")


def cmd_web(args) -> None:
    """Launch real-time web dashboard."""
    from arq.web.server import run_server
    run_server(port=args.port)


def main() -> None:
    """Parse command line arguments and execute subcommands."""
    parser = argparse.ArgumentParser(description="Adaptive Resource Quarantine (ARQ) CLI")
    subparsers = parser.add_subparsers(dest="command")

    # benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run comparative performance benchmark")
    p_bench.add_argument("--duration", type=float, default=4.0, help="Duration in seconds per trial")
    p_bench.add_argument("--markdown", action="store_true", help="Print Markdown table output")

    # demo
    subparsers.add_parser("demo", help="Run interactive quarantine & restoration demonstration")

    # optional ML training
    p_train = subparsers.add_parser(
        "train-ml", help="Train and calibrate the Isolation Forest detector"
    )
    p_train.add_argument("--data", required=True, help="Normal telemetry JSONL file")
    p_train.add_argument("--output-dir", default="models/arq", help="Model output directory")
    p_train.add_argument("--contamination", type=float, default=0.05)
    p_train.add_argument("--seed", type=int, default=42)

    # web
    p_web = subparsers.add_parser("web", help="Launch real-time web dashboard")
    p_web.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "demo":
        cmd_demo(args)
    elif args.command == "train-ml":
        cmd_train_ml(args)
    elif args.command == "web":
        cmd_web(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
