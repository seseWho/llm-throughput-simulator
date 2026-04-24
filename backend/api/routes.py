from uuid import uuid4

from fastapi import APIRouter

from backend.core.config_loader import ConfigLoader
from backend.core.request_models import GenerateRequest
from backend.core.response_models import GenerateResponse

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    """Return a placeholder generation response."""
    return GenerateResponse(
        request_id=str(uuid4()),
        status="accepted",
        message="Generation placeholder response. Full serving logic is not implemented yet.",
        estimated_input_tokens=None,
        estimated_output_tokens=request.max_tokens,
        estimated_cost_eur=None,
    )


@router.get("/metrics")
async def metrics() -> dict[str, str]:
    """Return placeholder metrics."""
    return {"status": "placeholder", "message": "Metrics collection is not implemented yet."}


@router.get("/config/summary")
async def config_summary() -> dict[str, object]:
    """Return a summary of loaded configuration files."""
    return ConfigLoader().get_config_summary()
