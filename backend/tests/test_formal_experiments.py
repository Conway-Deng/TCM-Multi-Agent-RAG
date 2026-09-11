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
from formal_experiments.jobs import FormalJobService
from formal_experiments.registry import frozen_root, public_registry, verify_deployment_integrity
from formal_experiments.schemas import FormalRunRequest


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


def test_relative_roots_are_resolved_from_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", ".")
    monkeypatch.setenv("FORMAL_REPLAY_ROOT", "research/replays")
    assert frozen_root() == ROOT.resolve()
    assert FormalJobService().replay_root == (ROOT / "research/replays").resolve()


def test_replay_root_cannot_target_deployed_or_frozen_directories(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORMAL_EXPERIMENT_ROOT", str(ROOT))
    monkeypatch.setenv("FORMAL_REPLAY_ROOT", "research/experiments/rq4_debate_vs_multiagent/formal_run_v1")
    with pytest.raises(ValueError, match="must not target"):
        _ = FormalJobService().replay_root


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

    class DormantThread:
        def __init__(self, *_, **__): pass
        def start(self): pass

    monkeypatch.setattr("formal_experiments.jobs.threading.Thread", DormantThread)
    monkeypatch.setattr(FormalJobService, "replay_root", property(lambda self: tmp_path / "replays"))
    service = FormalJobService()
    status = service.create(FormalRunRequest(experiment_id="research_b", run_mode="paired", case_id="RB-CAND-0001"))
    output = Path(status["replay_output_dir"])
    manifest = json.loads((output / "replay_manifest.json").read_text(encoding="utf-8"))
    assert manifest["result_origin"] == "new_replay"
    assert manifest["historical_results_modified"] is False
    assert tmp_path / "replays" in output.parents
    assert ROOT / "research/research_b/formal_run_v1" not in output.parents
    assert hashlib.sha256(runner.read_bytes()).hexdigest() == before


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


def test_frontend_capabilities_and_custom_workbench_are_preserved() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "research-app.js").read_text(encoding="utf-8")
    assert "Guided Paper Experiments" in html and "Custom Research Workbench" in html
    assert 'id="consensus-form" class="custom-research-workbench"' in html
    assert 'id="formal-capability-statuses"' in html
    assert "READY ONLINE" in js and "LOCAL FULL REPLAY" in js and "UNAVAILABLE" in js
    assert "selectedFormalExperiment.run_capabilities" in js
    assert "setPaperWorkbenchMode('guided')" in js
    assert "/api/formal-runs" in js and "/api/research/run" in js
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
