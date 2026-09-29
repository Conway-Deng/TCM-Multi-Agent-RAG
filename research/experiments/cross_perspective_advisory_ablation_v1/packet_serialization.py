from __future__ import annotations

import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _REPO_ROOT / "backend"
_CURRENT_DIR = Path(__file__).resolve().parent

for p in (str(_CURRENT_DIR), str(_BACKEND_DIR), str(_REPO_ROOT)):
    if p in sys.path:
        sys.path.remove(p)

sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_BACKEND_DIR))

try:
    from .packet_contract import (
        AMENDMENT_ID,
        CANONICAL_JSON_KWARGS,
        MANIFEST_SCHEMA_VERSION,
        PACKET_CONTRACT_ID,
        RECEIPT_SCHEMA_VERSION,
        SCHEMA_VERSION,
        SERIALIZATION_VERSION,
        STUDY_ID,
    )
except ImportError:
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_contract import (
        AMENDMENT_ID,
        CANONICAL_JSON_KWARGS,
        MANIFEST_SCHEMA_VERSION,
        PACKET_CONTRACT_ID,
        RECEIPT_SCHEMA_VERSION,
        SCHEMA_VERSION,
        SERIALIZATION_VERSION,
        STUDY_ID,
    )


def validate_serializable_value(val: Any, path: str = "root") -> Any:
    """Validate that val contains only strictly supported canonical JSON types.
    
    Rejects:
    - NaN, +Infinity, -Infinity
    - lone/invalid Unicode surrogates
    - sets, Path, datetime, custom objects
    - non-string object keys
    """
    if isinstance(val, BaseModel):
        return validate_serializable_value(val.model_dump(mode="json"), path=path)

    if val is None:
        return None

    if isinstance(val, bool):
        return val

    if isinstance(val, int):
        return val

    if isinstance(val, float):
        if not math.isfinite(val):
            raise ValueError(f"Non-finite float ({val}) not allowed in canonical JSON at {path}")
        return val

    if isinstance(val, str):
        # Strict UTF-8 surrogate check
        try:
            val.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError(f"Lone/invalid Unicode surrogate in string at {path}: {exc}") from exc
        return val

    if isinstance(val, (list, tuple)):
        return [
            validate_serializable_value(item, path=f"{path}[{idx}]")
            for idx, item in enumerate(val)
        ]

    if isinstance(val, dict):
        cleaned: dict[str, Any] = {}
        for k, v in val.items():
            if not isinstance(k, str):
                raise TypeError(f"Dictionary keys must be strings, got {type(k).__name__} at {path}")
            try:
                k.encode("utf-8", errors="strict")
            except UnicodeEncodeError as exc:
                raise ValueError(f"Lone surrogate in dictionary key at {path}: {exc}") from exc
            cleaned[k] = validate_serializable_value(v, path=f"{path}.{k}")
        return cleaned

    raise TypeError(
        f"Unsupported type for canonical JSON at {path}: {type(val).__name__} (value: {val!r})"
    )


def canonical_json_text(obj: Any) -> str:
    """Format obj as canonical JSON text under CPAA1-PACKET-SERIALIZATION-V1.
    
    Reference canonical operation:
    json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    """
    cleaned = validate_serializable_value(obj)
    return json.dumps(cleaned, **CANONICAL_JSON_KWARGS)


def canonical_json_bytes(obj: Any) -> bytes:
    """Format obj as strict UTF-8 encoded canonical JSON bytes with no BOM."""
    text = canonical_json_text(obj)
    return text.encode("utf-8", errors="strict")


def serialize_jsonl_records(records: Iterable[dict[str, Any] | BaseModel]) -> bytes:
    """Serialize records to JSONL bytes according to CPAA1-PACKET-SERIALIZATION-V1.
    
    Rules:
    - UTF-8, no BOM, LF only (b"\\n")
    - Exactly one LF per record
    - Exactly one final LF
    """
    lines: list[bytes] = []
    for rec in records:
        line_bytes = canonical_json_bytes(rec) + b"\n"
        lines.append(line_bytes)
    return b"".join(lines)


def serialize_metadata_json(obj: dict[str, Any] | BaseModel) -> bytes:
    """Serialize a single metadata JSON object file with exactly one final LF."""
    return canonical_json_bytes(obj) + b"\n"


def sha256_bytes(data: bytes) -> str:
    """Compute lower-case 64-character hex SHA256 digest of exact bytes."""
    return hashlib.sha256(data).hexdigest()


def packet_canonical_sha256(packet: dict[str, Any] | BaseModel) -> str:
    """Compute canonical SHA256 of native packet object with packet_canonical_sha256 removed.
    
    P_without_hash = P with ONLY top-level packet_canonical_sha256 removed.
    packet_canonical_sha256 = SHA256(UTF8(C(P_without_hash))).hexdigest()
    No trailing newline participates.
    """
    if isinstance(packet, BaseModel):
        data = packet.model_dump(mode="json")
    else:
        data = copy.deepcopy(packet)

    cleaned = {k: v for k, v in data.items() if k != "packet_canonical_sha256"}
    return sha256_bytes(canonical_json_bytes(cleaned))


def perspective_canonical_aggregate_sha256(
    packets: Sequence[dict[str, Any] | BaseModel],
) -> str:
    """Compute perspective canonical aggregate SHA256 over 48 packet objects.
    
    Takes the 48 P_without_hash packet objects in frozen question-manifest order.
    Returns SHA256(UTF8(C(array_of_48_packet_objects_without_self_hash))).hexdigest().
    No trailing newline participates.
    """
    cleaned_packets: list[dict[str, Any]] = []
    for pkt in packets:
        if isinstance(pkt, BaseModel):
            data = pkt.model_dump(mode="json")
        else:
            data = copy.deepcopy(pkt)
        cleaned = {k: v for k, v in data.items() if k != "packet_canonical_sha256"}
        cleaned_packets.append(cleaned)

    return sha256_bytes(canonical_json_bytes(cleaned_packets))


def manifest_canonical_sha256(manifest: dict[str, Any] | BaseModel) -> str:
    """Compute canonical SHA256 over manifest object. All fields participate."""
    if isinstance(manifest, BaseModel):
        data = manifest.model_dump(mode="json")
    else:
        data = copy.deepcopy(manifest)
    return sha256_bytes(canonical_json_bytes(data))


def manifest_file_bytes(manifest: dict[str, Any] | BaseModel) -> bytes:
    """Compute exact manifest file bytes: UTF8(C(manifest)) + b"\\n"."""
    return serialize_metadata_json(manifest)


def receipt_file_bytes(receipt: dict[str, Any] | BaseModel) -> bytes:
    """Compute exact receipt file bytes: UTF8(C(receipt)) + b"\\n"."""
    return serialize_metadata_json(receipt)


def strict_json_loads(data: str | bytes) -> Any:
    """Parse JSON string or bytes, rejecting duplicate keys and lone surrogates."""
    if isinstance(data, bytes):
        text = data.decode("utf-8", errors="strict")
    else:
        text = data
        text.encode("utf-8", errors="strict")

    def _strict_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        res: dict[str, Any] = {}
        for k, v in pairs:
            if k in res:
                raise ValueError(f"Duplicate key found in JSON: {k!r}")
            res[k] = v
        return res

    return json.loads(text, object_pairs_hook=_strict_pairs_hook)


def strict_deep_compare(a: Any, b: Any, path: str = "root") -> None:
    """Recursively compare two values with type-strictness.
    
    Distinguishes:
    - bool from int (e.g. True != 1)
    - int from float (e.g. 1 != 1.0)
    - None from missing, None from "", [] from None
    - float -0.0 from 0.0
    - list ordering is binding
    - dict key ordering is not binding, but keys and values must match
    """
    # Normalize BaseModel to dict
    if isinstance(a, BaseModel):
        a = a.model_dump(mode="json")
    if isinstance(b, BaseModel):
        b = b.model_dump(mode="json")

    # Sequence type normalization (tuple/list)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            raise ValueError(f"Sequence length mismatch at {path}: {len(a)} != {len(b)}")
        for idx, (item_a, item_b) in enumerate(zip(a, b)):
            strict_deep_compare(item_a, item_b, path=f"{path}[{idx}]")
        return

    if type(a) is not type(b):
        raise TypeError(
            f"Type mismatch at {path}: {type(a).__name__} vs {type(b).__name__} (values: {a!r} vs {b!r})"
        )

    if a is None:
        return

    if isinstance(a, bool):
        if a is not b:
            raise ValueError(f"Boolean mismatch at {path}: {a} != {b}")
        return

    if isinstance(a, (int, str)):
        if a != b:
            raise ValueError(f"Value mismatch at {path}: {a!r} != {b!r}")
        return

    if isinstance(a, float):
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError(f"Non-finite float in comparison at {path}: {a} vs {b}")
        if a != b:
            raise ValueError(f"Float mismatch at {path}: {a} != {b}")
        if math.copysign(1.0, a) != math.copysign(1.0, b):
            raise ValueError(f"Float sign mismatch at {path}: {a} != {b}")
        return

    if isinstance(a, dict):
        keys_a = set(a.keys())
        keys_b = set(b.keys())
        if keys_a != keys_b:
            missing_in_b = keys_a - keys_b
            missing_in_a = keys_b - keys_a
            raise ValueError(
                f"Dict keys mismatch at {path}: missing_in_second={missing_in_b}, missing_in_first={missing_in_a}"
            )
        for k in keys_a:
            strict_deep_compare(a[k], b[k], path=f"{path}.{k}")
        return

    raise TypeError(f"Unsupported type for strict comparison at {path}: {type(a).__name__}")
