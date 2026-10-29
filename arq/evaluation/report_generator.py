"""
Benchmark report generator and table formatter.
Produces formatted ASCII tables and Markdown reports.
"""

from typing import List

from arq.evaluation.metrics import BenchmarkResult


class ReportGenerator:
    """Formatter for benchmark comparison results."""

    @staticmethod
    def format_ascii_table(results: List[BenchmarkResult]) -> str:
        """Generate a formatted ASCII table comparing isolation strategies."""
        headers = ["Strategy", "P95 Latency", "P99 Latency", "Throughput", "State Loss", "Process Status"]
        col_w = [30, 14, 14, 14, 12, 16]

        sep = "+" + "+".join(["-" * (w + 2) for w in col_w]) + "+"
        header_row = "| " + " | ".join([h.ljust(col_w[i]) for i, h in enumerate(headers)]) + " |"

        lines = [sep, header_row, sep]
        for r in results:
            p_status = "Alive at end" if r.target_process_completed else "Exited"
            loss_str = "Not measured" if r.state_loss_rate_pct is None else f"{r.state_loss_rate_pct:.0f}%"
            row = [
                r.strategy_name.ljust(col_w[0]),
                f"{r.p95_latency_ms:.2f} ms".ljust(col_w[1]),
                f"{r.p99_latency_ms:.2f} ms".ljust(col_w[2]),
                f"{r.throughput_rps:.1f} rps".ljust(col_w[3]),
                loss_str.ljust(col_w[4]),
                p_status.ljust(col_w[5]),
            ]
            lines.append("| " + " | ".join(row) + " |")
        lines.append(sep)
        return "\n".join(lines)

    @staticmethod
    def format_markdown(results: List[BenchmarkResult]) -> str:
        """Generate a GitHub Flavored Markdown table summarizing benchmark results."""
        lines = [
            "### Experimental Evaluation Results",
            "",
            "| Strategy | Median Latency (ms) | P95 Latency (ms) | P99 Latency (ms) | Throughput (req/s) | State Loss (%) | Process Status |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        for r in results:
            p_status = "Alive at end" if r.target_process_completed else "Exited"
            loss_str = "Not measured" if r.state_loss_rate_pct is None else f"{r.state_loss_rate_pct:.0f}%"
            lines.append(
                f"| **{r.strategy_name}** | {r.median_latency_ms:.2f} | {r.p95_latency_ms:.2f} | "
                f"{r.p99_latency_ms:.2f} | {r.throughput_rps:.1f} | {loss_str} | {p_status} |"
            )
        lines.append("")
        lines.append(
            "> Local trial results only. Application state loss and recovery time were not measured."
        )
        return "\n".join(lines)
