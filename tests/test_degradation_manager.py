from backend.core.request_models import GenerateRequest
from backend.policies.degradation_manager import DegradationManager


def test_normal_level_selected_when_queue_usage_below_threshold() -> None:
    level = DegradationManager().get_current_level(
        queue_size=10,
        limits_config=_limits(max_queue_size=100),
        degradation_config=_degradation_config(),
    )

    assert level["name"] == "normal"
    assert level["level"] == 0


def test_soft_pressure_selected_when_queue_usage_crosses_060() -> None:
    level = DegradationManager().get_current_level(
        queue_size=60,
        limits_config=_limits(max_queue_size=100),
        degradation_config=_degradation_config(),
    )

    assert level["name"] == "soft_pressure"


def test_high_pressure_selected_when_queue_usage_crosses_080() -> None:
    level = DegradationManager().get_current_level(
        queue_size=80,
        limits_config=_limits(max_queue_size=100),
        degradation_config=_degradation_config(),
    )

    assert level["name"] == "high_pressure"


def test_critical_pressure_selected_when_queue_usage_crosses_095() -> None:
    level = DegradationManager().get_current_level(
        queue_size=95,
        limits_config=_limits(max_queue_size=100),
        degradation_config=_degradation_config(),
    )

    assert level["name"] == "critical_pressure"


def test_batch_request_is_rejected_when_reject_batch_is_true() -> None:
    result = DegradationManager().apply_degradation(
        request=_request(request_type="batch"),
        policy_result={"project_priority": "low"},
        current_level=_level("high_pressure"),
    )

    assert result["allowed"] is False
    assert result["actions_applied"] == ["reject_batch"]


def test_standard_request_is_rejected_when_reject_standard_is_true() -> None:
    result = DegradationManager().apply_degradation(
        request=_request(),
        policy_result={"project_priority": "normal"},
        current_level=_level("critical_pressure"),
    )

    assert result["allowed"] is False
    assert result["actions_applied"] == ["reject_standard"]


def test_high_priority_request_is_allowed_during_critical_pressure() -> None:
    result = DegradationManager().apply_degradation(
        request=_request(max_tokens=100),
        policy_result={"project_priority": "high"},
        current_level=_level("critical_pressure"),
    )

    assert result["allowed"] is True
    assert result["modified_max_tokens"] == 25


def test_max_tokens_is_reduced_by_factor() -> None:
    result = DegradationManager().apply_degradation(
        request=_request(max_tokens=100),
        policy_result={"project_priority": "normal"},
        current_level=_level("soft_pressure"),
    )

    assert result["allowed"] is True
    assert result["modified_max_tokens"] == 75
    assert "reduce_max_tokens" in result["actions_applied"]


def test_reduced_max_tokens_never_goes_below_one() -> None:
    result = DegradationManager().apply_degradation(
        request=_request(max_tokens=1),
        policy_result={"project_priority": "normal"},
        current_level=_level("soft_pressure"),
    )

    assert result["modified_max_tokens"] == 1


def _request(max_tokens: int = 64, request_type: str = "interactive") -> GenerateRequest:
    return GenerateRequest(
        user_id="user_standard_01",
        project_id="standard_project",
        model="simulated-small",
        prompt="hello",
        max_tokens=max_tokens,
        request_type=request_type,
    )


def _limits(max_queue_size: int) -> dict:
    return {"global_limits": {"max_queue_size": max_queue_size}}


def _degradation_config() -> dict:
    return {
        "degradation_levels": {
            "normal": _level("normal"),
            "soft_pressure": _level("soft_pressure"),
            "high_pressure": _level("high_pressure"),
            "critical_pressure": _level("critical_pressure"),
        }
    }


def _level(name: str) -> dict:
    levels = {
        "normal": {
            "level": 0,
            "queue_usage_threshold": 0.40,
            "actions": {
                "reduce_max_tokens": False,
                "reject_batch": False,
                "reject_standard": False,
            },
        },
        "soft_pressure": {
            "level": 1,
            "queue_usage_threshold": 0.60,
            "actions": {
                "reduce_max_tokens": True,
                "max_output_token_factor": 0.75,
                "reject_batch": False,
                "reject_standard": False,
            },
        },
        "high_pressure": {
            "level": 2,
            "queue_usage_threshold": 0.80,
            "actions": {
                "reduce_max_tokens": True,
                "max_output_token_factor": 0.50,
                "reject_batch": True,
                "reject_standard": False,
            },
        },
        "critical_pressure": {
            "level": 3,
            "queue_usage_threshold": 0.95,
            "actions": {
                "reduce_max_tokens": True,
                "max_output_token_factor": 0.25,
                "reject_batch": True,
                "reject_standard": True,
                "allow_only_priority": "high",
            },
        },
    }
    return levels[name] | {"name": name}
