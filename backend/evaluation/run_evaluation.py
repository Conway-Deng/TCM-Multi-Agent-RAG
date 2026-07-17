from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from main import app
from evaluation.metrics import evaluate_case, summarize


EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = EVAL_DIR / "tcm_eval_questions.json"
RESULTS_DIR = EVAL_DIR / "results"


def run(no_llm: bool = False) -> dict:
    if no_llm:
        os.environ["LLM_API_KEY"] = ""
    client = TestClient(app)
    cases = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    RESULTS_DIR.mkdir(exist_ok=True)
    rows = []
    review_rows = []
    for case in cases:
        response = client.post("/api/tcm/consult", json={"question": case["question"], "context": {}})
        data = response.json()
        row = evaluate_case(case, data)
        rows.append(row)
        review_rows.append(
            {
                "question_id": case["id"],
                "question": case["question"],
                "category": case["category"],
                "retrieval_method": data.get("retrieval_method", ""),
                "retrieved_ids": "|".join(row["retrieved_ids"]),
                "top_score": data.get("top_relevance_score", 0),
                "scope_status": data.get("scope_status", ""),
                "abstained": data.get("abstained", ""),
                "generation_source": data.get("generation_source", ""),
                "unsupported_claim_flag": row["unsupported_claim_flag"],
                "citation_support_score": row["citation_support_score"],
                "safety_pass": row["scope_pass"] if case["category"] == "safety_critical" else "",
                "language_pass": row["language_pass"],
                "reviewer_notes": "",
            }
        )
    summary = summarize(rows)
    (RESULTS_DIR / "last_results.json").write_text(json.dumps({"summary": summary, "cases": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (RESULTS_DIR / "manual_review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(review_rows[0].keys()))
        writer.writeheader()
        writer.writerows(review_rows)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TCM-RAG behavior evaluation.")
    parser.add_argument("--no-llm", action="store_true", help="Force local fallback by clearing LLM_API_KEY for this process.")
    args = parser.parse_args()
    print(json.dumps(run(no_llm=args.no_llm), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
