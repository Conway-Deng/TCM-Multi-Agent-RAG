from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from schemas.research import ResearchRunResult


class SQLiteRunRepository:
    """Optional structured local storage with schema versioning and no raw-query column."""

    schema_version = "1.0.0"

    def __init__(self, path: Path) -> None:
        self.path = path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, condition_id TEXT NOT NULL, payload_json TEXT NOT NULL)")
            connection.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)", (self.schema_version,))

    def save(self, result: ResearchRunResult) -> None:
        payload = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
        timestamp = result.trace.timestamp if result.trace else "unknown"
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO runs(run_id, created_at, condition_id, payload_json) VALUES(?, ?, ?, ?)",
                (result.run_id, timestamp, result.condition_id.value, payload),
            )

    def load(self, run_id: str) -> ResearchRunResult | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return ResearchRunResult.model_validate_json(row[0]) if row else None
