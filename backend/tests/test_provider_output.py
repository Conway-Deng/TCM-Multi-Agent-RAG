from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from agents import build_agents
from orchestration.workbench import _agent_prompt, _claim_with_citations, _synthesis
from providers.openai_compatible import OpenAICompatibleLLMProvider, _chat_payload, _extract_chat_content, _extract_finish_reason
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
    assert "enable_thinking" not in payload
    assert payload["max_tokens"] == 384
    assert payload["frequency_penalty"] == 0.5
    assert _extract_chat_content({"choices": [{"message": {"content": "one complete response"}}]}) == "one complete response"
    assert _extract_finish_reason({"choices": [{"message": {"content": "one complete response"}, "finish_reason": "stop"}]}) == "stop"
    assert _extract_finish_reason({"choices": [{"message": {"content": "one complete response"}}]}) is None
    with pytest.raises(TypeError):
        _extract_chat_content({"choices": [{"message": {"content": {"text": "not a string"}}}]})

    qwen3_payload = _chat_payload(
        model="Qwen/Qwen3-8B",
        system="system",
        prompt="prompt",
        temperature=0.0,
        max_tokens=384,
        frequency_penalty=0.5,
    )
    assert qwen3_payload["enable_thinking"] is False


def test_provider_generation_captures_finish_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": "A complete provider response."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 5},
            }

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *_, **__) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("providers.openai_compatible.httpx.AsyncClient", FakeClient)
    provider = OpenAICompatibleLLMProvider(
        api_key="unit-test-placeholder",
        base_url="https://api.siliconflow.cn/v1",
        model="Qwen/Qwen3-8B",
        timeout=45,
        max_tokens=1400,
        provider_name="siliconflow",
    )
    result = asyncio.run(provider.generate(system="system", prompt="prompt"))
    assert result.finish_reason == "stop"
    assert result.metadata["finish_reason"] == "stop"


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
    system, prompt, prompt_evidence_ids = _agent_prompt(agent, "What is Red Ginseng?", "en", baseline, evidence, None)
    decoded = json.loads(prompt)
    assert decoded["evidence"] == [{"label": "Evidence 1", "text": evidence[0].chunk_text}]
    assert "tcmv1-example" not in prompt
    assert prompt_evidence_ids == ["tcmv1-example"]
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
    assert runaway_output_reason("Red Ginseng is traditionally described as warm sweet and slightly bitter", finish_reason="stop") is None
    assert runaway_output_reason("Red Ginseng is traditionally described as warm sweet and slightly bitter", finish_reason="length") == "truncated output (finish_reason=length)"
    assert runaway_output_reason("Red Ginseng is traditionally slightly slightly bitter and used to reinforce qi", finish_reason="stop") == "consecutive repeated token"
    assert runaway_output_reason("Red Ginseng is knownR ginseng and is traditionally described as warm", finish_reason="stop") == "malformed token spacing"


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
