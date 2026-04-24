import asyncio

from backend.core.request_models import GenerateRequest
from backend.llm_backends.simulated_backend import SimulatedLLMBackend


def test_simulated_backend_returns_completed_response() -> None:
    request = GenerateRequest(
        user_id="user_standard_01",
        project_id="standard_project",
        model="simulated-small",
        prompt="hello simulated backend",
        max_tokens=64,
    )
    model_config = {
        "max_output_tokens": 512,
        "average_latency_seconds": 0,
        "input_cost_per_1k_tokens_eur": 0.0001,
        "output_cost_per_1k_tokens_eur": 0.0002,
    }

    response = asyncio.run(SimulatedLLMBackend().generate(request, model_config))

    assert response.status == "completed"
    assert response.request_id
    assert response.message


def test_simulated_backend_estimates_tokens() -> None:
    request = GenerateRequest(
        user_id="user_standard_01",
        project_id="standard_project",
        model="simulated-small",
        prompt="abcd" * 10,
        max_tokens=800,
    )
    model_config = {
        "max_output_tokens": 512,
        "average_latency_seconds": 0,
        "input_cost_per_1k_tokens_eur": 0.0001,
        "output_cost_per_1k_tokens_eur": 0.0002,
    }

    response = asyncio.run(SimulatedLLMBackend().generate(request, model_config))

    assert response.estimated_input_tokens == 10
    assert response.estimated_output_tokens == 512


def test_simulated_backend_estimated_cost_is_non_negative() -> None:
    request = GenerateRequest(
        user_id="user_standard_01",
        project_id="standard_project",
        model="simulated-small",
        prompt="hello",
        max_tokens=64,
    )
    model_config = {
        "max_output_tokens": 512,
        "average_latency_seconds": 0,
        "input_cost_per_1k_tokens_eur": 0.0001,
        "output_cost_per_1k_tokens_eur": 0.0002,
    }

    response = asyncio.run(SimulatedLLMBackend().generate(request, model_config))

    assert response.estimated_cost_eur is not None
    assert response.estimated_cost_eur >= 0
