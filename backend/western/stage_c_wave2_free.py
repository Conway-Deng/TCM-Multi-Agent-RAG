from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
from time import perf_counter
from typing import Any, Literal

from providers import build_llm_provider
from providers.openai_compatible import ProviderUnavailable

from .formal_eval import _atomic_new_json, _sha256, _utc_now
from .formal_judge import FormalJudgeOutput, JUDGE_SYSTEM_PROMPT
from .stage_c_free_judge import (
    OPERATIONAL_UNEVALUABILITY_LABEL,
    _attempt_classification,
    _classification_flags,
    _parse_utc,
    classify_provider_exception,
)
from .stage_c_judge_replacement import verify_scientific_and_historical_hashes
from .stage_c_preflight import (
    R3_PREFLIGHT_PROBE_COUNT,
    R3_PREFLIGHT_PROBE_PLAN_VERSION,
    StageCR3PreflightError,
    get_synthetic_probe_plan,
)
from .stage_c_preflight_v3 import (
    R3_JSON_MODE_RESPONSE_FORMAT,
    build_stage_c_r3_json_mode_prompt,
    validate_stage_c_r3_json_mode_probe_output,
)


WAVE2_POLICY_ID = "western-stage-c-judge-wave2-free-v0.1.5"
WAVE2_PROTOCOL_ID = "western_formal_v0.1.5"
WAVE2_POLICY_SHA256 = "5ac5b5bab86b853fe719303e92defcadc609015b29648630b29ed5db1191b596"
WAVE1_EXHAUSTION_SHA256 = "eead5bc8cbcd8fb27f79ca7095bc8d210d8ba513f2716120c493396ab9155827"
WAVE2_RELATIVE_DIR = (
    "research/experiments/western_formal_v0_1/stage_c_judge_wave2_free_v0_1_5"
)
WAVE2_POLICY_RELATIVE_PATH = f"{WAVE2_RELATIVE_DIR}/policy.json"
WAVE1_EXHAUSTION_RELATIVE_PATH = f"{WAVE2_RELATIVE_DIR}/wave1-exhaustion.json"
WAVE2_CATALOG_RELATIVE_PATH = f"{WAVE2_RELATIVE_DIR}/snapshots/provider-model-catalog.json"
WAVE2_PRICING_RELATIVE_PATH = f"{WAVE2_RELATIVE_DIR}/snapshots/pricing-ledger.json"
WAVE2_CAPABILITY_RELATIVE_PATH = f"{WAVE2_RELATIVE_DIR}/snapshots/capability-ledger.json"
WAVE2_ELIGIBILITY_RELATIVE_PATH = f"{WAVE2_RELATIVE_DIR}/eligibility/eligibility-ledger.json"
WAVE2_FREEZE_RELATIVE_PATH = f"{WAVE2_RELATIVE_DIR}/candidate-pool-freeze.json"
WAVE2_MANIFESTS_RELATIVE_DIR = f"{WAVE2_RELATIVE_DIR}/manifests"
WAVE2_ADJUDICATIONS_RELATIVE_DIR = f"{WAVE2_RELATIVE_DIR}/adjudications"
WAVE2_EXHAUSTION_RELATIVE_PATH = f"{WAVE2_RELATIVE_DIR}/wave2-exhaustion.json"

WAVE2_PROVIDER = "siliconflow"
WAVE2_FREE_ONLY = True
WAVE2_MAX_CANDIDATES = 4
WAVE3_PERMITTED = False
WAVE2_TRANSPORT = copy.deepcopy(R3_JSON_MODE_RESPONSE_FORMAT)
WAVE2_TEMPERATURE = 0
WAVE2_MAX_TOKENS = 1200
WAVE2_TIMEOUT_SECONDS = 120.0
WAVE2_MINIMUM_SPACING_SECONDS = 3600.0
WAVE2_REPLICATES_REQUIRED = 2
WAVE2_GENERATOR_MODEL = "Qwen/Qwen3-8B"
WAVE2_SORT_RULE = "ascending_utf8_bytes"
WAVE2_ZERO_PRICE = "0.000000"

WAVE1_POLICY_SHA256 = "1e77ab1a85ab54e155926c0c9c2b6a7e26728243415d6ccc484cc81c47f89648"
WAVE1_AMENDMENT_SHA256 = "87d237841b747fef74d1ed7d39ac99e2a0c8a84bf7ec57bc10222e399192bfc9"
PREVIOUSLY_TESTED_MODEL_IDS = frozenset(
    {
        "XingChenAGI/Xing4.0-29B",
        "THUDM/GLM-4-9B-0414",
        "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
        "Qwen/Qwen3.5-4B",
        "deepseek-ai/DeepSeek-V3.2",
    }
)

WAVE1_ANCHORS = {
    "candidate-01-replicate-01.json": "1f0a64a7b698e2d49c84f8f0b113d9f492ed4c40e742e4e664d8d0557efb8bf6",
    "candidate-01-replicate-01-recovery-01.json": "dff39085c3d9091b76a40634eadbf167cfc0ef8e360e79a863f399d0c92a33a2",
    "candidate-02-replicate-01.json": "31884df7556d5c24d87cce74fdcc227f348496fe57a2084fd03e98b29e29d3dd",
    "candidate-03-replicate-01.json": "d2028534671253b2068844344612841e343bfc8b37a3c41b34d76b43c5f2090a",
    "candidate-04-replicate-01.json": "47af4ef80b91b620f6bc88c50ea6698281fd2d3ea8ab87962b5ffbeb8bcf20ac",
    "candidate-04-replicate-01-recovery-01.json": "b0940bfec028d62a7e836b689705139a99ca51ca5f3d320b57cd82e066ad7002",
}
F4_ADJUDICATION_SHA256 = "09a4e0d98b1a83efbe7fc4d677dd5b1c6ee21f9c226e758dddb32158a73c3e4d"

SCIENTIFIC_ANCHORS = {
    "stage_a_retrieval_sha256": "91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e",
    "primary_stage_b_sha256": "afc0665858b0493d9c4dfbc2d8990ccd89c663f2b63278221407cb876feaf17c",
    "primary_stage_b_run_manifest_sha256": "32fbc0765fc91395af187abb46b92d2fb13b9eed3acbea016f8ac18a6bc00511",
    "protocol_v0_1_2_sha256": "af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192",
}

ThinkingToggle = Literal["omit", "send_false"]


class StageCWave2Error(RuntimeError):
    """A fail-closed Wave-2 policy, discovery, integrity, or execution error."""


@dataclass(frozen=True)
class Wave2Candidate:
    candidate_number: int
    model_id: str
    thinking_toggle: ThinkingToggle

    @property
    def expected_provider_enable_thinking(self) -> bool | None:
        return False if self.thinking_toggle == "send_false" else None


@dataclass(frozen=True)
class Wave2Registry:
    freeze_sha256: str
    candidates: tuple[Wave2Candidate, ...]
    freeze: dict[str, Any]

    def candidate(self, candidate_number: int) -> Wave2Candidate:
        for candidate in self.candidates:
            if candidate.candidate_number == candidate_number:
                return candidate
        raise StageCWave2Error(
            f"Wave-2 candidate number {candidate_number} is not in the frozen registry"
        )


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise StageCWave2Error(f"{label} is missing or corrupt at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StageCWave2Error(f"{label} must be a JSON object")
    return value


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise StageCWave2Error(f"{label} fields mismatch; missing={missing}, extra={extra}")


def _verify_file(path: Path, expected_sha: str, label: str) -> str:
    if not path.is_file():
        raise StageCWave2Error(f"{label} is missing at {path}")
    actual = _sha256(path)
    if actual != expected_sha:
        raise StageCWave2Error(
            f"{label} SHA256 mismatch: expected {expected_sha}, actual {actual}"
        )
    return actual


def verify_wave1_exhaustion_and_history(repository_root: Path) -> dict[str, str]:
    wave1_root = repository_root / (
        "research/experiments/western_formal_v0_1/"
        "stage_c_judge_replacement_policy_v2_free"
    )
    hashes = {
        "wave1_policy_sha256": _verify_file(
            wave1_root / "policy.json", WAVE1_POLICY_SHA256, "Wave-1 policy"
        ),
        "wave1_amendment_sha256": _verify_file(
            wave1_root
            / "amendments/operational_unevaluability_amendment_01/amendment.json",
            WAVE1_AMENDMENT_SHA256,
            "Wave-1 operational amendment",
        ),
    }
    for filename, expected in WAVE1_ANCHORS.items():
        hashes[filename] = _verify_file(
            wave1_root / "manifests" / filename,
            expected,
            f"Wave-1 manifest {filename}",
        )
    hashes["candidate-04-adjudication"] = _verify_file(
        wave1_root
        / "amendments/operational_unevaluability_amendment_01/adjudications/"
        "candidate-04-operationally-unevaluable.json",
        F4_ADJUDICATION_SHA256,
        "Wave-1 F4 adjudication",
    )
    exhaustion_path = repository_root / WAVE1_EXHAUSTION_RELATIVE_PATH
    hashes["wave1_exhaustion_sha256"] = _verify_file(
        exhaustion_path, WAVE1_EXHAUSTION_SHA256, "Wave-1 exhaustion record"
    )
    exhaustion = _read_json_object(exhaustion_path, "Wave-1 exhaustion record")
    if exhaustion.get("candidate_pool_exhausted") is not True:
        raise StageCWave2Error("Wave-1 exhaustion record does not mark the pool exhausted")
    if exhaustion.get("primary_judge_selected") is not False:
        raise StageCWave2Error("Wave-1 exhaustion record improperly selects a Primary Judge")
    expected_statuses = {
        1: OPERATIONAL_UNEVALUABILITY_LABEL,
        2: "terminal_candidate_readiness_failure",
        3: "terminal_candidate_readiness_failure",
        4: OPERATIONAL_UNEVALUABILITY_LABEL,
    }
    candidates = exhaustion.get("candidates")
    if not isinstance(candidates, list) or {
        item.get("candidate_number"): item.get("final_status")
        for item in candidates
        if isinstance(item, dict)
    } != expected_statuses:
        raise StageCWave2Error("Wave-1 exhaustion candidate statuses are inconsistent")
    return hashes


def verify_wave2_policy(repository_root: Path) -> dict[str, str]:
    history = verify_wave1_exhaustion_and_history(repository_root)
    try:
        scientific = verify_scientific_and_historical_hashes(repository_root)
    except Exception as exc:
        raise StageCWave2Error(f"Scientific anchor validation failed: {exc}") from exc
    for key, expected in SCIENTIFIC_ANCHORS.items():
        if scientific.get(key) != expected:
            raise StageCWave2Error(f"Scientific anchor {key} mismatch")
    policy_path = repository_root / WAVE2_POLICY_RELATIVE_PATH
    policy_sha = _verify_file(policy_path, WAVE2_POLICY_SHA256, "Wave-2 policy")
    policy = _read_json_object(policy_path, "Wave-2 policy")
    expected = {
        "policy_identity": WAVE2_POLICY_ID,
        "scientific_protocol_identity": WAVE2_PROTOCOL_ID,
        "provider": WAVE2_PROVIDER,
        "free_only": True,
        "maximum_wave2_candidates": WAVE2_MAX_CANDIDATES,
        "wave3_permitted": False,
        "candidate_pool_frozen_by_this_artifact": False,
    }
    for key, value in expected.items():
        if policy.get(key) != value:
            raise StageCWave2Error(f"Wave-2 policy field {key!r} mismatch")
    _parse_utc(policy.get("effective_at"))
    return {**scientific, **history, "wave2_policy_sha256": policy_sha}


def _validate_discovery_header(
    data: dict[str, Any],
    *,
    artifact_type: str,
    list_field: str,
    path: Path,
) -> tuple[str, list[dict[str, Any]]]:
    common = {
        "artifact_type",
        "provider",
        "snapshot_timestamp",
        "semantic_or_generation_outputs_used",
        "live_completion_calls_used",
        list_field,
    }
    if artifact_type == "provider_model_catalog":
        common.add("source_endpoint")
    else:
        common.add("evidence_source")
    if artifact_type == "capability_ledger":
        common.add("non_semantic_evidence_only")
    _require_exact_keys(data, common, artifact_type)
    if data.get("artifact_type") != artifact_type or data.get("provider") != WAVE2_PROVIDER:
        raise StageCWave2Error(f"{artifact_type} identity/provider mismatch at {path}")
    timestamp = data.get("snapshot_timestamp")
    _parse_utc(timestamp)
    if data.get("semantic_or_generation_outputs_used") is not False:
        raise StageCWave2Error(f"{artifact_type} used prohibited semantic/generation outputs")
    if data.get("live_completion_calls_used") is not False:
        raise StageCWave2Error(f"{artifact_type} used prohibited live completion calls")
    if artifact_type == "provider_model_catalog" and data.get("source_endpoint") != "/v1/models":
        raise StageCWave2Error("Catalog source endpoint must be /v1/models")
    if artifact_type == "capability_ledger" and data.get("non_semantic_evidence_only") is not True:
        raise StageCWave2Error("Capability ledger must use only non-semantic evidence")
    entries = data.get(list_field)
    if not isinstance(entries, list):
        raise StageCWave2Error(f"{artifact_type} {list_field} must be a list")
    if not all(isinstance(entry, dict) for entry in entries):
        raise StageCWave2Error(f"{artifact_type} entries must be objects")
    return timestamp, entries


def _index_unique(entries: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        model_id = entry.get("model_id")
        if not isinstance(model_id, str) or not model_id.strip() or model_id != model_id.strip():
            raise StageCWave2Error(f"{label} contains an invalid model_id")
        if model_id in indexed:
            raise StageCWave2Error(f"{label} contains duplicate model_id {model_id!r}")
        indexed[model_id] = entry
    return indexed


def validate_catalog_snapshot(path: Path) -> dict[str, Any]:
    data = _read_json_object(path, "Wave-2 catalog snapshot")
    timestamp, entries = _validate_discovery_header(
        data,
        artifact_type="provider_model_catalog",
        list_field="models",
        path=path,
    )
    for entry in entries:
        _require_exact_keys(entry, {"model_id"}, "catalog model")
    indexed = _index_unique(entries, "catalog")
    return {"data": data, "timestamp": timestamp, "entries": indexed, "sha256": _sha256(path)}


_PRICE_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.[0-9]{6}$")


def _validate_price(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _PRICE_PATTERN.fullmatch(value):
        raise StageCWave2Error(f"{label} must be null or a non-negative six-decimal string")
    return value


def validate_pricing_ledger(path: Path) -> dict[str, Any]:
    data = _read_json_object(path, "Wave-2 pricing ledger")
    timestamp, entries = _validate_discovery_header(
        data,
        artifact_type="pricing_ledger",
        list_field="prices",
        path=path,
    )
    for entry in entries:
        _require_exact_keys(
            entry,
            {"model_id", "input_price", "output_price", "evidence_reference"},
            "pricing entry",
        )
        _validate_price(entry.get("input_price"), "input_price")
        _validate_price(entry.get("output_price"), "output_price")
        if not isinstance(entry.get("evidence_reference"), str) or not entry["evidence_reference"].strip():
            raise StageCWave2Error("Pricing entry lacks an evidence reference")
    indexed = _index_unique(entries, "pricing ledger")
    return {"data": data, "timestamp": timestamp, "entries": indexed, "sha256": _sha256(path)}


def validate_capability_ledger(path: Path) -> dict[str, Any]:
    data = _read_json_object(path, "Wave-2 capability ledger")
    timestamp, entries = _validate_discovery_header(
        data,
        artifact_type="capability_ledger",
        list_field="capabilities",
        path=path,
    )
    expected_keys = {
        "model_id",
        "model_type",
        "openai_chat_completions_compatible",
        "json_object_compatible",
        "status",
        "account_accessible",
        "region_accessible",
        "thinking_toggle",
        "requires_candidate_specific_interface_changes",
        "aliases",
        "evidence_reference",
    }
    for entry in entries:
        _require_exact_keys(entry, expected_keys, "capability entry")
        aliases = entry.get("aliases")
        if not isinstance(aliases, list) or len(aliases) != len(set(aliases)) or not all(
            isinstance(alias, str) and alias.strip() == alias and alias for alias in aliases
        ):
            raise StageCWave2Error("Capability aliases must be unique non-empty strings")
        if entry.get("model_id") in aliases:
            raise StageCWave2Error("Capability aliases cannot repeat the exact model ID")
        if not isinstance(entry.get("evidence_reference"), str) or not entry["evidence_reference"].strip():
            raise StageCWave2Error("Capability entry lacks an evidence reference")
        if entry.get("requires_candidate_specific_interface_changes") not in {True, False}:
            raise StageCWave2Error("Capability interface-change field must be Boolean")
    indexed = _index_unique(entries, "capability ledger")
    return {"data": data, "timestamp": timestamp, "entries": indexed, "sha256": _sha256(path)}


def _exclusion_reasons(
    model_id: str,
    price: dict[str, Any],
    capability: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if model_id == WAVE2_GENERATOR_MODEL:
        reasons.append("generator_model_excluded")
    if model_id in PREVIOUSLY_TESTED_MODEL_IDS:
        reasons.append("previously_tested_exact_model")
    if set(capability.get("aliases", [])) & PREVIOUSLY_TESTED_MODEL_IDS:
        reasons.append("documented_alias_of_previously_tested_model")
    input_price = price.get("input_price")
    output_price = price.get("output_price")
    if input_price is None:
        reasons.append("unknown_input_price")
    elif input_price != WAVE2_ZERO_PRICE:
        reasons.append("nonzero_input_price")
    if output_price is None:
        reasons.append("unknown_output_price")
    elif output_price != WAVE2_ZERO_PRICE:
        reasons.append("nonzero_output_price")
    if capability.get("model_type") != "chat_completions":
        reasons.append("unsupported_or_non_chat_model_type")
    if capability.get("openai_chat_completions_compatible") is not True:
        reasons.append("openai_chat_completions_compatibility_not_documented")
    if capability.get("json_object_compatible") is not True:
        reasons.append("json_object_compatibility_not_documented")
    if capability.get("status") != "available":
        reasons.append("retired_deprecated_or_unavailable")
    if capability.get("account_accessible") is not True:
        reasons.append("account_access_not_documented")
    if capability.get("region_accessible") is not True:
        reasons.append("region_access_not_documented")
    if capability.get("thinking_toggle") not in {"omit", "send_false"}:
        reasons.append("thinking_behavior_unknown_or_unsupported")
    if capability.get("requires_candidate_specific_interface_changes") is not False:
        reasons.append("candidate_specific_interface_change_required")
    return reasons


def build_wave2_eligibility_ledger(
    catalog_path: Path,
    pricing_path: Path,
    capability_path: Path,
) -> dict[str, Any]:
    catalog = validate_catalog_snapshot(catalog_path)
    pricing = validate_pricing_ledger(pricing_path)
    capability = validate_capability_ledger(capability_path)
    timestamps = {catalog["timestamp"], pricing["timestamp"], capability["timestamp"]}
    if len(timestamps) != 1:
        raise StageCWave2Error("Discovery artifacts must share one identical snapshot timestamp")
    catalog_ids = set(catalog["entries"])
    if set(pricing["entries"]) != catalog_ids:
        raise StageCWave2Error("Pricing ledger must dispose every and only catalog model")
    if set(capability["entries"]) != catalog_ids:
        raise StageCWave2Error("Capability ledger must dispose every and only catalog model")
    ordered_catalog = sorted(catalog_ids, key=lambda value: value.encode("utf-8"))
    decisions: list[dict[str, Any]] = []
    eligible: list[str] = []
    thinking: dict[str, str] = {}
    for model_id in ordered_catalog:
        price = pricing["entries"][model_id]
        metadata = capability["entries"][model_id]
        reasons = _exclusion_reasons(model_id, price, metadata)
        if reasons:
            disposition = "excluded"
        else:
            disposition = "eligible"
            eligible.append(model_id)
            thinking[model_id] = metadata["thinking_toggle"]
        decisions.append(
            {
                "model_id": model_id,
                "disposition": disposition,
                "exclusion_reasons": reasons,
                "thinking_toggle": metadata.get("thinking_toggle") if not reasons else None,
            }
        )
    eligible = sorted(eligible, key=lambda value: value.encode("utf-8"))
    return {
        "artifact_type": "wave2_eligibility_ledger",
        "policy_identity": WAVE2_POLICY_ID,
        "scientific_protocol_identity": WAVE2_PROTOCOL_ID,
        "provider": WAVE2_PROVIDER,
        "free_only": True,
        "snapshot_timestamp": next(iter(timestamps)),
        "source_sha256": {
            "catalog": catalog["sha256"],
            "pricing": pricing["sha256"],
            "capability": capability["sha256"],
        },
        "complete_catalog_model_ids": ordered_catalog,
        "decisions": decisions,
        "complete_eligible_model_ids": eligible,
        "thinking_toggle_by_eligible_model": thinking,
        "all_catalog_models_disposed": len(decisions) == len(ordered_catalog),
        "semantic_or_generation_outputs_used": False,
        "live_completion_calls_used": False,
    }


def _canonical_wave2_paths(repository_root: Path) -> dict[str, Path]:
    return {
        "catalog": repository_root / WAVE2_CATALOG_RELATIVE_PATH,
        "pricing": repository_root / WAVE2_PRICING_RELATIVE_PATH,
        "capability": repository_root / WAVE2_CAPABILITY_RELATIVE_PATH,
        "eligibility": repository_root / WAVE2_ELIGIBILITY_RELATIVE_PATH,
        "freeze": repository_root / WAVE2_FREEZE_RELATIVE_PATH,
        "manifests": repository_root / WAVE2_MANIFESTS_RELATIVE_DIR,
        "adjudications": repository_root / WAVE2_ADJUDICATIONS_RELATIVE_DIR,
        "exhaustion": repository_root / WAVE2_EXHAUSTION_RELATIVE_PATH,
    }


def _ensure_new_path(path: Path, label: str) -> None:
    if path.exists() or path.with_suffix(path.suffix + ".tmp").exists():
        raise FileExistsError(f"Immutable {label} already exists at {path}")


def freeze_wave2_candidate_pool(
    repository_root: Path,
    *,
    catalog_path: Path | None = None,
    pricing_path: Path | None = None,
    capability_path: Path | None = None,
    eligibility_path: Path | None = None,
    freeze_path: Path | None = None,
    frozen_at: datetime | None = None,
) -> dict[str, Any]:
    anchors = verify_wave2_policy(repository_root)
    paths = _canonical_wave2_paths(repository_root)
    catalog = catalog_path or paths["catalog"]
    pricing = pricing_path or paths["pricing"]
    capability = capability_path or paths["capability"]
    eligibility_target = eligibility_path or paths["eligibility"]
    freeze_target = freeze_path or paths["freeze"]
    _ensure_new_path(eligibility_target, "Wave-2 eligibility ledger")
    _ensure_new_path(freeze_target, "Wave-2 candidate-pool freeze")
    eligibility = build_wave2_eligibility_ledger(catalog, pricing, capability)
    selected_ids = eligibility["complete_eligible_model_ids"][:WAVE2_MAX_CANDIDATES]
    selected = [
        {
            "candidate_number": index,
            "model_id": model_id,
            "thinking_toggle": eligibility["thinking_toggle_by_eligible_model"][model_id],
        }
        for index, model_id in enumerate(selected_ids, start=1)
    ]
    timestamp = frozen_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise StageCWave2Error("Wave-2 freeze timestamp must be timezone-aware")
    # Freeze the eligibility ledger first, then hash the exact bytes on disk.
    # This keeps the provenance stable across platforms whose text writers may
    # translate line endings.
    _atomic_new_json(eligibility_target, eligibility)
    freeze = {
        "artifact_type": "wave2_candidate_pool_freeze",
        "policy_identity": WAVE2_POLICY_ID,
        "policy_sha256": WAVE2_POLICY_SHA256,
        "scientific_protocol_identity": WAVE2_PROTOCOL_ID,
        "wave1_exhaustion_sha256": WAVE1_EXHAUSTION_SHA256,
        "frozen_at": timestamp.astimezone(timezone.utc).isoformat(),
        "snapshot_timestamp": eligibility["snapshot_timestamp"],
        "source_sha256": {
            **eligibility["source_sha256"],
            "eligibility": _sha256(eligibility_target),
        },
        "complete_catalog_model_ids": eligibility["complete_catalog_model_ids"],
        "complete_eligible_model_ids": eligibility["complete_eligible_model_ids"],
        "complete_exclusions": [
            decision
            for decision in eligibility["decisions"]
            if decision["disposition"] == "excluded"
        ],
        "deterministic_sort_rule": WAVE2_SORT_RULE,
        "selected_candidates": selected,
        "pool_size": len(selected),
        "maximum_wave2_candidates": WAVE2_MAX_CANDIDATES,
        "provider": WAVE2_PROVIDER,
        "free_only": True,
        "generator_exclusion": WAVE2_GENERATOR_MODEL,
        "previously_tested_model_exclusions": sorted(
            PREVIOUSLY_TESTED_MODEL_IDS, key=lambda value: value.encode("utf-8")
        ),
        "execution_contract": {
            "response_format": copy.deepcopy(WAVE2_TRANSPORT),
            "temperature": WAVE2_TEMPERATURE,
            "max_tokens": WAVE2_MAX_TOKENS,
            "timeout_seconds": WAVE2_TIMEOUT_SECONDS,
            "probe_plan_version": R3_PREFLIGHT_PROBE_PLAN_VERSION,
            "probe_count": R3_PREFLIGHT_PROBE_COUNT,
            "replicate_count_required": WAVE2_REPLICATES_REQUIRED,
            "replicate_pass_requirement": "6_of_6",
            "minimum_replicate_spacing_seconds": int(WAVE2_MINIMUM_SPACING_SECONDS),
            "judge_system_prompt_sha256": hashlib.sha256(
                JUDGE_SYSTEM_PROMPT.encode("utf-8")
            ).hexdigest(),
            "formal_judge_output_schema_sha256": hashlib.sha256(
                json.dumps(
                    FormalJudgeOutput.model_json_schema(),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        },
        "wave3_permitted": False,
        "semantic_or_generation_outputs_used_in_discovery": False,
        "live_completion_calls_used_in_discovery": False,
        "candidate_list_source": "deterministic_offline_eligibility_ledger_only",
        "formal_stage_c_run_created": False,
        "qualification_outputs_are_formal_stage_c_data": False,
        "scientific_anchors": SCIENTIFIC_ANCHORS,
        "verified_history_anchor_count": len(anchors),
    }
    _atomic_new_json(freeze_target, freeze)
    validate_wave2_candidate_pool_freeze(
        repository_root,
        freeze_path=freeze_target,
        catalog_path=catalog,
        pricing_path=pricing,
        capability_path=capability,
        eligibility_path=eligibility_target,
    )
    return freeze


def validate_wave2_candidate_pool_freeze(
    repository_root: Path,
    *,
    freeze_path: Path | None = None,
    catalog_path: Path | None = None,
    pricing_path: Path | None = None,
    capability_path: Path | None = None,
    eligibility_path: Path | None = None,
) -> Wave2Registry:
    verify_wave2_policy(repository_root)
    paths = _canonical_wave2_paths(repository_root)
    target = freeze_path or paths["freeze"]
    catalog = catalog_path or paths["catalog"]
    pricing = pricing_path or paths["pricing"]
    capability = capability_path or paths["capability"]
    eligibility_target = eligibility_path or paths["eligibility"]
    if not target.is_file():
        raise StageCWave2Error(
            "Wave-2 candidate-pool freeze is missing; candidate execution is blocked"
        )
    freeze = _read_json_object(target, "Wave-2 candidate-pool freeze")
    eligibility = _read_json_object(eligibility_target, "Wave-2 eligibility ledger")
    recomputed = build_wave2_eligibility_ledger(catalog, pricing, capability)
    if eligibility != recomputed:
        raise StageCWave2Error("Wave-2 eligibility ledger is inconsistent with discovery inputs")
    expected_source = {
        "catalog": _sha256(catalog),
        "pricing": _sha256(pricing),
        "capability": _sha256(capability),
        "eligibility": _sha256(eligibility_target),
    }
    if freeze.get("source_sha256") != expected_source:
        raise StageCWave2Error("Wave-2 freeze source hashes are inconsistent")
    fixed = {
        "artifact_type": "wave2_candidate_pool_freeze",
        "policy_identity": WAVE2_POLICY_ID,
        "policy_sha256": WAVE2_POLICY_SHA256,
        "scientific_protocol_identity": WAVE2_PROTOCOL_ID,
        "wave1_exhaustion_sha256": WAVE1_EXHAUSTION_SHA256,
        "provider": WAVE2_PROVIDER,
        "free_only": True,
        "maximum_wave2_candidates": WAVE2_MAX_CANDIDATES,
        "deterministic_sort_rule": WAVE2_SORT_RULE,
        "wave3_permitted": False,
        "semantic_or_generation_outputs_used_in_discovery": False,
        "live_completion_calls_used_in_discovery": False,
        "formal_stage_c_run_created": False,
        "qualification_outputs_are_formal_stage_c_data": False,
    }
    for key, value in fixed.items():
        if freeze.get(key) != value:
            raise StageCWave2Error(f"Wave-2 freeze field {key!r} mismatch")
    _parse_utc(freeze.get("frozen_at"))
    if freeze.get("snapshot_timestamp") != recomputed["snapshot_timestamp"]:
        raise StageCWave2Error("Wave-2 freeze snapshot timestamp mismatch")
    if freeze.get("complete_catalog_model_ids") != recomputed["complete_catalog_model_ids"]:
        raise StageCWave2Error("Wave-2 freeze omits or changes catalog model IDs")
    if freeze.get("complete_eligible_model_ids") != recomputed["complete_eligible_model_ids"]:
        raise StageCWave2Error("Wave-2 freeze changes the complete eligible set")
    expected_exclusions = [
        decision
        for decision in recomputed["decisions"]
        if decision["disposition"] == "excluded"
    ]
    if freeze.get("complete_exclusions") != expected_exclusions:
        raise StageCWave2Error("Wave-2 freeze exclusion ledger mismatch")
    selected_ids = recomputed["complete_eligible_model_ids"][:WAVE2_MAX_CANDIDATES]
    expected_selected = [
        {
            "candidate_number": index,
            "model_id": model_id,
            "thinking_toggle": recomputed["thinking_toggle_by_eligible_model"][model_id],
        }
        for index, model_id in enumerate(selected_ids, start=1)
    ]
    if freeze.get("selected_candidates") != expected_selected:
        raise StageCWave2Error("Wave-2 selected candidates are not the deterministic first four")
    if freeze.get("pool_size") != len(expected_selected) or len(expected_selected) > 4:
        raise StageCWave2Error("Wave-2 pool size is inconsistent")
    expected_contract = {
        "response_format": copy.deepcopy(WAVE2_TRANSPORT),
        "temperature": WAVE2_TEMPERATURE,
        "max_tokens": WAVE2_MAX_TOKENS,
        "timeout_seconds": WAVE2_TIMEOUT_SECONDS,
        "probe_plan_version": R3_PREFLIGHT_PROBE_PLAN_VERSION,
        "probe_count": R3_PREFLIGHT_PROBE_COUNT,
        "replicate_count_required": WAVE2_REPLICATES_REQUIRED,
        "replicate_pass_requirement": "6_of_6",
        "minimum_replicate_spacing_seconds": int(WAVE2_MINIMUM_SPACING_SECONDS),
        "judge_system_prompt_sha256": hashlib.sha256(
            JUDGE_SYSTEM_PROMPT.encode("utf-8")
        ).hexdigest(),
        "formal_judge_output_schema_sha256": hashlib.sha256(
            json.dumps(
                FormalJudgeOutput.model_json_schema(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }
    if freeze.get("execution_contract") != expected_contract:
        raise StageCWave2Error("Wave-2 judge execution contract mismatch")
    if freeze.get("scientific_anchors") != SCIENTIFIC_ANCHORS:
        raise StageCWave2Error("Wave-2 scientific anchors mismatch")
    candidates = tuple(
        Wave2Candidate(
            candidate_number=item["candidate_number"],
            model_id=item["model_id"],
            thinking_toggle=item["thinking_toggle"],
        )
        for item in expected_selected
    )
    return Wave2Registry(freeze_sha256=_sha256(target), candidates=candidates, freeze=freeze)


_ATTEMPT_PATTERN = re.compile(
    r"^candidate-(?P<candidate>0[1-4])-replicate-(?P<replicate>0[1-2])"
    r"(?P<recovery>-recovery-01)?\.json$"
)
_INELIGIBILITY_PATTERN = re.compile(
    r"^candidate-(?P<candidate>0[1-4])-zero-cost-ineligibility\.json$"
)
_ADJUDICATION_PATTERN = re.compile(
    r"^candidate-(?P<candidate>0[1-4])-operationally-unevaluable\.json$"
)


def wave2_manifest_name(candidate_number: int, replicate_number: int, recovery_number: int = 0) -> str:
    if candidate_number not in {1, 2, 3, 4}:
        raise StageCWave2Error("Wave-2 candidate number must be in 1..4")
    if replicate_number not in {1, 2}:
        raise StageCWave2Error("Only Wave-2 replicates 1 and 2 are permitted")
    if recovery_number not in {0, 1}:
        raise StageCWave2Error("Only Wave-2 recovery 01 is permitted")
    suffix = "-recovery-01" if recovery_number else ""
    return f"candidate-{candidate_number:02d}-replicate-{replicate_number:02d}{suffix}.json"


def wave2_attempt_id(candidate_number: int, replicate_number: int, recovery_number: int = 0) -> str:
    suffix = "-recovery-01" if recovery_number else ""
    return (
        f"western-stage-c-wave2-free-v1-candidate-{candidate_number:02d}-"
        f"replicate-{replicate_number:02d}{suffix}"
    )


def wave2_zero_cost_name(candidate_number: int) -> str:
    if candidate_number not in {1, 2, 3, 4}:
        raise StageCWave2Error("Wave-2 candidate number must be in 1..4")
    return f"candidate-{candidate_number:02d}-zero-cost-ineligibility.json"


def wave2_adjudication_name(candidate_number: int) -> str:
    if candidate_number not in {1, 2, 3, 4}:
        raise StageCWave2Error("Wave-2 candidate number must be in 1..4")
    return f"candidate-{candidate_number:02d}-operationally-unevaluable.json"


def _load_registry(
    repository_root: Path,
    freeze_validation: dict[str, Path] | None = None,
) -> Wave2Registry:
    return validate_wave2_candidate_pool_freeze(
        repository_root,
        **(freeze_validation or {}),
    )


def _candidate_from_registry(registry: Wave2Registry, candidate_number: int) -> Wave2Candidate:
    return registry.candidate(candidate_number)


def validate_wave2_attempt_manifest(
    path: Path,
    *,
    registry: Wave2Registry,
) -> dict[str, Any]:
    match = _ATTEMPT_PATTERN.fullmatch(path.name)
    if not match:
        raise StageCWave2Error(f"Unexpected Wave-2 attempt filename: {path.name}")
    data = _read_json_object(path, "Wave-2 attempt manifest")
    candidate_number = int(match.group("candidate"))
    replicate_number = int(match.group("replicate"))
    recovery_number = 1 if match.group("recovery") else 0
    candidate = _candidate_from_registry(registry, candidate_number)
    exact = {
        "policy_identity": WAVE2_POLICY_ID,
        "scientific_protocol_identity": WAVE2_PROTOCOL_ID,
        "source_policy_sha256": WAVE2_POLICY_SHA256,
        "source_pool_freeze_sha256": registry.freeze_sha256,
        "source_wave1_exhaustion_sha256": WAVE1_EXHAUSTION_SHA256,
        "candidate_number": candidate_number,
        "requested_model_id": candidate.model_id,
        "replicate_number": replicate_number,
        "recovery_number": recovery_number,
        "attempt_kind": "infrastructure_recovery" if recovery_number else "ordinary_replicate",
        "attempt_id": wave2_attempt_id(candidate_number, replicate_number, recovery_number),
        "provider": WAVE2_PROVIDER,
        "response_format": WAVE2_TRANSPORT,
        "temperature": WAVE2_TEMPERATURE,
        "max_tokens": WAVE2_MAX_TOKENS,
        "timeout_seconds": WAVE2_TIMEOUT_SECONDS,
        "thinking_toggle": candidate.thinking_toggle,
        "enable_thinking_sent": candidate.expected_provider_enable_thinking,
        "probe_plan_version": R3_PREFLIGHT_PROBE_PLAN_VERSION,
        "probe_count": R3_PREFLIGHT_PROBE_COUNT,
        "raw_response_stored": False,
        "formal_stage_c_run_created": False,
        "outputs_eligible_as_research_data": False,
        "outputs_must_never_enter_formal_analysis": True,
        "cross_wave_pooling": False,
    }
    for key, expected in exact.items():
        if data.get(key) != expected:
            raise StageCWave2Error(f"Wave-2 manifest {path} field {key!r} mismatch")
    confirmation = data.get("zero_cost_confirmation")
    if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True:
        raise StageCWave2Error(f"Wave-2 manifest {path} lacks zero-cost confirmation")
    if confirmation.get("candidate_model_id") != candidate.model_id:
        raise StageCWave2Error(f"Wave-2 manifest {path} zero-cost model mismatch")
    _parse_utc(confirmation.get("confirmed_at"))
    probes = data.get("probes")
    plan = get_synthetic_probe_plan()
    if not isinstance(probes, list) or len(probes) != 6 or len(plan) != 6:
        raise StageCWave2Error(f"Wave-2 manifest {path} must contain six probes")
    for index, (probe, spec) in enumerate(zip(probes, plan)):
        if not isinstance(probe, dict):
            raise StageCWave2Error(f"Wave-2 manifest {path} probe {index} is invalid")
        for raw_key in ("text", "response_text", "raw_response"):
            if raw_key in probe:
                raise StageCWave2Error(f"Wave-2 manifest stores prohibited {raw_key}")
        expected_probe = {
            "probe_number": spec["probe_number"],
            "probe_id": spec["probe_id"],
            "answerability": spec["answerability"],
            "expected_insufficiency_label": spec.get("expected_insufficiency_label"),
            "raw_response_stored": False,
        }
        for key, expected in expected_probe.items():
            if probe.get(key) != expected:
                raise StageCWave2Error(f"Wave-2 manifest {path} probe {index} {key} mismatch")
        failure_class = probe.get("failure_class")
        if failure_class not in {
            None,
            "candidate_readiness_failure",
            "infrastructure_incident",
            "ambiguous_technical_failure",
        }:
            raise StageCWave2Error(f"Wave-2 manifest {path} has invalid failure class")
        if probe.get("json_contract_success") is True:
            if failure_class is not None or probe.get("provider_reported_model") != candidate.model_id:
                raise StageCWave2Error(f"Wave-2 successful probe {index} is inconsistent")
        if probe.get("provider_call_success") is True:
            if probe.get("provider_reported_model") != candidate.model_id:
                if failure_class != "candidate_readiness_failure":
                    raise StageCWave2Error("Wave-2 model mismatch lacks readiness failure")
            response_sha = probe.get("response_sha256")
            if not isinstance(response_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", response_sha):
                raise StageCWave2Error("Wave-2 completed response lacks a valid SHA256")
        elif probe.get("provider_reported_model") is not None or probe.get("response_sha256") is not None:
            raise StageCWave2Error("Wave-2 failed provider call contains response provenance")
        try:
            latency_ms = float(probe.get("latency_ms"))
        except (TypeError, ValueError) as exc:
            raise StageCWave2Error("Wave-2 probe latency is invalid") from exc
        if latency_ms < 0:
            raise StageCWave2Error("Wave-2 probe latency is negative")
    classification = _attempt_classification(probes)
    if data.get("execution_classification") != classification:
        raise StageCWave2Error("Wave-2 manifest classification is inconsistent")
    flags = _classification_flags(classification, recovery_number)
    for key, expected in flags.items():
        if data.get(key) is not expected:
            raise StageCWave2Error(f"Wave-2 manifest flag {key} is inconsistent")
    successful = sum(probe.get("json_contract_success") is True for probe in probes)
    if data.get("successful_probe_count") != successful:
        raise StageCWave2Error("Wave-2 successful probe count is inconsistent")
    if data.get("replicate_passed") is not (classification == "passed"):
        raise StageCWave2Error("Wave-2 replicate pass flag is inconsistent")
    if data.get("json_contract_passed") is not (successful == 6):
        raise StageCWave2Error("Wave-2 JSON contract pass flag is inconsistent")
    expected_no_repair = {
        "coercion": False,
        "synonym_repair": False,
        "semantic_normalization": False,
        "post_hoc_value_repair": False,
    }
    if data.get("no_repair_declaration") != expected_no_repair:
        raise StageCWave2Error("Wave-2 no-repair declaration is inconsistent")
    started = _parse_utc(data.get("started_at"))
    completed = _parse_utc(data.get("completed_at"))
    if completed < started:
        raise StageCWave2Error("Wave-2 completion precedes start")
    spacing = data.get("replicate_spacing_seconds")
    if replicate_number == 2 and recovery_number == 0:
        if not isinstance(spacing, (int, float)) or isinstance(spacing, bool):
            raise StageCWave2Error("Wave-2 Replicate 2 lacks measured spacing")
        if float(spacing) < WAVE2_MINIMUM_SPACING_SECONDS:
            raise StageCWave2Error("Wave-2 Replicate 2 violates minimum spacing")
    elif spacing is not None:
        raise StageCWave2Error("Wave-2 spacing is recorded on an inapplicable attempt")
    return data


def _require_operational_pair(
    ordinary: dict[str, Any],
    recovery: dict[str, Any],
    *,
    candidate_number: int,
    replicate_number: int,
) -> None:
    for label, attempt, expected_recovery in (
        ("ordinary", ordinary, 0),
        ("recovery", recovery, 1),
    ):
        if attempt.get("candidate_number") != candidate_number:
            raise StageCWave2Error(f"{label} candidate mismatch")
        if attempt.get("replicate_number") != replicate_number:
            raise StageCWave2Error(f"{label} replicate mismatch")
        if attempt.get("recovery_number") != expected_recovery:
            raise StageCWave2Error(f"{label} recovery number mismatch")
        if attempt.get("execution_classification") != "infrastructure_incident":
            raise StageCWave2Error(f"{label} is not infrastructure-only")
        if attempt.get("replicate_passed") is not False:
            raise StageCWave2Error(f"{label} independently passed")
        for probe in attempt.get("probes", []):
            if probe.get("json_contract_success") is True:
                if probe.get("failure_class") is not None:
                    raise StageCWave2Error(f"{label} successful probe has failure class")
            elif probe.get("failure_class") != "infrastructure_incident":
                raise StageCWave2Error(f"{label} includes readiness or ambiguous failure")
    fields = (
        "policy_identity",
        "scientific_protocol_identity",
        "source_policy_sha256",
        "source_pool_freeze_sha256",
        "candidate_number",
        "requested_model_id",
        "provider",
        "response_format",
        "temperature",
        "max_tokens",
        "timeout_seconds",
        "thinking_toggle",
        "enable_thinking_sent",
        "probe_plan_version",
        "probe_count",
        "judge_system_prompt_sha256",
        "canonical_formal_judge_output_schema_sha256",
        "no_repair_declaration",
    )
    for field in fields:
        if ordinary.get(field) != recovery.get(field):
            raise StageCWave2Error(f"Recovery changes frozen field {field}")


def _validate_zero_cost_note(
    path: Path,
    *,
    registry: Wave2Registry,
) -> dict[str, Any]:
    match = _INELIGIBILITY_PATTERN.fullmatch(path.name)
    if not match:
        raise StageCWave2Error(f"Unexpected Wave-2 zero-cost filename: {path.name}")
    candidate_number = int(match.group("candidate"))
    candidate = registry.candidate(candidate_number)
    data = _read_json_object(path, "Wave-2 zero-cost ineligibility")
    expected = {
        "policy_identity": WAVE2_POLICY_ID,
        "scientific_protocol_identity": WAVE2_PROTOCOL_ID,
        "source_policy_sha256": WAVE2_POLICY_SHA256,
        "source_pool_freeze_sha256": registry.freeze_sha256,
        "candidate_number": candidate_number,
        "model_id": candidate.model_id,
        "status": "operationally_ineligible_nonzero_cost",
        "provider_calls_made": 0,
        "candidate_quality_interpretation": False,
        "advancement_authorized": True,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            raise StageCWave2Error(f"Wave-2 zero-cost note field {key!r} mismatch")
    _parse_utc(data.get("verified_at"))
    return data


def _validate_adjudication(
    path: Path,
    *,
    registry: Wave2Registry,
    manifests_dir: Path,
) -> dict[str, Any]:
    match = _ADJUDICATION_PATTERN.fullmatch(path.name)
    if not match:
        raise StageCWave2Error(f"Unexpected Wave-2 adjudication filename: {path.name}")
    candidate_number = int(match.group("candidate"))
    candidate = registry.candidate(candidate_number)
    data = _read_json_object(path, "Wave-2 operational adjudication")
    replicate_number = data.get("affected_replicate")
    if replicate_number not in {1, 2}:
        raise StageCWave2Error("Wave-2 adjudication has invalid replicate")
    next_candidate = (
        candidate_number + 1 if candidate_number < len(registry.candidates) else None
    )
    expected = {
        "policy_identity": WAVE2_POLICY_ID,
        "scientific_protocol_identity": WAVE2_PROTOCOL_ID,
        "source_policy_sha256": WAVE2_POLICY_SHA256,
        "source_pool_freeze_sha256": registry.freeze_sha256,
        "candidate_number": candidate_number,
        "candidate_model_id": candidate.model_id,
        "adjudication_state": OPERATIONAL_UNEVALUABILITY_LABEL,
        "candidate_readiness_failure": False,
        "semantic_or_capability_conclusion": False,
        "cross_attempt_pooling": False,
        "additional_recovery_authorized": False,
        "next_frozen_candidate_number": next_candidate,
        "advancement_authorized": True,
        "formal_stage_c_eligibility": False,
        "data_excluded_from_formal_analysis": True,
        "raw_provider_text_stored": False,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            raise StageCWave2Error(f"Wave-2 adjudication field {key!r} mismatch")
    _parse_utc(data.get("adjudicated_at"))
    ordinary_name = wave2_manifest_name(candidate_number, replicate_number, 0)
    recovery_name = wave2_manifest_name(candidate_number, replicate_number, 1)
    ordinary_path = manifests_dir / ordinary_name
    recovery_path = manifests_dir / recovery_name
    anchors = data.get("attempt_anchors")
    expected_anchors = {
        "ordinary": {"filename": ordinary_name, "sha256": _sha256(ordinary_path)},
        "recovery": {"filename": recovery_name, "sha256": _sha256(recovery_path)},
    }
    if anchors != expected_anchors:
        raise StageCWave2Error("Wave-2 adjudication attempt anchors mismatch")
    ordinary = validate_wave2_attempt_manifest(ordinary_path, registry=registry)
    recovery = validate_wave2_attempt_manifest(recovery_path, registry=registry)
    _require_operational_pair(
        ordinary,
        recovery,
        candidate_number=candidate_number,
        replicate_number=replicate_number,
    )
    return data


def inspect_wave2_state(
    repository_root: Path,
    *,
    manifests_dir: Path | None = None,
    adjudications_dir: Path | None = None,
    freeze_validation: dict[str, Path] | None = None,
) -> dict[str, Any]:
    registry = _load_registry(repository_root, freeze_validation)
    paths = _canonical_wave2_paths(repository_root)
    manifest_root = manifests_dir or paths["manifests"]
    adjudication_root = adjudications_dir or paths["adjudications"]
    attempts = {
        candidate.candidate_number: {1: {}, 2: {}} for candidate in registry.candidates
    }
    ineligible: dict[int, dict[str, Any]] = {}
    if manifest_root.is_dir():
        for path in sorted(manifest_root.iterdir()):
            if path.name == ".gitkeep":
                continue
            if not path.is_file() or path.suffix != ".json":
                raise StageCWave2Error(f"Unexpected Wave-2 manifest entry: {path.name}")
            if _ATTEMPT_PATTERN.fullmatch(path.name):
                data = validate_wave2_attempt_manifest(path, registry=registry)
                slot = attempts[data["candidate_number"]][data["replicate_number"]]
                if data["recovery_number"] in slot:
                    raise StageCWave2Error("Duplicate Wave-2 attempt slot")
                slot[data["recovery_number"]] = data
            elif _INELIGIBILITY_PATTERN.fullmatch(path.name):
                data = _validate_zero_cost_note(path, registry=registry)
                number = data["candidate_number"]
                if number in ineligible:
                    raise StageCWave2Error("Duplicate Wave-2 zero-cost note")
                ineligible[number] = data
            else:
                raise StageCWave2Error(f"Unexpected Wave-2 manifest filename: {path.name}")
    for number in attempts:
        if number in ineligible and any(attempts[number][rep] for rep in (1, 2)):
            raise StageCWave2Error("Candidate has both execution and zero-cost ineligibility")
        for replicate in (1, 2):
            slot = attempts[number][replicate]
            if 1 in slot and 0 not in slot:
                raise StageCWave2Error("Wave-2 recovery exists without ordinary attempt")
    adjudications: dict[int, dict[str, Any]] = {}
    if adjudication_root.is_dir():
        for path in sorted(adjudication_root.iterdir()):
            if path.name == ".gitkeep":
                continue
            if not path.is_file() or path.suffix != ".json":
                raise StageCWave2Error(f"Unexpected Wave-2 adjudication entry: {path.name}")
            data = _validate_adjudication(
                path,
                registry=registry,
                manifests_dir=manifest_root,
            )
            number = data["candidate_number"]
            if number in adjudications:
                raise StageCWave2Error("Duplicate Wave-2 operational adjudication")
            adjudications[number] = data
    return {
        "registry": registry,
        "attempts": attempts,
        "zero_cost_ineligible": ineligible,
        "operationally_unevaluable": adjudications,
    }


def _effective_replicate(state: dict[str, Any], candidate_number: int, replicate_number: int) -> dict[str, Any]:
    slot = state["attempts"][candidate_number][replicate_number]
    ordinary = slot.get(0)
    if ordinary is None:
        return {"status": "missing", "manifest": None}
    classification = ordinary["execution_classification"]
    if classification == "passed":
        return {"status": "passed", "manifest": ordinary}
    if classification == "candidate_readiness_failure":
        return {"status": "terminal_candidate_failure", "manifest": ordinary}
    if classification == "ambiguous_technical_failure":
        return {"status": "manual_review", "manifest": ordinary}
    recovery = slot.get(1)
    if recovery is None:
        return {"status": "pending_recovery", "manifest": ordinary}
    recovery_class = recovery["execution_classification"]
    if recovery_class == "passed":
        return {"status": "passed", "manifest": recovery}
    if recovery_class == "candidate_readiness_failure":
        return {"status": "terminal_candidate_failure", "manifest": recovery}
    return {"status": "manual_review", "manifest": recovery}


def _candidate_state(state: dict[str, Any], candidate_number: int) -> str:
    if candidate_number in state["zero_cost_ineligible"]:
        return "terminal_operational_ineligibility"
    rep1 = _effective_replicate(state, candidate_number, 1)
    rep2 = _effective_replicate(state, candidate_number, 2)
    if "terminal_candidate_failure" in {rep1["status"], rep2["status"]}:
        return "terminal_candidate_failure"
    if candidate_number in state["operationally_unevaluable"]:
        return "terminal_operational_unevaluable"
    if rep1["status"] != "passed":
        return rep1["status"]
    if rep2["status"] == "passed":
        return "selected_primary"
    return rep2["status"]


def evaluate_wave2_runner_eligibility(
    repository_root: Path,
    candidate_number: int,
    replicate_number: int,
    recovery_number: int = 0,
    *,
    current_time: datetime | None = None,
    manifests_dir: Path | None = None,
    adjudications_dir: Path | None = None,
    freeze_validation: dict[str, Path] | None = None,
) -> tuple[bool, str, float | None]:
    state = inspect_wave2_state(
        repository_root,
        manifests_dir=manifests_dir,
        adjudications_dir=adjudications_dir,
        freeze_validation=freeze_validation,
    )
    registry: Wave2Registry = state["registry"]
    candidate = registry.candidate(candidate_number)
    del candidate
    if replicate_number not in {1, 2}:
        return False, "Only Wave-2 replicates 1 and 2 are permitted", None
    if recovery_number not in {0, 1}:
        return False, "Only Wave-2 recovery 01 is permitted", None
    for prior in registry.candidates:
        prior_state = _candidate_state(state, prior.candidate_number)
        if prior_state == "selected_primary":
            return False, f"Wave-2 candidate {prior.candidate_number:02d} is already selected", None
        if prior.candidate_number >= candidate_number:
            break
        if prior_state not in {
            "terminal_candidate_failure",
            "terminal_operational_ineligibility",
            "terminal_operational_unevaluable",
        }:
            return False, (
                f"Wave-2 candidate {candidate_number:02d} is blocked because prior candidate "
                f"{prior.candidate_number:02d} is {prior_state}"
            ), None
    if candidate_number in state["zero_cost_ineligible"]:
        return False, "Candidate is terminally ineligible under the zero-cost rule", None
    if candidate_number in state["operationally_unevaluable"]:
        return False, "Candidate is terminally operationally unevaluable", None
    slot = state["attempts"][candidate_number][replicate_number]
    if recovery_number == 1:
        ordinary = slot.get(0)
        if ordinary is None:
            return False, "Recovery is blocked because ordinary attempt is missing", None
        if ordinary["execution_classification"] != "infrastructure_incident":
            return False, "Recovery requires an infrastructure-only ordinary attempt", None
        if 1 in slot:
            return False, "Recovery 01 exists; recovery-02 is prohibited", None
        return True, "Wave-2 recovery 01 is eligible", None
    if 0 in slot:
        return False, "Ordinary attempt already exists; overwrite is prohibited", None
    if replicate_number == 1:
        return True, "Wave-2 Replicate 1 is eligible", None
    rep1 = _effective_replicate(state, candidate_number, 1)
    if rep1["status"] != "passed":
        return False, f"Replicate 2 is blocked because Replicate 1 is {rep1['status']}", None
    now = current_time or datetime.now(timezone.utc)
    elapsed = (now - _parse_utc(rep1["manifest"]["completed_at"])).total_seconds()
    if elapsed < WAVE2_MINIMUM_SPACING_SECONDS:
        return False, (
            f"Replicate 2 spacing is {elapsed:.1f}s; {WAVE2_MINIMUM_SPACING_SECONDS:.0f}s required"
        ), elapsed
    return True, "Wave-2 Replicate 2 is eligible", elapsed


def _resolve_runtime_dirs(
    repository_root: Path,
    manifests_dir: Path | None,
    adjudications_dir: Path | None,
) -> tuple[Path, Path]:
    paths = _canonical_wave2_paths(repository_root)
    manifest_root = manifests_dir or paths["manifests"]
    adjudication_root = adjudications_dir or paths["adjudications"]
    manifest_root.mkdir(parents=True, exist_ok=True)
    adjudication_root.mkdir(parents=True, exist_ok=True)
    return manifest_root, adjudication_root


def _validate_runtime_target(
    repository_root: Path,
    target: Path,
    expected_parent: Path,
) -> Path:
    resolved = target.resolve()
    formal_root = (
        repository_root
        / "research/experiments/western_formal_v0_1/stage_c_execution_v0_1_5_wave2_jrv1"
    ).resolve()
    if resolved == formal_root or formal_root in resolved.parents:
        raise StageCWave2Error("Qualification output must never enter formal Stage C")
    if resolved.parent != expected_parent.resolve():
        raise StageCWave2Error("Wave-2 output must use its canonical artifact directory")
    _ensure_new_path(resolved, "Wave-2 output")
    return resolved


def record_wave2_zero_cost_ineligibility(
    repository_root: Path,
    *,
    candidate_number: int,
    verified_at: datetime | None = None,
    manifests_dir: Path | None = None,
    adjudications_dir: Path | None = None,
    freeze_validation: dict[str, Path] | None = None,
) -> dict[str, Any]:
    manifest_root, adjudication_root = _resolve_runtime_dirs(
        repository_root, manifests_dir, adjudications_dir
    )
    allowed, reason, _ = evaluate_wave2_runner_eligibility(
        repository_root,
        candidate_number,
        1,
        manifests_dir=manifest_root,
        adjudications_dir=adjudication_root,
        freeze_validation=freeze_validation,
        current_time=verified_at,
    )
    if not allowed:
        raise StageCWave2Error(f"Cannot record Wave-2 zero-cost ineligibility: {reason}")
    registry = _load_registry(repository_root, freeze_validation)
    candidate = registry.candidate(candidate_number)
    target = _validate_runtime_target(
        repository_root,
        manifest_root / wave2_zero_cost_name(candidate_number),
        manifest_root,
    )
    timestamp = verified_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise StageCWave2Error("Zero-cost verification timestamp must be timezone-aware")
    note = {
        "policy_identity": WAVE2_POLICY_ID,
        "scientific_protocol_identity": WAVE2_PROTOCOL_ID,
        "source_policy_sha256": WAVE2_POLICY_SHA256,
        "source_pool_freeze_sha256": registry.freeze_sha256,
        "candidate_number": candidate_number,
        "model_id": candidate.model_id,
        "status": "operationally_ineligible_nonzero_cost",
        "verified_at": timestamp.astimezone(timezone.utc).isoformat(),
        "provider_calls_made": 0,
        "candidate_quality_interpretation": False,
        "advancement_authorized": True,
        "reason": "operator_verified_nonzero_input_or_output_price_before_first_live_call",
    }
    _atomic_new_json(target, note)
    return _validate_zero_cost_note(target, registry=registry)


def create_wave2_operational_adjudication(
    repository_root: Path,
    *,
    candidate_number: int,
    replicate_number: int,
    adjudicated_at: datetime | None = None,
    manifests_dir: Path | None = None,
    adjudications_dir: Path | None = None,
    freeze_validation: dict[str, Path] | None = None,
) -> dict[str, Any]:
    manifest_root, adjudication_root = _resolve_runtime_dirs(
        repository_root, manifests_dir, adjudications_dir
    )
    state = inspect_wave2_state(
        repository_root,
        manifests_dir=manifest_root,
        adjudications_dir=adjudication_root,
        freeze_validation=freeze_validation,
    )
    registry: Wave2Registry = state["registry"]
    candidate = registry.candidate(candidate_number)
    if candidate_number in state["operationally_unevaluable"]:
        raise FileExistsError("Wave-2 operational adjudication already exists")
    if replicate_number not in {1, 2}:
        raise StageCWave2Error("Wave-2 adjudication requires replicate 1 or 2")
    ordinary_name = wave2_manifest_name(candidate_number, replicate_number, 0)
    recovery_name = wave2_manifest_name(candidate_number, replicate_number, 1)
    ordinary_path = manifest_root / ordinary_name
    recovery_path = manifest_root / recovery_name
    ordinary = validate_wave2_attempt_manifest(ordinary_path, registry=registry)
    recovery = validate_wave2_attempt_manifest(recovery_path, registry=registry)
    _require_operational_pair(
        ordinary,
        recovery,
        candidate_number=candidate_number,
        replicate_number=replicate_number,
    )
    if replicate_number == 2 and _effective_replicate(state, candidate_number, 1)[
        "status"
    ] != "passed":
        raise StageCWave2Error("Replicate-2 adjudication requires passing Replicate 1")
    target = _validate_runtime_target(
        repository_root,
        adjudication_root / wave2_adjudication_name(candidate_number),
        adjudication_root,
    )
    timestamp = adjudicated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise StageCWave2Error("Wave-2 adjudication timestamp must be timezone-aware")
    next_candidate = (
        candidate_number + 1 if candidate_number < len(registry.candidates) else None
    )
    adjudication = {
        "policy_identity": WAVE2_POLICY_ID,
        "scientific_protocol_identity": WAVE2_PROTOCOL_ID,
        "source_policy_sha256": WAVE2_POLICY_SHA256,
        "source_pool_freeze_sha256": registry.freeze_sha256,
        "adjudicated_at": timestamp.astimezone(timezone.utc).isoformat(),
        "candidate_number": candidate_number,
        "candidate_model_id": candidate.model_id,
        "affected_replicate": replicate_number,
        "adjudication_state": OPERATIONAL_UNEVALUABILITY_LABEL,
        "attempt_anchors": {
            "ordinary": {"filename": ordinary_name, "sha256": _sha256(ordinary_path)},
            "recovery": {"filename": recovery_name, "sha256": _sha256(recovery_path)},
        },
        "candidate_readiness_failure": False,
        "semantic_or_capability_conclusion": False,
        "cross_attempt_pooling": False,
        "additional_recovery_authorized": False,
        "next_frozen_candidate_number": next_candidate,
        "advancement_authorized": True,
        "formal_stage_c_eligibility": False,
        "data_excluded_from_formal_analysis": True,
        "raw_provider_text_stored": False,
    }
    _atomic_new_json(target, adjudication)
    return _validate_adjudication(
        target,
        registry=registry,
        manifests_dir=manifest_root,
    )


def create_wave2_exhaustion_artifact(
    repository_root: Path,
    *,
    created_at: datetime | None = None,
    manifests_dir: Path | None = None,
    adjudications_dir: Path | None = None,
    exhaustion_path: Path | None = None,
    freeze_validation: dict[str, Path] | None = None,
) -> dict[str, Any]:
    state = inspect_wave2_state(
        repository_root,
        manifests_dir=manifests_dir,
        adjudications_dir=adjudications_dir,
        freeze_validation=freeze_validation,
    )
    registry: Wave2Registry = state["registry"]
    statuses = [
        {
            "candidate_number": candidate.candidate_number,
            "model_id": candidate.model_id,
            "terminal_status": _candidate_state(state, candidate.candidate_number),
        }
        for candidate in registry.candidates
    ]
    if any(item["terminal_status"] == "selected_primary" for item in statuses):
        raise StageCWave2Error("Cannot exhaust Wave 2 after Primary Judge selection")
    terminal = {
        "terminal_candidate_failure",
        "terminal_operational_ineligibility",
        "terminal_operational_unevaluable",
    }
    if statuses and any(item["terminal_status"] not in terminal for item in statuses):
        raise StageCWave2Error("Wave-2 pool is not fully terminal")
    paths = _canonical_wave2_paths(repository_root)
    target = exhaustion_path or paths["exhaustion"]
    _ensure_new_path(target, "Wave-2 exhaustion artifact")
    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise StageCWave2Error("Wave-2 exhaustion timestamp must be timezone-aware")
    artifact = {
        "artifact_type": "wave2_final_candidate_pool_exhaustion",
        "policy_identity": WAVE2_POLICY_ID,
        "scientific_protocol_identity": WAVE2_PROTOCOL_ID,
        "source_policy_sha256": WAVE2_POLICY_SHA256,
        "source_pool_freeze_sha256": registry.freeze_sha256,
        "created_at": timestamp.astimezone(timezone.utc).isoformat(),
        "pool_size": len(registry.candidates),
        "candidate_terminal_states": statuses,
        "primary_judge_selected": False,
        "automated_semantic_stage_c_terminated": True,
        "scientific_conclusion": (
            "automated semantic Stage C evaluation was not completed because no candidate "
            "from the prospectively governed judge-selection procedures achieved the required "
            "qualification standard"
        ),
        "wave3_permitted": False,
        "automatic_paid_fallback_permitted": False,
        "judge_interface_redesign_permitted_within_study": False,
        "formal_stage_c_run_created": False,
        "stage_a_and_stage_b_remain_valid": True,
        "w_rq2_semantic_estimates_available": False,
        "w_rq3_semantic_estimates_available": False,
    }
    _atomic_new_json(target, artifact)
    return artifact


def assert_wave2_formal_stage_c_ready(
    repository_root: Path,
    *,
    manifests_dir: Path | None = None,
    adjudications_dir: Path | None = None,
    freeze_validation: dict[str, Path] | None = None,
) -> Wave2Candidate:
    state = inspect_wave2_state(
        repository_root,
        manifests_dir=manifests_dir,
        adjudications_dir=adjudications_dir,
        freeze_validation=freeze_validation,
    )
    selected = [
        candidate
        for candidate in state["registry"].candidates
        if _candidate_state(state, candidate.candidate_number) == "selected_primary"
    ]
    if len(selected) != 1:
        raise StageCWave2Error(
            "Formal Stage C is blocked until exactly one Wave-2 candidate passes two 6/6 replicates"
        )
    return selected[0]


def _validate_wave2_provider(provider: Any, candidate: Wave2Candidate) -> None:
    checks = {
        "provider": (getattr(provider, "name", None), WAVE2_PROVIDER),
        "model": (getattr(provider, "model", None), candidate.model_id),
        "timeout": (float(getattr(provider, "timeout", -1)), WAVE2_TIMEOUT_SECONDS),
    }
    for label, (actual, expected) in checks.items():
        if actual != expected:
            raise StageCWave2Error(
                f"Wave-2 provider {label} mismatch: expected {expected!r}, got {actual!r}"
            )
    if int(getattr(provider, "max_tokens", -1)) < WAVE2_MAX_TOKENS:
        raise StageCWave2Error("Wave-2 provider max_tokens is below 1200")
    if getattr(provider, "supports_response_format", False) is not True:
        raise StageCWave2Error("Wave-2 provider lacks response_format support")
    if getattr(provider, "supports_json_object_response_format", False) is not True:
        raise StageCWave2Error("Wave-2 provider lacks JSON-object support")
    if getattr(provider, "enable_thinking", None) is not candidate.expected_provider_enable_thinking:
        raise StageCWave2Error("Wave-2 provider thinking setting mismatches frozen registry")


async def run_wave2_candidate_preflight(
    repository_root: Path,
    *,
    candidate_number: int,
    replicate_number: int,
    recovery_number: int = 0,
    zero_cost_confirmed: bool,
    provider: Any | None = None,
    manifests_dir: Path | None = None,
    adjudications_dir: Path | None = None,
    freeze_validation: dict[str, Path] | None = None,
    current_time: datetime | None = None,
) -> dict[str, Any]:
    if zero_cost_confirmed is not True:
        raise StageCWave2Error("Wave-2 execution requires immediate manual zero-cost confirmation")
    manifest_root, adjudication_root = _resolve_runtime_dirs(
        repository_root, manifests_dir, adjudications_dir
    )
    registry = _load_registry(repository_root, freeze_validation)
    candidate = registry.candidate(candidate_number)
    allowed, reason, elapsed_spacing = evaluate_wave2_runner_eligibility(
        repository_root,
        candidate_number,
        replicate_number,
        recovery_number,
        current_time=current_time,
        manifests_dir=manifest_root,
        adjudications_dir=adjudication_root,
        freeze_validation=freeze_validation,
    )
    if not allowed:
        raise StageCWave2Error(f"Wave-2 preflight rejected by state machine: {reason}")
    target = _validate_runtime_target(
        repository_root,
        manifest_root / wave2_manifest_name(candidate_number, replicate_number, recovery_number),
        manifest_root,
    )
    active = provider or build_llm_provider(
        candidate.model_id,
        timeout_override=WAVE2_TIMEOUT_SECONDS,
        thinking_behavior=candidate.thinking_toggle,
    )
    _validate_wave2_provider(active, candidate)
    plan = get_synthetic_probe_plan()
    expected_probe_ids = [
        "synthetic-supported-probe-01",
        "synthetic-supported-probe-02",
        "synthetic-partially-supported-probe-01",
        "synthetic-partially-supported-probe-02",
        "synthetic-insufficient-probe-01",
        "synthetic-insufficient-probe-02",
    ]
    if [probe["probe_id"] for probe in plan] != expected_probe_ids:
        raise StageCWave2Error("Frozen Wave-2 six-probe plan changed")

    started_at = _utc_now()
    probes: list[dict[str, Any]] = []
    for spec in plan:
        retrieval = spec["retrieval"]
        prompt = build_stage_c_r3_json_mode_prompt(
            question=spec["question"],
            answer=spec["answer"],
            retrieved_evidence=spec["evidence"],
            expected_evidence_points=retrieval["expected_evidence_points"],
            answerability=retrieval["answerability"],
        )
        started = perf_counter()
        result: Any | None = None
        error_type: str | None = None
        error_message: str | None = None
        failure_class: str | None = None
        normalization: str | None = None
        json_contract_success = False
        http_status: int | None = None
        try:
            result = await active.generate(
                system=JUDGE_SYSTEM_PROMPT,
                prompt=prompt,
                temperature=WAVE2_TEMPERATURE,
                max_tokens=WAVE2_MAX_TOKENS,
                response_format=copy.deepcopy(WAVE2_TRANSPORT),
            )
            reported_model = getattr(result, "model", None)
            if reported_model != candidate.model_id:
                failure_class = "candidate_readiness_failure"
                error_type = "model_identity_mismatch"
                error_message = (
                    f"Provider model mismatch: expected {candidate.model_id!r}, "
                    f"got {reported_model!r}"
                )
            elif getattr(result, "finish_reason", None) not in {None, "stop"}:
                failure_class = "candidate_readiness_failure"
                error_type = "unsupported_finish_reason"
                error_message = f"Unsupported finish_reason={getattr(result, 'finish_reason', None)!r}"
            else:
                _, normalization = validate_stage_c_r3_json_mode_probe_output(
                    result.text,
                    retrieval=retrieval,
                    expected_insufficiency_label=spec.get("expected_insufficiency_label"),
                    require_all_enums_exercised=spec.get("require_all_enums_exercised", False),
                )
                json_contract_success = True
        except ProviderUnavailable as exc:
            failure_class, error_type = classify_provider_exception(exc)
            error_message = str(exc)
            http_status = getattr(exc, "http_status", None)
        except (StageCR3PreflightError, json.JSONDecodeError) as exc:
            failure_class = "candidate_readiness_failure"
            error_type = "schema_or_contract_failure"
            error_message = str(exc)
        except TypeError as exc:
            failure_class = "candidate_readiness_failure"
            error_type = "required_parameter_rejected"
            error_message = str(exc)
        latency_ms = round((perf_counter() - started) * 1000, 3)
        if result is not None and latency_ms > WAVE2_TIMEOUT_SECONDS * 1000:
            failure_class = "candidate_readiness_failure"
            error_type = "completed_response_exceeds_timeout"
            error_message = f"Completed response latency {latency_ms}ms exceeds 120000ms"
        response_sha = (
            hashlib.sha256(result.text.encode("utf-8")).hexdigest()
            if result is not None and isinstance(getattr(result, "text", None), str)
            else None
        )
        probes.append(
            {
                "probe_number": spec["probe_number"],
                "probe_id": spec["probe_id"],
                "answerability": spec["answerability"],
                "expected_evidence_point_count": len(retrieval["expected_evidence_points"]),
                "expected_insufficiency_label": spec.get("expected_insufficiency_label"),
                "provider_call_success": result is not None,
                "provider_reported_model": getattr(result, "model", None),
                "finish_reason": getattr(result, "finish_reason", None),
                "json_contract_success": json_contract_success and failure_class is None,
                "formal_timeout_compatible": (
                    result is not None and latency_ms <= WAVE2_TIMEOUT_SECONDS * 1000
                ),
                "failure_class": failure_class,
                "error_type": error_type,
                "http_status": http_status,
                "error_message": error_message,
                "normalization": normalization,
                "latency_ms": latency_ms,
                "response_sha256": response_sha,
                "raw_response_stored": False,
                "synthetic_non_formal": True,
            }
        )

    completed_at = _utc_now()
    classification = _attempt_classification(probes)
    flags = _classification_flags(classification, recovery_number)
    passed = classification == "passed"
    successful = sum(probe["json_contract_success"] is True for probe in probes)
    per_answerability: dict[str, dict[str, Any]] = {}
    for answerability in ("supported", "partially_supported", "insufficient"):
        subset = [probe for probe in probes if probe["answerability"] == answerability]
        successes = sum(probe["json_contract_success"] is True for probe in subset)
        per_answerability[answerability] = {
            "attempted": len(subset),
            "json_contract_successful": successes,
            "json_contract_passed": len(subset) == 2 and successes == 2,
            "formal_timeout_compatible": all(
                probe["formal_timeout_compatible"] is True for probe in subset
            ),
            "timeouts": sum(
                probe["error_type"] in {"timeout", "http_408"} for probe in subset
            ),
        }
    if passed and replicate_number == 2:
        qualification = "qualified_and_selected_primary_judge"
    elif passed:
        qualification = "effective_replicate_01_passed_pending_replicate_02"
    elif flags["candidate_terminally_failed"]:
        qualification = f"terminally_failed_on_replicate_{replicate_number:02d}"
    elif flags["infrastructure_recovery_authorized"]:
        qualification = "candidate_unresolved_recovery_01_authorized"
    else:
        qualification = "candidate_unresolved_manual_methodology_review_required"
    latencies = [float(probe["latency_ms"]) for probe in probes]
    manifest = {
        "policy_identity": WAVE2_POLICY_ID,
        "scientific_protocol_identity": WAVE2_PROTOCOL_ID,
        "source_policy_sha256": WAVE2_POLICY_SHA256,
        "source_pool_freeze_sha256": registry.freeze_sha256,
        "source_wave1_exhaustion_sha256": WAVE1_EXHAUSTION_SHA256,
        "candidate_number": candidate_number,
        "requested_model_id": candidate.model_id,
        "replicate_number": replicate_number,
        "recovery_number": recovery_number,
        "attempt_kind": "infrastructure_recovery" if recovery_number else "ordinary_replicate",
        "attempt_id": wave2_attempt_id(candidate_number, replicate_number, recovery_number),
        "status": "passed" if passed else "failed",
        "execution_classification": classification,
        "replicate_passed": passed,
        "candidate_qualification_status": qualification,
        **flags,
        "started_at": started_at,
        "completed_at": completed_at,
        "replicate_spacing_seconds": elapsed_spacing,
        "zero_cost_confirmation": {
            "confirmed": True,
            "confirmed_at": started_at,
            "candidate_model_id": candidate.model_id,
            "permanent_price_guarantee": False,
        },
        "provider": WAVE2_PROVIDER,
        "response_format": copy.deepcopy(WAVE2_TRANSPORT),
        "temperature": WAVE2_TEMPERATURE,
        "max_tokens": WAVE2_MAX_TOKENS,
        "timeout_seconds": WAVE2_TIMEOUT_SECONDS,
        "thinking_toggle": candidate.thinking_toggle,
        "enable_thinking_sent": candidate.expected_provider_enable_thinking,
        "probe_plan_version": R3_PREFLIGHT_PROBE_PLAN_VERSION,
        "probe_count": R3_PREFLIGHT_PROBE_COUNT,
        "successful_probe_count": successful,
        "json_contract_passed": successful == 6,
        "formal_timeout_compatible": all(
            probe["formal_timeout_compatible"] is True for probe in probes
        ),
        "timeout_occurrences": sum(
            probe["error_type"] in {"timeout", "http_408"} for probe in probes
        ),
        "per_answerability_summary": per_answerability,
        "latency_metrics": {
            "mean_latency_ms": statistics.fmean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "max_latency_ms": max(latencies),
        },
        "scientific_anchors": SCIENTIFIC_ANCHORS,
        "judge_system_prompt_sha256": hashlib.sha256(
            JUDGE_SYSTEM_PROMPT.encode("utf-8")
        ).hexdigest(),
        "canonical_formal_judge_output_schema_sha256": hashlib.sha256(
            json.dumps(
                FormalJudgeOutput.model_json_schema(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "no_repair_declaration": {
            "coercion": False,
            "synonym_repair": False,
            "semantic_normalization": False,
            "post_hoc_value_repair": False,
        },
        "raw_response_stored": False,
        "formal_stage_c_run_created": False,
        "outputs_eligible_as_research_data": False,
        "outputs_must_never_enter_formal_analysis": True,
        "cross_wave_pooling": False,
        "probes": probes,
    }
    _atomic_new_json(target, manifest)
    return validate_wave2_attempt_manifest(target, registry=registry)
