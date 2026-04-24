from backend.core.request_models import GenerateRequest
from backend.core.response_models import GenerateResponse
from backend.metrics.metrics_collector import MetricsCollector


def test_metrics_collector_starts_with_zero_counters() -> None:
    summary = MetricsCollector().get_summary()

    assert summary["total_requests"] == 0
    assert summary["accepted_requests"] == 0
    assert summary["queued_requests"] == 0
    assert summary["rejected_requests"] == 0
    assert summary["completed_requests"] == 0
    assert summary["failed_requests"] == 0


def test_record_received_increments_total_requests() -> None:
    collector = MetricsCollector()

    collector.record_received(_request())

    summary = collector.get_summary()
    assert summary["total_requests"] == 1
    assert summary["requests_by_user"]["user_standard_01"] == 1
    assert summary["requests_by_project"]["standard_project"] == 1
    assert summary["requests_by_model"]["simulated-small"] == 1


def test_record_queued_increments_queued_requests() -> None:
    collector = MetricsCollector()

    collector.record_queued(_request(), {"estimated_total_tokens": 65})

    summary = collector.get_summary()
    assert summary["queued_requests"] == 1
    assert summary["requests_by_status"]["queued"] == 1


def test_record_completed_increments_completed_and_token_totals() -> None:
    collector = MetricsCollector()

    collector.record_completed(
        _request(),
        GenerateResponse(
            request_id="request-1",
            status="completed",
            message="done",
            estimated_input_tokens=10,
            estimated_output_tokens=64,
            estimated_cost_eur=0.01,
        ),
        latency_seconds=0.2,
    )

    summary = collector.get_summary()
    assert summary["completed_requests"] == 1
    assert summary["total_input_tokens"] == 10
    assert summary["total_output_tokens"] == 64
    assert summary["total_estimated_cost_eur"] == 0.01


def test_get_summary_returns_latency_fields() -> None:
    summary = MetricsCollector().get_summary()

    assert "average_latency_seconds" in summary
    assert "p50_latency_seconds" in summary
    assert "p95_latency_seconds" in summary
    assert "p99_latency_seconds" in summary
    assert summary["average_latency_seconds"] is None


def _request() -> GenerateRequest:
    return GenerateRequest(
        user_id="user_standard_01",
        project_id="standard_project",
        model="simulated-small",
        prompt="hello",
        max_tokens=64,
    )
