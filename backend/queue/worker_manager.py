import asyncio
import time
from contextlib import suppress

from backend.core.config_loader import ConfigLoader
from backend.core.request_models import GenerateRequest
from backend.llm_backends.backend_factory import get_llm_backend
from backend.llm_backends.simulated_backend import SimulatedLLMBackend
from backend.metrics.metrics_collector import MetricsCollector
from backend.persistence.usage_repository import UsageRepository
from backend.policies.policy_engine import PolicyEngine
from backend.queue.queue_manager import QueueManager


class WorkerManager:
    """Run in-memory background workers for queued simulated requests."""

    def __init__(
        self,
        queue_manager: QueueManager,
        simulated_backend: SimulatedLLMBackend,
        policy_engine: PolicyEngine,
        config_loader: ConfigLoader,
        number_of_workers: int = 3,
        metrics_collector: MetricsCollector | None = None,
        usage_repository: UsageRepository | None = None,
    ) -> None:
        self.queue_manager = queue_manager
        self.simulated_backend = simulated_backend
        self.policy_engine = policy_engine
        self.config_loader = config_loader
        self.number_of_workers = number_of_workers
        self.metrics_collector = metrics_collector
        self.usage_repository = usage_repository
        self._tasks: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        self._running = False

    def start(self) -> None:
        """Start background worker tasks."""
        if self._running:
            return

        self._stop_event.clear()
        self._tasks = [
            asyncio.create_task(self.worker_loop(worker_id))
            for worker_id in range(self.number_of_workers)
        ]
        self._running = True

    async def stop(self) -> None:
        """Stop background worker tasks cleanly."""
        if not self._running:
            return

        self._stop_event.set()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        self._running = False

    async def worker_loop(self, worker_id: int) -> None:
        """Continuously process queued requests until shutdown."""
        while not self._stop_event.is_set():
            payload = await self.queue_manager.dequeue()
            if payload is None:
                await asyncio.sleep(0.01)
                continue

            request_id = payload["queue_id"]
            self.queue_manager.set_result(
                request_id,
                {
                    "request_id": request_id,
                    "status": "processing",
                    "message": f"Request is being processed by worker {worker_id}",
                },
            )
            if self.usage_repository is not None:
                self.usage_repository.update_status(request_id, "processing")

            try:
                request = GenerateRequest(**payload["request"])
                model_config = payload["model_config"]
                policy_result = payload["policy"]
                queue_wait_seconds = time.monotonic() - payload.get("enqueued_at", time.monotonic())

                start_time = time.perf_counter()
                backend = get_llm_backend(model_config)
                response = await backend.generate(request, model_config)
                latency_seconds = time.perf_counter() - start_time
                result = response.model_dump()
                result["request_id"] = request_id
                self.queue_manager.set_result(request_id, result)
                self.policy_engine.quota_manager.consume(
                    request.project_id,
                    policy_result["estimated_total_tokens"],
                )
                if self.usage_repository is not None:
                    self.usage_repository.record_completion(
                        request_id,
                        input_tokens=result.get("estimated_input_tokens"),
                        output_tokens=result.get("estimated_output_tokens"),
                        total_tokens=(
                            (result.get("estimated_input_tokens") or 0)
                            + (result.get("estimated_output_tokens") or 0)
                        ),
                        estimated_cost_eur=result.get("estimated_cost_eur"),
                        latency_seconds=latency_seconds,
                        queue_wait_seconds=queue_wait_seconds,
                    )
                if self.metrics_collector is not None:
                    self.metrics_collector.record_completed(
                        request,
                        result,
                        latency_seconds=latency_seconds,
                        queue_wait_seconds=queue_wait_seconds,
                    )
            except Exception as exc:
                self.queue_manager.mark_failed(request_id, str(exc))
                if self.usage_repository is not None:
                    self.usage_repository.record_failure(request_id, str(exc))
                if self.metrics_collector is not None:
                    self.metrics_collector.record_failed(payload.get("request", {}), str(exc))

    def is_running(self) -> bool:
        """Return whether worker tasks are currently running."""
        return self._running

    async def __aenter__(self) -> "WorkerManager":
        self.start()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        with suppress(Exception):
            await self.stop()
