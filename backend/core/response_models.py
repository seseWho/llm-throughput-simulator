from pydantic import BaseModel


class GenerateResponse(BaseModel):
    """Response model for a generation call."""

    request_id: str
    status: str
    message: str
    estimated_input_tokens: int | None
    estimated_output_tokens: int | None
    estimated_cost_eur: float | None
