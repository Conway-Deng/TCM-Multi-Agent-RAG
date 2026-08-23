from __future__ import annotations

import asyncio
import csv
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "research/experiment_pipeline"))

import rq4_platform as platform
from rq4_dashboard import dashboard_payload, render
from orchestration.genuine_debate import DebateStageFailure, run_genuine_debate
from providers.base import GenerationResult
from providers.openai_compatible import ProviderUnavailable
from schemas.research import ResearchAgentOutput, RetrievalItem, StructuredClaim


class FixtureProvider:
    name = "synthetic"
    model = platform.MODEL

    def __init__(self, fail_first: bool = False, always_fail: bool = False):
        self.calls = []
        self.fail_first = fail_first
        self.always_fail = always_fail

    async def generate(self, *, system, prompt, **_):
        self.calls.append((system, prompt))
        if self.always_fail or (self.fail_first and len(self.calls) == 1):
            raise ProviderUnavailable("bounded timeout", error_type="timeout")
        value = json.loads(prompt)
        if "Return JSON with reviewer_id" in system:
            text = json.dumps({"reviewer_id": value["reviewer_id"], "agreements": ["grounded"], "challenges": [], "unsupported_claims": [], "missing_evidence": [], "citation_issues": []})
        elif "Revise" in system:
            text = json.dumps({"agent_id": value["agent_id"], "revised_position": "Revised grounded position.", "evidence_ids": [value["evidence"][0]["evidence_id"]]})
        else:
            text = json.dumps({"final_answer": "Final grounded consensus.", "evidence_ids": [value["evidence"][0]["evidence_id"]], "agreements": ["grounded"], "disagreements": [], "unresolved_conflicts": []})
        return GenerationResult(text=text, provider=self.name, model=self.model, prompt_tokens=2, completion_tokens=3)


def agent(agent_id="herbal"):
    return ResearchAgentOutput(agent_id=agent_id, agent_name=agent_id, agent_version="1", question="q", language="en", subdomain=agent_id, claims=[StructuredClaim(claim_id="c", text="claim", evidence_ids=["tcmv1-a"], confidence=.5)], evidence_ids=["tcmv1-a"], confidence=.5)


def evidence():
    return [RetrievalItem(chunk_id="tcmv1-a", source_id="s", rank=1, retrieval_method="lexical", chunk_text="evidence")]


def test_c4_audit_classifies_deterministic_old_path():
    assert "DETERMINISTIC_AGGREGATION_ONLY" in (platform.RQ4 / "c4_audit/current_c4_audit.md").read_text(encoding="utf-8")


def test_structured_debate_schema():
    result = asyncio.run(run_genuine_debate(FixtureProvider(), question="q", evidence=evidence(), outputs=[agent()], rounds=1))
    assert result.trace.architecture == "genuine_llm_structured_debate" and result.trace.final_consensus


def test_single_specialist_grounding_critic_path():
    result = asyncio.run(run_genuine_debate(FixtureProvider(), question="q", evidence=evidence(), outputs=[agent()], rounds=1))
    assert result.trace.critic_invoked and result.trace.critiques[0]["reviewer_id"] == "grounding_critic"


def test_multi_specialist_peer_interaction():
    result = asyncio.run(run_genuine_debate(FixtureProvider(), question="q", evidence=evidence(), outputs=[agent("herbal"), agent("syndrome")], rounds=1))
    assert len(result.trace.critiques) == 2 and result.trace.critic_invoked is False


def test_max_one_debate_round():
    with pytest.raises(ValueError, match="exactly one"): asyncio.run(run_genuine_debate(FixtureProvider(), question="q", evidence=evidence(), outputs=[agent()], rounds=2))


def test_provider_timeout_is_classified():
    provider = FixtureProvider(always_fail=True)
    with pytest.raises(DebateStageFailure) as caught: asyncio.run(run_genuine_debate(provider, question="q", evidence=evidence(), outputs=[agent()], rounds=1))
    assert caught.value.attempts[-1].error_type == "timeout"


def test_bounded_retry_can_recover():
    provider = FixtureProvider(fail_first=True)
    result = asyncio.run(run_genuine_debate(provider, question="q", evidence=evidence(), outputs=[agent()], rounds=1))
    assert result.provider_calls == 4 and result.successful_provider_calls == 3


def test_no_infinite_retry():
    provider = FixtureProvider(always_fail=True)
    with pytest.raises(DebateStageFailure): asyncio.run(run_genuine_debate(provider, question="q", evidence=evidence(), outputs=[agent()], rounds=1))
    assert len(provider.calls) == 2


def test_single_instance_lock(tmp_path, monkeypatch):
    path = tmp_path / "lock.json"; lock = platform.PidLock(path); lock.acquire()
    with pytest.raises(RuntimeError, match="ALREADY_ACTIVE"): platform.PidLock(path).acquire()
    lock.release()


def test_stale_lock_cleanup(tmp_path):
    path = tmp_path / "lock.json"; platform.write_json(path, {"pid": 99999999}); lock = platform.PidLock(path); lock.acquire()
    assert json.loads(path.read_text())["pid"] == os.getpid(); lock.release()


def test_durable_result_append(tmp_path):
    path = tmp_path / "r.jsonl"; platform.durable_append(path, {"execution_id": "a"})
    assert platform.jsonl(path) == [{"execution_id": "a"}]


def test_resume_from_partial_run():
    order = platform.execution_order([f"q{i:03d}" for i in range(100)]); done = {x["execution_id"] for x in order[:83]}; remaining = [x for x in order if x["execution_id"] not in done]
    assert remaining[0]["sequence"] == 84 and len(remaining) == 117


def test_duplicate_execution_prevention():
    order = platform.execution_order(["q1"]); records = [{**order[0], "benchmark_sha256": "x", "corpus_sha256": platform.CORPUS_SHA}] * 2
    with pytest.raises(RuntimeError, match="DUPLICATE"): platform.validate_results(order, records)


def test_execution_order_determinism():
    ids = [f"q{i}" for i in range(100)]
    assert platform.execution_order(ids) == platform.execution_order(ids)


def test_execution_order_counterbalancing():
    order = platform.execution_order([f"q{i}" for i in range(100)]); first = [order[i]["condition"] for i in range(0, 200, 2)]
    assert first.count("C2") == first.count("C4") == 50


def test_smoke_set_is_10_distinct_development_only_questions():
    questions = platform.load_smoke_questions()
    assert len(questions) == len({item["question_id"] for item in questions}) == 10
    assert len({platform.normalize_text(item["question"]) for item in questions}) == 10
    assert any(item["expected_route"] == "single" for item in questions)
    assert any(item["expected_route"] == "multi" for item in questions)


def test_smoke_order_pairs_both_conditions_and_counterbalances():
    questions = platform.load_smoke_questions()
    order = platform.smoke_execution_order(questions, 1)
    assert len(order) == len({item["execution_id"] for item in order}) == 20
    assert {(item["question_id"], item["condition"]) for item in order} == {
        (question["question_id"], condition) for question in questions for condition in ("C2", "C4")
    }
    assert [order[index]["condition"] for index in range(0, 20, 2)].count("C2") == 5


def test_stale_backend_without_current_implementation_fingerprints_is_rejected():
    assert not platform.backend_matches_current_implementation({"status": "ok"})
    assert platform.backend_matches_current_implementation({
        "workbench_sha256": platform.sha(ROOT / "backend/orchestration/workbench.py"),
        "c4_implementation_sha256": platform.sha(ROOT / "backend/orchestration/genuine_debate.py"),
    })


def test_operational_smoke_validation_requires_genuine_single_and_multi_c4():
    questions = platform.load_smoke_questions()
    by_id = {item["question_id"]: item for item in questions}
    records = []
    for entry in platform.smoke_execution_order(questions, 1):
        source_ids = by_id[entry["question_id"]]["source_evidence_ids"]
        selected = ["herbal", "syndrome"] if by_id[entry["question_id"]]["expected_route"] == "multi" else ["herbal"]
        debate = {}
        if entry["condition"] == "C4":
            debate = {
                "architecture": "genuine_llm_structured_debate", "rounds": 1,
                "selected_agents": selected, "critic_invoked": len(selected) == 1,
                "initial_outputs": [{"agent_id": agent_id} for agent_id in selected],
                "critiques": [{"reviewer_id": agent_id} for agent_id in selected],
                "revisions": [{"agent_id": agent_id, "revised_position": "grounded", "evidence_ids": source_ids} for agent_id in selected],
                "final_consensus": {"final_answer": "grounded", "evidence_ids": source_ids},
                "stage_statuses": [
                    *[{"stage": f"critique:{agent_id}", "status": "PASS"} for agent_id in selected],
                    *[{"stage": f"revision:{agent_id}", "status": "PASS"} for agent_id in selected],
                    {"stage": "consensus", "status": "PASS"},
                ],
            }
        records.append({
            **entry, "run_status": "PASS", "retrieved_evidence_ids": source_ids,
            "provider_attempts": [], "fallback": False, "debate": debate,
        })
    validation = platform.validate_smoke(records, questions, 1)
    assert validation["status"] == "PASS"
    assert validation["c2_executions"] == validation["c4_executions"] == 10
    assert validation["c4_full_genuine_sequences"] == 10
    assert validation["grounding_critic_tested"] and validation["multi_specialist_debate_tested"]


def test_benchmark_leakage_exclusion():
    report = (platform.BENCH / "leakage_report_rq4_v1.md").read_text(encoding="utf-8")
    assert "normalized_question_overlap: 0" in report and "source_evidence_id_overlap: 0" in report


def test_benchmark_review_import_rejects_row_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, "BENCH", tmp_path); (tmp_path / "external_source_review_for_gpt.csv").write_text("row_id,question_id\na,q\n", encoding="utf-8")
    returned = tmp_path / "bad.csv"; returned.write_text("row_id,question_id\nb,q\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ROW_SET_MISMATCH"): platform.import_source_review(returned)


def test_benchmark_freeze_hashes_are_pending_not_fabricated():
    manifest = json.loads((platform.BENCH / "heldout_manifest_rq4_v1_draft.json").read_text(encoding="utf-8"))
    assert manifest["frozen"] is False and manifest["draft_sha256"] == platform.sha(platform.BENCH / "benchmark_rq4_v1_draft.jsonl")


def test_semantic_blinding_labels_only():
    labels = {"SYSTEM_A", "SYSTEM_B"}; assert all("C2" not in x and "C4" not in x for x in labels)


def test_semantic_import_rejects_invalid_label(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, "FORMAL", tmp_path); expected = "item_id,question_id,anonymous_system_label,question,gold_atomic_fact,source_evidence,answer,review_label,review_reason,confidence\na,q,SYSTEM_A,Q,G,E,A,,,\n"; (tmp_path / "rq4_semantic_review_for_gpt.csv").write_text(expected, encoding="utf-8")
    bad = tmp_path / "bad.csv"; bad.write_text(expected.replace(",,,\n", ",INVALID,,\n"), encoding="utf-8")
    with pytest.raises(RuntimeError, match="INVALID_SEMANTIC_LABEL"): platform.import_semantic(bad)


def test_state_machine_valid_transitions(tmp_path):
    state = platform.StateMachine(tmp_path / "state.json"); state.initialize_build_complete()
    assert state.read()["state"] == "BENCHMARK_SOURCE_REVIEW_REQUIRED"


def test_invalid_state_transition_rejected(tmp_path):
    state = platform.StateMachine(tmp_path / "state.json")
    with pytest.raises(RuntimeError, match="INVALID_RQ4_STATE_TRANSITION"): state.transition("FORMAL_RUNNING")


def test_dashboard_state_serialization(monkeypatch, tmp_path):
    payload = {"state": "BENCHMARK_SOURCE_REVIEW_REQUIRED", "runtime": {}, "next_valid_action": "review"}
    assert "RQ4 STATUS" in render(payload) and "BENCHMARK_SOURCE_REVIEW_REQUIRED" in render(payload)


def test_formal_start_integrity_guard_blocks_early_state(monkeypatch, tmp_path):
    monkeypatch.setattr(platform, "STATE_PATH", tmp_path / "state.json")
    class Early:
        def read(self): return {"state": "BENCHMARK_SOURCE_REVIEW_REQUIRED"}
    monkeypatch.setattr(platform, "StateMachine", Early)
    with pytest.raises(RuntimeError, match="BLOCKED_BY_STATE"): platform.formal_integrity_guard()


def test_systemic_formal_error_surfaces_stalled_state(monkeypatch, tmp_path):
    state = platform.StateMachine(tmp_path / "state.json")
    platform.write_json(state.path, {"state": "FORMAL_RUNNING", "updated_at": platform.utcnow()})
    monkeypatch.setattr(platform, "StateMachine", lambda: state)
    monkeypatch.setattr(platform, "RUNTIME_PATH", tmp_path / "runtime.json")
    monkeypatch.setattr(platform, "run_formal", lambda: (_ for _ in ()).throw(RuntimeError("systemic")))
    with pytest.raises(RuntimeError, match="systemic"): platform.run_formal_with_stall_guard()
    assert state.read()["state"] == "FORMAL_STALLED"
    assert json.loads((tmp_path / "runtime.json").read_text())["status"] == "STALLED"


def test_no_provider_calls_in_dry_run_mode():
    assert platform.status()["provider_calls"] == 0


def test_no_hidden_chain_of_thought_requested():
    provider = FixtureProvider(); asyncio.run(run_genuine_debate(provider, question="q", evidence=evidence(), outputs=[agent()], rounds=1))
    prompts = " ".join(system for system, _ in provider.calls).casefold()
    assert "show all your reasoning" not in prompts and "think step by step" not in prompts


def test_synthetic_end_to_end():
    result = platform.synthetic_e2e()
    assert result["passed"] and result["provider_calls"] == 0
    assert result["interrupted_at"] == 83 and result["resumed_at"] == 84
    assert result["executions"] == 200 and result["duplicates"] == 0
    assert result["objective_evaluation"] and result["dashboard_state_updates"]
    assert result["semantic_import"] and result["final_statistics"]
    assert result["final_state"] == "RQ4_COMPLETE"
