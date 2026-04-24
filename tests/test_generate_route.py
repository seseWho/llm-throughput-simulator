from fastapi.testclient import TestClient

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
