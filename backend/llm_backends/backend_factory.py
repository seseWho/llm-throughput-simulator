from backend.llm_backends.base_backend import BaseLLMBackend
from backend.llm_backends.ollama_backend import OllamaLLMBackend
from backend.llm_backends.simulated_backend import SimulatedLLMBackend


def get_llm_backend(model_config: dict) -> BaseLLMBackend:
    """Return the backend adapter configured for a model."""
    backend_name = model_config.get("backend")
    if backend_name == "simulated":
        return SimulatedLLMBackend()
    if backend_name == "ollama":
        return OllamaLLMBackend()

    raise ValueError(f"Unsupported backend: {backend_name}")
