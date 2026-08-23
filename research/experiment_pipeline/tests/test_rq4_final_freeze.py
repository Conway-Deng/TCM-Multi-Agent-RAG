from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research/experiment_pipeline"))

import rq4_platform as platform


BENCH = ROOT / "research/benchmarks/tcm_gold_rq4_v1"
RQ4 = ROOT / "research/experiments/rq4_debate_vs_multiagent"
FORMAL = RQ4 / "formal_run_v1"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_final_review_import_is_exact_and_fully_approved():
    expected = read_csv(BENCH / "external_source_review_v1_2_for_gpt.csv")
    completed = read_csv(BENCH / "final_source_review/external_source_review_v1_2_completed.csv")
    assert len(expected) == len(completed) == 232
    assert len({row["row_id"] for row in completed}) == 232
    assert len({row["question_id"] for row in completed}) == 100
    assert Counter(row["source_review_status"] for row in completed) == Counter({"APPROVE": 232})
    protected = set(expected[0]) - {"source_review_status", "review_reason", "confidence"}
    by_id = {row["row_id"]: row for row in expected}
    assert set(expected[0]) == set(completed[0])
    assert all(all(row[field] == by_id[row["row_id"]][field] for field in protected) for row in completed)


def test_frozen_benchmark_is_exact_v1_2_candidate():
    candidate = BENCH / "benchmark_rq4_v1_2_draft.jsonl"
    frozen = BENCH / "benchmark_rq4_v1_frozen.jsonl"
    assert frozen.read_bytes() == candidate.read_bytes()
    assert platform.sha(frozen) == "744298bc007aad562dab62268c0b887642e288408cd7cec87c8d03fb90aa21a4"
    items = platform.jsonl(frozen)
    assert len(items) == len({item["question_id"] for item in items}) == 100
    assert len({platform.normalize_text(item["question"]) for item in items}) == 100
    assert sum(len(item["gold_facts"]) for item in items) == 232
    assert Counter(item["domain"] for item in items) == Counter({
        "herbal_medicine": 60, "syndrome_differentiation": 25,
        "herbal_medicine + syndrome_differentiation": 15,
    })
    assert Counter(item["difficulty"] for item in items) == Counter({"easy": 40, "medium": 40, "hard": 20})


def test_freeze_manifest_and_duplicate_audit_are_locked():
    freeze = json.loads((BENCH / "freeze_manifest_rq4_v1.json").read_text(encoding="utf-8"))
    heldout = json.loads((BENCH / "heldout_manifest_rq4_v1_frozen.json").read_text(encoding="utf-8"))
    audit = json.loads((BENCH / "duplicate_audit_rq4_v1_2.json").read_text(encoding="utf-8"))
    assert freeze["status"] == heldout["status"] == "FROZEN_SOURCE_GROUNDED_RQ4_V1"
    assert freeze["source_candidate"] == heldout["source_candidate"] == "RQ4_CANDIDATE_V1_2"
    assert freeze["final_benchmark_sha256"] == heldout["benchmark_sha256"] == platform.sha(BENCH / "benchmark_rq4_v1_frozen.jsonl")
    assert freeze["source_review"] == "232_OF_232_APPROVED" and heldout["frozen"] is True
    assert audit["status"] == "PASS" and audit["unique_normalized_questions"] == 100
    assert not any(audit[key] for key in audit if key.endswith(("conflicts", "overlap", "duplicates")))


def test_formal_order_is_paired_counterbalanced_and_not_executed():
    order_record = json.loads((FORMAL / "execution_order.json").read_text(encoding="utf-8"))
    order = order_record["order"]
    assert len(order) == len({entry["execution_id"] for entry in order}) == 200
    assert Counter(entry["condition"] for entry in order) == Counter({"C2": 100, "C4": 100})
    assert Counter(order[index]["condition"] for index in range(0, 200, 2)) == Counter({"C2": 50, "C4": 50})
    assert len({(entry["question_id"], entry["condition"]) for entry in order}) == 200
    manifest = json.loads((FORMAL / "formal_execution_manifest.json").read_text(encoding="utf-8"))
    protocol = json.loads((RQ4 / "protocol/protocol_manifest.json").read_text(encoding="utf-8"))
    assert manifest["execution_order_sha256"] == platform.sha(FORMAL / "execution_order.json")
    assert manifest["protocol_sha256"] == protocol["protocol_sha256"] == platform.sha(RQ4 / "protocol/protocol.md")
    assert manifest["planned_c2_executions"] == manifest["planned_c4_executions"] == 100
    assert not (FORMAL / "results.jsonl").exists()


def test_state_never_advances_to_formal_during_smoke_gates():
    state = json.loads((RQ4 / "rq4_state.json").read_text(encoding="utf-8"))
    assert state["state"] in {
        "REAL_SMOKE_TEST_REQUIRED", "SMOKE_TEST_RUNNING", "SMOKE_TEST_FAILED",
        "SMOKE_TEST_PASSED", "READY_FOR_FORMAL_RQ4_RUN",
    }
    assert state.get("formal_execution_records", 0) == 0
