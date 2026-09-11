from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
OUT = STUDY / "formal_stage2"
BENCHMARK = ROOT / "research/benchmarks/tcm_gold_rq1_confirmatory_v1/benchmark_confirmatory_v1_1_frozen.jsonl"
CORPUS = ROOT / "research/corpus/tcm_v1/chunks.jsonl"
STAGE1 = STUDY / "formal_stage1"
LABELS = ("SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED", "CONTRADICTED")

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canon(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

def load_key() -> tuple[str, str, str, str]:
    from config import get_settings
    s = get_settings()
    key = os.getenv("LLM_API_KEY", "") or s.llm_api_key
    base = os.getenv("LLM_BASE_URL", "") or s.llm_base_url
    model = "Qwen/Qwen3-8B"
    return key, base.rstrip("/"), model, s.llm_provider

def build_prompt(question: str, evidence: list[dict[str, Any]]) -> tuple[str, str]:
    system = ("You are the single-RAG TCM research assistant. Use only the supplied evidence. "
              "Write one concise educational paragraph of at most 120 words, preserve uncertainty, "
              "and do not diagnose, prescribe, recommend doses, or add facts absent from the evidence. "
              "Traditional claims must be framed as source-reported TCM content, not established biomedical fact. "
              "Return plain text only: do not emit citations, evidence IDs, source labels, Markdown, JSON, or backslashes. "
              "Answer the named entity in the question directly and do not merge properties from evidence about a different entity.")
    payload = {"question": question, "response_language": "en", "specialist_scope": "single_rag",
               "evidence": [{"label": f"Evidence {i}", "text": e["text"]} for i, e in enumerate(evidence, 1)]}
    return system, json.dumps(payload, ensure_ascii=False)

async def call_llm(key: str, base: str, model: str, system: str, prompt: str, max_attempts: int = 2) -> dict[str, Any]:
    import httpx
    attempts = []
    for n in range(1, max_attempts + 1):
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(base + "/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                                       json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                                             "temperature": 0.0, "max_tokens": 384, "frequency_penalty": 0.5 if n == 1 else 1.0, "stream": False, "enable_thinking": False})
                r.raise_for_status(); body = r.json(); text = body["choices"][0]["message"]["content"]
            elapsed = round((time.perf_counter() - started) * 1000, 3)
            attempts.append({"attempt": n, "http_status": r.status_code, "latency_ms": elapsed, "model": body.get("model", model), "success": True, "error": None})
            return {"answer": str(text), "usable": bool(str(text).strip()), "latency_ms": sum(a["latency_ms"] for a in attempts), "http_status": r.status_code,
                    "model": body.get("model", model), "attempts": attempts, "error": None}
        except Exception as exc:
            attempts.append({"attempt": n, "http_status": getattr(getattr(exc, "response", None), "status_code", 0) or 0, "latency_ms": round((time.perf_counter() - started) * 1000, 3), "model": model, "success": False, "error": f"{type(exc).__name__}: {exc}"})
            if n < max_attempts:
                await asyncio.sleep(1.0)
    return {"answer": None, "usable": False, "latency_ms": sum(a["latency_ms"] for a in attempts), "http_status": 0, "model": model, "attempts": attempts, "error": attempts[-1]["error"]}

async def main() -> None:
    cfg = json.loads((STUDY / "retrieval_ablation_config.json").read_text(encoding="utf-8"))
    split = json.loads((STUDY / "selection_manifest.json").read_text(encoding="utf-8"))
    bench = read_jsonl(BENCHMARK); by_id = {x["question_id"]: x for x in bench}
    selection = {x["question_id"] for x in split["assignments"] if x["subset"] == "selection"}
    confirmation = [x["question_id"] for x in split["assignments"] if x["subset"] == "confirmation"]
    if len(confirmation) != 60 or selection & set(confirmation): raise RuntimeError("confirmation split invalid")
    stage_rows = read_jsonl(STAGE1 / "results.jsonl"); stage_hash = sha(STAGE1 / "results.jsonl")
    sr = {(x["question_id"], x["retrieval_condition"]): x for x in stage_rows}
    chunks = {x["chunk_id"]: x for x in read_jsonl(CORPUS)}
    evidence = []
    for qid in confirmation:
        for cond in ("R0", "R3"):
            row = sr[(qid, cond)]; ids = row["retrieved_ids"][:4]
            if len(ids) != 4 or any(i not in chunks for i in ids): raise RuntimeError("missing Stage 1 evidence")
            evidence.append({"question_id": qid, "condition": cond, "retrieved_chunk_ids": ids, "source_ids": [chunks[i]["source_id"] for i in ids], "evidence_excerpts": [chunks[i]["text"] for i in ids]})
    evidence_hash = canon(evidence)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "formal_run_manifest.json"
    if not manifest_path.exists():
        order = []
        rng = random.Random(20260903)
        for qid in confirmation:
            pair = ["R0", "R3"]; rng.shuffle(pair)
            for cond in pair: order.append({"sequence": len(order)+1, "question_id": qid, "condition": cond, "stage": "stage2"})
        order_hash = canon(order)
        (OUT / "execution_order.json").write_text(json.dumps(order, indent=2)+"\n", encoding="utf-8")
        (OUT / "stage2_evidence_manifest.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        manifest = {"status": "LOCKED_BEFORE_FIRST_QWEN_CALL", "stage": "stage2_generation", "benchmark_sha256": sha(BENCHMARK), "corpus_sha256": sha(CORPUS), "split_sha256": sha(STUDY/"selection_manifest.json"), "stage1_results_sha256": stage_hash, "evidence_manifest_sha256": evidence_hash, "qwen_model": "Qwen/Qwen3-8B", "prompt_hash": canon({"prompt": "backend/orchestration/workbench.py::_agent_prompt", "temperature": 0.0, "max_tokens": 384}), "execution_order_sha256": order_hash, "planned_executions": 120, "retry_policy": {"maximum_attempts": 2, "fallback": "forbidden"}, "embedding_calls": 0, "reranker_calls": 0}
        manifest_path.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    order = json.loads((OUT / "execution_order.json").read_text(encoding="utf-8")); existing = read_jsonl(OUT/"results.jsonl") if (OUT/"results.jsonl").exists() else []; done = {(x["question_id"], x["condition"]) for x in existing}
    key, base, model, provider = load_key()
    if not key: raise RuntimeError("LLM_API_KEY is missing")
    lock = asyncio.Semaphore(4)
    async def one(entry):
        q = by_id[entry["question_id"]]; ev = next(x for x in evidence if x["question_id"] == entry["question_id"] and x["condition"] == entry["condition"])
        system, prompt = build_prompt(q["question"], [{"text": t} for t in ev["evidence_excerpts"]])
        async with lock: pred = await call_llm(key, base, model, system, prompt)
        return {**entry, "question": q["question"], "answer": pred["answer"], "usable": pred["usable"], "latency_ms": pred["latency_ms"], "http_status": pred["http_status"], "model_actually_called": pred["model"], "provider": provider, "retrieved_chunk_ids": ev["retrieved_chunk_ids"], "source_ids": ev["source_ids"], "citation_ids": ev["retrieved_chunk_ids"], "provider_attempts": pred["attempts"], "retry_count": len(pred["attempts"])-1, "error": pred["error"], "benchmark_sha256": sha(BENCHMARK), "stage1_results_sha256": stage_hash, "evidence_manifest_sha256": evidence_hash}
    pending = [e for e in order if (e["question_id"], e["condition"]) not in done]
    results_path = OUT/"results.jsonl"; attempts_path = OUT/"provider_attempts.jsonl"
    for fut in asyncio.as_completed([one(e) for e in pending]):
        row = await fut
        with results_path.open("a", encoding="utf-8") as h: h.write(json.dumps(row, ensure_ascii=False)+"\n")
        with attempts_path.open("a", encoding="utf-8") as h:
            for a in row["provider_attempts"]: h.write(json.dumps({"question_id": row["question_id"], "condition": row["condition"], **a}, ensure_ascii=False)+"\n")
    rows = read_jsonl(results_path)
    if len(rows) != 120 or len({(r["question_id"], r["condition"]) for r in rows}) != 120: raise RuntimeError("Stage 2 row invariant failed")
    # Objective citation metrics use the system-attached provenance IDs; semantic scoring is deferred.
    metrics = {}
    for cond in ("R0", "R3"):
        rr = [r for r in rows if r["condition"] == cond]; usable = [r for r in rr if r["usable"]]
        recalls=[]; precisions=[]
        for r in usable:
            gold=set(by_id[r["question_id"]]["preferred_evidence_ids"]); cited=set(r["citation_ids"])
            recalls.append(len(gold & cited)/max(1,len(gold))); precisions.append(len(gold & cited)/max(1,len(cited)))
        metrics[cond] = {"usable": len(usable), "total": len(rr), "usable_rate": len(usable)/len(rr), "mean_latency_ms": sum(r["latency_ms"] for r in usable)/len(usable), "citation_recall": sum(recalls)/len(recalls), "citation_precision": sum(precisions)/len(precisions)}
    (OUT/"objective_metrics.json").write_text(json.dumps(metrics, indent=2)+"\n", encoding="utf-8")
    # Blinded packet: IDs are randomized and condition labels are omitted.
    rng = random.Random(20260903); packet=[]
    for r in rows:
        q = by_id[r["question_id"]]
        for i, fact in enumerate(q["gold_facts"]):
            packet.append({"review_item_id": canon({"qid":r["question_id"],"cond":r["condition"],"i":i}), "question_id": r["question_id"], "blinded_answer_id": canon({"qid":r["question_id"],"cond":r["condition"],"salt":rng.random()}), "question": q["question"], "gold_atomic_fact": fact["fact"], "supplied_source_evidence": "\n\n".join(ev for ev in next(x for x in evidence if x["question_id"]==r["question_id"] and x["condition"]==r["condition"])["evidence_excerpts"]), "generated_answer": r["answer"], "review_label": "", "review_reason": "", "reviewer_confidence": ""})
    with (OUT/"blinded_semantic_review.csv").open("w", newline="", encoding="utf-8") as h:
        w=csv.DictWriter(h, fieldnames=list(packet[0])); w.writeheader(); w.writerows(packet)
    (OUT/"semantic_review_instructions.md").write_text("Review each answer against the supplied atomic fact and evidence. Label SUPPORTED, PARTIALLY_SUPPORTED, NOT_SUPPORTED, or CONTRADICTED. Do not infer condition identity or expected performance. Return the CSV with review_label, review_reason, and reviewer_confidence filled.", encoding="utf-8")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8")); manifest.update({"status":"STAGE_2_GENERATION_COMPLETE_AWAITING_SEMANTIC_REVIEW","completed_executions":len(rows),"qwen_calls":sum(len(r["provider_attempts"]) for r in rows),"usable":sum(bool(r["usable"]) for r in rows),"embedding_calls":0,"reranker_calls":0}); manifest_path.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"rows":len(rows),"metrics":metrics,"review_rows":len(packet),"evidence_manifest_sha256":evidence_hash}, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
