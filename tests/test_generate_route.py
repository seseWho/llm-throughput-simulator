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
