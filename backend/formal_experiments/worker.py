"""Isolated replay worker.

This module deliberately imports the frozen runners from FORMAL_EXPERIMENT_ROOT
at execution time. It never writes beneath that root's historical result
directories; every output path is supplied by the replay job service.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


def _load(path: Path, name: str):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load frozen runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _append(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def _status(output: Path, **updates: Any) -> None:
    path = output / "worker_status.json"
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    _write(path, {**current, **updates, "updated_at": time.time()})


def _conditions(mode: str, selected: str | None, valid: list[str]) -> list[str]:
    if mode == "paired":
        return valid
    if mode == "one_case":
        return [selected or valid[0]]
    return valid


def _require_frozen_qwen_provider() -> None:
    if os.getenv("LLM_PROVIDER", "").strip().casefold() != "siliconflow":
        raise RuntimeError("Frozen protocol requires the configured SiliconFlow provider")
    if not os.getenv("LLM_API_KEY", "").strip():
        raise RuntimeError("Frozen protocol requires the existing LLM_API_KEY")
    os.environ["LLM_MODEL"] = "Qwen/Qwen3-8B"


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def _frozen_backend(root: Path, output: Path):
    """Run the hash-locked RQ4-era backend snapshot, never the current API."""
    snapshot = root / "research/formal_runtime/rq4_backend"
    port = _free_port(); api_url = f"http://127.0.0.1:{port}/api/research/run"
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(snapshot), "TCM_CORPUS_MODE": "required",
        "TCM_CORPUS_PATH": str(root / "research/corpus/tcm_v1/chunks.jsonl"),
        "RESEARCH_REAL_LLM_ENABLED": "true", "LLM_MODEL": "Qwen/Qwen3-8B",
    })
    log_dir = output / "logs"; log_dir.mkdir(parents=True, exist_ok=True)
    stdout = (log_dir / "frozen_backend.stdout.log").open("ab")
    stderr = (log_dir / "frozen_backend.stderr.log").open("ab")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--app-dir", str(snapshot), "--host", "127.0.0.1", "--port", str(port)],
        cwd=root, env=env, stdout=stdout, stderr=stderr, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    health = None
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                    health = json.loads(response.read().decode("utf-8"))
                break
            except Exception:
                if process.poll() is not None: break
                time.sleep(1)
        protocol = json.loads((root / "research/experiments/rq4_debate_vs_multiagent/protocol/protocol_manifest.json").read_text(encoding="utf-8"))
        valid = bool(
            health and health.get("provider_ready") is True and health.get("llm_execution_enabled") is True
            and health.get("mock_mode") is False and health.get("corpus_chunk_count") == 4461
            and health.get("corpus_mode") == "required"
            and health.get("workbench_sha256") == protocol["workbench_runtime_sha256_after_amendment"]
            and health.get("c4_implementation_sha256") == protocol["c4_implementation_sha256"]
        )
        if not valid: raise RuntimeError("Frozen backend snapshot failed its runtime/hash preflight")
        yield api_url
    finally:
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill()
        stdout.close(); stderr.close()


def _run_research_b(root: Path, output: Path, mode: str, condition: str | None, case_id: str | None) -> None:
    _require_frozen_qwen_provider()
    runner = _load(root / "research/research_b/runner.py", "frozen_research_b_runner")
    config = runner.config(root / "research/research_b/config/research_b_judge.json")
    benchmark, cases, _ = runner.validate_frozen(config)
    config["output_dir"] = str(output)
    if mode == "full_benchmark":
        runner.run(config, True)
        return
    case = next((item for item in cases if item["case_id"] == case_id), cases[0])
    chosen = _conditions(mode, condition, ["J1", "J2"])
    for index, current in enumerate(chosen, 1):
        _status(output, completed=index - 1, total=len(chosen), current_case=case["case_id"], current_condition=current)
        prediction = runner.request_prediction(config, case, current)
        row = {
            "result_origin": "new_replay", "case_id": case["case_id"], "condition": current,
            "input": {"claim": case["claim"], "evidence": case["evidence"] if current == "J2" else None},
            "reference_label": case["reference_label"], "raw_output": prediction.get("attempts", [{}])[-1].get("raw_output"),
            **{key: value for key, value in prediction.items() if key != "attempts"},
            "provider_attempts": prediction.get("attempts", []),
        }
        _append(output / "results.jsonl", row)
        _status(output, completed=index, successful=index - int(not row.get("usable")), failed=int(not row.get("usable")))
    _write(output / "manifest.json", {"result_origin": "new_replay", "runner": str(benchmark), "conditions": chosen, "case_id": case["case_id"]})


def _enrich_research_c(root: Path, cases: list[dict[str, Any]]) -> None:
    excerpt_ids: dict[str, str] = {}
    corpus = root / "research/corpus/tcm_v1/chunks.jsonl"
    if corpus.exists():
        for item in _read_jsonl(corpus):
            excerpt_ids[item.get("text", "").strip()] = item.get("chunk_id", "")
    for case in cases:
        case.setdefault("source_a_id", excerpt_ids.get(case.get("source_a_excerpt", "").strip(), "unknown-source-a"))
        case.setdefault("source_b_id", excerpt_ids.get(case.get("source_b_excerpt", "").strip(), "unknown-source-b"))


def _run_research_c(root: Path, output: Path, mode: str, condition: str | None, case_id: str | None) -> None:
    _require_frozen_qwen_provider()
    runner = _load(root / "research/research_c/runner.py", "frozen_research_c_runner")
    config = runner.config(root / "research/research_c/config/research_c_conflict.json")
    benchmark, cases, freeze = runner.validate_frozen(config)
    config["output_dir"] = str(output)
    if mode == "full_benchmark":
        runner.execute_formal(config, benchmark, cases, freeze)
        return
    _enrich_research_c(root, cases)
    case = next((item for item in cases if item["case_id"] == case_id), cases[0])
    chosen = _conditions(mode, condition, ["K1", "K2"])
    successful = failed = 0
    for index, current in enumerate(chosen, 1):
        _status(output, completed=index - 1, total=len(chosen), current_case=case["case_id"], current_condition=current)
        prediction = runner.request_prediction(config, case, current)
        usable = bool(prediction.get("usable")); successful += int(usable); failed += int(not usable)
        row = {
            "result_origin": "new_replay", "case_id": case["case_id"], "condition": current,
            "input": {"question": case["question"], "source_a": case["source_a_excerpt"], "source_b": case["source_b_excerpt"]},
            "reference_label": case["reference_label"], "raw_output": prediction.get("attempts", [{}])[-1].get("raw_output"),
            **{key: value for key, value in prediction.items() if key != "attempts"}, "provider_attempts": prediction.get("attempts", []),
        }
        _append(output / "results.jsonl", row)
        _status(output, completed=index, successful=successful, failed=failed)
    _write(output / "manifest.json", {"result_origin": "new_replay", "runner": str(benchmark), "conditions": chosen, "case_id": case["case_id"]})


def _run_a3(root: Path, output: Path, mode: str, condition: str | None, case_id: str | None) -> None:
    _require_frozen_qwen_provider()
    runner = _load(root / "research/multi_model_debate/formal_runner.py", "frozen_a3_v1_3_runner")
    # Redirect all module-global analysis and execution paths before any run.
    formal_output = output / "formal"
    runner.FORMAL = formal_output
    if (formal_output / "formal_run_manifest.json").exists():
        runner.validate_resume_checkpoint(formal_output)
    else:
        runner.prepare_clean_restart(formal_output)
    api_key = runner.load_api_key()
    execution = runner.FormalExecutionRunner(api_key, formal_dir=formal_output)
    if mode != "full_benchmark":
        first_qid = case_id or execution.execution_order[0]["question_id"]
        allowed = set(_conditions(mode, condition, ["M1", "M2"]))
        execution.execution_order = [item for item in execution.execution_order if item["question_id"] == first_qid and item["condition"] in allowed]
        if len(execution.execution_order) != len(allowed):
            raise RuntimeError(f"Frozen A3 case not found: {first_qid}")
    asyncio.run(execution.run())
    if mode == "full_benchmark":
        objective, process = runner.compute_objective_and_process_metrics()
        _write(formal_output / "objective_metrics.json", objective)
        _write(formal_output / "process_metrics.json", process)
        runner.generate_blinded_review_packet()
        runner.write_semantic_review_instructions()
        _write(formal_output / "formal_validation.json", runner.validate_formal_execution())


def _run_retrieval(root: Path, output: Path) -> None:
    _require_frozen_qwen_provider()
    os.environ["TCM_CORPUS_MODE"] = "required"
    os.environ["TCM_CORPUS_PATH"] = str(root / "research/corpus/tcm_v1/chunks.jsonl")
    warmer = _load(root / "research/retrieval_ablation/warm_formal_cache.py", "frozen_retrieval_cache_warmer")
    cache_dir = output / "cache"
    warmer.warm(cache_dir)
    stage1 = _load(root / "research/retrieval_ablation/runner.py", "frozen_retrieval_stage1")
    stage1.STUDY_ROOT = output
    os.environ["RETRIEVAL_ABLATION_EXECUTION"] = "FORMAL_STAGE1_APPROVED"
    stage1_out = output / "stage1"
    asyncio.run(stage1.execute_stage1(stage1_out))
    stage2 = _load(root / "research/retrieval_ablation/stage2_runner.py", "frozen_retrieval_stage2")
    stage2.STAGE1 = stage1_out
    stage2.OUT = output / "stage2"
    asyncio.run(stage2.main())


def _run_rq1(root: Path, output: Path, mode: str, condition: str | None, case_id: str | None) -> None:
    _require_frozen_qwen_provider()
    runner = _load(root / "research/experiment_pipeline/rq1_confirmatory.py", "frozen_rq1_runner")
    config = runner.load(root / "research/experiments/rq1_c1_vs_c2/confirmatory_protocol/rq1_confirmatory.yaml")
    config["output_dir"] = str(output)
    benchmark = runner.jsonl(root / config["benchmark_path"])
    if len(benchmark) != 100 or runner.sha(root / config["benchmark_path"]) != config["benchmark_sha256"]:
        raise RuntimeError("Frozen RQ1 benchmark integrity check failed")
    planned = runner.order(config, benchmark)
    selected_case = case_id or benchmark[0]["question_id"]
    allowed = set(_conditions(mode, condition, ["C1", "C2"])) if mode != "full_benchmark" else {"C1", "C2"}
    entries = [entry for entry in planned if (mode == "full_benchmark" or entry["question_id"] == selected_case) and entry["condition"] in allowed]
    expected = 200 if mode == "full_benchmark" else len(allowed)
    if len(entries) != expected: raise RuntimeError(f"Frozen RQ1 case not found: {selected_case}")
    by_id = {item["question_id"]: item for item in benchmark}
    results_path = output / "results.jsonl"; existing = _read_jsonl(results_path) if results_path.exists() else []
    done = {(row["question_id"], row["condition"]) for row in existing}
    _write(output / "execution_order.json", {"seed": config["random_seed"], "order": entries})
    with _frozen_backend(root, output) as api_url:
        config["api_url"] = api_url
        for entry in entries:
            if (entry["question_id"], entry["condition"]) in done: continue
            _status(output, completed=len(done), total=expected, current_case=entry["question_id"], current_condition=entry["condition"])
            row = runner.request_one(config, by_id[entry["question_id"]], entry)
            row["result_origin"] = "new_replay"; _append(results_path, row); done.add((entry["question_id"], entry["condition"]))
    rows = _read_jsonl(results_path)
    _status(output, completed=len(rows), successful=sum(row.get("run_status") in {"PASS", "PASS_WITH_RETRY"} for row in rows), failed=sum(row.get("run_status") not in {"PASS", "PASS_WITH_RETRY"} for row in rows))
    _write(output / "manifest.json", {"result_origin": "new_replay", "runner": "research/experiment_pipeline/rq1_confirmatory.py", "case_id": None if mode == "full_benchmark" else selected_case, "conditions": sorted(allowed), "historical_results_modified": False})


def _validate_rq4_assets(root: Path) -> dict[str, Any]:
    protocol_dir = root / "research/experiments/rq4_debate_vs_multiagent/protocol"
    manifest = json.loads((protocol_dir / "protocol_manifest.json").read_text(encoding="utf-8"))
    benchmark = root / "research/benchmarks/tcm_gold_rq4_v1/benchmark_rq4_v1_frozen.jsonl"
    corpus = root / "research/corpus/tcm_v1/chunks.jsonl"
    snapshot = root / "research/formal_runtime/rq4_backend/orchestration"
    checks = {
        "protocol": _sha256(protocol_dir / "protocol.md") == manifest["protocol_sha256"],
        "config": _sha256(protocol_dir / "rq4_config.json") == manifest["config_sha256"],
        "benchmark": _sha256(benchmark) == manifest["benchmark_sha256"],
        "corpus": _sha256(corpus) == manifest["corpus_sha256"],
        "workbench": _sha256(snapshot / "workbench.py") == manifest["workbench_runtime_sha256_after_amendment"],
        "c4": _sha256(snapshot / "genuine_debate.py") == manifest["c4_implementation_sha256"],
    }
    if not all(checks.values()): raise RuntimeError("RQ4 frozen protocol or backend snapshot hash mismatch")
    return manifest


def _run_rq4(root: Path, output: Path, mode: str, condition: str | None, case_id: str | None) -> None:
    _require_frozen_qwen_provider(); _validate_rq4_assets(root)
    runner = _load(root / "research/experiment_pipeline/rq4_platform.py", "frozen_rq4_runner")
    benchmark_path = root / "research/benchmarks/tcm_gold_rq4_v1/benchmark_rq4_v1_frozen.jsonl"
    benchmark_rows = runner.jsonl(benchmark_path); benchmark = {item["question_id"]: item for item in benchmark_rows}
    full_order = runner.execution_order([item["question_id"] for item in benchmark_rows])
    selected_case = case_id or benchmark_rows[0]["question_id"]
    allowed = set(_conditions(mode, condition, ["C2", "C4"])) if mode != "full_benchmark" else {"C2", "C4"}
    order = [entry for entry in full_order if (mode == "full_benchmark" or entry["question_id"] == selected_case) and entry["condition"] in allowed]
    expected = 200 if mode == "full_benchmark" else len(allowed)
    if len(order) != expected: raise RuntimeError(f"Frozen RQ4 case not found: {selected_case}")
    # Patch all historical module globals to replay-only locations before any write.
    runner.FORMAL = output; runner.RUNTIME_PATH = output / "runtime/runtime_state.json"; runner.LOCK_PATH = output / "runtime/rq4_runner.pid.json"; runner.STATE_PATH = output / "runtime/rq4_state.json"
    _write(output / "execution_order.json", {"seed": runner.SEED, "counterbalanced": True, "paired": True, "order": order})
    historical_manifest = json.loads((root / "research/experiments/rq4_debate_vs_multiagent/formal_run_v1/formal_execution_manifest.json").read_text(encoding="utf-8"))
    historical_manifest.update({"result_origin": "new_replay", "execution_order": order, "questions": 100 if mode == "full_benchmark" else 1, "executions": expected})
    _write(output / "formal_execution_manifest.json", historical_manifest)
    results_path = output / "results.jsonl"; records = _read_jsonl(results_path) if results_path.exists() else []
    completed = {row["execution_id"] for row in records}
    with _frozen_backend(root, output) as api_url:
        for entry in order:
            if entry["execution_id"] in completed: continue
            runtime = runner._runtime(records, entry, runner.utcnow()); _write(runner.RUNTIME_PATH, runtime)
            row = runner.request_execution(benchmark[entry["question_id"]], entry, runtime, api_url=api_url)
            row["result_origin"] = "new_replay"; _append(results_path, row)
            for attempt in row["provider_attempts"]: _append(output / "provider_attempts.jsonl", {"execution_id": entry["execution_id"], **attempt})
            if entry["condition"] == "C4": _append(output / "debate_traces.jsonl", {"execution_id": entry["execution_id"], "question_id": entry["question_id"], **row["debate"]})
            records.append(row); completed.add(entry["execution_id"])
            _status(output, completed=len(records), total=expected, current_case=entry["question_id"], current_condition=entry["condition"], successful=sum(item["run_status"] in {"PASS", "PASS_WITH_RETRY"} for item in records), failed=sum(item["run_status"].startswith("FAIL") for item in records))
    runner.validate_results(order, records)
    if mode == "full_benchmark": runner.objective_and_semantic_export(records)
    _write(output / "replay_isolation.json", {"result_origin": "new_replay", "historical_results_modified": False, "output_root": str(output), "conditions": sorted(allowed)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--run-mode", required=True)
    parser.add_argument("--condition")
    parser.add_argument("--case-id")
    parser.add_argument("--frozen-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from formal_experiments.registry import validate_replay_path, verify_deployment_integrity
    integrity_ok, integrity_errors = verify_deployment_integrity(args.frozen_root.resolve(), args.experiment)
    if not integrity_ok:
        raise RuntimeError("Formal asset integrity verification failed: " + ", ".join(integrity_errors))
    output = validate_replay_path(args.frozen_root, args.output); output.mkdir(parents=True, exist_ok=True)
    _status(output, status="running", completed=0, total=0, successful=0, failed=0)
    actions = {
        "retrieval_ablation": lambda: _run_retrieval(args.frozen_root, output),
        "rq1_architecture": lambda: _run_rq1(args.frozen_root, output, args.run_mode, args.condition, args.case_id),
        "rq4_debate": lambda: _run_rq4(args.frozen_root, output, args.run_mode, args.condition, args.case_id),
        "research_b": lambda: _run_research_b(args.frozen_root, output, args.run_mode, args.condition, args.case_id),
        "research_c": lambda: _run_research_c(args.frozen_root, output, args.run_mode, args.condition, args.case_id),
        "a3_v1_3": lambda: _run_a3(args.frozen_root, output, args.run_mode, args.condition, args.case_id),
    }
    if args.experiment not in actions:
        raise RuntimeError("No replay-safe adapter is available for this experiment")
    actions[args.experiment]()
    _status(output, status="complete", resume_state="complete")


if __name__ == "__main__":
    main()
