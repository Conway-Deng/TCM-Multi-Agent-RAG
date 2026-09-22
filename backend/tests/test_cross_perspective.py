from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cross_perspective.adapters import (
    AdapterOutcome,
    PerspectiveAdapterError,
    TCMEvidenceAdapter,
    WesternEvidenceAdapter,
)
from cross_perspective.governance import (
    CrossPerspectiveGovernanceAgent,
    GOVERNANCE_MAX_TOKENS,
    GOVERNANCE_SYSTEM_PROMPT,
    GOVERNANCE_TIMEOUT_SECONDS,
    build_governance_payload,
    validate_governance_grounding,
)
from cross_perspective.model_calls import StructuredCallResult, StructuredModelCallFailure
from cross_perspective.router import CrossPerspectiveRouter, ROUTER_MODEL
from cross_perspective.schemas import (
    CrossPerspectiveAnswer,
    CrossPerspectiveConsultRequest,
    EvidenceReference,
    ModelCallEvent,
    NUTRITION_UNAVAILABLE_MESSAGE,
    OVERALL_NO_CLAIM_SUMMARY,
    PerspectiveClaim,
    PerspectiveEvidencePacket,
    ProvenanceRecord,
    RoutingDecision,
    TCM_NO_CLAIM_SUMMARY,
    TCM_UNAVAILABLE_SUMMARY,
    WESTERN_NO_CLAIM_SUMMARY,
    WESTERN_UNAVAILABLE_SUMMARY,
)
from cross_perspective.service import CrossPerspectiveService, NutritionUnavailableError
from cross_perspective.tracing import DevelopmentTraceLogger
from providers.base import GenerationResult
from providers.openai_compatible import ProviderUnavailable
from tcm.agent import OpenAICompatibleClient
from schemas.research import ProviderAttempt
from tcm.schemas import Citation, Claim, Confidence, EvidenceChunk, QueryAnalysis, TCMConsultResponse
from western.schemas import (
    WesternClaim,
    WesternConsultResponse,
    WesternRetrievalEvidence,
    WesternTopic,
    WesternTrace,
)


def packet(perspective: str) -> PerspectiveEvidencePacket:
    prefix = "t" if perspective == "tcm" else "w"
    return PerspectiveEvidencePacket(
        perspective=perspective,
        interpretation=f"{perspective} interpretation",
        claims=[
            PerspectiveClaim(
                claim_id=f"{perspective}:c1",
                claim_text=f"{perspective} evidence-bounded claim",
                evidence_refs=[
                    EvidenceReference(
                        source_id=f"{prefix}-source-1",
                        chunk_id=f"{prefix}-chunk-1",
                        title=f"{perspective} source",
                    )
                ],
                support_status="supported",
            )
        ],
        uncertainty=["Pilot evidence is limited."],
        missing_information=[],
        limitations=["Development fixture."],
        provenance=[
            ProvenanceRecord(
                source_id=f"{prefix}-source-1",
                chunk_id=f"{prefix}-chunk-1",
                title=f"{perspective} source",
            )
        ],
    )


def answer(*, western_available: bool = True) -> CrossPerspectiveAnswer:
    overall_summary = "The selected evidence is reported separately."
    source_map = [
        {
            "final_claim_or_statement": "TCM packet summary.",
            "perspective": "tcm",
            "claim_ids": ["tcm:c1"],
            "evidence_refs": [{"source_id": "t-source-1", "chunk_id": "t-chunk-1", "title": "TCM source"}],
        }
    ]
    if western_available:
        source_map.append(
            {
                "final_claim_or_statement": "Western packet summary.",
                "perspective": "western",
                "claim_ids": ["western:c1"],
                "evidence_refs": [{"source_id": "w-source-1", "chunk_id": "w-chunk-1", "title": "Western source"}],
            }
        )
        source_map.extend(
            [
                {
                    "final_claim_or_statement": "Both packets describe the topic.",
                    "perspective": "tcm",
                    "claim_ids": ["tcm:c1"],
                    "evidence_refs": [{"source_id": "t-source-1", "chunk_id": "t-chunk-1", "title": "TCM source"}],
                },
                {
                    "final_claim_or_statement": "Both packets describe the topic.",
                    "perspective": "western",
                    "claim_ids": ["western:c1"],
                    "evidence_refs": [{"source_id": "w-source-1", "chunk_id": "w-chunk-1", "title": "Western source"}],
                },
            ]
        )
        source_map.extend(
            [
                {
                    "final_claim_or_statement": overall_summary,
                    "perspective": "tcm",
                    "claim_ids": ["tcm:c1"],
                    "evidence_refs": [{"source_id": "t-source-1", "chunk_id": "t-chunk-1", "title": "TCM source"}],
                },
                {
                    "final_claim_or_statement": overall_summary,
                    "perspective": "western",
                    "claim_ids": ["western:c1"],
                    "evidence_refs": [{"source_id": "w-source-1", "chunk_id": "w-chunk-1", "title": "Western source"}],
                },
            ]
        )
    else:
        source_map.append(
            {
                "final_claim_or_statement": overall_summary,
                "perspective": "tcm",
                "claim_ids": ["tcm:c1"],
                "evidence_refs": [{"source_id": "t-source-1", "chunk_id": "t-chunk-1", "title": "TCM source"}],
            }
        )
    return CrossPerspectiveAnswer.model_validate(
        {
            "overall_summary": overall_summary,
            "overall_supporting_claim_ids": ["tcm:c1", "western:c1"] if western_available else ["tcm:c1"],
            "perspectives": {
                "western": {
                    "available": western_available,
                    "summary": "Western packet summary." if western_available else WESTERN_UNAVAILABLE_SUMMARY,
                    "supported_claim_ids": ["western:c1"] if western_available else [],
                },
                "tcm": {
                    "available": True,
                    "summary": "TCM packet summary.",
                    "supported_claim_ids": ["tcm:c1"],
                },
            },
            "agreements": (
                [{"statement": "Both packets describe the topic.", "supporting_claim_ids": ["tcm:c1", "western:c1"]}]
                if western_available
                else []
            ),
            "differences_or_conflicts": [],
            "evidence_gaps": ["No clinical conclusion is established."],
            "uncertainty": ["This is a development output."],
            "source_map": source_map,
        }
    )


class QueueProvider:
    name = "fixture-provider"

    def __init__(self, model: str, outcomes: list[object]) -> None:
        self.model = model
        self.outcomes = list(outcomes)
        self.calls = 0
        self.prompts: list[str] = []

    async def generate(self, **kwargs):
        self.calls += 1
        self.prompts.append(kwargs.get("prompt", ""))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        text = outcome if isinstance(outcome, str) else json.dumps(outcome)
        return GenerationResult(text=text, provider=self.name, model=self.model, prompt_tokens=10, completion_tokens=5)


class StubAdapter:
    def __init__(self, result: PerspectiveEvidencePacket | Exception) -> None:
        self.result = result
        self.calls = 0

    async def collect(self, question: str) -> AdapterOutcome:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return AdapterOutcome(packet=self.result, events=[], latency_ms=1.0)


class StubGovernance:
    def __init__(self) -> None:
        self.received = None

    async def synthesize(self, *, question: str, packets):
        self.received = packets
        result = answer(western_available=packets["western"].available)
        validate_governance_grounding(result, packets)
        return StructuredCallResult(value=result, events=[])


class MemoryTraceSink:
    def __init__(self) -> None:
        self.items = []

    def write(self, trace) -> None:
        self.items.append(trace)


def test_tcm_packet_schema_preserves_claim_to_source_traceability() -> None:
    tcm = packet("tcm")
    claim = tcm.claims[0]
    assert claim.evidence_refs[0].chunk_id == "t-chunk-1"
    assert tcm.provenance[0].source_id == "t-source-1"


def test_western_packet_schema_preserves_claim_to_source_traceability() -> None:
    western = packet("western")
    assert western.perspective == "western"
    assert western.claims[0].support_status == "supported"
    assert western.provenance[0].chunk_id == "w-chunk-1"


def test_tcm_adapter_preserves_existing_claim_and_provenance_without_remote_call() -> None:
    async def fake_consult(_):
        return TCMConsultResponse(
            scope_status="supported",
            abstained=False,
            generation_mode="mock",
            generation_source="mock_fallback",
            response_language="en",
            llm_model="Qwen/Qwen3-8B",
            llm_error="LLM_API_KEY is missing",
            query_analysis=QueryAnalysis(),
            summary="TCM educational interpretation.",
            tcm_perspective="TCM educational interpretation.",
            claims=[Claim(claim_id="claim_1", text="Bounded TCM claim.", evidence_ids=["t-chunk"], claim_type="pattern_hypothesis")],
            possible_patterns=[],
            related_herbs_or_formulas=[],
            evidence=[
                EvidenceChunk(
                    evidence_id="t-chunk",
                    source="TCM source",
                    source_ids=["t-source"],
                    title="TCM chunk",
                    source_type="educational_reference",
                    snippet="A bounded TCM evidence excerpt.",
                    relevance_score=0.8,
                    review_status="needs_human_review",
                )
            ],
            citations=[
                Citation(
                    source_id="t-source",
                    title="TCM source",
                    organization="Fixture",
                    url_or_identifier="https://example.org/tcm",
                    source_type="educational_reference",
                )
            ],
            safety_notes=[],
            confidence=Confidence(level="medium", score=0.6, reason="Limited fixture evidence."),
            disclaimer="Development fixture only.",
        )

    result = asyncio.run(TCMEvidenceAdapter(consult_fn=fake_consult).collect("Question about headache."))
    assert result.packet.execution_status == "degraded"
    assert result.packet.failure is not None and result.packet.failure.failure_type == "configuration"
    assert result.packet.claims[0].evidence_refs[0].source_id == "t-source"
    assert result.packet.provenance[0].excerpt == "A bounded TCM evidence excerpt."
    assert result.events == []


def test_western_adapter_preserves_retrieval_provenance_and_support_boundary() -> None:
    class FakeAgent:
        provider = type("Provider", (), {"model": "Qwen/Qwen3-8B"})()

        async def consult(self, _):
            evidence = WesternRetrievalEvidence(
                chunk_id="w-chunk",
                source_id="w-source",
                rank=1,
                lexical_score=0.8,
                article_title="Western review",
                section="Results",
                pmcid="PMC123",
                source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC123/",
                license="CC BY",
                topic=WesternTopic.HEADACHE,
                text="A bounded Western evidence excerpt.",
            )
            return WesternConsultResponse(
                question="Question about headache.",
                topic=WesternTopic.HEADACHE,
                answer="Western educational interpretation.",
                retrieval=[evidence],
                claims=[WesternClaim(claim_id="western-answer-1", text="Western educational interpretation.")],
                limitations=["Pilot limitation."],
                provider="fixture-provider",
                model="Qwen/Qwen3-8B",
                generation_mode="llm",
                trace=WesternTrace(
                    corpus_name="fixture",
                    corpus_version="fixture-v1",
                    corpus_chunk_count=1,
                    corpus_source_count=1,
                    retrieved_evidence_ids=["w-chunk"],
                    provider_attempts=[
                        ProviderAttempt(
                            attempt=1,
                            provider="fixture-provider",
                            model="Qwen/Qwen3-8B",
                            success=True,
                        )
                    ],
                ),
            )

    result = asyncio.run(WesternEvidenceAdapter(agent=FakeAgent()).collect("Question about headache."))
    assert result.packet.available is True
    assert result.packet.claims[0].claim_kind == "source_excerpt"
    assert result.packet.claims[0].support_status == "supported"
    assert result.packet.claims[0].evidence_refs[0].source_id == "w-source"
    assert result.packet.provenance[0].source_id == "w-source"
    assert result.packet.provenance[0].excerpt == "A bounded Western evidence excerpt."
    assert result.packet.claims[1].support_status == "insufficient"


def test_packet_schema_rejects_claim_reference_absent_from_provenance() -> None:
    with pytest.raises(ValidationError, match="absent from packet provenance"):
        PerspectiveEvidencePacket(
            perspective="tcm",
            interpretation="fixture",
            claims=[
                PerspectiveClaim(
                    claim_id="tcm:c1",
                    claim_text="fixture",
                    evidence_refs=[EvidenceReference(source_id="fake", chunk_id="fake")],
                    support_status="supported",
                )
            ],
        )


def test_governance_schema_and_source_traceability_are_validated() -> None:
    packets = {"tcm": packet("tcm"), "western": packet("western")}
    result = answer()
    validate_governance_grounding(result, packets)
    assert result.source_map[0].claim_ids == ["tcm:c1"]


def test_forced_tcm_western_routing_bypasses_router_model() -> None:
    never_router_provider = QueueProvider(ROUTER_MODEL, [])
    router = CrossPerspectiveRouter(provider=never_router_provider)
    governance = StubGovernance()
    sink = MemoryTraceSink()
    tcm_adapter = StubAdapter(packet("tcm"))
    western_adapter = StubAdapter(packet("western"))
    service = CrossPerspectiveService(
        router=router,
        tcm_adapter=tcm_adapter,
        western_adapter=western_adapter,
        governance=governance,
        trace_sink=sink,
    )

    result = asyncio.run(service.consult(CrossPerspectiveConsultRequest(question="Compare evidence for headache.")))

    assert result.status == "completed"
    assert result.routing.requested_perspectives == ["tcm", "western"]
    assert never_router_provider.calls == 0
    assert tcm_adapter.calls == western_adapter.calls == 1
    assert sink.items[0].retrieval_chunk_ids == {"tcm": ["t-chunk-1"], "western": ["w-chunk-1"]}


def test_one_perspective_failure_is_visible_to_governance_and_not_fabricated() -> None:
    governance = StubGovernance()
    service = CrossPerspectiveService(
        router=CrossPerspectiveRouter(provider=QueueProvider(ROUTER_MODEL, [])),
        tcm_adapter=StubAdapter(packet("tcm")),
        western_adapter=StubAdapter(
            PerspectiveAdapterError("western", "Provider unavailable.", failure_type="provider")
        ),
        governance=governance,
        trace_sink=MemoryTraceSink(),
    )

    result = asyncio.run(service.consult(CrossPerspectiveConsultRequest(question="Compare evidence for cough.")))

    assert result.status == "partial_failure"
    assert result.failed_roles == ["western"]
    assert governance.received["western"].available is False
    assert governance.received["western"].claims == []
    assert result.answer is not None
    assert result.answer.perspectives.western.available is False


def test_governance_rejects_fake_source_ids_without_retry() -> None:
    invalid = answer().model_dump(mode="json")
    invalid["source_map"][0]["evidence_refs"] = [{"source_id": "fabricated-source", "chunk_id": "t-chunk-1"}]
    provider = QueueProvider("Qwen/Qwen3-8B", [invalid])
    governance = CrossPerspectiveGovernanceAgent(provider=provider)

    with pytest.raises(StructuredModelCallFailure) as caught:
        asyncio.run(
            governance.synthesize(
                question="Compare evidence for headache.",
                packets={"tcm": packet("tcm"), "western": packet("western")},
            )
        )

    assert provider.calls == 1
    assert caught.value.events[-1].failure_class == "semantic"


def test_router_allows_only_one_technical_retry() -> None:
    routed = RoutingDecision(
        use_tcm=True,
        use_western=True,
        reason_summary="Both evidence pathways are relevant.",
        requested_perspectives=["tcm", "western"],
    )
    provider = QueueProvider(
        ROUTER_MODEL,
        [ProviderUnavailable("LLM provider connectivity error", error_type="connectivity"), routed.model_dump(mode="json")],
    )
    result = asyncio.run(CrossPerspectiveRouter(provider=provider).route_auto("Compare approaches to headache."))
    assert provider.calls == 2
    assert len(result.events) == 2
    assert result.events[0].retry_performed is True
    assert result.events[1].attempt == 2


def test_nutrition_is_disabled_with_frozen_message() -> None:
    service = CrossPerspectiveService(
        router=CrossPerspectiveRouter(provider=QueueProvider(ROUTER_MODEL, [])),
        tcm_adapter=StubAdapter(packet("tcm")),
        western_adapter=StubAdapter(packet("western")),
        governance=StubGovernance(),
        trace_sink=MemoryTraceSink(),
    )
    request = CrossPerspectiveConsultRequest(
        question="What nutrition guidance applies?",
        perspectives=["nutrition"],
        router_mode="forced",
    )
    with pytest.raises(NutritionUnavailableError, match="dedicated provenance-preserving") as caught:
        asyncio.run(service.consult(request))
    assert str(caught.value) == NUTRITION_UNAVAILABLE_MESSAGE


def test_agreement_with_empty_supporting_claim_ids_is_rejected() -> None:
    payload = answer().model_dump(mode="json")
    payload["agreements"] = [{"statement": "Unsupported agreement.", "supporting_claim_ids": []}]
    with pytest.raises(ValidationError):
        CrossPerspectiveAnswer.model_validate(payload)


def test_agreement_using_an_insufficient_claim_is_rejected() -> None:
    insufficient_western = packet("western").model_copy(
        update={"claims": [packet("western").claims[0].model_copy(update={"support_status": "insufficient"})]}
    )
    with pytest.raises(Exception, match="insufficient"):
        validate_governance_grounding(answer(), {"tcm": packet("tcm"), "western": insufficient_western})


def test_difference_with_empty_claim_ids_is_rejected() -> None:
    payload = answer().model_dump(mode="json")
    payload["differences_or_conflicts"] = [{"statement": "Unsupported difference.", "tcm_claim_ids": [], "western_claim_ids": []}]
    with pytest.raises(ValidationError):
        CrossPerspectiveAnswer.model_validate(payload)


def test_fabricated_and_wrong_perspective_claim_ids_are_rejected() -> None:
    fabricated = answer().model_copy(
        update={
            "perspectives": answer().perspectives.model_copy(
                update={"tcm": answer().perspectives.tcm.model_copy(update={"supported_claim_ids": ["tcm:fabricated"]})}
            )
        }
    )
    with pytest.raises(Exception, match="unknown tcm claim ID"):
        validate_governance_grounding(fabricated, {"tcm": packet("tcm"), "western": packet("western")})

    wrong_perspective = answer().model_copy(
        update={
            "perspectives": answer().perspectives.model_copy(
                update={"tcm": answer().perspectives.tcm.model_copy(update={"supported_claim_ids": ["western:c1"]})}
            )
        }
    )
    with pytest.raises(Exception, match="unknown tcm claim ID"):
        validate_governance_grounding(wrong_perspective, {"tcm": packet("tcm"), "western": packet("western")})


def test_source_chunk_cross_pair_mismatch_is_rejected() -> None:
    payload = answer().model_dump(mode="json")
    payload["source_map"][0]["evidence_refs"] = [{"source_id": "t-source-1", "chunk_id": "w-chunk-1"}]
    malformed = CrossPerspectiveAnswer.model_validate(payload)
    with pytest.raises(Exception, match="source/chunk pair"):
        validate_governance_grounding(malformed, {"tcm": packet("tcm"), "western": packet("western")})


def test_source_map_cannot_use_an_insufficient_claim() -> None:
    insufficient_tcm = packet("tcm").model_copy(
        update={"claims": [packet("tcm").claims[0].model_copy(update={"support_status": "insufficient"})]}
    )
    with pytest.raises(Exception, match="insufficient"):
        validate_governance_grounding(answer(), {"tcm": insufficient_tcm, "western": packet("western")})


def test_perspective_summary_requires_matching_source_map_support() -> None:
    payload = answer().model_dump(mode="json")
    payload["source_map"] = [entry for entry in payload["source_map"] if entry["final_claim_or_statement"] != "TCM packet summary."]
    malformed = CrossPerspectiveAnswer.model_validate(payload)
    with pytest.raises(Exception, match="tcm summary"):
        validate_governance_grounding(malformed, {"tcm": packet("tcm"), "western": packet("western")})


def test_agreement_requires_source_map_support_from_both_perspectives() -> None:
    payload = answer().model_dump(mode="json")
    payload["source_map"] = [
        entry
        for entry in payload["source_map"]
        if not (entry["final_claim_or_statement"] == "Both packets describe the topic." and entry["perspective"] == "western")
    ]
    malformed = CrossPerspectiveAnswer.model_validate(payload)
    with pytest.raises(Exception, match="agreement requires"):
        validate_governance_grounding(malformed, {"tcm": packet("tcm"), "western": packet("western")})


def test_overall_summary_without_support_ids_is_rejected() -> None:
    payload = answer().model_dump(mode="json")
    payload["overall_supporting_claim_ids"] = []
    malformed = CrossPerspectiveAnswer.model_validate(payload)
    with pytest.raises(Exception, match="overall summary must cite usable claims"):
        validate_governance_grounding(malformed, {"tcm": packet("tcm"), "western": packet("western")})


def test_overall_summary_requires_source_map_for_each_represented_perspective() -> None:
    payload = answer().model_dump(mode="json")
    payload["source_map"] = [
        entry
        for entry in payload["source_map"]
        if not (
            entry["final_claim_or_statement"] == payload["overall_summary"]
            and entry["perspective"] == "western"
        )
    ]
    malformed = CrossPerspectiveAnswer.model_validate(payload)
    with pytest.raises(Exception, match="overall summary requires"):
        validate_governance_grounding(malformed, {"tcm": packet("tcm"), "western": packet("western")})


def test_available_perspective_with_usable_claims_requires_summary_ids() -> None:
    payload = answer().model_dump(mode="json")
    payload["perspectives"]["western"]["supported_claim_ids"] = []
    malformed = CrossPerspectiveAnswer.model_validate(payload)
    with pytest.raises(Exception, match="available western summary must cite usable claims"):
        validate_governance_grounding(malformed, {"tcm": packet("tcm"), "western": packet("western")})


def test_no_usable_perspective_uses_only_deterministic_status_summary() -> None:
    payload = answer().model_dump(mode="json")
    payload["perspectives"]["western"] = {
        "available": True,
        "summary": WESTERN_NO_CLAIM_SUMMARY,
        "supported_claim_ids": [],
    }
    payload["agreements"] = []
    payload["overall_supporting_claim_ids"] = ["tcm:c1"]
    payload["source_map"] = [
        entry
        for entry in payload["source_map"]
        if entry["perspective"] == "tcm"
        and entry["final_claim_or_statement"] in {"TCM packet summary.", payload["overall_summary"]}
    ]
    valid = CrossPerspectiveAnswer.model_validate(payload)
    validate_governance_grounding(valid, {"tcm": packet("tcm"), "western": packet("western").model_copy(update={"claims": [packet("western").claims[0].model_copy(update={"support_status": "insufficient"})]})})

    payload["perspectives"]["western"]["summary"] = "Uncited Western medical assertion."
    malformed = CrossPerspectiveAnswer.model_validate(payload)
    with pytest.raises(Exception, match="deterministic no-claim"):
        validate_governance_grounding(malformed, {"tcm": packet("tcm"), "western": packet("western").model_copy(update={"claims": [packet("western").claims[0].model_copy(update={"support_status": "insufficient"})]})})


def test_multi_claim_source_map_requires_evidence_for_every_claim() -> None:
    base_tcm = packet("tcm")
    second_claim = PerspectiveClaim(
        claim_id="tcm:c2",
        claim_text="Second TCM evidence-bounded claim.",
        evidence_refs=[EvidenceReference(source_id="t-source-2", chunk_id="t-chunk-2")],
        support_status="supported",
    )
    tcm = base_tcm.model_copy(
        update={
            "claims": [base_tcm.claims[0], second_claim],
            "provenance": [
                *base_tcm.provenance,
                ProvenanceRecord(source_id="t-source-2", chunk_id="t-chunk-2", title="TCM source 2"),
            ],
        }
    )
    payload = answer().model_dump(mode="json")
    payload["perspectives"]["tcm"]["supported_claim_ids"] = ["tcm:c1", "tcm:c2"]
    for entry in payload["source_map"]:
        if entry["perspective"] == "tcm" and entry["final_claim_or_statement"] == "TCM packet summary.":
            entry["claim_ids"] = ["tcm:c1", "tcm:c2"]
            break
    malformed = CrossPerspectiveAnswer.model_validate(payload)
    with pytest.raises(Exception, match="evidence coverage"):
        validate_governance_grounding(malformed, {"tcm": tcm, "western": packet("western")})


def test_governance_payload_omits_unverified_interpretation() -> None:
    payload = build_governance_payload({"tcm": packet("tcm"), "western": packet("western")})
    assert all("interpretation" not in item for item in payload.values())
    provider = QueueProvider("Qwen/Qwen3-8B", [answer().model_dump(mode="json")])
    asyncio.run(
        CrossPerspectiveGovernanceAgent(provider=provider).synthesize(
            question="Compare evidence for headache.",
            packets={"tcm": packet("tcm"), "western": packet("western")},
        )
    )
    assert '"interpretation"' not in provider.prompts[0]


def test_governance_prompt_requires_explicit_nested_output_shape() -> None:
    required_top_level = {
        "overall_summary",
        "overall_supporting_claim_ids",
        "perspectives",
        "agreements",
        "differences_or_conflicts",
        "evidence_gaps",
        "uncertainty",
        "source_map",
    }
    prompt_text = GOVERNANCE_SYSTEM_PROMPT.casefold()
    for field_name in required_top_level:
        assert field_name.casefold() in prompt_text
    assert "must never appear as top-level keys" in prompt_text
    assert "source_map is a top-level array" in prompt_text
    assert '"perspectives"' in GOVERNANCE_SYSTEM_PROMPT
    assert '"tcm"' in GOVERNANCE_SYSTEM_PROMPT
    assert '"western"' in GOVERNANCE_SYSTEM_PROMPT

    provider = QueueProvider("Qwen/Qwen3-8B", [answer().model_dump(mode="json")])
    asyncio.run(
        CrossPerspectiveGovernanceAgent(provider=provider).synthesize(
            question="Compare evidence for headache.",
            packets={"tcm": packet("tcm"), "western": packet("western")},
        )
    )
    captured_prompt = provider.prompts[0].casefold()
    assert "emit exactly these eight top-level keys" in captured_prompt
    assert "never emit tcm or western at the top level" in captured_prompt
    assert "source_map is a top-level array" in captured_prompt


def test_flat_governance_shape_with_top_level_perspectives_fails_contract() -> None:
    flat = answer().model_dump(mode="json")
    perspective_values = flat.pop("perspectives")
    flat["tcm"] = perspective_values["tcm"]
    flat["western"] = perspective_values["western"]
    with pytest.raises(ValidationError, match="perspectives|extra inputs"):
        CrossPerspectiveAnswer.model_validate(flat)


def test_western_generation_failure_keeps_source_evidence_as_degraded() -> None:
    class FailingWesternAgent:
        provider = type("Provider", (), {"model": "Qwen/Qwen3-8B"})()

        async def consult(self, _):
            evidence = WesternRetrievalEvidence(
                chunk_id="w-failure-chunk",
                source_id="w-failure-source",
                rank=1,
                lexical_score=0.7,
                article_title="Western failure fixture",
                section="Results",
                pmcid="PMC124",
                source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC124/",
                license="CC BY",
                topic=WesternTopic.HEADACHE,
                text="Exact source excerpt retained after generation failure.",
            )
            return WesternConsultResponse(
                question="Question about headache.",
                topic=WesternTopic.HEADACHE,
                retrieval=[evidence],
                claims=[],
                generation_mode="generation_failure",
                abstained=True,
                abstention_reason="Provider unavailable.",
                model="Qwen/Qwen3-8B",
                trace=WesternTrace(
                    corpus_name="fixture",
                    corpus_version="fixture-v1",
                    corpus_chunk_count=1,
                    corpus_source_count=1,
                    provider_attempts=[ProviderAttempt(attempt=1, provider="fixture", model="Qwen/Qwen3-8B", success=False, error_type="connectivity", error="Provider unavailable.")],
                ),
            )

    result = asyncio.run(WesternEvidenceAdapter(agent=FailingWesternAgent()).collect("Question about headache."))
    assert result.packet.available is True
    assert result.packet.execution_status == "degraded"
    assert result.packet.failure is not None
    assert result.packet.claims[0].claim_kind == "source_excerpt"
    assert "source-backed" in result.packet.interpretation


def test_western_returned_model_mismatch_is_degraded_and_visible() -> None:
    class MismatchWesternAgent:
        provider = type("Provider", (), {"model": "Qwen/Qwen3-8B"})()

        async def consult(self, _):
            evidence = WesternRetrievalEvidence(
                chunk_id="w-mismatch-chunk", source_id="w-mismatch-source", rank=1, lexical_score=0.7,
                article_title="Mismatch fixture", section="Results", pmcid="PMC125",
                source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC125/", license="CC BY",
                topic=WesternTopic.HEADACHE, text="Source excerpt.",
            )
            return WesternConsultResponse(
                question="Question about headache.", topic=WesternTopic.HEADACHE,
                answer="Untrusted generated text.", retrieval=[evidence],
                claims=[WesternClaim(claim_id="mismatched-generated", text="Untrusted generated claim.", evidence_ids=["w-mismatch-chunk"])],
                generation_mode="llm", provider="fixture", model="Other/Model",
                trace=WesternTrace(corpus_name="fixture", corpus_version="fixture-v1", corpus_chunk_count=1, corpus_source_count=1,
                    provider_attempts=[ProviderAttempt(attempt=1, provider="fixture", model="Other/Model", success=True)]),
            )

    result = asyncio.run(WesternEvidenceAdapter(agent=MismatchWesternAgent()).collect("Question about headache."))
    assert result.packet.available is True
    assert result.packet.execution_status == "degraded"
    assert result.packet.failure is not None and result.packet.failure.failure_type == "configuration"
    assert all(claim.claim_kind == "source_excerpt" for claim in result.packet.claims)
    assert all(claim.support_status == "supported" for claim in result.packet.claims)
    attempted_generated_use = answer().model_copy(
        update={
            "overall_supporting_claim_ids": ["tcm:c1", "western:mismatched-generated"],
            "perspectives": answer().perspectives.model_copy(
                update={
                    "western": answer().perspectives.western.model_copy(
                        update={"supported_claim_ids": ["western:mismatched-generated"]}
                    )
                }
            ),
        }
    )
    with pytest.raises(Exception, match="unknown western claim ID"):
        validate_governance_grounding(
            attempted_generated_use,
            {"tcm": packet("tcm"), "western": result.packet},
        )
    assert "Other/Model" in result.packet.interpretation


def test_tcm_returned_model_mismatch_is_degraded() -> None:
    async def fake_consult(_):
        return TCMConsultResponse(
            scope_status="supported", abstained=False, generation_mode="llm", generation_source="siliconflow_llm",
            response_language="en", llm_model="Qwen/Qwen3-8B", llm_provider_model="Other/Model",
            provider_attempts=1, provider_http_statuses=[200], query_analysis=QueryAnalysis(),
            summary="Untrusted generated summary.", tcm_perspective="Untrusted generated summary.",
            claims=[Claim(claim_id="deterministic-claim", text="Deterministic retrieval claim.", evidence_ids=["tcm-mismatch-chunk"], claim_type="pattern_hypothesis")],
            possible_patterns=[], related_herbs_or_formulas=[],
            evidence=[EvidenceChunk(evidence_id="tcm-mismatch-chunk", source="TCM source", source_ids=["tcm-mismatch-source"], title="TCM chunk", source_type="fixture", snippet="Deterministic retrieval excerpt.", relevance_score=0.8, review_status="verified")],
            citations=[Citation(source_id="tcm-mismatch-source", title="TCM source", organization="Fixture", source_type="fixture")], safety_notes=[],
            confidence=Confidence(level="medium", score=0.5, reason="Fixture."), disclaimer="Fixture.",
        )

    result = asyncio.run(TCMEvidenceAdapter(consult_fn=fake_consult).collect("Question about headache."))
    assert result.packet.execution_status == "degraded"
    assert result.packet.failure is not None and result.packet.failure.failure_type == "configuration"
    assert result.packet.claims[0].claim_id == "tcm:deterministic-claim"
    assert result.packet.claims[0].support_status == "supported"
    assert result.events[-1].success is False


def test_tcm_response_format_compatibility_retry_is_counted() -> None:
    class FakeResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return self._payload

    class FakeHTTP:
        def __init__(self):
            self.calls = []
            self.responses = [
                FakeResponse(400, {}),
                FakeResponse(200, {"model": "Qwen/Qwen3-8B", "choices": [{"message": {"content": "{}"}}]}),
            ]

        async def post(self, url, *, headers, json):
            self.calls.append(json)
            return self.responses.pop(0)

    client = OpenAICompatibleClient()
    fake_http = FakeHTTP()
    client._http_client = lambda: fake_http
    result = asyncio.run(client._post_chat({"response_format": {"type": "json_object"}}, {"Authorization": "Bearer test"}))
    assert result["model"] == "Qwen/Qwen3-8B"
    assert client.provider_telemetry.attempts == 2
    assert client.provider_telemetry.compatibility_retry is True
    assert client.provider_telemetry.http_statuses == [400, 200]
    assert "response_format" not in fake_http.calls[1]


def test_tcm_compatibility_retry_followed_by_failure_preserves_retry_count_and_status() -> None:
    async def fake_consult(_):
        return TCMConsultResponse(
            scope_status="supported", abstained=False, generation_mode="mock", generation_source="mock_fallback",
            response_language="en", llm_model="Qwen/Qwen3-8B", llm_error="LLM provider returned HTTP 500",
            provider_attempts=2, provider_retry_count=1, provider_http_statuses=[400, 500],
            provider_compatibility_retry=True, query_analysis=QueryAnalysis(),
            summary="Deterministic fallback summary.", tcm_perspective="Deterministic fallback summary.",
            claims=[], possible_patterns=[], related_herbs_or_formulas=[], evidence=[], citations=[], safety_notes=[],
            confidence=Confidence(level="low", score=0.2, reason="Fixture."), disclaimer="Fixture.",
        )

    result = asyncio.run(TCMEvidenceAdapter(consult_fn=fake_consult).collect("Question about headache."))
    assert result.packet.failure is not None
    assert result.packet.failure.retry_count == 1
    assert result.packet.failure.http_status == 500
    assert [event.attempt for event in result.events] == [1, 2]
    assert result.events[0].success is False
    assert result.events[1].success is False


def test_trace_omits_raw_question_by_default_and_hashes_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CROSS_PERSPECTIVE_TRACE_RAW_QUESTION", raising=False)
    question = "Unique private development question 12345."
    sink = DevelopmentTraceLogger(tmp_path / "trace.jsonl")
    service = CrossPerspectiveService(
        router=CrossPerspectiveRouter(provider=QueueProvider(ROUTER_MODEL, [])),
        tcm_adapter=StubAdapter(packet("tcm")), western_adapter=StubAdapter(packet("western")),
        governance=StubGovernance(), trace_sink=sink,
    )
    result = asyncio.run(service.consult(CrossPerspectiveConsultRequest(question=question, question_id="q-1")))
    stored = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
    assert question not in stored
    assert result.trace.question_hash == hashlib.sha256(question.encode()).hexdigest()
    assert result.trace.governance_input["question_hash"] == result.trace.question_hash
    assert "question" not in result.trace.governance_input


def test_no_deepseek_runtime_reference_exists_in_cross_perspective() -> None:
    root = Path(__file__).resolve().parents[1] / "cross_perspective"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert "DeepSeek-V3.2" not in text


def test_development_endpoint_is_registered() -> None:
    from main import app

    assert "/api/cross-perspective/consult" in app.openapi()["paths"]


def test_governance_default_provider_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, object]] = []
    fake_provider = object()

    def fake_build_llm_provider(model_id: str, **kwargs: object) -> object:
        captured.append({"model_id": model_id, **kwargs})
        return fake_provider

    import cross_perspective.governance as governance_module

    monkeypatch.setattr(governance_module, "build_llm_provider", fake_build_llm_provider)

    assert GOVERNANCE_TIMEOUT_SECONDS == 90.0
    assert GOVERNANCE_MAX_TOKENS == 1800
    agent = CrossPerspectiveGovernanceAgent()
    assert len(captured) == 1
    assert captured[0] == {
        "model_id": "Qwen/Qwen3-8B",
        "timeout_override": 90.0,
        "max_tokens_override": 1800,
        "thinking_behavior": "send_false",
    }
    assert agent.provider is fake_provider
