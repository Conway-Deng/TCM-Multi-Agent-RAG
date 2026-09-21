from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError

from cross_perspective.adapters import (
    AdapterOutcome,
    PerspectiveAdapterError,
    TCMEvidenceAdapter,
    WesternEvidenceAdapter,
)
from cross_perspective.governance import CrossPerspectiveGovernanceAgent, validate_governance_grounding
from cross_perspective.model_calls import StructuredCallResult, StructuredModelCallFailure
from cross_perspective.router import CrossPerspectiveRouter, ROUTER_MODEL
from cross_perspective.schemas import (
    CrossPerspectiveAnswer,
    CrossPerspectiveConsultRequest,
    EvidenceReference,
    ModelCallEvent,
    NUTRITION_UNAVAILABLE_MESSAGE,
    PerspectiveClaim,
    PerspectiveEvidencePacket,
    ProvenanceRecord,
    RoutingDecision,
)
from cross_perspective.service import CrossPerspectiveService, NutritionUnavailableError
from providers.base import GenerationResult
from providers.openai_compatible import ProviderUnavailable
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
    source_map = [
        {
            "final_claim_or_statement": "The TCM packet contains one bounded claim.",
            "perspective": "tcm",
            "claim_ids": ["tcm:c1"],
            "source_ids": ["t-source-1"],
            "chunk_ids": ["t-chunk-1"],
        }
    ]
    if western_available:
        source_map.append(
            {
                "final_claim_or_statement": "The Western packet contains one bounded claim.",
                "perspective": "western",
                "claim_ids": ["western:c1"],
                "source_ids": ["w-source-1"],
                "chunk_ids": ["w-chunk-1"],
            }
        )
    return CrossPerspectiveAnswer.model_validate(
        {
            "overall_summary": "The two perspectives are reported separately.",
            "perspectives": {
                "western": {
                    "available": western_available,
                    "summary": "Western packet summary." if western_available else "Western perspective unavailable.",
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

    async def generate(self, **kwargs):
        self.calls += 1
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
    assert result.packet.claims[0].support_status == "insufficient"
    assert result.packet.claims[0].evidence_refs == []
    assert result.packet.provenance[0].source_id == "w-source"
    assert result.packet.provenance[0].excerpt == "A bounded Western evidence excerpt."


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
    invalid["source_map"][0]["source_ids"] = ["fabricated-source"]
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


def test_development_endpoint_is_registered() -> None:
    from main import app

    assert "/api/cross-perspective/consult" in app.openapi()["paths"]
