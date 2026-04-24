import asyncio
from typing import Any
from uuid import uuid4

from backend.core.request_models import GenerateRequest
from backend.core.response_models import GenerateResponse
from backend.llm_backends.base_backend import BaseLLMBackend


class SimulatedLLMBackend(BaseLLMBackend):
    """Simulated LLM backend for MVP request flow testing."""

    async def generate(
        self,
        request: GenerateRequest,
        model_config: dict[str, Any],
    ) -> GenerateResponse:
        """Simulate LLM generation latency, token usage, and cost."""
        estimated_input_tokens = max(1, len(request.prompt) // 4)
        estimated_output_tokens = min(
            request.max_tokens,
            int(model_config.get("max_output_tokens", request.max_tokens)),
        )

        latency_seconds = float(model_config.get("average_latency_seconds", 0))
        if latency_seconds > 0:
            await asyncio.sleep(latency_seconds)

        input_cost = (
            estimated_input_tokens
            / 1000
            * float(model_config.get("input_cost_per_1k_tokens_eur", 0))
        )
        output_cost = (
            estimated_output_tokens
            / 1000
            * float(model_config.get("output_cost_per_1k_tokens_eur", 0))
        )
        estimated_cost_eur = input_cost + output_cost

        generated_text = (
            f"Simulated response for model '{request.model}' "
            f"with {estimated_output_tokens} estimated output tokens."
        )

        return GenerateResponse(
            request_id=str(uuid4()),
            status="completed",
            message=generated_text,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            estimated_cost_eur=estimated_cost_eur,
        )
