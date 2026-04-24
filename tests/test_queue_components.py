import asyncio

from backend.core.config_loader import ConfigLoader
from backend.core.request_models import GenerateRequest
from backend.llm_backends.simulated_backend import SimulatedLLMBackend
from backend.policies.policy_engine import PolicyEngine
from backend.queue.admission_controller import AdmissionController
from backend.queue.priority_scheduler import PriorityScheduler
from backend.queue.queue_manager import QueueManager
from backend.queue.worker_manager import WorkerManager


def test_admission_controller_accepts_when_active_capacity_available() -> None:
    decision = AdmissionController().decide(
        queue_size=0,
        active_requests=0,
        limits_config=_limits_config(max_active_requests=1, max_queue_size=1),
        project_priority="normal",
        request_type="interactive",
    )

    assert decision["admitted"] is True
    assert decision["decision"] == "accept"


def test_admission_controller_queues_when_active_full_and_queue_has_capacity() -> None:
    decision = AdmissionController().decide(
        queue_size=0,
        active_requests=1,
        limits_config=_limits_config(max_active_requests=1, max_queue_size=1),
        project_priority="normal",
        request_type="interactive",
    )

    assert decision["admitted"] is True
    assert decision["decision"] == "queue"


def test_admission_controller_rejects_when_active_full_and_queue_full() -> None:
    decision = AdmissionController().decide(
        queue_size=1,
        active_requests=1,
        limits_config=_limits_config(max_active_requests=1, max_queue_size=1),
        project_priority="normal",
        request_type="interactive",
    )

    assert decision["admitted"] is False
    assert decision["decision"] == "reject"


def test_priority_scheduler_scores_high_priority_above_normal() -> None:
    scheduler = PriorityScheduler()
    limits_config = _limits_config()

    high_score = scheduler.get_priority_score("high", "interactive", limits_config)
    normal_score = scheduler.get_priority_score("normal", "interactive", limits_config)

    assert high_score > normal_score


def test_priority_scheduler_scores_interactive_above_batch_for_same_priority() -> None:
    scheduler = PriorityScheduler()
    limits_config = _limits_config()

    interactive_score = scheduler.get_priority_score("normal", "interactive", limits_config)
    batch_score = scheduler.get_priority_score("normal", "batch", limits_config)

    assert interactive_score > batch_score


def test_queue_manager_dequeues_high_priority_before_low_priority() -> None:
    async def run_queue_check() -> None:
        queue_manager = QueueManager()

        await queue_manager.enqueue(priority_score=1, payload={"name": "low"})
        await queue_manager.enqueue(priority_score=10, payload={"name": "high"})

        first = await queue_manager.dequeue()
        second = await queue_manager.dequeue()

        assert first is not None
        assert second is not None
        assert first["name"] == "high"
        assert second["name"] == "low"
        assert first["queue_id"]
        assert second["queue_id"]

    asyncio.run(run_queue_check())


def test_queue_manager_can_store_and_retrieve_result() -> None:
    queue_manager = QueueManager()

    queue_manager.set_result(
        "request-1",
        {
            "request_id": "request-1",
            "status": "completed",
            "message": "done",
        },
    )

    result = queue_manager.get_result("request-1")

    assert result is not None
    assert result["status"] == "completed"
    assert queue_manager.completed_count() == 1


def test_queue_manager_can_mark_failed_request() -> None:
    queue_manager = QueueManager()

    queue_manager.mark_failed("request-1", "failed for test")

    result = queue_manager.get_result("request-1")

    assert result is not None
    assert result["status"] == "failed"
    assert result["message"] == "failed for test"
    assert queue_manager.failed_count() == 1


def test_worker_manager_can_process_one_queued_simulated_request() -> None:
    async def run_worker_check() -> None:
        queue_manager = QueueManager()
        policy_engine = PolicyEngine()
        worker_manager = WorkerManager(
            queue_manager=queue_manager,
            simulated_backend=SimulatedLLMBackend(),
            policy_engine=policy_engine,
            config_loader=ConfigLoader(),
            number_of_workers=1,
        )
        request = GenerateRequest(
            user_id="user_standard_01",
            project_id="standard_project",
            model="simulated-small",
            prompt="hello",
            max_tokens=64,
        )

        request_id = await queue_manager.enqueue(
            priority_score=5,
            payload={
                "request": request.model_dump(),
                "model_config": {
                    "backend": "simulated",
                    "max_output_tokens": 512,
                    "average_latency_seconds": 0,
                    "input_cost_per_1k_tokens_eur": 0.0001,
                    "output_cost_per_1k_tokens_eur": 0.0002,
                },
                "policy": {
                    "estimated_total_tokens": 65,
                },
            },
        )

        worker_manager.start()
        try:
            result = None
            for _ in range(20):
                result = queue_manager.get_result(request_id)
                if result is not None and result["status"] == "completed":
                    break
                await asyncio.sleep(0.01)

            assert result is not None
            assert result["status"] == "completed"
            assert result["request_id"] == request_id
            assert policy_engine.quota_manager.get_project_usage("standard_project") == 65
        finally:
            await worker_manager.stop()

    asyncio.run(run_worker_check())


def _limits_config(
    max_active_requests: int = 50,
    max_queue_size: int = 1000,
) -> dict:
    return {
        "global_limits": {
            "max_active_requests": max_active_requests,
            "max_queue_size": max_queue_size,
        },
        "priority_weights": {
            "high": 10,
            "normal": 5,
            "low": 1,
        },
    }
