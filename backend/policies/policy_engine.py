from typing import Any

from backend.core.request_models import GenerateRequest
from backend.policies.cost_tracker import CostTracker
from backend.policies.quota_manager import QuotaManager
from backend.policies.rate_limiter import RateLimiter


class PolicyEngine:
    """Coordinate initial request validation, rate limiting, quotas, and cost."""

    def __init__(
        self,
        rate_limiter: RateLimiter | None = None,
        quota_manager: QuotaManager | None = None,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        self.rate_limiter = rate_limiter or RateLimiter()
        self.quota_manager = quota_manager or QuotaManager()
        self.cost_tracker = cost_tracker or CostTracker()

    def evaluate_request(
        self,
        request: GenerateRequest,
        users_config: dict[str, Any],
        projects_config: dict[str, Any],
        models_config: dict[str, Any],
        limits_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate whether a request is allowed before backend execution."""
        users = users_config.get("users", users_config)
        projects = projects_config.get("projects", projects_config)
        models = models_config.get("models", models_config)

        empty_result = self._result()

        user_config = users.get(request.user_id)
        if user_config is None:
            return empty_result | {"allowed": False, "reason": "unknown_user"}

        if not user_config.get("enabled", False):
            return empty_result | {"allowed": False, "reason": "user_disabled"}

        project_config = projects.get(request.project_id)
        if project_config is None:
            return empty_result | {"allowed": False, "reason": "unknown_project"}

        if not project_config.get("enabled", False):
            return empty_result | {"allowed": False, "reason": "project_disabled"}

        if user_config.get("project_id") != request.project_id:
            return empty_result | {"allowed": False, "reason": "project_mismatch"}

        model_config = models.get(request.model)
        if model_config is None:
            return empty_result | {"allowed": False, "reason": "unknown_model"}

        if not model_config.get("enabled", False):
            return empty_result | {"allowed": False, "reason": "model_disabled"}

        estimated_input_tokens = len(request.prompt) // 4
        estimated_output_tokens = min(
            request.max_tokens,
            int(model_config.get("max_output_tokens", request.max_tokens)),
        )
        estimated_total_tokens = estimated_input_tokens + estimated_output_tokens
        project_plan = str(project_config.get("plan", "standard"))
        project_priority = str(project_config.get("priority", "normal"))

        if not self.rate_limiter.allow_request(request.user_id, project_plan, limits_config):
            return self._result(
                allowed=False,
                reason="rate_limited",
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
                estimated_total_tokens=estimated_total_tokens,
                estimated_cost_eur=self.cost_tracker.estimate_cost(
                    estimated_input_tokens,
                    estimated_output_tokens,
                    model_config,
                ),
                project_priority=project_priority,
                project_plan=project_plan,
            )

        if not self.quota_manager.can_consume(
            request.project_id,
            estimated_total_tokens,
            project_config,
        ):
            return self._result(
                allowed=False,
                reason="quota_exceeded",
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
                estimated_total_tokens=estimated_total_tokens,
                estimated_cost_eur=self.cost_tracker.estimate_cost(
                    estimated_input_tokens,
                    estimated_output_tokens,
                    model_config,
                ),
                project_priority=project_priority,
                project_plan=project_plan,
            )

        return self._result(
            allowed=True,
            reason="allowed",
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            estimated_total_tokens=estimated_total_tokens,
            estimated_cost_eur=self.cost_tracker.estimate_cost(
                estimated_input_tokens,
                estimated_output_tokens,
                model_config,
            ),
            project_priority=project_priority,
            project_plan=project_plan,
        )

    def _result(
        self,
        allowed: bool = False,
        reason: str = "not_evaluated",
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
        estimated_total_tokens: int = 0,
        estimated_cost_eur: float = 0.0,
        project_priority: str = "",
        project_plan: str = "",
    ) -> dict[str, Any]:
        return {
            "allowed": allowed,
            "reason": reason,
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "estimated_total_tokens": estimated_total_tokens,
            "estimated_cost_eur": estimated_cost_eur,
            "project_priority": project_priority,
            "project_plan": project_plan,
        }
