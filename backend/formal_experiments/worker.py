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
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator


StopPredicate = Callable[[], bool] | None


def _stop_requested(predicate: StopPredicate) -> bool:
    return bool(predicate and predicate())


class _CooperativeIterable:
    """Stop yielding before the next atomic execution, never during one."""

    def __init__(self, values: Iterable[Any], should_stop: StopPredicate) -> None:
        self.values = values
        self.should_stop = should_stop

    def __iter__(self) -> Iterator[Any]:
        for value in self.values:
            if _stop_requested(self.should_stop):
                return
            yield value


def _cooperative_as_completed(awaitables: Iterable[Any], should_stop: StopPredicate, limit: int = 4):
    """Yield awaitables with a bounded active window and no launches after stop."""
    iterator = iter(awaitables)
    active: set[asyncio.Task] = set()
    exhausted = False

    def fill() -> None:
        nonlocal exhausted
        while not exhausted and len(active) < limit and not _stop_requested(should_stop):
            try:
                active.add(asyncio.create_task(next(iterator)))
            except StopIteration:
                exhausted = True

    fill()
    try:
        while active:
            async def next_completed():
                done, _ = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
                task = next(iter(done))
                active.remove(task)
                result = await task
                fill()
                return result
            yield next_completed()
    finally:
        for pending in iterator:
            close = getattr(pending, "close", None)
            if close:
                close()


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


def _run_research_b(root: Path, output: Path, mode: str, condition: str | None, case_id: str | None, should_stop: StopPredicate = None) -> bool:
    _require_frozen_qwen_provider()
    runner = _load(root / "research/research_b/runner.py", "frozen_research_b_runner")
    config = runner.config(root / "research/research_b/config/research_b_judge.json")
    benchmark, cases, _ = runner.validate_frozen(config)
    config["output_dir"] = str(output)
    if mode == "full_benchmark":
        results_path = output / "results.jsonl"
        existing = runner.read_jsonl(results_path) if results_path.exists() else []
        done = {(row["case_id"], row["condition"]) for row in existing}
        by_id = {item["case_id"]: item for item in cases}
        plan = runner.plan(config, cases)
        remaining = iter(entry for entry in plan if (entry["case_id"], entry["condition"]) not in done)

        def execute_one(entry):
            return entry, runner.request_prediction(config, by_id[entry["case_id"]], entry["condition"])

        max_workers = int(config.get("concurrency", 8))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: dict[Any, dict[str, Any]] = {}

            def fill() -> None:
                while len(futures) < max_workers and not _stop_requested(should_stop):
                    try:
                        entry = next(remaining)
                    except StopIteration:
                        return
                    futures[executor.submit(execute_one, entry)] = entry

            fill()
            while futures:
                finished, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in finished:
                    futures.pop(future, None)
                    entry, prediction = future.result()
                    case = by_id[entry["case_id"]]
                    record = {
                        **entry, "reference_label": case["reference_label"], "prediction": prediction["label"],
                        "confidence": prediction["confidence"], "reason": prediction["reason"], "usable": prediction["usable"],
                        "latency_ms": prediction["latency_ms"], "http_status": prediction["http_status"],
                        "model_actually_called": prediction["model_actually_called"], "provider_attempts": prediction["attempts"],
                        "retry_count": max(0, len(prediction["attempts"]) - 1), "error": prediction["error"],
                        "benchmark_sha256": runner.sha256(benchmark), "freeze_sha256": runner.sha256(root / config["freeze_manifest"]),
                    }
                    with results_path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(record, ensure_ascii=False) + "\n"); handle.flush(); os.fsync(handle.fileno())
                    done.add((entry["case_id"], entry["condition"]))
                fill()
        if _stop_requested(should_stop):
            return True
        runner.write_analysis_outputs(config, runner.read_jsonl(results_path))
        return False
    case = next((item for item in cases if item["case_id"] == case_id), cases[0])
    chosen = _conditions(mode, condition, ["J1", "J2"])
    for index, current in enumerate(chosen, 1):
        if _stop_requested(should_stop):
            return True
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
    return False


def _enrich_research_c(root: Path, cases: list[dict[str, Any]]) -> None:
    excerpt_ids: dict[str, str] = {}
    corpus = root / "research/corpus/tcm_v1/chunks.jsonl"
    if corpus.exists():
        for item in _read_jsonl(corpus):
            excerpt_ids[item.get("text", "").strip()] = item.get("chunk_id", "")
    for case in cases:
        case.setdefault("source_a_id", excerpt_ids.get(case.get("source_a_excerpt", "").strip(), "unknown-source-a"))
        case.setdefault("source_b_id", excerpt_ids.get(case.get("source_b_excerpt", "").strip(), "unknown-source-b"))


def _run_research_c(root: Path, output: Path, mode: str, condition: str | None, case_id: str | None, should_stop: StopPredicate = None) -> bool:
    _require_frozen_qwen_provider()
    runner = _load(root / "research/research_c/runner.py", "frozen_research_c_runner")
    config = runner.config(root / "research/research_c/config/research_c_conflict.json")
    benchmark, cases, freeze = runner.validate_frozen(config)
    config["output_dir"] = str(output)
    if mode == "full_benchmark":
        # The frozen runner's executor submits the entire benchmark at once.
        # This adapter preserves its plan, calls, row schema, and concurrency cap,
        # while admitting new work only after a safe cancellation check.
        runner.ROOT = root
        out = output
        entries = runner.plan(config, cases)
        formal_manifest = {
            "benchmark_sha256": runner.sha256(benchmark),
            "freeze_manifest_sha256": runner.sha256(root / config["freeze_manifest"]),
            "runner_sha256": runner.sha256(Path(runner.__file__)),
            "model": config.get("model"),
            "provider": config.get("base_url_env"),
            "runtime": {key: config.get(key) for key in ("temperature", "max_tokens", "timeout_seconds", "max_attempts", "concurrency")},
            "planned_formal_executions": 264,
            "execution_order_seed": config["random_seed"],
            "analysis_plan_version": "research_c_imbalanced_v1",
        }
        runner.atomic_write(out / "formal_run_manifest.json", json.dumps(formal_manifest, indent=2) + "\n")
        runner.atomic_write(out / "execution_order.json", json.dumps(entries, indent=2) + "\n")
        _enrich_research_c(root, cases)
        results_path = out / "results.jsonl"; attempts_path = out / "provider_attempts.jsonl"
        results = runner.read_jsonl(results_path) if results_path.exists() else []
        attempts = runner.read_jsonl(attempts_path) if attempts_path.exists() else []
        done = {(row.get("case_id"), row.get("condition")) for row in results}
        by_id = {item["case_id"]: item for item in cases}
        remaining = iter(entry for entry in entries if (entry["case_id"], entry["condition"]) not in done)

        def execute_one(entry):
            case = by_id[entry["case_id"]]
            prediction = runner.request_prediction(config, case, entry["condition"])
            row = {"case_id": case["case_id"], "condition": entry["condition"], "reference_label": case["reference_label"], "prediction": prediction.get("label"), **{key: value for key, value in prediction.items() if key not in {"attempts", "label"}}}
            attempt_rows = [{"case_id": case["case_id"], "condition": entry["condition"], **attempt} for attempt in prediction.get("attempts", [])]
            return row, attempt_rows

        max_workers = int(config.get("concurrency", 8))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: set[Any] = set()

            def fill() -> None:
                while len(futures) < max_workers and not _stop_requested(should_stop):
                    try:
                        futures.add(executor.submit(execute_one, next(remaining)))
                    except StopIteration:
                        return

            fill()
            while futures:
                finished, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in finished:
                    futures.remove(future)
                    row, attempt_rows = future.result(); results.append(row); attempts.extend(attempt_rows)
                    runner.atomic_write(results_path, "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in results))
                    runner.atomic_write(attempts_path, "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in attempts))
                    runner.atomic_write(out / "run_progress.json", json.dumps({"completed": len(results), "planned": 264}) + "\n")
                fill()
        if _stop_requested(should_stop):
            return True
        runner.atomic_write(out / "analysis.json", json.dumps(runner.analyze_rows(results), ensure_ascii=False, indent=2) + "\n")
        return False
    _enrich_research_c(root, cases)
    case = next((item for item in cases if item["case_id"] == case_id), cases[0])
    chosen = _conditions(mode, condition, ["K1", "K2"])
    successful = failed = 0
    for index, current in enumerate(chosen, 1):
        if _stop_requested(should_stop):
            return True
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
    return False


def _run_a3(root: Path, output: Path, mode: str, condition: str | None, case_id: str | None, should_stop: StopPredicate = None) -> bool:
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
    execution.execution_order = _CooperativeIterable(execution.execution_order, should_stop)
    asyncio.run(execution.run())
    if _stop_requested(should_stop):
        return True
    if mode == "full_benchmark":
        objective, process = runner.compute_objective_and_process_metrics()
        _write(formal_output / "objective_metrics.json", objective)
        _write(formal_output / "process_metrics.json", process)
        runner.generate_blinded_review_packet()
        runner.write_semantic_review_instructions()
        _write(formal_output / "formal_validation.json", runner.validate_formal_execution())
    return False


def _run_retrieval(root: Path, output: Path, should_stop: StopPredicate = None) -> bool:
    _require_frozen_qwen_provider()
    os.environ.update({
        "TCM_CORPUS_MODE": "required",
        "TCM_CORPUS_PATH": str(root / "research/corpus/tcm_v1/chunks.jsonl"),
        "EMBEDDING_PROVIDER": "siliconflow",
        "EMBEDDING_API_KEY": os.environ["LLM_API_KEY"],
        "EMBEDDING_MODEL": "BAAI/bge-m3",
        "RERANK_PROVIDER": "siliconflow",
        "RERANK_API_KEY": os.environ["LLM_API_KEY"],
        "RERANK_MODEL": "BAAI/bge-reranker-v2-m3",
    })
    warmer = _load(root / "research/retrieval_ablation/warm_formal_cache.py", "frozen_retrieval_cache_warmer")
    cache_dir = output / "cache"
    warmer.warm(cache_dir)
    stage1 = _load(root / "research/retrieval_ablation/runner.py", "frozen_retrieval_stage1")
    stage1.STUDY_ROOT = output
    os.environ["RETRIEVAL_ABLATION_EXECUTION"] = "FORMAL_STAGE1_APPROVED"
    stage1_out = output / "stage1"
    original_plan = stage1.build_stage1_plan
    calls = 0
    def cooperative_plan():
        nonlocal calls
        calls += 1
        plan = original_plan()
        return plan if calls == 1 else _CooperativeIterable(plan, should_stop)
    stage1.build_stage1_plan = cooperative_plan
    try:
        try:
            asyncio.run(stage1.execute_stage1(stage1_out))
        except RuntimeError:
            if not _stop_requested(should_stop):
                raise
    finally:
        stage1.build_stage1_plan = original_plan
    if _stop_requested(should_stop):
        return True
    stage2 = _load(root / "research/retrieval_ablation/stage2_runner.py", "frozen_retrieval_stage2")
    stage2.STAGE1 = stage1_out
    stage2.OUT = output / "stage2"
    original_as_completed = stage2.asyncio.as_completed
    stage2.asyncio.as_completed = lambda awaitables: _cooperative_as_completed(awaitables, should_stop, 4)
    try:
        try:
            asyncio.run(stage2.main())
        except RuntimeError:
            if not _stop_requested(should_stop):
                raise
    finally:
        stage2.asyncio.as_completed = original_as_completed
    return _stop_requested(should_stop)


def _run_rq1(root: Path, output: Path, mode: str, condition: str | None, case_id: str | None, should_stop: StopPredicate = None) -> bool:
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
            if _stop_requested(should_stop):
                return True
            _status(output, completed=len(done), total=expected, current_case=entry["question_id"], current_condition=entry["condition"])
            row = runner.request_one(config, by_id[entry["question_id"]], entry)
            row["result_origin"] = "new_replay"; _append(results_path, row); done.add((entry["question_id"], entry["condition"]))
    rows = _read_jsonl(results_path)
    _status(output, completed=len(rows), successful=sum(row.get("run_status") in {"PASS", "PASS_WITH_RETRY"} for row in rows), failed=sum(row.get("run_status") not in {"PASS", "PASS_WITH_RETRY"} for row in rows))
    _write(output / "manifest.json", {"result_origin": "new_replay", "runner": "research/experiment_pipeline/rq1_confirmatory.py", "case_id": None if mode == "full_benchmark" else selected_case, "conditions": sorted(allowed), "historical_results_modified": False})
    return False


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


def _run_rq4(root: Path, output: Path, mode: str, condition: str | None, case_id: str | None, should_stop: StopPredicate = None) -> bool:
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
            if _stop_requested(should_stop):
                return True
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
    return False


def run_replay(
    *,
    experiment_id: str,
    run_mode: str,
    frozen_root: Path,
    output: Path,
    condition: str | None = None,
    case_id: str | None = None,
    should_stop: StopPredicate = None,
) -> bool:
    """Run one exact replay adapter inside a worker-owned disposable workspace."""
    from formal_experiments.registry import validate_replay_path, verify_deployment_integrity
    root = frozen_root.resolve()
    integrity_ok, integrity_errors = verify_deployment_integrity(root, experiment_id)
    if not integrity_ok:
        raise RuntimeError("Formal asset integrity verification failed: " + ", ".join(integrity_errors))
    output = validate_replay_path(root, output); output.mkdir(parents=True, exist_ok=True)
    _status(output, status="running", completed=0, total=0, successful=0, failed=0)
    actions = {
        "retrieval_ablation": lambda: _run_retrieval(root, output, should_stop),
        "rq1_architecture": lambda: _run_rq1(root, output, run_mode, condition, case_id, should_stop),
        "rq4_debate": lambda: _run_rq4(root, output, run_mode, condition, case_id, should_stop),
        "research_b": lambda: _run_research_b(root, output, run_mode, condition, case_id, should_stop),
        "research_c": lambda: _run_research_c(root, output, run_mode, condition, case_id, should_stop),
        "a3_v1_3": lambda: _run_a3(root, output, run_mode, condition, case_id, should_stop),
    }
    if experiment_id not in actions:
        raise RuntimeError("No replay-safe adapter is available for this experiment")
    stopped = bool(actions[experiment_id]())
    if stopped:
        _status(output, status="stopped", resume_state="stopped")
        return True
    _status(output, status="complete", resume_state="complete")
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--run-mode", required=True)
    parser.add_argument("--condition")
    parser.add_argument("--case-id")
    parser.add_argument("--frozen-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_replay(
        experiment_id=args.experiment,
        run_mode=args.run_mode,
        condition=args.condition,
        case_id=args.case_id,
        frozen_root=args.frozen_root,
        output=args.output,
    )


if __name__ == "__main__":
    main()
