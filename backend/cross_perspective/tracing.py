from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import Protocol

from .schemas import CrossPerspectiveTrace


DEFAULT_TRACE_PATH = Path(__file__).resolve().parent / "runtime" / "consultations.jsonl"


class TraceSink(Protocol):
    def write(self, trace: CrossPerspectiveTrace) -> None: ...


class DevelopmentTraceLogger:
    """Append-only local JSONL logging; the runtime directory is Git-ignored."""

    _lock = Lock()

    def __init__(self, path: Path | None = None) -> None:
        configured = os.getenv("CROSS_PERSPECTIVE_TRACE_PATH", "").strip()
        self.path = path or (Path(configured) if configured else DEFAULT_TRACE_PATH)

    def write(self, trace: CrossPerspectiveTrace) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = trace.model_dump_json(exclude_none=False)
        with self._lock, self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
