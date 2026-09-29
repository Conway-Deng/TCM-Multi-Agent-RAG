from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_ROOT = _BACKEND.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

try:
    from backend.cross_perspective.schemas import (
        AssessmentIssue,
        CriticExecutionStatus,
        CrossPerspectiveAnswer,
        CrossPerspectiveCritique,
        CrossPerspectiveRelation,
        EvidenceReference,
        PerspectiveAgentAssessment,
        PerspectiveClaim,
        PerspectiveEvidencePacket,
        ProvenanceRecord,
    )
except ModuleNotFoundError:
    from cross_perspective.schemas import (
        AssessmentIssue,
        CriticExecutionStatus,
        CrossPerspectiveAnswer,
        CrossPerspectiveCritique,
        CrossPerspectiveRelation,
        EvidenceReference,
        PerspectiveAgentAssessment,
        PerspectiveClaim,
        PerspectiveEvidencePacket,
        ProvenanceRecord,
    )

from research.experiments.cross_perspective_advisory_ablation_v1.blinding import (
    create_blinded_record,
    make_opaque_blind_id,
    reconcile_audit,
    select_audit_blind_ids,
    select_audit_questions,
)
from research.experiments.cross_perspective_advisory_ablation_v1.condition_builder import (
    build_governance_advisory_for_condition,
    build_governance_prompt_for_condition,
    build_governance_visible_payload,
)
from research.experiments.cross_perspective_advisory_ablation_v1.execution_plan import (
    build_cell_id,
    export_execution_plan,
    generate_execution_plan,
    load_execution_plan,
    validate_execution_plan,
)
from research.experiments.cross_perspective_advisory_ablation_v1.manifest import (
    canonical_json_dumps,
    sha256_canonical_obj,
    sha256_file,
    sha256_text,
    verify_file_hash,
)
from research.experiments.cross_perspective_advisory_ablation_v1.selection import (
    SELECTION_ALGORITHM_ID,
    SELECTION_SEED,
    SOURCE_B_DYS_SC_002,
    validate_candidate_pool,
)
from research.experiments.cross_perspective_advisory_ablation_v1.preflight import (
    PreflightValidationError,
    run_preflight_checks,
    validate_advisory_visibility_matrix,
    validate_corpus_integrity,
    validate_critic_dependency,
    validate_evidence_parity_across_conditions,
    validate_governance_configuration,
    validate_no_condition_leakage,
    validate_no_historical_pooling,
    validate_protected_file_safety,
    validate_question_population,
)
from research.experiments.cross_perspective_advisory_ablation_v1.schemas import (
    AdvisoryFreezeRecord,
    AuditRecord,
    ConditionCell,
    CriticFreezeRecord,
    EvidenceFreezeRecord,
    EvidenceRetrievalRecord,
    HumanScoringRecord,
    PacketPair,
    QuestionScore,
    ScoredClaim,
    SelectedQuestion,
    TaskType,
    Topic,
)
from research.experiments.cross_perspective_advisory_ablation_v1.statistics import (
    aggregate_question_scores,
    calculate_usable_fully_grounded_coverage_yield,
    run_full_statistical_analysis,
    topic_stratified_question_bootstrap,
)


TOPICS: list[Topic] = ["cough", "dyspepsia_digestive_symptoms", "headache", "constipation"]
TASK_TYPES: list[TaskType] = ["evidence_description", "cross_perspective_synthesis", "boundary_uncertainty"]


def _make_mock_questions() -> list[SelectedQuestion]:
    """Create exactly 48 mock questions balanced across 4 topics and 3 task types."""
    questions: list[SelectedQuestion] = []
    order = 1
    for topic in TOPICS:
        for task_type in TASK_TYPES:
            for i in range(4):
                qid = f"cpaa-{topic[:4]}-{task_type[:4]}-{i+1:02d}"
                questions.append(
                    SelectedQuestion(
                        question_id=qid,
                        topic=topic,
                        task_type=task_type,
                        question_text=f"Mock clinical consultation question for {topic} ({task_type}) #{i+1}?",
                        selection_order=order,
                        frozen_timestamp="2026-09-28T00:00:00Z",
                    )
                )
                order += 1
    return questions


def _make_mock_packets() -> dict[str, PerspectiveEvidencePacket]:
    """Create mock TCM and Western evidence packets conforming to Patch 3 contract."""
    tcm_provenance = ProvenanceRecord(
        source_id="tcm-src-01",
        chunk_id="tcm-chk-01",
        title="TCM Herbal Source",
        excerpt="Licorice root harmonizes formulas and clears heat.",
    )
    tcm_claim = PerspectiveClaim(
        claim_id="tcm-cl-01",
        claim_text="Licorice clears heat and harmonizes herbs.",
        evidence_refs=[EvidenceReference(source_id="tcm-src-01", chunk_id="tcm-chk-01")],
        support_status="supported",
    )
    tcm_packet = PerspectiveEvidencePacket(
        perspective="tcm",
        available=True,
        execution_status="available",
        interpretation="Traditional Chinese Medicine perspective.",
        claims=[tcm_claim],
        uncertainty=["Pattern diagnosis requires physical evaluation."],
        missing_information=[],
        limitations=[],
        provenance=[tcm_provenance],
    )

    west_provenance = ProvenanceRecord(
        source_id="west-src-01",
        chunk_id="west-chk-01",
        title="Western Review Source",
        excerpt="Systematic review of glycyrrhizin anti-inflammatory mechanisms.",
    )
    west_claim = PerspectiveClaim(
        claim_id="west-cl-01",
        claim_text="Glycyrrhizin demonstrates anti-inflammatory properties in review data.",
        evidence_refs=[EvidenceReference(source_id="west-src-01", chunk_id="west-chk-01")],
        support_status="supported",
    )
    west_packet = PerspectiveEvidencePacket(
        perspective="western",
        available=True,
        execution_status="available",
        interpretation="Western biomedical perspective.",
        claims=[west_claim],
        uncertainty=["Clinical dosage requires standardization."],
        missing_information=[],
        limitations=[],
        provenance=[west_provenance],
    )
    return {"tcm": tcm_packet, "western": west_packet}


def _make_mock_assessments() -> dict[str, list[PerspectiveAgentAssessment]]:
    """Create mock advisory assessments for TCM and Western perspectives."""
    tcm_adv = [
        PerspectiveAgentAssessment(
            perspective="tcm",
            role="evidence_specialist",
            assessment_summary="Strong support for licorice harmonization.",
            referenced_claim_ids=["tcm-cl-01"],
            issues=[],
        ),
        PerspectiveAgentAssessment(
            perspective="tcm",
            role="coverage_auditor",
            assessment_summary="Good coverage.",
            referenced_claim_ids=[],
            issues=[],
        ),
        PerspectiveAgentAssessment(
            perspective="tcm",
            role="grounding_skeptic",
            assessment_summary="Grounding verified against source excerpt.",
            referenced_claim_ids=["tcm-cl-01"],
            issues=[],
        ),
    ]
    west_adv = [
        PerspectiveAgentAssessment(
            perspective="western",
            role="evidence_specialist",
            assessment_summary="Supported review mechanism.",
            referenced_claim_ids=["west-cl-01"],
            issues=[],
        ),
        PerspectiveAgentAssessment(
            perspective="western",
            role="coverage_auditor",
            assessment_summary="Standard review coverage.",
            referenced_claim_ids=[],
            issues=[],
        ),
        PerspectiveAgentAssessment(
            perspective="western",
            role="grounding_skeptic",
            assessment_summary="Well grounded in PMC text.",
            referenced_claim_ids=["west-cl-01"],
            issues=[],
        ),
    ]
    return {"tcm": tcm_adv, "western": west_adv}


def _make_mock_critique() -> CrossPerspectiveCritique:
    """Create mock Cross-Perspective Critic critique."""
    rel = CrossPerspectiveRelation(
        relation_type="possible_agreement",
        statement="The cited TCM and Western claims may reflect a possible agreement.",
        tcm_claim_ids=["tcm-cl-01"],
        western_claim_ids=["west-cl-01"],
    )
    return CrossPerspectiveCritique(relations=[rel])


# ==============================================================================
# 1. Manifest & Serialization Tests
# ==============================================================================

def test_manifest_canonicalization_and_hashing():
    obj1 = {"b": 2, "a": 1, "c": [3, 2, 1]}
    obj2 = {"a": 1, "c": [3, 2, 1], "b": 2}
    dump1 = canonical_json_dumps(obj1)
    dump2 = canonical_json_dumps(obj2)
    assert dump1 == dump2 == '{"a":1,"b":2,"c":[3,2,1]}'
    assert sha256_canonical_obj(obj1) == sha256_canonical_obj(obj2)


# ==============================================================================
# 2. Schemas Tests
# ==============================================================================

def test_schemas_packet_pair_validation():
    packets = _make_mock_packets()
    pair = PacketPair(
        question_id="cpaa-01",
        tcm_packet=packets["tcm"],
        western_packet=packets["western"],
        pair_hash="a" * 64,
    )
    assert pair.question_id == "cpaa-01"

    # Fails if perspective is wrong
    with pytest.raises(ValueError, match="tcm_packet perspective must be 'tcm'"):
        PacketPair(
            question_id="cpaa-01",
            tcm_packet=packets["western"],  # swapped
            western_packet=packets["western"],
            pair_hash="a" * 64,
        )


def test_human_scoring_record_yield_gate():
    # Pass gate: structurally usable, has substantive content, all claims supported
    record = HumanScoringRecord(
        evaluator_id="rev-a",
        blind_id="blind-01",
        is_structurally_usable=True,
        has_substantive_content=True,
        scored_claims=[
            ScoredClaim(
                claim_statement="Licorice relieves cough.",
                perspective="tcm",
                rating="supported",
                evidence_grounding_verified=True,
            )
        ],
        reference_units_total_m_q=4,
        reference_units_fully_conveyed=3,
        all_substantive_claims_fully_supported=True,
        primary_usable_grounded_coverage_yield=0.75,
        scoring_timestamp="2026-09-28T00:00:00Z",
    )
    assert record.primary_usable_grounded_coverage_yield == 0.75

    # If any substantive claim is partially supported, score MUST be 0.0
    with pytest.raises(ValueError, match="does not match gate calculation"):
        HumanScoringRecord(
            evaluator_id="rev-a",
            blind_id="blind-02",
            is_structurally_usable=True,
            has_substantive_content=True,
            scored_claims=[
                ScoredClaim(
                    claim_statement="Licorice may work.",
                    perspective="tcm",
                    rating="partially_supported",
                    evidence_grounding_verified=True,
                )
            ],
            reference_units_total_m_q=4,
            reference_units_fully_conveyed=3,
            all_substantive_claims_fully_supported=False,
            primary_usable_grounded_coverage_yield=0.75,  # Invalid: must be 0.0
            scoring_timestamp="2026-09-28T00:00:00Z",
        )


# ==============================================================================
# 3. Execution Plan Tests
# ==============================================================================

def test_execution_plan_structure(tmp_path):
    questions = _make_mock_questions()
    assert len(questions) == 48

    cells = generate_execution_plan(questions)
    assert len(cells) == 384

    # Check cell ID format
    assert cells[0].cell_id == f"{questions[0].question_id}__G0__rep1"
    assert cells[1].cell_id == f"{questions[0].question_id}__G0__rep2"
    assert cells[2].cell_id == f"{questions[0].question_id}__G1__rep1"

    # Validation
    validate_execution_plan(cells)

    # Export & Load
    plan_path = tmp_path / "plan.json"
    export_execution_plan(cells, plan_path)
    loaded = load_execution_plan(plan_path)
    assert len(loaded) == 384
    assert loaded[0].cell_id == cells[0].cell_id


# ==============================================================================
# 4. Condition Builder Tests
# ==============================================================================

def test_condition_builder_payloads_and_prompts():
    packets = _make_mock_packets()
    assessments = _make_mock_assessments()
    critique = _make_mock_critique()

    # G0: No local advisory, no critic
    g0_adv = build_governance_advisory_for_condition(
        "G0", assessments=assessments, critique=critique, packets=packets
    )
    assert g0_adv["critic_relations"] == []
    assert g0_adv["perspective_advisory"]["tcm"] == []
    assert g0_adv["perspective_advisory"]["western"] == []

    # G1: Local advisory, no critic
    g1_adv = build_governance_advisory_for_condition(
        "G1", assessments=assessments, critique=critique, packets=packets
    )
    assert g1_adv["critic_relations"] == []
    assert len(g1_adv["perspective_advisory"]["tcm"]) == 3
    assert len(g1_adv["perspective_advisory"]["western"]) == 3

    # G2: No local advisory, critic present
    g2_adv = build_governance_advisory_for_condition(
        "G2", assessments=assessments, critique=critique, packets=packets
    )
    assert len(g2_adv["critic_relations"]) == 1
    assert g2_adv["perspective_advisory"]["tcm"] == []
    assert g2_adv["perspective_advisory"]["western"] == []

    # G3: Local advisory and critic present
    g3_adv = build_governance_advisory_for_condition(
        "G3", assessments=assessments, critique=critique, packets=packets
    )
    assert len(g3_adv["critic_relations"]) == 1
    assert len(g3_adv["perspective_advisory"]["tcm"]) == 3
    assert len(g3_adv["perspective_advisory"]["western"]) == 3

    # Section A parity across all conditions
    payloads = {
        cond: build_governance_visible_payload(
            cond, packets=packets, assessments=assessments, critique=critique
        )
        for cond in ("G0", "G1", "G2", "G3")
    }
    validate_evidence_parity_across_conditions(payloads)
    validate_advisory_visibility_matrix(payloads)

    # Prompt generation and condition leakage test
    for cond in ("G0", "G1", "G2", "G3"):
        prompt = build_governance_prompt_for_condition(
            "What is the role of licorice in cough?",
            cond,
            packets=packets,
            assessments=assessments,
            critique=critique,
        )
        validate_no_condition_leakage(prompt)
        assert "=== SECTION A: EVIDENCE PACKETS" in prompt
        assert "=== SECTION B: ADVISORY CONTEXT" in prompt


# ==============================================================================
# 5. Preflight & Safety Tests
# ==============================================================================

def test_preflight_corpus_integrity():
    # Tests actual local research corpora
    report = validate_corpus_integrity()
    assert report["tcm_corpus_sha256"] == "316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9"
    assert report["western_corpus_sha256"] == "8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b"


def test_preflight_governance_configuration():
    gov_report = validate_governance_configuration()
    assert gov_report["model"] == "THUDM/GLM-4-9B-0414"
    assert gov_report["timeout"] == 90.0
    assert gov_report["max_tokens"] == 2400


def test_preflight_question_population():
    questions = _make_mock_questions()
    validate_question_population(questions)

    # Imbalance raises PreflightValidationError
    unbalanced = questions[:-1] + [questions[0].model_copy(update={"question_id": "cpaa-dup"})]
    with pytest.raises(PreflightValidationError):
        validate_question_population(unbalanced)


def test_preflight_protected_file_safety():
    # Attempting to access protected paths raises an error
    with pytest.raises(PreflightValidationError, match="CRITICAL SAFETY VIOLATION"):
        validate_protected_file_safety(["research/experiments/western_semantic_followup_v0_2/stage_c2_blind_key.csv"])

    with pytest.raises(PreflightValidationError, match="CRITICAL SAFETY VIOLATION"):
        validate_protected_file_safety(["scratch/temp_file.txt"])


def test_preflight_no_historical_pooling():
    # Valid study ID passes
    validate_no_historical_pooling("cross-perspective-advisory-ablation-v1", ["cpaa-q01", "cpaa-q02"])

    # Historical question ID raises error
    with pytest.raises(PreflightValidationError, match="Historical study data leakage"):
        validate_no_historical_pooling("cross-perspective-advisory-ablation-v1", ["tcmc-v1-001"])

    with pytest.raises(PreflightValidationError, match="Historical study data leakage"):
        validate_no_historical_pooling("cross-perspective-advisory-ablation-v1", ["west-formal-01"])


def test_preflight_critic_dependency_hash_mismatch():
    packets = _make_mock_packets()
    evidence_pair_hash = "a" * 64
    advisory_freeze_hash = "b" * 64
    mismatched_hash = "f" * 64

    # Synthetic evidence freeze
    _evidence_freeze = EvidenceFreezeRecord(
        question_id="cpaa-q01",
        tcm_retrieval=EvidenceRetrievalRecord(
            perspective="tcm",
            query="cough licorice",
            corpus_sha256="1" * 64,
            retrieval_hash="2" * 64,
        ),
        western_retrieval=EvidenceRetrievalRecord(
            perspective="western",
            query="cough licorice",
            corpus_sha256="3" * 64,
            retrieval_hash="4" * 64,
        ),
        retrieval_timestamp="2026-09-28T00:00:00Z",
        freeze_hash=evidence_pair_hash,
    )
    packet_pair = PacketPair(
        question_id="cpaa-q01",
        tcm_packet=packets["tcm"],
        western_packet=packets["western"],
        pair_hash=evidence_pair_hash,
    )

    # Synthetic advisory freeze
    advisory_record = AdvisoryFreezeRecord(
        question_id="cpaa-q01",
        evidence_pair_hash=evidence_pair_hash,
        tcm_assessments=[],
        western_assessments=[],
        failed_roles=[],
        provider_events=[],
        freeze_hash=advisory_freeze_hash,
    )

    # Synthetic critic freeze with deliberately mismatched advisory_freeze_hash
    critic_record = CriticFreezeRecord(
        question_id="cpaa-q01",
        evidence_pair_hash=evidence_pair_hash,
        advisory_freeze_hash=mismatched_hash,  # Deliberate mismatch
        critic_status="completed",
        critique=None,
        critic_model="deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
        freeze_hash="d" * 64,
    )

    # Matching advisory_freeze_hash passes validation cleanly
    valid_critic = critic_record.model_copy(update={"advisory_freeze_hash": advisory_freeze_hash})
    validate_critic_dependency(valid_critic, advisory_record, packet_pair)

    # Mismatched advisory_freeze_hash must be rejected with PreflightValidationError
    with pytest.raises(PreflightValidationError, match="Critic record advisory_freeze_hash does not match advisory record hash"):
        validate_critic_dependency(critic_record, advisory_record, packet_pair)


# ==============================================================================
# 6. Blinding & Audit Reconciliation Tests
# ==============================================================================

def test_blinding_opaque_id_and_key():
    cell = ConditionCell(
        cell_id="cpaa-q01__G3__rep1",
        question_id="cpaa-q01",
        topic="cough",
        task_type="evidence_description",
        condition="G3",
        repetition=1,
    )
    q = SelectedQuestion(
        question_id="cpaa-q01",
        topic="cough",
        task_type="evidence_description",
        question_text="What is the evidence for cough?",
        selection_order=1,
        frozen_timestamp="2026-09-28T00:00:00Z",
    )
    ans = {
        "overall_summary": "Licorice demonstrates cough relief properties.",
        "overall_supporting_claim_ids": ["tcm-cl-01"],
    }
    blinded, key = create_blinded_record(cell, q, ans)

    assert blinded.blind_id.startswith("blind-")
    assert key.blind_id == blinded.blind_id
    assert key.condition == "G3"
    assert key.repetition == 1
    # Condition must NOT be present in blinded record
    assert not hasattr(blinded, "condition")
    assert not hasattr(blinded, "repetition")


def test_audit_selection_and_reconciliation_gate():
    questions = _make_mock_questions()
    audit_qs = select_audit_questions(questions, seed=20260928)
    assert len(audit_qs) == 12

    # Verify 3 questions per topic
    by_topic = {}
    for q in audit_qs:
        by_topic[q.topic] = by_topic.get(q.topic, 0) + 1
    assert all(count == 3 for count in by_topic.values())

    # Build mock keys for all 384 cells
    cells = generate_execution_plan(questions)
    all_keys = [
        create_blinded_record(cell, questions[0], {"overall_summary": "Test"})[1]
        for cell in cells
    ]
    audit_blind_ids = select_audit_blind_ids(audit_qs, all_keys)
    assert len(audit_blind_ids) == 96

    # Test audit reconciliation gate: <=10% changes -> PASSED_AUDIT_GATE
    rev_a: dict[str, HumanScoringRecord] = {}
    rev_b: dict[str, AuditRecord] = {}
    reconciled: dict[str, float] = {}

    for bid in audit_blind_ids:
        rev_a[bid] = HumanScoringRecord(
            evaluator_id="rev-a",
            blind_id=bid,
            is_structurally_usable=True,
            has_substantive_content=True,
            scored_claims=[ScoredClaim(claim_statement="s", perspective="tcm", rating="supported", evidence_grounding_verified=True)],
            reference_units_total_m_q=4,
            reference_units_fully_conveyed=2,
            all_substantive_claims_fully_supported=True,
            primary_usable_grounded_coverage_yield=0.5,
            scoring_timestamp="2026-09-28T00:00:00Z",
        )
        rev_b[bid] = AuditRecord(
            auditor_id="rev-b",
            blind_id=bid,
            is_structurally_usable=True,
            has_substantive_content=True,
            scored_claims=[ScoredClaim(claim_statement="s", perspective="tcm", rating="supported", evidence_grounding_verified=True)],
            reference_units_total_m_q=4,
            reference_units_fully_conveyed=2,
            all_substantive_claims_fully_supported=True,
            primary_usable_grounded_coverage_yield=0.5,
            audit_timestamp="2026-09-28T00:00:00Z",
        )
        reconciled[bid] = 0.5  # 0 changes initially

    # Case 1: 5 changes out of 96 (5.2% <= 10%)
    for bid in list(audit_blind_ids)[:5]:
        reconciled[bid] = 0.75
    records, summary = reconcile_audit(rev_a, rev_b, reconciled)
    assert summary.reconciled_outputs_changed_count == 5
    assert not summary.full_second_review_required
    assert summary.audit_status == "PASSED_AUDIT_GATE"

    # Case 2: 12 changes out of 96 (12.5% > 10%) -> triggers FULL_SECOND_REVIEW_REQUIRED
    for bid in list(audit_blind_ids)[:12]:
        reconciled[bid] = 0.75
    records, summary = reconcile_audit(rev_a, rev_b, reconciled)
    assert summary.reconciled_outputs_changed_count == 12
    assert summary.full_second_review_required
    assert summary.audit_status == "FULL_SECOND_REVIEW_REQUIRED"


# ==============================================================================
# 7. Primary Endpoint & Statistics Tests
# ==============================================================================

def test_usable_fully_grounded_coverage_yield_gate():
    # 1. Clean fully supported output
    claims = [
        ScoredClaim(claim_statement="Claim 1", perspective="tcm", rating="supported", evidence_grounding_verified=True),
        ScoredClaim(claim_statement="Claim 2", perspective="western", rating="supported", evidence_grounding_verified=True),
    ]
    score = calculate_usable_fully_grounded_coverage_yield(
        is_structurally_usable=True,
        has_substantive_content=True,
        scored_claims=claims,
        reference_units_total_m_q=4,
        reference_units_fully_conveyed=3,
    )
    assert score == 0.75

    # 2. Terminal failure -> 0
    assert calculate_usable_fully_grounded_coverage_yield(
        is_structurally_usable=False,
        has_substantive_content=True,
        scored_claims=claims,
        reference_units_total_m_q=4,
        reference_units_fully_conveyed=3,
    ) == 0.0

    # 3. Partially supported claim -> fails full-grounding gate -> 0
    mixed_claims = [
        ScoredClaim(claim_statement="Claim 1", perspective="tcm", rating="supported", evidence_grounding_verified=True),
        ScoredClaim(claim_statement="Claim 2", perspective="western", rating="partially_supported", evidence_grounding_verified=True),
    ]
    assert calculate_usable_fully_grounded_coverage_yield(
        is_structurally_usable=True,
        has_substantive_content=True,
        scored_claims=mixed_claims,
        reference_units_total_m_q=4,
        reference_units_fully_conveyed=3,
    ) == 0.0

    # 4. Unsupported claim -> 0
    unsupported_claims = [
        ScoredClaim(claim_statement="Claim 1", perspective="tcm", rating="unsupported", evidence_grounding_verified=False),
    ]
    assert calculate_usable_fully_grounded_coverage_yield(
        is_structurally_usable=True,
        has_substantive_content=True,
        scored_claims=unsupported_claims,
        reference_units_total_m_q=4,
        reference_units_fully_conveyed=3,
    ) == 0.0


def test_primary_yield_gate_contradicted_claim():
    """Demonstrate explicitly that a contradicted substantive claim fails the full-grounding gate (returns 0.0)."""
    contradicted_claims = [
        ScoredClaim(
            claim_statement="Contradicted herbal efficacy claim",
            perspective="tcm",
            rating="contradicted",
            evidence_grounding_verified=False,
            rationale="Directly contradicted by reference evidence corpus.",
        ),
    ]

    yield_score = calculate_usable_fully_grounded_coverage_yield(
        is_structurally_usable=True,
        has_substantive_content=True,
        scored_claims=contradicted_claims,
        reference_units_total_m_q=4,
        reference_units_fully_conveyed=3,
    )
    assert yield_score == 0.0

    # Even with grounded flag set or mixed with supported claims, contradiction gates to 0.0
    mixed_contradicted = [
        ScoredClaim(
            claim_statement="Fully supported claim",
            perspective="western",
            rating="supported",
            evidence_grounding_verified=True,
        ),
        ScoredClaim(
            claim_statement="Contradicted claim",
            perspective="tcm",
            rating="contradicted",
            evidence_grounding_verified=True,
        ),
    ]
    assert calculate_usable_fully_grounded_coverage_yield(
        is_structurally_usable=True,
        has_substantive_content=True,
        scored_claims=mixed_contradicted,
        reference_units_total_m_q=4,
        reference_units_fully_conveyed=4,
    ) == 0.0


def test_primary_yield_gate_zero_substantive_claims():
    """Demonstrate that zero substantive claims (has_substantive_content=False or scored_claims=[]) yields 0.0."""
    supported_claims = [
        ScoredClaim(
            claim_statement="Supported claim",
            perspective="western",
            rating="supported",
            evidence_grounding_verified=True,
        ),
    ]

    # Case 1: has_substantive_content = False
    assert calculate_usable_fully_grounded_coverage_yield(
        is_structurally_usable=True,
        has_substantive_content=False,
        scored_claims=supported_claims,
        reference_units_total_m_q=4,
        reference_units_fully_conveyed=4,
    ) == 0.0

    # Case 2: scored_claims = []
    assert calculate_usable_fully_grounded_coverage_yield(
        is_structurally_usable=True,
        has_substantive_content=True,
        scored_claims=[],
        reference_units_total_m_q=4,
        reference_units_fully_conveyed=4,
    ) == 0.0

    # Both has_substantive_content = False and scored_claims = []
    assert calculate_usable_fully_grounded_coverage_yield(
        is_structurally_usable=True,
        has_substantive_content=False,
        scored_claims=[],
        reference_units_total_m_q=4,
        reference_units_fully_conveyed=4,
    ) == 0.0


def test_statistics_synthetic_question_bootstrap():
    questions = _make_mock_questions()
    q_topics = {q.question_id: q.topic for q in questions}
    q_tasks = {q.question_id: q.task_type for q in questions}

    # Generate synthetic scores with nested repetitions
    # G0: mean ~0.20, G1: ~0.30, G2: ~0.35, G3: ~0.50
    question_outputs: dict[tuple[str, str], list[float]] = {}
    for i, q in enumerate(questions):
        base = 0.15 + (i % 5) * 0.02
        question_outputs[(q.question_id, "G0")] = [base, base + 0.02]
        question_outputs[(q.question_id, "G1")] = [base + 0.10, base + 0.12]
        question_outputs[(q.question_id, "G2")] = [base + 0.15, base + 0.17]
        question_outputs[(q.question_id, "G3")] = [base + 0.30, base + 0.32]

    # Aggregate repetitions (nested repeated observations)
    q_scores = aggregate_question_scores(question_outputs, q_topics, q_tasks)
    assert len(q_scores) == 48

    # Run topic-stratified question bootstrap (fast test with 500 resamples for speed)
    g0_m, g3_m, diff_m, ci_low, ci_high = topic_stratified_question_bootstrap(
        q_scores,
        left_condition="G0",
        right_condition="G3",
        resamples=500,
        seed=20260928,
    )
    assert g3_m > g0_m
    assert ci_low <= diff_m <= ci_high
    assert ci_low > 0.25  # G3 is clearly higher by ~0.30

    # Determinism: same seed produces exact same CI
    g0_m2, g3_m2, diff_m2, ci_low2, ci_high2 = topic_stratified_question_bootstrap(
        q_scores,
        left_condition="G0",
        right_condition="G3",
        resamples=500,
        seed=20260928,
    )
    assert ci_low == ci_low2
    assert ci_high == ci_high2

    # Run full analysis record
    analysis = run_full_statistical_analysis(
        q_scores,
        resamples=500,
        seed=20260928,
    )
    assert analysis.primary_comparison_name == "G3 - G0"
    assert analysis.sample_size_questions == 48
    assert analysis.total_cells == 384
    assert len(analysis.secondary_comparisons) == 4
    assert all(sec.is_exploratory for sec in analysis.secondary_comparisons)


# ==============================================================================
# 8. Candidate Pool Tests (Phase 0G Freeze)
# ==============================================================================

def test_candidate_pool_72_count_contract_and_manifest():
    """Verify 72-candidate pool contract, strata balance, review status, and manifest hashes."""
    pool_path = _ROOT / "research" / "experiments" / "cross_perspective_advisory_ablation_v1" / "candidate_pool_v1.jsonl"
    manifest_path = _ROOT / "research" / "experiments" / "cross_perspective_advisory_ablation_v1" / "candidate_pool_v1_manifest.json"

    assert pool_path.is_file(), f"Missing candidate pool file: {pool_path}"
    assert manifest_path.is_file(), f"Missing candidate pool manifest: {manifest_path}"

    with pool_path.open("r", encoding="utf-8") as f:
        candidates = [json.loads(line) for line in f if line.strip()]

    assert len(candidates) == 72
    validate_candidate_pool(candidates)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["candidate_count"] == 72
    assert manifest["independent_review_completion_status"] == "ALL_PASS"
    assert manifest["reserved_selection_seed"] == SELECTION_SEED
    assert manifest["selection_algorithm_id"] == SELECTION_ALGORITHM_ID

    # Hash verification
    actual_byte_sha = sha256_file(pool_path)
    actual_canonical_sha = sha256_canonical_obj(candidates)
    assert manifest["candidate_pool_byte_sha256"] == actual_byte_sha
    assert manifest["candidate_pool_canonical_sha256"] == actual_canonical_sha


def test_candidate_pool_revised_dys_sc_002_identity():
    """Verify that CPAA1-DYS-SC-002 matches the approved revised SOURCE B record exactly."""
    pool_path = _ROOT / "research" / "experiments" / "cross_perspective_advisory_ablation_v1" / "candidate_pool_v1.jsonl"
    with pool_path.open("r", encoding="utf-8") as f:
        candidates = [json.loads(line) for line in f if line.strip()]

    dys_cand = [c for c in candidates if c["candidate_id"] == "CPAA1-DYS-SC-002"][0]
    for key, expected_val in SOURCE_B_DYS_SC_002.items():
        assert dys_cand[key] == expected_val, f"Mismatch in field {key!r}: got {dys_cand[key]!r}, expected {expected_val!r}"
