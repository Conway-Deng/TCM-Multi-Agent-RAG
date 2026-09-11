from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

SCHEMAS: dict[str, tuple[set[str], set[str]]] = {
    "initial": ({"answer", "evidence_ids", "uncertainties"}, {"evidence_ids", "uncertainties"}),
    "critique": ({"target_seat", "disagreements", "missing_evidence_concerns", "grounding_concerns", "source_ids"}, {"disagreements", "missing_evidence_concerns", "grounding_concerns", "source_ids"}),
    "revision": ({"revised_answer", "evidence_ids", "critique_uptake", "changes_made"}, {"evidence_ids", "critique_uptake", "changes_made"}),
    "consensus": ({"answer", "evidence_ids"}, {"evidence_ids"}),
}


class StructuredOutputError(ValueError):
    pass


@dataclass(frozen=True)
class StructuredOutput:
    value: dict[str, Any]
    normalized_text: str
    audit: dict[str, Any]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def visible_text_only(provider_message: dict[str, Any]) -> str:
    """Return only visible content; reasoning_content is deliberately ignored."""
    content = provider_message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise StructuredOutputError("provider message has no non-empty visible content")
    return content


def _top_level_object_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    depth = 0
    start = -1
    quoted = False
    escaped = False
    for index, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth == 0:
                raise StructuredOutputError("unmatched closing brace")
            depth -= 1
            if depth == 0:
                spans.append((start, index + 1))
                start = -1
    if quoted or depth:
        raise StructuredOutputError("truncated or incomplete JSON object")
    return spans


def _harmless_wrapper(text: str) -> bool:
    compact = " ".join(text.strip().split()).casefold()
    if not compact:
        return True
    return bool(re.fullmatch(r"(?:here is|here's)?\s*(?:the\s+)?(?:requested\s+)?(?:json|json object|response|output)(?:\s+is)?\s*[:.\-]*", compact))


def normalize(raw_text: str) -> tuple[str, str]:
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise StructuredOutputError("empty model output")
    stripped = raw_text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*\r?\n?(.*?)\r?\n?```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        inner = fence.group(1).strip()
        if "```" in inner:
            raise StructuredOutputError("nested or multiple code fences are not allowed")
        return inner, "REMOVE_SINGLE_JSON_FENCE"
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return stripped, "TRIM_WHITESPACE" if stripped != raw_text else "NONE"
    spans = _top_level_object_spans(stripped)
    if len(spans) != 1:
        raise StructuredOutputError(f"expected exactly one complete top-level JSON object; found {len(spans)}")
    start, end = spans[0]
    before, candidate, after = stripped[:start], stripped[start:end], stripped[end:]
    if not (_harmless_wrapper(before) and _harmless_wrapper(after)):
        raise StructuredOutputError("text outside JSON is not an allowed non-semantic wrapper")
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(f"JSON syntax remains invalid: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise StructuredOutputError("top-level JSON must be an object")
    return candidate, "EXTRACT_SINGLE_UNAMBIGUOUS_JSON_OBJECT"


def parse_and_validate(
    raw_text: str,
    *,
    schema: str,
    allowed_source_ids: Iterable[str],
    allowed_target_seats: Iterable[str] = ("A", "B", "C"),
    critique_inputs: Iterable[dict[str, Any]] | None = None,
) -> StructuredOutput:
    if schema not in SCHEMAS:
        raise StructuredOutputError(f"unknown schema: {schema}")
    normalized, action = normalize(raw_text)
    try:
        value = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(f"JSON syntax remains invalid: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise StructuredOutputError("top-level JSON must be an object")
    required, array_fields = SCHEMAS[schema]
    if set(value) != required:
        raise StructuredOutputError(f"schema fields differ: expected {sorted(required)}, got {sorted(value)}")
    for field in required - array_fields:
        if not isinstance(value[field], str) or not value[field].strip():
            raise StructuredOutputError(f"{field} must be a non-empty string")
    for field in array_fields:
        if not isinstance(value[field], list) or any(not isinstance(item, str) for item in value[field]):
            raise StructuredOutputError(f"{field} must be a string array")
    if schema == "critique" and value["target_seat"] not in set(allowed_target_seats):
        raise StructuredOutputError("critique target seat is invalid")
    source_field = "source_ids" if schema == "critique" else "evidence_ids"
    allowed = set(allowed_source_ids)
    if not value[source_field] or set(value[source_field]) - allowed:
        raise StructuredOutputError(f"{source_field} contains missing or invalid source IDs")
    actionable_critique_count = None
    empty_uptake_allowed = None
    if schema == "revision":
        if critique_inputs is None:
            raise StructuredOutputError("revision validation requires the exact critique inputs")
        critiques = list(critique_inputs)
        actionable_fields = ("disagreements", "missing_evidence_concerns", "grounding_concerns")
        actionable_critique_count = 0
        for index, critique in enumerate(critiques):
            if not isinstance(critique, dict):
                raise StructuredOutputError(f"critique input {index} is not an object")
            for field in actionable_fields:
                items = critique.get(field)
                if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
                    raise StructuredOutputError(f"critique input {index} has invalid {field}")
                actionable_critique_count += sum(bool(item.strip()) for item in items)
        empty_uptake_allowed = actionable_critique_count == 0
        if not value["critique_uptake"] and not empty_uptake_allowed:
            raise StructuredOutputError("revision must record critique uptake when actionable critique items exist")
    audit = {
        "raw_text_hash": _sha(raw_text),
        "normalized_text_hash": _sha(normalized),
        "normalization_action": action,
        "schema": schema,
        "schema_validation_result": "PASS",
    }
    if schema == "revision":
        audit["actionable_critique_count"] = actionable_critique_count
        audit["empty_uptake_allowed"] = empty_uptake_allowed
    return StructuredOutput(
        value=value,
        normalized_text=normalized,
        audit=audit,
    )
