from typing import Any
from uuid import uuid4

import httpx

from backend.core.request_models import GenerateRequest
from backend.core.response_models import GenerateResponse
from backend.llm_backends.base_backend import BaseLLMBackend


class OllamaLLMBackend(BaseLLMBackend):
    """Ollama backend adapter using the local Ollama HTTP API."""

    async def generate(
        self,
        request: GenerateRequest,
        model_config: dict[str, Any],
    ) -> GenerateResponse:
        """Generate a response through Ollama."""
        estimated_input_tokens = max(1, len(request.prompt) // 4)
        estimated_output_tokens = min(
            request.max_tokens,
            int(model_config.get("max_output_tokens", request.max_tokens)),
        )
        estimated_cost_eur = self._estimate_cost(
            estimated_input_tokens,
            estimated_output_tokens,
            model_config,
        )

        base_url = str(model_config.get("ollama_base_url", "http://localhost:11434")).rstrip("/")
        timeout = float(model_config.get("request_timeout_seconds", 120))
        payload = {
            "model": model_config.get("ollama_model", request.model),
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "num_predict": request.max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{base_url}/api/generate", json=payload)

        if response.status_code >= 400:
            raise RuntimeError(f"Ollama request failed with HTTP {response.status_code}: {response.text}")

        data = response.json()
        if "error" in data:
            raise RuntimeError(f"Ollama request failed: {data['error']}")

        return GenerateResponse(
            request_id=str(uuid4()),
            status="completed",
            message=str(data.get("response", "")),
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            estimated_cost_eur=estimated_cost_eur,
        )

    def _estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_config: dict[str, Any],
    ) -> float:
        input_cost = (
            input_tokens
            / 1000
            * float(model_config.get("input_cost_per_1k_tokens_eur", 0))
        )
        output_cost = (
            output_tokens
            / 1000
            * float(model_config.get("output_cost_per_1k_tokens_eur", 0))
        )
        return input_cost + output_cost
