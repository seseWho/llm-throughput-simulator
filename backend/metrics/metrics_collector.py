from statistics import mean
from typing import Any


class MetricsCollector:
    """In-memory metrics collector for simulator behavior."""

    def __init__(self) -> None:
        self.reset()

    def record_received(self, request: Any) -> None:
        """Record an incoming request."""
        self.total_requests += 1
        self._increment_dimensions(request)
        self._increment(self.requests_by_status, "received")

    def record_accepted(self, request: Any, policy_result: dict) -> None:
        """Record a request accepted for immediate processing."""
        self.accepted_requests += 1
        self._increment(self.requests_by_status, "accepted")

    def record_queued(self, request: Any, policy_result: dict) -> None:
        """Record a request queued for background processing."""
        self.queued_requests += 1
        self._increment(self.requests_by_status, "queued")

    def record_rejected(self, request: Any, reason: str) -> None:
        """Record a rejected request."""
        self.rejected_requests += 1
        self._increment(self.requests_by_status, "rejected")

    def record_completed(
        self,
        request: Any,
        response: Any,
        latency_seconds: float | None = None,
        queue_wait_seconds: float | None = None,
    ) -> None:
        """Record a completed request and its token/cost accounting."""
        self.completed_requests += 1
        self._increment(self.requests_by_status, "completed")

        input_tokens = self._get(response, "estimated_input_tokens") or 0
        output_tokens = self._get(response, "estimated_output_tokens") or 0
        estimated_cost = self._get(response, "estimated_cost_eur") or 0.0

        self.total_input_tokens += int(input_tokens)
        self.total_output_tokens += int(output_tokens)
        self.total_estimated_cost_eur = round(
            self.total_estimated_cost_eur + float(estimated_cost),
            8,
        )

        if latency_seconds is not None:
            self.latencies_seconds.append(latency_seconds)
        if queue_wait_seconds is not None:
            self.queue_wait_times_seconds.append(queue_wait_seconds)

    def record_failed(self, request: Any, error: str) -> None:
        """Record a failed request."""
        self.failed_requests += 1
        self._increment(self.requests_by_status, "failed")

    def get_summary(self) -> dict:
        """Return a snapshot of all collected metrics."""
        latency_summary = self._latency_summary()
        return {
            "total_requests": self.total_requests,
            "accepted_requests": self.accepted_requests,
            "queued_requests": self.queued_requests,
            "rejected_requests": self.rejected_requests,
            "completed_requests": self.completed_requests,
            "failed_requests": self.failed_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_estimated_cost_eur": self.total_estimated_cost_eur,
            "average_latency_seconds": latency_summary["average"],
            "p50_latency_seconds": latency_summary["p50"],
            "p95_latency_seconds": latency_summary["p95"],
            "p99_latency_seconds": latency_summary["p99"],
            "average_queue_wait_seconds": (
                mean(self.queue_wait_times_seconds)
                if self.queue_wait_times_seconds
                else None
            ),
            "requests_by_project": self.requests_by_project,
            "requests_by_user": self.requests_by_user,
            "requests_by_model": self.requests_by_model,
            "requests_by_status": self.requests_by_status,
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.total_requests = 0
        self.accepted_requests = 0
        self.queued_requests = 0
        self.rejected_requests = 0
        self.completed_requests = 0
        self.failed_requests = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_estimated_cost_eur = 0.0
        self.latencies_seconds: list[float] = []
        self.queue_wait_times_seconds: list[float] = []
        self.requests_by_project: dict[str, int] = {}
        self.requests_by_user: dict[str, int] = {}
        self.requests_by_model: dict[str, int] = {}
        self.requests_by_status: dict[str, int] = {}

    def _increment_dimensions(self, request: Any) -> None:
        user_id = self._get(request, "user_id")
        project_id = self._get(request, "project_id")
        model = self._get(request, "model")

        if user_id:
            self._increment(self.requests_by_user, str(user_id))
        if project_id:
            self._increment(self.requests_by_project, str(project_id))
        if model:
            self._increment(self.requests_by_model, str(model))

    def _latency_summary(self) -> dict[str, float | None]:
        if not self.latencies_seconds:
            return {"average": None, "p50": None, "p95": None, "p99": None}

        values = sorted(self.latencies_seconds)
        return {
            "average": mean(values),
            "p50": self._percentile(values, 50),
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99),
        }

    def _percentile(self, values: list[float], percentile: int) -> float:
        index = round((len(values) - 1) * percentile / 100)
        return values[index]

    def _get(self, value: Any, field: str) -> Any:
        if isinstance(value, dict):
            return value.get(field)
        return getattr(value, field, None)

    def _increment(self, values: dict[str, int], key: str) -> None:
        values[key] = values.get(key, 0) + 1
