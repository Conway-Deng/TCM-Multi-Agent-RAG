from __future__ import annotations

import hashlib
from pathlib import Path


PROMPT_ROOT = Path(__file__).resolve().parent
PROMPT_ROLES = (
    "planner", "syndrome", "herbs", "acupuncture", "constitution", "dietary", "lifestyle",
    "debate", "critic", "revision", "evidence_judge", "hallucination_judge", "safety_judge",
    "conflict_judge", "confidence_judge", "provenance_judge", "synthesis",
)


def prompt_metadata() -> tuple[dict[str, str], dict[str, str]]:
    versions: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for role in PROMPT_ROLES:
        path = PROMPT_ROOT / role / "v1.txt"
        content = path.read_text(encoding="utf-8") if path.exists() else f"id: {role}\nversion: v1\n"
        versions[role] = "v1"
        hashes[role] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return versions, hashes
