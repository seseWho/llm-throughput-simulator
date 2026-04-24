import asyncio

import pytest

from backend.core.request_models import GenerateRequest
from backend.llm_backends.backend_factory import get_llm_backend
from backend.llm_backends.ollama_backend import OllamaLLMBackend
from backend.llm_backends.simulated_backend import SimulatedLLMBackend


def test_backend_selection_returns_simulated_backend_for_simulated_model() -> None:
    backend = get_llm_backend({"backend": "simulated"})

    assert isinstance(backend, SimulatedLLMBackend)


def test_backend_selection_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Unsupported backend"):
        get_llm_backend({"backend": "missing"})


def test_ollama_backend_generates_with_mocked_httpx_client(monkeypatch) -> None:
    captured: dict = {}

    class DummyResponse:
        status_code = 200
        text = '{"response":"hello from ollama"}'

        def json(self) -> dict:
            return {"response": "hello from ollama"}

    class DummyAsyncClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def post(self, url: str, json: dict) -> DummyResponse:
            captured["url"] = url
            captured["json"] = json
            return DummyResponse()

    monkeypatch.setattr("backend.llm_backends.ollama_backend.httpx.AsyncClient", DummyAsyncClient)
    request = GenerateRequest(
        user_id="user_vip_01",
        project_id="vip_project",
        model="ollama-llama",
        prompt="hello",
        max_tokens=64,
    )
    model_config = {
        "ollama_base_url": "http://localhost:11434",
        "ollama_model": "llama3.1",
        "request_timeout_seconds": 120,
        "max_output_tokens": 1024,
        "input_cost_per_1k_tokens_eur": 0.0,
        "output_cost_per_1k_tokens_eur": 0.0,
    }

    response = asyncio.run(OllamaLLMBackend().generate(request, model_config))

    assert response.status == "completed"
    assert response.message == "hello from ollama"
    assert response.estimated_input_tokens == 1
    assert response.estimated_output_tokens == 64
    assert response.estimated_cost_eur == 0.0
    assert captured["timeout"] == 120
    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["json"] == {
        "model": "llama3.1",
        "prompt": "hello",
        "stream": False,
        "options": {
            "num_predict": 64,
        },
    }
