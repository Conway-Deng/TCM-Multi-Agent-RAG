from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


APP_ROOT = Path(__file__).resolve().parents[2]


class FormalJobStore:
    """Durable queue/results store shared by the control plane and worker."""

    def __init__(self, database_url: str | None = None) -> None:
        configured = database_url or os.getenv("FORMAL_DATABASE_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()
        self._pool = None
        if configured.startswith(("postgres://", "postgresql://")):
            self.kind = "postgres"
            self.database_url = configured
        else:
            self.kind = "sqlite"
            default_path = Path(os.getenv("FORMAL_JOB_DB", "research/replays/formal_jobs.sqlite3"))
            path = Path(configured.removeprefix("sqlite:///")) if configured.startswith("sqlite:///") else default_path
            self.path = (path if path.is_absolute() else APP_ROOT / path).resolve()
            self.database_url = f"sqlite:///{self.path.as_posix()}"
        self._initialized = False

    def _postgres_pool(self):
        if self._pool is None:
            try:
                from psycopg_pool import ConnectionPool
            except ImportError as exc:  # pragma: no cover - deployed PostgreSQL only
                raise RuntimeError("psycopg_pool is required when FORMAL_DATABASE_URL uses PostgreSQL") from exc
            self._pool = ConnectionPool(
                conninfo=self.database_url,
                min_size=0,
                max_size=max(1, int(os.getenv("FORMAL_DATABASE_POOL_SIZE", "4"))),
                open=True,
                check=ConnectionPool.check_connection,
            )
        return self._pool

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.kind == "postgres":
            with self._postgres_pool().connection() as connection:
                try:
                    yield connection
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    def _sql(self, value: str) -> str:
        return value.replace("?", "%s") if self.kind == "postgres" else value

    def initialize(self) -> None:
        if self._initialized:
            return
        blob = "BYTEA" if self.kind == "postgres" else "BLOB"
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS formal_jobs (
                    run_id TEXT PRIMARY KEY,
                    job_kind TEXT NOT NULL DEFAULT 'formal',
                    experiment_id TEXT NOT NULL,
                    run_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    completed INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    current_stage TEXT,
                    current_condition TEXT,
                    current_case TEXT,
                    successful INTEGER NOT NULL,
                    failed INTEGER NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL,
                    started_at DOUBLE PRECISION,
                    updated_at DOUBLE PRECISION NOT NULL,
                    resume_state TEXT NOT NULL,
                    replay_output_dir TEXT NOT NULL,
                    persistence TEXT NOT NULL,
                    error TEXT,
                    request_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    worker_id TEXT,
                    lease_until DOUBLE PRECISION
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS formal_executions (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    case_id TEXT,
                    condition_id TEXT,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence)
                )
            """)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS formal_artifacts (
                    run_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    media_type TEXT NOT NULL,
                    content {blob} NOT NULL,
                    PRIMARY KEY (run_id, path)
                )
            """)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS formal_checkpoints (
                    run_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    content {blob} NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (run_id, path)
                )
            """)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS formal_checkpoint_chunks (
                    run_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    chunk_start INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    content {blob} NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (run_id, path, chunk_start)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS formal_jobs_queue_idx ON formal_jobs (status, created_at)")
        self._initialized = True

    @staticmethod
    def _row(row: Any, columns: list[str] | None = None) -> dict[str, Any]:
        if hasattr(row, "keys"):
            return dict(row)
        return dict(zip(columns or [], row))

    def create(self, job: dict[str, Any], request: dict[str, Any], metadata: dict[str, Any]) -> None:
        self.initialize()
        job = {"job_kind": "formal", "current_stage": "queued", **job}
        columns = [
            "run_id", "job_kind", "experiment_id", "run_mode", "status", "completed", "total",
            "current_stage", "current_condition", "current_case", "successful", "failed", "created_at",
            "started_at", "updated_at", "resume_state", "replay_output_dir", "persistence",
            "error", "request_json", "metadata_json", "worker_id", "lease_until",
        ]
        values = [job.get(column) for column in columns[:-4]] + [
            json.dumps(request, ensure_ascii=False), json.dumps(metadata, ensure_ascii=False), None, None,
        ]
        with self.connect() as connection:
            connection.cursor().execute(
                self._sql(f"INSERT INTO formal_jobs ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})"),
                values,
            )

    def get(self, run_id: str) -> dict[str, Any]:
        self.initialize()
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(self._sql("SELECT * FROM formal_jobs WHERE run_id = ?"), (run_id,))
            row = cursor.fetchone()
            if row is None:
                raise KeyError(run_id)
            columns = [item[0] for item in cursor.description]
        value = self._row(row, columns)
        value["request"] = json.loads(value.pop("request_json"))
        value["metadata"] = json.loads(value.pop("metadata_json"))
        value["elapsed_seconds"] = round(time.time() - (value.get("started_at") or value["created_at"]), 3)
        return value

    def update(self, run_id: str, **values: Any) -> None:
        if not values:
            return
        self.initialize()
        values["updated_at"] = time.time()
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self.connect() as connection:
            connection.cursor().execute(self._sql(f"UPDATE formal_jobs SET {assignments} WHERE run_id = ?"), (*values.values(), run_id))

    def claim_next(self, worker_id: str, lease_seconds: int = 120) -> dict[str, Any] | None:
        self.initialize()
        now = time.time()
        with self.connect() as connection:
            cursor = connection.cursor()
            if self.kind == "sqlite":
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute("SELECT run_id FROM formal_jobs WHERE status = 'queued' OR (status = 'running' AND lease_until < ?) ORDER BY created_at LIMIT 1", (now,))
            else:  # pragma: no cover - deployed PostgreSQL
                cursor.execute("SELECT run_id FROM formal_jobs WHERE status = 'queued' OR (status = 'running' AND lease_until < %s) ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1", (now,))
            row = cursor.fetchone()
            if row is None:
                return None
            run_id = row[0]
            cursor.execute(
                self._sql("UPDATE formal_jobs SET status = 'running', resume_state = 'running', worker_id = ?, lease_until = ?, started_at = COALESCE(started_at, ?), updated_at = ? WHERE run_id = ?"),
                (worker_id, now + lease_seconds, now, now, run_id),
            )
        return self.get(run_id)

    def heartbeat(self, run_id: str, worker_id: str, lease_seconds: int = 120, **values: Any) -> None:
        values.update(worker_id=worker_id, lease_until=time.time() + lease_seconds)
        self.update(run_id, **values)

    def request_resume(self, run_id: str) -> dict[str, Any]:
        job = self.get(run_id)
        if job["status"] != "failed":
            raise ValueError("Only a failed replay job can be resumed")
        self.update(run_id, status="queued", resume_state="queued", error=None, worker_id=None, lease_until=None)
        return self.get(run_id)

    @staticmethod
    def _execution_values(row: dict[str, Any]) -> tuple[str | None, str | None, str]:
        case_id = row.get("case_id", row.get("question_id"))
        condition = row.get("condition", row.get("condition_id"))
        if "usable" in row:
            passed = bool(row["usable"])
        elif "run_status" in row:
            passed = row["run_status"] in {"PASS", "PASS_WITH_RETRY"}
        else:
            passed = not bool(row.get("error"))
        return case_id, condition, "Completed" if passed else "Failed"

    def upsert_execution(self, run_id: str, sequence: int, row: dict[str, Any]) -> None:
        self.initialize()
        case_id, condition, status = self._execution_values(row)
        if self.kind == "postgres":  # pragma: no cover - deployed PostgreSQL
            sql = "INSERT INTO formal_executions (run_id,sequence,case_id,condition_id,status,payload_json) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (run_id,sequence) DO UPDATE SET case_id=EXCLUDED.case_id,condition_id=EXCLUDED.condition_id,status=EXCLUDED.status,payload_json=EXCLUDED.payload_json"
        else:
            sql = "INSERT INTO formal_executions (run_id,sequence,case_id,condition_id,status,payload_json) VALUES (?,?,?,?,?,?) ON CONFLICT(run_id,sequence) DO UPDATE SET case_id=excluded.case_id,condition_id=excluded.condition_id,status=excluded.status,payload_json=excluded.payload_json"
        with self.connect() as connection:
            connection.cursor().execute(sql, (run_id, sequence, case_id, condition, status, json.dumps(row, ensure_ascii=False)))

    def replace_executions(self, run_id: str, rows: list[dict[str, Any]]) -> None:
        self.initialize()
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(self._sql("SELECT COALESCE(MAX(sequence), 0) FROM formal_executions WHERE run_id = ?"), (run_id,))
            persisted = int(cursor.fetchone()[0])
            for sequence, row in enumerate(rows[persisted:], start=persisted + 1):
                case_id, condition, status = self._execution_values(row)
                if self.kind == "postgres":  # pragma: no cover - deployed PostgreSQL
                    sql = "INSERT INTO formal_executions (run_id,sequence,case_id,condition_id,status,payload_json) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (run_id,sequence) DO UPDATE SET case_id=EXCLUDED.case_id,condition_id=EXCLUDED.condition_id,status=EXCLUDED.status,payload_json=EXCLUDED.payload_json"
                else:
                    sql = "INSERT INTO formal_executions (run_id,sequence,case_id,condition_id,status,payload_json) VALUES (?,?,?,?,?,?) ON CONFLICT(run_id,sequence) DO UPDATE SET case_id=excluded.case_id,condition_id=excluded.condition_id,status=excluded.status,payload_json=excluded.payload_json"
                cursor.execute(sql, (run_id, sequence, case_id, condition, status, json.dumps(row, ensure_ascii=False)))

    def executions(self, run_id: str, after: int = 0, *, include_payload: bool = False) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(self._sql("SELECT sequence, case_id, condition_id, status, payload_json FROM formal_executions WHERE run_id = ? AND sequence > ? ORDER BY sequence"), (run_id, after))
            rows = cursor.fetchall()
        values = []
        for row in rows:
            value = {"sequence": row[0], "case_id": row[1], "condition": row[2], "status": row[3]}
            if include_payload:
                value["result"] = json.loads(row[4])
            values.append(value)
        return values

    @staticmethod
    def _media_type(path: str) -> str:
        suffix = Path(path).suffix.casefold()
        return "application/json" if suffix in {".json", ".jsonl"} else "text/csv" if suffix == ".csv" else "text/markdown" if suffix == ".md" else "application/octet-stream"

    def store_artifact_bytes(self, run_id: str, path: str, content: bytes, media_type: str | None = None) -> None:
        self.initialize()
        if path.startswith("/") or ".." in Path(path).parts or re.match(r"^[A-Za-z]:", path):
            raise ValueError("Invalid artifact path")
        if self.kind == "postgres":  # pragma: no cover - deployed PostgreSQL
            sql = "INSERT INTO formal_artifacts (run_id,path,size,media_type,content) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (run_id,path) DO UPDATE SET size=EXCLUDED.size,media_type=EXCLUDED.media_type,content=EXCLUDED.content"
        else:
            sql = "INSERT INTO formal_artifacts (run_id,path,size,media_type,content) VALUES (?,?,?,?,?) ON CONFLICT(run_id,path) DO UPDATE SET size=excluded.size,media_type=excluded.media_type,content=excluded.content"
        with self.connect() as connection:
            connection.cursor().execute(sql, (run_id, path, len(content), media_type or self._media_type(path), content))

    def store_artifacts(self, run_id: str, output: Path) -> None:
        for path in output.rglob("*"):
            relative_parts = path.relative_to(output).parts
            if not path.is_file() or path.name in {"worker.stdout.log", "worker.stderr.log"} or any(part in {"cache", "logs"} for part in relative_parts):
                continue
            relative = str(path.relative_to(output)).replace("\\", "/")
            self.store_artifact_bytes(run_id, relative, path.read_bytes())

    @staticmethod
    def _checkpoint_bytes(path: Path) -> bytes | None:
        try:
            content = path.read_bytes()
            text = content.decode("utf-8") if path.suffix.casefold() in {".json", ".jsonl"} else None
            if path.suffix.casefold() == ".json":
                json.loads(text or "")
            elif path.suffix.casefold() == ".jsonl":
                for line in (text or "").splitlines():
                    if line.strip():
                        json.loads(line)
            return content
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None

    def store_checkpoints(
        self,
        run_id: str,
        output: Path,
        known_files: dict[str, tuple[int, int, str]] | None = None,
    ) -> int:
        """Persist a consistent disposable-workspace snapshot for restart/resume."""
        self.initialize()
        stored = 0
        with self.connect() as connection:
            cursor = connection.cursor()
            for path in output.rglob("*"):
                if not path.is_file() or path.suffix == ".tmp" or any(part == "logs" for part in path.relative_to(output).parts):
                    continue
                relative = str(path.relative_to(output)).replace("\\", "/")
                try:
                    stat = path.stat()
                except OSError:
                    continue
                cached = known_files.get(relative) if known_files is not None else None
                if cached is not None and cached[:2] == (stat.st_mtime_ns, stat.st_size):
                    continue
                content = self._checkpoint_bytes(path)
                if content is None:
                    continue
                digest = hashlib.sha256(content).hexdigest()
                if path.suffix.casefold() == ".jsonl":
                    cursor.execute(
                        self._sql("SELECT COALESCE(SUM(size), 0) FROM formal_checkpoint_chunks WHERE run_id = ? AND path = ?"),
                        (run_id, relative),
                    )
                    stored_size = int(cursor.fetchone()[0])
                    if stored_size > len(content):
                        cursor.execute(self._sql("DELETE FROM formal_checkpoint_chunks WHERE run_id = ? AND path = ?"), (run_id, relative))
                        stored_size = 0
                    if stored_size < len(content):
                        chunk = content[stored_size:]
                        cursor.execute(
                            self._sql("INSERT INTO formal_checkpoint_chunks (run_id,path,chunk_start,size,content,updated_at) VALUES (?,?,?,?,?,?)"),
                            (run_id, relative, stored_size, len(chunk), chunk, time.time()),
                        )
                elif self.kind == "postgres":  # pragma: no cover - deployed PostgreSQL
                    sql = "INSERT INTO formal_checkpoints (run_id,path,size,sha256,content,updated_at) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (run_id,path) DO UPDATE SET size=EXCLUDED.size,sha256=EXCLUDED.sha256,content=EXCLUDED.content,updated_at=EXCLUDED.updated_at WHERE formal_checkpoints.sha256 <> EXCLUDED.sha256"
                    cursor.execute(sql, (run_id, relative, len(content), digest, content, time.time()))
                else:
                    sql = "INSERT INTO formal_checkpoints (run_id,path,size,sha256,content,updated_at) VALUES (?,?,?,?,?,?) ON CONFLICT(run_id,path) DO UPDATE SET size=excluded.size,sha256=excluded.sha256,content=excluded.content,updated_at=excluded.updated_at WHERE formal_checkpoints.sha256 <> excluded.sha256"
                    cursor.execute(sql, (run_id, relative, len(content), digest, content, time.time()))
                if known_files is not None:
                    known_files[relative] = (stat.st_mtime_ns, stat.st_size, digest)
                stored += 1
        return stored

    def restore_checkpoints(self, run_id: str, output: Path) -> int:
        self.initialize()
        root = output.resolve()
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(self._sql("SELECT path, content FROM formal_checkpoints WHERE run_id = ? ORDER BY path"), (run_id,))
            rows = cursor.fetchall()
            cursor.execute(self._sql("SELECT path, chunk_start, content FROM formal_checkpoint_chunks WHERE run_id = ? ORDER BY path, chunk_start"), (run_id,))
            chunk_rows = cursor.fetchall()
        for relative, content in rows:
            path = (root / relative).resolve()
            if root != path and root not in path.parents:
                raise ValueError("Checkpoint path escapes disposable workspace")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(bytes(content))
        chunk_paths: set[str] = set()
        for relative, chunk_start, content in chunk_rows:
            path = (root / relative).resolve()
            if root != path and root not in path.parents:
                raise ValueError("Checkpoint path escapes disposable workspace")
            path.parent.mkdir(parents=True, exist_ok=True)
            start = int(chunk_start)
            current_size = path.stat().st_size if path.exists() else 0
            if current_size != start:
                raise ValueError("Checkpoint chunks are not contiguous")
            mode = "wb" if start == 0 else "ab"
            with path.open(mode) as handle:
                handle.write(bytes(content))
            chunk_paths.add(relative)
        return len(rows) + len(chunk_paths)

    def delete_checkpoints(self, run_id: str) -> None:
        self.initialize()
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(self._sql("DELETE FROM formal_checkpoints WHERE run_id = ?"), (run_id,))
            cursor.execute(self._sql("DELETE FROM formal_checkpoint_chunks WHERE run_id = ?"), (run_id,))

    def artifacts(self, run_id: str) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(self._sql("SELECT path, size FROM formal_artifacts WHERE run_id = ? ORDER BY path"), (run_id,))
            return [{"name": row[0], "size": row[1]} for row in cursor.fetchall()]

    def artifact(self, run_id: str, path: str) -> tuple[str, bytes]:
        self.initialize()
        if path.startswith("/") or ".." in Path(path).parts or re.match(r"^[A-Za-z]:", path):
            raise ValueError("Replay file not found")
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(self._sql("SELECT media_type, content FROM formal_artifacts WHERE run_id = ? AND path = ?"), (run_id, path))
            row = cursor.fetchone()
        if row is None:
            raise ValueError("Replay file not found")
        return row[0], bytes(row[1])

    def final_metrics(self, run_id: str) -> dict[str, Any]:
        markers = ("objective_metrics", "final_results", "paired_statistics", "statistics", "summary")
        summaries: dict[str, Any] = {}
        for item in self.artifacts(run_id):
            name = item["name"]
            if not name.casefold().endswith(".json") or not any(marker in name.casefold() for marker in markers):
                continue
            _, content = self.artifact(run_id, name)
            try:
                summaries[name] = json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        return summaries

    def active_count(self) -> int:
        self.initialize()
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM formal_jobs WHERE status IN ('queued', 'running')")
            return int(cursor.fetchone()[0])

    def queue_summary(self) -> dict[str, int]:
        self.initialize()
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT status, COUNT(*) FROM formal_jobs GROUP BY status")
            values = {str(row[0]): int(row[1]) for row in cursor.fetchall()}
        return {"queued": values.get("queued", 0), "running": values.get("running", 0)}

    def cleanup_old_replays(self, retention_days: int) -> int:
        """Delete old generated jobs only; frozen historical outputs never enter this database."""
        if retention_days <= 0:
            return 0
        self.initialize()
        cutoff = time.time() - retention_days * 86400
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(self._sql("SELECT run_id FROM formal_jobs WHERE status IN ('complete', 'failed') AND updated_at < ?"), (cutoff,))
            run_ids = [row[0] for row in cursor.fetchall()]
            for run_id in run_ids:
                for table in ("formal_executions", "formal_artifacts", "formal_checkpoints", "formal_checkpoint_chunks"):
                    cursor.execute(self._sql(f"DELETE FROM {table} WHERE run_id = ?"), (run_id,))
                cursor.execute(self._sql("DELETE FROM formal_jobs WHERE run_id = ?"), (run_id,))
        return len(run_ids)
