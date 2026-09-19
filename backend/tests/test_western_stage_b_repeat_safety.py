from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from providers.openai_compatible import ProviderUnavailable
import western.formal_eval as formal_eval
from western.formal_eval import (
    BENCHMARK_MANIFEST_SHA256,
    BENCHMARK_SHA256,
    CORPUS_CHUNKS_SHA256,
    GENERATOR_MAX_TOKENS,
    GENERATOR_MODEL,
    GENERATOR_PROVIDER,
    GENERATOR_TEMPERATURE,
    GENERATOR_TIMEOUT_SECONDS,
    ORIGINAL_STAGE_B_EXECUTION_FREEZE_COMMIT,
    ORIGINAL_STAGE_B_EXECUTION_MANIFEST_SHA256,
    ORIGINAL_STAGE_B_SHA256,
    ORIGINAL_STAGE_B_SEAL_MANIFEST_SHA256,
    PROTOCOL_SHA256,
    PROTOCOL_VERSION,
    SOURCE_REGISTRY_SHA256,
    STAGE_A_CHECKPOINT_COMMIT,
    STAGE_A_RETRIEVAL_SHA256,
    STAGE_A_RUN_ID,
    STAGE_B_REPEAT_EXECUTION_VERSION,
    STAGE_B_REPEAT_RUN_ID,
    FatalFormalRunError,
    RunDirectory,
    StageBRepeatDirectory,
    _canonical_json_sha256,
    _expected_provenance,
    _expected_readiness_policy,
    _expected_repeat_failure_policy,
    classify_stage_b_repeat_outage,
    finalize_stage_b_incident,
    finalize_stage_b_repeat,
    finalize_stage_b_run,
    run_stage_b_repeat,
    run_stage_b_repeat_readiness,
    verify_frozen_stage_a,
    verify_stage_b_repeat_execution_freeze,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_RUN = ROOT / "research/experiments/western_formal_v0_1/runs" / STAGE_A_RUN_ID


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _incident_config() -> dict[str, object]:
    return {
        "status": "stage_b_outage_incident",
        "run_id": STAGE_A_RUN_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "stage_b_execution_freeze_commit": ORIGINAL_STAGE_B_EXECUTION_FREEZE_COMMIT,
        "stage_b_sha256": ORIGINAL_STAGE_B_SHA256,
        "stage_b_seal_manifest_sha256": ORIGINAL_STAGE_B_SEAL_MANIFEST_SHA256,
        "stage_b_execution_manifest_sha256": ORIGINAL_STAGE_B_EXECUTION_MANIFEST_SHA256,
        "cell_count": 192,
        "completed_count": 106,
        "technical_failure_count": 86,
        "first_failure_position": 107,
        "first_failed_experiment_id": "western_formal_v0.1.2:westbench-v0.1-headache-03:R0",
        "consecutive_failure_suffix_count": 86,
        "successes_after_first_failure": 0,
        "retry_used_failure_count": 86,
        "attempt_count_two_failure_count": 86,
        "provider_reported_model": GENERATOR_MODEL,
        "provider_reported_model_count": 192,
        "final_error_counts": {"connectivity": 86},
        "first_error_counts": {"connectivity": 85, "timeout": 1},
        "failure_counts_by_condition": {"R0": 22, "R1": 22, "R2": 21, "R3": 21},
        "eligible_as_primary": False,
        "eligible_for_stage_c": False,
        "preservation_only": True,
        "decision_basis": "operational_failure_metadata_only",
        "standard_b_finalized": False,
        "stage_c_executed": False,
    }


def _execution_config() -> dict[str, object]:
    implementation = {
        "backend/western/formal_eval.py": _sha(ROOT / "backend/western/formal_eval.py"),
        "scripts/run-western-formal-v0.1.py": _sha(ROOT / "scripts/run-western-formal-v0.1.py"),
    }
    return {
        "execution_version": STAGE_B_REPEAT_EXECUTION_VERSION,
        "repeat_run_id": STAGE_B_REPEAT_RUN_ID,
        "repeat_ordinal": 1,
        "repeat_reason": "provider_outage",
        "repeat_scope": "all_192_cells",
        "reuse_original_successes": False,
        "primary_semantic_dataset": True,
        "scientific_protocol_unchanged": True,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_run_id": STAGE_A_RUN_ID,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "supersedes_stage_b_attempt_run_id": STAGE_A_RUN_ID,
        "superseded_stage_b_sha256": ORIGINAL_STAGE_B_SHA256,
        "benchmark_sha256": BENCHMARK_SHA256,
        "benchmark_manifest_sha256": BENCHMARK_MANIFEST_SHA256,
        "corpus_chunks_sha256": CORPUS_CHUNKS_SHA256,
        "source_registry_sha256": SOURCE_REGISTRY_SHA256,
        "provider": GENERATOR_PROVIDER,
        "model": GENERATOR_MODEL,
        "temperature": GENERATOR_TEMPERATURE,
        "max_tokens": GENERATOR_MAX_TOKENS,
        "timeout_seconds": GENERATOR_TIMEOUT_SECONDS,
        "incident_sha256": _canonical_json_sha256(_incident_config()),
        "readiness_policy": _expected_readiness_policy(),
        "repeat_failure_policy": _expected_repeat_failure_policy(),
        "implementation_commit": _head(),
        "implementation_sha256": implementation,
    }


@pytest.fixture
def copied_original(tmp_path: Path) -> RunDirectory:
    destination = tmp_path / "original" / STAGE_A_RUN_ID
    shutil.copytree(SOURCE_RUN, destination)
    return RunDirectory(destination)


def _finalize_incident(run: RunDirectory) -> None:
    finalize_stage_b_incident(
        ROOT, run, expected_execution_commit=_head(), require_clean_worktree=False,
        execution_config=_execution_config(), incident_config=_incident_config(),
    )


class ReadyProvider:
    name = GENERATOR_PROVIDER
    model = GENERATOR_MODEL
    timeout = GENERATOR_TIMEOUT_SECONDS
    max_tokens = GENERATOR_MAX_TOKENS
    api_key = "offline-test"

    def __init__(self, responses: list[object] | None = None) -> None:
        self.responses = list(responses or ["READY", "READY", "READY"])
        self.calls = 0

    async def generate(self, **kwargs: object) -> object:
        assert kwargs["prompt"] == "Return exactly the word READY."
        assert kwargs["max_tokens"] == 16
        self.calls += 1
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(text=value, model=GENERATOR_MODEL)


class StubGenerator:
    name = GENERATOR_PROVIDER
    model = GENERATOR_MODEL
    timeout = GENERATOR_TIMEOUT_SECONDS
    max_tokens = GENERATOR_MAX_TOKENS
    api_key = "offline-test"

    def __init__(self, fail_after: int | None = None) -> None:
        self.fail_after = fail_after
        self.calls = 0

    async def generate(self, **kwargs: object) -> object:
        del kwargs
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise TypeError("synthetic local defect")
        return SimpleNamespace(
            text="This synthetic educational response is based only on the supplied evidence and is not medical advice.",
            model=GENERATOR_MODEL,
        )


async def _no_sleep(_: float) -> None:
    return None


def _repeat(tmp_path: Path) -> StageBRepeatDirectory:
    return StageBRepeatDirectory(tmp_path / STAGE_B_REPEAT_RUN_ID)


def _readiness(run: RunDirectory, repeat: StageBRepeatDirectory, provider: ReadyProvider | None = None) -> None:
    asyncio.run(run_stage_b_repeat_readiness(
        ROOT, repeat, provider=provider or ReadyProvider(), sleep=_no_sleep,
        expected_execution_commit=_head(), require_clean_worktree=False,
        execution_config=_execution_config(), incident_config=_incident_config(), original_run=run,
    ))


def _run_repeat(run: RunDirectory, repeat: StageBRepeatDirectory, generator: object) -> None:
    asyncio.run(run_stage_b_repeat(
        ROOT, repeat, generator=generator,
        expected_execution_commit=_head(), require_clean_worktree=False,
        execution_config=_execution_config(), incident_config=_incident_config(), original_run=run,
    ))


def _finalize_repeat(run: RunDirectory, repeat: StageBRepeatDirectory) -> dict[str, object]:
    return finalize_stage_b_repeat(
        ROOT, repeat, expected_execution_commit=_head(), require_clean_worktree=False,
        execution_config=_execution_config(), incident_config=_incident_config(), original_run=run,
    )


def _success_record(retrieval: dict[str, object], answer: str = "Synthetic complete answer.") -> dict[str, object]:
    return {
        "experiment_id": retrieval["experiment_id"], "first_attempt_success": True,
        "attempt_count": 1, "technical_retry_used": False, "first_error_type": None,
        "final_error_type": None, "generation_success": True, "final_generation_success": True,
        "generation_outcome": "completed", "generation_latency_ms": 1.0, "answer": answer,
        "provenance": _expected_provenance(retrieval), "provider_reported_model": GENERATOR_MODEL,
        "errors": [], "timestamps": {"generation_completed_at": "2026-09-19T00:00:00+00:00"},
    }


def _failure_record(retrieval: dict[str, object]) -> dict[str, object]:
    return {
        "experiment_id": retrieval["experiment_id"], "first_attempt_success": False,
        "attempt_count": 2, "technical_retry_used": True, "first_error_type": "connectivity",
        "final_error_type": "connectivity", "generation_success": False,
        "final_generation_success": False, "generation_outcome": "technical_failure",
        "generation_latency_ms": 2.0, "answer": "", "provenance": _expected_provenance(retrieval),
        "provider_reported_model": GENERATOR_MODEL,
        "errors": [{"attempt": 1, "error_type": "connectivity", "message": "offline"}, {"attempt": 2, "error_type": "connectivity", "message": "offline"}],
        "timestamps": {"generation_completed_at": "2026-09-19T00:00:00+00:00"},
    }


def test_original_stage_b_sha_and_incident_finalizer_are_immutable(copied_original: RunDirectory) -> None:
    before = {name: _sha(copied_original.path / name) for name in (
        "stage_b_generation.jsonl", "stage_b_manifest.json", "stage_b_execution_manifest.json",
    )}
    assert before["stage_b_generation.jsonl"] == ORIGINAL_STAGE_B_SHA256
    _finalize_incident(copied_original)
    manifest = json.loads((copied_original.path / "stage_b_incident_manifest.json").read_text(encoding="utf-8"))
    assert manifest["eligible_as_primary"] is False
    assert manifest["eligible_for_stage_c"] is False
    assert manifest["completed_count"] == 106 and manifest["technical_failure_count"] == 86
    assert before == {name: _sha(copied_original.path / name) for name in before}
    with pytest.raises(FileExistsError):
        _finalize_incident(copied_original)


def test_tampered_original_stage_b_is_rejected(copied_original: RunDirectory) -> None:
    with copied_original.stage_path("B").open("a", encoding="utf-8") as handle:
        handle.write("{}\n")
    with pytest.raises((FatalFormalRunError, RuntimeError), match="hash|SHA256"):
        _finalize_incident(copied_original)


def test_original_standard_b_finalize_is_blocked(copied_original: RunDirectory) -> None:
    with pytest.raises(FatalFormalRunError, match="incident-preservation-only"):
        finalize_stage_b_run(ROOT, copied_original)


def test_exact_repeat_run_id_is_required(tmp_path: Path) -> None:
    with pytest.raises(FatalFormalRunError, match="exact run ID"):
        StageBRepeatDirectory(tmp_path / "failed-86-only")


def test_arbitrary_head_dirty_tree_and_freeze_mismatch_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(formal_eval, "_git_head", lambda root: "b" * 40)
    with pytest.raises(FatalFormalRunError, match="execution freeze HEAD"):
        verify_stage_b_repeat_execution_freeze(
            ROOT, expected_execution_commit="a" * 40,
            execution_config=_execution_config(), incident_config=_incident_config(),
        )
    monkeypatch.setattr(formal_eval, "_git_head", lambda root: "a" * 40)
    monkeypatch.setattr(formal_eval, "_git_worktree_clean", lambda root: False)
    with pytest.raises(FatalFormalRunError, match="clean Git working tree"):
        verify_stage_b_repeat_execution_freeze(
            ROOT, expected_execution_commit="a" * 40,
            execution_config=_execution_config(), incident_config=_incident_config(),
        )
    config = _execution_config()
    config["model"] = "wrong-model"
    with pytest.raises(FatalFormalRunError, match="freeze mismatch"):
        verify_stage_b_repeat_execution_freeze(
            ROOT, expected_execution_commit="a" * 40, require_clean_worktree=False,
            execution_config=config, incident_config=_incident_config(),
        )


def test_repeat_requires_passed_readiness(copied_original: RunDirectory, tmp_path: Path) -> None:
    _finalize_incident(copied_original)
    with pytest.raises(FatalFormalRunError, match="readiness"):
        _run_repeat(copied_original, _repeat(tmp_path), StubGenerator())


def test_mocked_readiness_three_of_three_passes_and_stays_out_of_formal_jsonl(copied_original: RunDirectory, tmp_path: Path) -> None:
    _finalize_incident(copied_original)
    repeat = _repeat(tmp_path)
    provider = ReadyProvider()
    _readiness(copied_original, repeat, provider)
    assert provider.calls == 3
    assert (repeat.path / "stage_b_repeat_readiness_manifest.json").is_file()
    assert not repeat.stage_path().exists()


@pytest.mark.parametrize("responses", [["READY", "READY", "NO"], ["READY", ProviderUnavailable("offline", error_type="connectivity")]])
def test_readiness_two_of_three_or_provider_error_fails(copied_original: RunDirectory, tmp_path: Path, responses: list[object]) -> None:
    _finalize_incident(copied_original)
    repeat = _repeat(tmp_path)
    with pytest.raises(FatalFormalRunError, match="readiness probe"):
        _readiness(copied_original, repeat, ReadyProvider(responses))
    assert not (repeat.path / "stage_b_repeat_readiness_manifest.json").exists()


def test_fresh_repeat_runs_all_192_and_never_reuses_original_answers(copied_original: RunDirectory, tmp_path: Path) -> None:
    _finalize_incident(copied_original)
    repeat = _repeat(tmp_path)
    _readiness(copied_original, repeat)
    generator = StubGenerator()
    _run_repeat(copied_original, repeat, generator)
    assert generator.calls == 192
    rows = [json.loads(line) for line in repeat.stage_path().read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 192
    assert all("synthetic educational response" in row["answer"] for row in rows)
    assert repeat.stage_manifest_path().is_file()


def test_manifest_only_crash_and_partial_prefix_resume(copied_original: RunDirectory, tmp_path: Path) -> None:
    _finalize_incident(copied_original)
    repeat = _repeat(tmp_path)
    _readiness(copied_original, repeat)
    with pytest.raises(FatalFormalRunError, match="programming/runtime defect"):
        _run_repeat(copied_original, repeat, StubGenerator(fail_after=0))
    assert (repeat.path / "stage_b_repeat_execution_manifest.json").is_file()
    assert not repeat.stage_path().exists()
    with pytest.raises(FatalFormalRunError):
        _run_repeat(copied_original, repeat, StubGenerator(fail_after=3))
    assert len(repeat.stage_path().read_text(encoding="utf-8").splitlines()) == 3
    resumed = StubGenerator()
    _run_repeat(copied_original, repeat, resumed)
    assert resumed.calls == 189


def test_192_rows_before_seal_recovery_makes_zero_provider_calls(copied_original: RunDirectory, tmp_path: Path) -> None:
    _finalize_incident(copied_original)
    repeat = _repeat(tmp_path)
    _readiness(copied_original, repeat)
    with pytest.raises(FatalFormalRunError):
        _run_repeat(copied_original, repeat, StubGenerator(fail_after=0))
    stage_a = verify_frozen_stage_a(ROOT, copied_original)
    repeat.stage_path().write_text("".join(json.dumps(_success_record(row), sort_keys=True) + "\n" for row in stage_a), encoding="utf-8")
    generator = StubGenerator(fail_after=0)
    _run_repeat(copied_original, repeat, generator)
    assert generator.calls == 0
    assert repeat.stage_manifest_path().is_file()


@pytest.mark.parametrize("kind", ["duplicate", "foreign", "out_of_order"])
def test_invalid_repeat_prefixes_are_rejected(copied_original: RunDirectory, tmp_path: Path, kind: str) -> None:
    _finalize_incident(copied_original)
    repeat = _repeat(tmp_path)
    _readiness(copied_original, repeat)
    with pytest.raises(FatalFormalRunError):
        _run_repeat(copied_original, repeat, StubGenerator(fail_after=0))
    stage_a = verify_frozen_stage_a(ROOT, copied_original)
    records = [_success_record(stage_a[0]), _success_record(stage_a[1])]
    if kind == "duplicate":
        records[1] = _success_record(stage_a[0])
    elif kind == "foreign":
        records[1]["experiment_id"] = "foreign"
    else:
        records.reverse()
    repeat.stage_path().write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    with pytest.raises(FatalFormalRunError, match="duplicate|foreign|prefix"):
        _run_repeat(copied_original, repeat, StubGenerator())


def test_repeat_seal_requires_exact_order(tmp_path: Path) -> None:
    repeat = _repeat(tmp_path)
    repeat.path.mkdir(parents=True)
    repeat.stage_path().write_text("".join(json.dumps({"experiment_id": f"cell-{i}"}) + "\n" for i in range(192)), encoding="utf-8")
    with pytest.raises(FatalFormalRunError, match="exact ordered"):
        repeat.seal([f"expected-{i}" for i in range(192)])


def test_repeat_outage_threshold_and_isolated_missingness() -> None:
    successes = [{"experiment_id": f"c-{i}", "generation_success": True, "final_error_type": None} for i in range(192)]
    isolated = list(successes)
    isolated[50] = {"experiment_id": "c-50", "generation_success": False, "final_error_type": "connectivity"}
    assert classify_stage_b_repeat_outage(isolated)["run_level_outage"] is False
    suffix_19 = successes[:173] + [{"experiment_id": f"f-{i}", "generation_success": False, "final_error_type": "connectivity"} for i in range(19)]
    suffix_20 = successes[:172] + [{"experiment_id": f"f-{i}", "generation_success": False, "final_error_type": "connectivity"} for i in range(20)]
    assert classify_stage_b_repeat_outage(suffix_19)["run_level_outage"] is False
    result = classify_stage_b_repeat_outage(suffix_20)
    assert result["run_level_outage"] is True
    assert result["third_attempt_automatically_authorized"] is False


def test_successful_repeat_finalizes_as_primary(copied_original: RunDirectory, tmp_path: Path) -> None:
    _finalize_incident(copied_original)
    repeat = _repeat(tmp_path)
    _readiness(copied_original, repeat)
    _run_repeat(copied_original, repeat, StubGenerator())
    result = _finalize_repeat(copied_original, repeat)
    manifest = json.loads((repeat.path / "stage_b_run_manifest.json").read_text(encoding="utf-8"))
    assert result["classification"]["run_level_outage"] is False
    assert manifest["eligible_as_primary"] is True and manifest["eligible_for_stage_c"] is True
    assert manifest["reuse_original_successes"] is False


def test_outage_repeat_cannot_become_stage_c_input(copied_original: RunDirectory, tmp_path: Path) -> None:
    _finalize_incident(copied_original)
    repeat = _repeat(tmp_path)
    _readiness(copied_original, repeat)
    with pytest.raises(FatalFormalRunError):
        _run_repeat(copied_original, repeat, StubGenerator(fail_after=0))
    stage_a = verify_frozen_stage_a(ROOT, copied_original)
    records = [_success_record(row) for row in stage_a[:172]] + [_failure_record(row) for row in stage_a[172:]]
    repeat.stage_path().write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in records), encoding="utf-8")
    repeat.seal([row["experiment_id"] for row in stage_a])
    result = _finalize_repeat(copied_original, repeat)
    manifest = json.loads((repeat.path / "stage_b_repeat_outage_manifest.json").read_text(encoding="utf-8"))
    assert result["classification"]["run_level_outage"] is True
    assert manifest["eligible_for_stage_c"] is False
    assert manifest["third_attempt_automatically_authorized"] is False
    assert not (repeat.path / "stage_b_run_manifest.json").exists()
