from typing import Any

from backend.core.request_models import GenerateRequest


class DegradationManager:
    """Apply queue-pressure degradation rules from configuration."""

    def get_current_level(
        self,
        queue_size: int,
        limits_config: dict,
        degradation_config: dict,
    ) -> dict[str, Any]:
        """Return the current degradation level based on queue usage."""
        global_limits = limits_config.get("global_limits", {})
        max_queue_size = int(global_limits.get("max_queue_size", 0))
        queue_usage_ratio = queue_size / max_queue_size if max_queue_size > 0 else 0.0
        levels = degradation_config.get("degradation_levels", {})
        selected_name = "normal"
        selected_level = levels.get("normal", {"level": 0, "actions": {}})

        for level_name, level_config in levels.items():
            threshold = float(level_config.get("queue_usage_threshold", 0))
            current_level_number = int(level_config.get("level", 0))
            selected_level_number = int(selected_level.get("level", 0))
            if queue_usage_ratio >= threshold and current_level_number >= selected_level_number:
                selected_name = level_name
                selected_level = level_config

        return selected_level | {
            "name": selected_name,
            "queue_usage_ratio": queue_usage_ratio,
        }

    def apply_degradation(
        self,
        request: GenerateRequest,
        policy_result: dict,
        current_level: dict,
    ) -> dict[str, Any]:
        """Return degradation decision and modified request parameters."""
        actions = current_level.get("actions", {})
        actions_applied: list[str] = []
        modified_max_tokens = request.max_tokens
        degradation_level = str(current_level.get("name", "normal"))

        if actions.get("reject_batch") is True and request.request_type == "batch":
            return {
                "allowed": False,
                "reason": "Batch requests rejected due to high system pressure",
                "modified_max_tokens": modified_max_tokens,
                "degradation_level": degradation_level,
                "actions_applied": ["reject_batch"],
            }

        if actions.get("reject_standard") is True and policy_result.get("project_priority") != "high":
            return {
                "allowed": False,
                "reason": "Standard requests rejected due to critical system pressure",
                "modified_max_tokens": modified_max_tokens,
                "degradation_level": degradation_level,
                "actions_applied": ["reject_standard"],
            }

        allow_only_priority = actions.get("allow_only_priority")
        if allow_only_priority and policy_result.get("project_priority") != allow_only_priority:
            return {
                "allowed": False,
                "reason": f"Only {allow_only_priority} priority requests allowed due to system pressure",
                "modified_max_tokens": modified_max_tokens,
                "degradation_level": degradation_level,
                "actions_applied": ["allow_only_priority"],
            }

        if actions.get("reduce_max_tokens") is True:
            factor = float(actions.get("max_output_token_factor", 1.0))
            modified_max_tokens = max(1, int(request.max_tokens * factor))
            if modified_max_tokens < request.max_tokens:
                actions_applied.append("reduce_max_tokens")

        return {
            "allowed": True,
            "reason": "allowed",
            "modified_max_tokens": modified_max_tokens,
            "degradation_level": degradation_level,
            "actions_applied": actions_applied,
        }
