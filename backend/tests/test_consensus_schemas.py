from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ["LLM_API_KEY"] = ""

from consensus.adapters.west_fixture_adapter import FIXTURE_LIMITATION, WestFixtureAdapter
from consensus.adapters.tcm_adapter import TCMAdapter
from consensus.schemas import AgentOutput
from tcm.schemas import UserContext


def test_agent_output_schema_accepts_local_rag() -> None:
    output = AgentOutput(
        agent_id="tcm_agent",
        domain="tcm",
        source_type="local_rag",
        summary="Educational summary",
    )
    assert output.source_type.value == "local_rag"


def test_fixture_requires_explicit_fixture_limitation() -> None:
    with pytest.raises(ValidationError):
        AgentOutput(
            agent_id="west",
            domain="western",
            source_type="fixture",
            summary="Synthetic",
            limitations=["No live retrieval."],
        )


def test_fixture_adapter_is_always_fixture_and_experimental() -> None:
    result = asyncio.run(WestFixtureAdapter(allow_fixture=True).run("I have trouble sleeping", UserContext()))
    assert result.source_type.value == "fixture"
    assert result.experimental is True
    assert FIXTURE_LIMITATION in result.limitations
    assert result.metadata["not_clinically_verified"] is True


def test_fixture_adapter_abstains_for_unmatched_case() -> None:
    result = asyncio.run(WestFixtureAdapter(allow_fixture=True).run("an unrelated description", UserContext()))
    assert result.abstained is True
    assert result.scope_status == "insufficient_information"


def test_tcm_adapter_preserves_evidence_scope_and_generation_metadata() -> None:
    result = asyncio.run(TCMAdapter().run("我有点失眠，最近腰酸", UserContext()))
    assert result.source_type.value == "local_rag"
    assert result.scope_status == "supported"
    assert result.generation_source == "mock_fallback"
    assert result.evidence
    evidence_ids = {item.evidence_id for item in result.evidence}
    assert all(evidence_id in evidence_ids for claim in result.claims for evidence_id in claim.evidence_ids)
    assert result.metadata["citations"]


def test_tcm_adapter_preserves_deterministic_urgent_safety() -> None:
    result = asyncio.run(TCMAdapter().run("我胸口剧痛而且呼吸困难", UserContext()))
    assert result.urgent is True
    assert result.abstained is True
    assert result.generation_source == "safety_rule"
    assert "deterministic_tcm_urgent_rule" in result.safety_flags
