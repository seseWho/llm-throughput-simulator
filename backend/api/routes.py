import asyncio
import time

from fastapi import APIRouter, HTTPException

from backend.core.config_loader import ConfigLoader
from backend.core.request_models import GenerateRequest
from backend.core.response_models import GenerateResponse
from backend.llm_backends.backend_factory import get_llm_backend
from backend.llm_backends.simulated_backend import SimulatedLLMBackend
from backend.metrics.metrics_collector import MetricsCollector
from backend.policies.policy_engine import PolicyEngine
from backend.queue.admission_controller import AdmissionController
from backend.queue.priority_scheduler import PriorityScheduler
from backend.queue.queue_manager import QueueManager
from backend.queue.worker_manager import WorkerManager

router = APIRouter()
policy_engine = PolicyEngine()
admission_controller = AdmissionController()
priority_scheduler = PriorityScheduler()
queue_manager = QueueManager()
simulated_backend = SimulatedLLMBackend()
metrics_collector = MetricsCollector()
worker_manager = WorkerManager(
    queue_manager=queue_manager,
    simulated_backend=simulated_backend,
    policy_engine=policy_engine,
    config_loader=ConfigLoader(),
    metrics_collector=metrics_collector,
)
active_requests = 0
active_requests_lock = asyncio.Lock()


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    """Generate a response using the simulated backend."""
    metrics_collector.record_received(request)
    config_loader = ConfigLoader()
    users = config_loader.configs["users.yaml"]["users"]
    projects = config_loader.configs["projects.yaml"]["projects"]
    models = config_loader.configs["models.yaml"]["models"]
    limits = config_loader.configs["limits.yaml"]

    policy_result = policy_engine.evaluate_request(
        request=request,
        users_config=users,
        projects_config=projects,
        models_config=models,
        limits_config=limits,
    )

    if not policy_result["allowed"]:
        metrics_collector.record_rejected(request, policy_result["reason"])
        raise HTTPException(
            status_code=_policy_status_code(policy_result["reason"]),
            detail=policy_result["reason"],
        )

    model_config = models.get(request.model)

    try:
        backend = get_llm_backend(model_config)
    except ValueError as exc:
        metrics_collector.record_rejected(request, "unsupported_backend")
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    global active_requests
    async with active_requests_lock:
        admission_decision = admission_controller.decide(
            queue_size=queue_manager.size(),
            active_requests=active_requests,
            limits_config=limits,
            project_priority=policy_result["project_priority"],
            request_type=request.request_type,
        )

        if admission_decision["decision"] == "accept":
            active_requests += 1
            metrics_collector.record_accepted(request, policy_result)
        elif admission_decision["decision"] == "queue":
            priority_score = priority_scheduler.get_priority_score(
                project_priority=policy_result["project_priority"],
                request_type=request.request_type,
                limits_config=limits,
            )
            queue_id = await queue_manager.enqueue(
                priority_score=priority_score,
                payload={
                    "request": request.model_dump(),
                    "model_config": model_config,
                    "policy": policy_result,
                },
            )
            metrics_collector.record_queued(request, policy_result)
            return GenerateResponse(
                request_id=queue_id,
                status="queued",
                message="Request queued for background processing",
                estimated_input_tokens=policy_result["estimated_input_tokens"],
                estimated_output_tokens=policy_result["estimated_output_tokens"],
                estimated_cost_eur=policy_result["estimated_cost_eur"],
            )
        else:
            metrics_collector.record_rejected(request, str(admission_decision["reason"]))
            raise HTTPException(
                status_code=503,
                detail=f"Request rejected by admission controller: {admission_decision['reason']}",
            )

    try:
        start_time = time.perf_counter()
        response = await backend.generate(request, model_config)
        latency_seconds = time.perf_counter() - start_time
        policy_engine.quota_manager.consume(
            request.project_id,
            policy_result["estimated_total_tokens"],
        )
        metrics_collector.record_completed(
            request,
            response,
            latency_seconds=latency_seconds,
        )
        return response
    except Exception as exc:
        metrics_collector.record_failed(request, str(exc))
        raise
    finally:
        async with active_requests_lock:
            active_requests -= 1


def _policy_status_code(reason: str) -> int:
    if reason in {"rate_limited", "quota_exceeded"}:
        return 429
    if reason in {"unknown_user", "user_disabled", "project_mismatch"}:
        return 403
    if reason == "unknown_model":
        return 404
    return 400


@router.get("/metrics")
async def metrics() -> dict[str, object]:
    """Return in-memory metrics summary."""
    return metrics_collector.get_summary()


@router.post("/metrics/reset")
async def reset_metrics() -> dict[str, str]:
    """Reset in-memory metrics."""
    metrics_collector.reset()
    return {"status": "ok", "message": "Metrics reset"}


@router.get("/queue/status")
async def queue_status() -> dict[str, object]:
    """Return in-memory queue and active request status."""
    config_loader = ConfigLoader()
    global_limits = config_loader.configs["limits.yaml"]["global_limits"]

    async with active_requests_lock:
        current_active_requests = active_requests

    return {
        "queue_size": queue_manager.size(),
        "active_requests": current_active_requests,
        "max_active_requests": int(global_limits["max_active_requests"]),
        "max_queue_size": int(global_limits["max_queue_size"]),
        "worker_running": worker_manager.is_running(),
        "worker_count": worker_manager.number_of_workers,
        "completed_requests": metrics_collector.completed_requests,
        "failed_requests": metrics_collector.failed_requests,
    }


@router.get("/requests/{request_id}")
async def request_status(request_id: str) -> dict[str, object]:
    """Return queued request status or result."""
    result = queue_manager.get_result(request_id)
    if result is None:
        return {
            "request_id": request_id,
            "status": "not_found",
            "message": "Request not found",
        }
    return result


@router.get("/config/summary")
async def config_summary() -> dict[str, object]:
    """Return a summary of loaded configuration files."""
    return ConfigLoader().get_config_summary()
