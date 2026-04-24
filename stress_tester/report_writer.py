import csv
import json
from pathlib import Path
from statistics import mean


def summarize_results(results: list[dict]) -> dict:
    """Return aggregate statistics for load generator results."""
    status_code_distribution: dict[str, int] = {}
    backend_status_distribution: dict[str, int] = {}
    latencies = []

    for result in results:
        status_code = str(result.get("http_status", "error"))
        backend_status = str(result.get("backend_status") or "unknown")
        status_code_distribution[status_code] = status_code_distribution.get(status_code, 0) + 1
        backend_status_distribution[backend_status] = (
            backend_status_distribution.get(backend_status, 0) + 1
        )

        latency = result.get("latency_seconds")
        if latency is not None:
            latencies.append(float(latency))

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
        "average_latency_seconds": mean(latencies) if latencies else None,
        "p50_latency_seconds": _percentile(latencies, 50),
        "p95_latency_seconds": _percentile(latencies, 95),
        "p99_latency_seconds": _percentile(latencies, 99),
        "status_code_distribution": status_code_distribution,
        "backend_status_distribution": backend_status_distribution,
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
        "request_type",
        "http_status",
        "backend_status",
        "request_id",
        "latency_seconds",
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


def _count_backend_status(results: list[dict], statuses: set[str]) -> int:
    return sum(1 for result in results if result.get("backend_status") in statuses)


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None

    sorted_values = sorted(values)
    index = round((len(sorted_values) - 1) * percentile / 100)
    return sorted_values[index]
