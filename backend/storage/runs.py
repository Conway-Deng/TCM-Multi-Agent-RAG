from __future__ import annotations

import json
from pathlib import Path

from schemas.research import ResearchRunResult


class RunRepository:
    """Schema-versioned JSON storage; raw questions are excluded unless explicitly opted in."""

    schema_version = "1.0.0"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root

    def save(self, result: ResearchRunResult, *, raw_question: str | None = None) -> Path | None:
        if self.root is None:
            return None
        target = self.root / result.run_id
        target.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": self.schema_version, "result": result.model_dump(mode="json")}
        if raw_question is not None:
            payload["raw_question"] = raw_question
        path = target / "run.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, run_id: str) -> ResearchRunResult | None:
        if self.root is None:
            return None
        path = self.root / run_id / "run.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ResearchRunResult.model_validate(data["result"])
