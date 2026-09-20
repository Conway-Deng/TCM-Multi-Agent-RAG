from __future__ import annotations

import asyncio
from datetime import timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from providers.base import GenerationResult
from providers.openai_compatible import ProviderUnavailable, _chat_payload
from western import formal_eval as formal
from western import stage_c_wave2_free as wave2
from western.stage_c_preflight import get_synthetic_probe_plan


ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _model(model_id: str, **overrides: Any) -> dict[str, Any]:
    value = {
        "model_id": model_id,
        "input_price": "0.000000",
        "output_price": "0.000000",
        "model_type": "chat_completions",
        "openai_chat_completions_compatible": True,
        "json_object_compatible": True,
        "status": "available",
        "account_accessible": True,
        "region_accessible": True,
        "thinking_toggle": "omit",
        "requires_candidate_specific_interface_changes": False,
        "aliases": [],
    }
    value.update(overrides)
    return value


def _discovery(tmp_path: Path, models: list[dict[str, Any]]) -> dict[str, Path]:
    timestamp = "2026-09-20T14:00:00+00:00"
    catalog = {
        "artifact_type": "provider_model_catalog",
        "provider": "siliconflow",
        "snapshot_timestamp": timestamp,
        "source_endpoint": "/v1/models",
        "semantic_or_generation_outputs_used": False,
        "live_completion_calls_used": False,
        "models": [{"model_id": item["model_id"]} for item in models],
    }
    pricing = {
        "artifact_type": "pricing_ledger",
        "provider": "siliconflow",
        "snapshot_timestamp": timestamp,
        "evidence_source": "operator_manual_provider_pricing_snapshot",
        "semantic_or_generation_outputs_used": False,
        "live_completion_calls_used": False,
        "prices": [
            {
                "model_id": item["model_id"],
                "input_price": item["input_price"],
                "output_price": item["output_price"],
                "evidence_reference": f"pricing:{item['model_id']}",
            }
            for item in models
        ],
    }
    capability = {
        "artifact_type": "capability_ledger",
        "provider": "siliconflow",
        "snapshot_timestamp": timestamp,
        "evidence_source": "provider_documentation_and_non_inference_metadata",
        "non_semantic_evidence_only": True,
        "semantic_or_generation_outputs_used": False,
        "live_completion_calls_used": False,
        "capabilities": [
            {
                "model_id": item["model_id"],
                "model_type": item["model_type"],
                "openai_chat_completions_compatible": item[
                    "openai_chat_completions_compatible"
                ],
                "json_object_compatible": item["json_object_compatible"],
                "status": item["status"],
                "account_accessible": item["account_accessible"],
                "region_accessible": item["region_accessible"],
                "thinking_toggle": item["thinking_toggle"],
                "requires_candidate_specific_interface_changes": item[
                    "requires_candidate_specific_interface_changes"
                ],
                "aliases": item["aliases"],
                "evidence_reference": f"capability:{item['model_id']}",
            }
            for item in models
        ],
    }
    return {
        "catalog_path": _write(tmp_path / "provider-model-catalog.json", catalog),
        "pricing_path": _write(tmp_path / "pricing-ledger.json", pricing),
        "capability_path": _write(tmp_path / "capability-ledger.json", capability),
        "eligibility_path": tmp_path / "eligibility-ledger.json",
        "freeze_path": tmp_path / "candidate-pool-freeze.json",
    }


def _freeze(tmp_path: Path, models: list[dict[str, Any]]) -> dict[str, Path]:
    paths = _discovery(tmp_path, models)
    wave2.freeze_wave2_candidate_pool(
        ROOT,
        **paths,
        frozen_at=wave2._parse_utc("2026-09-20T14:05:00+00:00"),
    )
    return paths


def _payload(probe: dict[str, Any]) -> dict[str, Any]:
    answerability = probe["answerability"]
    count = len(probe["retrieval"]["expected_evidence_points"])
    if answerability == "partially_supported" and probe.get("require_all_enums_exercised"):
        claim_labels = ["supported", "partially_supported", "unsupported", "not_checkable"]
        evidence_labels = ["covered", "partially_covered", "not_covered", "contradicted"]
    else:
        claim_labels = ["supported"] * max(1, count)
        evidence_labels = ["covered"] * count
    scope = (True, True, False) if answerability == "partially_supported" else (None, None, None)
    insufficiency = (
        probe.get("expected_insufficiency_label", "appropriate_abstention")
        if answerability == "insufficient"
        else "not_applicable"
    )
    return {
        "claim_labels": [
            {
                "claim_id": f"c{index}",
                "claim": f"Synthetic claim {index}",
                "label": label,
                "justification": "Wave-2 offline fixture.",
            }
            for index, label in enumerate(claim_labels)
        ],
        "evidence_point_labels": [
            {
                "point_index": index,
                "label": label,
                "justification": "Wave-2 offline fixture.",
            }
            for index, label in enumerate(evidence_labels)
        ],
        "insufficiency_label": insufficiency,
        "stays_within_supported_evidence": scope[0],
        "preserves_uncertainty": scope[1],
        "invented_unsupported_information": scope[2],
        "diagnosis_like_personalized_statement": False,
        "individualized_dosing": False,
        "prescription_like_recommendation": False,
        "research_or_educational_limitation_preserved": True,
    }


def _result(
    probe: dict[str, Any],
    candidate: wave2.Wave2Candidate,
    *,
    payload: dict[str, Any] | None = None,
    reported_model: str | None = None,
) -> GenerationResult:
    return GenerationResult(
        text=json.dumps(payload if payload is not None else _payload(probe)),
        provider=wave2.WAVE2_PROVIDER,
        model=reported_model if reported_model is not None else candidate.model_id,
        finish_reason="stop",
    )


class MockProvider:
    name = wave2.WAVE2_PROVIDER
    timeout = wave2.WAVE2_TIMEOUT_SECONDS
    max_tokens = wave2.WAVE2_MAX_TOKENS
    supports_response_format = True
    supports_json_object_response_format = True

    def __init__(
        self,
        candidate: wave2.Wave2Candidate,
        results: list[GenerationResult | Exception],
    ) -> None:
        self.model = candidate.model_id
        self.enable_thinking = candidate.expected_provider_enable_thinking
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> GenerationResult:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _provider(
    registry: wave2.Wave2Registry,
    candidate_number: int,
    results: list[GenerationResult | Exception] | None = None,
) -> MockProvider:
    candidate = registry.candidate(candidate_number)
    successes = [_result(probe, candidate) for probe in get_synthetic_probe_plan()]
    return MockProvider(candidate, list(results) if results is not None else successes)


def _runtime(tmp_path: Path) -> tuple[Path, Path]:
    manifests = tmp_path / "runtime" / "manifests"
    adjudications = tmp_path / "runtime" / "adjudications"
    manifests.mkdir(parents=True)
    adjudications.mkdir(parents=True)
    return manifests, adjudications


def _run(
    paths: dict[str, Path],
    manifests: Path,
    adjudications: Path,
    *,
    candidate_number: int = 1,
    replicate_number: int = 1,
    recovery_number: int = 0,
    provider: MockProvider | None = None,
    current_time: Any | None = None,
) -> dict[str, Any]:
    registry = wave2.validate_wave2_candidate_pool_freeze(ROOT, **paths)
    return asyncio.run(
        wave2.run_wave2_candidate_preflight(
            ROOT,
            candidate_number=candidate_number,
            replicate_number=replicate_number,
            recovery_number=recovery_number,
            zero_cost_confirmed=True,
            provider=provider or _provider(registry, candidate_number),
            manifests_dir=manifests,
            adjudications_dir=adjudications,
            freeze_validation=paths,
            current_time=current_time,
        )
    )


def test_policy_history_and_scientific_invariants_are_pinned() -> None:
    hashes = wave2.verify_wave2_policy(ROOT)
    assert hashes["wave2_policy_sha256"] == wave2.WAVE2_POLICY_SHA256
    assert hashes["wave1_exhaustion_sha256"] == wave2.WAVE1_EXHAUSTION_SHA256
    assert wave2.WAVE2_PROTOCOL_ID == "western_formal_v0.1.5"
    assert wave2.WAVE2_PROVIDER == "siliconflow"
    assert wave2.WAVE2_FREE_ONLY is True
    assert wave2.WAVE2_MAX_CANDIDATES == 4
    assert wave2.WAVE3_PERMITTED is False
    assert formal.GENERATOR_MODEL == "Qwen/Qwen3-8B"


def test_canonical_pool_is_not_yet_frozen_and_execution_fails_before_provider() -> None:
    assert not (ROOT / wave2.WAVE2_FREEZE_RELATIVE_PATH).exists()
    candidate = wave2.Wave2Candidate(1, "fixture/model", "omit")
    provider = MockProvider(candidate, [])
    with pytest.raises(wave2.StageCWave2Error, match="freeze is missing"):
        asyncio.run(
            wave2.run_wave2_candidate_preflight(
                ROOT,
                candidate_number=1,
                replicate_number=1,
                zero_cost_confirmed=True,
                provider=provider,
            )
        )
    assert provider.calls == []


def test_duplicate_catalog_ids_and_incomplete_ledgers_fail_closed(tmp_path: Path) -> None:
    models = [_model("Model/A"), _model("Model/A")]
    paths = _discovery(tmp_path / "duplicate", models)
    with pytest.raises(wave2.StageCWave2Error, match="duplicate model_id"):
        wave2.build_wave2_eligibility_ledger(
            paths["catalog_path"], paths["pricing_path"], paths["capability_path"]
        )
    paths = _discovery(tmp_path / "missing", [_model("Model/A"), _model("Model/B")])
    pricing = json.loads(paths["pricing_path"].read_text(encoding="utf-8"))
    pricing["prices"].pop()
    _write(paths["pricing_path"], pricing)
    with pytest.raises(wave2.StageCWave2Error, match="Pricing ledger must dispose"):
        wave2.build_wave2_eligibility_ledger(
            paths["catalog_path"], paths["pricing_path"], paths["capability_path"]
        )


def test_all_required_exclusion_classes_are_explicit(tmp_path: Path) -> None:
    models = [
        _model("Eligible/One"),
        _model("Unknown/Input", input_price=None),
        _model("Paid/Output", output_price="1.000000"),
        _model(wave2.WAVE2_GENERATOR_MODEL),
        _model("XingChenAGI/Xing4.0-29B"),
        _model("Alias/Old", aliases=["THUDM/GLM-4-9B-0414"]),
        _model("Type/Embedding", model_type="embedding"),
        _model("JSON/Unknown", json_object_compatible=None),
        _model("Thinking/Unknown", thinking_toggle=None),
        _model("Retired/Model", status="retired"),
        _model("Blocked/Region", region_accessible=False),
        _model("Needs/Repair", requires_candidate_specific_interface_changes=True),
    ]
    paths = _discovery(tmp_path, models)
    ledger = wave2.build_wave2_eligibility_ledger(
        paths["catalog_path"], paths["pricing_path"], paths["capability_path"]
    )
    assert ledger["complete_eligible_model_ids"] == ["Eligible/One"]
    decisions = {item["model_id"]: item for item in ledger["decisions"]}
    assert "unknown_input_price" in decisions["Unknown/Input"]["exclusion_reasons"]
    assert "nonzero_output_price" in decisions["Paid/Output"]["exclusion_reasons"]
    assert "generator_model_excluded" in decisions[wave2.WAVE2_GENERATOR_MODEL]["exclusion_reasons"]
    assert "previously_tested_exact_model" in decisions["XingChenAGI/Xing4.0-29B"]["exclusion_reasons"]
    assert "documented_alias_of_previously_tested_model" in decisions["Alias/Old"]["exclusion_reasons"]
    assert "unsupported_or_non_chat_model_type" in decisions["Type/Embedding"]["exclusion_reasons"]
    assert "json_object_compatibility_not_documented" in decisions["JSON/Unknown"]["exclusion_reasons"]
    assert "thinking_behavior_unknown_or_unsupported" in decisions["Thinking/Unknown"]["exclusion_reasons"]
    assert "retired_deprecated_or_unavailable" in decisions["Retired/Model"]["exclusion_reasons"]
    assert "region_access_not_documented" in decisions["Blocked/Region"]["exclusion_reasons"]
    assert "candidate_specific_interface_change_required" in decisions["Needs/Repair"]["exclusion_reasons"]


def test_utf8_ordering_first_four_fewer_and_zero_cases(tmp_path: Path) -> None:
    ids = ["z/model", "A/model", "é/model", "a/model", "B/model"]
    paths = _freeze(tmp_path / "five", [_model(model_id) for model_id in ids])
    registry = wave2.validate_wave2_candidate_pool_freeze(ROOT, **paths)
    expected = sorted(ids, key=lambda value: value.encode("utf-8"))[:4]
    assert [candidate.model_id for candidate in registry.candidates] == expected
    assert registry.freeze["complete_eligible_model_ids"] == sorted(
        ids, key=lambda value: value.encode("utf-8")
    )
    fewer = _freeze(tmp_path / "fewer", [_model("B"), _model("A")])
    assert len(wave2.validate_wave2_candidate_pool_freeze(ROOT, **fewer).candidates) == 2
    zero = _freeze(
        tmp_path / "zero",
        [_model("Paid", input_price="1.000000", output_price="1.000000")],
    )
    assert len(wave2.validate_wave2_candidate_pool_freeze(ROOT, **zero).candidates) == 0


def test_freeze_is_immutable_and_manual_reordering_is_rejected(tmp_path: Path) -> None:
    paths = _freeze(tmp_path, [_model("A"), _model("B")])
    with pytest.raises(FileExistsError):
        wave2.freeze_wave2_candidate_pool(ROOT, **paths)
    freeze = json.loads(paths["freeze_path"].read_text(encoding="utf-8"))
    freeze["selected_candidates"].reverse()
    _write(paths["freeze_path"], freeze)
    with pytest.raises(wave2.StageCWave2Error, match="deterministic first four"):
        wave2.validate_wave2_candidate_pool_freeze(ROOT, **paths)


def test_candidate_identity_thinking_and_contract_are_loaded_only_from_freeze(tmp_path: Path) -> None:
    paths = _freeze(
        tmp_path,
        [_model("Model/Omit"), _model("Model/Thinking", thinking_toggle="send_false")],
    )
    registry = wave2.validate_wave2_candidate_pool_freeze(ROOT, **paths)
    assert registry.candidate(1).model_id == "Model/Omit"
    assert registry.candidate(2).expected_provider_enable_thinking is False
    contract = registry.freeze["execution_contract"]
    assert contract["response_format"] == {"type": "json_object"}
    assert contract["temperature"] == 0
    assert contract["max_tokens"] == 1200
    assert contract["timeout_seconds"] == 120.0
    assert contract["probe_count"] == 6
    common = {
        "model": "New/Documented-Model",
        "system": "system",
        "prompt": "prompt",
        "temperature": 0,
        "max_tokens": 1200,
        "frequency_penalty": 0.0,
    }
    assert "enable_thinking" not in _chat_payload(**common, thinking_behavior="omit")
    assert _chat_payload(**common, thinking_behavior="send_false")["enable_thinking"] is False


def test_cli_has_no_model_force_order_or_output_override() -> None:
    script = ROOT / "scripts/run-western-stage-c-wave2-free.py"
    spec = importlib.util.spec_from_file_location("wave2_cli", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = vars(module.parse_args(["--inspect"]))
    assert set(args) == {
        "freeze_candidate_pool",
        "inspect",
        "record_not_zero_cost",
        "adjudicate_operationally_unevaluable",
        "finalize_exhaustion",
        "execute_candidate_preflight",
        "candidate",
        "replicate",
        "recovery",
        "confirm_zero_cost",
    }
    text = script.read_text(encoding="utf-8")
    for prohibited in ("--model", "--force", "--order", "--output"):
        assert prohibited not in text


def test_two_independent_replicates_select_primary_and_stop_later_candidates(tmp_path: Path) -> None:
    paths = _freeze(tmp_path / "freeze", [_model("Model/A"), _model("Model/B")])
    manifests, adjudications = _runtime(tmp_path)
    rep1 = _run(paths, manifests, adjudications)
    completed = wave2._parse_utc(rep1["completed_at"])
    early = wave2.evaluate_wave2_runner_eligibility(
        ROOT,
        1,
        2,
        current_time=completed + timedelta(seconds=3599),
        manifests_dir=manifests,
        adjudications_dir=adjudications,
        freeze_validation=paths,
    )
    assert early[0] is False
    rep2 = _run(
        paths,
        manifests,
        adjudications,
        replicate_number=2,
        current_time=completed + timedelta(seconds=3600),
    )
    assert rep2["candidate_qualification_status"] == "qualified_and_selected_primary_judge"
    assert wave2.assert_wave2_formal_stage_c_ready(
        ROOT,
        manifests_dir=manifests,
        adjudications_dir=adjudications,
        freeze_validation=paths,
    ).model_id == "Model/A"
    assert wave2.evaluate_wave2_runner_eligibility(
        ROOT,
        2,
        1,
        manifests_dir=manifests,
        adjudications_dir=adjudications,
        freeze_validation=paths,
    )[0] is False


def test_readiness_failure_precedes_infrastructure_and_unlocks_next(tmp_path: Path) -> None:
    paths = _freeze(tmp_path / "freeze", [_model("Model/A"), _model("Model/B")])
    manifests, adjudications = _runtime(tmp_path)
    registry = wave2.validate_wave2_candidate_pool_freeze(ROOT, **paths)
    candidate = registry.candidate(1)
    plan = get_synthetic_probe_plan()
    invalid = _payload(plan[0])
    invalid["claim_labels"][0]["label"] = "wrong"
    results: list[GenerationResult | Exception] = [
        _result(plan[0], candidate, payload=invalid),
        ProviderUnavailable("connect", error_type="connectivity"),
        *[_result(probe, candidate) for probe in plan[2:]],
    ]
    manifest = _run(
        paths,
        manifests,
        adjudications,
        provider=_provider(registry, 1, results),
    )
    assert manifest["execution_classification"] == "candidate_readiness_failure"
    assert manifest["infrastructure_recovery_authorized"] is False
    assert wave2.evaluate_wave2_runner_eligibility(
        ROOT,
        2,
        1,
        manifests_dir=manifests,
        adjudications_dir=adjudications,
        freeze_validation=paths,
    )[0] is True


def test_infrastructure_recovery_partial_success_no_pooling_and_adjudication(tmp_path: Path) -> None:
    paths = _freeze(tmp_path / "freeze", [_model("Model/A"), _model("Model/B")])
    manifests, adjudications = _runtime(tmp_path)
    registry = wave2.validate_wave2_candidate_pool_freeze(ROOT, **paths)
    successes = [_result(probe, registry.candidate(1)) for probe in get_synthetic_probe_plan()]
    infra = ProviderUnavailable("connect", error_type="connectivity")
    ordinary = _run(
        paths,
        manifests,
        adjudications,
        provider=_provider(registry, 1, [successes[0], successes[1], infra, infra, infra, infra]),
    )
    recovery = _run(
        paths,
        manifests,
        adjudications,
        recovery_number=1,
        provider=_provider(registry, 1, [successes[0], successes[1], successes[2], infra, infra, infra]),
    )
    assert ordinary["successful_probe_count"] == 2
    assert recovery["successful_probe_count"] == 3
    adjudication = wave2.create_wave2_operational_adjudication(
        ROOT,
        candidate_number=1,
        replicate_number=1,
        adjudicated_at=wave2._parse_utc("2026-09-20T14:10:00+00:00"),
        manifests_dir=manifests,
        adjudications_dir=adjudications,
        freeze_validation=paths,
    )
    assert adjudication["cross_attempt_pooling"] is False
    assert adjudication["adjudication_state"] == wave2.OPERATIONAL_UNEVALUABILITY_LABEL
    assert wave2.evaluate_wave2_runner_eligibility(
        ROOT,
        2,
        1,
        manifests_dir=manifests,
        adjudications_dir=adjudications,
        freeze_validation=paths,
    )[0] is True
    with pytest.raises(wave2.StageCWave2Error, match="Only Wave-2 recovery 01"):
        wave2.wave2_manifest_name(1, 1, 2)


def test_zero_cost_ineligibility_makes_no_call_and_remains_distinct(tmp_path: Path) -> None:
    paths = _freeze(tmp_path / "freeze", [_model("Model/A"), _model("Model/B")])
    manifests, adjudications = _runtime(tmp_path)
    note = wave2.record_wave2_zero_cost_ineligibility(
        ROOT,
        candidate_number=1,
        verified_at=wave2._parse_utc("2026-09-20T14:10:00+00:00"),
        manifests_dir=manifests,
        adjudications_dir=adjudications,
        freeze_validation=paths,
    )
    assert note["provider_calls_made"] == 0
    assert note["candidate_quality_interpretation"] is False
    state = wave2.inspect_wave2_state(
        ROOT,
        manifests_dir=manifests,
        adjudications_dir=adjudications,
        freeze_validation=paths,
    )
    assert wave2._candidate_state(state, 1) == "terminal_operational_ineligibility"
    assert wave2.evaluate_wave2_runner_eligibility(
        ROOT,
        2,
        1,
        manifests_dir=manifests,
        adjudications_dir=adjudications,
        freeze_validation=paths,
    )[0] is True


def test_final_exhaustion_for_zero_or_all_terminal_and_no_wave3(tmp_path: Path) -> None:
    zero_paths = _freeze(
        tmp_path / "zero-freeze",
        [_model("Paid", input_price="1.000000", output_price="1.000000")],
    )
    zero_manifests, zero_adjudications = _runtime(tmp_path / "zero-runtime")
    zero = wave2.create_wave2_exhaustion_artifact(
        ROOT,
        created_at=wave2._parse_utc("2026-09-20T14:10:00+00:00"),
        manifests_dir=zero_manifests,
        adjudications_dir=zero_adjudications,
        exhaustion_path=tmp_path / "zero-exhaustion.json",
        freeze_validation=zero_paths,
    )
    assert zero["pool_size"] == 0
    assert zero["wave3_permitted"] is False
    assert zero["w_rq2_semantic_estimates_available"] is False

    paths = _freeze(tmp_path / "one-freeze", [_model("Model/A")])
    manifests, adjudications = _runtime(tmp_path / "one-runtime")
    wave2.record_wave2_zero_cost_ineligibility(
        ROOT,
        candidate_number=1,
        manifests_dir=manifests,
        adjudications_dir=adjudications,
        freeze_validation=paths,
    )
    final = wave2.create_wave2_exhaustion_artifact(
        ROOT,
        manifests_dir=manifests,
        adjudications_dir=adjudications,
        exhaustion_path=tmp_path / "final-exhaustion.json",
        freeze_validation=paths,
    )
    assert final["automated_semantic_stage_c_terminated"] is True
    assert final["stage_a_and_stage_b_remain_valid"] is True


def test_formal_stage_c_blocked_before_selection_and_reserved_directory_absent(tmp_path: Path) -> None:
    paths = _freeze(tmp_path / "freeze", [_model("Model/A")])
    manifests, adjudications = _runtime(tmp_path)
    with pytest.raises(wave2.StageCWave2Error, match="blocked"):
        wave2.assert_wave2_formal_stage_c_ready(
            ROOT,
            manifests_dir=manifests,
            adjudications_dir=adjudications,
            freeze_validation=paths,
        )
    formal_dir = (
        ROOT
        / "research/experiments/western_formal_v0_1/stage_c_execution_v0_1_5_wave2_jrv1"
    )
    assert not formal_dir.exists()


def test_prompt_schema_probes_tcm_and_stage_ab_are_unchanged() -> None:
    assert hashlib.sha256(wave2.JUDGE_SYSTEM_PROMPT.encode("utf-8")).hexdigest() == (
        "b5c5b71ae89871d9854a806ea7f413caec36cba98aa74f396ff2224dfd0c5226"
    )
    schema_hash = hashlib.sha256(
        json.dumps(
            wave2.FormalJudgeOutput.model_json_schema(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert schema_hash == "2f33277a2e6292ad1c02fff423b6f0aa226b1da03bbb96da9b648bb1625e1d7a"
    assert len(get_synthetic_probe_plan()) == 6
    assert wave2.SCIENTIFIC_ANCHORS == {
        "stage_a_retrieval_sha256": "91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e",
        "primary_stage_b_sha256": "afc0665858b0493d9c4dfbc2d8990ccd89c663f2b63278221407cb876feaf17c",
        "primary_stage_b_run_manifest_sha256": "32fbc0765fc91395af187abb46b92d2fb13b9eed3acbea016f8ac18a6bc00511",
        "protocol_v0_1_2_sha256": "af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192",
    }
    assert not (ROOT / "research/experiments/western_formal_v0_1/stage_c_judge_wave2_free_v0_1_5/candidate-pool-freeze.json").exists()
