"""Write quality evaluation reports: CSV, JSON, and Markdown."""

from __future__ import annotations

import csv
import json
import os
import statistics
from datetime import datetime, timezone


_CSV_FIELDS = [
    "task_id",
    "model",
    "passed",
    "http_status",
    "simulator_status",
    "latency_seconds",
    "end_to_end_latency_seconds",
    "estimated_input_tokens",
    "estimated_output_tokens",
    "estimated_cost_eur",
    "error_type",
    "error_message",
]


def summarize_results(results: list[dict]) -> dict:
    """Aggregate per-problem results into quality summary statistics."""
    total = len(results)
    if total == 0:
        return {}

    passed_results = [r for r in results if r.get("passed")]
    failed_results = [r for r in results if not r.get("passed")]

    latencies = [r["latency_seconds"] for r in results if r.get("latency_seconds") is not None]
    e2e_latencies = [
        r["end_to_end_latency_seconds"]
        for r in results
        if r.get("end_to_end_latency_seconds") is not None
    ]

    total_cost = sum(r.get("estimated_cost_eur") or 0.0 for r in results)
    passed_count = len(passed_results)
    cost_per_passed = (total_cost / passed_count) if passed_count > 0 else None

    error_breakdown: dict[str, int] = {}
    for r in failed_results:
        et = r.get("error_type") or "unknown"
        error_breakdown[et] = error_breakdown.get(et, 0) + 1

    model = results[0].get("model", "unknown") if results else "unknown"

    summary = {
        "model": model,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_problems": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "pass_at_1": round(passed_count / total, 4) if total > 0 else 0.0,
        "avg_latency_seconds": _safe_mean(latencies),
        "p50_latency_seconds": _safe_percentile(latencies, 50),
        "p95_latency_seconds": _safe_percentile(latencies, 95),
        "avg_end_to_end_latency_seconds": _safe_mean(e2e_latencies),
        "p95_end_to_end_latency_seconds": _safe_percentile(e2e_latencies, 95),
        "total_cost_eur": round(total_cost, 6),
        "cost_per_passed_problem_eur": round(cost_per_passed, 6) if cost_per_passed is not None else None,
        "error_breakdown": error_breakdown,
        "simulator_rejected": sum(1 for r in results if r.get("error_type") == "simulator_rejected"),
    }
    return summary


def write_csv(results: list[dict], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)


def write_json(summary: dict, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def write_markdown(summary: dict, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    model = summary.get("model", "unknown")
    total = summary.get("total_problems", 0)
    passed = summary.get("passed", 0)
    pass_at_1 = summary.get("pass_at_1", 0.0)
    ts = summary.get("run_timestamp", "")

    lines = [
        f"# HumanEval Quality Report — {model}",
        "",
        f"Run: {ts}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Problems evaluated | {total} |",
        f"| Passed (pass@1) | {passed} / {total} ({pass_at_1:.1%}) |",
        f"| Failed | {summary.get('failed', 0)} |",
        f"| Avg latency (s) | {_fmt(summary.get('avg_latency_seconds'))} |",
        f"| P50 latency (s) | {_fmt(summary.get('p50_latency_seconds'))} |",
        f"| P95 latency (s) | {_fmt(summary.get('p95_latency_seconds'))} |",
        f"| Avg E2E latency (s) | {_fmt(summary.get('avg_end_to_end_latency_seconds'))} |",
        f"| P95 E2E latency (s) | {_fmt(summary.get('p95_end_to_end_latency_seconds'))} |",
        f"| Total cost (EUR) | {summary.get('total_cost_eur', 0.0):.6f} |",
        f"| Cost per passed problem (EUR) | {_fmt(summary.get('cost_per_passed_problem_eur'))} |",
        "",
        "## Error Breakdown",
        "",
    ]

    error_breakdown = summary.get("error_breakdown", {})
    if error_breakdown:
        lines += [f"| Error type | Count |", f"|---|---|"]
        for error_type, count in sorted(error_breakdown.items()):
            lines.append(f"| {error_type} | {count} |")
    else:
        lines.append("No errors.")

    lines += [
        "",
        "## Notes",
        "",
        "- pass@1: fraction of problems solved correctly on the first attempt.",
        "- Latency measures simulator round-trip time, not model inference time exclusively.",
        "- Cost is estimated from token counts using model config pricing.",
        "- simulator_rejected: requests that the simulator refused due to rate limits, quota, or capacity.",
    ]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_comparison_markdown(summaries: list[dict], output_path: str) -> None:
    """Write a multi-model comparison table when multiple models were evaluated."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    lines = [
        "# HumanEval Quality Comparison",
        "",
        f"Run: {ts}",
        "",
        "## pass@1 and Latency by Model",
        "",
        "| Model | Problems | pass@1 | Avg latency (s) | P95 latency (s) | Cost/passed (EUR) |",
        "|---|---|---|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| {s.get('model')} "
            f"| {s.get('total_problems')} "
            f"| {s.get('pass_at_1', 0):.1%} "
            f"| {_fmt(s.get('avg_latency_seconds'))} "
            f"| {_fmt(s.get('p95_latency_seconds'))} "
            f"| {_fmt(s.get('cost_per_passed_problem_eur'))} |"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(statistics.mean(values), 4)


def _safe_percentile(values: list[float], p: int) -> float | None:
    if not values:
        return None
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * p / 100)
    idx = min(idx, len(sorted_vals) - 1)
    return round(sorted_vals[idx], 4)


def _fmt(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f}"
