from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FORMAL = HERE / "formal_v1_3"
ABORTED_V12 = HERE / "formal_aborted_v1_2"
ABORTED_V11 = HERE / "formal_aborted_v1_1"
EARLIER_ABORTED_FORMAL = HERE / "formal_aborted_v1"
CONFIG_PATH = HERE / "study_config.json"
BENCHMARK_PATH = ROOT / "research/benchmarks/tcm_gold_rq4_v1/benchmark_rq4_v1_frozen.jsonl"
CORPUS_PATH = ROOT / "research/corpus/tcm_v1/chunks.jsonl"
EVIDENCE_PATH = HERE / "frozen_evidence_manifest.json"
ROLE_ROTATION_PATH = HERE / "role_rotation_manifest.json"
EXECUTION_PLAN_PATH = HERE / "execution_plan.json"
PREREGISTRATION_PATH = HERE / "preregistration_manifest.json"
PROTECTED_PATH = HERE / "protected_artifacts.json"

ENDPOINT = "https://api.siliconflow.cn/v1"
APPROVED_MODELS = (
    "Qwen/Qwen3-8B",
    "THUDM/GLM-Z1-9B-0414",
    "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
)
FIXED_CONSENSUS_MODEL = "Qwen/Qwen3-8B"
PROVIDER_READ_TIMEOUT_SECONDS = 240.0
COMMON_PROVIDER_TIMEOUT = httpx.Timeout(connect=30.0, read=PROVIDER_READ_TIMEOUT_SECONDS, write=30.0, pool=30.0)

# Import existing study components
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "backend"))
import prompt_templates as prompts
import review_packet as review
import runner
import structured_output as structured


class TerminalSlotFailure(RuntimeError):
    def __init__(self, *, question_id: str, condition: str, stage: str, seat: str, model_id: str, attempts: int, last_error: Exception | None) -> None:
        super().__init__(f"Provider slot failed terminally after {attempts} attempts: {stage} seat {seat} model {model_id}: {last_error}")
        self.question_id = question_id
        self.condition = condition
        self.stage = stage
        self.seat = seat
        self.model_id = model_id
        self.attempts = attempts
        self.last_error = last_error


class SystemicTruncationStop(RuntimeError):
    pass


class FormalRunnerLock:
    """Non-blocking OS lock; the lock file persists but carries no run state."""

    def __init__(self, formal_dir: Path):
        self.path = formal_dir.with_name(formal_dir.name + ".runner.lock")
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, "a+b")
        if self.path.stat().st_size == 0:
            self.handle.write(b"\0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            self.handle = None
            raise RuntimeError("ANOTHER_FORMAL_RUNNER_IS_ACTIVE") from exc
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.handle is None:
            return
        self.handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        self.handle = None


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json_hash(val: Any) -> str:
    return hashlib.sha256(
        json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def load_api_key() -> str:
    load_dotenv(ROOT / "backend/.env", override=False)
    key = os.getenv("LLM_API_KEY", "").strip()
    if not key:
        raise RuntimeError("LLM_API_KEY is missing from environment")
    return key


def validate_preflight() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    
    # 1. Hashes
    bench_sha = sha256_file(BENCHMARK_PATH)
    if bench_sha != config["benchmark"]["sha256"]:
        raise RuntimeError(f"Benchmark hash mismatch: {bench_sha} != {config['benchmark']['sha256']}")
    
    corp_sha = sha256_file(CORPUS_PATH)
    if corp_sha != config["corpus"]["sha256"]:
        raise RuntimeError(f"Corpus hash mismatch: {corp_sha} != {config['corpus']['sha256']}")
    
    ev_sha = sha256_file(EVIDENCE_PATH)
    ev_manifest = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    if ev_manifest["questions"] != 100 or ev_manifest["retrieval"] != "R0" or ev_manifest["top_k"] != 4:
        raise RuntimeError("Evidence manifest invalid")
    
    rot_sha = sha256_file(ROLE_ROTATION_PATH)
    if rot_sha != "21144519a963345795678d45123b1525840fa2969831e3915541e7f31443d705":
        raise RuntimeError(f"Role rotation manifest hash mismatch: {rot_sha}")
    
    exec_sha = sha256_file(EXECUTION_PLAN_PATH)
    plan_data = json.loads(EXECUTION_PLAN_PATH.read_text(encoding="utf-8"))
    if len(plan_data["order"]) != 200:
        raise RuntimeError(f"Execution plan must have exactly 200 items, got {len(plan_data['order'])}")
    
    # 2. Benchmark counts
    bench_rows = [json.loads(line) for line in BENCHMARK_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(bench_rows) != 100 or sum(len(x["gold_facts"]) for x in bench_rows) != 232:
        raise RuntimeError("Benchmark count mismatch (expected 100 questions, 232 gold facts)")
    
    # 3. Model IDs and Free-only check
    approved = set(APPROVED_MODELS)
    if set(config["free_only"]["approved_non_pro_ids"]) != approved:
        raise RuntimeError("Approved model IDs mismatch")
    if any(m.casefold().startswith("pro/") for m in approved):
        raise RuntimeError("Pro models forbidden")
    
    # 4. Protected artifacts
    runner.validate_protected()
    
    # 5. Prompt bundle hash
    prompt_bundle_sha = sha256_text(prompts.canonical_prompt_bundle())
    prereg = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))
    if prompt_bundle_sha != prereg["prompt_bundle_sha256"]:
        raise RuntimeError("Prompt bundle hash mismatch")
    
    return {
        "benchmark_sha256": bench_sha,
        "corpus_sha256": corp_sha,
        "evidence_manifest_sha256": ev_sha,
        "role_rotation_manifest_sha256": rot_sha,
        "execution_plan_sha256": exec_sha,
        "prompt_bundle_sha256": prompt_bundle_sha,
        "study_config_sha256": sha256_file(CONFIG_PATH),
        "structured_output_sha256": sha256_file(HERE / "structured_output.py"),
        "runner_sha256": sha256_file(HERE / "runner.py"),
        "formal_runner_sha256": sha256_file(Path(__file__).resolve()),
    }


class FormalExecutionRunner:
    def __init__(self, api_key: str, *, formal_dir: Path = FORMAL, sleep_func=asyncio.sleep):
        self.api_key = api_key
        self.formal_dir = formal_dir
        self._sleep = sleep_func
        self.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.benchmark_by_qid = {
            x["question_id"]: x
            for x in [json.loads(line) for line in BENCHMARK_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        }
        ev_data = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        self.evidence_by_qid = {x["question_id"]: x for x in ev_data["items"]}
        plan_data = json.loads(EXECUTION_PLAN_PATH.read_text(encoding="utf-8"))
        self.execution_order = plan_data["order"]

        # Semaphores for strict concurrency limit = 1 per model ID
        self.semaphores = {
            m: asyncio.Semaphore(1)
            for m in APPROVED_MODELS
        }

        self.formal_dir.mkdir(parents=True, exist_ok=True)
        self.attempts_path = self.formal_dir / "provider_attempts.jsonl"
        self.stage_outputs_path = self.formal_dir / "stage_outputs.jsonl"
        self.results_path = self.formal_dir / "formal_results.jsonl"
        self.terminal_path = self.formal_dir / "terminal_conditions.jsonl"
        self.progress_path = self.formal_dir / "run_progress.json"

        # Stage cache for intra-condition resumption
        self.stage_cache: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        if self.stage_outputs_path.exists():
            for line in self.stage_outputs_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        obj = json.loads(line)
                        qid = obj["question_id"]
                        cond = obj["condition"]
                        stg = obj["stage"]
                        sub_key = f"{obj['seat']}_to_{obj['target_seat']}" if stg == "critique" else obj["seat"]
                        self.stage_cache[(qid, cond, stg, sub_key)] = obj
                    except Exception:
                        pass

    async def call_provider_slot(
        self,
        client: httpx.AsyncClient,
        *,
        question_id: str,
        condition: str,
        stage: str,
        seat: str,
        role: str,
        model_id: str,
        system: str,
        user: str,
        max_tokens: int,
        schema_name: str,
        allowed_source_ids: set[str],
        allowed_target_seats: set[str] = ("A", "B", "C"),
        critique_inputs: list[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, Any], structured.StructuredOutput]:
        # Pre-call gold and leakage validation
        runner.validate_no_gold_leakage({"system": system, "user": user})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "stream": False,
            "enable_thinking": False,
        }

        # Maximum 2 attempts per formal generation slot
        last_error = None
        for attempt in (1, 2):
            started = time.perf_counter()
            record: dict[str, Any] = {
                "question_id": question_id,
                "condition": condition,
                "stage": stage,
                "seat": seat,
                "role": role,
                "requested_model": model_id,
                "endpoint": ENDPOINT,
                "timestamp_utc": now_utc(),
                "attempt": attempt,
                "fallback_used": False,
                "enable_thinking_requested": False,
            }

            try:
                # Acquire model semaphore to guarantee max concurrency = 1 per model
                async with self.semaphores[model_id]:
                    # Polite inter-request spacing to avoid tight bursts
                    await self._sleep(0.3)
                    response = await client.post(
                        f"{ENDPOINT}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=COMMON_PROVIDER_TIMEOUT,
                    )

                latency = round(time.perf_counter() - started, 6)
                record["latency_seconds"] = latency
                record["http_status"] = response.status_code

                # Handle rate-limit and server error backoff
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = response.headers.get("retry-after")
                    backoff = float(retry_after) if retry_after and retry_after.isdigit() else 5.0
                    record["success"] = False
                    record["error"] = f"HTTP_{response.status_code}: {response.text[:200]}"
                    self._append_jsonl(self.attempts_path, record)
                    last_error = RuntimeError(record["error"])
                    if attempt == 1:
                        await self._sleep(backoff)
                    continue

                response.raise_for_status()
                data = response.json()
                returned_model = data.get("model")
                record["returned_model"] = returned_model
                if returned_model != model_id:
                    raise ValueError(f"model substitution mismatch: requested {model_id}, returned {returned_model!r}")

                message = data["choices"][0]["message"]
                content = structured.visible_text_only(message)
                record["raw_visible_text"] = content
                record["raw_text_hash"] = sha256_text(content)

                reasoning = message.get("reasoning_content")
                record["reasoning_content_field_present"] = "reasoning_content" in message
                record["reasoning_content_nonempty"] = isinstance(reasoning, str) and bool(reasoning.strip())
                record["usage"] = data.get("usage", {})
                record["finish_reason"] = data["choices"][0].get("finish_reason")

                if record["finish_reason"] == "length":
                    raise ValueError("response truncated at max_tokens")

                # Parse and validate with common parser
                parsed_result = structured.parse_and_validate(
                    content,
                    schema=schema_name,
                    allowed_source_ids=allowed_source_ids,
                    allowed_target_seats=allowed_target_seats,
                    critique_inputs=critique_inputs,
                )
                record.update(parsed_result.audit)
                record["success"] = True
                record["error"] = None
                self._append_jsonl(self.attempts_path, record)

                return record, parsed_result

            except Exception as exc:
                latency = round(time.perf_counter() - started, 6)
                record.setdefault("latency_seconds", latency)
                record["success"] = False
                record["error"] = f"{type(exc).__name__}: {exc}"
                last_error = exc
                self._append_jsonl(self.attempts_path, record)

                if attempt == 1:
                    # Retry once after short backoff
                    await self._sleep(2.0)
                    continue

        raise TerminalSlotFailure(
            question_id=question_id,
            condition=condition,
            stage=stage,
            seat=seat,
            model_id=model_id,
            attempts=2,
            last_error=last_error,
        )

    def _append_jsonl(self, path: Path, data: dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def load_completed_identities(self) -> set[str]:
        if not self.results_path.exists():
            return set()
        completed = set()
        for line in self.results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    obj = json.loads(line)
                    completed.add(obj["resume_identity"])
                except Exception:
                    pass
        return completed

    async def execute_canonical_condition(
        self,
        client: httpx.AsyncClient,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        qid = item["question_id"]
        cond = item["condition"]
        resume_id = item["resume_identity"]
        rotation_id = item["rotation_id"]
        assignment = item["agent_assignment"]
        consensus_model = item["consensus_model"]

        question_text = self.benchmark_by_qid[qid]["question"]
        evidence_item = self.evidence_by_qid[qid]
        evidence_list = evidence_item["evidence"]
        allowed_sources = set(evidence_item["ordered_chunk_ids"]) | set(evidence_item["source_ids"])

        # Seat mapping
        seats = ["A", "B", "C"]
        seat_roles = {seat: asgn["role"] for seat, asgn in zip(seats, assignment)}
        seat_models = {seat: asgn["model"] for seat, asgn in zip(seats, assignment)}

        stage_attempts_count = 0
        stage_retries_count = 0
        model_counts: dict[str, int] = {m: 0 for m in APPROVED_MODELS}
        latencies_list: list[float] = []

        # -------------------------------------------------------------
        # STAGE 1: INITIAL (Seats A, B, C)
        # -------------------------------------------------------------
        async def run_initial(seat: str):
            role = seat_roles[seat]
            model = seat_models[seat]
            key = (qid, cond, "initial", seat)
            if key in self.stage_cache:
                cached = self.stage_cache[key]
                rec = {
                    "requested_model": cached["model_id"],
                    "attempt": cached.get("attempt", 1),
                    "latency_seconds": 0.0,
                    "timestamp_utc": cached.get("timestamp_utc", now_utc()),
                }
                return seat, rec, cached["parsed_value"], cached["audit"]

            user = (
                f"Supplied evidence: {json.dumps(evidence_list, ensure_ascii=False)}\n"
                f"Question: {question_text}\n"
                f"Role: {role}\n"
                f"Role instruction: {prompts.ROLE_INSTRUCTIONS[role]}"
            )
            rec, res = await self.call_provider_slot(
                client,
                question_id=qid,
                condition=cond,
                stage="initial",
                seat=seat,
                role=role,
                model_id=model,
                system=prompts.INITIAL_SYSTEM,
                user=user,
                max_tokens=self.config["generation"]["initial_max_tokens"],
                schema_name="initial",
                allowed_source_ids=allowed_sources,
            )
            stage_out = {
                "question_id": qid,
                "condition": cond,
                "resume_identity": resume_id,
                "stage": "initial",
                "seat": seat,
                "role": role,
                "model_id": model,
                "attempt": rec["attempt"],
                "raw_text": rec["raw_visible_text"],
                "normalized_text": res.normalized_text,
                "parsed_value": res.value,
                "audit": res.audit,
                "timestamp_utc": rec["timestamp_utc"],
            }
            self._append_jsonl(self.stage_outputs_path, stage_out)
            self.stage_cache[key] = stage_out
            return seat, rec, res.value, res.audit

        initial_results = await asyncio.gather(*(run_initial(s) for s in seats))
        initial_map = {seat: val for seat, rec, val, aud in initial_results}
        initial_audits = {seat: aud for seat, rec, val, aud in initial_results}
        for _, rec, _, _ in initial_results:
            model_counts[rec["requested_model"]] += 1
            latencies_list.append(rec["latency_seconds"])
            stage_attempts_count += rec["attempt"]
            if rec["attempt"] > 1:
                stage_retries_count += 1

        # -------------------------------------------------------------
        # STAGE 2: CRITIQUE (A->B, B->C, C->A)
        # -------------------------------------------------------------
        critique_pairs = [
            ("A", "B"),
            ("B", "C"),
            ("C", "A"),
        ]

        async def run_critique(src_seat: str, tgt_seat: str):
            src_model = seat_models[src_seat]
            tgt_initial = initial_map[tgt_seat]
            key = (qid, cond, "critique", f"{src_seat}_to_{tgt_seat}")
            if key in self.stage_cache:
                cached = self.stage_cache[key]
                rec = {
                    "requested_model": cached["model_id"],
                    "attempt": cached.get("attempt", 1),
                    "latency_seconds": 0.0,
                    "timestamp_utc": cached.get("timestamp_utc", now_utc()),
                }
                return (src_seat, tgt_seat), rec, cached["parsed_value"], cached["audit"]

            user = (
                f"Supplied evidence: {json.dumps(evidence_list, ensure_ascii=False)}\n"
                f"Question: {question_text}\n"
                f"Target seat {tgt_seat} visible answer: {json.dumps(tgt_initial, ensure_ascii=False)}\n"
                f"Target exactly seat {tgt_seat}."
            )
            rec, res = await self.call_provider_slot(
                client,
                question_id=qid,
                condition=cond,
                stage="critique",
                seat=src_seat,
                role=seat_roles[src_seat],
                model_id=src_model,
                system=prompts.CRITIQUE_SYSTEM,
                user=user,
                max_tokens=self.config["generation"]["critique_max_tokens"],
                schema_name="critique",
                allowed_source_ids=allowed_sources,
                allowed_target_seats={tgt_seat},
            )
            stage_out = {
                "question_id": qid,
                "condition": cond,
                "resume_identity": resume_id,
                "stage": "critique",
                "seat": src_seat,
                "target_seat": tgt_seat,
                "role": seat_roles[src_seat],
                "model_id": src_model,
                "attempt": rec["attempt"],
                "raw_text": rec["raw_visible_text"],
                "normalized_text": res.normalized_text,
                "parsed_value": res.value,
                "audit": res.audit,
                "timestamp_utc": rec["timestamp_utc"],
            }
            self._append_jsonl(self.stage_outputs_path, stage_out)
            self.stage_cache[key] = stage_out
            return (src_seat, tgt_seat), rec, res.value, res.audit

        critique_results = await asyncio.gather(*(run_critique(s, t) for s, t in critique_pairs))
        critique_map = {f"{s}_to_{t}": val for (s, t), rec, val, aud in critique_results}
        critique_audits = {f"{s}_to_{t}": aud for (s, t), rec, val, aud in critique_results}
        for _, rec, _, _ in critique_results:
            model_counts[rec["requested_model"]] += 1
            latencies_list.append(rec["latency_seconds"])
            stage_attempts_count += rec["attempt"]
            if rec["attempt"] > 1:
                stage_retries_count += 1

        # -------------------------------------------------------------
        # STAGE 3: REVISION (Seats A, B, C)
        # -------------------------------------------------------------
        critique_received_by_seat = {
            "A": critique_map["C_to_A"],
            "B": critique_map["A_to_B"],
            "C": critique_map["B_to_C"],
        }

        async def run_revision(seat: str):
            role = seat_roles[seat]
            model = seat_models[seat]
            own_init = initial_map[seat]
            crit = critique_received_by_seat[seat]
            key = (qid, cond, "revision", seat)
            if key in self.stage_cache:
                cached = self.stage_cache[key]
                rec = {
                    "requested_model": cached["model_id"],
                    "attempt": cached.get("attempt", 1),
                    "latency_seconds": 0.0,
                    "timestamp_utc": cached.get("timestamp_utc", now_utc()),
                }
                return seat, rec, cached["parsed_value"], cached["audit"]

            user = (
                f"Supplied evidence: {json.dumps(evidence_list, ensure_ascii=False)}\n"
                f"Question: {question_text}\n"
                f"Role: {role}\n"
                f"Role instruction: {prompts.ROLE_INSTRUCTIONS[role]}\n"
                f"Own initial answer: {json.dumps(own_init, ensure_ascii=False)}\n"
                f"Peer critique: {json.dumps(crit, ensure_ascii=False)}"
            )
            rec, res = await self.call_provider_slot(
                client,
                question_id=qid,
                condition=cond,
                stage="revision",
                seat=seat,
                role=role,
                model_id=model,
                system=prompts.REVISION_SYSTEM,
                user=user,
                max_tokens=self.config["generation"]["revision_max_tokens"],
                schema_name="revision",
                allowed_source_ids=allowed_sources,
                critique_inputs=[crit],
            )
            stage_out = {
                "question_id": qid,
                "condition": cond,
                "resume_identity": resume_id,
                "stage": "revision",
                "seat": seat,
                "role": role,
                "model_id": model,
                "attempt": rec["attempt"],
                "raw_text": rec["raw_visible_text"],
                "normalized_text": res.normalized_text,
                "parsed_value": res.value,
                "audit": res.audit,
                "timestamp_utc": rec["timestamp_utc"],
            }
            self._append_jsonl(self.stage_outputs_path, stage_out)
            self.stage_cache[key] = stage_out
            return seat, rec, res.value, res.audit

        revision_results = await asyncio.gather(*(run_revision(s) for s in seats))
        revision_map = {seat: val for seat, rec, val, aud in revision_results}
        revision_audits = {seat: aud for seat, rec, val, aud in revision_results}
        for _, rec, _, _ in revision_results:
            model_counts[rec["requested_model"]] += 1
            latencies_list.append(rec["latency_seconds"])
            stage_attempts_count += rec["attempt"]
            if rec["attempt"] > 1:
                stage_retries_count += 1

        # -------------------------------------------------------------
        # STAGE 4: CONSENSUS (Qwen/Qwen3-8B)
        # -------------------------------------------------------------
        revisions_for_consensus = [
            {
                "seat": s,
                "role": seat_roles[s],
                "revised_answer": revision_map[s]["revised_answer"],
                "evidence_ids": revision_map[s]["evidence_ids"],
            }
            for s in seats
        ]
        consensus_user = (
            f"Supplied evidence: {json.dumps(evidence_list, ensure_ascii=False)}\n"
            f"Question: {question_text}\n"
            f"Visible revisions:\n{json.dumps(revisions_for_consensus, ensure_ascii=False)}"
        )
        forbidden = ("m1", "m2", "homogeneous", "heterogeneous", "qwen", "glm", "deepseek")
        if any(token in consensus_user.casefold() for token in forbidden):
            raise RuntimeError("Consensus prompt leaks condition or model identity")

        cons_key = (qid, cond, "consensus", "consensus")
        if cons_key in self.stage_cache:
            cached = self.stage_cache[cons_key]
            cons_rec = {
                "requested_model": cached["model_id"],
                "attempt": cached.get("attempt", 1),
                "latency_seconds": 0.0,
                "timestamp_utc": cached.get("timestamp_utc", now_utc()),
            }
            cons_value = cached["parsed_value"]
            cons_audit = cached["audit"]
        else:
            cons_rec, cons_res = await self.call_provider_slot(
                client,
                question_id=qid,
                condition=cond,
                stage="consensus",
                seat="consensus",
                role="consensus",
                model_id=consensus_model,
                system=prompts.CONSENSUS_SYSTEM,
                user=consensus_user,
                max_tokens=self.config["generation"]["consensus_max_tokens"],
                schema_name="consensus",
                allowed_source_ids=allowed_sources,
            )
            consensus_out = {
                "question_id": qid,
                "condition": cond,
                "resume_identity": resume_id,
                "stage": "consensus",
                "seat": "consensus",
                "role": "consensus",
                "model_id": consensus_model,
                "attempt": cons_rec["attempt"],
                "raw_text": cons_rec["raw_visible_text"],
                "normalized_text": cons_res.normalized_text,
                "parsed_value": cons_res.value,
                "audit": cons_res.audit,
                "timestamp_utc": cons_rec["timestamp_utc"],
            }
            self._append_jsonl(self.stage_outputs_path, consensus_out)
            self.stage_cache[cons_key] = consensus_out
            cons_value = cons_res.value
            cons_audit = cons_res.audit

        model_counts[cons_rec["requested_model"]] += 1
        latencies_list.append(cons_rec["latency_seconds"])
        stage_attempts_count += cons_rec["attempt"]
        if cons_rec["attempt"] > 1:
            stage_retries_count += 1

        # Compute objective question-condition metrics
        final_answer = cons_value["answer"]
        cited_ids = cons_value["evidence_ids"]
        retrieved_ids = evidence_item["ordered_chunk_ids"]
        retrieved_set = set(retrieved_ids)
        cited_set = set(cited_ids)

        prec = len(cited_set & retrieved_set) / len(cited_set) if cited_set else 0.0
        rec = len(cited_set & retrieved_set) / len(retrieved_set) if retrieved_set else 0.0
        usable = bool(final_answer.strip() and cited_ids and (cited_set <= allowed_sources))

        # Process metrics
        init_answers = [initial_map[s]["answer"].strip() for s in seats]
        init_disagreement = len(set(init_answers)) > 1
        rev_changed = {s: (revision_map[s]["revised_answer"].strip() != initial_map[s]["answer"].strip()) for s in seats}
        uptake_counts = {s: len(revision_map[s].get("critique_uptake", [])) for s in seats}
        rev_answers = [revision_map[s]["revised_answer"].strip() for s in seats]
        consensus_changed = final_answer.strip() not in rev_answers

        result_row = {
            "sequence": item["sequence"],
            "question_id": qid,
            "condition": cond,
            "rotation_id": rotation_id,
            "resume_identity": resume_id,
            "agent_assignment": assignment,
            "consensus_model": consensus_model,
            "initial_stage": initial_map,
            "initial_audits": initial_audits,
            "critique_stage": critique_map,
            "critique_audits": critique_audits,
            "revision_stage": revision_map,
            "revision_audits": revision_audits,
            "consensus_stage": cons_value,
            "consensus_audit": cons_audit,
            "final_answer": final_answer,
            "evidence_ids": cited_ids,
            "usable": usable,
            "total_latency_seconds": round(sum(latencies_list), 6),
            "provider_attempts_count": stage_attempts_count,
            "retries_count": stage_retries_count,
            "model_call_counts": model_counts,
            "citations": {
                "retrieved_evidence_ids": retrieved_ids,
                "cited_evidence_ids": cited_ids,
                "citation_precision": round(prec, 6),
                "citation_recall": round(rec, 6),
            },
            "process_data": {
                "initial_disagreement": init_disagreement,
                "revision_changed": rev_changed,
                "critique_uptake_count": uptake_counts,
                "consensus_changed_from_revisions": consensus_changed,
            },
            "timestamp_utc": now_utc(),
        }

        self._append_jsonl(self.results_path, result_row)
        return result_row

    def checkpoint_terminal_condition(self, item: dict[str, Any], failure: TerminalSlotFailure) -> dict[str, Any]:
        attempts = []
        if self.attempts_path.exists():
            attempts = [
                json.loads(line)
                for line in self.attempts_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        condition_attempts = [
            row for row in attempts
            if row.get("question_id") == item["question_id"] and row.get("condition") == item["condition"]
        ]
        terminal = {
            "stage": failure.stage,
            "seat": failure.seat,
            "model": failure.model_id,
            "attempts": failure.attempts,
            "last_error": f"{type(failure.last_error).__name__}: {failure.last_error}",
            "later_dependent_stages_skipped": True,
        }
        row = {
            "sequence": item["sequence"],
            "question_id": item["question_id"],
            "condition": item["condition"],
            "rotation_id": item["rotation_id"],
            "resume_identity": item["resume_identity"],
            "agent_assignment": item["agent_assignment"],
            "consensus_model": item["consensus_model"],
            "usable": False,
            "terminal_failure": terminal,
            "provider_attempts_count": len(condition_attempts),
            "retries_count": sum(1 for attempt in condition_attempts if attempt.get("attempt") == 2),
            "final_answer": "",
            "evidence_ids": [],
            "timestamp_utc": now_utc(),
        }
        self._append_jsonl(self.terminal_path, {**row, "checkpoint_status": "TERMINAL_UNUSABLE_CHECKPOINTED"})
        self._append_jsonl(self.results_path, row)
        return row

    def write_progress(self, completed: set[str], sequence: int) -> None:
        rows = [
            json.loads(line)
            for line in self.results_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ] if self.results_path.exists() else []
        progress = {
            "total_canonical": 200,
            "completed_canonical": len(completed),
            "current_sequence": sequence,
            "completed_m1": sum(row["condition"] == "M1" for row in rows),
            "completed_m2": sum(row["condition"] == "M2" for row in rows),
            "usable_canonical": sum(bool(row.get("usable")) for row in rows),
            "terminal_unusable_canonical": sum("terminal_failure" in row for row in rows),
            "timestamp_utc": now_utc(),
        }
        self.progress_path.write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")

    def enforce_systemic_truncation_gate(self) -> None:
        rule = self.config["systemic_truncation_stop_rule"]
        attempts = [json.loads(line) for line in self.attempts_path.read_text(encoding="utf-8").splitlines() if line.strip()] if self.attempts_path.exists() else []
        terminals = [json.loads(line) for line in self.terminal_path.read_text(encoding="utf-8").splitlines() if line.strip()] if self.terminal_path.exists() else []
        for stage in ("initial", "critique", "revision", "consensus"):
            length_count = sum(row.get("stage") == stage and row.get("finish_reason") == "length" for row in attempts)
            terminal_count = sum(
                row.get("terminal_failure", {}).get("stage") == stage
                and "truncated at max_tokens" in row.get("terminal_failure", {}).get("last_error", "")
                for row in terminals
            )
            if length_count >= rule["length_attempts_same_stage"] or terminal_count >= rule["terminal_truncation_conditions_same_stage"]:
                report = {
                    "status": "ABORTED_SYSTEMIC_TRUNCATION",
                    "stage": stage,
                    "length_attempts": length_count,
                    "terminal_truncation_conditions": terminal_count,
                    "rule": rule,
                    "timestamp_utc": now_utc(),
                }
                (self.formal_dir / "systemic_truncation_stop.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                raise SystemicTruncationStop(f"Systemic truncation stop rule reached at {stage}: {length_count} length attempts, {terminal_count} terminal conditions")

    async def run(self) -> None:
        completed = self.load_completed_identities()
        print(f"Loaded {len(completed)} existing completed condition results.")

        async with httpx.AsyncClient(timeout=COMMON_PROVIDER_TIMEOUT) as client:
            for idx, item in enumerate(self.execution_order, 1):
                resume_id = item["resume_identity"]
                if resume_id in completed:
                    continue

                seq = item["sequence"]
                qid = item["question_id"]
                cond = item["condition"]
                print(f"[{seq}/200] Executing {qid} {cond} (rotation {item['rotation_id']})...")

                try:
                    await self.execute_canonical_condition(client, item)
                except TerminalSlotFailure as failure:
                    self.checkpoint_terminal_condition(item, failure)
                completed.add(resume_id)
                self.write_progress(completed, seq)
                self.enforce_systemic_truncation_gate()

        print(f"Execution complete. Total completed canonical rows: {len(completed)}")


def compute_objective_and_process_metrics() -> tuple[dict[str, Any], dict[str, Any]]:
    results = [json.loads(line) for line in (FORMAL / "formal_results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    attempts = [json.loads(line) for line in (FORMAL / "provider_attempts.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    m1_rows = [r for r in results if r["condition"] == "M1"]
    m2_rows = [r for r in results if r["condition"] == "M2"]
    paired_usable_qids = {
        qid for qid in {r["question_id"] for r in results}
        if {r["condition"] for r in results if r["question_id"] == qid and r.get("usable")} == {"M1", "M2"}
    }
    m1_quality_rows = [r for r in m1_rows if r["question_id"] in paired_usable_qids]
    m2_quality_rows = [r for r in m2_rows if r["question_id"] in paired_usable_qids]

    # Usability
    m1_usable = sum(r["usable"] for r in m1_rows)
    m2_usable = sum(r["usable"] for r in m2_rows)

    # Citation metrics
    m1_recalls = [r["citations"]["citation_recall"] for r in m1_quality_rows]
    m2_recalls = [r["citations"]["citation_recall"] for r in m2_quality_rows]
    m1_precisions = [r["citations"]["citation_precision"] for r in m1_quality_rows]
    m2_precisions = [r["citations"]["citation_precision"] for r in m2_quality_rows]

    # Latencies
    m1_latencies = [r["total_latency_seconds"] for r in m1_quality_rows]
    m2_latencies = [r["total_latency_seconds"] for r in m2_quality_rows]

    # Provider metrics by model
    model_stats = {}
    for m in APPROVED_MODELS:
        m_attempts = [a for a in attempts if a["requested_model"] == m]
        m_successes = [a for a in m_attempts if a["success"]]
        retries = sum(1 for a in m_attempts if a["attempt"] > 1)
        failures = sum(1 for a in m_attempts if not a["success"])
        lats = [a["latency_seconds"] for a in m_successes if "latency_seconds" in a]
        actions: dict[str, int] = {}
        for a in m_successes:
            act = a.get("normalization_action", "UNKNOWN")
            actions[act] = actions.get(act, 0) + 1

        prompt_toks = sum(a.get("usage", {}).get("prompt_tokens", 0) for a in m_successes)
        comp_toks = sum(a.get("usage", {}).get("completion_tokens", 0) for a in m_successes)
        reasoning_toks = sum(a.get("usage", {}).get("completion_tokens_details", {}).get("reasoning_tokens", 0) for a in m_successes)

        model_stats[m] = {
            "total_attempts": len(m_attempts),
            "successful_calls": len(m_successes),
            "retries": retries,
            "failures": failures,
            "mean_latency_seconds": round(sum(lats) / len(lats), 3) if lats else 0.0,
            "normalization_actions": actions,
            "token_usage": {
                "prompt_tokens": prompt_toks,
                "completion_tokens": comp_toks,
                "reasoning_tokens": reasoning_toks,
                "total_tokens": prompt_toks + comp_toks,
            },
        }

    objective = {
        "canonical_executions": len(results),
        "m1_executions": len(m1_rows),
        "m2_executions": len(m2_rows),
        "complete_usable_pairs_for_quality": len(paired_usable_qids),
        "usable_rate": {
            "M1": round(m1_usable / len(m1_rows), 4) if m1_rows else 0.0,
            "M2": round(m2_usable / len(m2_rows), 4) if m2_rows else 0.0,
        },
        "citation_recall": {
            "M1_mean": round(sum(m1_recalls) / len(m1_recalls), 4) if m1_recalls else 0.0,
            "M2_mean": round(sum(m2_recalls) / len(m2_recalls), 4) if m2_recalls else 0.0,
        },
        "citation_precision": {
            "M1_mean": round(sum(m1_precisions) / len(m1_precisions), 4) if m1_precisions else 0.0,
            "M2_mean": round(sum(m2_precisions) / len(m2_precisions), 4) if m2_precisions else 0.0,
        },
        "latency_seconds": {
            "M1_total": round(sum(m1_latencies), 2),
            "M1_mean": round(sum(m1_latencies) / len(m1_latencies), 2) if m1_latencies else 0.0,
            "M2_total": round(sum(m2_latencies), 2),
            "M2_mean": round(sum(m2_latencies) / len(m2_latencies), 2) if m2_latencies else 0.0,
        },
        "provider_by_model": model_stats,
    }

    # Process metrics
    m1_disagreements = sum(r["process_data"]["initial_disagreement"] for r in m1_quality_rows)
    m2_disagreements = sum(r["process_data"]["initial_disagreement"] for r in m2_quality_rows)

    m1_rev_changes = sum(any(r["process_data"]["revision_changed"].values()) for r in m1_quality_rows)
    m2_rev_changes = sum(any(r["process_data"]["revision_changed"].values()) for r in m2_quality_rows)

    m1_cons_changes = sum(r["process_data"]["consensus_changed_from_revisions"] for r in m1_quality_rows)
    m2_cons_changes = sum(r["process_data"]["consensus_changed_from_revisions"] for r in m2_quality_rows)

    process = {
        "initial_disagreement_rate": {
            "M1": round(m1_disagreements / len(m1_quality_rows), 4) if m1_quality_rows else 0.0,
            "M2": round(m2_disagreements / len(m2_quality_rows), 4) if m2_quality_rows else 0.0,
        },
        "any_revision_changed_rate": {
            "M1": round(m1_rev_changes / len(m1_quality_rows), 4) if m1_quality_rows else 0.0,
            "M2": round(m2_rev_changes / len(m2_quality_rows), 4) if m2_quality_rows else 0.0,
        },
        "consensus_changed_from_revisions_rate": {
            "M1": round(m1_cons_changes / len(m1_quality_rows), 4) if m1_quality_rows else 0.0,
            "M2": round(m2_cons_changes / len(m2_quality_rows), 4) if m2_quality_rows else 0.0,
        },
    }

    return objective, process


def generate_blinded_review_packet() -> tuple[Path, Path]:
    results = [json.loads(line) for line in (FORMAL / "formal_results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    benchmark_rows = [json.loads(line) for line in BENCHMARK_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    benchmark = {x["question_id"]: x for x in benchmark_rows}

    paired_usable_qids = {
        qid for qid in {r["question_id"] for r in results}
        if {r["condition"] for r in results if r["question_id"] == qid and r.get("usable")} == {"M1", "M2"}
    }
    review_input = [
        {
            "question_id": r["question_id"],
            "condition": r["condition"],
            "resume_identity": r["resume_identity"],
            "final_answer": r["final_answer"],
        }
        for r in results if r["question_id"] in paired_usable_qids
    ]

    rows, mapping = review.blinded_rows(review_input, benchmark, seed=20260905)

    csv_path = FORMAL / "blinded_semantic_review.csv"
    fieldnames = [
        "review_item_id",
        "blinded_answer_id",
        "question_id",
        "question",
        "gold_atomic_fact",
        "supplied_evidence",
        "generated_answer",
        "review_label",
        "review_reason",
        "reviewer_confidence",
    ]

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            # Ensure labels are strictly blank
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    mapping_path = FORMAL / "blind_mapping.json"
    mapping_path.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")

    return csv_path, mapping_path


def write_semantic_review_instructions() -> Path:
    text = """# Independent Blinded Semantic Review Instructions

## Context and Purpose
This review evaluates the source-grounded agreement of candidate answers with the frozen TCM Benchmark Gold Atomic Facts (RQ4/A3).
The evaluation does NOT assess clinical truth, medical correctness, or prescriptive clinical guidance. It strictly evaluates whether the generated final consensus answer is supported by the supplied corpus evidence and matches the Gold atomic fact.

## Review Rubric
For each row in `blinded_semantic_review.csv`, evaluate the `generated_answer` against the `gold_atomic_fact` and `supplied_evidence`. Assign exactly one `review_label`:

1. **SUPPORTED**:
   - The claim asserted by the Gold atomic fact is fully stated or directly implied by the generated answer in agreement with the supplied evidence.
   - Preserves all essential entity attributes, definitions, or relationships.

2. **PARTIALLY_SUPPORTED**:
   - Some aspects of the Gold atomic fact are present, but important qualifiers, domain boundaries, or details are omitted, incomplete, or vague.

3. **NOT_SUPPORTED**:
   - The claim in the Gold atomic fact is entirely absent from the generated answer, or the answer explicitly states it has no information regarding the claim.

4. **CONTRADICTED**:
   - The generated answer makes an assertion that directly contradicts, negates, or conflicts with the Gold atomic fact.

## Required Review CSV Fields to Populate
For each row:
- `review_label`: Exactly one of `SUPPORTED`, `PARTIALLY_SUPPORTED`, `NOT_SUPPORTED`, `CONTRADICTED`.
- `review_reason`: Brief concise explanation justifying the label.
- `reviewer_confidence`: `HIGH`, `MEDIUM`, or `LOW`.

## Strict Full Recall Rule
A question achieves strict Gold Fact Full Recall if and only if **ALL** of its constituent Gold atomic facts are rated `SUPPORTED`. A single `PARTIALLY_SUPPORTED`, `NOT_SUPPORTED`, or `CONTRADICTED` rating prevents Full Recall for that question.
"""
    path = FORMAL / "semantic_review_instructions.md"
    path.write_text(text, encoding="utf-8")
    return path


def validate_formal_execution() -> dict[str, Any]:
    results_path = FORMAL / "formal_results.jsonl"
    attempts_path = FORMAL / "provider_attempts.jsonl"
    csv_path = FORMAL / "blinded_semantic_review.csv"
    mapping_path = FORMAL / "blind_mapping.json"
    manifest_path = FORMAL / "formal_run_manifest.json"

    results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    attempts = [json.loads(line) for line in attempts_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Canonical validation
    if len(results) != 200:
        raise ValueError(f"Expected 200 canonical results, found {len(results)}")
    
    m1_count = sum(1 for r in results if r["condition"] == "M1")
    m2_count = sum(1 for r in results if r["condition"] == "M2")
    if m1_count != 100 or m2_count != 100:
        raise ValueError(f"Expected 100 M1 and 100 M2, got {m1_count} M1 and {m2_count} M2")
    
    identities = {(r["question_id"], r["condition"]) for r in results}
    if len(identities) != 200:
        raise ValueError(f"Duplicate (question_id, condition) detected: {len(identities)} != 200")
    
    qids = {r["question_id"] for r in results}
    if len(qids) != 100:
        raise ValueError(f"Expected 100 unique questions, found {len(qids)}")
    
    for qid in qids:
        conds = {r["condition"] for r in results if r["question_id"] == qid}
        if conds != {"M1", "M2"}:
            raise ValueError(f"Question {qid} does not have complete paired M1 and M2")

    # Provider validations
    successful_attempts = [a for a in attempts if a["success"]]
    if len(successful_attempts) > 2000:
        raise ValueError(f"Successful generation slots exceed nominal 2,000: {len(successful_attempts)}")
    slot_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for attempt in attempts:
        key = (attempt["question_id"], attempt["condition"], attempt["stage"], attempt["seat"])
        slot_groups.setdefault(key, []).append(attempt)
    if any(len(group) > 2 or max(row["attempt"] for row in group) > 2 for group in slot_groups.values()):
        raise ValueError("Provider slot exceeded the preregistered maximum two attempts")

    retries = sum(1 for a in attempts if a["attempt"] > 1)
    failures = sum(1 for a in attempts if not a["success"])

    # Model IDs validation
    used_models = {a["requested_model"] for a in attempts}
    if not used_models.issubset(set(APPROVED_MODELS)):
        raise ValueError(f"Unauthorized models detected: {used_models - set(APPROVED_MODELS)}")
    
    if any(a.get("fallback_used") for a in attempts):
        raise ValueError("Model fallback detected!")

    terminal_rows = [r for r in results if "terminal_failure" in r]
    if any(r.get("usable") or r["terminal_failure"].get("attempts") != 2 for r in terminal_rows):
        raise ValueError("Terminal condition checkpoint is inconsistent")
    paired_usable_qids = {
        qid for qid in qids
        if {r["condition"] for r in results if r["question_id"] == qid and r.get("usable")} == {"M1", "M2"}
    }

    # Rotation validation
    rotations = [r["rotation_id"] for r in results if r["condition"] == "M2"]
    rot_counts = {1: rotations.count(1), 2: rotations.count(2), 3: rotations.count(3)}
    if rot_counts != {1: 34, 2: 33, 3: 33}:
        raise ValueError(f"Role rotation distribution invalid: {rot_counts}")

    # Blinded review CSV validation
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        review_rows = list(reader)

    benchmark = {row["question_id"]: row for row in [json.loads(line) for line in BENCHMARK_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]}
    expected_review_rows = 2 * sum(len(benchmark[qid]["gold_facts"]) for qid in paired_usable_qids)
    if len(review_rows) != expected_review_rows:
        raise ValueError(f"Expected {expected_review_rows} paired-usable review rows, found {len(review_rows)}")

    if any(r["review_label"] != "" or r["review_reason"] != "" or r["reviewer_confidence"] != "" for r in review_rows):
        raise ValueError("Review labels must be strictly unpopulated!")

    validation_report = {
        "status": "PASS",
        "canonical_executions": len(results),
        "m1_executions": m1_count,
        "m2_executions": m2_count,
        "complete_pairs": len(qids),
        "complete_usable_pairs_for_quality": len(paired_usable_qids),
        "terminal_unusable_conditions": len(terminal_rows),
        "canonical_duplicates": 0,
        "nominal_generation_slots": 2000,
        "successful_generation_slots": len(successful_attempts),
        "total_provider_attempts": len(attempts),
        "retries": retries,
        "failures": failures,
        "fallback_used": False,
        "rotation_distribution": rot_counts,
        "review_rows_count": len(review_rows),
        "review_labels_filled": False,
        "canonical_hashes": {
            "formal_results_sha256": sha256_file(results_path),
            "provider_attempts_sha256": sha256_file(attempts_path),
            "blinded_semantic_review_sha256": sha256_file(csv_path),
            "blind_mapping_sha256": sha256_file(mapping_path),
            "formal_run_manifest_sha256": sha256_file(manifest_path),
        },
        "timestamp_utc": now_utc(),
    }

    (FORMAL / "formal_validation.json").write_text(json.dumps(validation_report, indent=2) + "\n", encoding="utf-8")
    return validation_report


def _strict_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(f"Missing checkpoint artifact: {path.name}")
    output = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSONL in {path.name}:{line_no}") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"Non-object JSONL row in {path.name}:{line_no}")
        output.append(value)
    return output


def _stage_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    suffix = f"{row['seat']}_to_{row['target_seat']}" if row["stage"] == "critique" else row["seat"]
    return row["question_id"], row["condition"], row["stage"], suffix


def validate_resume_checkpoint(formal_dir: Path = FORMAL) -> dict[str, Any]:
    """Validate a non-empty checkpoint without changing it or relaxing scientific invariants."""
    required = (
        "formal_run_manifest.json", "execution_order.json", "run_progress.json",
        "formal_results.jsonl", "provider_attempts.jsonl", "stage_outputs.jsonl",
        "terminal_conditions.jsonl",
    )
    missing = [name for name in required if not (formal_dir / name).exists()]
    if missing:
        raise RuntimeError(f"Resume checkpoint is missing artifacts: {missing}")

    manifest = json.loads((formal_dir / "formal_run_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("study_id") != "RESEARCH_A3_MULTI_MODEL_DEBATE_V1_3":
        raise RuntimeError("Resume checkpoint is not A3 v1.3")
    if any(manifest.get(key) is not False for key in (
        "aborted_v1_outputs_included", "aborted_v1_1_outputs_included", "aborted_v1_2_outputs_included"
    )):
        raise RuntimeError("Resume checkpoint includes excluded prior-run output")

    preflight = validate_preflight()
    scientific_hash_keys = (
        "benchmark_sha256", "corpus_sha256", "evidence_manifest_sha256",
        "role_rotation_manifest_sha256", "execution_plan_sha256",
        "prompt_bundle_sha256", "study_config_sha256", "structured_output_sha256",
    )
    for key in scientific_hash_keys:
        if manifest.get(key) != preflight.get(key):
            raise RuntimeError(f"Resume scientific invariant changed: {key}")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    budgets = config["generation"]
    expected_budgets = {
        "initial": budgets["initial_max_tokens"], "critique": budgets["critique_max_tokens"],
        "revision": budgets["revision_max_tokens"], "consensus": budgets["consensus_max_tokens"],
    }
    if manifest.get("token_budgets") != expected_budgets:
        raise RuntimeError("Resume token budgets differ from the frozen manifest")
    if manifest.get("systemic_truncation_stop_rule") != config["systemic_truncation_stop_rule"]:
        raise RuntimeError("Resume truncation stop rule differs from the frozen manifest")

    execution = json.loads((formal_dir / "execution_order.json").read_text(encoding="utf-8"))
    plan = execution.get("order")
    if not isinstance(plan, list) or len(plan) != 200:
        raise RuntimeError("Resume execution order is invalid")
    if sha256_file(formal_dir / "execution_order.json") != manifest["execution_plan_sha256"]:
        raise RuntimeError("Resume execution order hash changed")
    plan_by_sequence = {int(row["sequence"]): row for row in plan}

    results = _strict_jsonl(formal_dir / "formal_results.jsonl")
    attempts = _strict_jsonl(formal_dir / "provider_attempts.jsonl")
    stages = _strict_jsonl(formal_dir / "stage_outputs.jsonl")
    terminals = _strict_jsonl(formal_dir / "terminal_conditions.jsonl")
    progress = json.loads((formal_dir / "run_progress.json").read_text(encoding="utf-8"))
    completed = len(results)
    if completed <= 0 or completed >= 200:
        raise RuntimeError(f"Resume requires an incomplete non-empty checkpoint, got {completed} rows")
    sequences = [int(row["sequence"]) for row in results]
    identities = [row["resume_identity"] for row in results]
    if sequences != list(range(1, completed + 1)):
        raise RuntimeError("Committed canonical prefix is not contiguous and ordered")
    if len(set(identities)) != completed:
        raise RuntimeError("Duplicate committed canonical resume identity")
    for row in results:
        expected = plan_by_sequence[int(row["sequence"])]
        if any(row.get(key) != expected.get(key) for key in ("question_id", "condition", "resume_identity")):
            raise RuntimeError(f"Committed canonical row does not match plan: {row['sequence']}")
    if progress.get("completed_canonical") != completed or progress.get("current_sequence") != completed:
        raise RuntimeError("Progress checkpoint does not match committed canonical prefix")
    if progress.get("completed_m1") != sum(row["condition"] == "M1" for row in results):
        raise RuntimeError("Progress M1 count mismatch")
    if progress.get("completed_m2") != sum(row["condition"] == "M2" for row in results):
        raise RuntimeError("Progress M2 count mismatch")

    stage_keys = [_stage_key(row) for row in stages]
    if len(stage_keys) != len(set(stage_keys)):
        raise RuntimeError("Duplicate stage-cache key")
    attempt_keys = [
        (row.get("question_id"), row.get("condition"), row.get("stage"), row.get("seat"), row.get("attempt"))
        for row in attempts
    ]
    if len(attempt_keys) != len(set(attempt_keys)):
        raise RuntimeError("Duplicate provider-attempt key")

    committed_pairs = {(row["question_id"], row["condition"]) for row in results}
    for row in results:
        if row.get("usable"):
            count = sum((stage["question_id"], stage["condition"]) == (row["question_id"], row["condition"]) for stage in stages)
            if count != 10:
                raise RuntimeError(f"Usable canonical row lacks 10 unique stage outputs: {row['sequence']}")
    terminal_ids = {row["resume_identity"] for row in terminals}
    result_terminal_ids = {row["resume_identity"] for row in results if "terminal_failure" in row}
    if terminal_ids != result_terminal_ids:
        raise RuntimeError("Terminal-condition history does not match committed terminal rows")

    next_item = plan_by_sequence[completed + 1]
    next_pair = (next_item["question_id"], next_item["condition"])
    tail_stages = [row for row in stages if (row["question_id"], row["condition"]) not in committed_pairs]
    tail_attempts = [row for row in attempts if (row["question_id"], row["condition"]) not in committed_pairs]
    if any((row["question_id"], row["condition"]) != next_pair for row in [*tail_stages, *tail_attempts]):
        raise RuntimeError("Uncommitted records extend beyond the next canonical condition")
    successful_tail_attempt_keys = {
        (row["question_id"], row["condition"], row["stage"], row["seat"])
        for row in tail_attempts if row.get("success") is True
    }
    tail_stage_attempt_keys = {
        (row["question_id"], row["condition"], row["stage"], row["seat"])
        for row in tail_stages
    }
    if successful_tail_attempt_keys != tail_stage_attempt_keys or any(row.get("success") is not True for row in tail_attempts):
        raise RuntimeError("Uncommitted tail contains an attempt that is not a reusable validated stage")

    length_by_stage = {
        stage: sum(row.get("stage") == stage and row.get("finish_reason") == "length" for row in attempts)
        for stage in ("initial", "critique", "revision", "consensus")
    }
    terminal_truncation_by_stage = {
        stage: sum(
            row.get("terminal_failure", {}).get("stage") == stage
            and "truncated at max_tokens" in row.get("terminal_failure", {}).get("last_error", "")
            for row in terminals
        ) for stage in ("initial", "critique", "revision", "consensus")
    }
    rule = config["systemic_truncation_stop_rule"]
    if any(
        length_by_stage[stage] >= rule["length_attempts_same_stage"]
        or terminal_truncation_by_stage[stage] >= rule["terminal_truncation_conditions_same_stage"]
        for stage in length_by_stage
    ):
        raise RuntimeError("Resume forbidden because systemic truncation stop rule is already triggered")

    return {
        "status": "VALID_RESUME_CHECKPOINT",
        "completed_canonical": completed,
        "next_sequence": completed + 1,
        "next_question_id": next_item["question_id"],
        "next_condition": next_item["condition"],
        "tail_stage_count": len(tail_stages),
        "tail_stage_keys": [list(_stage_key(row)) for row in tail_stages],
        "length_by_stage": length_by_stage,
        "terminal_truncation_by_stage": terminal_truncation_by_stage,
        "fallback_count": sum(bool(row.get("fallback_used")) for row in attempts),
    }


def prepare_clean_restart(formal_dir: Path = FORMAL) -> Path:
    """Prepare the v1.3 formal directory without making any provider call."""
    preflight = validate_preflight()
    abort_v12_manifest = ABORTED_V12 / "abort_manifest.json"
    abort_v11_manifest = ABORTED_V11 / "abort_manifest.json"
    if not abort_v12_manifest.exists() or not abort_v11_manifest.exists():
        raise RuntimeError("Aborted v1.1/v1.2 attempts have not both been preserved")
    if not (EARLIER_ABORTED_FORMAL / "abort_manifest.json").exists():
        raise RuntimeError("Earlier aborted schema-validation attempt has not been preserved")
    aborted = json.loads(abort_v12_manifest.read_text(encoding="utf-8"))
    for name, expected in {
        "formal_run_manifest.json": aborted["preservation"]["formal_run_manifest_sha256"],
        "formal_results.jsonl": aborted["preservation"]["formal_results_sha256"],
        "provider_attempts.jsonl": aborted["preservation"]["provider_attempts_sha256"],
        "stage_outputs.jsonl": aborted["preservation"]["stage_outputs_sha256"],
        "execution_order.json": aborted["preservation"]["execution_order_sha256"],
        "run_progress.json": aborted["preservation"]["run_progress_sha256"],
    }.items():
        if sha256_file(ABORTED_V12 / name) != expected:
            raise RuntimeError(f"Aborted artifact changed: {name}")
    if formal_dir.exists() and any(formal_dir.iterdir()):
        manifest_path = formal_dir / "formal_run_manifest.json"
        if not manifest_path.exists():
            raise RuntimeError("Clean restart directory is non-empty without a manifest")
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("status") != "PREPARED_NOT_STARTED":
            raise RuntimeError("Clean restart directory is not in PREPARED_NOT_STARTED state")
        for key, value in preflight.items():
            if existing.get(key) != value:
                raise RuntimeError(f"Prepared restart manifest is stale for {key}")
        for name in ("formal_results.jsonl", "provider_attempts.jsonl", "stage_outputs.jsonl", "terminal_conditions.jsonl"):
            if (formal_dir / name).read_bytes():
                raise RuntimeError(f"Prepared restart is no longer clean: {name}")
        return manifest_path
    formal_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "status": "PREPARED_NOT_STARTED",
        "study_id": "RESEARCH_A3_MULTI_MODEL_DEBATE_V1_3",
        "timestamp_utc": now_utc(),
        **preflight,
        "protocol_amendment_sha256": sha256_file(HERE / "A3_V1_3_TOKEN_BUDGET_AMENDMENT.md"),
        "token_budget_config_sha256": sha256_file(HERE / "token_budget_config_v1_3.json"),
        "raw_token_audit_sha256": sha256_file(HERE / "A3_V1_3_RAW_TOKEN_AUDIT.json"),
        "v1_3_smoke_validation_sha256": sha256_file(HERE / "v1_3_smoke_validation.json"),
        "aborted_v1_2_manifest_sha256": sha256_file(abort_v12_manifest),
        "aborted_v1_1_manifest_sha256": sha256_file(abort_v11_manifest),
        "aborted_v1_manifest_sha256": sha256_file(EARLIER_ABORTED_FORMAL / "abort_manifest.json"),
        "exact_model_ids": list(APPROVED_MODELS),
        "consensus_model": FIXED_CONSENSUS_MODEL,
        "retry_policy": {"max_attempts_per_slot": 2, "allowed_failures": ["429", "5xx", "timeout", "parse_failure"]},
        "terminal_slot_policy": "After two failed attempts, checkpoint condition usable=false and continue to the next canonical execution.",
        "systemic_truncation_stop_rule": json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["systemic_truncation_stop_rule"],
        "provider_read_timeout_seconds": PROVIDER_READ_TIMEOUT_SECONDS,
        "decoding_settings": {"temperature": 0.0, "frequency_penalty": 0.0},
        "token_budgets": {
            "initial": json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["generation"]["initial_max_tokens"],
            "critique": json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["generation"]["critique_max_tokens"],
            "revision": json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["generation"]["revision_max_tokens"],
            "consensus": json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["generation"]["consensus_max_tokens"],
        },
        "concurrency_policy": {
            "Qwen/Qwen3-8B": 1,
            "THUDM/GLM-Z1-9B-0414": 1,
            "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B": 1,
        },
        "planned_canonical_executions": 200,
        "planned_provider_generations": 2000,
        "starting_state": {"canonical_completed": 0, "provider_attempts": 0, "semantic_review_rows": 0},
        "aborted_v1_outputs_included": False,
        "aborted_v1_1_outputs_included": False,
        "aborted_v1_2_outputs_included": False,
    }
    for name in ("formal_results.jsonl", "provider_attempts.jsonl", "stage_outputs.jsonl", "terminal_conditions.jsonl"):
        (formal_dir / name).write_text("", encoding="utf-8")
    (formal_dir / "execution_order.json").write_text(EXECUTION_PLAN_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    (formal_dir / "run_progress.json").write_text(json.dumps({
        "total_canonical": 200,
        "completed_canonical": 0,
        "current_sequence": 0,
        "completed_m1": 0,
        "completed_m2": 0,
        "usable_canonical": 0,
        "terminal_unusable_canonical": 0,
        "timestamp_utc": now_utc(),
    }, indent=2) + "\n", encoding="utf-8")
    (formal_dir / "semantic_review_state.json").write_text(json.dumps({"rows": 0, "status": "NOT_CREATED"}, indent=2) + "\n", encoding="utf-8")
    manifest_path = formal_dir / "formal_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def run_formal_experiment(*, resume: bool = False) -> None:
    print("Starting A3 Formal Execution pre-flight checks...")
    with FormalRunnerLock(FORMAL):
        if resume:
            checkpoint = validate_resume_checkpoint(FORMAL)
            manifest_path = FORMAL / "formal_run_manifest.json"
            print(
                "Resume validation PASS; "
                f"completed={checkpoint['completed_canonical']}, next={checkpoint['next_sequence']} "
                f"{checkpoint['next_question_id']} {checkpoint['next_condition']}, "
                f"cached_tail_stages={checkpoint['tail_stage_count']}."
            )
        else:
            manifest_path = prepare_clean_restart(FORMAL)
            print(f"Clean-start checks PASS; using {manifest_path}.")

        # Run execution only after a separately authorized caller invokes this function.
        api_key = load_api_key()
        runner_instance = FormalExecutionRunner(api_key)
        asyncio.run(runner_instance.run())

    # 3. Compute objective and process metrics
    print("Computing objective and process metrics...")
    objective, process = compute_objective_and_process_metrics()
    (FORMAL / "objective_metrics.json").write_text(json.dumps(objective, indent=2) + "\n", encoding="utf-8")
    (FORMAL / "process_metrics.json").write_text(json.dumps(process, indent=2) + "\n", encoding="utf-8")

    # 4. Blinded review packet
    print("Generating blinded semantic review packet...")
    generate_blinded_review_packet()
    write_semantic_review_instructions()

    # 5. Formal validation
    print("Validating formal execution artifacts...")
    report = validate_formal_execution()
    print("Validation report:\n", json.dumps(report, indent=2))
