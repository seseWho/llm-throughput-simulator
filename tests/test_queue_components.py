import asyncio

from backend.queue.admission_controller import AdmissionController
from backend.queue.priority_scheduler import PriorityScheduler
from backend.queue.queue_manager import QueueManager


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
