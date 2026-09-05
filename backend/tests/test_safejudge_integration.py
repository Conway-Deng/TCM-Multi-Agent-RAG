from __future__ import annotations

import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "mock"
os.environ["RESEARCH_REAL_LLM_ENABLED"] = "false"

from judges import run_integrated_judges
from main import app
from schemas.research import (
    DebateTrace,
    ResearchAgentOutput,
    ResearchCitation,
    RetrievalItem,
    StructuredClaim,
)


client = TestClient(app)


def evidence(*, score: float = 1.0, text: str = "Source-reported educational content.", cautions=None) -> RetrievalItem:
    metadata = {"title": "Fixture source", "review_status": "verified"}
    if cautions:
        metadata["cautions"] = cautions
    return RetrievalItem(
        chunk_id="e1",
        source_id="fixture",
        rank=1,
        semantic_score=score,
        retrieval_method="dense",
        chunk_text=text,
        source_metadata=metadata,
    )


def output(
    text: str,
    *,
    claim_id: str = "c1",
    evidence_ids=None,
    agent_id: str = "agent-1",
    confidence: float = 0.5,
    abstained: bool = False,
) -> ResearchAgentOutput:
    ids = ["e1"] if evidence_ids is None else evidence_ids
    citations = [
        ResearchCitation(evidence_id=item, source_id="fixture", title="Fixture source", provenance_valid=True)
        for item in ids
    ]
    return ResearchAgentOutput(
        agent_id=agent_id,
        agent_name=agent_id,
        agent_version="test",
        question="test question",
        language="en",
        subdomain="test",
        claims=[] if abstained else [StructuredClaim(claim_id=claim_id, text=text, evidence_ids=ids, confidence=confidence)],
        evidence_ids=ids,
        citations=citations,
        confidence=confidence,
        abstained=abstained,
    )


def judge(outputs, supplied_evidence, *, debate=None, response_text=None, model_failures=0):
    return run_integrated_judges(
        outputs,
        supplied_evidence,
        debate or DebateTrace(),
        [],
        response_text=response_text or " ".join(claim.text for item in outputs for claim in item.claims),
        model_failure_count=model_failures,
    )


def test_supported_response_with_strong_evidence() -> None:
    bundle = judge([output("The source reports an educational TCM concept.")], [evidence()])
    assert bundle.evidence_support.evidence_coverage == 1.0
    assert bundle.safety_assessment.assessment == "no_flags_detected"
    assert bundle.evidence_confidence.score == 0.9
    assert bundle.evidence_confidence.band == "strong"


def test_unsupported_treatment_certainty() -> None:
    bundle = judge(
        [output("This herbal treatment will cure the condition.", evidence_ids=[])],
        [evidence()],
    )
    assert "unsupported_treatment_certainty" in {item.code for item in bundle.safety_assessment.findings}


def test_unsupported_dosage() -> None:
    bundle = judge([output("Take 10 g daily.")], [evidence(text="Traditional source description only.")])
    assert "unsupported_dosage_or_use" in {item.code for item in bundle.safety_assessment.findings}


def test_missing_source_caution() -> None:
    bundle = judge(
        [output("The source reports a traditional use.")],
        [evidence(cautions=["Avoid during pregnancy."])],
    )
    assert "source_caution_not_preserved" in {item.code for item in bundle.safety_assessment.findings}


def test_unresolved_conflict_is_exposed_and_overresolution_is_flagged() -> None:
    debate = DebateTrace(
        disagreements=["Specialists differ."],
        unresolved_conflicts=["The evidence remains conflicting."],
    )
    bundle = judge(
        [output("The source reports one view.")],
        [evidence()],
        debate=debate,
        response_text="Therefore, the correct answer conclusively settles the conflict.",
    )
    assert bundle.conflict_status.has_unresolved_conflict is True
    assert "conflict_overresolution" in {item.code for item in bundle.safety_assessment.findings}


def test_weak_retrieval_confidence_cap() -> None:
    bundle = judge([output("Source-reported content.")], [evidence(score=0.3)])
    assert bundle.evidence_support.retrieval_sufficiency == 0.3
    assert bundle.evidence_confidence.score == 0.49
    assert any("0.49" in item for item in bundle.evidence_confidence.caps_applied)


def test_unsupported_claim_confidence_cap() -> None:
    outputs = [
        output("Unsupported plain assertion.", claim_id="c0", evidence_ids=[], agent_id="agent-0"),
        *[
            output(
                f"Supported source report {index}.",
                claim_id=f"c{index}",
                agent_id=f"agent-{index}",
            )
            for index in range(1, 10)
        ],
    ]
    debate = DebateTrace(agreements=[f"agreement {index}" for index in range(9)])
    bundle = judge(outputs, [evidence()], debate=debate)
    assert bundle.evidence_confidence.score == 0.69
    assert any("0.69" in item for item in bundle.evidence_confidence.caps_applied)


def test_high_safety_confidence_cap() -> None:
    bundle = judge([output("Take 10 g daily.")], [evidence(text="Traditional source description only.")])
    assert bundle.evidence_confidence.score == 0.39
    assert any("0.39" in item for item in bundle.evidence_confidence.caps_applied)


def test_model_failure_penalty() -> None:
    baseline = judge([output("Source-reported content.")], [evidence()])
    failed = judge([output("Source-reported content.")], [evidence()], model_failures=1)
    assert round(baseline.evidence_confidence.score - failed.evidence_confidence.score, 4) == 0.07
    penalty = next(item for item in failed.evidence_confidence.penalties if item.signal == "model_failure")
    assert penalty.applied_penalty == 0.07


def test_agent_self_confidence_has_no_effect() -> None:
    low = judge([output("Source-reported content.", confidence=0.0)], [evidence()])
    high = judge([output("Source-reported content.", confidence=1.0)], [evidence()])
    assert low.evidence_confidence == high.evidence_confidence


def test_api_serializes_typed_safejudge_fields_offline() -> None:
    response = client.post("/api/research/run", json={
        "question": "How does TCM teaching discuss insomnia and palpitations?",
        "condition_id": "C6",
        "retrieval_strategy": "R0",
        "active_agents": ["syndrome", "herbal"],
        "top_k": 4,
        "include_trace": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["evidence_support"] is not None
    assert data["conflict_status"] is not None
    assert data["safety_assessment"]["judge_version"] == "safejudge-deterministic-v0.1"
    assert data["evidence_confidence"]["judge_version"] == "confidence-deterministic-v0.1"
    assert data["confidence"] == data["evidence_confidence"]["score"]
    assert data["trace"]["provider_calls"] == 0
