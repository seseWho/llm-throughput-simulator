import asyncio
import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from backend.core.config_loader import ConfigLoader
from backend.core.request_models import GenerateRequest
from backend.core.response_models import GenerateResponse
from backend.llm_backends.backend_factory import get_llm_backend
from backend.llm_backends.simulated_backend import SimulatedLLMBackend
from backend.metrics.metrics_collector import MetricsCollector
from backend.persistence.usage_repository import UsageRepository
from backend.policies.degradation_manager import DegradationManager
from backend.policies.policy_engine import PolicyEngine
from backend.queue.admission_controller import AdmissionController
from backend.queue.priority_scheduler import PriorityScheduler
from backend.queue.queue_manager import QueueManager
from backend.queue.worker_manager import WorkerManager

router = APIRouter()
policy_engine = PolicyEngine()
degradation_manager = DegradationManager()
admission_controller = AdmissionController()
priority_scheduler = PriorityScheduler()
queue_manager = QueueManager()
simulated_backend = SimulatedLLMBackend()
metrics_collector = MetricsCollector()
usage_repository = UsageRepository()
worker_manager = WorkerManager(
    queue_manager=queue_manager,
    simulated_backend=simulated_backend,
    policy_engine=policy_engine,
    config_loader=ConfigLoader(),
    metrics_collector=metrics_collector,
    usage_repository=usage_repository,
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
    degradation = config_loader.configs["degradation.yaml"]

    policy_result = policy_engine.evaluate_request(
        request=request,
        users_config=users,
        projects_config=projects,
        models_config=models,
        limits_config=limits,
    )

    if not policy_result["allowed"]:
        request_id = str(uuid4())
        usage_repository.create_record(
            request_id=request_id,
            user_id=request.user_id,
            project_id=request.project_id,
            model=request.model,
            backend=_backend_name(models.get(request.model)),
            request_type=request.request_type,
            priority=policy_result.get("project_priority"),
            status="rejected",
            decision="policy_rejected",
            degradation_level=None,
            input_tokens=policy_result.get("estimated_input_tokens", 0),
            output_tokens=policy_result.get("estimated_output_tokens", 0),
            total_tokens=policy_result.get("estimated_total_tokens", 0),
            estimated_cost_eur=policy_result.get("estimated_cost_eur", 0.0),
            error_message=policy_result["reason"],
        )
        metrics_collector.record_rejected(request, policy_result["reason"])
        raise HTTPException(
            status_code=_policy_status_code(policy_result["reason"]),
            detail=policy_result["reason"],
        )

    current_degradation_level = degradation_manager.get_current_level(
        queue_size=queue_manager.size(),
        limits_config=limits,
        degradation_config=degradation,
    )
    degradation_result = degradation_manager.apply_degradation(
        request=request,
        policy_result=policy_result,
        current_level=current_degradation_level,
    )

    if degradation_result["actions_applied"]:
        metrics_collector.record_degraded(request, degradation_result)

    if not degradation_result["allowed"]:
        request_id = str(uuid4())
        usage_repository.create_record(
            request_id=request_id,
            user_id=request.user_id,
            project_id=request.project_id,
            model=request.model,
            backend=_backend_name(models.get(request.model)),
            request_type=request.request_type,
            priority=policy_result.get("project_priority"),
            status="rejected",
            decision="degradation_rejected",
            degradation_level=degradation_result["degradation_level"],
            input_tokens=policy_result.get("estimated_input_tokens", 0),
            output_tokens=policy_result.get("estimated_output_tokens", 0),
            total_tokens=policy_result.get("estimated_total_tokens", 0),
            estimated_cost_eur=policy_result.get("estimated_cost_eur", 0.0),
            error_message=degradation_result["reason"],
        )
        metrics_collector.record_rejected(request, degradation_result["reason"])
        raise HTTPException(status_code=503, detail=degradation_result["reason"])

    if degradation_result["modified_max_tokens"] != request.max_tokens:
        request = request.model_copy(
            update={"max_tokens": degradation_result["modified_max_tokens"]}
        )
        policy_result = policy_engine.evaluate_request(
            request=request,
            users_config=users,
            projects_config=projects,
            models_config=models,
            limits_config=limits,
        )
        if not policy_result["allowed"]:
            request_id = str(uuid4())
            usage_repository.create_record(
                request_id=request_id,
                user_id=request.user_id,
                project_id=request.project_id,
                model=request.model,
                backend=_backend_name(models.get(request.model)),
                request_type=request.request_type,
                priority=policy_result.get("project_priority"),
                status="rejected",
                decision="policy_rejected",
                degradation_level=degradation_result["degradation_level"],
                input_tokens=policy_result.get("estimated_input_tokens", 0),
                output_tokens=policy_result.get("estimated_output_tokens", 0),
                total_tokens=policy_result.get("estimated_total_tokens", 0),
                estimated_cost_eur=policy_result.get("estimated_cost_eur", 0.0),
                error_message=policy_result["reason"],
            )
            metrics_collector.record_rejected(request, policy_result["reason"])
            raise HTTPException(
                status_code=_policy_status_code(policy_result["reason"]),
                detail=policy_result["reason"],
            )

    model_config = models.get(request.model)

    try:
        backend = get_llm_backend(model_config)
    except ValueError as exc:
        request_id = str(uuid4())
        usage_repository.create_record(
            request_id=request_id,
            user_id=request.user_id,
            project_id=request.project_id,
            model=request.model,
            backend=_backend_name(model_config),
            request_type=request.request_type,
            priority=policy_result.get("project_priority"),
            status="rejected",
            decision="unsupported_backend",
            degradation_level=degradation_result["degradation_level"],
            input_tokens=policy_result.get("estimated_input_tokens", 0),
            output_tokens=policy_result.get("estimated_output_tokens", 0),
            total_tokens=policy_result.get("estimated_total_tokens", 0),
            estimated_cost_eur=policy_result.get("estimated_cost_eur", 0.0),
            error_message=str(exc),
        )
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
            request_id = str(uuid4())
            usage_repository.create_record(
                request_id=request_id,
                user_id=request.user_id,
                project_id=request.project_id,
                model=request.model,
                backend=_backend_name(model_config),
                request_type=request.request_type,
                priority=policy_result.get("project_priority"),
                status="processing",
                decision="accept",
                degradation_level=degradation_result["degradation_level"],
                input_tokens=policy_result.get("estimated_input_tokens", 0),
                output_tokens=policy_result.get("estimated_output_tokens", 0),
                total_tokens=policy_result.get("estimated_total_tokens", 0),
                estimated_cost_eur=policy_result.get("estimated_cost_eur", 0.0),
            )
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
            usage_repository.create_record(
                request_id=queue_id,
                user_id=request.user_id,
                project_id=request.project_id,
                model=request.model,
                backend=_backend_name(model_config),
                request_type=request.request_type,
                priority=policy_result.get("project_priority"),
                status="queued",
                decision="queue",
                degradation_level=degradation_result["degradation_level"],
                input_tokens=policy_result.get("estimated_input_tokens", 0),
                output_tokens=policy_result.get("estimated_output_tokens", 0),
                total_tokens=policy_result.get("estimated_total_tokens", 0),
                estimated_cost_eur=policy_result.get("estimated_cost_eur", 0.0),
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
            request_id = str(uuid4())
            usage_repository.create_record(
                request_id=request_id,
                user_id=request.user_id,
                project_id=request.project_id,
                model=request.model,
                backend=_backend_name(model_config),
                request_type=request.request_type,
                priority=policy_result.get("project_priority"),
                status="rejected",
                decision="admission_rejected",
                degradation_level=degradation_result["degradation_level"],
                input_tokens=policy_result.get("estimated_input_tokens", 0),
                output_tokens=policy_result.get("estimated_output_tokens", 0),
                total_tokens=policy_result.get("estimated_total_tokens", 0),
                estimated_cost_eur=policy_result.get("estimated_cost_eur", 0.0),
                error_message=str(admission_decision["reason"]),
            )
            metrics_collector.record_rejected(request, str(admission_decision["reason"]))
            raise HTTPException(
                status_code=503,
                detail=f"Request rejected by admission controller: {admission_decision['reason']}",
            )

    try:
        start_time = time.perf_counter()
        response = await backend.generate(request, model_config)
        response.request_id = request_id
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
        usage_repository.record_completion(
            request_id,
            input_tokens=response.estimated_input_tokens,
            output_tokens=response.estimated_output_tokens,
            total_tokens=(response.estimated_input_tokens or 0) + (response.estimated_output_tokens or 0),
            estimated_cost_eur=response.estimated_cost_eur,
            latency_seconds=latency_seconds,
        )
        return response
    except Exception as exc:
        usage_repository.record_failure(request_id, str(exc))
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


def _backend_name(model_config: dict | None) -> str | None:
    if not model_config:
        return None
    return model_config.get("backend")


@router.get("/metrics")
async def metrics() -> dict[str, object]:
    """Return in-memory metrics summary."""
    return metrics_collector.get_summary()


@router.post("/metrics/reset")
async def reset_metrics() -> dict[str, str]:
    """Reset in-memory metrics."""
    metrics_collector.reset()
    return {"status": "ok", "message": "Metrics reset"}


@router.get("/usage/summary")
async def usage_summary() -> dict[str, object]:
    """Return persisted usage summary."""
    return usage_repository.get_summary()


@router.get("/usage/project/{project_id}")
async def usage_project_summary(project_id: str) -> dict[str, object]:
    """Return persisted usage summary for a project."""
    return usage_repository.get_project_summary(project_id)


@router.get("/usage/user/{user_id}")
async def usage_user_summary(user_id: str) -> dict[str, object]:
    """Return persisted usage summary for a user."""
    return usage_repository.get_user_summary(user_id)


@router.get("/usage/recent")
async def usage_recent(limit: int = 50) -> list[dict]:
    """Return recent persisted usage records."""
    return usage_repository.get_recent_records(limit=limit)


@router.get("/queue/status")
async def queue_status() -> dict[str, object]:
    """Return in-memory queue and active request status."""
    config_loader = ConfigLoader()
    limits = config_loader.configs["limits.yaml"]
    global_limits = limits["global_limits"]
    current_degradation_level = degradation_manager.get_current_level(
        queue_size=queue_manager.size(),
        limits_config=limits,
        degradation_config=config_loader.configs["degradation.yaml"],
    )

    async with active_requests_lock:
        current_active_requests = active_requests

    return {
        "queue_size": queue_manager.size(),
        "active_requests": current_active_requests,
        "max_active_requests": int(global_limits["max_active_requests"]),
        "max_queue_size": int(global_limits["max_queue_size"]),
        "current_degradation_level": current_degradation_level["name"],
        "current_degradation_level_number": current_degradation_level["level"],
        "queue_usage_ratio": current_degradation_level["queue_usage_ratio"],
        "degradation_actions": current_degradation_level.get("actions", {}),
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
