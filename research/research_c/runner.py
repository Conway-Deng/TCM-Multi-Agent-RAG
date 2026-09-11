"""State-gated paired K1/K2 runner for Research C.

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
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config/research_c_conflict.json"
LABELS = ("AGREEMENT", "PARTIAL_CONFLICT", "DIRECT_CONFLICT", "INSUFFICIENT_OR_AMBIGUOUS")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


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
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({key: value for key, value in os.environ.items() if key.startswith("LLM_")})
    return values


def build_messages(case: dict[str, Any], condition: str) -> list[dict[str, str]]:
    if condition not in {"K1", "K2"}:
        raise ValueError("INVALID_CONDITION")

    if condition == "K1":
        rubric = (
            "You are a TCM question-answering assistant. Answer the user's question accurately using ONLY the provided source excerpts. "
            "Base your answer strictly on the text provided. "
            "Return strict JSON with: "
            "\"conflict_status\" (one of: AGREEMENT, PARTIAL_CONFLICT, DIRECT_CONFLICT, or INSUFFICIENT_OR_AMBIGUOUS), "
            "\"answer\" (your direct answer based on the excerpts), "
            "\"reason\" (concise explanation), and "
            "\"confidence\" (optional float 0 to 1)."
        )
    else:
        rubric = (
            "You are a conflict-aware TCM evidence assistant. Evaluate the provided sources carefully and answer the user's question while transparently managing any evidence conflicts.\n"
            "You must adhere to these rules:\n"
            "1. Classify the source relationship: AGREEMENT, PARTIAL_CONFLICT, DIRECT_CONFLICT, or INSUFFICIENT_OR_AMBIGUOUS.\n"
            "2. If sources conflict (partial or direct), preserve BOTH viewpoints clearly and cite both relevant sources.\n"
            "3. Express appropriate uncertainty when sources diverge; do NOT pick a favorite source or invent an ungrounded resolution.\n"
            "4. If sources agree, confirm mutual corroboration.\n"
            "5. If sources are insufficient or ambiguous, explicitly state what information is missing.\n"
            "Return strict JSON with:\n"
            "- \"conflict_status\": exactly one of AGREEMENT, PARTIAL_CONFLICT, DIRECT_CONFLICT, INSUFFICIENT_OR_AMBIGUOUS\n"
            "- \"answer\": your transparent response preserving distinct source viewpoints and citations\n"
            "- \"preserves_both_viewpoints\": boolean\n"
            "- \"cites_both_sources\": boolean\n"
            "- \"expresses_uncertainty\": boolean\n"
            "- \"reason\": concise explanation\n"
            "- \"confidence\": optional float from 0 to 1"
        )

    content = (
        f"QUESTION:\n{case['question']}\n\n"
        f"SOURCE A ({case['source_a_title']}, ID: {case['source_a_id']}):\n{case['source_a_excerpt']}\n\n"
        f"SOURCE B ({case['source_b_title']}, ID: {case['source_b_id']}):\n{case['source_b_excerpt']}"
    )
    return [{"role": "system", "content": rubric}, {"role": "user", "content": content}]


def validate_frozen(c: dict[str, Any]) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    benchmark = ROOT / c["formal_benchmark"]
    freeze_path = ROOT / c["freeze_manifest"]
    if not benchmark.exists() or not freeze_path.exists():
        raise RuntimeError("RESEARCH_C_SOURCE_REVIEW_AND_FREEZE_REQUIRED")
    freeze = load_json(freeze_path)
    cases = read_jsonl(benchmark)
    if freeze.get("status") not in {"FROZEN_INDEPENDENTLY_REVIEWED_RESEARCH_C_V1", "FROZEN"}:
        raise RuntimeError("RESEARCH_C_NOT_FROZEN")
    if freeze.get("benchmark_sha256") != sha256(benchmark):
        raise RuntimeError("RESEARCH_C_FREEZE_HASH_MISMATCH")
    if len(cases) != 132 or len({case["case_id"] for case in cases}) != 132:
        raise RuntimeError("RESEARCH_C_BENCHMARK_SIZE_OR_ID_MISMATCH")
    counts = Counter(case.get("reference_label") for case in cases)
    if set(counts) - set(LABELS) or any("proposed_label" in case for case in cases):
        raise RuntimeError("RESEARCH_C_INVALID_OR_LEAKED_GOLD")
    return benchmark, cases, freeze


def plan(c: dict[str, Any], cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rng = random.Random(c["random_seed"])
    entries = []
    for case in cases:
        conditions = ["K1", "K2"]
        rng.shuffle(conditions)
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

    # Status can be returned in conflict_status or label
    raw_status = value.get("conflict_status") or value.get("label", "")
    status_label = str(raw_status).upper().strip()
    raw_confidence = value.get("confidence")
    confidence = None if raw_confidence is None else float(raw_confidence)
    reason = str(value.get("reason", "")).strip()
    answer = str(value.get("answer", "")).strip()

    if status_label not in LABELS:
        raise ValueError(f"INVALID_CONFLICT_LABEL:{status_label}")
    if confidence is not None and not (0 <= confidence <= 1):
        raise ValueError(f"INVALID_CONFIDENCE:{confidence}")
    if not reason:
        raise ValueError("EMPTY_REASON")

    return {
        "label": status_label,
        "answer": answer,
        "preserves_both_viewpoints": bool(value.get("preserves_both_viewpoints", False)),
        "cites_both_sources": bool(value.get("cites_both_sources", False)),
        "expresses_uncertainty": bool(value.get("expresses_uncertainty", False)),
        "confidence": confidence,
        "reason": reason,
    }


def request_prediction(c: dict[str, Any], case: dict[str, Any], condition: str) -> dict[str, Any]:
    env = provider_env()
    base = env.get(c["base_url_env"], "https://api.siliconflow.cn/v1").rstrip("/")
    key = env.get(c["api_key_env"], "")
    model = env.get(c["model_env"], c["model"])
    if not base or not key:
        raise RuntimeError("PROVIDER_ENV_NOT_CONFIGURED")

    payload = {
        "model": model,
        "messages": build_messages(case, condition),
        "temperature": c["temperature"],
        "max_tokens": c["max_tokens"],
    }
    attempts = []
    for attempt_number in range(1, int(c.get("max_attempts", 3)) + 1):
        started = time.perf_counter()
        raw_content = None
        try:
            request = urllib.request.Request(
                base + "/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(request, timeout=c["timeout_seconds"]) as response:
                body = json.loads(response.read().decode("utf-8"))
                status = response.status
            raw_content = body["choices"][0]["message"]["content"]
            prediction = parse_prediction(raw_content)
            attempts.append({
                "attempt": attempt_number,
                "http_status": status,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "raw_output": raw_content,
                "model": body.get("model", model),
                "error": None,
            })
            return {
                **prediction,
                "usable": True,
                "latency_ms": sum(item["latency_ms"] for item in attempts),
                "http_status": status,
                "model_actually_called": body.get("model", model),
                "attempts": attempts,
                "error": None,
            }
        except Exception as exc:
            attempts.append({
                "attempt": attempt_number,
                "http_status": 0,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "raw_output": raw_content,
                "model": model,
                "error": f"{type(exc).__name__}: {exc}",
            })
            if attempt_number < int(c.get("max_attempts", 3)):
                time.sleep(float(c.get("retry_backoff_seconds", 1)))

    return {
        "label": None,
        "answer": None,
        "preserves_both_viewpoints": False,
        "cites_both_sources": False,
        "expresses_uncertainty": False,
        "confidence": None,
        "reason": None,
        "usable": False,
        "latency_ms": sum(item["latency_ms"] for item in attempts),
        "http_status": 0,
        "model_actually_called": model,
        "attempts": attempts,
        "error": attempts[-1]["error"],
    }


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
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(confusion[label].values()),
        }
    accuracy = sum(confusion[label][label] for label in LABELS) / len(usable) if usable else 0.0
    macro_f1 = sum(value["f1"] for value in per_class.values()) / len(LABELS)

    # Secondary metrics
    dual_citations = sum(row.get("cites_both_sources", False) for row in usable)
    dual_viewpoints = sum(row.get("preserves_both_viewpoints", False) for row in usable)
    uncertainty_count = sum(row.get("expresses_uncertainty", False) for row in usable)

    latencies = [float(row.get("latency_ms") or 0) for row in usable]
    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix": confusion,
        "usable": len(usable),
        "total": len(rows),
        "usable_rate": round(len(usable) / len(rows), 4) if rows else 0.0,
        "dual_citation_rate": round(dual_citations / len(usable), 4) if usable else 0.0,
        "dual_viewpoint_rate": round(dual_viewpoints / len(usable), 4) if usable else 0.0,
        "uncertainty_rate": round(uncertainty_count / len(usable), 4) if usable else 0.0,
        "mean_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "median_latency_ms": round(sorted(latencies)[len(latencies)//2], 2) if latencies else None,
    }


def analyze_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    conditions = {cond: _condition_metrics([r for r in rows if r.get("condition") == cond]) for cond in ("K1", "K2")}
    by_case: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_case.setdefault(row["case_id"], {})[row["condition"]] = row
    paired = [pair for pair in by_case.values() if "K1" in pair and "K2" in pair and pair["K1"].get("usable") and pair["K2"].get("usable")]
    k1_only = sum(pair["K1"]["prediction"] == pair["K1"]["reference_label"] and pair["K2"]["prediction"] != pair["K2"]["reference_label"] for pair in paired)
    k2_only = sum(pair["K2"]["prediction"] == pair["K2"]["reference_label"] and pair["K1"]["prediction"] != pair["K1"]["reference_label"] for pair in paired)
    return {
        **conditions,
        "difference_k2_minus_k1": {
            "accuracy": round(conditions["K2"]["accuracy"] - conditions["K1"]["accuracy"], 4),
            "macro_f1": round(conditions["K2"]["macro_f1"] - conditions["K1"]["macro_f1"], 4),
            "dual_citation_diff": round(conditions["K2"]["dual_citation_rate"] - conditions["K1"]["dual_citation_rate"], 4),
            "dual_viewpoint_diff": round(conditions["K2"]["dual_viewpoint_rate"] - conditions["K1"]["dual_viewpoint_rate"], 4),
        },
        "paired_usable_cases": len(paired),
        "paired_accuracy_discordance": {
            "K1_correct_K2_wrong": k1_only,
            "K2_correct_K1_wrong": k2_only,
        },
    }


def execute_formal(c: dict[str, Any], benchmark: Path, cases: list[dict[str, Any]], freeze: dict[str, Any]) -> dict[str, Any]:
    """Run exactly one paired K1/K2 pass and persist raw attempts/results."""
    out = ROOT / c.get("output_dir", "research/research_c/formal_run_v1")
    out.mkdir(parents=True, exist_ok=True)
    entries = plan(c, cases)
    manifest = {"benchmark_sha256": sha256(benchmark), "freeze_manifest_sha256": sha256(ROOT / c["freeze_manifest"]),
                "runner_sha256": sha256(Path(__file__)), "model": c.get("model"), "provider": c.get("base_url_env"),
                "runtime": {k: c.get(k) for k in ("temperature","max_tokens","timeout_seconds","max_attempts","concurrency")},
                "planned_formal_executions": 264, "execution_order_seed": c["random_seed"], "analysis_plan_version":"research_c_imbalanced_v1"}
    atomic_write(out / "formal_run_manifest.json", json.dumps(manifest, indent=2) + "\n")
    atomic_write(out / "execution_order.json", json.dumps(entries, indent=2) + "\n")
    # The frozen JSONL predates explicit source-ID fields; enrich only the
    # in-memory execution objects from exact corpus excerpts (benchmark bytes
    # and hash remain unchanged).
    corpus_path = ROOT / "research/corpus/tcm_v1/chunks.jsonl"
    excerpt_ids = {}
    if corpus_path.exists():
        for line in corpus_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line); excerpt_ids[item.get("text", "").strip()] = item.get("chunk_id", "")
    for case in cases:
        case.setdefault("source_a_id", excerpt_ids.get(case.get("source_a_excerpt", "").strip(), "unknown-source-a"))
        case.setdefault("source_b_id", excerpt_ids.get(case.get("source_b_excerpt", "").strip(), "unknown-source-b"))
    results = [json.loads(line) for line in (out / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()] if (out / "results.jsonl").exists() else []
    attempts = [json.loads(line) for line in (out / "provider_attempts.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()] if (out / "provider_attempts.jsonl").exists() else []
    done={(r.get("case_id"),r.get("condition")) for r in results}
    todo=[e for e in entries if (e["case_id"],e["condition"]) not in done]
    def work(entry):
        case=next(x for x in cases if x["case_id"]==entry["case_id"])
        result=request_prediction(c, case, entry["condition"])
        row={"case_id":case["case_id"],"condition":entry["condition"],"reference_label":case["reference_label"],"prediction":result.get("label"),**{k:v for k,v in result.items() if k not in {"attempts","label"}}}
        ats=[{"case_id":case["case_id"],"condition":entry["condition"],**a} for a in result.get("attempts",[])]
        return row,ats
    with ThreadPoolExecutor(max_workers=int(c.get("concurrency",8))) as pool:
        futures=[pool.submit(work,e) for e in todo]
        for future in as_completed(futures):
            row,ats=future.result(); results.append(row); attempts.extend(ats)
            atomic_write(out / "results.jsonl", "".join(json.dumps(r,ensure_ascii=False)+"\n" for r in results))
            atomic_write(out / "provider_attempts.jsonl", "".join(json.dumps(r,ensure_ascii=False)+"\n" for r in attempts))
            atomic_write(out / "run_progress.json", json.dumps({"completed":len(results),"planned":264})+"\n")
    analysis=analyze_rows(results); atomic_write(out / "analysis.json", json.dumps(analysis,ensure_ascii=False,indent=2)+"\n")
    return {"scheduled":len(results),"provider_attempts":len(attempts),"analysis":analysis,"output_dir":str(out)}


def status(c: dict[str, Any]) -> dict[str, Any]:
    candidate = ROOT / c["candidate_benchmark"]
    formal = ROOT / c["formal_benchmark"]
    freeze = ROOT / c["freeze_manifest"]
    return {
        "study": "Research C — TCM conflict identification & transparent evidence study",
        "status": "READY_FOR_INDEPENDENT_SOURCE_REVIEW" if candidate.exists() and not freeze.exists() else "FROZEN_NOT_RUN" if formal.exists() and freeze.exists() else "CANDIDATE_PREPARATION_INCOMPLETE",
        "candidate_cases": len(read_jsonl(candidate)) if candidate.exists() else 0,
        "formal_benchmark_exists": formal.exists(),
        "freeze_manifest_exists": freeze.exists(),
        "provider_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="status", choices=("status", "run"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    c = config(args.config)
    if args.command == "status":
        result = status(c)
    elif args.command == "run":
        if not args.execute:
            raise RuntimeError("EXPLICIT_EXECUTE_FLAG_REQUIRED")
        benchmark, cases, freeze = validate_frozen(c)
        result = execute_formal(c, benchmark, cases, freeze)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
