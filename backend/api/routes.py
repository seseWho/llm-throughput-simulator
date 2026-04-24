from fastapi import APIRouter, HTTPException

from backend.core.config_loader import ConfigLoader
from backend.core.request_models import GenerateRequest
from backend.core.response_models import GenerateResponse
from backend.llm_backends.simulated_backend import SimulatedLLMBackend

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    """Generate a response using the simulated backend."""
    config_loader = ConfigLoader()
    models = config_loader.configs["models.yaml"]["models"]
    model_config = models.get(request.model)

    if model_config is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {request.model}")

    if not model_config.get("enabled", False):
        raise HTTPException(status_code=400, detail=f"Model is disabled: {request.model}")

    if model_config.get("backend") != "simulated":
        raise HTTPException(
            status_code=400,
            detail="Only simulated backend is supported in Step 3.",
        )

    backend = SimulatedLLMBackend()
    return await backend.generate(request, model_config)


@router.get("/metrics")
async def metrics() -> dict[str, str]:
    """Return placeholder metrics."""
    return {"status": "placeholder", "message": "Metrics collection is not implemented yet."}


@router.get("/config/summary")
async def config_summary() -> dict[str, object]:
    """Return a summary of loaded configuration files."""
    return ConfigLoader().get_config_summary()
