from backend.policies.cost_tracker import CostTracker
from backend.policies.quota_manager import QuotaManager
from backend.policies.rate_limiter import RateLimiter


def test_cost_tracker_calculates_cost() -> None:
    cost = CostTracker().estimate_cost(
        input_tokens=1000,
        output_tokens=500,
        model_config={
            "input_cost_per_1k_tokens_eur": 0.10,
            "output_cost_per_1k_tokens_eur": 0.20,
        },
    )

    assert cost == 0.20


def test_quota_manager_allows_usage_below_quota() -> None:
    quota_manager = QuotaManager()

    assert quota_manager.can_consume(
        project_id="standard_project",
        tokens=100,
        project_config={"monthly_token_quota": 1000},
    )


def test_quota_manager_rejects_usage_above_quota() -> None:
    quota_manager = QuotaManager()
    quota_manager.consume("standard_project", 950)

    assert not quota_manager.can_consume(
        project_id="standard_project",
        tokens=100,
        project_config={"monthly_token_quota": 1000},
    )


def test_rate_limiter_allows_requests_below_limit() -> None:
    rate_limiter = RateLimiter()
    limits_config = {
        "rate_limits": {
            "standard": {
                "requests_per_minute": 2,
            },
        },
    }

    assert rate_limiter.allow_request("user_standard_01", "standard", limits_config)
    assert rate_limiter.allow_request("user_standard_01", "standard", limits_config)
