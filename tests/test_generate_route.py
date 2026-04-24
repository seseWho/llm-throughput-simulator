from fastapi.testclient import TestClient

from backend.api import routes
from backend.main import app


client = TestClient(app)


def test_generate_works_with_simulated_small() -> None:
    response = client.post(
        "/generate",
        json={
            "user_id": "user_standard_01",
            "project_id": "standard_project",
            "model": "simulated-small",
            "prompt": "hello",
            "max_tokens": 64,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["estimated_input_tokens"] == 1
    assert data["estimated_output_tokens"] == 64
    assert data["estimated_cost_eur"] >= 0


def test_queue_status_returns_expected_fields() -> None:
    response = client.get("/queue/status")

    assert response.status_code == 200
    data = response.json()
    assert "queue_size" in data
    assert "active_requests" in data
    assert "max_active_requests" in data
    assert "max_queue_size" in data
    assert "worker_running" in data
    assert "worker_count" in data
    assert "completed_requests" in data
    assert "failed_requests" in data
    assert "current_degradation_level" in data
    assert "current_degradation_level_number" in data
    assert "queue_usage_ratio" in data
    assert "degradation_actions" in data


def test_metrics_reset_resets_counters() -> None:
    client.post(
        "/generate",
        json={
            "user_id": "user_standard_01",
            "project_id": "standard_project",
            "model": "simulated-small",
            "prompt": "hello",
            "max_tokens": 64,
        },
    )

    reset_response = client.post("/metrics/reset")
    metrics_response = client.get("/metrics")

    assert reset_response.status_code == 200
    assert reset_response.json()["status"] == "ok"
    assert metrics_response.json()["total_requests"] == 0


def test_request_status_returns_not_found_for_unknown_id() -> None:
    response = client.get("/requests/unknown-request-id")

    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "unknown-request-id"
    assert data["status"] == "not_found"


def test_generate_can_return_queued_when_capacity_is_saturated() -> None:
    original_active_requests = routes.active_requests
    routes.active_requests = 50

    try:
        response = client.post(
            "/generate",
            json={
                "user_id": "user_standard_01",
                "project_id": "standard_project",
                "model": "simulated-small",
                "prompt": "hello",
                "max_tokens": 64,
            },
        )
    finally:
        routes.active_requests = original_active_requests

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["request_id"]
    assert data["message"] == "Request queued for background processing"


def test_generate_rejects_nonexistent_model() -> None:
    response = client.post(
        "/generate",
        json={
            "user_id": "user_standard_01",
            "project_id": "standard_project",
            "model": "missing-model",
            "prompt": "hello",
            "max_tokens": 64,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "unknown_model"


def test_generate_rejects_invalid_user() -> None:
    response = client.post(
        "/generate",
        json={
            "user_id": "missing_user",
            "project_id": "standard_project",
            "model": "simulated-small",
            "prompt": "hello",
            "max_tokens": 64,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "unknown_user"


def test_generate_rejects_disabled_ollama_model(monkeypatch) -> None:
    class DisabledOllamaConfigLoader:
        def __init__(self) -> None:
            self.configs = {
                "users.yaml": {
                    "users": {
                        "user_vip_01": {
                            "name": "VIP User 01",
                            "project_id": "vip_project",
                            "role": "user",
                            "enabled": True,
                        },
                    },
                },
                "projects.yaml": {
                    "projects": {
                        "vip_project": {
                            "name": "VIP Project",
                            "plan": "vip",
                            "priority": "high",
                            "monthly_token_quota": 20000000,
                            "enabled": True,
                        },
                    },
                },
                "models.yaml": {
                    "models": {
                        "ollama-llama": {
                            "backend": "ollama",
                            "enabled": False,
                            "max_output_tokens": 1024,
                            "input_cost_per_1k_tokens_eur": 0.0,
                            "output_cost_per_1k_tokens_eur": 0.0,
                        },
                    },
                },
                "limits.yaml": {
                    "global_limits": {
                        "max_active_requests": 50,
                        "max_queue_size": 1000,
                    },
                    "rate_limits": {
                        "vip": {
                            "requests_per_minute": 300,
                            "tokens_per_minute": 500000,
                        },
                    },
                    "priority_weights": {
                        "high": 10,
                        "normal": 5,
                        "low": 1,
                    },
                },
                "degradation.yaml": {
                    "degradation_levels": {
                        "normal": {
                            "level": 0,
                            "queue_usage_threshold": 0.40,
                            "actions": {
                                "reduce_max_tokens": False,
                                "reject_batch": False,
                                "reject_standard": False,
                            },
                        },
                    },
                },
            }

    monkeypatch.setattr(routes, "ConfigLoader", DisabledOllamaConfigLoader)

    response = client.post(
        "/generate",
        json={
            "user_id": "user_vip_01",
            "project_id": "vip_project",
            "model": "ollama-llama",
            "prompt": "hello",
            "max_tokens": 64,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "model_disabled"
