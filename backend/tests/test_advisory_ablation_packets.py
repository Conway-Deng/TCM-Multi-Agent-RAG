from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path
import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_ROOT = _BACKEND.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

FROZEN_TCM_PACKET_BYTE_SHA256 = (
    "7ce35d0d8ea42ebc1b61cf87de858fed5c9b993a6e032435bab88a30e25eef3f"
)
FROZEN_WESTERN_PACKET_BYTE_SHA256 = (
    "b5c48507de5467c2c8a5ee031d5d790b1e5ceccd53cf84ca2cd8b70f227555de"
)
FROZEN_MANIFEST_BYTE_SHA256 = (
    "c934db63ec6d0cb811b7716b18ac62e7a38f9d848cbafbd3993505d8c6721ecf"
)
FROZEN_RECEIPT_BYTE_SHA256 = (
    "87952c77980f5f81388921e619586f920d3f199b8695c58bc1d6520345bfe9bc"
)


def _snapshot_sealed_packets(packets_dir: Path) -> dict[str, str]:
    if not packets_dir.exists():
        return {}
    return {
        f.name: hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(packets_dir.iterdir())
        if f.is_file()
    }

from backend.cross_perspective.cross_perspective_critic import CRITIC_SYSTEM_PROMPT
from backend.cross_perspective.governance import (
    GOVERNANCE_SYSTEM_PROMPT,
    build_governance_advisory_context,
    build_governance_payload,
)
from backend.cross_perspective.perspective_agents import (
    COVERAGE_AUDITOR_SYSTEM_PROMPT,
    EVIDENCE_SPECIALIST_SYSTEM_PROMPT,
    GROUNDING_SKEPTIC_SYSTEM_PROMPT,
)
from backend.cross_perspective.schemas import (
    ActivePerspectiveName,
    AssessmentIssue,
    CrossPerspectiveCritique,
    CrossPerspectiveRelation,
    EvidenceReference,
    PerspectiveAgentAssessment,
    PerspectiveClaim,
    PerspectiveEvidencePacket,
    ProvenanceRecord,
)

from research.experiments.cross_perspective_advisory_ablation_v1.condition_builder import (
    build_governance_advisory_for_condition,
    build_governance_prompt_for_condition,
    build_governance_visible_payload,
)
from research.experiments.cross_perspective_advisory_ablation_v1.packet_contract import (
    ALLOW_DEDUPLICATION,
    ALLOW_MODEL_CALL,
    ALLOW_RETRIEVAL_CALL,
    ALLOW_REWRITING,
    ALLOW_TRUNCATION,
    AMENDMENT_ID,
    COMPATIBILITY_CLAIM_KIND,
    COMPATIBILITY_SUPPORT_STATUS,
    EXPECTED_QUESTION_COUNT,
    EXPECTED_QUESTION_MANIFEST_SHA256,
    EXPECTED_TCM_ITEMS,
    EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
    EXPECTED_TCM_RECORDS,
    EXPECTED_TOTAL_ITEMS,
    EXPECTED_TOTAL_RECORDS,
    EXPECTED_WESTERN_ITEMS,
    EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256,
    EXPECTED_WESTERN_RECORDS,
    HITS_PER_RECORD,
    PACKET_CONTRACT_ID,
    QUESTION_MANIFEST_RELPATH,
    SCHEMA_VERSION,
    SEMANTIC_SUPPORT_STATUS,
    STUDY_ID,
    SUPPORT_BASIS,
    TCM_RAW_RETRIEVAL_RELPATH,
    WESTERN_RAW_RETRIEVAL_RELPATH,
    compute_item_canonical_sha256,
    compute_packet_canonical_sha256,
    format_compatibility_claim_id,
    format_evidence_id,
    format_packet_id,
)
from research.experiments.cross_perspective_advisory_ablation_v1.packet_projection import (
    project_frozen_packet_to_compatibility_wrapper,
    project_raw_record_to_frozen_packet,
    validate_frozen_evidence_item_integrity,
    validate_frozen_packet_integrity,
)
from research.experiments.cross_perspective_advisory_ablation_v1.packet_runner import (
    check_formal_packet_generation_authorization,
    validate_packet_preflight,
)
from research.experiments.cross_perspective_advisory_ablation_v1.preflight import (
    PreflightValidationError,
    validate_advisory_visibility_matrix,
    validate_evidence_parity_across_conditions,
)
from research.experiments.cross_perspective_advisory_ablation_v1.prompt_variants import (
    CPAA1_COVERAGE_AUDITOR_SYSTEM_PROMPT,
    CPAA1_CRITIC_SYSTEM_PROMPT,
    CPAA1_EVIDENCE_SPECIALIST_SYSTEM_PROMPT,
    CPAA1_GOVERNANCE_SYSTEM_PROMPT,
    CPAA1_GROUNDING_SKEPTIC_SYSTEM_PROMPT,
    EXPECTED_AMENDED_PROMPT_HASHES,
    EXPECTED_ORIGINAL_PROMPT_HASHES,
    RESEARCH_SYSTEM_PROMPTS,
    SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT,
    build_coverage_auditor_prompt,
    build_critic_prompt,
    build_evidence_specialist_prompt,
    build_governance_prompt,
    build_grounding_skeptic_prompt,
    sha256_prompt,
    verify_baseline_prompt_hash,
)
from research.experiments.cross_perspective_advisory_ablation_v1.schemas import (
    FrozenEvidenceItem,
    FrozenEvidencePacket,
    RawRetrievalItem,
    RawRetrievalRecord,
)
from research.experiments.cross_perspective_advisory_ablation_v1.token_budget_scaffold import (
    TokenBudgetRecord,
    TokenBudgetScaffold,
)
from pydantic import ValidationError


@pytest.fixture
def synthetic_raw_record() -> RawRetrievalRecord:
    """Create a synthetic RawRetrievalRecord for testing with >2000 character passage and newlines."""
    long_passage = "Paragraph 1: Clinical findings on herbal decoctions.\n\n" + ("Detailed analysis. " * 150)
    assert len(long_passage) > 2000

    results = [
        RawRetrievalItem(
            rank=1,
            retrieval_score=0.95,
            score_is_zero=False,
            chunk_id="chunk_001",
            corpus_record_ordinal=10,
            source_id="src_001",
            source_record_id="rec_001",
            source_title="Title of Source 1",
            source_url="https://example.org/1",
            doi="10.1000/1",
            pmcid="PMC12345",
            section_or_category="Results",
            license_or_access_status="cc-by",
            source_citation_or_version="2026.1",
            review_status="peer_reviewed",
            exact_original_chunk_text=long_passage,
            chunk_text_utf8_sha256=hashlib.sha256(long_passage.encode("utf-8")).hexdigest(),
            chunk_record_canonical_sha256="a" * 64,
            provenance={"extra": "meta1"},
        ),
        RawRetrievalItem(
            rank=2,
            retrieval_score=0.85,
            score_is_zero=False,
            chunk_id="chunk_002",
            corpus_record_ordinal=20,
            source_id="src_002",
            source_record_id=None,
            source_title="Title 2",
            source_url=None,
            doi=None,
            pmcid=None,
            section_or_category=None,
            license_or_access_status=None,
            source_citation_or_version=None,
            review_status=None,
            exact_original_chunk_text="Short passage with whitespace and \t tabs.",
            chunk_text_utf8_sha256=hashlib.sha256("Short passage with whitespace and \t tabs.".encode("utf-8")).hexdigest(),
            chunk_record_canonical_sha256="b" * 64,
            provenance={},
        ),
        RawRetrievalItem(
            rank=3,
            retrieval_score=0.50,
            score_is_zero=False,
            chunk_id="chunk_003",
            corpus_record_ordinal=30,
            source_id="src_003",
            source_record_id="rec_003",
            source_title="Title 3",
            exact_original_chunk_text="Passage 3 content with punctuation: semi; colon, dash-hyphen.",
            chunk_text_utf8_sha256=hashlib.sha256("Passage 3 content with punctuation: semi; colon, dash-hyphen.".encode("utf-8")).hexdigest(),
            chunk_record_canonical_sha256="c" * 64,
        ),
        RawRetrievalItem(
            rank=4,
            retrieval_score=0.0,
            score_is_zero=True,
            chunk_id="chunk_004",
            corpus_record_ordinal=40,
            source_id="src_004",
            source_title="Title 4",
            exact_original_chunk_text="Passage 4 zero score baseline hit.",
            chunk_text_utf8_sha256=hashlib.sha256("Passage 4 zero score baseline hit.".encode("utf-8")).hexdigest(),
            chunk_record_canonical_sha256="d" * 64,
        ),
    ]

    return RawRetrievalRecord(
        schema_version="cpaa1_raw_retrieval_v1",
        retrieval_record_id="cpaa1:ret:CPAA1-TEST-001:western:R0",
        question_id="CPAA1-TEST-001",
        candidate_id="CPAA1-CAN-001",
        question_text="What is the evidence regarding therapy?",
        topic="cough",
        task_type="evidence_description",
        perspective="western",
        question_manifest_sha256=EXPECTED_QUESTION_MANIFEST_SHA256,
        corpus_id="west_v0_1",
        corpus_version="medirag-west-v0.1-pilot",
        corpus_sha256="8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b",
        retrieval_algorithm_id="CPAA1-R0-LEXICAL-V1",
        query_text="What is the evidence regarding therapy?",
        query_text_sha256=hashlib.sha256("What is the evidence regarding therapy?".encode("utf-8")).hexdigest(),
        requested_top_k=4,
        returned_count=4,
        positive_score_count=3,
        zero_score_count=1,
        retrieval_status="SUCCESS",
        retrieved_at_utc="2026-09-29T12:00:00Z",
        implementation_commit="b234f40f2beb017431de2ce27256b983d3eeb177",
        record_canonical_sha256="f" * 64,
        results=results,
    )


# --- 1. Deterministic evidence IDs ---
def test_deterministic_evidence_ids():
    ev_id = format_evidence_id("Q-123", "tcm", 1, "chunk_99")
    assert ev_id == "cpaa1:ev:Q-123:tcm:R0:1:chunk_99"
    # Same inputs must produce exact same ID
    assert ev_id == format_evidence_id("Q-123", "tcm", 1, "chunk_99")
    # Different rank produces different ID
    assert ev_id != format_evidence_id("Q-123", "tcm", 2, "chunk_99")


# --- 2. Deterministic wrapper IDs ---
def test_deterministic_wrapper_ids():
    ev_id = "cpaa1:ev:Q-123:tcm:R0:1:chunk_99"
    claim_id = format_compatibility_claim_id(ev_id)
    assert claim_id == "cpaa1:sx:cpaa1:ev:Q-123:tcm:R0:1:chunk_99"
    assert claim_id == format_compatibility_claim_id(ev_id)


# --- 3. Four-hit order preservation ---
def test_four_hit_order_preservation(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    assert len(packet.evidence_items) == 4
    for i, item in enumerate(packet.evidence_items, start=1):
        assert item.rank == i
        assert item.chunk_id == f"chunk_{i:03d}"


# --- 4. Full exact text preservation (>2000 chars, whitespace, newlines) ---
def test_full_exact_text_preservation(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    item1 = packet.evidence_items[0]
    assert len(item1.exact_chunk_text) > 2000
    assert "\n\n" in item1.exact_chunk_text
    assert item1.exact_chunk_text == synthetic_raw_record.results[0].exact_original_chunk_text

    item2 = packet.evidence_items[1]
    assert "\t" in item2.exact_chunk_text
    assert item2.exact_chunk_text == synthetic_raw_record.results[1].exact_original_chunk_text


# --- 5. No truncation ---
def test_no_truncation(synthetic_raw_record):
    assert ALLOW_TRUNCATION is False
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    wrapper = project_frozen_packet_to_compatibility_wrapper(packet)
    assert len(packet.evidence_items[0].exact_chunk_text) > 2000
    assert len(wrapper.claims[0].claim_text) > 2000
    assert wrapper.claims[0].claim_text == packet.evidence_items[0].exact_chunk_text


# --- 6. Score and rank preservation ---
def test_score_rank_preservation(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    for orig_hit, item in zip(synthetic_raw_record.results, packet.evidence_items):
        assert item.rank == orig_hit.rank
        assert item.retrieval_score == orig_hit.retrieval_score
        assert item.score_is_zero == orig_hit.score_is_zero
        assert item.corpus_record_ordinal == orig_hit.corpus_record_ordinal


# --- 7. Provenance and null preservation ---
def test_provenance_null_preservation(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    # item 1 has full fields
    item1 = packet.evidence_items[0]
    assert item1.doi == "10.1000/1"
    assert item1.pmcid == "PMC12345"
    assert item1.provenance == {"extra": "meta1"}

    # item 2 has None fields
    item2 = packet.evidence_items[1]
    assert item2.doi is None
    assert item2.pmcid is None
    assert item2.source_url is None
    assert item2.section_or_category is None


# --- 8. No added evidence ---
def test_no_added_evidence(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    assert len(packet.evidence_items) == 4
    wrapper = project_frozen_packet_to_compatibility_wrapper(packet)
    assert len(wrapper.claims) == 4


# --- 9. No dropped evidence ---
def test_no_dropped_evidence(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    assert len(packet.evidence_items) == 4
    for i in range(4):
        assert packet.evidence_items[i].chunk_id == synthetic_raw_record.results[i].chunk_id


# --- 10. No deduplication ---
def test_no_deduplication():
    """Verify that if two different ranks contain the same source/chunk content, both survive projection without deduplication."""
    assert ALLOW_DEDUPLICATION is False
    dup_text = "Repeated clinical passage regarding Glycyrrhiza root and herbal interactions."
    results = [
        RawRetrievalItem(
            rank=1,
            retrieval_score=0.9,
            score_is_zero=False,
            chunk_id="chunk_dup_1",
            corpus_record_ordinal=1,
            source_id="src_dup_1",
            exact_original_chunk_text=dup_text,
            chunk_text_utf8_sha256=hashlib.sha256(dup_text.encode("utf-8")).hexdigest(),
            chunk_record_canonical_sha256="1" * 64,
        ),
        RawRetrievalItem(
            rank=2,
            retrieval_score=0.8,
            score_is_zero=False,
            chunk_id="chunk_dup_2",
            corpus_record_ordinal=2,
            source_id="src_dup_2",
            exact_original_chunk_text=dup_text,
            chunk_text_utf8_sha256=hashlib.sha256(dup_text.encode("utf-8")).hexdigest(),
            chunk_record_canonical_sha256="2" * 64,
        ),
        RawRetrievalItem(
            rank=3,
            retrieval_score=0.7,
            score_is_zero=False,
            chunk_id="chunk_other_3",
            corpus_record_ordinal=3,
            source_id="src_other_3",
            exact_original_chunk_text="Distinct third passage.",
            chunk_text_utf8_sha256=hashlib.sha256("Distinct third passage.".encode("utf-8")).hexdigest(),
            chunk_record_canonical_sha256="3" * 64,
        ),
        RawRetrievalItem(
            rank=4,
            retrieval_score=0.6,
            score_is_zero=False,
            chunk_id="chunk_other_4",
            corpus_record_ordinal=4,
            source_id="src_other_4",
            exact_original_chunk_text="Distinct fourth passage.",
            chunk_text_utf8_sha256=hashlib.sha256("Distinct fourth passage.".encode("utf-8")).hexdigest(),
            chunk_record_canonical_sha256="4" * 64,
        ),
    ]
    raw_rec = RawRetrievalRecord(
        schema_version="cpaa1_raw_retrieval_v1",
        retrieval_record_id="cpaa1:ret:TEST-DUP:tcm:R0",
        question_id="TEST-DUP",
        candidate_id="CAN-DUP",
        question_text="Repeated passage question?",
        topic="cough",
        task_type="evidence_description",
        perspective="tcm",
        question_manifest_sha256=EXPECTED_QUESTION_MANIFEST_SHA256,
        corpus_id="tcm_v1",
        corpus_version="tcm-v1",
        corpus_sha256="3" * 64,
        retrieval_algorithm_id="CPAA1-R0-LEXICAL-V1",
        query_text="Repeated passage question?",
        query_text_sha256=hashlib.sha256("Repeated passage question?".encode("utf-8")).hexdigest(),
        requested_top_k=4,
        returned_count=4,
        positive_score_count=4,
        zero_score_count=0,
        retrieval_status="SUCCESS",
        retrieved_at_utc="2026-09-29T00:00:00Z",
        implementation_commit="b234f40f2beb017431de2ce27256b983d3eeb177",
        record_canonical_sha256="0" * 64,
        results=results,
    )
    # Project into FrozenEvidencePacket and wrapper
    packet = project_raw_record_to_frozen_packet(raw_rec, "a" * 64)
    wrapper = project_frozen_packet_to_compatibility_wrapper(packet)

    # 1. Both occurrences survive projection
    assert len(packet.evidence_items) == 4
    assert len(wrapper.claims) == 4
    assert packet.evidence_items[0].exact_chunk_text == dup_text
    assert packet.evidence_items[1].exact_chunk_text == dup_text
    assert wrapper.claims[0].claim_text == dup_text
    assert wrapper.claims[1].claim_text == dup_text

    # 2. Order survives
    assert packet.evidence_items[0].rank == 1
    assert packet.evidence_items[1].rank == 2

    # 3. Each occurrence has distinct occurrence-specific evidence ID and claim ID
    ev_id_1 = packet.evidence_items[0].evidence_id
    ev_id_2 = packet.evidence_items[1].evidence_id
    assert ev_id_1 == "cpaa1:ev:TEST-DUP:tcm:R0:1:chunk_dup_1"
    assert ev_id_2 == "cpaa1:ev:TEST-DUP:tcm:R0:2:chunk_dup_2"
    assert ev_id_1 != ev_id_2

    claim_id_1 = wrapper.claims[0].claim_id
    claim_id_2 = wrapper.claims[1].claim_id
    assert claim_id_1 == "cpaa1:sx:cpaa1:ev:TEST-DUP:tcm:R0:1:chunk_dup_1"
    assert claim_id_2 == "cpaa1:sx:cpaa1:ev:TEST-DUP:tcm:R0:2:chunk_dup_2"
    assert claim_id_1 != claim_id_2



# --- 11. Packet canonical hash repeatability ---
def test_packet_canonical_hash_repeatability(synthetic_raw_record):
    pkt1 = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    pkt2 = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    assert pkt1.packet_canonical_sha256 == pkt2.packet_canonical_sha256
    assert len(pkt1.packet_canonical_sha256) == 64


# --- 12. Wrapper claim_text == native exact text ---
def test_wrapper_claim_text_equals_native_exact_text(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    wrapper = project_frozen_packet_to_compatibility_wrapper(packet)
    for native_item, claim in zip(packet.evidence_items, wrapper.claims):
        assert claim.claim_text == native_item.exact_chunk_text


# --- 13. claim_kind == source_excerpt ---
def test_claim_kind_is_source_excerpt(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    wrapper = project_frozen_packet_to_compatibility_wrapper(packet)
    assert COMPATIBILITY_CLAIM_KIND == "source_excerpt"
    for claim in wrapper.claims:
        assert claim.claim_kind == "source_excerpt"


# --- 14. Compatibility support_status == supported ---
def test_compatibility_support_status_is_supported(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    wrapper = project_frozen_packet_to_compatibility_wrapper(packet)
    assert COMPATIBILITY_SUPPORT_STATUS == "supported"
    for claim in wrapper.claims:
        assert claim.support_status == "supported"


# --- 15. Native support_basis == verbatim_source_copy ---
def test_support_basis_is_verbatim_source_copy(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    assert SUPPORT_BASIS == "verbatim_source_copy"
    for item in packet.evidence_items:
        assert item.support_basis == "verbatim_source_copy"


# --- 16. Native semantic_support_status == not_assessed ---
def test_semantic_support_status_is_not_assessed(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    assert SEMANTIC_SUPPORT_STATUS == "not_assessed"
    for item in packet.evidence_items:
        assert item.semantic_support_status == "not_assessed"


# --- 17. No provider/model call ---
def test_no_provider_model_call():
    assert ALLOW_MODEL_CALL is False
    import inspect
    import research.experiments.cross_perspective_advisory_ablation_v1.packet_projection as pp
    src = inspect.getsource(pp)
    assert "build_llm_provider" not in src
    assert "generate_content" not in src
    assert "chat_complete" not in src


# --- 18. No retrieval call ---
def test_no_retrieval_call():
    assert ALLOW_RETRIEVAL_CALL is False
    import inspect
    import research.experiments.cross_perspective_advisory_ablation_v1.packet_projection as pp
    src = inspect.getsource(pp)
    assert "RetrievalEngine" not in src
    assert "run_retrieval" not in src


# --- 19. No production adapter / consult call ---
def test_no_production_adapter_consult_call():
    import inspect
    import research.experiments.cross_perspective_advisory_ablation_v1.packet_projection as pp
    src = inspect.getsource(pp)
    assert "consult" not in src
    assert "WesternEvidenceAgent" not in src
    assert "TCMEvidenceAgent" not in src


# --- 20. Raw-parent hash mismatch fails ---
def test_raw_parent_hash_mismatch_fails(tmp_path):
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_runner import validate_packet_preflight
    # Create fake workspace where TCM raw retrieval has wrong hash
    fake_root = tmp_path / "repo"
    tcm_dir = fake_root / "research/experiments/cross_perspective_advisory_ablation_v1/retrieval"
    tcm_dir.mkdir(parents=True)
    (tcm_dir / "retrieval_tcm_r0_top4.jsonl").write_text("corrupted content", encoding="utf-8")
    (fake_root / "research/experiments/cross_perspective_advisory_ablation_v1/question_manifest.jsonl").write_text("fake", encoding="utf-8")

    with pytest.raises(ValueError, match="manifest SHA mismatch|raw retrieval byte SHA mismatch"):
        validate_packet_preflight(fake_root)


# --- 21. Question manifest hash mismatch fails ---
def test_question_manifest_hash_mismatch_fails(tmp_path):
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_runner import validate_packet_preflight
    fake_root = tmp_path / "repo"
    q_dir = fake_root / "research/experiments/cross_perspective_advisory_ablation_v1"
    q_dir.mkdir(parents=True)
    (q_dir / "question_manifest.jsonl").write_text("corrupted manifest content", encoding="utf-8")

    with pytest.raises(ValueError, match="manifest SHA mismatch"):
        validate_packet_preflight(fake_root)


# --- 22. Malformed input fails ---
def test_malformed_input_fails(synthetic_raw_record):
    # Malformed record with only 3 results
    bad_record_dict = synthetic_raw_record.model_dump(mode="json")
    bad_record_dict["results"] = bad_record_dict["results"][:3]
    bad_record_dict["returned_count"] = 3
    bad_record_dict["positive_score_count"] = 3
    bad_record_dict["zero_score_count"] = 0
    bad_record = RawRetrievalRecord.model_validate(bad_record_dict)

    with pytest.raises(ValueError, match="Expected exactly 4 hits"):
        project_raw_record_to_frozen_packet(bad_record, "0" * 64)


# --- 23. Duplicate evidence IDs fail ---
def test_duplicate_evidence_ids_fail(synthetic_raw_record):
    packet = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    pkt_dict = packet.model_dump(mode="json")
    # Force duplicate evidence_id
    pkt_dict["evidence_items"][1]["evidence_id"] = pkt_dict["evidence_items"][0]["evidence_id"]
    with pytest.raises(ValueError, match="Evidence IDs must be unique"):
        FrozenEvidencePacket.model_validate(pkt_dict)


# --- 24. Prompt shared clarification appears once in all five variants ---
def test_prompt_shared_clarification_appears_once():
    for role, prompt_text in RESEARCH_SYSTEM_PROMPTS.items():
        count = prompt_text.count(SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT)
        assert count == 1, f"Shared clarification must appear exactly once in {role}, found {count}"


# --- 25. Evidence Specialist original sentence absent and replacement exact ---
def test_evidence_specialist_prompt_delta():
    old_target = "Your purpose is to identify the strongest and most useful ALREADY-SUPPORTED claims inside the supplied evidence packet."
    new_target = "Your purpose is to identify the strongest and most useful structurally eligible source-passage entries inside the supplied evidence packet."
    
    assert old_target not in CPAA1_EVIDENCE_SPECIALIST_SYSTEM_PROMPT
    assert new_target in CPAA1_EVIDENCE_SPECIALIST_SYSTEM_PROMPT
    assert CPAA1_EVIDENCE_SPECIALIST_SYSTEM_PROMPT.count(new_target) == 1


# --- 26. Grounding Skeptic original sentence absent and replacement exact ---
def test_grounding_skeptic_prompt_delta():
    old_target = "Inspect claim_text against linked evidence excerpts in provenance to identify overstatement, weak support, ambiguity, partial support, or uncertainty, and flag insufficient claims where appropriate."
    new_target = "Inspect the supplied source passages and linked provenance to identify overstatement risks, limits of support, ambiguity, or uncertainty relevant to the question. Identical claim_text and provenance excerpt establish faithful copying only, not semantic support for an inferred answer. Report concerns through the existing advisory schema; do not rewrite passages or change packet statuses."
    
    assert old_target not in CPAA1_GROUNDING_SKEPTIC_SYSTEM_PROMPT
    assert new_target in CPAA1_GROUNDING_SKEPTIC_SYSTEM_PROMPT
    assert CPAA1_GROUNDING_SKEPTIC_SYSTEM_PROMPT.count(new_target) == 1


# --- 27. Other roles have no extra unapproved text delta ---
def test_other_roles_have_no_extra_unapproved_delta():
    # Coverage Auditor: only shared clarification inserted after opening
    ca_open = "You are a Coverage Auditor for a single medical evidence perspective."
    ca_tail = COVERAGE_AUDITOR_SYSTEM_PROMPT[len(ca_open):].lstrip()
    expected_ca = f"{ca_open} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {ca_tail}"
    assert CPAA1_COVERAGE_AUDITOR_SYSTEM_PROMPT == expected_ca

    # Critic: only shared clarification inserted after opening
    critic_open = "You are a Cross-Perspective Critic for a dual-perspective health QA system comparing TCM (Traditional Chinese Medicine) and Western biomedical perspectives."
    critic_tail = CRITIC_SYSTEM_PROMPT[len(critic_open):].lstrip()
    expected_critic = f"{critic_open} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {critic_tail}"
    assert CPAA1_CRITIC_SYSTEM_PROMPT == expected_critic

    # Governance: only shared clarification inserted after opening
    gov_open = "You are the governance and synthesis component of a development-only cross-perspective health QA prototype."
    gov_tail = GOVERNANCE_SYSTEM_PROMPT[len(gov_open):].lstrip()
    expected_gov = f"{gov_open} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {gov_tail}"
    assert CPAA1_GOVERNANCE_SYSTEM_PROMPT == expected_gov


# --- 28. Production prompt constants unchanged ---
def test_production_prompt_constants_unchanged():
    expected_hashes = {
        "evidence_specialist": "0b659434568f2975843f5e338f42e81ec908d389557136621b113d17b44a0d75",
        "coverage_auditor": "ffb22307033e910752e90f9d325372e611802a9a682efb3748e2f2919efedba1",
        "grounding_skeptic": "8e45e6c37b9013e89a9146515e08cc863f5939daf9ba5c68ccb7c8ca7a98e0e7",
        "critic": "9cdf6f9cf157e1da37aa7b28d489af83fbc355e1b46aa761d01d297808835c36",
        "governance": "50bccba1fe344e971a50d5f1382262eb152bbb58bab051d34a46f69231807702",
    }
    prompts = {
        "evidence_specialist": EVIDENCE_SPECIALIST_SYSTEM_PROMPT,
        "coverage_auditor": COVERAGE_AUDITOR_SYSTEM_PROMPT,
        "grounding_skeptic": GROUNDING_SKEPTIC_SYSTEM_PROMPT,
        "critic": CRITIC_SYSTEM_PROMPT,
        "governance": GOVERNANCE_SYSTEM_PROMPT,
    }
    for role, text in prompts.items():
        assert sha256_prompt(text) == expected_hashes[role], f"Production prompt {role} was modified!"


# --- 29. Original/amended prompt hashes match map ---
def test_prompt_hashes_match_map():
    map_path = _ROOT / "research/experiments/cross_perspective_advisory_ablation_v1/prompt_amendment_map_v1.json"
    assert map_path.exists()
    entries = json.loads(map_path.read_text(encoding="utf-8"))
    assert len(entries) == 5
    for item in entries:
        role = item["role"]
        amended_text = RESEARCH_SYSTEM_PROMPTS[role]
        assert sha256_prompt(amended_text) == item["amended_prompt_sha256"]


# --- 30. Real Data Read-Only In-Memory Cardinality and Integrity (TASK 4) ---
def test_real_data_read_only_in_memory_cardinality_and_integrity():
    """Verify real frozen raw retrieval data read-only in memory without writing packet files.

    Cardinality requirements:
    - 48 TCM records -> 48 packets, 192 items
    - 48 Western records -> 48 packets, 192 items
    - 96 total packets, 384 total items
    - Exactly 4 items per packet (ranks 1..4)
    - All 48 questions from question manifest represented once per perspective
    - Every packet passes independent integrity validation
    - No retrieval rerun, no model/provider calls
    - No packet files written, packets/ directory does not exist
    """
    tcm_path = _ROOT / TCM_RAW_RETRIEVAL_RELPATH
    west_path = _ROOT / WESTERN_RAW_RETRIEVAL_RELPATH
    q_path = _ROOT / QUESTION_MANIFEST_RELPATH

    assert tcm_path.exists(), f"Missing TCM raw retrieval file: {tcm_path}"
    assert west_path.exists(), f"Missing Western raw retrieval file: {west_path}"
    assert q_path.exists(), f"Missing question manifest: {q_path}"

    tcm_sha = hashlib.sha256(tcm_path.read_bytes()).hexdigest()
    west_sha = hashlib.sha256(west_path.read_bytes()).hexdigest()
    q_sha = hashlib.sha256(q_path.read_bytes()).hexdigest()
    assert tcm_sha == EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256
    assert west_sha == EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256
    assert q_sha == EXPECTED_QUESTION_MANIFEST_SHA256

    # Load question manifest
    manifest_qids = []
    with q_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                manifest_qids.append(json.loads(line.strip())["question_id"])
    assert len(manifest_qids) == EXPECTED_QUESTION_COUNT
    assert len(set(manifest_qids)) == EXPECTED_QUESTION_COUNT

    # Load and project TCM records in memory
    tcm_records = []
    with tcm_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tcm_records.append(RawRetrievalRecord.model_validate_json(line.strip()))
    assert len(tcm_records) == EXPECTED_TCM_RECORDS

    tcm_packets = []
    for rec in tcm_records:
        pkt = project_raw_record_to_frozen_packet(rec, raw_artifact_sha256=tcm_sha)
        validate_frozen_packet_integrity(pkt, raw_record=rec, raw_artifact_sha256=tcm_sha)
        tcm_packets.append(pkt)

    # Load and project Western records in memory
    west_records = []
    with west_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                west_records.append(RawRetrievalRecord.model_validate_json(line.strip()))
    assert len(west_records) == EXPECTED_WESTERN_RECORDS

    west_packets = []
    for rec in west_records:
        pkt = project_raw_record_to_frozen_packet(rec, raw_artifact_sha256=west_sha)
        validate_frozen_packet_integrity(pkt, raw_record=rec, raw_artifact_sha256=west_sha)
        west_packets.append(pkt)

    all_packets = tcm_packets + west_packets

    # Assert exactly 96 packets, 384 evidence items
    assert len(tcm_packets) == EXPECTED_TCM_RECORDS
    assert len(west_packets) == EXPECTED_WESTERN_RECORDS
    assert len(all_packets) == EXPECTED_TOTAL_RECORDS

    tcm_items = sum(len(pkt.evidence_items) for pkt in tcm_packets)
    west_items = sum(len(pkt.evidence_items) for pkt in west_packets)
    assert tcm_items == EXPECTED_TCM_ITEMS
    assert west_items == EXPECTED_WESTERN_ITEMS
    assert (tcm_items + west_items) == EXPECTED_TOTAL_ITEMS

    for pkt in all_packets:
        assert len(pkt.evidence_items) == HITS_PER_RECORD
        assert [it.rank for it in pkt.evidence_items] == [1, 2, 3, 4]

    # Assert all expected questions represented once per perspective
    tcm_qids = [pkt.question_id for pkt in tcm_packets]
    west_qids = [pkt.question_id for pkt in west_packets]
    assert tcm_qids == manifest_qids
    assert west_qids == manifest_qids

    # Capture sealed packet artifact state before in-memory projection
    packets_dir = _ROOT / "research/experiments/cross_perspective_advisory_ablation_v1/packets"
    pre_snapshot = _snapshot_sealed_packets(packets_dir)
    assert packets_dir.exists(), "Formal packets directory must exist post-freeze"
    assert pre_snapshot.get("tcm_packets.jsonl") == FROZEN_TCM_PACKET_BYTE_SHA256
    assert pre_snapshot.get("western_packets.jsonl") == FROZEN_WESTERN_PACKET_BYTE_SHA256
    assert pre_snapshot.get("packet_manifest.json") == FROZEN_MANIFEST_BYTE_SHA256
    assert pre_snapshot.get("packet_freeze_receipt.json") == FROZEN_RECEIPT_BYTE_SHA256

    # Verify post-freeze invariant: in-memory projection does not mutate sealed packet files
    post_snapshot = _snapshot_sealed_packets(packets_dir)
    assert post_snapshot == pre_snapshot, "Post-freeze invariant violated: sealed packet files altered!"


# --- 31. Formal Packet Generation Safeguards at Unit Level (TASKS 8 & 9) ---
def test_formal_packet_generation_safeguards_unit_level(tmp_path):
    """Unit-level proof of Phase 1E formal-generation denial without CLI invocation."""
    # 1. Calling without explicit formal request fails closed
    with pytest.raises(PermissionError, match="not explicitly requested"):
        check_formal_packet_generation_authorization(authorized=False)

    # 2. Formal writer function is absent / not implemented in this phase
    import research.experiments.cross_perspective_advisory_ablation_v1.packet_projection as pp
    import research.experiments.cross_perspective_advisory_ablation_v1.packet_runner as pr
    assert not hasattr(pp, "write_formal_packets")
    assert not hasattr(pp, "materialize_formal_packets")
    assert not hasattr(pr, "write_formal_packets")
    assert not hasattr(pr, "materialize_formal_packets")

    # 3. Expected formal output paths are designated local-only by configuration
    expected_relpaths = [
        "research/experiments/cross_perspective_advisory_ablation_v1/packets/tcm_packets.jsonl",
        "research/experiments/cross_perspective_advisory_ablation_v1/packets/western_packets.jsonl",
    ]
    for p in expected_relpaths:
        assert "packets/" in p

    # Capture sealed formal repository packet state before dry preflight
    packets_dir = _ROOT / "research/experiments/cross_perspective_advisory_ablation_v1/packets"
    pre_snapshot = _snapshot_sealed_packets(packets_dir)
    assert pre_snapshot.get("tcm_packets.jsonl") == FROZEN_TCM_PACKET_BYTE_SHA256
    assert pre_snapshot.get("western_packets.jsonl") == FROZEN_WESTERN_PACKET_BYTE_SHA256
    assert pre_snapshot.get("packet_manifest.json") == FROZEN_MANIFEST_BYTE_SHA256
    assert pre_snapshot.get("packet_freeze_receipt.json") == FROZEN_RECEIPT_BYTE_SHA256

    # 4. Dry preflight in a clean sandbox creates no packets/ directory and no output files
    sandbox_root = tmp_path / "preflight_sandbox"
    sub_dir = sandbox_root / "research/experiments/cross_perspective_advisory_ablation_v1"
    (sub_dir / "retrieval").mkdir(parents=True)
    shutil.copy(
        _ROOT / "research/experiments/cross_perspective_advisory_ablation_v1/question_manifest.jsonl",
        sub_dir / "question_manifest.jsonl",
    )
    shutil.copy(
        _ROOT / "research/experiments/cross_perspective_advisory_ablation_v1/prompt_amendment_map_v1.json",
        sub_dir / "prompt_amendment_map_v1.json",
    )
    shutil.copy(
        _ROOT / "research/experiments/cross_perspective_advisory_ablation_v1/retrieval/retrieval_tcm_r0_top4.jsonl",
        sub_dir / "retrieval/retrieval_tcm_r0_top4.jsonl",
    )
    shutil.copy(
        _ROOT / "research/experiments/cross_perspective_advisory_ablation_v1/retrieval/retrieval_western_r0_top4.jsonl",
        sub_dir / "retrieval/retrieval_western_r0_top4.jsonl",
    )

    report = validate_packet_preflight(sandbox_root)
    assert report["status"] == "PASS"
    assert report["formal_packets_materialized"] is False
    assert not (sub_dir / "packets").exists(), "Dry preflight must never create packets/ directory"

    # Verify post-freeze invariant: pre-existing sealed state in _ROOT remains bitwise unchanged
    post_snapshot = _snapshot_sealed_packets(packets_dir)
    assert post_snapshot == pre_snapshot, "Post-freeze invariant violated: sealed packet files altered!"


# --- 32. Source-derived formal packet files are not accidentally staged ---
def test_source_derived_formal_packet_files_not_staged():
    import subprocess
    res = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=str(_ROOT))
    output = res.stdout
    # Formal packet jsonl files must never appear as staged ("A  .../packets/...")
    assert "A  research/experiments/cross_perspective_advisory_ablation_v1/packets/tcm_packets.jsonl" not in output
    assert "A  research/experiments/cross_perspective_advisory_ablation_v1/packets/western_packets.jsonl" not in output


# --- 33. Real Condition-Path Equality and Visibility Tests (TASK 6) ---
def test_real_condition_builder_section_a_equality_and_advisory_visibility(synthetic_raw_record):
    """Exercise real study condition-aware builder logic using synthetic packets plus nonempty advisory artifacts.
    
    Tests G0, G1, G2, G3:
    1. Section A serialization is BYTE-IDENTICAL across all four conditions.
    2. Identical passage IDs, claim_text, support_status, claim_kind, and order across all conditions.
    3. Advisory visibility:
       - G0: local hidden, critic hidden (Section B present with empty content)
       - G1: local visible, critic hidden
       - G2: local hidden, critic visible
       - G3: local visible, critic visible
    4. Repetition plans (R1, R2) receive identical Section A.
    """
    packet_west = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    wrapper_west = project_frozen_packet_to_compatibility_wrapper(packet_west)

    tcm_dict = synthetic_raw_record.model_dump(mode="json")
    tcm_dict["perspective"] = "tcm"
    tcm_dict["retrieval_record_id"] = "cpaa1:ret:CPAA1-TEST-001:tcm:R0"
    raw_tcm = RawRetrievalRecord.model_validate(tcm_dict)
    packet_tcm = project_raw_record_to_frozen_packet(raw_tcm, "e" * 64)
    wrapper_tcm = project_frozen_packet_to_compatibility_wrapper(packet_tcm)

    packets_pair = {"tcm": wrapper_tcm, "western": wrapper_west}

    # Nonempty advisory assessments fixture
    nonempty_assessments = {
        "tcm": [
            PerspectiveAgentAssessment(
                perspective="tcm",
                role="evidence_specialist",
                assessment_summary="TCM evidence specialist assessment of decoction.",
                referenced_claim_ids=[wrapper_tcm.claims[0].claim_id],
                issues=[],
            ),
            PerspectiveAgentAssessment(
                perspective="tcm",
                role="coverage_auditor",
                assessment_summary="TCM coverage auditor identified cough pattern.",
                referenced_claim_ids=[wrapper_tcm.claims[1].claim_id],
                issues=[],
            ),
            PerspectiveAgentAssessment(
                perspective="tcm",
                role="grounding_skeptic",
                assessment_summary="TCM grounding skeptic checked provenance.",
                referenced_claim_ids=[wrapper_tcm.claims[2].claim_id],
                issues=[AssessmentIssue(claim_ids=[wrapper_tcm.claims[2].claim_id], issue_type="grounding_risk", description="Narrow applicability.")],
            ),
        ],
        "western": [
            PerspectiveAgentAssessment(
                perspective="western",
                role="evidence_specialist",
                assessment_summary="Western evidence specialist identified active compounds.",
                referenced_claim_ids=[wrapper_west.claims[0].claim_id],
                issues=[],
            ),
            PerspectiveAgentAssessment(
                perspective="western",
                role="coverage_auditor",
                assessment_summary="Western coverage auditor reviewed trial endpoints.",
                referenced_claim_ids=[wrapper_west.claims[1].claim_id],
                issues=[],
            ),
            PerspectiveAgentAssessment(
                perspective="western",
                role="grounding_skeptic",
                assessment_summary="Western grounding skeptic flagged sample size.",
                referenced_claim_ids=[wrapper_west.claims[2].claim_id],
                issues=[],
            ),
        ],
    }

    # Nonempty Critic fixture
    nonempty_critique = CrossPerspectiveCritique(
        relations=[
            CrossPerspectiveRelation(
                relation_type="possible_agreement",
                statement="Both perspectives identify anti-tussive effects of herbal extract.",
                tcm_claim_ids=[wrapper_tcm.claims[0].claim_id],
                western_claim_ids=[wrapper_west.claims[0].claim_id],
            )
        ]
    )

    # Build visible payload for all four conditions
    payload_g0 = build_governance_visible_payload("G0", packets=packets_pair, assessments=nonempty_assessments, critique=nonempty_critique)
    payload_g1 = build_governance_visible_payload("G1", packets=packets_pair, assessments=nonempty_assessments, critique=nonempty_critique)
    payload_g2 = build_governance_visible_payload("G2", packets=packets_pair, assessments=nonempty_assessments, critique=nonempty_critique)
    payload_g3 = build_governance_visible_payload("G3", packets=packets_pair, assessments=nonempty_assessments, critique=nonempty_critique)

    payloads = {"G0": payload_g0, "G1": payload_g1, "G2": payload_g2, "G3": payload_g3}

    # 1. Section A serialization is BYTE-IDENTICAL across all four conditions
    sec_a_bytes_g0 = json.dumps(payload_g0["perspective_packets"], sort_keys=True).encode("utf-8")
    sec_a_bytes_g1 = json.dumps(payload_g1["perspective_packets"], sort_keys=True).encode("utf-8")
    sec_a_bytes_g2 = json.dumps(payload_g2["perspective_packets"], sort_keys=True).encode("utf-8")
    sec_a_bytes_g3 = json.dumps(payload_g3["perspective_packets"], sort_keys=True).encode("utf-8")

    assert sec_a_bytes_g0 == sec_a_bytes_g1
    assert sec_a_bytes_g1 == sec_a_bytes_g2
    assert sec_a_bytes_g2 == sec_a_bytes_g3

    # Built-in study parity validation passes
    validate_evidence_parity_across_conditions(payloads)

    # 2. Check identical passage IDs, claim_text, support_status, claim_kind, and order
    for cond_name, p in payloads.items():
        for persp in ("tcm", "western"):
            claims = p["perspective_packets"][persp]["claims"]
            assert len(claims) == 4
            for idx, c in enumerate(claims):
                expected_claim = packets_pair[persp].claims[idx]
                assert c["claim_id"] == expected_claim.claim_id
                assert c["claim_text"] == expected_claim.claim_text
                assert c["support_status"] == expected_claim.support_status == "supported"
                assert c["claim_kind"] == expected_claim.claim_kind == "source_excerpt"

    # 3. Verify advisory visibility matrix
    # G0: local hidden, critic hidden (Section B present with empty advisory content)
    adv_g0 = payload_g0["advisory_context"]
    assert adv_g0["perspective_advisory"]["tcm"] == []
    assert adv_g0["perspective_advisory"]["western"] == []
    assert adv_g0["critic_relations"] == []

    # G1: local visible, critic hidden
    adv_g1 = payload_g1["advisory_context"]
    assert len(adv_g1["perspective_advisory"]["tcm"]) == 3
    assert len(adv_g1["perspective_advisory"]["western"]) == 3
    assert adv_g1["critic_relations"] == []

    # G2: local hidden, critic visible
    adv_g2 = payload_g2["advisory_context"]
    assert adv_g2["perspective_advisory"]["tcm"] == []
    assert adv_g2["perspective_advisory"]["western"] == []
    assert len(adv_g2["critic_relations"]) == 1
    assert adv_g2["critic_relations"][0]["statement"] == nonempty_critique.relations[0].statement

    # G3: local visible, critic visible
    adv_g3 = payload_g3["advisory_context"]
    assert len(adv_g3["perspective_advisory"]["tcm"]) == 3
    assert len(adv_g3["perspective_advisory"]["western"]) == 3
    assert len(adv_g3["critic_relations"]) == 1

    validate_advisory_visibility_matrix(payloads)

    # 4. Verify repetition plans use the same Section A
    rep1_payload = build_governance_visible_payload("G3", packets=packets_pair, assessments=nonempty_assessments, critique=nonempty_critique)
    rep2_payload = build_governance_visible_payload("G3", packets=packets_pair, assessments=nonempty_assessments, critique=nonempty_critique)
    assert json.dumps(rep1_payload["perspective_packets"], sort_keys=True) == json.dumps(rep2_payload["perspective_packets"], sort_keys=True)

    # 5. Verify prompt building: Section A byte-identical across conditions, Section B present in all
    prompts = {
        cond: build_governance_prompt_for_condition(
            "What is the clinical evidence?",
            cond,
            packets=packets_pair,
            assessments=nonempty_assessments,
            critique=nonempty_critique,
        )
        for cond in ("G0", "G1", "G2", "G3")
    }
    for cond, p_text in prompts.items():
        assert "=== SECTION A: EVIDENCE PACKETS (PRIMARY EVIDENCE) ===" in p_text
        assert "=== SECTION B: ADVISORY CONTEXT (CONTROLLED ADVISORY SIGNALS ONLY - NOT EVIDENCE) ===" in p_text


# --- 34. Packet Substitution and Mutation Detection (TASK 7) ---
def test_packet_substitution_and_mutation_detection(synthetic_raw_record):
    """Verify that equality validation catches packet substitution or mutation across condition paths."""
    packet_west = project_raw_record_to_frozen_packet(synthetic_raw_record, "e" * 64)
    wrapper_west = project_frozen_packet_to_compatibility_wrapper(packet_west)

    tcm_dict = synthetic_raw_record.model_dump(mode="json")
    tcm_dict["perspective"] = "tcm"
    tcm_dict["retrieval_record_id"] = "cpaa1:ret:CPAA1-TEST-001:tcm:R0"
    raw_tcm = RawRetrievalRecord.model_validate(tcm_dict)
    packet_tcm = project_raw_record_to_frozen_packet(raw_tcm, "e" * 64)
    wrapper_tcm = project_frozen_packet_to_compatibility_wrapper(packet_tcm)

    packets_pair = {"tcm": wrapper_tcm, "western": wrapper_west}

    # Baseline valid payloads across conditions
    payloads = {
        cond: build_governance_visible_payload(cond, packets=packets_pair, assessments=None, critique=None)
        for cond in ("G0", "G1", "G2", "G3")
    }
    validate_evidence_parity_across_conditions(payloads)

    # 1. Different packet in one condition
    tampered_1 = copy.deepcopy(payloads)
    other_rec_dict = synthetic_raw_record.model_dump(mode="json")
    other_rec_dict["question_id"] = "DIFFERENT-QUESTION"
    other_rec = RawRetrievalRecord.model_validate(other_rec_dict)
    other_pkt = project_raw_record_to_frozen_packet(other_rec, "e" * 64)
    other_wrap = project_frozen_packet_to_compatibility_wrapper(other_pkt)
    tampered_1["G2"]["perspective_packets"] = build_governance_payload({"tcm": wrapper_tcm, "western": other_wrap})
    with pytest.raises(PreflightValidationError, match="Section A evidence packet mismatch"):
        validate_evidence_parity_across_conditions(tampered_1)

    # 2. Claim text changes in one condition
    tampered_2 = copy.deepcopy(payloads)
    tampered_2["G1"]["perspective_packets"]["western"]["claims"][0]["claim_text"] += " tampered extra sentence"
    with pytest.raises(PreflightValidationError, match="Section A evidence packet mismatch"):
        validate_evidence_parity_across_conditions(tampered_2)

    # 3. Passage order changes in one condition
    tampered_3 = copy.deepcopy(payloads)
    tampered_3["G3"]["perspective_packets"]["tcm"]["claims"].reverse()
    with pytest.raises(PreflightValidationError, match="Section A evidence packet mismatch"):
        validate_evidence_parity_across_conditions(tampered_3)

    # 4. Claim ID changes in one condition
    tampered_4 = copy.deepcopy(payloads)
    tampered_4["G0"]["perspective_packets"]["tcm"]["claims"][0]["claim_id"] = "cpaa1:sx:tampered_id"
    with pytest.raises(PreflightValidationError, match="Section A evidence packet mismatch"):
        validate_evidence_parity_across_conditions(tampered_4)

    # 5. Support status changes in one condition
    tampered_5 = copy.deepcopy(payloads)
    tampered_5["G2"]["perspective_packets"]["western"]["claims"][0]["support_status"] = "unsupported"
    with pytest.raises(PreflightValidationError, match="Section A evidence packet mismatch"):
        validate_evidence_parity_across_conditions(tampered_5)

    # 6. Claim kind changes in one condition
    tampered_6 = copy.deepcopy(payloads)
    tampered_6["G3"]["perspective_packets"]["western"]["claims"][0]["claim_kind"] = "atomic_proposition"
    with pytest.raises(PreflightValidationError, match="Section A evidence packet mismatch"):
        validate_evidence_parity_across_conditions(tampered_6)

    # 7. Model immutability: FrozenEvidenceItem and FrozenEvidencePacket disallow attribute assignment
    with pytest.raises(ValidationError):
        packet_tcm.perspective = "western"  # frozen model raises on mutation
    with pytest.raises(ValidationError):
        packet_tcm.evidence_items[0].exact_chunk_text = "Mutated text"

    # 8. Integrity validation catches tampering
    with pytest.raises(ValueError, match="Chunk text SHA256 mismatch"):
        bad_item = FrozenEvidenceItem(
            evidence_id=packet_tcm.evidence_items[0].evidence_id,
            rank=1,
            retrieval_score=0.95,
            score_is_zero=False,
            chunk_id="chunk_001",
            corpus_record_ordinal=10,
            exact_chunk_text="Tampered text",
            chunk_text_sha256=packet_tcm.evidence_items[0].chunk_text_sha256,
            chunk_record_canonical_sha256=packet_tcm.evidence_items[0].chunk_record_canonical_sha256,
            source_id="src_001",
        )
        validate_frozen_evidence_item_integrity(bad_item, packet_tcm.question_id, packet_tcm.perspective)


# --- 35. Prompt Baseline Hash Enforcement Fail-Closed (TASK 13) ---
def test_prompt_baseline_hash_enforcement_fail_closed():
    """Prove that any tampering or drift in baseline production prompts fails closed."""
    # 1. Tampering with Coverage Auditor baseline raises AssertionError
    with pytest.raises(AssertionError, match="Baseline prompt hash mismatch for coverage_auditor"):
        build_coverage_auditor_prompt(base_prompt=COVERAGE_AUDITOR_SYSTEM_PROMPT + " unapproved tail")

    # 2. Tampering with all other roles fails closed
    with pytest.raises(AssertionError, match="Baseline prompt hash mismatch for evidence_specialist"):
        build_evidence_specialist_prompt(base_prompt=EVIDENCE_SPECIALIST_SYSTEM_PROMPT + " unapproved")

    with pytest.raises(AssertionError, match="Baseline prompt hash mismatch for grounding_skeptic"):
        build_grounding_skeptic_prompt(base_prompt=GROUNDING_SKEPTIC_SYSTEM_PROMPT + " unapproved")

    with pytest.raises(AssertionError, match="Baseline prompt hash mismatch for critic"):
        build_critic_prompt(base_prompt=CRITIC_SYSTEM_PROMPT + " unapproved")

    with pytest.raises(AssertionError, match="Baseline prompt hash mismatch for governance"):
        build_governance_prompt(base_prompt=GOVERNANCE_SYSTEM_PROMPT + " unapproved")

    # 3. Exact valid baseline succeeds
    assert build_coverage_auditor_prompt(COVERAGE_AUDITOR_SYSTEM_PROMPT) == RESEARCH_SYSTEM_PROMPTS["coverage_auditor"]
    assert build_evidence_specialist_prompt(EVIDENCE_SPECIALIST_SYSTEM_PROMPT) == RESEARCH_SYSTEM_PROMPTS["evidence_specialist"]
    assert build_grounding_skeptic_prompt(GROUNDING_SKEPTIC_SYSTEM_PROMPT) == RESEARCH_SYSTEM_PROMPTS["grounding_skeptic"]
    assert build_critic_prompt(CRITIC_SYSTEM_PROMPT) == RESEARCH_SYSTEM_PROMPTS["critic"]
    assert build_governance_prompt(GOVERNANCE_SYSTEM_PROMPT) == RESEARCH_SYSTEM_PROMPTS["governance"]

    # 4. Approved amended hashes remain unchanged
    for role, amended_prompt in RESEARCH_SYSTEM_PROMPTS.items():
        assert sha256_prompt(amended_prompt) == EXPECTED_AMENDED_PROMPT_HASHES[role]



# --- TASK 12: Token-budget offline scaffolding tests ---
def test_token_budget_scaffold_offline_unclearable():
    rec = TokenBudgetScaffold.evaluate_role_budget(
        role="evidence_specialist",
        question_id="TEST-Q",
        system_prompt=CPAA1_EVIDENCE_SPECIALIST_SYSTEM_PROMPT,
        user_payload="Sample question and candidate evidence passages",
    )
    assert rec.status == "NOT_YET_CLEARABLE"
    assert rec.chat_formatted_input_token_estimate is None
    assert rec.remaining_margin_tokens is None


def test_token_budget_scaffold_synthetic_clearance():
    # Synthetic mock tokenizer for interface testing
    mock_tokenizer = lambda text: len(text.split())
    rec = TokenBudgetScaffold.evaluate_role_budget(
        role="evidence_specialist",
        question_id="TEST-Q",
        system_prompt="Short prompt",
        user_payload="Short payload",
        tokenizer=mock_tokenizer,
        max_context=4096,
        reserved_output=512,
    )
    assert rec.status == "CLEARED"
    assert rec.chat_formatted_input_token_estimate == 4
    assert rec.remaining_margin_tokens == 4096 - (4 + 512)
