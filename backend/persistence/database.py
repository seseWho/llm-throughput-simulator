import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path("data") / "usage.db"


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Return a SQLite connection with row dictionaries enabled."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Initialize the usage accounting database."""
    with get_connection(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                user_id TEXT,
                project_id TEXT,
                model TEXT,
                backend TEXT,
                request_type TEXT,
                priority TEXT,
                status TEXT,
                decision TEXT,
                degradation_level TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                total_tokens INTEGER,
                estimated_cost_eur REAL,
                latency_seconds REAL,
                queue_wait_seconds REAL,
                error_message TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        connection.commit()
