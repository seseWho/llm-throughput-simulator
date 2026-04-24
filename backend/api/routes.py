from fastapi import APIRouter, HTTPException

from backend.core.config_loader import ConfigLoader
from backend.core.request_models import GenerateRequest
from backend.core.response_models import GenerateResponse
from backend.llm_backends.simulated_backend import SimulatedLLMBackend
from backend.policies.policy_engine import PolicyEngine

router = APIRouter()
policy_engine = PolicyEngine()


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    """Generate a response using the simulated backend."""
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
        raise HTTPException(
            status_code=_policy_status_code(policy_result["reason"]),
            detail=policy_result["reason"],
        )

    model_config = models.get(request.model)

    if model_config.get("backend") != "simulated":
        raise HTTPException(
            status_code=400,
            detail="Only simulated backend is supported in Step 4.",
        )

    backend = SimulatedLLMBackend()
    response = await backend.generate(request, model_config)
    policy_engine.quota_manager.consume(
        request.project_id,
        policy_result["estimated_total_tokens"],
    )
    return response


def _policy_status_code(reason: str) -> int:
    if reason in {"rate_limited", "quota_exceeded"}:
        return 429
    if reason in {"unknown_user", "user_disabled", "project_mismatch"}:
        return 403
    if reason == "unknown_model":
        return 404
    return 400


@router.get("/metrics")
async def metrics() -> dict[str, str]:
    """Return placeholder metrics."""
    return {"status": "placeholder", "message": "Metrics collection is not implemented yet."}


@router.get("/config/summary")
async def config_summary() -> dict[str, object]:
    """Return a summary of loaded configuration files."""
    return ConfigLoader().get_config_summary()
