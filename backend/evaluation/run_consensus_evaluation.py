from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from evaluation.consensus_metrics import evaluate_consensus_case, summarize_consensus
from main import app


EVAL_DIR = Path(__file__).resolve().parent
CASES_PATH = EVAL_DIR / "consensus_eval_cases.json"
RESULTS_DIR = EVAL_DIR / "results"
CONFIGURATIONS = {
    "concatenate": "concatenate",
    "weighted": "weighted",
    "same_model_debate": "debate",
    "same_model_debate_judge": "debate_judge",
}


def _single_tcm_row(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/tcm/consult", json={"question": case["question"], "context": {}})
    data = response.json()
    wrapped = {
        "strategy": "tcm_single",
        "agents": [{
            "source_type": "local_rag",
            "experimental": True,
            "limitations": data.get("limitations", []),
            "evidence": data.get("evidence", []),
            "claims": data.get("claims", []),
            "urgent": data.get("urgent", False),
            "abstained": data.get("abstained", False),
            "generation_source": data.get("generation_source", ""),
        }],
        "judges": {},
        "integrated_response": {"summary": data.get("summary", ""), "disagreements": []},
        "latency_ms": 0,
        "api_call_count": 0,
        "model_call_failure_count": 0,
    }
    return evaluate_consensus_case(case, "tcm_single", wrapped, response.status_code)


def run(*, no_llm: bool = False) -> dict[str, Any]:
    if no_llm:
        os.environ["LLM_API_KEY"] = ""
    os.environ["ALLOW_WEST_FIXTURE"] = "true"
    os.environ["CONSENSUS_ENABLED"] = "true"
    os.environ["ENABLE_SEMANTIC_RETRIEVAL"] = "false"
    os.environ["ENABLE_REMOTE_RERANK"] = "false"
    client = TestClient(app)
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for case in cases:
        rows.append(_single_tcm_row(client, case))
        for configuration, strategy in CONFIGURATIONS.items():
            response = client.post(
                "/api/consensus/consult",
                json={
                    "question": case["question"],
                    "context": {},
                    "strategy": strategy,
                    "domains": ["tcm", "western_fixture"],
                    "include_trace": True,
                },
            )
            rows.append(evaluate_consensus_case(case, configuration, response.json(), response.status_code))

    summary = summarize_consensus(rows)
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "consensus_last_results.json").write_text(
        json.dumps({"research_notice": "Synthetic orchestration benchmark; not clinical validation.", "summary": summary, "cases": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    review_fields = [
        "case_id", "category", "configuration", "factual_accuracy", "completeness", "relevance",
        "explainability", "safety", "evidence_support", "preference", "reviewer_notes",
    ]
    with (RESULTS_DIR / "consensus_manual_review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=review_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in review_fields})
    lines = [
        "# Consensus Evaluation Summary",
        "",
        "> Synthetic orchestration benchmark only. These metrics do not establish medical correctness.",
        "",
        "| Configuration | Pipeline success | Urgent safety | Unsupported claim detection | Fixture labels | Mean latency (ms) | API calls |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, metrics in summary.items():
        lines.append(
            f"| {name} | {metrics['pipeline_success_rate']:.3f} | {metrics['urgent_safety_detection_rate']:.3f} | "
            f"{metrics['unsupported_claim_detection_rate']:.3f} | {metrics['fixture_label_accuracy']:.3f} | "
            f"{metrics['mean_latency_ms']:.1f} | {metrics['total_api_call_count']} |"
        )
    (RESULTS_DIR / "consensus_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the synthetic MediConsensus orchestration evaluation.")
    parser.add_argument("--no-llm", action="store_true", help="Disable all real model calls for deterministic CI.")
    args = parser.parse_args()
    print(json.dumps(run(no_llm=args.no_llm), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
