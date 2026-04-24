class PriorityScheduler:
    """Calculate priority scores for queued requests."""

    def get_priority_score(
        self,
        project_priority: str,
        request_type: str,
        limits_config: dict,
    ) -> int:
        """Return a priority score where higher means more important."""
        priority_weights = limits_config.get("priority_weights", {})
        base_score = int(
            priority_weights.get(
                project_priority,
                priority_weights.get("normal", 5),
            )
        )

        if request_type == "interactive":
            return base_score + 2
        if request_type == "batch":
            return base_score - 1
        return base_score
