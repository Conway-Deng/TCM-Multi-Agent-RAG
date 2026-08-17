from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from agents import build_agents
from orchestration.workbench import _agent_prompt, _claim_with_citations, _synthesis
from providers.openai_compatible import _chat_payload, _extract_chat_content
from providers.output_quality import runaway_output_reason
from schemas.research import DebateTrace, ResearchAgentOutput, StructuredClaim


def test_non_streaming_payload_and_response_content_are_extracted_once() -> None:
    payload = _chat_payload(
        model="test-model",
        system="system",
        prompt="prompt",
        temperature=0.0,
        max_tokens=384,
        frequency_penalty=0.5,
    )
    assert payload["stream"] is False
    assert payload["max_tokens"] == 384
    assert payload["frequency_penalty"] == 0.5
    assert _extract_chat_content({"choices": [{"message": {"content": "one complete response"}}]}) == "one complete response"
    with pytest.raises(TypeError):
        _extract_chat_content({"choices": [{"message": {"content": {"text": "not a string"}}}]})


def test_evidence_prompt_is_clean_and_leaves_provenance_to_backend() -> None:
    agent = build_agents(["herbal"])[0]
    baseline = ResearchAgentOutput(
        agent_id="herbal",
        agent_name="Herbal Knowledge Agent",
        agent_version="test",
        question="What is Red Ginseng?",
        language="en",
        subdomain="herbal medicine",
        evidence_ids=["tcmv1-example"],
    )
    evidence = [type("Evidence", (), {
        "chunk_id": "tcmv1-example",
        "source_id": "symmap_v2",
        "chunk_text": "Red Ginseng is source-reported as sweet and slightly bitter.",
    })()]
    system, prompt = _agent_prompt(agent, "What is Red Ginseng?", "en", baseline, evidence)
    decoded = json.loads(prompt)
    assert decoded["evidence"] == [{"label": "Evidence 1", "text": evidence[0].chunk_text}]
    assert "tcmv1-example" not in prompt
    assert "symmap_v2" not in prompt
    assert "do not emit citations" in system


def test_citations_are_added_exactly_once() -> None:
    text = "Source-constrained specialist summary."
    assert _claim_with_citations(text, ["chunk-a", "chunk-b"]) == f"{text} [chunk-a] [chunk-b]"
    assert _claim_with_citations(f"{text} [chunk-a]", ["chunk-a", "chunk-b"]) == f"{text} [chunk-a] [chunk-b]"


def test_runaway_output_is_rejected_without_rewriting_content() -> None:
    assert runaway_output_reason("Red Ginseng is traditionally described as sweet and slightly bitter.") is None
    assert runaway_output_reason("Red Ginseng is traditionally slightly slightly bitter and used to reinforce qi.") == "consecutive repeated token"
    repeated = " ".join(["spleen lung kidney"] * 5)
    assert runaway_output_reason(repeated + ".") == "repeated phrase pattern"
    assert runaway_output_reason("Red Ginseng is used classified as reinforcing qi") == "incomplete paragraph"
    assert runaway_output_reason("Red Ginseng is knownR. ginseng and is traditionally described as warm.") == "malformed token spacing"
    assert runaway_output_reason("Red Ginseng is traditionally described as warm,, sweet, and slightly bitter.") == "malformed repeated punctuation"


def test_normal_c1_c2_synthesis_serializes_cleanly() -> None:
    claim = StructuredClaim(
        claim_id="claim-a",
        text="Red Ginseng is traditionally described as warm, sweet, and slightly bitter.",
        confidence=0.6,
        evidence_ids=["chunk-a"],
    )
    output = ResearchAgentOutput(
        agent_id="herbal",
        agent_name="Herbal Knowledge Agent",
        agent_version="test",
        question="What is Red Ginseng?",
        language="en",
        subdomain="herbal medicine",
        claims=[claim],
        evidence_ids=["chunk-a"],
        confidence=0.6,
    )
    independent = {"aggregation": "independent"}
    direct = {"aggregation": "direct"}
    c2, _, _, _ = _synthesis([output], independent, DebateTrace(), [])
    c1, _, _, _ = _synthesis([output], direct, DebateTrace(), [])
    assert c2.count("[chunk-a]") == 1
    assert c1.count("[chunk-a]") == 1
    assert runaway_output_reason(claim.text) is None
    assert "slightly slightly" not in c1
    assert "slightly slightly" not in c2
