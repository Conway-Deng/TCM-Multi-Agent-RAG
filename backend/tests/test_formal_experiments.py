from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from formal_experiments import worker
from formal_experiments.jobs import CustomJobService, FormalJobService
from formal_experiments.registry import frozen_root, public_registry, validate_replay_path, verify_deployment_integrity
from formal_experiments.schemas import CustomRunRequest, FormalRunRequest
from formal_experiments.store import FormalJobStore
from formal_experiments.worker_service import FormalReplayWorker


EXPERIMENT_IDS = [
    "retrieval_ablation", "rq1_architecture", "rq4_debate",
    "research_b", "research_c", "a3_v1_3",
]


def file_hashes(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*") if path.is_file()
    }


def test_registry_exposes_six_separate_locked_studies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(tmp_path))
    studies = public_registry()
    assert [item["experiment_id"] for item in studies] == EXPERIMENT_IDS
    assert all(item["paper_protocol_locked"] for item in studies)
    assert all(item["available_run_modes"] == [] for item in studies)
    assert all(item["missing_artifacts"] for item in studies)
    assert all(
        capability["state"] == "UNAVAILABLE" and "integrity" in capability["reason"].lower()
        for item in studies for capability in item["run_capabilities"].values()
    )


def test_repository_relative_assets_and_hashes_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORMAL_EXPERIMENT_ROOT", raising=False)
    monkeypatch.delenv("FORMAL_ALLOW_FULL_BENCHMARK", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "siliconflow")
    monkeypatch.setenv("LLM_API_KEY", "offline-test-placeholder")
    assert frozen_root() == ROOT.resolve()
    manifest = json.loads((ROOT / "research/formal_assets_deployment_manifest.json").read_text(encoding="utf-8"))
    assert manifest["asset_count"] == len(manifest["assets"]) == 139
    assert len({item["path"] for item in manifest["assets"]}) == 139
    for experiment_id in EXPERIMENT_IDS:
        assert verify_deployment_integrity(ROOT, experiment_id) == (True, [])
    studies = {item["experiment_id"]: item for item in public_registry()}
    assert all(item["hash_verification"] == "PASS" for item in studies.values())
    assert studies["retrieval_ablation"]["available_run_modes"] == []
    for experiment_id in EXPERIMENT_IDS[1:]:
        assert studies[experiment_id]["available_run_modes"] == ["one_case", "paired"]
        assert studies[experiment_id]["run_capabilities"]["full_benchmark"]["state"] == "LOCAL FULL REPLAY"


def test_relative_frozen_root_is_resolved_from_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", ".")
    assert frozen_root() == ROOT.resolve()
    assert "TemporaryDirectory" in (ROOT / "backend/formal_experiments/worker_service.py").read_text(encoding="utf-8")
    assert "FORMAL_REPLAY_ROOT" not in (ROOT / "backend/formal_experiments/worker_service.py").read_text(encoding="utf-8")


def test_replay_root_cannot_target_deployed_or_frozen_directories(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(ROOT))
    with pytest.raises(ValueError, match="must not target"):
        validate_replay_path(ROOT, ROOT / "research/experiments/rq4_debate_vs_multiagent/formal_run_v1")


def test_a3_nested_formal_outputs_are_visible_to_job_service(tmp_path: Path) -> None:
    output = tmp_path / "replay"
    formal = output / "formal"
    formal.mkdir(parents=True)
    (formal / "run_progress.json").write_text(json.dumps({
        "completed_canonical": 2, "current_question_id": "rq4-v1-025", "current_condition": "M2",
    }), encoding="utf-8")
    (formal / "formal_results.jsonl").write_text(
        json.dumps({"question_id": "rq4-v1-025", "condition": "M1", "usable": True}) + "\n"
        + json.dumps({"question_id": "rq4-v1-025", "condition": "M2", "usable": True}) + "\n",
        encoding="utf-8",
    )
    assert FormalJobService._worker_status(output) == {
        "completed": 2, "current_condition": "M2", "current_case": "rq4-v1-025", "successful": 2, "failed": 0,
    }


def test_hash_mismatch_disables_affected_experiment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manifest = json.loads((ROOT / "research/formal_assets_deployment_manifest.json").read_text(encoding="utf-8"))
    selected = manifest["experiments"]["research_b"]["assets"]
    (tmp_path / "research").mkdir()
    (tmp_path / "research/formal_assets_deployment_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for relative in selected:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    tampered = tmp_path / selected[0]
    tampered.write_bytes(tampered.read_bytes() + b"tampered")
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(tmp_path))
    item = next(value for value in public_registry() if value["experiment_id"] == "research_b")
    assert item["hash_verification"] == "FAIL" and item["available_run_modes"] == []
    assert all(value["state"] == "UNAVAILABLE" for value in item["run_capabilities"].values())


def test_missing_provider_never_exposes_guaranteed_failure_button(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(ROOT))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    studies = public_registry()
    assert all(item["hash_verification"] == "PASS" for item in studies)
    assert all(item["available_run_modes"] == [] for item in studies)
    assert all(
        value["state"] == "UNAVAILABLE" and "SiliconFlow" in value["reason"]
        for item in studies for value in item["run_capabilities"].values()
    )


def test_condition_controls_and_exact_frozen_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(ROOT))
    monkeypatch.setenv("FORMAL_ALLOW_FULL_BENCHMARK", "true")
    monkeypatch.setenv("LLM_PROVIDER", "siliconflow")
    monkeypatch.setenv("LLM_API_KEY", "offline-test-placeholder")
    studies = {item["experiment_id"]: item for item in public_registry()}
    assert [item["id"] for item in studies["rq1_architecture"]["conditions"]] == ["C1", "C2"]
    assert [item["id"] for item in studies["rq4_debate"]["conditions"]] == ["C2", "C4"]
    assert [item["id"] for item in studies["research_b"]["conditions"]] == ["J1", "J2"]
    assert [item["id"] for item in studies["research_c"]["conditions"]] == ["K1", "K2"]
    assert [item["id"] for item in studies["a3_v1_3"]["conditions"]] == ["M1", "M2"]
    assert studies["research_c"]["conditions"][0]["name"].startswith("Standard source-grounded")
    assert studies["research_c"]["conditions"][1]["name"].startswith("Conflict-aware answering")
    assert studies["retrieval_ablation"]["available_run_modes"] == ["full_benchmark"]
    for experiment_id in EXPERIMENT_IDS[1:]:
        assert studies[experiment_id]["available_run_modes"] == ["one_case", "paired", "full_benchmark"]
    assert {key: value["scheduled_executions"] for key, value in studies.items()} == {
        "retrieval_ablation": 520,
        "rq1_architecture": 200,
        "rq4_debate": 200,
        "research_b": 480,
        "research_c": 264,
        "a3_v1_3": 200,
    }


def test_original_adapters_resolve_exact_deployed_runners() -> None:
    script = """
from pathlib import Path
from formal_experiments import worker
root = Path.cwd()
b = worker._load(root / 'research/research_b/runner.py', 'test_frozen_research_b')
c = worker._load(root / 'research/research_c/runner.py', 'test_frozen_research_c')
a3 = worker._load(root / 'research/multi_model_debate/formal_runner.py', 'test_frozen_a3')
rq4 = worker._load(root / 'research/experiment_pipeline/rq4_platform.py', 'test_frozen_rq4')
assert callable(b.request_prediction) and callable(b.validate_frozen)
assert callable(c.request_prediction) and callable(c.validate_frozen)
assert hasattr(a3, 'FormalExecutionRunner') and callable(a3.prepare_clean_restart)
assert callable(rq4.request_execution) and callable(rq4.execution_order)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(BACKEND)},
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_retrieval_adapter_pins_frozen_remote_models() -> None:
    source = (ROOT / "backend/formal_experiments/worker.py").read_text(encoding="utf-8")
    assert '"EMBEDDING_PROVIDER": "siliconflow"' in source
    assert '"EMBEDDING_MODEL": "BAAI/bge-m3"' in source
    assert '"RERANK_PROVIDER": "siliconflow"' in source
    assert '"RERANK_MODEL": "BAAI/bge-reranker-v2-m3"' in source


def test_no_machine_specific_production_dependency() -> None:
    targets = [ROOT / "backend/formal_experiments", ROOT / "backend/.env.example", ROOT / "research-app.js"]
    paths = [path for target in targets for path in ([target] if target.is_file() else target.rglob("*.py"))]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "D:\\" not in text and "D:/" not in text


def test_formal_request_forbids_custom_workbench_control_leakage() -> None:
    with pytest.raises(ValidationError):
        FormalRunRequest.model_validate({"experiment_id": "research_b", "run_mode": "paired", "model_target": "qwen"})
    with pytest.raises(ValidationError):
        FormalRunRequest.model_validate({"experiment_id": "a3_v1_3", "run_mode": "paired", "model_profile": "M2"})
    with pytest.raises(ValidationError):
        FormalRunRequest(experiment_id="research_c", run_mode="paired", condition="K1")
    with pytest.raises(ValidationError):
        FormalRunRequest(experiment_id="research_b", run_mode="full_benchmark")


def test_replay_manifest_is_separate_and_frozen_runner_is_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = ROOT / "research/research_b/runner.py"
    before = hashlib.sha256(runner.read_bytes()).hexdigest()
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(ROOT))
    monkeypatch.setenv("LLM_PROVIDER", "siliconflow")
    monkeypatch.setenv("LLM_API_KEY", "offline-test-placeholder")

    store = FormalJobStore(f"sqlite:///{(tmp_path / 'jobs.sqlite3').as_posix()}")
    service = FormalJobService(store)
    status = service.create(FormalRunRequest(experiment_id="research_b", run_mode="paired", case_id="RB-CAND-0001"))
    assert status["replay_output_dir"].startswith("research_b/")
    claimed = store.claim_next("offline-test-worker")
    assert claimed is not None
    output = tmp_path / "disposable-worker" / "replay"
    assert not output.exists()
    output.mkdir(parents=True)
    service._write_manifest(output, claimed["request"], claimed["metadata"], claimed)
    manifest = json.loads((output / "replay_manifest.json").read_text(encoding="utf-8"))
    assert manifest["result_origin"] == "new_replay"
    assert manifest["historical_results_modified"] is False
    assert tmp_path / "disposable-worker" in output.parents
    assert ROOT / "research/research_b/formal_run_v1" not in output.parents
    assert hashlib.sha256(runner.read_bytes()).hexdigest() == before


def test_web_create_does_not_resolve_worker_replay_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(ROOT))
    monkeypatch.setenv("FORMAL_DURABLE_JOBS_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "siliconflow")
    monkeypatch.setenv("LLM_API_KEY", "offline-test-placeholder")
    monkeypatch.delenv("FORMAL_REPLAY_ROOT", raising=False)
    service = FormalJobService(FormalJobStore(f"sqlite:///{(tmp_path / 'jobs.sqlite3').as_posix()}"))
    status = service.create(FormalRunRequest(
        experiment_id="rq1_architecture", run_mode="full_benchmark", confirm_full_benchmark=True,
    ))
    assert status["status"] == "queued"
    assert status["replay_output_dir"].startswith("rq1_architecture/replay-rq1_architecture-")
    assert not Path(status["replay_output_dir"]).is_absolute()
    assert "FORMAL_REPLAY_ROOT" not in (ROOT / "backend/formal_experiments/jobs.py").read_text(encoding="utf-8")


def test_durable_store_reconnects_and_streams_incremental_rows(tmp_path: Path) -> None:
    database = f"sqlite:///{(tmp_path / 'jobs.sqlite3').as_posix()}"
    store = FormalJobStore(database)
    now = 1.0
    job = {
        "run_id": "replay-test", "experiment_id": "rq1_architecture", "run_mode": "full_benchmark",
        "status": "queued", "completed": 0, "total": 200, "current_condition": None,
        "current_case": None, "successful": 0, "failed": 0, "created_at": now,
        "started_at": None, "updated_at": now, "resume_state": "queued",
        "replay_output_dir": "rq1_architecture/replay-test", "persistence": "durable", "error": None,
    }
    store.create(job, {"experiment_id": "rq1_architecture", "run_mode": "full_benchmark"}, {"planned_executions": 200})
    claimed = FormalJobStore(database).claim_next("worker-1")
    assert claimed is not None and claimed["status"] == "running"
    store.replace_executions("replay-test", [
        {"question_id": "Q-001", "condition": "C1", "run_status": "PASS"},
        {"question_id": "Q-001", "condition": "C2", "run_status": "PASS_WITH_RETRY"},
    ])
    assert FormalJobStore(database).executions("replay-test", after=1, include_payload=True) == [{
        "sequence": 2, "case_id": "Q-001", "condition": "C2", "status": "Completed",
        "result": {"question_id": "Q-001", "condition": "C2", "run_status": "PASS_WITH_RETRY"},
    }]


def test_worker_sync_persists_rows_without_running_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = FormalJobStore(f"sqlite:///{(tmp_path / 'jobs.sqlite3').as_posix()}")
    now = 1.0
    output = tmp_path / "worker-disk" / "rq1_architecture" / "replay-test"; output.mkdir(parents=True)
    job = {
        "run_id": "replay-test", "experiment_id": "rq1_architecture", "run_mode": "full_benchmark",
        "status": "running", "completed": 0, "total": 2, "current_condition": None,
        "current_case": None, "successful": 0, "failed": 0, "created_at": now,
        "started_at": now, "updated_at": now, "resume_state": "running",
        "replay_output_dir": "rq1_architecture/replay-test", "persistence": "durable", "error": None,
    }
    store.create(job, {"experiment_id": "rq1_architecture", "run_mode": "full_benchmark"}, {"planned_executions": 2})
    (output / "results.jsonl").write_text(json.dumps({"question_id": "Q-001", "condition": "C1", "run_status": "PASS"}) + "\n", encoding="utf-8")
    rows = FormalReplayWorker(store, worker_id="worker-1")._sync_formal(store.get("replay-test"), output)
    assert len(rows) == 1
    assert store.get("replay-test")["completed"] == 1
    assert store.executions("replay-test")[0]["status"] == "Completed"


def test_expired_worker_lease_is_reclaimed_without_losing_progress(tmp_path: Path) -> None:
    store = FormalJobStore(f"sqlite:///{(tmp_path / 'jobs.sqlite3').as_posix()}")
    now = 1.0
    job = {
        "run_id": "replay-test", "experiment_id": "rq1_architecture", "run_mode": "full_benchmark",
        "status": "running", "completed": 73, "total": 200, "current_condition": "C1",
        "current_case": "Q-037", "successful": 72, "failed": 1, "created_at": now,
        "started_at": now, "updated_at": now, "resume_state": "running",
        "replay_output_dir": "rq1_architecture/replay-test", "persistence": "durable", "error": None,
    }
    store.create(job, {"experiment_id": "rq1_architecture", "run_mode": "full_benchmark"}, {"planned_executions": 200})
    store.update("replay-test", worker_id="dead-worker", lease_until=0)
    reclaimed = FormalJobStore(store.database_url).claim_next("replacement-worker")
    assert reclaimed is not None
    assert reclaimed["completed"] == 73 and reclaimed["successful"] == 72 and reclaimed["failed"] == 1
    assert reclaimed["worker_id"] == "replacement-worker" and reclaimed["status"] == "running"


def test_generated_final_metrics_and_downloads_are_persisted(tmp_path: Path) -> None:
    store = FormalJobStore(f"sqlite:///{(tmp_path / 'jobs.sqlite3').as_posix()}")
    output = tmp_path / "replay"; (output / "final_analysis").mkdir(parents=True)
    (output / "final_analysis" / "objective_metrics.json").write_text(json.dumps({"full_recall": 0.8}), encoding="utf-8")
    (output / "results.jsonl").write_text("{}\n", encoding="utf-8")
    (output / "cache").mkdir(); (output / "cache" / "large.bin").write_bytes(b"cache")
    store.initialize()
    store.store_artifacts("replay-test", output)
    assert store.final_metrics("replay-test") == {"final_analysis/objective_metrics.json": {"full_recall": 0.8}}
    assert {item["name"] for item in store.artifacts("replay-test")} == {"final_analysis/objective_metrics.json", "results.jsonl"}


def test_web_download_uses_database_and_not_worker_filesystem(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    import main

    store = FormalJobStore(f"sqlite:///{(tmp_path / 'jobs.sqlite3').as_posix()}")
    now = 1.0
    job = {
        "run_id": "replay-test", "experiment_id": "rq1_architecture", "run_mode": "full_benchmark",
        "status": "complete", "completed": 200, "total": 200, "current_condition": "C2",
        "current_case": "Q-100", "successful": 200, "failed": 0, "created_at": now,
        "started_at": now, "updated_at": now, "resume_state": "complete",
        "replay_output_dir": "rq1_architecture/replay-test", "persistence": "durable", "error": None,
    }
    store.create(job, {"experiment_id": "rq1_architecture", "run_mode": "full_benchmark"}, {"planned_executions": 200})
    artifact_source = tmp_path / "artifact-source"; artifact_source.mkdir()
    (artifact_source / "objective_metrics.json").write_bytes(b'{"full_recall":0.8}')
    store.store_artifacts("replay-test", artifact_source)
    service = FormalJobService(store)
    monkeypatch.setattr(main, "formal_jobs", service)
    response = TestClient(main.app).get("/api/formal-runs/replay-test/files/objective_metrics.json")
    assert response.status_code == 200
    assert response.content == b'{"full_recall":0.8}'
    assert response.headers["content-type"].startswith("application/json")


def test_rq4_adapter_writes_only_to_replay_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    frozen_dir = ROOT / "research/experiments/rq4_debate_vs_multiagent/formal_run_v1"
    before = file_hashes(frozen_dir)

    class FakeRunner:
        SEED = 20260824
        FORMAL = RUNTIME_PATH = LOCK_PATH = STATE_PATH = None

        @staticmethod
        def jsonl(path): return worker._read_jsonl(path)

        @staticmethod
        def execution_order(question_ids):
            return [
                {"execution_id": f"{question_ids[0]}-{condition}", "question_id": question_ids[0], "condition": condition}
                for condition in ("C2", "C4")
            ]

        @staticmethod
        def utcnow(): return "2026-09-11T00:00:00Z"

        @staticmethod
        def _runtime(records, entry, started): return {"completed": len(records), "entry": entry, "started": started}

        @staticmethod
        def request_execution(item, entry, runtime, *, api_url):
            return {**entry, "run_status": "PASS", "provider_attempts": [], "debate": {} if entry["condition"] == "C4" else None}

        @staticmethod
        def validate_results(order, records): assert len(order) == len(records) == 2

        @staticmethod
        def objective_and_semantic_export(records): raise AssertionError("not used for paired replay")

    @contextmanager
    def fake_backend(root, output):
        yield "http://127.0.0.1:1/api/research/run"

    monkeypatch.setattr(worker, "_require_frozen_qwen_provider", lambda: None)
    monkeypatch.setattr(worker, "_validate_rq4_assets", lambda root: {})
    monkeypatch.setattr(worker, "_load", lambda path, name: FakeRunner)
    monkeypatch.setattr(worker, "_frozen_backend", fake_backend)
    output = tmp_path / "replay"
    worker._run_rq4(ROOT, output, "paired", None, None)
    assert len(worker._read_jsonl(output / "results.jsonl")) == 2
    assert (output / "replay_isolation.json").is_file()
    assert FakeRunner.FORMAL == output
    assert file_hashes(frozen_dir) == before


def test_frontend_guided_mode_is_one_click_and_custom_workbench_is_preserved() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "research-app.js").read_text(encoding="utf-8")
    assert "Guided Paper Experiments" in html and "Custom Research Workbench" in html
    assert 'id="consensus-form" class="custom-research-workbench"' in html
    assert html.count('id="run-paper-experiment"') == 1
    assert all(value not in html for value in ('id="formal-case-id"', 'id="run-formal-one"', 'id="run-formal-paired"', 'id="run-formal-full"', 'id="formal-capability-statuses"'))
    assert "Run Paper Experiment" in html
    assert "run_mode: 'full_benchmark'" in js and "confirm_full_benchmark: true" in js
    assert "setPaperWorkbenchMode('guided')" in js
    assert "/api/formal-runs" in js and "/api/custom-runs" in js
    formal_run_source = js[js.index("async function startFormalRun"):js.index("function showMessage")]
    assert "model_target" not in formal_run_source and "model_profile" not in formal_run_source
    assert "Historical paper result" in (ROOT / "backend/formal_experiments/registry.py").read_text(encoding="utf-8")
    assert "New replay result" in html


def test_job_api_exposes_registry_and_rejects_control_leakage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from main import app
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(tmp_path))
    client = TestClient(app)
    registry = client.get("/api/formal-experiments")
    assert registry.status_code == 200 and len(registry.json()) == 6
    response = client.post("/api/formal-runs", json={
        "experiment_id": "research_b", "run_mode": "paired", "model_target": "qwen",
    })
    assert response.status_code == 422


def custom_request(*questions: str) -> CustomRunRequest:
    return CustomRunRequest(
        questions=list(questions), condition_id="C2", retrieval_strategy="R2",
        specialist_model_targets=["qwen", "glm", "deepseek"], consensus_model_target="qwen",
        active_agents=["syndrome", "herbal"], active_judges=["evidence", "safety"],
    )


def test_control_plane_queues_and_wakes_without_loading_corpus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    import main

    store = FormalJobStore(f"sqlite:///{(tmp_path / 'control.sqlite3').as_posix()}")
    monkeypatch.setattr(main, "formal_jobs", FormalJobService(store))
    monkeypatch.setattr(main, "custom_jobs", CustomJobService(store))
    monkeypatch.setattr(main, "corpus_stats", lambda: (_ for _ in ()).throw(AssertionError("control plane loaded corpus")))
    monkeypatch.setenv("RENDER_API_CONTROL_PLANE_ONLY", "true")
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(ROOT))
    monkeypatch.setenv("FORMAL_DATABASE_URL", "postgresql://configured-for-registry")
    monkeypatch.setenv("FORMAL_WORKER_PUBLIC_URL", "https://worker.invalid")
    wakes = []

    async def fake_wake() -> bool:
        wakes.append(True)
        return True

    monkeypatch.setattr(main, "_wake_worker", fake_wake)
    with TestClient(main.app) as client:
        health = client.get("/health")
        assert health.status_code == 200 and health.json()["runtime_profile"] == "cloud_control_plane"
        queued = client.post("/api/custom-runs", json=custom_request("Question one?").model_dump(mode="json"))
        assert queued.status_code == 202 and queued.json()["status"] == "queued"
        assert client.post("/api/research/run", json={"question": "Must not execute here"}).status_code == 503
    assert wakes == [True]


def test_checkpoint_round_trip_restores_partial_formal_state(tmp_path: Path) -> None:
    database = f"sqlite:///{(tmp_path / 'checkpoint.sqlite3').as_posix()}"
    store = FormalJobStore(database)
    source = tmp_path / "source"; source.mkdir()
    rows = [
        {"case_id": f"RB-CAND-{index:04d}", "condition": "J1" if index % 2 else "J2", "usable": True}
        for index in range(1, 127)
    ]
    (source / "results.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    (source / "run_progress.json").write_text(json.dumps({"completed": 126, "planned": 480}), encoding="utf-8")
    assert store.store_checkpoints("replay-partial", source) == 2
    restored = tmp_path / "fresh-worker"; restored.mkdir()
    assert FormalJobStore(database).restore_checkpoints("replay-partial", restored) == 2
    assert FormalJobService._result_rows(restored) == rows
    assert not source.samefile(restored)


def test_custom_worker_resumes_without_repeating_persisted_questions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import orchestration.workbench as workbench_module

    store = FormalJobStore(f"sqlite:///{(tmp_path / 'custom.sqlite3').as_posix()}")
    service = CustomJobService(store)
    status = service.create(custom_request("First question?", "Second question?", "Third question?"))
    store.upsert_execution(status["run_id"], 1, {"question_id": "CUSTOM-001", "condition_id": "C2", "final_answer": "persisted"})
    calls = []

    class Result:
        def __init__(self, question: str) -> None: self.question = question
        def model_dump(self, mode: str) -> dict: return {"condition_id": "C2", "final_answer": self.question}

    class FakeWorkbench:
        def __init__(self, **kwargs): assert kwargs == {"cache_results": False}
        async def run(self, request):
            calls.append(request.question)
            return Result(request.question)

    monkeypatch.setattr(workbench_module, "ResearchWorkbench", FakeWorkbench)
    worker_service = FormalReplayWorker(store, worker_id="replacement-worker")
    assert worker_service.run_once() is True
    assert calls == ["Second question?", "Third question?"]
    final = service.get(status["run_id"])
    assert final["status"] == "complete" and final["completed"] == 3
    assert len(store.executions(status["run_id"])) == 3


def test_worker_web_health_and_wake_are_lightweight(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    import formal_experiments.worker_web as worker_web

    store = FormalJobStore(f"sqlite:///{(tmp_path / 'worker-web.sqlite3').as_posix()}")
    monkeypatch.setattr(worker_web, "store", store)
    monkeypatch.setattr(worker_web, "worker", FormalReplayWorker(store, worker_id="web-worker"))
    monkeypatch.setenv("FORMAL_WORKER_WAKE_TOKEN", "offline-token")
    with TestClient(worker_web.app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["single_concurrency"] is True
        assert client.post("/wake").status_code == 401
        assert client.post("/wake", headers={"X-Worker-Wake-Token": "offline-token"}).status_code == 202


def test_worker_loop_executes_only_one_claimed_job_at_a_time(tmp_path: Path) -> None:
    store = FormalJobStore(f"sqlite:///{(tmp_path / 'single-worker.sqlite3').as_posix()}")
    service = CustomJobService(store)
    first = service.create(custom_request("First queued question?"))
    second = service.create(custom_request("Second queued question?"))
    active = 0
    peak = 0

    class RecordingWorker(FormalReplayWorker):
        def run_job(self, job):
            nonlocal active, peak
            active += 1; peak = max(peak, active)
            self.store.update(job["run_id"], status="complete", completed=1, successful=1, current_stage="complete")
            active -= 1

    assert RecordingWorker(store, worker_id="single").run_until_idle() == 2
    assert peak == 1
    assert service.get(first["run_id"])["status"] == "complete"
    assert service.get(second["run_id"])["status"] == "complete"


def test_retention_deletes_only_old_generated_database_runs(tmp_path: Path) -> None:
    store = FormalJobStore(f"sqlite:///{(tmp_path / 'retention.sqlite3').as_posix()}")
    now = 1.0
    job = {
        "run_id": "old-new-replay", "experiment_id": "rq1_architecture", "run_mode": "full_benchmark",
        "status": "complete", "completed": 200, "total": 200, "current_condition": "C2",
        "current_case": "Q-100", "successful": 200, "failed": 0, "created_at": now,
        "started_at": now, "updated_at": now, "resume_state": "complete",
        "replay_output_dir": "disposable", "persistence": "database", "error": None,
    }
    store.create(job, {}, {})
    with store.connect() as connection:
        connection.cursor().execute("UPDATE formal_jobs SET updated_at = 0 WHERE run_id = 'old-new-replay'")
    assert store.cleanup_old_replays(1) == 1
    with pytest.raises(KeyError): store.get("old-new-replay")


def test_stop_queued_guided_run_is_immediate_and_durable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(ROOT))
    monkeypatch.setenv("FORMAL_DURABLE_JOBS_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "siliconflow")
    monkeypatch.setenv("LLM_API_KEY", "offline-test-placeholder")
    database = f"sqlite:///{(tmp_path / 'queued-stop.sqlite3').as_posix()}"
    service = FormalJobService(FormalJobStore(database))
    created = service.create(FormalRunRequest(
        experiment_id="rq1_architecture", run_mode="full_benchmark", confirm_full_benchmark=True,
    ))
    stopped = service.stop(created["run_id"])
    assert stopped["status"] == "stopped" and stopped["stop_requested"] is True
    assert stopped["completed"] == 0 and stopped["total"] == 200
    assert FormalJobStore(database).get(created["run_id"])["status"] == "stopped"
    assert {item["name"] for item in service.results(created["run_id"])["downloads"]} >= {
        "partial_report.md", "partial_results.csv", "partial_results.json",
    }


def test_custom_stop_waits_for_active_atomic_execution_then_preserves_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import orchestration.workbench as workbench_module

    database = f"sqlite:///{(tmp_path / 'running-stop.sqlite3').as_posix()}"
    store = FormalJobStore(database)
    service = CustomJobService(store)
    created = service.create(custom_request("First question?", "Second question?", "Third question?"))
    calls: list[str] = []

    class Result:
        def __init__(self, question: str) -> None: self.question = question
        def model_dump(self, mode: str) -> dict: return {"condition_id": "C2", "final_answer": self.question}

    class FakeWorkbench:
        def __init__(self, **kwargs): assert kwargs == {"cache_results": False}
        async def run(self, request):
            calls.append(request.question)
            if len(calls) == 2:
                requested = service.stop(created["run_id"])
                assert requested["status"] == "stop_requested"
            return Result(request.question)

    monkeypatch.setattr(workbench_module, "ResearchWorkbench", FakeWorkbench)
    assert FormalReplayWorker(store, worker_id="stop-worker").run_once() is True
    final = CustomJobService(FormalJobStore(database)).get(created["run_id"])
    assert calls == ["First question?", "Second question?"]
    assert final["status"] == "stopped" and final["completed"] == 2 and final["total"] == 3
    persisted = FormalJobStore(database).get(created["run_id"])
    assert persisted["worker_id"] is None and persisted["lease_until"] is None
    assert len(FormalJobStore(database).executions(created["run_id"], include_payload=True)) == 2


def test_partial_report_exports_completed_rows_only(tmp_path: Path) -> None:
    store = FormalJobStore(f"sqlite:///{(tmp_path / 'partial-report.sqlite3').as_posix()}")
    service = CustomJobService(store)
    created = service.create(custom_request("First question?", "Second question?"))
    store.upsert_execution(created["run_id"], 1, {
        "question_id": "CUSTOM-001", "condition_id": "C2", "final_answer": "completed",
    })
    stopped = service.stop(created["run_id"])
    assert stopped["status"] == "stopped"
    _, json_content = service.file(created["run_id"], "partial_results.json")
    report = json.loads(json_content)
    assert report["completed_execution_count"] == 1
    assert report["original_scheduled_execution_count"] == 2
    assert len(report["completed_rows"]) == 1
    assert report["warning"] == "Partial replay — not directly comparable to the complete paper result."
    csv_type, csv_content = service.file(created["run_id"], "partial_results.csv")
    markdown_type, markdown_content = service.file(created["run_id"], "partial_report.md")
    assert csv_type == "text/csv" and b"CUSTOM-001" in csv_content
    assert markdown_type == "text/markdown" and b"Completed: 1 / 2" in markdown_content


def test_stop_requested_job_is_recovered_after_worker_restart(tmp_path: Path) -> None:
    database = f"sqlite:///{(tmp_path / 'restart-stop.sqlite3').as_posix()}"
    store = FormalJobStore(database)
    service = CustomJobService(store)
    created = service.create(custom_request("Restart-safe question?"))
    claimed = store.claim_next("crashed-worker", lease_seconds=30)
    assert claimed and claimed["status"] == "running"
    requested = service.stop(created["run_id"])
    assert requested["status"] == "stop_requested"
    store.update(created["run_id"], lease_until=0)
    replacement = FormalReplayWorker(FormalJobStore(database), worker_id="replacement-worker")
    assert replacement.run_once() is True
    assert CustomJobService(FormalJobStore(database)).get(created["run_id"])["status"] == "stopped"


def test_guided_and_custom_stop_endpoints(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    import main

    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(ROOT))
    monkeypatch.setenv("FORMAL_DURABLE_JOBS_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "siliconflow")
    monkeypatch.setenv("LLM_API_KEY", "offline-test-placeholder")
    store = FormalJobStore(f"sqlite:///{(tmp_path / 'stop-api.sqlite3').as_posix()}")
    monkeypatch.setattr(main, "formal_jobs", FormalJobService(store))
    monkeypatch.setattr(main, "custom_jobs", CustomJobService(store))
    formal = main.formal_jobs.create(FormalRunRequest(
        experiment_id="rq1_architecture", run_mode="full_benchmark", confirm_full_benchmark=True,
    ))
    custom = main.custom_jobs.create(custom_request("API stop question?"))
    with TestClient(main.app) as client:
        formal_response = client.post(f"/api/formal-runs/{formal['run_id']}/stop")
        custom_response = client.post(f"/api/custom-runs/{custom['run_id']}/stop")
    assert formal_response.status_code == 202 and formal_response.json()["status"] == "stopped"
    assert custom_response.status_code == 202 and custom_response.json()["status"] == "stopped"


def test_formal_cooperative_iterable_stops_only_between_atomic_items() -> None:
    requested = False
    started: list[int] = []
    for value in worker._CooperativeIterable([1, 2, 3], lambda: requested):
        started.append(value)
        if value == 2:
            requested = True
    assert started == [1, 2]


def test_formal_worker_finishes_active_atomic_row_before_stopping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import formal_experiments.worker as worker_module

    database = f"sqlite:///{(tmp_path / 'formal-running-stop.sqlite3').as_posix()}"
    store = FormalJobStore(database)
    now = 1.0
    job = {
        "run_id": "replay-safe-boundary", "experiment_id": "rq1_architecture", "run_mode": "full_benchmark",
        "status": "queued", "completed": 0, "total": 200, "current_condition": None,
        "current_case": None, "successful": 0, "failed": 0, "created_at": now,
        "started_at": None, "updated_at": now, "resume_state": "queued",
        "replay_output_dir": "rq1_architecture/replay-safe-boundary", "persistence": "durable", "error": None,
    }
    store.create(job, {"experiment_id": "rq1_architecture", "run_mode": "full_benchmark"}, {
        "experiment_id": "rq1_architecture", "runner": "frozen-runner", "dataset_path": "frozen.jsonl",
        "conditions": [{"id": "C1"}, {"id": "C2"}], "models": ["Qwen/Qwen3-8B"],
        "planned_executions": 200, "dataset_size": 100,
    })

    def fake_replay(*, output: Path, should_stop, **kwargs) -> bool:
        FormalJobService(store).stop("replay-safe-boundary")
        assert should_stop() is True
        output.mkdir(parents=True, exist_ok=True)
        (output / "results.jsonl").write_text(json.dumps({
            "question_id": "Q-001", "condition": "C1", "run_status": "PASS",
        }) + "\n", encoding="utf-8")
        return True

    monkeypatch.setattr(worker_module, "run_replay", fake_replay)
    assert FormalReplayWorker(store, worker_id="formal-stop-worker", poll_seconds=0.1).run_once() is True
    final = FormalJobService(FormalJobStore(database)).get("replay-safe-boundary")
    assert final["status"] == "stopped" and final["completed"] == 1 and final["total"] == 200
    assert len(FormalJobStore(database).executions("replay-safe-boundary")) == 1
    assert {item["name"] for item in store.artifacts("replay-safe-boundary")} >= {
        "partial_report.md", "partial_results.csv", "partial_results.json",
    }
