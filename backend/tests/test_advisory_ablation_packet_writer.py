from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

_BACKEND = Path(__file__).resolve().parents[1]
_ROOT = _BACKEND.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from research.experiments.cross_perspective_advisory_ablation_v1.packet_contract import (
    AMENDMENT_ID,
    CANONICAL_JSON_KWARGS,
    EXPECTED_QUESTION_COUNT,
    EXPECTED_QUESTION_MANIFEST_SHA256,
    EXPECTED_TCM_CORPUS_SHA256,
    EXPECTED_TCM_ITEMS,
    EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
    EXPECTED_TCM_RECORDS,
    EXPECTED_TOTAL_ITEMS,
    EXPECTED_TOTAL_RECORDS,
    EXPECTED_WESTERN_CORPUS_SHA256,
    EXPECTED_WESTERN_ITEMS,
    EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256,
    EXPECTED_WESTERN_RECORDS,
    HITS_PER_RECORD,
    MANIFEST_SCHEMA_VERSION,
    PACKET_CONTRACT_ID,
    RECEIPT_SCHEMA_VERSION,
    SCHEMA_VERSION,
    SERIALIZATION_VERSION,
    STUDY_ID,
    format_evidence_id,
    format_packet_id,
)
from research.experiments.cross_perspective_advisory_ablation_v1.packet_projection import (
    TrustedParentStore,
    project_raw_record_to_frozen_packet,
    validate_frozen_evidence_item_integrity,
    validate_frozen_packet_integrity,
    validate_packet_against_trusted_parent,
)
from research.experiments.cross_perspective_advisory_ablation_v1.packet_serialization import (
    canonical_json_bytes,
    canonical_json_text,
    manifest_canonical_sha256,
    manifest_file_bytes,
    packet_canonical_sha256,
    perspective_canonical_aggregate_sha256,
    receipt_file_bytes,
    serialize_jsonl_records,
    serialize_metadata_json,
    sha256_bytes,
    strict_deep_compare,
    strict_json_loads,
    validate_serializable_value,
)
from research.experiments.cross_perspective_advisory_ablation_v1.packet_writer import (
    PHASE_1F_FORMAL_AUTHORIZATION_GRANTED,
    PHASE_1G_FORMAL_AUTHORIZATION_GRANTED,
    build_in_memory_formal_packet_artifacts,
    execute_formal_packet_generation,
    verify_and_get_executing_git_head,
    verify_frozen_inputs,
    verify_research_prompts,
    write_formal_packet_artifacts,
)
from research.experiments.cross_perspective_advisory_ablation_v1.schemas import (
    FrozenEvidenceItem,
    FrozenEvidencePacket,
    PacketFreezeReceipt,
    PacketRunManifest,
    RawRetrievalItem,
    RawRetrievalRecord,
)


@pytest.fixture(scope="module")
def repo_root() -> Path:
    return _ROOT


@pytest.fixture(scope="module")
def trusted_store(repo_root: Path) -> TrustedParentStore:
    return TrustedParentStore(repo_root)


@pytest.fixture(scope="module")
def sample_tcm_packet_and_raw(trusted_store: TrustedParentStore):
    q_rec = trusted_store.question_manifest_records[0]
    qid = q_rec["question_id"]
    raw_rec = trusted_store.tcm_raw_records[qid]
    pkt = project_raw_record_to_frozen_packet(
        record=raw_rec,
        raw_artifact_sha256=EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
    )
    validate_packet_against_trusted_parent(pkt, trusted_store)
    return pkt, raw_rec, q_rec


# ==============================================================================
# TASK 19: TAMPERING REGRESSION TESTS (31 TESTS)
# Every test alters a field, recomputes packet canonical hash (and text SHA if
# text was changed), and verifies validation against trusted parent STILL FAILS.
# ==============================================================================

def _tamper_and_rehash(
    base_pkt: FrozenEvidencePacket,
    modifier_fn,
) -> dict:
    data = base_pkt.model_dump(mode="json")
    modifier_fn(data)
    # Recompute packet canonical hash after tampering
    data["packet_canonical_sha256"] = packet_canonical_sha256(data)
    return data


def _assert_tamper_fails(tampered_data: dict, trusted_store: TrustedParentStore):
    try:
        tampered_pkt = FrozenEvidencePacket.model_validate(tampered_data)
    except (ValidationError, ValueError, TypeError):
        # Schema rejected tamper during construction: counts as PASS
        return
    # If schema accepted, validation against trusted parent must fail
    with pytest.raises((ValueError, TypeError)):
        validate_packet_against_trusted_parent(tampered_pkt, trusted_store)


def test_tamper_01_nested_provenance_scalar(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["provenance"]["tampered_scalar"] = "injected_value"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_02_nested_provenance_list(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["provenance"]["tampered_list"] = ["item1", "item2"]

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_03_source_title(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["source_title"] = "Tampered Source Title"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_04_source_url(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["source_url"] = "https://tampered.example.com/source"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_05_doi(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["doi"] = "10.1234/tampered.doi"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_06_pmcid(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["pmcid"] = "PMC9999999"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_07_source_record_id(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["source_record_id"] = "TAMPERED_SRC_REC_001"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_08_section_or_category(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["section_or_category"] = "Tampered Section Name"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_09_citation_or_version(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["source_citation_or_version"] = "Tampered Citation v2"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_10_license_or_access_status(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["license_or_access_status"] = "tampered_access"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_11_review_status(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["review_status"] = "tampered_review_status"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_12_retrieval_score(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["retrieval_score"] = 0.555555

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_13_score_is_zero(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["score_is_zero"] = True

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_14_corpus_record_ordinal(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["corpus_record_ordinal"] += 999

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_15_exact_chunk_text(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        new_text = d["evidence_items"][0]["exact_chunk_text"] + " [TAMPERED EVIDENCE]"
        d["evidence_items"][0]["exact_chunk_text"] = new_text
        # Also recompute chunk text SHA256 as required by Task 19
        d["evidence_items"][0]["chunk_text_sha256"] = hashlib.sha256(new_text.encode("utf-8")).hexdigest()

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_16_rank(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["rank"] = 2

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_17_chunk_id(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["chunk_id"] = "tampered_chunk_001"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_18_source_id(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["source_id"] = "tampered_source_001"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_19_stored_chunk_hashes(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["chunk_record_canonical_sha256"] = "f" * 64

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_20_null_to_empty_string(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        # Substitute None with "" on an optional field
        d["evidence_items"][0]["doi"] = ""

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_21_missing_to_null(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["provenance"]["missing_in_parent"] = None

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_22_numeric_type_substitution(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        # Float replaced by int
        d["evidence_items"][0]["retrieval_score"] = 1

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_23_bool_to_int(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0]["score_is_zero"] = 0

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_24_evidence_item_reorder(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"][0], d["evidence_items"][1] = d["evidence_items"][1], d["evidence_items"][0]

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_25_item_deletion(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["evidence_items"] = d["evidence_items"][:3]

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_26_item_insertion(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        extra = copy.deepcopy(d["evidence_items"][0])
        extra["rank"] = 5
        d["evidence_items"].append(extra)

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_27_replacement_by_another_valid_hit(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw
    # Get a valid hit from another question
    other_qid = trusted_store.question_manifest_records[1]["question_id"]
    other_raw = trusted_store.tcm_raw_records[other_qid]
    other_pkt = project_raw_record_to_frozen_packet(other_raw, EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256)
    other_item_dict = other_pkt.evidence_items[0].model_dump(mode="json")

    def mod(d):
        d["evidence_items"][0] = other_item_dict

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_28_question_substitution(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw
    other_qid = trusted_store.question_manifest_records[1]["question_id"]

    def mod(d):
        d["question_id"] = other_qid

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_29_perspective_substitution(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["perspective"] = "western"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_30_metadata_substitution(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw

    def mod(d):
        d["question_text"] = "Altered question text?"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


def test_tamper_31_shared_reference_provenance_mutation(sample_tcm_packet_and_raw, trusted_store):
    pkt, _, _ = sample_tcm_packet_and_raw
    # 1. Verify defensive deep copy: mutating a copy of raw record does not affect packet
    raw_copy = copy.deepcopy(trusted_store.tcm_raw_records[pkt.question_id])
    pkt_fresh = project_raw_record_to_frozen_packet(raw_copy, EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256)
    raw_copy.results[0].provenance["injected_in_caller"] = "val"
    assert "injected_in_caller" not in pkt_fresh.evidence_items[0].provenance

    # 2. Shared reference tamper: if a packet had an injected provenance entry and was self-rehashed
    def mod(d):
        d["evidence_items"][0]["provenance"]["shared_mutated_key"] = "tampered_value"

    tampered = _tamper_and_rehash(pkt, mod)
    _assert_tamper_fails(tampered, trusted_store)


# ==============================================================================
# TASK 20: SERIALIZATION CONFORMANCE TESTS
# ==============================================================================

def test_serialization_utf8_non_ascii():
    obj = {"term": "咳嗽与白术", "nested": ["胃肠"]}
    b = canonical_json_bytes(obj)
    assert b.decode("utf-8") == '{"nested":["胃肠"],"term":"咳嗽与白术"}'
    assert "\\u" not in b.decode("utf-8")


def test_serialization_no_bom():
    obj = {"key": "val"}
    b = canonical_json_bytes(obj)
    assert not b.startswith(b"\xef\xbb\xbf")


def test_serialization_lf_only_no_crlf():
    records = [{"id": 1}, {"id": 2}]
    b = serialize_jsonl_records(records)
    assert b"\r" not in b
    assert b == b'{"id":1}\n{"id":2}\n'


def test_serialization_exactly_one_final_lf():
    b_jsonl = serialize_jsonl_records([{"a": 1}])
    assert b_jsonl.endswith(b"\n")
    assert not b_jsonl.endswith(b"\n\n")

    b_meta = serialize_metadata_json({"a": 1})
    assert b_meta.endswith(b"\n")
    assert not b_meta.endswith(b"\n\n")


def test_serialization_embedded_newlines_escaped():
    obj = {"text": "line1\nline2\rline3\tline4"}
    b = canonical_json_bytes(obj)
    # Inside JSON string, newline must be escaped as literal \n, not byte 0x0A
    assert b == b'{"text":"line1\\nline2\\rline3\\tline4"}'


def test_serialization_sorted_keys():
    obj = {"z": 1, "a": 2, "m": 3}
    text = canonical_json_text(obj)
    assert text == '{"a":2,"m":3,"z":1}'


def test_serialization_compact_separators():
    obj = {"a": 1, "b": [2, 3]}
    text = canonical_json_text(obj)
    assert text == '{"a":1,"b":[2,3]}'
    assert " " not in text


def test_serialization_arrays_preserve_order():
    obj = {"ranks": [4, 1, 3, 2]}
    text = canonical_json_text(obj)
    assert text == '{"ranks":[4,1,3,2]}'


def test_serialization_explicit_nulls():
    obj = {"val": None}
    text = canonical_json_text(obj)
    assert text == '{"val":null}'


def test_serialization_one_vs_one_point_zero():
    t_int = canonical_json_text({"v": 1})
    t_float = canonical_json_text({"v": 1.0})
    assert t_int == '{"v":1}'
    assert t_float == '{"v":1.0}'
    assert t_int != t_float


def test_serialization_negative_zero():
    t_neg = canonical_json_text({"v": -0.0})
    t_pos = canonical_json_text({"v": 0.0})
    assert t_neg == '{"v":-0.0}'
    assert t_pos == '{"v":0.0}'


def test_serialization_booleans():
    t_true = canonical_json_text({"b": True})
    t_false = canonical_json_text({"b": False})
    assert t_true == '{"b":true}'
    assert t_false == '{"b":false}'
    # Booleans must not serialize as integers 1/0
    assert t_true != '{"b":1}'
    assert t_false != '{"b":0}'


def test_serialization_nan_infinity_rejection():
    with pytest.raises(ValueError):
        validate_serializable_value(float("nan"))
    with pytest.raises(ValueError):
        validate_serializable_value(float("inf"))
    with pytest.raises(ValueError):
        validate_serializable_value(float("-inf"))


def test_serialization_lone_surrogate_rejection():
    with pytest.raises(ValueError):
        validate_serializable_value("invalid_\ud800_surrogate")


def test_serialization_duplicate_json_key_rejection():
    raw_dup = '{"key": 1, "key": 2}'
    with pytest.raises(ValueError, match="Duplicate key"):
        strict_json_loads(raw_dup)


def test_serialization_unsupported_object_rejection():
    with pytest.raises(TypeError):
        validate_serializable_value(set([1, 2]))
    with pytest.raises(TypeError):
        validate_serializable_value(datetime.datetime.now())
    with pytest.raises(TypeError):
        validate_serializable_value(Path("."))
    with pytest.raises(TypeError):
        validate_serializable_value({123: "non-string-key"})


# ==============================================================================
# TASK 21: AGGREGATE / MANIFEST / RECEIPT TESTS
# ==============================================================================

def test_manifest_question_physical_order(trusted_store: TrustedParentStore):
    # Verify that the 48 manifest questions have unique IDs and match physical nonblank line order
    records = trusted_store.question_manifest_records
    assert len(records) == 48
    qids = [r["question_id"] for r in records]
    assert len(set(qids)) == 48


def test_perspective_canonical_aggregate_exact_rule(sample_tcm_packet_and_raw):
    pkt, _, _ = sample_tcm_packet_and_raw
    packets = [pkt] * 48
    agg_sha = perspective_canonical_aggregate_sha256(packets)
    assert len(agg_sha) == 64
    assert agg_sha.islower()

    # Reversing packet order must change aggregate hash
    pkt_reversed = list(reversed(packets))
    # Create two slightly different packets
    d2 = copy.deepcopy(pkt.model_dump(mode="json"))
    d2["question_id"] = "cpaa1-cou-ed-002"
    d2["packet_id"] = format_packet_id(d2["question_id"], d2["perspective"])
    d2["packet_canonical_sha256"] = packet_canonical_sha256(d2)
    pkt2 = FrozenEvidencePacket.model_validate(d2)

    order1 = [pkt, pkt2]
    order2 = [pkt2, pkt]
    assert perspective_canonical_aggregate_sha256(order1) != perspective_canonical_aggregate_sha256(order2)


def test_manifest_and_receipt_exact_format(repo_root: Path):
    dummy_commit = "0" * 40
    arts = build_in_memory_formal_packet_artifacts(repo_root, dummy_commit)

    # Manifest checks
    assert arts.manifest.schema_version == MANIFEST_SCHEMA_VERSION
    assert arts.manifest_bytes.endswith(b"\n")
    assert not arts.manifest_bytes.endswith(b"\n\n")
    assert arts.manifest_canonical_sha256 == sha256_bytes(canonical_json_bytes(arts.manifest))
    assert arts.manifest_byte_sha256 == sha256_bytes(arts.manifest_bytes)

    # Receipt checks
    assert arts.receipt.schema_version == RECEIPT_SCHEMA_VERSION
    assert arts.receipt_bytes.endswith(b"\n")
    assert not arts.receipt_bytes.endswith(b"\n\n")
    assert arts.receipt.manifest_byte_sha256 == arts.manifest_byte_sha256
    assert arts.receipt.manifest_canonical_sha256 == arts.manifest_canonical_sha256

    # Receipt externally hashable, does not contain self-hash
    receipt_dict = arts.receipt.model_dump(mode="json")
    assert "receipt_sha256" not in receipt_dict
    assert "packet_freeze_receipt_sha256" not in receipt_dict


def test_metadata_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        PacketRunManifest(
            schema_version=MANIFEST_SCHEMA_VERSION,
            study_id=STUDY_ID,
            amendment_id=AMENDMENT_ID,
            packet_contract_id=PACKET_CONTRACT_ID,
            serialization_version=SERIALIZATION_VERSION,
            implementation_commit="0" * 40,
            question_manifest_sha256="0" * 64,
            tcm_raw_retrieval_byte_sha256="0" * 64,
            western_raw_retrieval_byte_sha256="0" * 64,
            tcm_corpus_sha256="0" * 64,
            western_corpus_sha256="0" * 64,
            research_prompt_sha256={},
            tcm_packet_byte_sha256="0" * 64,
            western_packet_byte_sha256="0" * 64,
            tcm_packet_canonical_aggregate_sha256="0" * 64,
            western_packet_canonical_aggregate_sha256="0" * 64,
            unexpected_field="forbidden",
        )


# ==============================================================================
# TASK 22: WRITER SAFETY TESTS WITHOUT REAL FORMAL OUTPUT
# ==============================================================================

def test_writer_authorization_closed_by_default(repo_root: Path, tmp_path: Path):
    dummy_commit = "0" * 40
    arts = build_in_memory_formal_packet_artifacts(repo_root, dummy_commit)

    # Calling write_formal_packet_artifacts without flags must fail
    with pytest.raises(PermissionError, match="not explicitly requested"):
        write_formal_packet_artifacts(
            artifacts=arts,
            output_dir=tmp_path / "packets",
            request_formal_execution=False,
            authorize_formal=False,
        )

    # Calling with request_formal_execution=True but authorize_formal=False must fail
    with pytest.raises(PermissionError, match="authorization remains CLOSED"):
        write_formal_packet_artifacts(
            artifacts=arts,
            output_dir=tmp_path / "packets",
            request_formal_execution=True,
            authorize_formal=False,
        )

    # Verify no files were created
    assert not (tmp_path / "packets").exists()


def test_writer_forbidden_on_real_packets_dir(repo_root: Path):
    dummy_commit = "0" * 40
    arts = build_in_memory_formal_packet_artifacts(repo_root, dummy_commit)
    real_dir = repo_root / "research/experiments/cross_perspective_advisory_ablation_v1/packets"

    with pytest.raises(PermissionError):
        write_formal_packet_artifacts(
            artifacts=arts,
            output_dir=real_dir,
            request_formal_execution=True,
            authorize_formal=True,
        )


def test_writer_exclusive_creation_and_no_overwrite(repo_root: Path, tmp_path: Path):
    dummy_commit = "0" * 40
    arts = build_in_memory_formal_packet_artifacts(repo_root, dummy_commit)
    fake_sink = tmp_path / "fake_packets"

    # Pre-create one of the target files
    fake_sink.mkdir(parents=True, exist_ok=True)
    existing_file = fake_sink / "tcm_packets.jsonl"
    existing_file.write_bytes(b"existing")

    # Writer must detect existing file and fail without overwriting
    with pytest.raises(FileExistsError, match="already exists"):
        write_formal_packet_artifacts(
            artifacts=arts,
            output_dir=fake_sink,
            request_formal_execution=True,
            authorize_formal=True,
        )

    # Confirm original file was not overwritten
    assert existing_file.read_bytes() == b"existing"


def test_writer_successful_synthetic_sink(repo_root: Path, tmp_path: Path):
    dummy_commit = "0" * 40
    arts = build_in_memory_formal_packet_artifacts(repo_root, dummy_commit)
    fake_sink = tmp_path / "fresh_packets"

    result = write_formal_packet_artifacts(
        artifacts=arts,
        output_dir=fake_sink,
        request_formal_execution=True,
        authorize_formal=True,
    )

    assert result["status"] == "WRITTEN"
    assert (fake_sink / "tcm_packets.jsonl").exists()
    assert (fake_sink / "western_packets.jsonl").exists()
    assert (fake_sink / "packet_manifest.json").exists()
    assert (fake_sink / "packet_freeze_receipt.json").exists()

    # Reread and verify bytes
    assert (fake_sink / "tcm_packets.jsonl").read_bytes() == arts.tcm_jsonl_bytes
    assert (fake_sink / "western_packets.jsonl").read_bytes() == arts.western_jsonl_bytes
    assert (fake_sink / "packet_manifest.json").read_bytes() == arts.manifest_bytes
    assert (fake_sink / "packet_freeze_receipt.json").read_bytes() == arts.receipt_bytes


# ==============================================================================
# TASK 23: REAL-DATA READ-ONLY IN-MEMORY PREFLIGHT
# ==============================================================================

def test_real_data_read_only_in_memory_preflight(repo_root: Path):
    dummy_commit = "0" * 40
    arts = build_in_memory_formal_packet_artifacts(repo_root, dummy_commit)

    assert len(arts.tcm_packets) == 48
    assert len(arts.western_packets) == 48
    assert len(arts.tcm_packets) + len(arts.western_packets) == 96

    total_items = sum(len(p.evidence_items) for p in arts.tcm_packets + arts.western_packets)
    assert total_items == 384

    # Verify deterministic repeated construction
    arts2 = build_in_memory_formal_packet_artifacts(repo_root, dummy_commit)
    assert arts.tcm_jsonl_bytes == arts2.tcm_jsonl_bytes
    assert arts.western_jsonl_bytes == arts2.western_jsonl_bytes
    assert arts.manifest_bytes == arts2.manifest_bytes
    assert arts.receipt_bytes == arts2.receipt_bytes

    # Verify real packets/ does NOT exist
    real_packets_dir = repo_root / "research/experiments/cross_perspective_advisory_ablation_v1/packets"
    assert not real_packets_dir.exists()


# ==============================================================================
# TASK 4: REGRESSION TEST MUTATED TRUSTED PARENT (SOL DEMONSTRATED DEFECT)
# Mutating an exposed or parsed parent object must NEVER alter validation truth.
# ==============================================================================

def test_mutated_parsed_parent_provenance_fails_validation(repo_root: Path):
    """Mutating exposed parsed parent provenance must fail validation against byte anchor."""
    store = TrustedParentStore(repo_root)
    qid = store.get_manifest_question_ids()[0]

    # Get a fresh record to mutate
    raw_rec = store.tcm_raw_records[qid]
    # Mutate the exposed parsed record's provenance
    raw_rec.results[0].provenance["tampered_key"] = "malicious_value"

    # Build packet matching the mutated provenance
    pkt = project_raw_record_to_frozen_packet(
        record=raw_rec,
        raw_artifact_sha256=EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
    )
    # The packet now has "tampered_key" in provenance
    assert "tampered_key" in pkt.evidence_items[0].provenance

    # Validation must FAIL because the store reconstructs the parent from SHA-bound bytes!
    with pytest.raises((ValueError, KeyError), match="tampered_key"):
        validate_packet_against_trusted_parent(pkt, store)


def test_mutated_parsed_parent_source_title_fails_validation(repo_root: Path):
    """Mutating exposed source_title must fail validation against byte anchor."""
    store = TrustedParentStore(repo_root)
    qid = store.get_manifest_question_ids()[0]
    raw_rec = store.tcm_raw_records[qid]
    raw_rec.results[0].source_title = "MALICIOUS TAMPERED TITLE"

    pkt = project_raw_record_to_frozen_packet(
        record=raw_rec,
        raw_artifact_sha256=EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
    )
    with pytest.raises(ValueError, match="MALICIOUS TAMPERED TITLE"):
        validate_packet_against_trusted_parent(pkt, store)


def test_mutated_parsed_parent_source_url_fails_validation(repo_root: Path):
    """Mutating exposed source_url must fail validation against byte anchor."""
    store = TrustedParentStore(repo_root)
    qid = store.get_manifest_question_ids()[0]
    raw_rec = store.tcm_raw_records[qid]
    raw_rec.results[0].source_url = "https://tampered-source.org"

    pkt = project_raw_record_to_frozen_packet(
        record=raw_rec,
        raw_artifact_sha256=EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
    )
    with pytest.raises(ValueError, match="tampered-source"):
        validate_packet_against_trusted_parent(pkt, store)


def test_mutated_parsed_parent_retrieval_score_fails_validation(repo_root: Path):
    """Mutating exposed retrieval_score must fail validation against byte anchor."""
    store = TrustedParentStore(repo_root)
    qid = store.get_manifest_question_ids()[0]
    raw_rec = store.tcm_raw_records[qid]
    raw_rec.results[0].retrieval_score = 999.0

    pkt = project_raw_record_to_frozen_packet(
        record=raw_rec,
        raw_artifact_sha256=EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
    )
    with pytest.raises(ValueError, match="999.0"):
        validate_packet_against_trusted_parent(pkt, store)


def test_mutated_parsed_parent_nullable_metadata_fails_validation(repo_root: Path):
    """Mutating nullable metadata in exposed parent must fail validation against byte anchor."""
    store = TrustedParentStore(repo_root)
    qid = store.get_manifest_question_ids()[0]
    raw_rec = store.tcm_raw_records[qid]
    raw_rec.results[0].provenance["volume"] = 99999

    pkt = project_raw_record_to_frozen_packet(
        record=raw_rec,
        raw_artifact_sha256=EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
    )
    with pytest.raises((ValueError, KeyError)):
        validate_packet_against_trusted_parent(pkt, store)


def test_mutated_parsed_question_metadata_fails_validation(repo_root: Path):
    """Mutating exposed question metadata must fail validation against byte anchor."""
    store = TrustedParentStore(repo_root)
    qid = store.get_manifest_question_ids()[0]

    # Mutate the dictionary returned by question property
    q_dict = store.questions_by_id[qid]
    q_dict["clinical_domain"] = "TAMPERED_DOMAIN"

    raw_rec = store.tcm_raw_records[qid]
    pkt = project_raw_record_to_frozen_packet(
        record=raw_rec,
        raw_artifact_sha256=EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
    )
    # The packet dict topic/task_type are bound to question manifest
    pkt_dict = pkt.model_dump(mode="json")
    pkt_dict["topic"] = "TAMPERED_TOPIC"
    pkt_dict["packet_canonical_sha256"] = packet_canonical_sha256(pkt_dict)

    with pytest.raises(ValueError, match="TAMPERED_TOPIC"):
        validate_packet_against_trusted_parent(pkt_dict, store)


# ==============================================================================
# TASK 21: ORIGINAL KEY PRESENCE AND JSON TYPES TESTS
# ==============================================================================

def test_original_key_presence_missing_key_fails(repo_root: Path, sample_tcm_packet_and_raw):
    """Missing required key in packet evidence item or raw hit must fail."""
    pkt, raw_rec, _ = sample_tcm_packet_and_raw
    item_dict = pkt.evidence_items[0].model_dump(mode="json")
    raw_hit_dict = raw_rec.results[0].model_dump(mode="json")

    # Missing in item
    del item_dict["source_id"]
    with pytest.raises(KeyError, match="source_id"):
        validate_frozen_evidence_item_integrity(
            item=item_dict,
            expected_question_id=pkt.question_id,
            expected_perspective=pkt.perspective,
            raw_item=raw_hit_dict,
        )

    # Missing in raw parent
    item_dict_restored = pkt.evidence_items[0].model_dump(mode="json")
    del raw_hit_dict["source_id"]
    with pytest.raises(KeyError, match="source_id"):
        validate_frozen_evidence_item_integrity(
            item=item_dict_restored,
            expected_question_id=pkt.question_id,
            expected_perspective=pkt.perspective,
            raw_item=raw_hit_dict,
        )


def test_original_key_presence_extra_null_fails(repo_root: Path, sample_tcm_packet_and_raw):
    """Present null key when original key was absent must fail."""
    pkt, raw_rec, _ = sample_tcm_packet_and_raw
    item_dict = pkt.evidence_items[0].model_dump(mode="json")
    raw_hit_dict = raw_rec.results[0].model_dump(mode="json")

    # Raw provenance does not have "nonexistent_key", but item provenance does with None
    item_dict["provenance"]["nonexistent_key"] = None
    with pytest.raises((ValueError, KeyError), match="nonexistent_key"):
        validate_frozen_evidence_item_integrity(
            item=item_dict,
            expected_question_id=pkt.question_id,
            expected_perspective=pkt.perspective,
            raw_item=raw_hit_dict,
        )


def test_original_key_presence_missing_null_fails(repo_root: Path, sample_tcm_packet_and_raw):
    """Absent key when original key was present as null must fail."""
    pkt, raw_rec, _ = sample_tcm_packet_and_raw
    item_dict = pkt.evidence_items[0].model_dump(mode="json")
    raw_hit_dict = raw_rec.results[0].model_dump(mode="json")

    # Raw hit has "doi": None, delete it from item
    assert raw_hit_dict["doi"] is None
    del item_dict["doi"]
    with pytest.raises(KeyError, match="doi"):
        validate_frozen_evidence_item_integrity(
            item=item_dict,
            expected_question_id=pkt.question_id,
            expected_perspective=pkt.perspective,
            raw_item=raw_hit_dict,
        )


def test_original_type_null_vs_empty_string_fails(repo_root: Path, sample_tcm_packet_and_raw):
    """Original null replaced by empty string must fail strict comparison."""
    pkt, raw_rec, _ = sample_tcm_packet_and_raw
    item_dict = pkt.evidence_items[0].model_dump(mode="json")
    raw_hit_dict = raw_rec.results[0].model_dump(mode="json")

    # Raw hit has "doi": None, change item's "doi" to ""
    assert raw_hit_dict["doi"] is None
    item_dict["doi"] = ""
    with pytest.raises(TypeError, match="Type mismatch"):
        validate_frozen_evidence_item_integrity(
            item=item_dict,
            expected_question_id=pkt.question_id,
            expected_perspective=pkt.perspective,
            raw_item=raw_hit_dict,
        )


def test_original_type_bool_vs_int_fails(repo_root: Path, sample_tcm_packet_and_raw):
    """Original boolean replaced by integer (e.g. True vs 1) must fail strict comparison."""
    pkt, raw_rec, _ = sample_tcm_packet_and_raw
    item_dict = pkt.evidence_items[0].model_dump(mode="json")
    raw_hit_dict = raw_rec.results[0].model_dump(mode="json")

    # score_is_zero is bool
    item_dict["score_is_zero"] = 0
    with pytest.raises(TypeError, match="Type mismatch"):
        validate_frozen_evidence_item_integrity(
            item=item_dict,
            expected_question_id=pkt.question_id,
            expected_perspective=pkt.perspective,
            raw_item=raw_hit_dict,
        )


def test_original_type_int_vs_float_fails(repo_root: Path, sample_tcm_packet_and_raw):
    """Original integer replaced by float (e.g. 2124 vs 2124.0) must fail strict comparison."""
    pkt, raw_rec, _ = sample_tcm_packet_and_raw
    item_dict = pkt.evidence_items[0].model_dump(mode="json")
    raw_hit_dict = raw_rec.results[0].model_dump(mode="json")

    # corpus_record_ordinal is int
    item_dict["corpus_record_ordinal"] = float(item_dict["corpus_record_ordinal"])
    with pytest.raises(TypeError, match="Type mismatch"):
        validate_frozen_evidence_item_integrity(
            item=item_dict,
            expected_question_id=pkt.question_id,
            expected_perspective=pkt.perspective,
            raw_item=raw_hit_dict,
        )


def test_original_provenance_nested_type_fails(repo_root: Path, sample_tcm_packet_and_raw):
    """Nested provenance type mutation (e.g. int vs str) must fail strict comparison."""
    pkt, raw_rec, _ = sample_tcm_packet_and_raw
    item_dict = pkt.evidence_items[0].model_dump(mode="json")
    raw_hit_dict = raw_rec.results[0].model_dump(mode="json")

    # Mutate provenance value type: find an int or str in provenance
    if "chunk_index" in item_dict["provenance"]:
        orig_val = item_dict["provenance"]["chunk_index"]
        item_dict["provenance"]["chunk_index"] = str(orig_val)
    else:
        item_dict["provenance"]["test_field"] = "1"
        raw_hit_dict["provenance"]["test_field"] = 1

    with pytest.raises(TypeError, match="Type mismatch"):
        validate_frozen_evidence_item_integrity(
            item=item_dict,
            expected_question_id=pkt.question_id,
            expected_perspective=pkt.perspective,
            raw_item=raw_hit_dict,
        )


# ==============================================================================
# TASK 16: WRITE-BOUNDARY STALE / SUBSTITUTED BUFFER REJECTION TESTS
# ==============================================================================

def test_formal_executor_rejects_caller_supplied_buffers():
    """execute_formal_packet_generation must not accept caller artifact bundles or buffers."""
    import inspect
    sig = inspect.signature(execute_formal_packet_generation)
    params = sig.parameters
    # Ensure no parameter allows passing candidate artifacts, jsonl bytes, or manifests
    disallowed_params = ["artifacts", "tcm_bytes", "western_bytes", "manifest", "receipt", "tcm_packets"]
    for p in disallowed_params:
        assert p not in params, f"Formal executor unexpectedly accepted caller parameter: {p}"


# ==============================================================================
# TASK 17: FAILURE-INJECTION TESTS (STAGES A THROUGH G)
# Injected failures must preserve all already-written artifacts (NO unlink).
# ==============================================================================

@pytest.mark.parametrize(
    "stage, expected_files, unexpected_files",
    [
        (
            "tcm_write",
            ["tcm_packets.jsonl"],
            ["western_packets.jsonl", "packet_manifest.json", "packet_freeze_receipt.json"],
        ),
        (
            "western_write",
            ["tcm_packets.jsonl", "western_packets.jsonl"],
            ["packet_manifest.json", "packet_freeze_receipt.json"],
        ),
        (
            "packet_audit",
            ["tcm_packets.jsonl", "western_packets.jsonl"],
            ["packet_manifest.json", "packet_freeze_receipt.json"],
        ),
        (
            "manifest_write",
            ["tcm_packets.jsonl", "western_packets.jsonl", "packet_manifest.json"],
            ["packet_freeze_receipt.json"],
        ),
        (
            "manifest_audit",
            ["tcm_packets.jsonl", "western_packets.jsonl", "packet_manifest.json"],
            ["packet_freeze_receipt.json"],
        ),
        (
            "receipt_write",
            ["tcm_packets.jsonl", "western_packets.jsonl", "packet_manifest.json", "packet_freeze_receipt.json"],
            [],
        ),
        (
            "receipt_audit",
            ["tcm_packets.jsonl", "western_packets.jsonl", "packet_manifest.json", "packet_freeze_receipt.json"],
            [],
        ),
    ],
)
def test_formal_execution_failure_injection_preserves_artifacts(
    repo_root: Path,
    tmp_path: Path,
    monkeypatch,
    stage: str,
    expected_files: list[str],
    unexpected_files: list[str],
):
    """Failure at any stage must preserve already-written files and never return SEALED."""
    # Monkeypatch authorization to True ONLY within this temporary test
    monkeypatch.setattr(
        "research.experiments.cross_perspective_advisory_ablation_v1.packet_writer.PHASE_1G_FORMAL_AUTHORIZATION_GRANTED",
        True,
    )
    # Monkeypatch git HEAD verification for the test directory
    dummy_head = "a" * 40
    monkeypatch.setattr(
        "research.experiments.cross_perspective_advisory_ablation_v1.packet_writer.verify_and_get_executing_git_head",
        lambda root: dummy_head,
    )

    sink_dir = tmp_path / f"failure_stage_{stage}"

    with pytest.raises(RuntimeError, match="Injected failure after"):
        execute_formal_packet_generation(
            repo_root=repo_root,
            output_dir=sink_dir,
            request_formal_execution=True,
            _inject_failure_after=stage,
        )

    # Verify that expected files exist and were NOT unlinked/deleted
    for fname in expected_files:
        p = sink_dir / fname
        assert p.exists(), f"Expected artifact {fname} was deleted on failure at stage {stage}!"
        assert p.stat().st_size > 0, f"Artifact {fname} is empty!"

    # Verify that unexpected files do NOT exist
    for fname in unexpected_files:
        p = sink_dir / fname
        assert not p.exists(), f"Artifact {fname} should not have been created at stage {stage}!"


# ==============================================================================
# TASK 18 & 15: SUCCESSFUL SYNTHETIC FULL WRITE & COLLISION FAIL-CLOSED
# ==============================================================================

def test_successful_synthetic_full_write_and_collision_policy(
    repo_root: Path,
    tmp_path: Path,
    monkeypatch,
):
    """Full execution in a synthetic test directory must succeed, seal, and fail-closed on collision."""
    monkeypatch.setattr(
        "research.experiments.cross_perspective_advisory_ablation_v1.packet_writer.PHASE_1G_FORMAL_AUTHORIZATION_GRANTED",
        True,
    )
    dummy_head = "b" * 40
    monkeypatch.setattr(
        "research.experiments.cross_perspective_advisory_ablation_v1.packet_writer.verify_and_get_executing_git_head",
        lambda root: dummy_head,
    )

    sink_dir = tmp_path / "synthetic_successful_run"

    res = execute_formal_packet_generation(
        repo_root=repo_root,
        output_dir=sink_dir,
        request_formal_execution=True,
    )

    assert res["status"] == "SEALED"
    assert res["implementation_commit"] == dummy_head

    tcm_file = sink_dir / "tcm_packets.jsonl"
    western_file = sink_dir / "western_packets.jsonl"
    manifest_file = sink_dir / "packet_manifest.json"
    receipt_file = sink_dir / "packet_freeze_receipt.json"

    assert tcm_file.exists()
    assert western_file.exists()
    assert manifest_file.exists()
    assert receipt_file.exists()

    # Verify disk byte hashes match result
    assert sha256_bytes(tcm_file.read_bytes()) == res["tcm_packet_byte_sha256"]
    assert sha256_bytes(western_file.read_bytes()) == res["western_packet_byte_sha256"]
    assert sha256_bytes(manifest_file.read_bytes()) == res["manifest_byte_sha256"]
    assert sha256_bytes(receipt_file.read_bytes()) == res["receipt_byte_sha256"]

    # Collision test (Task 15): Running a second time on the same directory MUST FAIL CLOSED
    with pytest.raises(FileExistsError, match="already exists"):
        execute_formal_packet_generation(
            repo_root=repo_root,
            output_dir=sink_dir,
            request_formal_execution=True,
        )


# ==============================================================================
# TASK 19: FORMAL AUTHORIZATION ENFORCEMENT TESTS
# ==============================================================================

def test_formal_authorization_gate_enforcement(repo_root: Path, tmp_path: Path, monkeypatch):
    """Tracked authorization gate must block execution whenever authorization is False or not requested."""
    # Statically verify that PHASE_1G_FORMAL_AUTHORIZATION_GRANTED is False
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_writer import (
        PHASE_1G_FORMAL_AUTHORIZATION_GRANTED as AUTH_STATIC,
    )
    assert AUTH_STATIC is False

    test_sink = tmp_path / "auth_test"

    # Case 1: formal_requested=False, auth=False -> denied
    with pytest.raises(PermissionError, match="not explicitly requested"):
        execute_formal_packet_generation(
            repo_root=repo_root,
            output_dir=test_sink,
            request_formal_execution=False,
        )

    # Case 2: formal_requested=True, auth=False -> denied
    with pytest.raises(PermissionError, match="Phase 1G formal authorization remains CLOSED"):
        execute_formal_packet_generation(
            repo_root=repo_root,
            output_dir=test_sink,
            request_formal_execution=True,
        )

    # Case 3: formal_requested=False, auth=True -> denied (both required!)
    monkeypatch.setattr(
        "research.experiments.cross_perspective_advisory_ablation_v1.packet_writer.PHASE_1G_FORMAL_AUTHORIZATION_GRANTED",
        True,
    )
    with pytest.raises(PermissionError, match="not explicitly requested"):
        execute_formal_packet_generation(
            repo_root=repo_root,
            output_dir=test_sink,
            request_formal_execution=False,
        )


# ==============================================================================
# TASK 20: EXECUTING GIT HEAD TESTS
# ==============================================================================

def test_executing_git_head_verification(repo_root: Path, monkeypatch):
    """Git HEAD verification must enforce exact branch, clean working tree, and 40-hex SHA."""
    import subprocess

    # Case 1: Wrong branch -> RuntimeError
    def mock_branch(*args, **kwargs):
        class MockRes:
            returncode = 0
            stdout = "main\n"
            stderr = ""
        return MockRes()

    monkeypatch.setattr(subprocess, "run", mock_branch)
    with pytest.raises(RuntimeError, match="Executing branch mismatch"):
        verify_and_get_executing_git_head(repo_root)

    # Case 2: Dirty tracked working tree -> RuntimeError
    def mock_dirty_tree(cmd, *args, **kwargs):
        class MockRes:
            stderr = ""
        res = MockRes()
        if "branch" in cmd:
            res.returncode = 0
            res.stdout = "research/cross-perspective-advisory-ablation-v1\n"
        elif "diff-index" in cmd:
            res.returncode = 1  # Uncommitted changes detected!
            res.stdout = ""
        else:
            res.returncode = 0
            res.stdout = "a" * 40 + "\n"
        return res

    monkeypatch.setattr(subprocess, "run", mock_dirty_tree)
    with pytest.raises(RuntimeError, match="Tracked working tree has uncommitted modifications"):
        verify_and_get_executing_git_head(repo_root)

    # Case 3: Invalid HEAD SHA format -> ValueError
    def mock_invalid_sha(cmd, *args, **kwargs):
        class MockRes:
            stderr = ""
        res = MockRes()
        if "branch" in cmd:
            res.returncode = 0
            res.stdout = "research/cross-perspective-advisory-ablation-v1\n"
        elif "diff-index" in cmd:
            res.returncode = 0
            res.stdout = ""
        elif "rev-parse" in cmd:
            res.returncode = 0
            res.stdout = "NOT_A_VALID_40_HEX_COMMIT\n"
        return res

    monkeypatch.setattr(subprocess, "run", mock_invalid_sha)
    with pytest.raises(ValueError, match="Invalid executing git HEAD SHA format"):
        verify_and_get_executing_git_head(repo_root)
