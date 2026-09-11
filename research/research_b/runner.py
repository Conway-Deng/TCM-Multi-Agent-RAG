"""State-gated paired J1/J2 runner for Research B.

Default operation is status-only. Provider execution is impossible until an
independently reviewed benchmark and matching freeze manifest exist, and then
still requires the explicit ``run --execute`` command.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config/research_b_judge.json"
LABELS = ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONTRADICTED")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp"); temporary.write_text(text, encoding="utf-8"); temporary.replace(path)


def config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return load_json(path)


def provider_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = ROOT / "backend/.env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1); values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({key: value for key, value in os.environ.items() if key.startswith("LLM_")})
    return values


def build_messages(case: dict[str, Any], condition: str) -> list[dict[str, str]]:
    if condition not in {"J1", "J2"}:
        raise ValueError("INVALID_JUDGE_CONDITION")
    rubric = (
        "Classify the claim using exactly one label: SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, or CONTRADICTED. "
        "SUPPORTED means all substantive claim content is supported; PARTIALLY_SUPPORTED means some but not all is supported; "
        "UNSUPPORTED means the supplied information does not substantively support it and does not explicitly conflict; "
        "CONTRADICTED means supplied information explicitly conflicts with a central claim. "
        "Return strict JSON with label, confidence (0 to 1), and a concise reason."
    )
    content = f"CLAIM:\n{case['claim']}"
    if condition == "J2":
        content += f"\n\nEVIDENCE:\n{case['evidence']}\n\nSOURCE IDS:\n{' | '.join(case.get('source_ids', []))}"
    return [{"role": "system", "content": rubric}, {"role": "user", "content": content}]


def validate_frozen(c: dict[str, Any]) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    benchmark = ROOT / c["formal_benchmark"]
    freeze_path = ROOT / c["freeze_manifest"]
    if not benchmark.exists() or not freeze_path.exists():
        raise RuntimeError("RESEARCH_B_SOURCE_REVIEW_AND_FREEZE_REQUIRED")
    freeze = load_json(freeze_path); cases = read_jsonl(benchmark)
    if freeze.get("status") != "FROZEN_INDEPENDENTLY_REVIEWED_RESEARCH_B_V1":
        raise RuntimeError("RESEARCH_B_NOT_FROZEN")
    if freeze.get("benchmark_sha256") != sha256(benchmark):
        raise RuntimeError("RESEARCH_B_FREEZE_HASH_MISMATCH")
    if len(cases) != 240 or len({case["case_id"] for case in cases}) != 240:
        raise RuntimeError("RESEARCH_B_BENCHMARK_SIZE_OR_ID_MISMATCH")
    counts = Counter(case.get("reference_label") for case in cases)
    if set(counts) - set(LABELS) or any("proposed_label" in case for case in cases):
        raise RuntimeError("RESEARCH_B_INVALID_OR_LEAKED_GOLD")
    return benchmark, cases, freeze


def plan(c: dict[str, Any], cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rng = random.Random(c["random_seed"]); entries = []
    for case in cases:
        conditions = ["J1", "J2"]; rng.shuffle(conditions)
        for condition in conditions:
            entries.append({"sequence": len(entries) + 1, "case_id": case["case_id"], "condition": condition})
    return entries


def parse_prediction(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    if not cleaned.startswith("{"):
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]
    value = json.loads(cleaned)
    label = str(value.get("label", "")).upper()
    raw_confidence = value.get("confidence")
    confidence = None if raw_confidence is None else float(raw_confidence)
    if label not in LABELS or (confidence is not None and not 0 <= confidence <= 1) or not str(value.get("reason", "")).strip():
        raise ValueError("INVALID_JUDGE_OUTPUT")
    return {"label": label, "confidence": confidence, "reason": str(value["reason"]).strip()}


def request_prediction(c: dict[str, Any], case: dict[str, Any], condition: str) -> dict[str, Any]:
    env = provider_env(); base = env.get(c["base_url_env"], "https://api.siliconflow.cn/v1").rstrip("/")
    key = env.get(c["api_key_env"], ""); model = env.get(c["model_env"], c["model"])
    if not base or not key:
        raise RuntimeError("JUDGE_PROVIDER_ENV_NOT_CONFIGURED")
    payload = {"model": model, "messages": build_messages(case, condition), "temperature": c["temperature"], "max_tokens": c["max_tokens"]}
    attempts = []
    for attempt_number in range(1, int(c.get("max_attempts", 2)) + 1):
        started = time.perf_counter()
        raw_content = None
        try:
            request = urllib.request.Request(base + "/chat/completions", data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=c["timeout_seconds"]) as response:
                body = json.loads(response.read().decode("utf-8")); status = response.status
            raw_content = body["choices"][0]["message"]["content"]; prediction = parse_prediction(raw_content)
            attempts.append({"attempt": attempt_number, "http_status": status, "latency_ms": round((time.perf_counter() - started) * 1000, 3), "raw_output": raw_content, "model": body.get("model", model), "error": None})
            return {**prediction, "usable": True, "latency_ms": sum(item["latency_ms"] for item in attempts), "http_status": status, "model_actually_called": body.get("model", model), "attempts": attempts, "error": None}
        except Exception as exc:
            attempts.append({"attempt": attempt_number, "http_status": 0, "latency_ms": round((time.perf_counter() - started) * 1000, 3), "raw_output": raw_content, "model": model, "error": f"{type(exc).__name__}: {exc}"})
            if attempt_number < int(c.get("max_attempts", 2)):
                time.sleep(float(c.get("retry_backoff_seconds", 1)))
    return {"label": None, "confidence": None, "reason": None, "usable": False, "latency_ms": sum(item["latency_ms"] for item in attempts), "http_status": 0, "model_actually_called": model, "attempts": attempts, "error": attempts[-1]["error"]}


def run(c: dict[str, Any], execute: bool) -> dict[str, Any]:
    benchmark, cases, freeze = validate_frozen(c)
    if not execute:
        raise RuntimeError("EXPLICIT_EXECUTE_FLAG_REQUIRED")
    output = ROOT / c["output_dir"]; output.mkdir(parents=True, exist_ok=True)
    results_path = output / "results.jsonl"; existing = read_jsonl(results_path) if results_path.exists() else []
    done = {(row["case_id"], row["condition"]) for row in existing}; by_id = {case["case_id"]: case for case in cases}
    execution_plan = plan(c, cases)
    remaining = [entry for entry in execution_plan if (entry["case_id"], entry["condition"]) not in done]

    def execute_one(entry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        return entry, request_prediction(c, by_id[entry["case_id"]], entry["condition"])

    with ThreadPoolExecutor(max_workers=int(c.get("concurrency", 8))) as executor:
        futures = [executor.submit(execute_one, entry) for entry in remaining]
        for future in as_completed(futures):
            entry, prediction = future.result()
            case = by_id[entry["case_id"]]
            pair = (entry["case_id"], entry["condition"])
            record = {**entry, "reference_label": case["reference_label"], "prediction": prediction["label"], "confidence": prediction["confidence"], "reason": prediction["reason"], "usable": prediction["usable"], "latency_ms": prediction["latency_ms"], "http_status": prediction["http_status"], "model_actually_called": prediction["model_actually_called"], "provider_attempts": prediction["attempts"], "retry_count": max(0, len(prediction["attempts"]) - 1), "error": prediction["error"], "benchmark_sha256": sha256(benchmark), "freeze_sha256": sha256(ROOT / c["freeze_manifest"])}
            with results_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n"); handle.flush(); os.fsync(handle.fileno())
            done.add(pair)
            if len(done) % 20 == 0 or len(done) == len(execution_plan):
                print(json.dumps({"progress": len(done), "total": len(execution_plan), "usable": sum(row.get("usable", False) for row in read_jsonl(results_path))}), flush=True)
    return write_analysis_outputs(c, read_jsonl(results_path))


def _condition_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if row.get("usable") and row.get("prediction") in LABELS]
    confusion = {gold: {pred: 0 for pred in LABELS} for gold in LABELS}
    for row in usable:
        confusion[row["reference_label"]][row["prediction"]] += 1
    per_class = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[gold][label] for gold in LABELS if gold != label)
        fn = sum(confusion[label][pred] for pred in LABELS if pred != label)
        precision = tp / (tp + fp) if tp + fp else 0.0; recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(confusion[label].values())}
    accuracy = sum(confusion[label][label] for label in LABELS) / len(usable) if usable else 0.0
    confidences = [float(row["confidence"]) for row in usable if row.get("confidence") is not None]
    correct_conf = [float(row["confidence"]) for row in usable if row.get("confidence") is not None and row["prediction"] == row["reference_label"]]
    calibration = []
    for bin_index in range(10):
        low, high = bin_index / 10, (bin_index + 1) / 10
        bucket = [row for row in usable if row.get("confidence") is not None and low <= float(row["confidence"]) <= high if bin_index == 9 or float(row["confidence"]) < high]
        if bucket:
            calibration.append({"low": low, "high": high, "n": len(bucket), "mean_confidence": sum(float(row["confidence"]) for row in bucket) / len(bucket), "accuracy": sum(row["prediction"] == row["reference_label"] for row in bucket) / len(bucket)})
    ece = sum(item["n"] / len(usable) * abs(item["accuracy"] - item["mean_confidence"]) for item in calibration) if usable else None
    brier = sum((float(row["confidence"]) - float(row["prediction"] == row["reference_label"])) ** 2 for row in usable if row.get("confidence") is not None) / len(confidences) if confidences else None
    return {"accuracy": accuracy, "macro_f1": sum(value["f1"] for value in per_class.values()) / len(LABELS), "per_class": per_class, "confusion_matrix": confusion, "usable": len(usable), "total": len(rows), "usable_rate": len(usable) / len(rows) if rows else 0.0, "mean_latency_ms": sum(float(row.get("latency_ms") or 0) for row in usable) / len(usable) if usable else None, "median_latency_ms": sorted(float(row.get("latency_ms") or 0) for row in usable)[len(usable)//2] if usable else None, "mean_confidence": sum(confidences) / len(confidences) if confidences else None, "mean_confidence_correct": sum(correct_conf) / len(correct_conf) if correct_conf else None, "ece_10_bin": ece, "correctness_brier": brier, "calibration_bins": calibration}


def analyze_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    conditions = {condition: _condition_metrics([row for row in rows if row.get("condition") == condition]) for condition in ("J1", "J2")}
    by_case: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_case.setdefault(row["case_id"], {})[row["condition"]] = row
    paired = [pair for pair in by_case.values() if "J1" in pair and "J2" in pair and pair["J1"].get("usable") and pair["J2"].get("usable")]
    j1_only = sum(pair["J1"]["prediction"] == pair["J1"]["reference_label"] and pair["J2"]["prediction"] != pair["J2"]["reference_label"] for pair in paired)
    j2_only = sum(pair["J2"]["prediction"] == pair["J2"]["reference_label"] and pair["J1"]["prediction"] != pair["J1"]["reference_label"] for pair in paired)
    return {**conditions, "difference_j2_minus_j1": {"accuracy": conditions["J2"]["accuracy"] - conditions["J1"]["accuracy"], "macro_f1": conditions["J2"]["macro_f1"] - conditions["J1"]["macro_f1"]}, "paired_usable_cases": len(paired), "paired_accuracy_discordance": {"J1_correct_J2_wrong": j1_only, "J2_correct_J1_wrong": j2_only}}


def write_analysis_outputs(c: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    output = ROOT / c["output_dir"]; analysis = analyze_rows(rows)
    atomic_write(output / "analysis.json", json.dumps(analysis, ensure_ascii=False, indent=2) + "\n")
    fields = ["case_id", "condition", "reference_label", "prediction", "correct", "usable", "confidence", "latency_ms", "retry_count", "http_status", "model_actually_called", "error"]
    temporary = output / "case_level_metrics.csv.tmp"
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for row in rows:
            writer.writerow({field: (row.get("prediction") == row.get("reference_label")) if field == "correct" else row.get(field) for field in fields})
    temporary.replace(output / "case_level_metrics.csv")
    j1, j2 = analysis["J1"], analysis["J2"]
    conclusion = "Providing evidence improved Judge performance." if analysis["difference_j2_minus_j1"]["accuracy"] > 0 else "Providing evidence did not improve Judge accuracy in this frozen run."
    markdown = f"""# Research B final results\n\n- Frozen cases: 240; formal executions: {len(rows)}.\n- J1 accuracy: {j1['accuracy']:.4%}; macro-F1: {j1['macro_f1']:.4f}; usable: {j1['usable']}/{j1['total']}.\n- J2 accuracy: {j2['accuracy']:.4%}; macro-F1: {j2['macro_f1']:.4f}; usable: {j2['usable']}/{j2['total']}.\n- J2 − J1 accuracy: {analysis['difference_j2_minus_j1']['accuracy']:+.4%}; macro-F1: {analysis['difference_j2_minus_j1']['macro_f1']:+.4f}.\n- Mean latency: J1 {j1['mean_latency_ms']:.1f} ms; J2 {j2['mean_latency_ms']:.1f} ms.\n\n## Conclusion\n\n{conclusion}\n"""
    atomic_write(output / "final_results.md", markdown)
    return analysis


def status(c: dict[str, Any]) -> dict[str, Any]:
    candidate = ROOT / c["candidate_benchmark"]; formal = ROOT / c["formal_benchmark"]; freeze = ROOT / c["freeze_manifest"]
    return {"status": "READY_FOR_INDEPENDENT_SOURCE_REVIEW" if candidate.exists() and not freeze.exists() else "FROZEN_NOT_RUN" if formal.exists() and freeze.exists() else "CANDIDATE_PREPARATION_INCOMPLETE", "candidate_cases": len(read_jsonl(candidate)) if candidate.exists() else 0, "formal_benchmark_exists": formal.exists(), "freeze_manifest_exists": freeze.exists(), "provider_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("command", nargs="?", default="status", choices=("status", "run", "analyze")); parser.add_argument("--execute", action="store_true"); parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG); args = parser.parse_args(); c = config(args.config)
    if args.command == "status": result = status(c)
    elif args.command == "run": result = run(c, args.execute)
    else:
        path = ROOT / c["output_dir"] / "results.jsonl"
        if not path.exists(): raise RuntimeError("RESEARCH_B_RESULTS_NOT_FOUND")
        result = write_analysis_outputs(c, read_jsonl(path))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
