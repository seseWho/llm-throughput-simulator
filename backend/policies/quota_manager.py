class QuotaManager:
    """Track in-memory project token usage against configured quotas."""

    def __init__(self) -> None:
        self._project_usage: dict[str, int] = {}

    def get_project_usage(self, project_id: str) -> int:
        """Return tokens consumed by a project in this process."""
        return self._project_usage.get(project_id, 0)

    def can_consume(self, project_id: str, tokens: int, project_config: dict) -> bool:
        """Return whether the project can consume the requested tokens."""
        quota = project_config.get("monthly_token_quota")
        if quota is None:
            return True

        return self.get_project_usage(project_id) + tokens <= int(quota)

    def consume(self, project_id: str, tokens: int) -> None:
        """Record token consumption for a project."""
        self._project_usage[project_id] = self.get_project_usage(project_id) + tokens
