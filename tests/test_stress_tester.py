import json

from stress_tester.report_writer import (
    summarize_results,
    write_comparison_markdown,
    write_csv,
    write_json,
)
from stress_tester.scenarios import SCENARIOS


def test_scenario_registry_contains_normal_load() -> None:
    assert "normal_load" in SCENARIOS


def test_scenario_registry_contains_ollama_normal_load() -> None:
    assert "ollama_normal_load" in SCENARIOS


def test_scenario_registry_contains_ollama_burst_load() -> None:
    assert "ollama_burst_load" in SCENARIOS


def test_summarize_results_handles_empty_list() -> None:
    summary = summarize_results([])

    assert summary["total_requests"] == 0
    assert summary["successful_http_requests"] == 0
    assert summary["failed_http_requests"] == 0
    assert summary["average_latency_seconds"] is None


def test_summarize_results_calculates_status_code_distribution() -> None:
    summary = summarize_results(
        [
            {"http_status": 200, "backend_status": "completed", "latency_seconds": 0.1},
            {"http_status": 200, "backend_status": "queued", "latency_seconds": 0.2},
            {"http_status": 429, "backend_status": None, "latency_seconds": 0.3},
        ]
    )

    assert summary["status_code_distribution"] == {"200": 2, "429": 1}
    assert summary["backend_status_distribution"]["completed"] == 1
    assert summary["backend_status_distribution"]["queued"] == 1
    assert summary["successful_http_requests"] == 2
    assert summary["failed_http_requests"] == 1


def test_summarize_results_includes_requests_by_model() -> None:
    summary = summarize_results(
        [
            {
                "http_status": 200,
                "model": "simulated-small",
                "backend_name": "simulated",
                "backend_status": "completed",
                "final_backend_status": "completed",
                "latency_seconds": 0.1,
                "end_to_end_latency_seconds": 0.1,
            },
            {
                "http_status": 200,
                "model": "ollama-llama",
                "backend_name": "ollama",
                "backend_status": "completed",
                "final_backend_status": "completed",
                "latency_seconds": 0.5,
                "end_to_end_latency_seconds": 0.5,
            },
        ]
    )

    assert summary["requests_by_model"] == {"simulated-small": 1, "ollama-llama": 1}


def test_summarize_results_includes_requests_by_backend() -> None:
    summary = summarize_results(
        [
            {"http_status": 200, "model": "simulated-small", "backend_status": "completed"},
            {"http_status": 200, "model": "ollama-llama", "backend_status": "completed"},
        ]
    )

    assert summary["requests_by_backend"] == {"simulated": 1, "ollama": 1}


def test_summarize_results_calculates_latency_by_model() -> None:
    summary = summarize_results(
        [
            {
                "http_status": 200,
                "model": "simulated-small",
                "backend_status": "completed",
                "latency_seconds": 0.1,
            },
            {
                "http_status": 200,
                "model": "simulated-small",
                "backend_status": "completed",
                "latency_seconds": 0.3,
            },
        ]
    )

    assert summary["latency_by_model"]["simulated-small"]["count"] == 2
    assert summary["latency_by_model"]["simulated-small"]["average"] == 0.2


def test_summarize_results_calculates_end_to_end_latency_by_backend() -> None:
    summary = summarize_results(
        [
            {
                "http_status": 200,
                "model": "ollama-llama",
                "backend_name": "ollama",
                "backend_status": "queued",
                "final_backend_status": "completed",
                "end_to_end_latency_seconds": 1.0,
            },
            {
                "http_status": 200,
                "model": "ollama-llama",
                "backend_name": "ollama",
                "backend_status": "queued",
                "final_backend_status": "completed",
                "end_to_end_latency_seconds": 3.0,
            },
        ]
    )

    assert summary["end_to_end_latency_by_backend"]["ollama"]["count"] == 2
    assert summary["end_to_end_latency_by_backend"]["ollama"]["average"] == 2.0


def test_summarize_results_includes_final_backend_status_distribution() -> None:
    summary = summarize_results(
        [
            {
                "http_status": 200,
                "backend_status": "queued",
                "final_backend_status": "completed",
                "latency_seconds": 0.1,
                "end_to_end_latency_seconds": 0.5,
            },
            {
                "http_status": 200,
                "backend_status": "queued",
                "final_backend_status": "failed",
                "latency_seconds": 0.1,
                "end_to_end_latency_seconds": 0.4,
            },
        ]
    )

    assert summary["final_backend_status_distribution"] == {"completed": 1, "failed": 1}
    assert summary["completed_final"] == 1
    assert summary["failed_final"] == 1


def test_summarize_results_calculates_end_to_end_latency_percentiles() -> None:
    summary = summarize_results(
        [
            {
                "http_status": 200,
                "backend_status": "completed",
                "final_backend_status": "completed",
                "latency_seconds": 0.1,
                "end_to_end_latency_seconds": 0.1,
            },
            {
                "http_status": 200,
                "backend_status": "queued",
                "final_backend_status": "completed",
                "latency_seconds": 0.1,
                "end_to_end_latency_seconds": 0.5,
            },
            {
                "http_status": 200,
                "backend_status": "queued",
                "final_backend_status": "completed",
                "latency_seconds": 0.1,
                "end_to_end_latency_seconds": 0.9,
            },
        ]
    )

    assert summary["average_end_to_end_latency_seconds"] == 0.5
    assert summary["p50_end_to_end_latency_seconds"] == 0.5
    assert summary["p95_end_to_end_latency_seconds"] == 0.9
    assert summary["p99_end_to_end_latency_seconds"] == 0.9


def test_summarize_results_handles_timed_out_results() -> None:
    summary = summarize_results(
        [
            {
                "http_status": 200,
                "backend_status": "queued",
                "final_backend_status": "timed_out",
                "latency_seconds": 0.1,
                "end_to_end_latency_seconds": 30.0,
            }
        ]
    )

    assert summary["timed_out_final"] == 1
    assert summary["final_backend_status_distribution"]["timed_out"] == 1


def test_write_csv_creates_file(tmp_path) -> None:
    output_path = tmp_path / "results.csv"

    write_csv(
        [
            {
                "request_index": 0,
                "user_id": "user_standard_01",
                "project_id": "standard_project",
                "model": "simulated-small",
                "backend_name": "simulated",
                "request_type": "interactive",
                "http_status": 200,
                "backend_status": "completed",
                "request_id": "request-1",
                "latency_seconds": 0.1,
                "final_backend_status": "completed",
                "final_latency_seconds": 0.1,
                "end_to_end_latency_seconds": 0.1,
                "polling_attempts": 0,
                "polling_error": None,
                "error": None,
            }
        ],
        str(output_path),
    )

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "request_index" in content
    assert "final_backend_status" in content
    assert "end_to_end_latency_seconds" in content
    assert "polling_attempts" in content


def test_write_json_creates_file(tmp_path) -> None:
    output_path = tmp_path / "summary.json"

    write_json({"total_requests": 1}, str(output_path))

    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == {"total_requests": 1}


def test_write_comparison_markdown_creates_file(tmp_path) -> None:
    output_path = tmp_path / "comparison.md"

    write_comparison_markdown(
        {
            "total_requests": 1,
            "status_code_distribution": {"200": 1},
            "final_backend_status_distribution": {"completed": 1},
            "requests_by_backend": {"simulated": 1},
            "requests_by_model": {"simulated-small": 1},
            "latency_by_backend": {
                "simulated": {"count": 1, "average": 0.1, "p50": 0.1, "p95": 0.1, "p99": 0.1}
            },
            "latency_by_model": {
                "simulated-small": {
                    "count": 1,
                    "average": 0.1,
                    "p50": 0.1,
                    "p95": 0.1,
                    "p99": 0.1,
                }
            },
            "end_to_end_latency_by_backend": {},
            "end_to_end_latency_by_model": {},
        },
        str(output_path),
    )

    assert output_path.exists()
    assert "LLM Throughput Comparison Report" in output_path.read_text(encoding="utf-8")
