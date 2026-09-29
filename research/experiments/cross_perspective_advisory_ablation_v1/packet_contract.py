from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Final, Literal

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from .manifest import canonical_json_dumps, sha256_canonical_obj, sha256_text
except ImportError:
    from research.experiments.cross_perspective_advisory_ablation_v1.manifest import (
        canonical_json_dumps,
        sha256_canonical_obj,
        sha256_text,
    )

# Study, Amendment, and Contract Identifiers
STUDY_ID: Final[str] = "cross-perspective-advisory-ablation-v1"
AMENDMENT_ID: Final[str] = "CPAA1-PACKET-GOVERNANCE-AMENDMENT-V1"
PACKET_CONTRACT_ID: Final[str] = "CPAA1-FROZEN-PACKET-LOSSLESS-V1"
SERIALIZATION_VERSION: Final[str] = "CPAA1-PACKET-SERIALIZATION-V1"
SCHEMA_VERSION: Final[str] = "cpaa1_frozen_packet_v1"
MANIFEST_SCHEMA_VERSION: Final[str] = "cpaa1_packet_manifest_v1"
RECEIPT_SCHEMA_VERSION: Final[str] = "cpaa1_packet_freeze_receipt_v1"

# Frozen Corpus Anchors
EXPECTED_TCM_CORPUS_SHA256: Final[str] = (
    "316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9"
)
EXPECTED_WESTERN_CORPUS_SHA256: Final[str] = (
    "8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b"
)

# Canonical JSON Specification (CPAA1-PACKET-SERIALIZATION-V1)
# Reference operation:
# json.dumps(
#     obj,
#     ensure_ascii=False,
#     sort_keys=True,
#     separators=(",", ":"),
#     allow_nan=False,
# )
CANONICAL_JSON_KWARGS: Final[dict[str, Any]] = {
    "ensure_ascii": False,
    "sort_keys": True,
    "separators": (",", ":"),
    "allow_nan": False,
}

# Frozen Parent Artifact Anchors
QUESTION_MANIFEST_RELPATH: Final[str] = (
    "research/experiments/cross_perspective_advisory_ablation_v1/question_manifest.jsonl"
)
EXPECTED_QUESTION_MANIFEST_SHA256: Final[str] = (
    "a7daead783134ef6c2d4e5632153c19a8aa4a826a3c172838de90172796f9bbf"
)
TCM_RAW_RETRIEVAL_RELPATH: Final[str] = (
    "research/experiments/cross_perspective_advisory_ablation_v1/retrieval/retrieval_tcm_r0_top4.jsonl"
)
EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256: Final[str] = (
    "a82cd4894465cfabaf9de7fd47fde7afd2a956580230e14cf1797fe02ee97d40"
)
WESTERN_RAW_RETRIEVAL_RELPATH: Final[str] = (
    "research/experiments/cross_perspective_advisory_ablation_v1/retrieval/retrieval_western_r0_top4.jsonl"
)
EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256: Final[str] = (
    "a1933bba57d2c28609af19473954064fee4d7f1429717dfd93fe0e06bdd2f379"
)

# Expected Cardinalities
EXPECTED_QUESTION_COUNT: Final[int] = 48
EXPECTED_TCM_RECORDS: Final[int] = 48
EXPECTED_WESTERN_RECORDS: Final[int] = 48
EXPECTED_TOTAL_RECORDS: Final[int] = 96
HITS_PER_RECORD: Final[int] = 4
EXPECTED_TCM_ITEMS: Final[int] = 192
EXPECTED_WESTERN_ITEMS: Final[int] = 192
EXPECTED_TOTAL_ITEMS: Final[int] = 384

# Identity Templates
EVIDENCE_ID_TEMPLATE: Final[str] = "cpaa1:ev:{question_id}:{perspective}:R0:{rank}:{chunk_id}"
COMPATIBILITY_CLAIM_ID_TEMPLATE: Final[str] = "cpaa1:sx:{evidence_id}"
PACKET_ID_TEMPLATE: Final[str] = "cpaa1:packet:{question_id}:{perspective}"

# Research Metadata and Compatibility Semantics
SUPPORT_BASIS: Final[str] = "verbatim_source_copy"
SEMANTIC_SUPPORT_STATUS: Final[str] = "not_assessed"
COMPATIBILITY_CLAIM_KIND: Final[str] = "source_excerpt"
COMPATIBILITY_SUPPORT_STATUS: Final[str] = "supported"

# Invariant Rules
ALLOW_TRUNCATION: Final[bool] = False
ALLOW_MODEL_CALL: Final[bool] = False
ALLOW_RETRIEVAL_CALL: Final[bool] = False
ALLOW_REWRITING: Final[bool] = False
ALLOW_DEDUPLICATION: Final[bool] = False
ALLOW_SENTENCE_EXTRACTION: Final[bool] = False
ALLOW_EVIDENCE_SELECTION: Final[bool] = False

# Delimiter Escaping Rule
# If colons appear in identifiers, escape them as %3A to preserve namespace boundaries
def escape_delimiter(value: str) -> str:
    """Escape delimiter ':' as '%3A' in identifier segments if present."""
    return value.replace(":", "%3A")


def unescape_delimiter(value: str) -> str:
    """Unescape '%3A' back to ':'."""
    return value.replace("%3A", ":")


def format_evidence_id(question_id: str, perspective: str, rank: int, chunk_id: str) -> str:
    """Format a globally unique, deterministic native evidence ID."""
    if rank < 1 or rank > HITS_PER_RECORD:
        raise ValueError(f"rank must be 1..{HITS_PER_RECORD}, got {rank}")
    q_safe = escape_delimiter(question_id)
    p_safe = escape_delimiter(perspective)
    c_safe = escape_delimiter(chunk_id)
    return f"cpaa1:ev:{q_safe}:{p_safe}:R0:{rank}:{c_safe}"


def format_compatibility_claim_id(evidence_id: str) -> str:
    """Format deterministic compatibility wrapper claim ID from evidence ID."""
    return f"cpaa1:sx:{evidence_id}"


def format_packet_id(question_id: str, perspective: str) -> str:
    """Format deterministic packet ID."""
    q_safe = escape_delimiter(question_id)
    p_safe = escape_delimiter(perspective)
    return f"cpaa1:packet:{q_safe}:{p_safe}"


def compute_item_canonical_sha256(item_data: dict[str, Any]) -> str:
    """Compute canonical SHA256 of native evidence item dictionary."""
    return sha256_canonical_obj(item_data)


def compute_packet_canonical_sha256(packet_data: dict[str, Any]) -> str:
    """Compute canonical SHA256 of native evidence packet dictionary excluding packet_canonical_sha256."""
    cleaned = {k: v for k, v in packet_data.items() if k != "packet_canonical_sha256"}
    return sha256_canonical_obj(cleaned)
