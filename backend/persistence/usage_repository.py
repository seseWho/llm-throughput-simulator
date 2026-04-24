from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.persistence.database import DEFAULT_DB_PATH, get_connection, init_db

USAGE_FIELDS = {
    "request_id",
    "user_id",
    "project_id",
    "model",
    "backend",
    "request_type",
    "priority",
    "status",
    "decision",
    "degradation_level",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "estimated_cost_eur",
    "latency_seconds",
    "queue_wait_seconds",
    "error_message",
    "created_at",
    "updated_at",
}


class UsageRepository:
    """SQLite-backed repository for request usage accounting."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        init_db(self.db_path)

    def create_record(self, **fields: Any) -> None:
        """Create a usage record."""
        now = _now()
        values = _clean_fields(fields | {"created_at": now, "updated_at": now})
        columns = list(values.keys())
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(columns)

        with get_connection(self.db_path) as connection:
            connection.execute(
                f"INSERT INTO usage_records ({column_sql}) VALUES ({placeholders})",
                [values[column] for column in columns],
            )
            connection.commit()

    def update_status(self, request_id: str, status: str, **fields: Any) -> None:
        """Update status and optional fields for a request."""
        values = _clean_fields(fields | {"status": status, "updated_at": _now()})
        assignments = ", ".join(f"{column} = ?" for column in values)

        with get_connection(self.db_path) as connection:
            connection.execute(
                f"UPDATE usage_records SET {assignments} WHERE request_id = ?",
                [*values.values(), request_id],
            )
            connection.commit()

    def record_completion(self, request_id: str, **fields: Any) -> None:
        """Mark a request as completed."""
        self.update_status(request_id, "completed", **fields)

    def record_failure(self, request_id: str, error_message: str, **fields: Any) -> None:
        """Mark a request as failed."""
        self.update_status(request_id, "failed", error_message=error_message, **fields)

    def get_summary(self) -> dict:
        """Return aggregate usage summary."""
        return self._summary()

    def get_project_summary(self, project_id: str) -> dict:
        """Return aggregate usage summary for one project."""
        return self._summary("project_id = ?", [project_id])

    def get_user_summary(self, user_id: str) -> dict:
        """Return aggregate usage summary for one user."""
        return self._summary("user_id = ?", [user_id])

    def get_recent_records(self, limit: int = 50) -> list[dict]:
        """Return recent usage records."""
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                "SELECT * FROM usage_records ORDER BY id DESC LIMIT ?",
                [limit],
            ).fetchall()
        return [dict(row) for row in rows]

    def _summary(self, where_clause: str | None = None, params: list[Any] | None = None) -> dict:
        params = params or []
        where_sql = f" WHERE {where_clause}" if where_clause else ""

        with get_connection(self.db_path) as connection:
            totals = connection.execute(
                f"""
                SELECT
                    COUNT(*) AS total_records,
                    COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    COALESCE(SUM(estimated_cost_eur), 0.0) AS total_estimated_cost_eur
                FROM usage_records
                {where_sql}
                """,
                params,
            ).fetchone()

            return {
                "total_records": int(totals["total_records"]),
                "total_input_tokens": int(totals["total_input_tokens"]),
                "total_output_tokens": int(totals["total_output_tokens"]),
                "total_tokens": int(totals["total_tokens"]),
                "total_estimated_cost_eur": float(totals["total_estimated_cost_eur"]),
                "records_by_status": self._group_count(connection, "status", where_clause, params),
                "records_by_project": self._group_count(connection, "project_id", where_clause, params),
                "records_by_user": self._group_count(connection, "user_id", where_clause, params),
                "records_by_model": self._group_count(connection, "model", where_clause, params),
                "records_by_backend": self._group_count(connection, "backend", where_clause, params),
            }

    def _group_count(
        self,
        connection,
        column: str,
        where_clause: str | None = None,
        params: list[Any] | None = None,
    ) -> dict[str, int]:
        params = params or []
        where_sql = f" WHERE {where_clause}" if where_clause else ""
        rows = connection.execute(
            f"""
            SELECT {column} AS name, COUNT(*) AS count
            FROM usage_records
            {where_sql}
            GROUP BY {column}
            """,
            params,
        ).fetchall()
        return {str(row["name"]): int(row["count"]) for row in rows if row["name"] is not None}


def _clean_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if key in USAGE_FIELDS}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
