from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from western.formal_eval import (
    FatalFormalRunError,
    RunDirectory,
    _base_record,
    _git_worktree_clean,
    finalize_stage_a_run,
    load_frozen_cases,
    load_frozen_execution_order,
)


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Formal Tester"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo, check=True)

    # Copy .gitignore
    (repo / ".gitignore").write_text((ROOT / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")

    # Copy frozen inputs and protocol
    for rel in (
        "research/experiments/western_formal_v0_1/protocol_v0_1_2",
        "research/benchmarks/western_pilot_v0_1",
        "research/corpus/west_v0_1",
    ):
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / rel, dest)

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Freeze Western formal evaluation protocol v0.1.2"], cwd=repo, check=True, capture_output=True)
    return repo


def test_a_unrelated_untracked_file_causes_dirty_gate_to_reject_stage_a(clean_repo: Path) -> None:
    untracked = clean_repo / "unrelated_untracked_file.txt"
    untracked.write_text("untracked development edit", encoding="utf-8")
    assert not _git_worktree_clean(clean_repo), "Worktree must be detected as dirty"
    runs_dir = clean_repo / "research/experiments/western_formal_v0_1/runs"
    with pytest.raises(FatalFormalRunError, match="clean Git working tree"):
        RunDirectory.create(runs_dir, "rejected-run", repository_root=clean_repo, require_clean_worktree=True)
    untracked.unlink()
    assert _git_worktree_clean(clean_repo), "Worktree must be clean after removal"


def test_b_files_under_ignored_runs_do_not_make_git_status_dirty(clean_repo: Path) -> None:
    runs_dir = clean_repo / "research/experiments/western_formal_v0_1/runs/synthetic_run_b"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "run_manifest.json").write_text("{}", encoding="utf-8")
    (runs_dir / "stage_a_retrieval.jsonl").write_text('{"evidence_excerpt": "source text"}\n', encoding="utf-8")
    assert _git_worktree_clean(clean_repo), "Worktree must remain clean when files exist under ignored runs/**"


def test_c_files_under_ignored_cache_do_not_make_git_status_dirty(clean_repo: Path) -> None:
    cache_dir = clean_repo / "research/experiments/western_formal_v0_1/cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "bge_m3_cache.json").write_text(json.dumps({"hash1": [0.1, 0.2]}), encoding="utf-8")
    assert _git_worktree_clean(clean_repo), "Worktree must remain clean when files exist under ignored cache/**"


def test_d_after_run_directory_create_repository_remains_git_clean(clean_repo: Path) -> None:
    runs_dir = clean_repo / "research/experiments/western_formal_v0_1/runs"
    run_d = RunDirectory.create(
        runs_dir, "synthetic-run-d", repository_root=clean_repo, require_clean_worktree=True,
    )
    assert _git_worktree_clean(clean_repo), "Worktree must remain clean after RunDirectory.create()"
    run_d.verify_run_manifest(clean_repo, require_clean_worktree=True)


def test_e_after_synthetic_dense_cache_write_repository_remains_git_clean(clean_repo: Path) -> None:
    cache_dir = clean_repo / "research/experiments/western_formal_v0_1/cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "dense_vectors.json").write_text(json.dumps({"synthetic_query": [0.0] * 1024}), encoding="utf-8")
    assert _git_worktree_clean(clean_repo), "Worktree must remain clean after dense cache write"


def test_f_resume_can_proceed_with_existing_ignored_run_and_cache_artifacts(clean_repo: Path) -> None:
    runs_dir = clean_repo / "research/experiments/western_formal_v0_1/runs"
    cache_dir = clean_repo / "research/experiments/western_formal_v0_1/cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "dense_vectors.json").write_text(json.dumps({"q": [0.5]}), encoding="utf-8")

    run_f = RunDirectory.create(
        runs_dir, "synthetic-run-f", repository_root=clean_repo, require_clean_worktree=True,
    )
    cases = load_frozen_cases(clean_repo)
    first_order = load_frozen_execution_order(clean_repo, cases)[0]
    first_case = next(c for c in cases if c["case_id"] == first_order["case_id"])
    run_f.append("A", {
        **_base_record(first_case, first_order["retrieval_condition"]),
        "retrieval_success": True, "terminal_state": "success",
        "attempt_count": 1, "technical_retry_used": False,
        "technical_retry_stage": "none", "first_error_type": None,
        "final_error_type": None, "errors": [], "provider_operation_trace": [],
        "retrieval_latency_ms": 1.0, "retrieved_items": [], "timestamps": {},
    })
    assert _git_worktree_clean(clean_repo), "Worktree must remain clean after appending cell"

    resumed = RunDirectory.resume_stage_a(run_f.path, repository_root=clean_repo)
    resumed.verify_run_manifest(clean_repo, require_clean_worktree=True)
    assert resumed.completed_ids("A") == {first_order["experiment_id"]}


def test_g_finalization_can_proceed_with_ignored_run_and_cache_artifacts(clean_repo: Path) -> None:
    runs_dir = clean_repo / "research/experiments/western_formal_v0_1/runs"
    cache_dir = clean_repo / "research/experiments/western_formal_v0_1/cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "dense_vectors.json").write_text(json.dumps({"q": [0.5]}), encoding="utf-8")

    run_g = RunDirectory.create(
        runs_dir, "synthetic-run-g", repository_root=clean_repo, require_clean_worktree=True,
    )
    cases = load_frozen_cases(clean_repo)
    order = load_frozen_execution_order(clean_repo, cases)
    cases_by_id = {c["case_id"]: c for c in cases}
    for cell in order:
        case = cases_by_id[cell["case_id"]]
        run_g.append("A", {
            **_base_record(case, cell["retrieval_condition"]),
            "retrieval_success": True, "terminal_state": "success",
            "attempt_count": 1, "technical_retry_used": False,
            "technical_retry_stage": "none", "first_error_type": None,
            "final_error_type": None, "errors": [], "provider_operation_trace": [],
            "retrieval_latency_ms": 1.0, "retrieved_items": [], "timestamps": {},
        })
    run_g.seal("A")
    assert _git_worktree_clean(clean_repo), "Worktree must remain clean after sealing Stage A"

    hashes = finalize_stage_a_run(clean_repo, run_g, require_clean_worktree=True)
    required = {
        "stage_a_raw_results.jsonl", "stage_a_retrieval_metrics.json",
        "stage_a_provider_metrics.json", "stage_a_run_manifest.json",
        "stage_a_pairwise_statistics.json", "STAGE_A_FROZEN.md",
    }
    assert required <= set(hashes)
    assert _git_worktree_clean(clean_repo), "Worktree must remain clean after Stage A finalization"
