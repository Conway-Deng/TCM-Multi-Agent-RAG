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
from western.formal_eval import (
    BENCHMARK_MANIFEST_SHA256,
    BENCHMARK_SHA256,
    CORPUS_CHUNKS_SHA256,
    GENERATOR_MODEL,
    PROTOCOL_SHA256,
    PROTOCOL_VERSION,
    SOURCE_REGISTRY_SHA256,
    STAGE_A_CHECKPOINT_COMMIT,
    STAGE_A_RETRIEVAL_SHA256,
    STAGE_A_RUN_ID,
    STAGE_B_EXECUTION_VERSION,
    FatalFormalRunError,
    RunDirectory,
    _expected_provenance,
    _validate_stage_b_record,
    finalize_stage_b_run,
    invoke_stage_b_generation,
    load_frozen_cases,
    load_frozen_execution_order,
    run_stage_b,
    verify_frozen_stage_a,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_RUN = ROOT / "research/experiments/western_formal_v0_1/runs" / STAGE_A_RUN_ID


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _execution_config() -> dict[str, object]:
    implementation = {
        "backend/western/formal_eval.py": _sha(ROOT / "backend/western/formal_eval.py"),
        "scripts/run-western-formal-v0.1.py": _sha(ROOT / "scripts/run-western-formal-v0.1.py"),
    }
    return {
        "execution_version": STAGE_B_EXECUTION_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_run_id": STAGE_A_RUN_ID,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "benchmark_sha256": BENCHMARK_SHA256,
        "benchmark_manifest_sha256": BENCHMARK_MANIFEST_SHA256,
        "corpus_chunks_sha256": CORPUS_CHUNKS_SHA256,
        "source_registry_sha256": SOURCE_REGISTRY_SHA256,
        "implementation_sha256": implementation,
    }


@pytest.fixture
def copied_run(tmp_path: Path) -> RunDirectory:
    destination = tmp_path / STAGE_A_RUN_ID
    shutil.copytree(SOURCE_RUN, destination)
    # The canonical source run now contains the sealed provider-outage Stage B.
    # Legacy Stage-B execution tests need an isolated Stage-A-only copy.
    for name in ("stage_b_generation.jsonl", "stage_b_manifest.json", "stage_b_execution_manifest.json"):
        (destination / name).unlink(missing_ok=True)
    return RunDirectory.resume(destination)


class StubGenerator:
    name = "siliconflow"
    model = GENERATOR_MODEL

    def __init__(self, *, fail_after: int | None = None) -> None:
        self.calls = 0
        self.fail_after = fail_after

    async def generate(self, **kwargs: object) -> object:
        del kwargs
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise TypeError("synthetic programming defect")
        return SimpleNamespace(
            text="This synthetic educational response is based only on the supplied evidence and is not medical advice.",
            model=GENERATOR_MODEL,
        )


def _run_b(run: RunDirectory, generator: object) -> None:
    asyncio.run(run_stage_b(
        ROOT, run, generator=generator,
        expected_execution_commit=_head(), require_clean_worktree=False,
        execution_config=_execution_config(),
    ))


def _success_record(retrieval: dict[str, object]) -> dict[str, object]:
    return {
        "experiment_id": retrieval["experiment_id"],
        "first_attempt_success": True,
        "attempt_count": 1,
        "technical_retry_used": False,
        "first_error_type": None,
        "final_error_type": None,
        "generation_success": True,
        "final_generation_success": True,
        "generation_outcome": "completed",
        "generation_latency_ms": 1.0,
        "answer": "Synthetic valid educational answer.",
        "provenance": _expected_provenance(retrieval),
        "provider_reported_model": GENERATOR_MODEL,
        "errors": [],
        "timestamps": {"generation_completed_at": "2026-09-18T00:00:00+00:00"},
    }


def _write_execution_manifest(run: RunDirectory) -> None:
    anchor_hash = hashlib.sha256(json.dumps(_execution_config(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload = {
        "stage": "B", "status": "in_progress", "run_id": STAGE_A_RUN_ID,
        "protocol_version": PROTOCOL_VERSION, "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "stage_b_execution_version": STAGE_B_EXECUTION_VERSION,
        "stage_b_execution_freeze_commit": _head(),
        "stage_b_execution_json_sha256": anchor_hash,
        "implementation_sha256": _execution_config()["implementation_sha256"],
        "created_at": "2026-09-18T00:00:00+00:00",
    }
    (run.path / "stage_b_execution_manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_arbitrary_head_and_dirty_worktree_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    import western.formal_eval as module
    monkeypatch.setattr(module, "_git_head", lambda root: "b" * 40)
    with pytest.raises(FatalFormalRunError, match="execution freeze HEAD"):
        module.verify_stage_b_execution_freeze(ROOT, expected_execution_commit="a" * 40, execution_config=_execution_config())
    monkeypatch.setattr(module, "_git_head", lambda root: "a" * 40)
    monkeypatch.setattr(module, "_git_worktree_clean", lambda root: False)
    with pytest.raises(FatalFormalRunError, match="clean Git working tree"):
        module.verify_stage_b_execution_freeze(ROOT, expected_execution_commit="a" * 40, execution_config=_execution_config())


def test_tampered_stage_a_is_rejected(copied_run: RunDirectory) -> None:
    with copied_run.stage_path("A").open("a", encoding="utf-8") as handle:
        handle.write("{}\n")
    with pytest.raises(FatalFormalRunError, match="SHA256 mismatch"):
        verify_frozen_stage_a(ROOT, copied_run)


def test_exact_stage_a_matrix_validation(copied_run: RunDirectory) -> None:
    records = verify_frozen_stage_a(ROOT, copied_run)
    expected = [cell["experiment_id"] for cell in load_frozen_execution_order(ROOT, load_frozen_cases(ROOT))]
    assert [row["experiment_id"] for row in records] == expected
    assert len(records) == 192


def test_fresh_stage_b_start_creates_manifest_and_seals(copied_run: RunDirectory) -> None:
    generator = StubGenerator()
    _run_b(copied_run, generator)
    assert generator.calls == 192
    assert (copied_run.path / "stage_b_execution_manifest.json").is_file()
    assert copied_run.stage_manifest_path("B").is_file()


def test_crash_after_manifest_before_first_call_resumes(copied_run: RunDirectory) -> None:
    crashing = StubGenerator(fail_after=0)
    with pytest.raises(FatalFormalRunError, match="programming/runtime defect"):
        _run_b(copied_run, crashing)
    assert (copied_run.path / "stage_b_execution_manifest.json").is_file()
    assert not copied_run.stage_path("B").exists()
    resumed = StubGenerator()
    _run_b(copied_run, resumed)
    assert resumed.calls == 192


def test_partial_resume_only_calls_remaining_cells(copied_run: RunDirectory) -> None:
    first = StubGenerator(fail_after=3)
    with pytest.raises(FatalFormalRunError):
        _run_b(copied_run, first)
    assert len(copied_run.stage_path("B").read_text(encoding="utf-8").splitlines()) == 3
    resumed = StubGenerator()
    _run_b(copied_run, resumed)
    assert resumed.calls == 189


def test_192_rows_before_seal_recovery_makes_zero_provider_calls(copied_run: RunDirectory) -> None:
    stage_a = verify_frozen_stage_a(ROOT, copied_run)
    _write_execution_manifest(copied_run)
    copied_run.stage_path("B").write_text("".join(json.dumps(_success_record(row), sort_keys=True) + "\n" for row in stage_a), encoding="utf-8")
    generator = StubGenerator(fail_after=0)
    _run_b(copied_run, generator)
    assert generator.calls == 0
    assert copied_run.stage_manifest_path("B").is_file()


@pytest.mark.parametrize("kind", ["duplicate", "foreign"])
def test_duplicate_or_foreign_stage_b_ids_are_rejected(copied_run: RunDirectory, kind: str) -> None:
    stage_a = verify_frozen_stage_a(ROOT, copied_run)
    _write_execution_manifest(copied_run)
    records = [_success_record(stage_a[0]), _success_record(stage_a[0] if kind == "duplicate" else stage_a[1])]
    if kind == "foreign":
        records[1]["experiment_id"] = "foreign-cell"
    copied_run.stage_path("B").write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    with pytest.raises(FatalFormalRunError, match="duplicate|foreign"):
        _run_b(copied_run, StubGenerator())


def test_stage_b_seal_requires_exact_stage_a_id_set(tmp_path: Path) -> None:
    run = RunDirectory.create(tmp_path, "unit")
    run.stage_path("B").write_text(
        "".join(json.dumps({"experiment_id": f"cell-{index}"}) + "\n" for index in range(192)),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="differ from"):
        run.seal("B", expected_experiment_ids={f"expected-{index}" for index in range(192)})


@pytest.mark.parametrize(
    ("exc", "outcome", "attempts"),
    [
        (ProviderUnavailable("quality", error_type="output_quality_rejection"), "output_quality_rejection", 1),
        (ProviderUnavailable("limited", error_type="rate_limit", http_status=429), "rate_limit", 1),
    ],
)
def test_nonretryable_provider_outcomes_are_explicit(exc: Exception, outcome: str, attempts: int) -> None:
    calls = 0
    async def operation() -> object:
        nonlocal calls
        calls += 1
        raise exc
    result = asyncio.run(invoke_stage_b_generation(operation))
    assert result.generation_outcome == outcome
    assert result.attempt_count == attempts
    assert result.technical_retry_used is False
    assert calls == 1


@pytest.mark.parametrize("exc", [TypeError("bug"), KeyError("bug"), AssertionError("bug")])
def test_programming_defects_are_fatal(exc: Exception) -> None:
    async def operation() -> object:
        raise exc
    with pytest.raises(FatalFormalRunError, match="programming/runtime defect"):
        asyncio.run(invoke_stage_b_generation(operation))


@pytest.mark.parametrize("error_type,status", [("configuration", None), ("authentication", None), ("http_4xx", 401), ("http_4xx", 403)])
def test_authentication_and_configuration_failures_are_fatal(error_type: str, status: int | None) -> None:
    async def operation() -> object:
        raise ProviderUnavailable("fatal config", error_type=error_type, http_status=status)
    with pytest.raises(FatalFormalRunError, match="configuration/authentication"):
        asyncio.run(invoke_stage_b_generation(operation))


def test_provenance_violation_is_fatal(copied_run: RunDirectory) -> None:
    retrieval = verify_frozen_stage_a(ROOT, copied_run)[0]
    record = _success_record(retrieval)
    record["provenance"][0]["source_id"] = "tampered-source"  # type: ignore[index]
    with pytest.raises(FatalFormalRunError, match="provenance invariant"):
        _validate_stage_b_record(ROOT, retrieval, record)


def test_stage_b_finalization_is_immutable_and_emits_only_b_artifacts(copied_run: RunDirectory) -> None:
    _run_b(copied_run, StubGenerator())
    hashes = finalize_stage_b_run(
        ROOT, copied_run, expected_execution_commit=_head(), require_clean_worktree=False,
        execution_config=_execution_config(),
    )
    required = {"stage_b_raw_results.jsonl", "stage_b_generation_metrics.json", "stage_b_provider_metrics.json", "stage_b_run_manifest.json", "STAGE_B_FROZEN.md"}
    assert required <= set(hashes)
    assert not copied_run.stage_path("C").exists()
    with pytest.raises(FileExistsError):
        finalize_stage_b_run(
            ROOT, copied_run, expected_execution_commit=_head(), require_clean_worktree=False,
            execution_config=_execution_config(),
        )
