import csv
import json
from pathlib import Path
from statistics import mean


def summarize_results(results: list[dict]) -> dict:
    """Return aggregate statistics for load generator results."""
    status_code_distribution: dict[str, int] = {}
    backend_status_distribution: dict[str, int] = {}
    final_backend_status_distribution: dict[str, int] = {}
    latencies = []
    end_to_end_latencies = []
    latency_by_model_values: dict[str, list[float]] = {}
    latency_by_backend_values: dict[str, list[float]] = {}
    end_to_end_by_model_values: dict[str, list[float]] = {}
    end_to_end_by_backend_values: dict[str, list[float]] = {}
    requests_by_model: dict[str, int] = {}
    requests_by_backend: dict[str, int] = {}
    final_status_by_model: dict[str, dict[str, int]] = {}
    final_status_by_backend: dict[str, dict[str, int]] = {}

    for result in results:
        status_code = str(result.get("http_status", "error"))
        backend_status = str(result.get("backend_status") or "unknown")
        final_backend_status = str(result.get("final_backend_status") or "unknown")
        model = str(result.get("model") or "unknown")
        backend_name = str(result.get("backend_name") or _infer_backend_name(model))
        status_code_distribution[status_code] = status_code_distribution.get(status_code, 0) + 1
        backend_status_distribution[backend_status] = (
            backend_status_distribution.get(backend_status, 0) + 1
        )
        final_backend_status_distribution[final_backend_status] = (
            final_backend_status_distribution.get(final_backend_status, 0) + 1
        )
        requests_by_model[model] = requests_by_model.get(model, 0) + 1
        requests_by_backend[backend_name] = requests_by_backend.get(backend_name, 0) + 1
        _increment_nested(final_status_by_model, model, final_backend_status)
        _increment_nested(final_status_by_backend, backend_name, final_backend_status)

        latency = result.get("latency_seconds")
        if latency is not None:
            latency_value = float(latency)
            latencies.append(latency_value)
            latency_by_model_values.setdefault(model, []).append(latency_value)
            latency_by_backend_values.setdefault(backend_name, []).append(latency_value)
        end_to_end_latency = result.get("end_to_end_latency_seconds")
        if end_to_end_latency is not None:
            end_to_end_value = float(end_to_end_latency)
            end_to_end_latencies.append(end_to_end_value)
            end_to_end_by_model_values.setdefault(model, []).append(end_to_end_value)
            end_to_end_by_backend_values.setdefault(backend_name, []).append(end_to_end_value)

    successful_http_requests = sum(
        1 for result in results if 200 <= int(result.get("http_status", 0) or 0) < 300
    )
    failed_http_requests = len(results) - successful_http_requests

    return {
        "total_requests": len(results),
        "successful_http_requests": successful_http_requests,
        "failed_http_requests": failed_http_requests,
        "accepted_or_completed": _count_backend_status(results, {"accepted", "completed"}),
        "queued": _count_backend_status(results, {"queued"}),
        "rejected": failed_http_requests,
        "completed_final": _count_final_backend_status(results, {"completed"}),
        "failed_final": _count_final_backend_status(results, {"failed"}),
        "timed_out_final": _count_final_backend_status(results, {"timed_out"}),
        "queued_initial": _count_backend_status(results, {"queued"}),
        "completed_immediate": sum(
            1
            for result in results
            if result.get("backend_status") == "completed"
            and result.get("final_backend_status") == "completed"
        ),
        "average_latency_seconds": mean(latencies) if latencies else None,
        "p50_latency_seconds": _percentile(latencies, 50),
        "p95_latency_seconds": _percentile(latencies, 95),
        "p99_latency_seconds": _percentile(latencies, 99),
        "average_end_to_end_latency_seconds": (
            mean(end_to_end_latencies) if end_to_end_latencies else None
        ),
        "p50_end_to_end_latency_seconds": _percentile(end_to_end_latencies, 50),
        "p95_end_to_end_latency_seconds": _percentile(end_to_end_latencies, 95),
        "p99_end_to_end_latency_seconds": _percentile(end_to_end_latencies, 99),
        "status_code_distribution": status_code_distribution,
        "backend_status_distribution": backend_status_distribution,
        "final_backend_status_distribution": final_backend_status_distribution,
        "requests_by_model": requests_by_model,
        "requests_by_backend": requests_by_backend,
        "latency_by_model": _summarize_groups(latency_by_model_values),
        "latency_by_backend": _summarize_groups(latency_by_backend_values),
        "end_to_end_latency_by_model": _summarize_groups(end_to_end_by_model_values),
        "end_to_end_latency_by_backend": _summarize_groups(end_to_end_by_backend_values),
        "final_status_by_model": final_status_by_model,
        "final_status_by_backend": final_status_by_backend,
    }


def write_csv(results: list[dict], output_path: str) -> None:
    """Write per-request results to CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "request_index",
        "user_id",
        "project_id",
        "model",
        "backend_name",
        "request_type",
        "http_status",
        "backend_status",
        "request_id",
        "latency_seconds",
        "final_backend_status",
        "final_latency_seconds",
        "end_to_end_latency_seconds",
        "polling_attempts",
        "polling_error",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: result.get(field) for field in fieldnames} for result in results)


def write_json(summary: dict, output_path: str) -> None:
    """Write summary data to JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)


def write_comparison_markdown(summary: dict, output_path: str) -> None:
    """Write a human-readable backend/model comparison report."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# LLM Throughput Comparison Report",
        "",
        f"- Total requests: {summary.get('total_requests', 0)}",
        "",
        "## Status Distribution",
        _format_mapping(summary.get("status_code_distribution", {})),
        "",
        "## Final Status Distribution",
        _format_mapping(summary.get("final_backend_status_distribution", {})),
        "",
        "## Requests By Backend",
        _format_mapping(summary.get("requests_by_backend", {})),
        "",
        "## Requests By Model",
        _format_mapping(summary.get("requests_by_model", {})),
        "",
        "## Latency By Backend",
        _format_latency_table(summary.get("latency_by_backend", {})),
        "",
        "## Latency By Model",
        _format_latency_table(summary.get("latency_by_model", {})),
        "",
        "## End-To-End Latency By Backend",
        _format_latency_table(summary.get("end_to_end_latency_by_backend", {})),
        "",
        "## End-To-End Latency By Model",
        _format_latency_table(summary.get("end_to_end_latency_by_model", {})),
        "",
        "## Notes",
        "- Ollama results depend on local hardware, available RAM/VRAM, model size, and Ollama configuration.",
        "- Simulated backend results are artificial and intended for architecture validation.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _count_backend_status(results: list[dict], statuses: set[str]) -> int:
    return sum(1 for result in results if result.get("backend_status") in statuses)


def _count_final_backend_status(results: list[dict], statuses: set[str]) -> int:
    return sum(1 for result in results if result.get("final_backend_status") in statuses)


def _summarize_groups(groups: dict[str, list[float]]) -> dict[str, dict[str, float | int | None]]:
    return {name: _latency_summary(values) for name, values in groups.items()}


def _latency_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "average": None, "p50": None, "p95": None, "p99": None}

    return {
        "count": len(values),
        "average": mean(values),
        "p50": _percentile(values, 50),
        "p95": _percentile(values, 95),
        "p99": _percentile(values, 99),
    }


def _increment_nested(values: dict[str, dict[str, int]], first_key: str, second_key: str) -> None:
    values.setdefault(first_key, {})
    values[first_key][second_key] = values[first_key].get(second_key, 0) + 1


def _infer_backend_name(model: str) -> str:
    if model.startswith("simulated"):
        return "simulated"
    if model.startswith("ollama"):
        return "ollama"
    return "unknown"


def _format_mapping(values: dict) -> str:
    if not values:
        return "- none"
    return "\n".join(f"- {key}: {value}" for key, value in values.items())


def _format_latency_table(values: dict) -> str:
    if not values:
        return "- none"

    lines = ["| Name | Count | Average | P50 | P95 | P99 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, stats in values.items():
        lines.append(
            f"| {name} | {stats.get('count')} | {stats.get('average')} | "
            f"{stats.get('p50')} | {stats.get('p95')} | {stats.get('p99')} |"
        )
    return "\n".join(lines)


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None

    sorted_values = sorted(values)
    index = round((len(sorted_values) - 1) * percentile / 100)
    return sorted_values[index]
