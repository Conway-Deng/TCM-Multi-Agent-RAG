from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any

from tcm.schemas import UserContext

from ..schemas import AgentClaim, AgentEvidence, AgentOutput, Domain, SourceType
from .base import FixtureDisabledError


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "west_agent_outputs.json"
FIXTURE_LIMITATION = "Synthetic Western Medicine fixture for orchestration testing only."


def fixture_enabled() -> bool:
    return os.getenv("ALLOW_WEST_FIXTURE", "false").strip().casefold() in {"1", "true", "yes", "on"}


class WestFixtureAdapter:
    def __init__(self, *, allow_fixture: bool | None = None) -> None:
        self.allow_fixture = fixture_enabled() if allow_fixture is None else allow_fixture

    def _load(self) -> list[dict[str, Any]]:
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not data:
            raise ValueError("Western fixture file is empty or invalid")
        return data

    @staticmethod
    def _select(question: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
        lowered = question.casefold()
        deliberate = next((case for case in cases if case.get("case_id") == "deliberate_conflict"), None)
        if deliberate and any(str(keyword).casefold() in lowered for keyword in deliberate.get("keywords", [])):
            return deliberate
        ranked = sorted(
            cases,
            key=lambda case: sum(1 for keyword in case.get("keywords", []) if str(keyword).casefold() in lowered),
            reverse=True,
        )
        if ranked and any(str(keyword).casefold() in lowered for keyword in ranked[0].get("keywords", [])):
            return ranked[0]
        return next((case for case in cases if case.get("case_id") == "insufficient_information"), cases[0])

    async def run(self, question: str, context: UserContext) -> AgentOutput:
        del context
        if not self.allow_fixture:
            raise FixtureDisabledError("Western fixture use is disabled. Set ALLOW_WEST_FIXTURE=true only for local research testing.")
        started = time.perf_counter()
        case = self._select(question, self._load())
        evidence = [AgentEvidence.model_validate(item) for item in case.get("evidence", [])]
        claims = [AgentClaim.model_validate(item) for item in case.get("claims", [])]
        limitations = [FIXTURE_LIMITATION, *case.get("limitations", [])]
        return AgentOutput(
            agent_id="western_fixture_agent",
            domain=Domain.WESTERN,
            source_type=SourceType.FIXTURE,
            experimental=True,
            summary=str(case.get("summary", "")),
            claims=claims,
            evidence=evidence,
            confidence=float(case.get("confidence", 0.3)),
            limitations=list(dict.fromkeys(limitations)),
            safety_flags=list(case.get("safety_flags", [])),
            urgent=bool(case.get("urgent", False)),
            abstained=bool(case.get("abstained", False)),
            scope_status=str(case.get("scope_status", "supported")),
            generation_source="fixture",
            model="synthetic_fixture_v1",
            latency_ms=round((time.perf_counter() - started) * 1000),
            metadata={
                "fixture_case_id": case.get("case_id"),
                "fixture_notice": FIXTURE_LIMITATION,
                "not_clinically_verified": True,
            },
        )
