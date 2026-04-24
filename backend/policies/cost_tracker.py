class CostTracker:
    """Estimate token costs for a model request."""

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_config: dict,
    ) -> float:
        """Estimate total request cost in EUR."""
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
        return round(input_cost + output_cost, 8)
