from pydantic import BaseModel


class GenerateRequest(BaseModel):
    """Request model for a generation call."""

    user_id: str
    project_id: str
    model: str
    prompt: str
    max_tokens: int = 256
    request_type: str = "interactive"
