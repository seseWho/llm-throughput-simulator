import sqlite3

from backend.persistence.database import init_db
from backend.persistence.usage_repository import UsageRepository


def test_init_db_creates_usage_records_table(tmp_path) -> None:
    db_path = tmp_path / "usage.db"

    init_db(db_path)

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'usage_records'"
        ).fetchone()

    assert row is not None


def test_usage_repository_can_create_record(tmp_path) -> None:
    repository = UsageRepository(tmp_path / "usage.db")

    repository.create_record(**_record())

    records = repository.get_recent_records()
    assert len(records) == 1
    assert records[0]["request_id"] == "request-1"


def test_usage_repository_can_update_status(tmp_path) -> None:
    repository = UsageRepository(tmp_path / "usage.db")
    repository.create_record(**_record())

    repository.update_status("request-1", "processing")

    records = repository.get_recent_records()
    assert records[0]["status"] == "processing"


def test_usage_repository_can_record_completion(tmp_path) -> None:
    repository = UsageRepository(tmp_path / "usage.db")
    repository.create_record(**_record())

    repository.record_completion(
        "request-1",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        estimated_cost_eur=0.01,
        latency_seconds=0.5,
    )

    records = repository.get_recent_records()
    assert records[0]["status"] == "completed"
    assert records[0]["total_tokens"] == 30


def test_usage_repository_can_record_failure(tmp_path) -> None:
    repository = UsageRepository(tmp_path / "usage.db")
    repository.create_record(**_record())

    repository.record_failure("request-1", "failed for test")

    records = repository.get_recent_records()
    assert records[0]["status"] == "failed"
    assert records[0]["error_message"] == "failed for test"


def test_usage_repository_summary_returns_totals(tmp_path) -> None:
    repository = UsageRepository(tmp_path / "usage.db")
    repository.create_record(**_record())
    repository.create_record(
        **(
            _record()
            | {
                "request_id": "request-2",
                "user_id": "user_vip_01",
                "project_id": "vip_project",
                "model": "ollama-llama",
                "backend": "ollama",
                "input_tokens": 5,
                "output_tokens": 15,
                "total_tokens": 20,
                "estimated_cost_eur": 0.02,
            }
        )
    )

    summary = repository.get_summary()

    assert summary["total_records"] == 2
    assert summary["total_input_tokens"] == 15
    assert summary["total_output_tokens"] == 35
    assert summary["total_tokens"] == 50
    assert summary["total_estimated_cost_eur"] == 0.03
    assert summary["records_by_backend"] == {"ollama": 1, "simulated": 1}


def test_usage_repository_project_summary_filters_by_project_id(tmp_path) -> None:
    repository = UsageRepository(tmp_path / "usage.db")
    repository.create_record(**_record())
    repository.create_record(**(_record() | {"request_id": "request-2", "project_id": "vip_project"}))

    summary = repository.get_project_summary("standard_project")

    assert summary["total_records"] == 1
    assert summary["records_by_project"] == {"standard_project": 1}


def test_usage_repository_user_summary_filters_by_user_id(tmp_path) -> None:
    repository = UsageRepository(tmp_path / "usage.db")
    repository.create_record(**_record())
    repository.create_record(**(_record() | {"request_id": "request-2", "user_id": "user_vip_01"}))

    summary = repository.get_user_summary("user_standard_01")

    assert summary["total_records"] == 1
    assert summary["records_by_user"] == {"user_standard_01": 1}


def test_usage_repository_recent_records_returns_recent_rows(tmp_path) -> None:
    repository = UsageRepository(tmp_path / "usage.db")
    repository.create_record(**_record())
    repository.create_record(**(_record() | {"request_id": "request-2"}))

    records = repository.get_recent_records(limit=1)

    assert len(records) == 1
    assert records[0]["request_id"] == "request-2"


def _record() -> dict:
    return {
        "request_id": "request-1",
        "user_id": "user_standard_01",
        "project_id": "standard_project",
        "model": "simulated-small",
        "backend": "simulated",
        "request_type": "interactive",
        "priority": "normal",
        "status": "completed",
        "decision": "accept",
        "degradation_level": "normal",
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "estimated_cost_eur": 0.01,
        "latency_seconds": 0.5,
        "queue_wait_seconds": 0.0,
        "error_message": None,
    }
