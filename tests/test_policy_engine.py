from backend.core.config_loader import ConfigLoader
from backend.core.request_models import GenerateRequest
from backend.policies.policy_engine import PolicyEngine


def test_policy_engine_accepts_valid_request() -> None:
    result = PolicyEngine().evaluate_request(
        request=_valid_request(),
        **_configs(),
    )

    assert result["allowed"] is True
    assert result["reason"] == "allowed"
    assert result["estimated_total_tokens"] > 0
    assert result["estimated_cost_eur"] >= 0
    assert result["project_priority"] == "normal"
    assert result["project_plan"] == "standard"


def test_policy_engine_rejects_unknown_user() -> None:
    request = _valid_request()
    request.user_id = "missing_user"

    result = PolicyEngine().evaluate_request(request=request, **_configs())

    assert result["allowed"] is False
    assert result["reason"] == "unknown_user"


def test_policy_engine_rejects_project_mismatch() -> None:
    request = _valid_request()
    request.project_id = "vip_project"

    result = PolicyEngine().evaluate_request(request=request, **_configs())

    assert result["allowed"] is False
    assert result["reason"] == "project_mismatch"


def _valid_request() -> GenerateRequest:
    return GenerateRequest(
        user_id="user_standard_01",
        project_id="standard_project",
        model="simulated-small",
        prompt="hello from policy engine",
        max_tokens=64,
    )


def _configs() -> dict:
    loader = ConfigLoader()
    return {
        "users_config": loader.configs["users.yaml"]["users"],
        "projects_config": loader.configs["projects.yaml"]["projects"],
        "models_config": loader.configs["models.yaml"]["models"],
        "limits_config": loader.configs["limits.yaml"],
    }
