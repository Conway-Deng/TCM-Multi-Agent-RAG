from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from pydantic import BaseModel


def canonical_json_dumps(obj: Any) -> str:
    """Serialize object to canonical JSON string with sorted keys and no unnecessary whitespace."""
    def _default(val: Any) -> Any:
        if isinstance(val, (datetime, date)):
            return val.isoformat()
        if isinstance(val, set):
            return sorted(list(val))
        if isinstance(val, Path):
            return str(val).replace("\\", "/")
        if isinstance(val, BaseModel):
            return val.model_dump(mode="json")
        raise TypeError(f"Object of type {type(val)} is not JSON serializable")

    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_default,
    )


def sha256_bytes(data: bytes) -> str:
    """Compute hex SHA256 digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Compute hex SHA256 digest of UTF-8 encoded string."""
    return sha256_bytes(text.encode("utf-8"))


def sha256_canonical_obj(obj: Any) -> str:
    """Compute hex SHA256 digest of canonical JSON representation of object."""
    if isinstance(obj, BaseModel):
        dumped = obj.model_dump(mode="json")
        return sha256_text(canonical_json_dumps(dumped))
    return sha256_text(canonical_json_dumps(obj))


def sha256_file(path: str | Path) -> str:
    """Compute hex SHA256 digest of a file in streaming chunks."""
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {target}")
    hasher = hashlib.sha256()
    with target.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_file_hash(path: str | Path, expected_sha256: str) -> bool:
    """Verify that file matches the expected SHA256 hash."""
    actual = sha256_file(path)
    return actual.lower() == expected_sha256.lower()
