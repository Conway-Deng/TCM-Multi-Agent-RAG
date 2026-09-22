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
    GOVERNANCE_MODEL,
    GOVERNANCE_SYSTEM_PROMPT,
    GOVERNANCE_TIMEOUT_SECONDS,
    GovernanceContractError,
    build_deterministic_source_map,
    build_governance_payload,
    validate_governance_grounding,
)
from cross_perspective.model_calls import StructuredCallResult, StructuredModelCallFailure
from cross_perspective.perspective_agents import (
    ADVISORY_MAX_TOKENS,
    COVERAGE_AUDITOR_MODEL,
    EVIDENCE_SPECIALIST_MODEL,
    GROUNDING_SKEPTIC_MODEL,
    AdvisoryRunResult,
    PerspectiveAdvisorySuite,
    PerspectiveAssessmentError,
    build_advisory_payload,
    build_advisory_structural_template,
    build_advisory_user_prompt,
    validate_perspective_assessment,
)
from cross_perspective.router import CrossPerspectiveRouter, ROUTER_MODEL, ROUTER_SYSTEM_PROMPT
from cross_perspective.schemas import (
    ActivePerspectiveName,
    AgentRole,
    Agreement,
    AssessmentIssue,
    CrossPerspectiveAnswer,
    CrossPerspectiveConsultRequest,
    CrossPerspectiveDraft,
    DifferenceOrConflict,
    EvidenceReference,
    ModelCallEvent,
    NUTRITION_UNAVAILABLE_MESSAGE,
    OVERALL_NO_CLAIM_SUMMARY,
    PerspectiveAgentAssessment,
    PerspectiveClaim,
    PerspectiveEvidencePacket,
    PerspectiveFailure,
    PerspectiveSummaries,
    PerspectiveSummary,
    ProvenanceRecord,
    RouterDraft,
    RoutingDecision,
    SourceMapEntry,
    TCM_NO_CLAIM_SUMMARY,
    TCM_UNAVAILABLE_SUMMARY,
    WESTERN_NO_CLAIM_SUMMARY,
    WESTERN_UNAVAILABLE_SUMMARY,
)
from cross_perspective.service import CrossPerspectiveRunError, CrossPerspectiveService, NutritionUnavailableError
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


def draft(*, western_available: bool = True, include_difference: bool = False) -> CrossPerspectiveDraft:
    overall_summary = "The selected evidence is reported separately."
    agreements = (
        [Agreement(statement="Both packets describe the topic.", supporting_claim_ids=["tcm:c1", "western:c1"])]
        if western_available
        else []
    )
    differences = (
        [DifferenceOrConflict(statement="Perspective difference statement.", tcm_claim_ids=["tcm:c1"], western_claim_ids=["western:c1"])]
        if (western_available and include_difference)
        else []
    )
    return CrossPerspectiveDraft(
        overall_summary=overall_summary,
        overall_supporting_claim_ids=["tcm:c1", "western:c1"] if western_available else ["tcm:c1"],
        perspectives=PerspectiveSummaries(
            western=PerspectiveSummary(
                available=western_available,
                summary="Western packet summary." if western_available else WESTERN_UNAVAILABLE_SUMMARY,
                supported_claim_ids=["western:c1"] if western_available else [],
            ),
            tcm=PerspectiveSummary(
                available=True,
                summary="TCM packet summary.",
                supported_claim_ids=["tcm:c1"],
            ),
        ),
        agreements=agreements,
        differences_or_conflicts=differences,
        evidence_gaps=["No clinical conclusion is established."],
        uncertainty=["This is a development output."],
    )


def answer(*, western_available: bool = True) -> CrossPerspectiveAnswer:
    d = draft(western_available=western_available)
    packets = {
        "tcm": packet("tcm"),
        "western": packet("western") if western_available else packet("western").model_copy(update={"available": False, "claims": []}),
    }
    source_map = build_deterministic_source_map(d, packets)
    return CrossPerspectiveAnswer(
        overall_summary=d.overall_summary,
        overall_supporting_claim_ids=d.overall_supporting_claim_ids,
        perspectives=d.perspectives,
        agreements=d.agreements,
        differences_or_conflicts=d.differences_or_conflicts,
        evidence_gaps=d.evidence_gaps,
        uncertainty=d.uncertainty,
        source_map=source_map,
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
        d = draft(western_available=packets["western"].available)
        source_map = build_deterministic_source_map(d, packets)
        result = CrossPerspectiveAnswer(
            overall_summary=d.overall_summary,
            overall_supporting_claim_ids=d.overall_supporting_claim_ids,
            perspectives=d.perspectives,
            agreements=d.agreements,
            differences_or_conflicts=d.differences_or_conflicts,
            evidence_gaps=d.evidence_gaps,
            uncertainty=d.uncertainty,
            source_map=source_map,
        )
        validate_governance_grounding(result, packets)
        return StructuredCallResult(value=result, events=[])


class MemoryTraceSink:
    def __init__(self) -> None:
        self.items = []

    def write(self, trace) -> None:
        self.items.append(trace)


class StubAdvisorySuite:
    def __init__(
        self,
        assessments: dict[ActivePerspectiveName, list[PerspectiveAgentAssessment]] | None = None,
        events: list[ModelCallEvent] | None = None,
        latency_by_role: dict[str, float] | None = None,
        failed_roles: list[str] | None = None,
    ) -> None:
        self.assessments = assessments or {"tcm": [], "western": []}
        self.events = events or []
        self.latency_by_role = latency_by_role or {}
        self.failed_roles = failed_roles or []

    async def analyze(
        self,
        question: str,
        packets: dict[ActivePerspectiveName, PerspectiveEvidencePacket],
    ) -> AdvisoryRunResult:
        return AdvisoryRunResult(
            assessments=self.assessments,
            events=self.events,
            latency_by_role=self.latency_by_role,
            failed_roles=self.failed_roles,
        )


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
        advisory_suite=StubAdvisorySuite(),
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
        advisory_suite=StubAdvisorySuite(),
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
    invalid = draft().model_dump(mode="json")
    invalid["overall_supporting_claim_ids"] = ["fabricated-claim-id"]
    provider = QueueProvider(GOVERNANCE_MODEL, [invalid])
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
    draft = RouterDraft(
        use_tcm=True,
        use_western=True,
        reason_summary="Both evidence pathways are relevant.",
    )
    provider = QueueProvider(
        ROUTER_MODEL,
        [ProviderUnavailable("LLM provider connectivity error", error_type="connectivity"), draft.model_dump(mode="json")],
    )
    result = asyncio.run(CrossPerspectiveRouter(provider=provider).route_auto("Compare approaches to headache."))
    assert provider.calls == 2
    assert len(result.events) == 2
    assert result.events[0].retry_performed is True
    assert result.events[1].attempt == 2
    assert isinstance(result.value, RoutingDecision)
    assert result.value.requested_perspectives == ["tcm", "western"]


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
    provider = QueueProvider(GOVERNANCE_MODEL, [draft().model_dump(mode="json")])
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
    }
    prompt_text = GOVERNANCE_SYSTEM_PROMPT.casefold()
    for field_name in required_top_level:
        assert field_name.casefold() in prompt_text
    assert "must never appear as top-level keys" in prompt_text
    assert "source_map" not in prompt_text
    assert "sourcemapentry" not in prompt_text
    assert "evidence_refs" not in prompt_text
    assert "perspectives" in prompt_text
    assert "perspectives.tcm" in prompt_text
    assert "perspectives.western" in prompt_text

    # Output compaction requirements in system prompt
    assert "minified json" in prompt_text
    assert "no pretty printing" in prompt_text
    assert "overall_summary: maximum 2 concise sentences" in prompt_text
    assert "perspectives.tcm.summary: maximum 2 concise sentences" in prompt_text
    assert "perspectives.western.summary: maximum 2 concise sentences" in prompt_text
    assert "agreements: include only clearly evidence-supported agreements, maximum 2 entries" in prompt_text
    assert "differences_or_conflicts: include only clearly evidence-supported differences/conflicts, maximum 2 entries" in prompt_text
    assert "evidence_gaps: maximum 3 items" in prompt_text
    assert "uncertainty: maximum 3 items" in prompt_text
    assert "smallest sufficient subset of usable claim ids" in prompt_text
    for status_str in (
        TCM_UNAVAILABLE_SUMMARY,
        WESTERN_UNAVAILABLE_SUMMARY,
        TCM_NO_CLAIM_SUMMARY,
        WESTERN_NO_CLAIM_SUMMARY,
        OVERALL_NO_CLAIM_SUMMARY,
    ):
        assert status_str in GOVERNANCE_SYSTEM_PROMPT

    provider = QueueProvider(GOVERNANCE_MODEL, [draft().model_dump(mode="json")])
    asyncio.run(
        CrossPerspectiveGovernanceAgent(provider=provider).synthesize(
            question="Compare evidence for headache.",
            packets={"tcm": packet("tcm"), "western": packet("western")},
        )
    )
    captured_prompt = provider.prompts[0].casefold()
    assert "emit exactly these seven top-level keys" in captured_prompt
    assert "never emit tcm or western at the top level" in captured_prompt
    instructions = captured_prompt.split("the packet interpretation field", 1)[1]
    assert "source_map" not in instructions
    assert "sourcemapentry" not in instructions
    assert "evidence_refs" not in instructions

    # Output compaction requirements in per-request prompt
    assert "minified json" in captured_prompt
    assert "no pretty printing" in captured_prompt
    assert "overall_summary: maximum 2 concise sentences" in captured_prompt
    assert "perspectives.tcm.summary: maximum 2 concise sentences" in captured_prompt
    assert "perspectives.western.summary: maximum 2 concise sentences" in captured_prompt
    assert "agreements: include only clearly evidence-supported agreements, maximum 2 entries" in captured_prompt
    assert "differences_or_conflicts: include only clearly evidence-supported differences/conflicts, maximum 2 entries" in captured_prompt
    assert "evidence_gaps: maximum 3 items" in captured_prompt
    assert "uncertainty: maximum 3 items" in captured_prompt
    assert "smallest sufficient subset of usable claim ids" in captured_prompt
    for status_str in (
        TCM_UNAVAILABLE_SUMMARY,
        WESTERN_UNAVAILABLE_SUMMARY,
        TCM_NO_CLAIM_SUMMARY,
        WESTERN_NO_CLAIM_SUMMARY,
        OVERALL_NO_CLAIM_SUMMARY,
    ):
        assert status_str in provider.prompts[0]


def test_list_form_source_map_entries_fail_contract() -> None:
    payload = answer().model_dump(mode="json")
    payload["source_map"] = [
        [
            "overall statement",
            "tcm",
            ["claim-1"],
            [{"source_id": "src-1", "chunk_id": "chk-1"}],
        ]
    ]
    with pytest.raises(ValidationError, match="source_map"):
        CrossPerspectiveAnswer.model_validate(payload)


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
        advisory_suite=StubAdvisorySuite(),
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
    assert GOVERNANCE_MAX_TOKENS == 2400
    agent = CrossPerspectiveGovernanceAgent()
    assert len(captured) == 1
    assert captured[0] == {
        "model_id": "THUDM/GLM-4-9B-0414",
        "timeout_override": 90.0,
        "max_tokens_override": 2400,
        "thinking_behavior": "omit",
    }
    assert agent.provider is fake_provider


def test_router_model_is_glm_4_9b() -> None:
    assert ROUTER_MODEL == "THUDM/GLM-4-9B-0414"


def test_router_default_provider_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, object]] = []
    fake_provider = object()

    def fake_build(model_id: str, **kwargs: object) -> object:
        captured.append({"model_id": model_id, **kwargs})
        return fake_provider

    import cross_perspective.router as router_module

    monkeypatch.setattr(router_module, "build_llm_provider", fake_build)
    router = CrossPerspectiveRouter()
    assert captured == [{"model_id": "THUDM/GLM-4-9B-0414", "thinking_behavior": "omit"}]
    assert router.provider is fake_provider


def test_governance_model_is_glm_4_9b() -> None:
    assert GOVERNANCE_MODEL == "THUDM/GLM-4-9B-0414"


def test_governance_response_model_is_cross_perspective_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    import cross_perspective.governance as gov_mod
    called_response_models: list[type] = []
    real_call = gov_mod.call_structured_model

    async def fake_call(*args, **kwargs):
        called_response_models.append(kwargs.get("response_model"))
        return await real_call(*args, **kwargs)

    monkeypatch.setattr(gov_mod, "call_structured_model", fake_call)
    provider = QueueProvider(GOVERNANCE_MODEL, [draft().model_dump(mode="json")])
    agent = CrossPerspectiveGovernanceAgent(provider=provider)
    asyncio.run(
        agent.synthesize(
            question="Compare evidence.",
            packets={"tcm": packet("tcm"), "western": packet("western")},
        )
    )
    assert called_response_models == [CrossPerspectiveDraft]


def test_draft_rejects_source_map_as_extra_field() -> None:
    data = draft().model_dump(mode="json")
    data["source_map"] = []
    with pytest.raises(ValidationError, match="extra|extra_forbidden|Extra inputs"):
        CrossPerspectiveDraft.model_validate(data)


def test_deterministic_source_map_materialization_order_and_content() -> None:
    packets = {"tcm": packet("tcm"), "western": packet("western")}
    d = draft(western_available=True, include_difference=True)
    source_map = build_deterministic_source_map(d, packets)

    assert len(source_map) == 8

    # 1. overall TCM row
    assert source_map[0].final_claim_or_statement == d.overall_summary
    assert source_map[0].perspective == "tcm"
    assert source_map[0].claim_ids == ["tcm:c1"]

    # 2. overall Western row
    assert source_map[1].final_claim_or_statement == d.overall_summary
    assert source_map[1].perspective == "western"
    assert source_map[1].claim_ids == ["western:c1"]

    # 3. TCM summary row
    assert source_map[2].final_claim_or_statement == d.perspectives.tcm.summary
    assert source_map[2].perspective == "tcm"
    assert source_map[2].claim_ids == ["tcm:c1"]

    # 4. Western summary row
    assert source_map[3].final_claim_or_statement == d.perspectives.western.summary
    assert source_map[3].perspective == "western"
    assert source_map[3].claim_ids == ["western:c1"]

    # 5. Agreement TCM row
    assert source_map[4].final_claim_or_statement == d.agreements[0].statement
    assert source_map[4].perspective == "tcm"
    assert source_map[4].claim_ids == ["tcm:c1"]

    # 6. Agreement Western row
    assert source_map[5].final_claim_or_statement == d.agreements[0].statement
    assert source_map[5].perspective == "western"
    assert source_map[5].claim_ids == ["western:c1"]

    # 7. Difference TCM row
    assert source_map[6].final_claim_or_statement == d.differences_or_conflicts[0].statement
    assert source_map[6].perspective == "tcm"
    assert source_map[6].claim_ids == ["tcm:c1"]

    # 8. Difference Western row
    assert source_map[7].final_claim_or_statement == d.differences_or_conflicts[0].statement
    assert source_map[7].perspective == "western"
    assert source_map[7].claim_ids == ["western:c1"]


def test_deterministic_source_map_evidence_refs_from_declared_claims_only() -> None:
    packets = {"tcm": packet("tcm"), "western": packet("western")}
    d = draft(western_available=True)
    source_map = build_deterministic_source_map(d, packets)
    for entry in source_map:
        for ref in entry.evidence_refs:
            assert ref.title is None
            if entry.perspective == "tcm":
                assert ref.source_id == "t-source-1"
                assert ref.chunk_id == "t-chunk-1"
            else:
                assert ref.source_id == "w-source-1"
                assert ref.chunk_id == "w-chunk-1"


def test_deterministic_source_map_unknown_ids_fail_closed() -> None:
    packets = {"tcm": packet("tcm"), "western": packet("western")}
    # Unknown in overall
    d1 = draft().model_copy(update={"overall_supporting_claim_ids": ["unknown:claim"]})
    with pytest.raises(GovernanceContractError, match="unknown"):
        build_deterministic_source_map(d1, packets)

    # Unknown in TCM summary
    d2 = draft()
    d2.perspectives.tcm.supported_claim_ids = ["unknown:claim"]
    with pytest.raises(GovernanceContractError, match="unknown"):
        build_deterministic_source_map(d2, packets)

    # Unknown in Western summary
    d3 = draft()
    d3.perspectives.western.supported_claim_ids = ["unknown:claim"]
    with pytest.raises(GovernanceContractError, match="unknown"):
        build_deterministic_source_map(d3, packets)

    # Unknown in agreements
    d4 = draft()
    d4.agreements = [Agreement(statement="agree", supporting_claim_ids=["tcm:c1", "unknown:claim"])]
    with pytest.raises(GovernanceContractError, match="unknown"):
        build_deterministic_source_map(d4, packets)

    # Unknown in differences
    d5 = draft()
    d5.differences_or_conflicts = [
        DifferenceOrConflict(statement="diff", tcm_claim_ids=["unknown:claim"], western_claim_ids=["western:c1"])
    ]
    with pytest.raises(GovernanceContractError, match="unknown"):
        build_deterministic_source_map(d5, packets)


def test_deterministic_source_map_insufficient_ids_fail_closed() -> None:
    tcm_insufficient = packet("tcm")
    tcm_insufficient.claims[0].support_status = "insufficient"
    packets = {"tcm": tcm_insufficient, "western": packet("western")}

    # Insufficient in overall
    with pytest.raises(GovernanceContractError, match="insufficient"):
        build_deterministic_source_map(draft(), packets)

    # Insufficient in TCM summary
    d_clean_overall = draft().model_copy(update={"overall_supporting_claim_ids": ["western:c1"]})
    with pytest.raises(GovernanceContractError, match="insufficient"):
        build_deterministic_source_map(d_clean_overall, packets)


def test_deterministic_source_map_wrong_perspective_ids_fail_closed() -> None:
    packets = {"tcm": packet("tcm"), "western": packet("western")}

    # TCM summary citing Western claim
    d1 = draft()
    d1.perspectives.tcm.supported_claim_ids = ["western:c1"]
    with pytest.raises(GovernanceContractError, match="wrong-perspective"):
        build_deterministic_source_map(d1, packets)

    # Western summary citing TCM claim
    d2 = draft()
    d2.perspectives.western.supported_claim_ids = ["tcm:c1"]
    with pytest.raises(GovernanceContractError, match="wrong-perspective"):
        build_deterministic_source_map(d2, packets)

    # Difference TCM citing Western claim
    d3 = draft()
    d3.differences_or_conflicts = [
        DifferenceOrConflict(statement="diff", tcm_claim_ids=["western:c1"], western_claim_ids=["western:c1"])
    ]
    with pytest.raises(GovernanceContractError, match="wrong-perspective"):
        build_deterministic_source_map(d3, packets)

    # Difference Western citing TCM claim
    d4 = draft()
    d4.differences_or_conflicts = [
        DifferenceOrConflict(statement="diff", tcm_claim_ids=["tcm:c1"], western_claim_ids=["tcm:c1"])
    ]
    with pytest.raises(GovernanceContractError, match="wrong-perspective"):
        build_deterministic_source_map(d4, packets)


def test_valid_materialized_answer_passes_validate_governance_grounding() -> None:
    packets = {"tcm": packet("tcm"), "western": packet("western")}
    d = draft(western_available=True, include_difference=True)
    source_map = build_deterministic_source_map(d, packets)
    answer = CrossPerspectiveAnswer(
        overall_summary=d.overall_summary,
        overall_supporting_claim_ids=d.overall_supporting_claim_ids,
        perspectives=d.perspectives,
        agreements=d.agreements,
        differences_or_conflicts=d.differences_or_conflicts,
        evidence_gaps=d.evidence_gaps,
        uncertainty=d.uncertainty,
        source_map=source_map,
    )
    validate_governance_grounding(answer, packets)


def test_public_cross_perspective_answer_shape_remains_unchanged() -> None:
    expected_fields = {
        "overall_summary",
        "overall_supporting_claim_ids",
        "perspectives",
        "agreements",
        "differences_or_conflicts",
        "evidence_gaps",
        "uncertainty",
        "source_map",
    }
    assert set(CrossPerspectiveAnswer.model_fields.keys()) == expected_fields


def test_governance_instructions_contain_all_exact_deterministic_status_strings() -> None:
    expected_status_strings = [
        TCM_UNAVAILABLE_SUMMARY,
        WESTERN_UNAVAILABLE_SUMMARY,
        TCM_NO_CLAIM_SUMMARY,
        WESTERN_NO_CLAIM_SUMMARY,
        OVERALL_NO_CLAIM_SUMMARY,
    ]
    for expected in expected_status_strings:
        assert expected in GOVERNANCE_SYSTEM_PROMPT

    provider = QueueProvider(GOVERNANCE_MODEL, [draft().model_dump(mode="json")])
    asyncio.run(
        CrossPerspectiveGovernanceAgent(provider=provider).synthesize(
            question="Compare evidence for headache.",
            packets={"tcm": packet("tcm"), "western": packet("western")},
        )
    )
    request_prompt = provider.prompts[0]
    for expected in expected_status_strings:
        assert expected in request_prompt


def test_governance_unavailable_perspective_deterministic_summary_materializes_successfully() -> None:
    unavailable_western = packet("western").model_copy(update={"available": False, "claims": []})
    packets = {"tcm": packet("tcm"), "western": unavailable_western}
    d = draft(western_available=False)
    provider = QueueProvider(GOVERNANCE_MODEL, [d.model_dump(mode="json")])
    agent = CrossPerspectiveGovernanceAgent(provider=provider)
    result = asyncio.run(
        agent.synthesize(
            question="Compare evidence for headache.",
            packets=packets,
        )
    )
    answer = result.value
    assert isinstance(answer, CrossPerspectiveAnswer)
    assert answer.perspectives.western.available is False
    assert answer.perspectives.western.summary == WESTERN_UNAVAILABLE_SUMMARY
    assert answer.perspectives.western.supported_claim_ids == []
    assert len(answer.source_map) == 2
    assert all(entry.perspective == "tcm" for entry in answer.source_map)
    assert provider.calls == 1


def test_governance_payload_excludes_provenance_and_citation_metadata() -> None:
    tcm_pkt = packet("tcm")
    west_pkt = packet("western")
    payload = build_governance_payload({"tcm": tcm_pkt, "western": west_pkt})
    raw_dump = json.dumps(payload)

    # Excluded top-level and packet fields
    assert all("interpretation" not in item for item in payload.values())
    assert all("provenance" not in item for item in payload.values())

    # Excluded claim-level citation fields
    for p_name, item in payload.items():
        for clm in item["claims"]:
            assert "evidence_refs" not in clm
            assert "source_id" not in clm
            assert "chunk_id" not in clm
            assert "title" not in clm

    # Excluded metadata strings in raw payload dump
    for forbidden in (
        "source_id",
        "chunk_id",
        "excerpt",
        "source_url",
        "title",
        "identifier",
        "license",
        "evidence_refs",
    ):
        assert f'"{forbidden}"' not in raw_dump


def test_governance_payload_retains_semantic_and_concise_failure_fields() -> None:
    tcm_pkt = packet("tcm")
    west_pkt = packet("western").model_copy(
        update={
            "available": False,
            "execution_status": "unavailable",
            "claims": [],
            "failure": PerspectiveFailure(
                role="western",
                failure_type="provider",
                error_summary="Model provider timeout.",
                http_status=504,
                retry_count=1,
            ),
        }
    )
    payload = build_governance_payload({"tcm": tcm_pkt, "western": west_pkt})

    tcm_data = payload["tcm"]
    assert tcm_data["perspective"] == "tcm"
    assert tcm_data["available"] is True
    assert tcm_data["execution_status"] == "available"
    assert len(tcm_data["claims"]) == 1
    tcm_claim = tcm_data["claims"][0]
    assert tcm_claim["claim_id"] == "tcm:c1"
    assert tcm_claim["claim_text"] == tcm_pkt.claims[0].claim_text
    assert tcm_claim["support_status"] == "supported"
    assert tcm_claim["claim_kind"] == tcm_pkt.claims[0].claim_kind
    assert tcm_data["uncertainty"] == tcm_pkt.uncertainty
    assert tcm_data["missing_information"] == tcm_pkt.missing_information
    assert tcm_data["limitations"] == tcm_pkt.limitations
    assert tcm_data["failure"] is None

    west_data = payload["western"]
    assert west_data["perspective"] == "western"
    assert west_data["available"] is False
    assert west_data["execution_status"] == "unavailable"
    assert west_data["claims"] == []
    assert west_data["failure"] == {
        "failure_type": "provider",
        "error_summary": "Model provider timeout.",
    }
    assert "http_status" not in west_data["failure"]
    assert "retry_count" not in west_data["failure"]
    assert "role" not in west_data["failure"]


def test_original_packets_unmodified_by_payload_construction() -> None:
    tcm_pkt = packet("tcm")
    west_pkt = packet("western")

    # Verify original has provenance and refs
    assert len(tcm_pkt.provenance) > 0
    assert len(tcm_pkt.claims[0].evidence_refs) > 0

    _ = build_governance_payload({"tcm": tcm_pkt, "western": west_pkt})

    # Still retains complete provenance and refs
    assert len(tcm_pkt.provenance) > 0
    assert tcm_pkt.provenance[0].source_id == "t-source-1"
    assert tcm_pkt.provenance[0].chunk_id == "t-chunk-1"
    assert len(tcm_pkt.claims[0].evidence_refs) > 0
    assert tcm_pkt.claims[0].evidence_refs[0].source_id == "t-source-1"


def test_deterministic_source_map_equivalent_before_and_after_payload_construction() -> None:
    packets = {"tcm": packet("tcm"), "western": packet("western")}
    d = draft(western_available=True, include_difference=True)

    sm_before = build_deterministic_source_map(d, packets)
    _ = build_governance_payload(packets)
    sm_after = build_deterministic_source_map(d, packets)

    assert sm_before == sm_after
    assert [entry.model_dump(mode="json") for entry in sm_before] == [
        entry.model_dump(mode="json") for entry in sm_after
    ]


def test_governance_prompt_does_not_claim_provenance_metadata_in_payload() -> None:
    prompt_text = GOVERNANCE_SYSTEM_PROMPT.casefold()
    assert "claims were pre-associated with provenance" in prompt_text
    assert "citation and source-map materialization is handled deterministically outside the model" in prompt_text
    assert "claims with linked provenance" not in prompt_text

    provider = QueueProvider(GOVERNANCE_MODEL, [draft().model_dump(mode="json")])
    asyncio.run(
        CrossPerspectiveGovernanceAgent(provider=provider).synthesize(
            question="Compare evidence for headache.",
            packets={"tcm": packet("tcm"), "western": packet("western")},
        )
    )
    captured = provider.prompts[0].casefold()
    assert "claims were pre-associated with provenance" in captured
    assert "citation and source-map materialization is handled deterministically outside the model" in captured
    assert "claims with linked provenance" not in captured


def test_governance_payload_size_diagnostic() -> None:
    packets = {"tcm": packet("tcm"), "western": packet("western")}
    full_dump = json.dumps({k: v.model_dump(mode="json") for k, v in packets.items()})
    compact_payload = build_governance_payload(packets)
    compact_dump = json.dumps(compact_payload)

    # Diagnostic assertion: compact payload is strictly smaller than full packets
    assert len(compact_dump) < len(full_dump)


def test_router_draft_schema_fields_and_forbids_extra() -> None:
    # 1. RouterDraft contains exactly: use_tcm, use_western, reason_summary
    fields = set(RouterDraft.model_fields.keys())
    assert fields == {"use_tcm", "use_western", "reason_summary"}

    draft_obj = RouterDraft(
        use_tcm=True,
        use_western=False,
        reason_summary="TCM only applicable.",
    )
    assert draft_obj.use_tcm is True
    assert draft_obj.use_western is False
    assert draft_obj.reason_summary == "TCM only applicable."

    # 2. RouterDraft rejects requested_perspectives as an extra field
    with pytest.raises(ValidationError) as exc:
        RouterDraft.model_validate({
            "use_tcm": True,
            "use_western": True,
            "reason_summary": "Both needed.",
            "requested_perspectives": ["tcm", "western"],
        })
    assert "extra_forbidden" in str(exc.value)


def test_router_draft_rejects_all_false_and_empty_reason() -> None:
    # 3. RouterDraft rejects use_tcm = false, use_western = false
    with pytest.raises(ValidationError, match="router must select at least one available perspective"):
        RouterDraft(use_tcm=False, use_western=False, reason_summary="Neither selected.")

    with pytest.raises(ValidationError):
        RouterDraft(use_tcm=True, use_western=False, reason_summary="")


def test_auto_routing_materializes_both_perspectives() -> None:
    # 4. Auto routing with use_tcm=true, use_western=true deterministically produces ["tcm", "western"]
    draft_data = {"use_tcm": True, "use_western": True, "reason_summary": "Both perspectives relevant."}
    provider = QueueProvider(ROUTER_MODEL, [draft_data])
    router = CrossPerspectiveRouter(provider=provider)
    result = asyncio.run(router.route_auto("Should I combine TCM and Western treatments?"))

    assert isinstance(result.value, RoutingDecision)
    assert result.value.use_tcm is True
    assert result.value.use_western is True
    assert result.value.requested_perspectives == ["tcm", "western"]
    assert result.value.reason_summary == "Both perspectives relevant."


def test_auto_routing_materializes_tcm_only() -> None:
    # 5. Auto routing with only TCM produces ["tcm"]
    draft_data = {"use_tcm": True, "use_western": False, "reason_summary": "Only TCM perspective relevant."}
    provider = QueueProvider(ROUTER_MODEL, [draft_data])
    router = CrossPerspectiveRouter(provider=provider)
    result = asyncio.run(router.route_auto("TCM herbal question."))

    assert isinstance(result.value, RoutingDecision)
    assert result.value.use_tcm is True
    assert result.value.use_western is False
    assert result.value.requested_perspectives == ["tcm"]
    assert result.value.reason_summary == "Only TCM perspective relevant."


def test_auto_routing_materializes_western_only() -> None:
    # 6. Auto routing with only Western produces ["western"]
    draft_data = {"use_tcm": False, "use_western": True, "reason_summary": "Only Western perspective relevant."}
    provider = QueueProvider(ROUTER_MODEL, [draft_data])
    router = CrossPerspectiveRouter(provider=provider)
    result = asyncio.run(router.route_auto("Western clinical guidelines."))

    assert isinstance(result.value, RoutingDecision)
    assert result.value.use_tcm is False
    assert result.value.use_western is True
    assert result.value.requested_perspectives == ["western"]
    assert result.value.reason_summary == "Only Western perspective relevant."


def test_auto_routing_single_provider_call_and_preserves_events() -> None:
    # 7. Only one provider/model call occurs.
    # 8. Provider/model events from the draft call are preserved unchanged.
    draft_data = {"use_tcm": True, "use_western": True, "reason_summary": "Dual perspective."}
    provider = QueueProvider(ROUTER_MODEL, [draft_data])
    router = CrossPerspectiveRouter(provider=provider)
    result = asyncio.run(router.route_auto("Test single call."))

    assert provider.calls == 1
    assert len(result.events) == 1
    event = result.events[0]
    assert event.role == "router"
    assert event.success is True
    assert event.attempt == 1
    assert event.requested_model == ROUTER_MODEL
    assert event.reported_model == ROUTER_MODEL


def test_auto_routing_prompt_does_not_request_perspectives() -> None:
    # 9. Auto-router prompt does not ask the model to generate requested_perspectives.
    assert "requested_perspectives" not in ROUTER_SYSTEM_PROMPT
    assert "use_tcm" in ROUTER_SYSTEM_PROMPT
    assert "use_western" in ROUTER_SYSTEM_PROMPT
    assert "reason_summary" in ROUTER_SYSTEM_PROMPT

    draft_data = {"use_tcm": True, "use_western": True, "reason_summary": "Dual."}
    provider = QueueProvider(ROUTER_MODEL, [draft_data])
    router = CrossPerspectiveRouter(provider=provider)
    asyncio.run(router.route_auto("Check prompt content."))

    prompt_captured = provider.prompts[0]
    assert "requested_perspectives" not in prompt_captured
    assert "use_tcm" in prompt_captured
    assert "use_western" in prompt_captured
    assert "reason_summary" in prompt_captured


def test_routing_decision_public_schema_and_forced_routing_unchanged() -> None:
    # 10. Existing RoutingDecision public schema remains unchanged.
    expected_fields = {"use_tcm", "use_western", "reason_summary", "requested_perspectives"}
    assert set(RoutingDecision.model_fields.keys()) == expected_fields

    decision = RoutingDecision(
        use_tcm=True,
        use_western=False,
        reason_summary="TCM chosen",
        requested_perspectives=["tcm"],
    )
    assert decision.model_dump() == {
        "use_tcm": True,
        "use_western": False,
        "reason_summary": "TCM chosen",
        "requested_perspectives": ["tcm"],
    }

    # 11. Forced routing behavior remains unchanged.
    forced_dual = CrossPerspectiveRouter.route_forced(["tcm", "western"])
    assert forced_dual.use_tcm is True
    assert forced_dual.use_western is True
    assert forced_dual.requested_perspectives == ["tcm", "western"]
    assert "forced development routing" in forced_dual.reason_summary

    forced_tcm = CrossPerspectiveRouter.route_forced(["tcm"])
    assert forced_tcm.use_tcm is True
    assert forced_tcm.use_western is False
    assert forced_tcm.requested_perspectives == ["tcm"]

    forced_western = CrossPerspectiveRouter.route_forced(["western"])
    assert forced_western.use_tcm is False
    assert forced_western.use_western is True
    assert forced_western.requested_perspectives == ["western"]


# =====================================================================
# Cross-Perspective v0.4 Patch 2: Advisory Agents Tests
# =====================================================================


def test_assessment_issue_rejects_extra_fields() -> None:
    # 1. AssessmentIssue rejects extra fields
    with pytest.raises(ValidationError) as exc:
        AssessmentIssue.model_validate({
            "issue_type": "uncertainty",
            "description": "Valid description",
            "claim_ids": ["tcm:c1"],
            "extra_forbidden_field": "disallowed",
        })
    assert "extra_forbidden" in str(exc.value)


def test_perspective_agent_assessment_rejects_extra_fields() -> None:
    # 2. PerspectiveAgentAssessment rejects extra fields
    with pytest.raises(ValidationError) as exc:
        PerspectiveAgentAssessment.model_validate({
            "perspective": "tcm",
            "role": "evidence_specialist",
            "assessment_summary": "Valid summary.",
            "referenced_claim_ids": ["tcm:c1"],
            "issues": [],
            "extra_disallowed_field": "disallowed",
        })
    assert "extra_forbidden" in str(exc.value)


def test_advisory_roles_valid_structured_output_passes() -> None:
    # 3, 4, 5. Valid structured output passes for each advisory role
    tcm_pkt = packet("tcm")
    for role in ("evidence_specialist", "coverage_auditor", "grounding_skeptic"):
        ass = PerspectiveAgentAssessment(
            perspective="tcm",
            role=role,
            assessment_summary=f"Summary for {role}.",
            referenced_claim_ids=["tcm:c1"],
            issues=[
                AssessmentIssue(
                    issue_type="uncertainty",
                    description=f"Issue description for {role}.",
                    claim_ids=["tcm:c1"],
                )
            ],
        )
        validate_perspective_assessment(ass, packet=tcm_pkt, expected_role=role)


def test_advisory_invented_referenced_claim_id_fails() -> None:
    # 6. Invented referenced_claim_id fails
    tcm_pkt = packet("tcm")
    ass = PerspectiveAgentAssessment(
        perspective="tcm",
        role="evidence_specialist",
        assessment_summary="Valid summary.",
        referenced_claim_ids=["tcm:invented_claim_999"],
        issues=[],
    )
    with pytest.raises(PerspectiveAssessmentError, match="not an existing claim"):
        validate_perspective_assessment(ass, packet=tcm_pkt, expected_role="evidence_specialist")


def test_advisory_referenced_claim_ids_rejects_insufficient_claim() -> None:
    # 7. referenced_claim_ids cannot include an existing insufficient claim
    tcm_pkt = packet("tcm").model_copy(deep=True)
    tcm_pkt.claims.append(
        PerspectiveClaim(
            claim_id="tcm:insuf1",
            claim_text="Insufficiently supported claim text.",
            support_status="insufficient",
        )
    )
    ass = PerspectiveAgentAssessment(
        perspective="tcm",
        role="evidence_specialist",
        assessment_summary="Valid summary.",
        referenced_claim_ids=["tcm:insuf1"],
        issues=[],
    )
    with pytest.raises(PerspectiveAssessmentError, match="insufficient support_status"):
        validate_perspective_assessment(ass, packet=tcm_pkt, expected_role="evidence_specialist")


def test_advisory_issues_claim_ids_may_include_insufficient_claim() -> None:
    # 8. issues[*].claim_ids MAY include an existing insufficient claim
    tcm_pkt = packet("tcm").model_copy(deep=True)
    tcm_pkt.claims.append(
        PerspectiveClaim(
            claim_id="tcm:insuf1",
            claim_text="Insufficiently supported claim text.",
            support_status="insufficient",
        )
    )
    ass = PerspectiveAgentAssessment(
        perspective="tcm",
        role="grounding_skeptic",
        assessment_summary="Skeptic flags insufficient claim.",
        referenced_claim_ids=["tcm:c1"],
        issues=[
            AssessmentIssue(
                issue_type="grounding_risk",
                description="This claim is marked insufficient.",
                claim_ids=["tcm:insuf1"],
            )
        ],
    )
    # Must succeed without raising:
    validate_perspective_assessment(ass, packet=tcm_pkt, expected_role="grounding_skeptic")


def test_advisory_issues_claim_ids_rejects_unknown_claim_id() -> None:
    # 9. issues[*].claim_ids rejects unknown claim ID
    tcm_pkt = packet("tcm")
    ass = PerspectiveAgentAssessment(
        perspective="tcm",
        role="coverage_auditor",
        assessment_summary="Auditor summary.",
        referenced_claim_ids=["tcm:c1"],
        issues=[
            AssessmentIssue(
                issue_type="coverage_gap",
                description="Issue referencing non-existent claim.",
                claim_ids=["tcm:c_unknown_xyz"],
            )
        ],
    )
    with pytest.raises(PerspectiveAssessmentError, match="not an existing claim"):
        validate_perspective_assessment(ass, packet=tcm_pkt, expected_role="coverage_auditor")


def test_advisory_perspective_mismatch_fails() -> None:
    # 10. Perspective mismatch fails
    tcm_pkt = packet("tcm")
    ass = PerspectiveAgentAssessment(
        perspective="western",
        role="evidence_specialist",
        assessment_summary="Summary.",
        referenced_claim_ids=[],
        issues=[],
    )
    with pytest.raises(PerspectiveAssessmentError, match="did not match packet perspective"):
        validate_perspective_assessment(ass, packet=tcm_pkt, expected_role="evidence_specialist")


def test_advisory_role_mismatch_fails() -> None:
    # 11. Role mismatch fails
    tcm_pkt = packet("tcm")
    ass = PerspectiveAgentAssessment(
        perspective="tcm",
        role="coverage_auditor",
        assessment_summary="Summary.",
        referenced_claim_ids=["tcm:c1"],
        issues=[],
    )
    with pytest.raises(PerspectiveAssessmentError, match="did not match expected role"):
        validate_perspective_assessment(ass, packet=tcm_pkt, expected_role="evidence_specialist")


def test_advisory_duplicate_referenced_claim_ids_fails() -> None:
    # 12. Duplicate referenced_claim_ids fails
    tcm_pkt = packet("tcm")
    ass = PerspectiveAgentAssessment(
        perspective="tcm",
        role="evidence_specialist",
        assessment_summary="Summary.",
        referenced_claim_ids=["tcm:c1", "tcm:c1"],
        issues=[],
    )
    with pytest.raises(PerspectiveAssessmentError, match="referenced_claim_ids must not contain duplicates"):
        validate_perspective_assessment(ass, packet=tcm_pkt, expected_role="evidence_specialist")


def test_advisory_duplicate_issue_claim_ids_fails() -> None:
    # 13. Duplicate issue.claim_ids fails
    tcm_pkt = packet("tcm")
    ass = PerspectiveAgentAssessment(
        perspective="tcm",
        role="grounding_skeptic",
        assessment_summary="Summary.",
        referenced_claim_ids=["tcm:c1"],
        issues=[
            AssessmentIssue(
                issue_type="uncertainty",
                description="Duplicate claim IDs in issue.",
                claim_ids=["tcm:c1", "tcm:c1"],
            )
        ],
    )
    with pytest.raises(PerspectiveAssessmentError, match="duplicate entries"):
        validate_perspective_assessment(ass, packet=tcm_pkt, expected_role="grounding_skeptic")


def test_advisory_agent_emits_correct_role_perspective_and_model() -> None:
    # 14, 15, 16. Correct role, perspective, and model identity preserved
    tcm_pkt = packet("tcm")
    ass_data = {
        "perspective": "tcm",
        "role": "evidence_specialist",
        "assessment_summary": "Strong evidence exists in packet.",
        "referenced_claim_ids": ["tcm:c1"],
        "issues": [],
    }
    provider = QueueProvider(EVIDENCE_SPECIALIST_MODEL, [ass_data])
    suite = PerspectiveAdvisorySuite(evidence_specialist_provider=provider)
    ass, events, latency, failed_role = asyncio.run(
        suite._run_role(
            role="evidence_specialist",
            perspective="tcm",
            packet=tcm_pkt,
            question="Question on headache?",
        )
    )
    assert ass is not None
    assert failed_role is None
    assert len(events) == 1
    event = events[0]
    assert event.role == "evidence_specialist"
    assert event.perspective == "tcm"
    assert event.requested_model == EVIDENCE_SPECIALIST_MODEL
    assert event.reported_model == EVIDENCE_SPECIALIST_MODEL
    assert event.success is True


def test_advisory_reported_model_mismatch_fails() -> None:
    # 17. Reported model mismatch fails
    tcm_pkt = packet("tcm")
    ass_data = {
        "perspective": "tcm",
        "role": "evidence_specialist",
        "assessment_summary": "Strong evidence exists.",
        "referenced_claim_ids": ["tcm:c1"],
        "issues": [],
    }

    class MismatchProvider(QueueProvider):
        async def generate(self, **kwargs):
            res = await super().generate(**kwargs)
            return GenerationResult(
                text=res.text,
                provider=res.provider,
                model="Substituted/Wrong-Model",
                prompt_tokens=1,
                completion_tokens=1,
            )

    provider = MismatchProvider(EVIDENCE_SPECIALIST_MODEL, [ass_data])
    suite = PerspectiveAdvisorySuite(evidence_specialist_provider=provider)
    ass, events, latency, failed_role = asyncio.run(
        suite._run_role(
            role="evidence_specialist",
            perspective="tcm",
            packet=tcm_pkt,
            question="Test question?",
        )
    )
    assert ass is None
    assert failed_role == "tcm:evidence_specialist"
    assert len(events) == 1
    assert events[0].success is False
    assert events[0].failure_class == "semantic"


def test_advisory_technical_retry_allowed_once() -> None:
    # 18. At most one technical retry remains allowed
    tcm_pkt = packet("tcm")
    ass_data = {
        "perspective": "tcm",
        "role": "coverage_auditor",
        "assessment_summary": "Coverage is adequate.",
        "referenced_claim_ids": ["tcm:c1"],
        "issues": [],
    }
    provider = QueueProvider(
        COVERAGE_AUDITOR_MODEL,
        [
            ProviderUnavailable("Temporary network timeout", error_type="timeout"),
            ass_data,
        ],
    )
    suite = PerspectiveAdvisorySuite(coverage_auditor_provider=provider)
    ass, events, latency, failed_role = asyncio.run(
        suite._run_role(
            role="coverage_auditor",
            perspective="tcm",
            packet=tcm_pkt,
            question="Question?",
        )
    )
    assert ass is not None
    assert failed_role is None
    assert provider.calls == 2
    assert len(events) == 2
    assert events[0].retry_performed is True
    assert events[1].attempt == 2
    assert events[1].success is True


def test_advisory_semantic_failure_receives_zero_retry() -> None:
    # 19. Semantic/schema failure receives zero retry
    tcm_pkt = packet("tcm")
    bad_data = {
        "perspective": "tcm",
        "role": "grounding_skeptic",
        "assessment_summary": "Summary.",
        "referenced_claim_ids": ["tcm:c1"],
        "issues": [],
        "invented_extra_field": "invalid",
    }
    provider = QueueProvider(GROUNDING_SKEPTIC_MODEL, [bad_data])
    suite = PerspectiveAdvisorySuite(grounding_skeptic_provider=provider)
    ass, events, latency, failed_role = asyncio.run(
        suite._run_role(
            role="grounding_skeptic",
            perspective="tcm",
            packet=tcm_pkt,
            question="Question?",
        )
    )
    assert ass is None
    assert failed_role == "tcm:grounding_skeptic"
    assert provider.calls == 1
    assert len(events) == 1
    assert events[0].retry_performed is False
    assert events[0].success is False
    assert events[0].failure_class == "semantic"


def test_advisory_suite_skips_not_selected_unavailable_and_zero_claims() -> None:
    # 20, 21, 22. not_selected, unavailable, and zero claims cause zero advisory calls
    provider = QueueProvider(EVIDENCE_SPECIALIST_MODEL, [])
    suite = PerspectiveAdvisorySuite(
        evidence_specialist_provider=provider,
        coverage_auditor_provider=QueueProvider(COVERAGE_AUDITOR_MODEL, []),
        grounding_skeptic_provider=QueueProvider(GROUNDING_SKEPTIC_MODEL, []),
    )
    p_not_sel = packet("tcm").model_copy(update={"execution_status": "not_selected", "available": False})
    p_unavail = packet("western").model_copy(update={"execution_status": "unavailable", "available": False})
    res1 = asyncio.run(suite.analyze("Question?", {"tcm": p_not_sel, "western": p_unavail}))
    assert res1.assessments == {"tcm": [], "western": []}
    assert res1.events == []
    assert provider.calls == 0

    p_zero = packet("tcm").model_copy(update={"available": True, "execution_status": "available", "claims": []})
    res2 = asyncio.run(suite.analyze("Question?", {"tcm": p_zero}))
    assert res2.assessments == {"tcm": [], "western": []}
    assert res2.events == []
    assert provider.calls == 0


def test_advisory_failure_isolation_sibling_and_perspective_resilience() -> None:
    # 23, 24, 25. Single failure does not fabricate, does not cancel siblings, does not block other perspective
    tcm_pkt = packet("tcm")
    west_pkt = packet("western")

    valid_tcm_es = {"perspective": "tcm", "role": "evidence_specialist", "assessment_summary": "TCM ES", "referenced_claim_ids": ["tcm:c1"], "issues": []}
    valid_tcm_ca = {"perspective": "tcm", "role": "coverage_auditor", "assessment_summary": "TCM CA", "referenced_claim_ids": ["tcm:c1"], "issues": []}
    bad_tcm_gs = {"perspective": "tcm", "role": "grounding_skeptic", "assessment_summary": "TCM GS", "referenced_claim_ids": ["tcm:invented_claim"], "issues": []}

    valid_w_es = {"perspective": "western", "role": "evidence_specialist", "assessment_summary": "West ES", "referenced_claim_ids": ["western:c1"], "issues": []}
    valid_w_ca = {"perspective": "western", "role": "coverage_auditor", "assessment_summary": "West CA", "referenced_claim_ids": ["western:c1"], "issues": []}
    valid_w_gs = {"perspective": "western", "role": "grounding_skeptic", "assessment_summary": "West GS", "referenced_claim_ids": ["western:c1"], "issues": []}

    suite = PerspectiveAdvisorySuite(
        evidence_specialist_provider=QueueProvider(EVIDENCE_SPECIALIST_MODEL, [valid_tcm_es, valid_w_es]),
        coverage_auditor_provider=QueueProvider(COVERAGE_AUDITOR_MODEL, [valid_tcm_ca, valid_w_ca]),
        grounding_skeptic_provider=QueueProvider(GROUNDING_SKEPTIC_MODEL, [bad_tcm_gs, valid_w_gs]),
    )

    result = asyncio.run(suite.analyze("Dual question", {"tcm": tcm_pkt, "western": west_pkt}))

    # 23. No replacement fabricated:
    tcm_roles = [a.role for a in result.assessments["tcm"]]
    assert "grounding_skeptic" not in tcm_roles
    assert len(tcm_roles) == 2

    # 24. Siblings succeed:
    assert set(tcm_roles) == {"evidence_specialist", "coverage_auditor"}

    # 25. Opposing perspective is unaffected:
    west_roles = [a.role for a in result.assessments["western"]]
    assert set(west_roles) == {"evidence_specialist", "coverage_auditor", "grounding_skeptic"}

    assert result.failed_roles == ["tcm:grounding_skeptic"]


def test_advisory_failure_with_successful_governance_yields_partial_failure() -> None:
    # 26, 27, 28, 29, 30. Advisory failure + successful Governance yields partial_failure, trace writing, and failed_roles
    tcm_pkt = packet("tcm")
    west_pkt = packet("western")

    failing_suite = StubAdvisorySuite(
        assessments={
            "tcm": [
                PerspectiveAgentAssessment(
                    perspective="tcm",
                    role="evidence_specialist",
                    assessment_summary="TCM ES ok.",
                    referenced_claim_ids=["tcm:c1"],
                    issues=[],
                )
            ],
            "western": [],
        },
        events=[
            ModelCallEvent(
                role="grounding_skeptic",
                attempt=1,
                provider="fixture",
                requested_model=GROUNDING_SKEPTIC_MODEL,
                success=False,
                latency_ms=10.0,
                failure_class="semantic",
                error_summary="Failed grounding",
                perspective="tcm",
            )
        ],
        latency_by_role={"tcm:evidence_specialist": 15.0, "tcm:grounding_skeptic": 10.0},
        failed_roles=["tcm:grounding_skeptic"],
    )

    sink = MemoryTraceSink()
    service = CrossPerspectiveService(
        router=CrossPerspectiveRouter(provider=QueueProvider(ROUTER_MODEL, [])),
        tcm_adapter=StubAdapter(tcm_pkt),
        western_adapter=StubAdapter(west_pkt),
        advisory_suite=failing_suite,
        governance=StubGovernance(),
        trace_sink=sink,
    )

    resp = asyncio.run(service.consult(CrossPerspectiveConsultRequest(question="Compare headache evidence.")))

    # 26. Governance was not blocked and produced answer:
    assert resp.answer is not None

    # 27. Overall status is partial_failure:
    assert resp.status == "partial_failure"

    # 28. Successful advisory role is written to perspective_assessments:
    assert len(resp.perspective_assessments["tcm"]) == 1
    assert resp.perspective_assessments["tcm"][0].role == "evidence_specialist"

    # 29. Failed advisory role is absent from perspective_assessments:
    assert not any(a.role == "grounding_skeptic" for a in resp.perspective_assessments["tcm"])

    # 30. Failed role appears in failed_roles:
    assert "tcm:grounding_skeptic" in resp.failed_roles
    assert "tcm:grounding_skeptic" in sink.items[0].failed_roles


def test_governance_input_does_not_contain_assessments_and_payload_identical() -> None:
    # 31, 32. Governance input does NOT contain assessments and payload is identical
    tcm_pkt = packet("tcm")
    west_pkt = packet("western")
    packets = {"tcm": tcm_pkt, "western": west_pkt}

    gov = StubGovernance()
    advisory_suite = StubAdvisorySuite(
        assessments={
            "tcm": [
                PerspectiveAgentAssessment(
                    perspective="tcm",
                    role="evidence_specialist",
                    assessment_summary="Advisory assessment.",
                    referenced_claim_ids=["tcm:c1"],
                    issues=[],
                )
            ],
            "western": [],
        }
    )
    sink = MemoryTraceSink()
    service = CrossPerspectiveService(
        router=CrossPerspectiveRouter(provider=QueueProvider(ROUTER_MODEL, [])),
        tcm_adapter=StubAdapter(tcm_pkt),
        western_adapter=StubAdapter(west_pkt),
        advisory_suite=advisory_suite,
        governance=gov,
        trace_sink=sink,
    )

    resp = asyncio.run(service.consult(CrossPerspectiveConsultRequest(question="Compare evidence for headache.")))

    # 31. Governance input does not contain assessments:
    assert "perspective_assessments" not in resp.trace.governance_input
    assert "perspective_assessments" not in gov.received
    assert set(gov.received.keys()) == {"tcm", "western"}

    # 32. build_governance_payload is completely unaffected:
    payload = build_governance_payload(packets)
    assert "perspective_assessments" not in payload
    assert "tcm" in payload and "western" in payload


def test_concurrent_advisory_orchestration_all_roles() -> None:
    # 38. Concurrent orchestration produces all successful assessments without changing result semantics
    tcm_pkt = packet("tcm")
    west_pkt = packet("western")

    valid_tcm_es = {"perspective": "tcm", "role": "evidence_specialist", "assessment_summary": "TCM ES", "referenced_claim_ids": ["tcm:c1"], "issues": []}
    valid_tcm_ca = {"perspective": "tcm", "role": "coverage_auditor", "assessment_summary": "TCM CA", "referenced_claim_ids": ["tcm:c1"], "issues": []}
    valid_tcm_gs = {"perspective": "tcm", "role": "grounding_skeptic", "assessment_summary": "TCM GS", "referenced_claim_ids": ["tcm:c1"], "issues": []}

    valid_w_es = {"perspective": "western", "role": "evidence_specialist", "assessment_summary": "West ES", "referenced_claim_ids": ["western:c1"], "issues": []}
    valid_w_ca = {"perspective": "western", "role": "coverage_auditor", "assessment_summary": "West CA", "referenced_claim_ids": ["western:c1"], "issues": []}
    valid_w_gs = {"perspective": "western", "role": "grounding_skeptic", "assessment_summary": "West GS", "referenced_claim_ids": ["western:c1"], "issues": []}

    suite = PerspectiveAdvisorySuite(
        evidence_specialist_provider=QueueProvider(EVIDENCE_SPECIALIST_MODEL, [valid_tcm_es, valid_w_es]),
        coverage_auditor_provider=QueueProvider(COVERAGE_AUDITOR_MODEL, [valid_tcm_ca, valid_w_ca]),
        grounding_skeptic_provider=QueueProvider(GROUNDING_SKEPTIC_MODEL, [valid_tcm_gs, valid_w_gs]),
    )

    result = asyncio.run(suite.analyze("Concurrent test", {"tcm": tcm_pkt, "western": west_pkt}))

    assert len(result.assessments["tcm"]) == 3
    assert len(result.assessments["western"]) == 3
    assert len(result.events) == 6
    assert result.failed_roles == []
    assert set(result.latency_by_role.keys()) == {
        "tcm:evidence_specialist",
        "tcm:coverage_auditor",
        "tcm:grounding_skeptic",
        "western:evidence_specialist",
        "western:coverage_auditor",
        "western:grounding_skeptic",
    }


def test_build_advisory_payload_projection_excludes_forbidden_fields() -> None:
    tcm_pkt = packet("tcm")
    payload = build_advisory_payload(tcm_pkt)
    assert set(payload.keys()) == {
        "perspective",
        "available",
        "execution_status",
        "claims",
        "provenance",
        "uncertainty",
        "missing_information",
        "limitations",
    }
    assert "interpretation" not in payload
    assert "source_url" not in payload
    assert "identifier" not in payload
    assert "license" not in payload
    assert "router" not in payload
    assert "governance" not in payload


def test_consult_run_id_prefix_is_v0_4() -> None:
    service = CrossPerspectiveService(
        router=CrossPerspectiveRouter(provider=QueueProvider(ROUTER_MODEL, [])),
        tcm_adapter=StubAdapter(packet("tcm")),
        western_adapter=StubAdapter(packet("western")),
        advisory_suite=StubAdvisorySuite(),
        governance=StubGovernance(),
        trace_sink=MemoryTraceSink(),
    )
    resp = asyncio.run(service.consult(CrossPerspectiveConsultRequest(question="Check run ID format.")))
    assert resp.run_id.startswith("cross-perspective-v0.4-dev-")
    assert resp.trace.run_id == resp.run_id


def test_trace_model_ids_contains_advisory_assignments() -> None:
    service = CrossPerspectiveService(
        router=CrossPerspectiveRouter(provider=QueueProvider(ROUTER_MODEL, [])),
        tcm_adapter=StubAdapter(packet("tcm")),
        western_adapter=StubAdapter(packet("western")),
        advisory_suite=StubAdvisorySuite(),
        governance=StubGovernance(),
        trace_sink=MemoryTraceSink(),
    )
    resp = asyncio.run(service.consult(CrossPerspectiveConsultRequest(question="Check model IDs.")))
    assert resp.trace.model_ids["evidence_specialist"] == EVIDENCE_SPECIALIST_MODEL
    assert resp.trace.model_ids["coverage_auditor"] == COVERAGE_AUDITOR_MODEL
    assert resp.trace.model_ids["grounding_skeptic"] == GROUNDING_SKEPTIC_MODEL


def test_auto_router_failure_trace_has_perspective_assessments_and_skips_downstream() -> None:
    class TrackingGovernance(StubGovernance):
        def __init__(self) -> None:
            super().__init__()
            self.called = False

        async def synthesize(self, **kwargs):
            self.called = True
            return await super().synthesize(**kwargs)

    class TrackingAdvisorySuite(StubAdvisorySuite):
        def __init__(self) -> None:
            super().__init__()
            self.called = False

        async def analyze(self, **kwargs):
            self.called = True
            return await super().analyze(**kwargs)

    sink = MemoryTraceSink()
    gov = TrackingGovernance()
    advisory = TrackingAdvisorySuite()
    router_provider = QueueProvider(ROUTER_MODEL, ["invalid json not an object"])
    service = CrossPerspectiveService(
        router=CrossPerspectiveRouter(provider=router_provider),
        tcm_adapter=StubAdapter(packet("tcm")),
        western_adapter=StubAdapter(packet("western")),
        advisory_suite=advisory,
        governance=gov,
        trace_sink=sink,
    )
    request = CrossPerspectiveConsultRequest(
        question="Compare headache evidence.",
        router_mode="auto",
    )

    with pytest.raises(CrossPerspectiveRunError) as exc_info:
        asyncio.run(service.consult(request))

    run_err = exc_info.value
    trace = run_err.trace
    assert "router" in trace.failed_roles
    assert trace.perspective_assessments == {}
    assert advisory.called is False
    assert gov.called is False
    assert len(sink.items) == 1
    assert sink.items[0].perspective_assessments == {}


def test_perspective_agent_assessment_rejects_more_than_four_issues() -> None:
    issues = [
        AssessmentIssue(issue_type="uncertainty", description=f"Issue {i}", claim_ids=["tcm:c1"])
        for i in range(5)
    ]
    with pytest.raises(ValidationError):
        PerspectiveAgentAssessment(
            perspective="tcm",
            role="evidence_specialist",
            assessment_summary="Summary.",
            referenced_claim_ids=["tcm:c1"],
            issues=issues,
        )


def test_advisory_structural_templates_and_prompts_are_role_and_perspective_specific() -> None:
    tcm_pkt = packet("tcm")
    tcm_payload = build_advisory_payload(tcm_pkt)
    west_pkt = packet("western")
    west_payload = build_advisory_payload(west_pkt)

    prompt_west_gs = build_advisory_user_prompt(
        role="grounding_skeptic",
        perspective="western",
        question="Western grounding question?",
        payload=west_payload,
    )
    assert '"perspective": "western"' in prompt_west_gs
    assert '"role": "grounding_skeptic"' in prompt_west_gs

    prompt_tcm_ca = build_advisory_user_prompt(
        role="coverage_auditor",
        perspective="tcm",
        question="TCM coverage question?",
        payload=tcm_payload,
    )
    assert '"perspective": "tcm"' in prompt_tcm_ca
    assert '"role": "coverage_auditor"' in prompt_tcm_ca

    # Check structural templates for all combinations do not contain fake claim IDs
    for p in ("tcm", "western"):
        for r in ("evidence_specialist", "coverage_auditor", "grounding_skeptic"):
            tmpl = build_advisory_structural_template(perspective=p, role=r)  # type: ignore[arg-type]
            assert f'"perspective": "{p}"' in tmpl
            assert f'"role": "{r}"' in tmpl
            assert '"referenced_claim_ids": []' in tmpl
            assert '"issues": []' in tmpl
            assert '"c1"' not in tmpl
            assert '"c2"' not in tmpl


def test_advisory_technical_retry_preserves_telemetry_when_semantic_validation_fails() -> None:
    tcm_pkt = packet("tcm")
    bad_assessment_data = {
        "perspective": "tcm",
        "role": "coverage_auditor",
        "assessment_summary": "Coverage summary.",
        "referenced_claim_ids": ["tcm:invented_claim_999"],
        "issues": [],
    }
    provider = QueueProvider(
        COVERAGE_AUDITOR_MODEL,
        [
            ProviderUnavailable("Initial network timeout", error_type="timeout"),
            bad_assessment_data,
        ],
    )
    suite = PerspectiveAdvisorySuite(coverage_auditor_provider=provider)
    ass, events, latency, failed_role = asyncio.run(
        suite._run_role(
            role="coverage_auditor",
            perspective="tcm",
            packet=tcm_pkt,
            question="Question?",
        )
    )
    assert ass is None
    assert failed_role == "tcm:coverage_auditor"
    assert provider.calls == 2
    assert len(events) == 2

    # Event 1: preserved as technical timeout failure
    assert events[0].attempt == 1
    assert events[0].success is False
    assert events[0].failure_class == "timeout"
    assert events[0].retry_performed is True
    assert "Initial network timeout" in events[0].error_summary

    # Event 2: provider call succeeded, but reclassified as semantic failure due to validation error
    assert events[1].attempt == 2
    assert events[1].success is False
    assert events[1].failure_class == "semantic"
    assert "not an existing claim" in events[1].error_summary


def test_advisory_prompt_contract_exposes_assessment_issue_schema_and_claim_id_rules() -> None:
    tcm_pkt = packet("tcm")
    tcm_payload = build_advisory_payload(tcm_pkt)
    prompt = build_advisory_user_prompt(
        role="coverage_auditor",
        perspective="tcm",
        question="Check prompt contract rules.",
        payload=tcm_payload,
    )

    # 1. Contains AssessmentIssue fields
    assert '"issue_type"' in prompt
    assert '"description"' in prompt
    assert '"claim_ids"' in prompt

    # 2. Contains all allowed issue_type values
    for itype in ("coverage_gap", "grounding_risk", "support_ambiguity", "redundancy", "uncertainty", "other"):
        assert itype in prompt

    # 3. Explicitly says issues must not be returned as plain strings
    assert "Do NOT return issues as plain strings." in prompt
    assert '"Some coverage concern."' in prompt

    # 4. Explicit claim ID rules
    assert "Claim ID Rules:" in prompt
    assert "Never create, abbreviate, normalize, or rewrite claim IDs." in prompt

    # 5. Dynamic perspective and role preserved
    assert '"perspective": "tcm"' in prompt
    assert '"role": "coverage_auditor"' in prompt

    # 6. No fake claim IDs like c1 or c2 anywhere in the prompt
    assert '"c1"' not in prompt
    assert '"c2"' not in prompt
