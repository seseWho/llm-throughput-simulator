from abc import ABC, abstractmethod
from typing import Any

from backend.core.request_models import GenerateRequest


class BaseLLMBackend(ABC):
    """Abstract base class for LLM backend implementations."""

    @abstractmethod
    async def generate(
        self,
        request: GenerateRequest,
        model_config: dict[str, Any],
    ) -> Any:
        """Generate a response using the provided request and model configuration."""
