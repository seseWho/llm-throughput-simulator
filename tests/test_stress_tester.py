import json

from stress_tester.report_writer import summarize_results, write_csv, write_json
from stress_tester.scenarios import SCENARIOS


def test_scenario_registry_contains_normal_load() -> None:
    assert "normal_load" in SCENARIOS


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


def test_write_csv_creates_file(tmp_path) -> None:
    output_path = tmp_path / "results.csv"

    write_csv(
        [
            {
                "request_index": 0,
                "user_id": "user_standard_01",
                "project_id": "standard_project",
                "model": "simulated-small",
                "request_type": "interactive",
                "http_status": 200,
                "backend_status": "completed",
                "request_id": "request-1",
                "latency_seconds": 0.1,
                "error": None,
            }
        ],
        str(output_path),
    )

    assert output_path.exists()
    assert "request_index" in output_path.read_text(encoding="utf-8")


def test_write_json_creates_file(tmp_path) -> None:
    output_path = tmp_path / "summary.json"

    write_json({"total_requests": 1}, str(output_path))

    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == {"total_requests": 1}
