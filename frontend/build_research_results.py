"""Build the public-safe dashboard summary from frozen final artifacts."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "data" / "research_results.json"
RQ1_MANIFEST = ROOT / "research" / "experiments" / "rq1_c1_vs_c2" / "rq1_closeout" / "rq1_final_manifest_with_confirmatory.json"
RQ4_DIR = ROOT / "research" / "experiments" / "rq4_debate_vs_multiagent" / "formal_run_v1" / "final_analysis"
RQ4_MANIFEST = RQ4_DIR / "rq4_final_manifest.json"
RQ4_STATS = RQ4_DIR / "rq4_paired_statistics.json"
RQ4_RELIABILITY = RQ4_DIR / "rq4_reliability_analysis.json"
RQ4_LATENCY = RQ4_DIR / "rq4_latency_analysis.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def source_commit(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", relative],
        cwd=ROOT,
        text=True,
    ).strip()


def pct(value: float) -> float:
    return round(value * 100, 2)


def build() -> dict:
    rq1_manifest = read_json(RQ1_MANIFEST)
    rq1 = rq1_manifest["study_1B"]
    rq1_full = rq1["full_recall"]
    rq4_manifest = read_json(RQ4_MANIFEST)
    rq4_stats = read_json(RQ4_STATS)
    rq4_reliability = read_json(RQ4_RELIABILITY)
    rq4_latency = read_json(RQ4_LATENCY)

    return {
        "schema_version": "1.0",
        "generated_by": "frontend/build_research_results.py",
        "public_safety": {
            "aggregate_results_only": True,
            "contains_raw_corpus": False,
            "contains_raw_experiment_outputs": False,
            "contains_secrets": False,
        },
        "project": {
            "title": "TCM Multi-Agent RAG Research",
            "corpus_name": "TCM Research Corpus v1",
            "corpus_chunks": 4461,
            "corpus_scope": "Herbal medicine + syndrome knowledge",
            "model": rq4_manifest["model"],
            "formal_retrieval": rq4_manifest["retrieval"],
            "corpus_sha256": rq4_manifest["corpus_sha256"],
        },
        "rq1": {
            "status": rq1_manifest["status"],
            "study": "Independent confirmatory extension (Study 1B)",
            "question": "Does ordinary Multi-Agent improve source-grounded answer quality over Single-RAG?",
            "conditions": {"C1": "Single-RAG", "C2": "Ordinary Multi-Agent specialists"},
            "complete_usable_pairs": rq1["complete_usable_pairs"],
            "full_recall_pct": {"C1": pct(rq1_full["c1_mean"]), "C2": pct(rq1_full["c2_mean"])},
            "difference_c2_minus_c1_pp": pct(rq1_full["mean_paired_difference_c2_minus_c1"]),
            "bootstrap_95_ci_pp": [pct(value) for value in rq1_full["bootstrap_95ci_mean_difference"]],
            "wilcoxon_p": rq1_full["wilcoxon"]["p_value_two_sided"],
            "meaningful_improvement_threshold_pp": pct(rq1_full["practical_threshold"]),
            "conclusion": "Ordinary Multi-Agent did not demonstrate a robust meaningful advantage over Single-RAG under the tested setup.",
            "provenance": {
                "source_artifact": RQ1_MANIFEST.relative_to(ROOT).as_posix(),
                "benchmark_sha256": rq1["benchmark_sha256"],
                "corpus_sha256": rq1_manifest["study_1A"]["corpus_sha256"],
                "source_commit": source_commit(RQ1_MANIFEST),
            },
        },
        "rq4": {
            "status": rq4_manifest["status"],
            "question": "Does genuine critique, revision, and consensus improve answer quality over ordinary Multi-Agent?",
            "conditions": {"C2": "Ordinary Multi-Agent", "C4": "One-round structured debate"},
            "complete_usable_pairs": rq4_manifest["complete_usable_pairs"],
            "full_recall_pct": {
                "C2": pct(rq4_stats["primary_full_recall"]["c2"]),
                "C4": pct(rq4_stats["primary_full_recall"]["c4"]),
            },
            "difference_c4_minus_c2_pp": rq4_stats["primary_full_recall"]["difference_pp"],
            "bootstrap_95_ci_pp": [pct(value) for value in rq4_stats["primary_full_recall"]["bootstrap_95_ci"]],
            "full_recall_wilcoxon_p": rq4_stats["primary_full_recall"]["wilcoxon_p"],
            "partial_or_better_pct": {
                "C2": pct(rq4_stats["partial_or_better"]["c2"]),
                "C4": pct(rq4_stats["partial_or_better"]["c4"]),
            },
            "missing_pct": {
                "C2": pct(rq4_stats["missing"]["c2"]),
                "C4": pct(rq4_stats["missing"]["c4"]),
            },
            "contradiction_pct": {
                "C2": pct(rq4_stats["contradiction"]["c2"]),
                "C4": pct(rq4_stats["contradiction"]["c4"]),
            },
            "reliability_usable": {"C2": rq4_reliability["C2_usable"], "C4": rq4_reliability["C4_usable"]},
            "reliability_total": rq4_reliability["planned_questions"],
            "reliability_mcnemar_p": rq4_reliability["mcnemar"]["exact_two_sided_p"],
            "mean_latency_seconds": {
                "C2": round(rq4_latency["c2_mean_ms"] / 1000, 4),
                "C4": round(rq4_latency["c4_mean_ms"] / 1000, 4),
            },
            "latency_paired_wilcoxon_p": rq4_latency["wilcoxon_p"],
            "meaningful_improvement_threshold_pp": rq4_stats["threshold_pp"],
            "conclusion": "C4 did not establish superior Full Recall and incurred materially lower usable execution rate and higher latency.",
            "provenance": {
                "source_artifacts": [
                    RQ4_MANIFEST.relative_to(ROOT).as_posix(),
                    RQ4_STATS.relative_to(ROOT).as_posix(),
                    RQ4_RELIABILITY.relative_to(ROOT).as_posix(),
                    RQ4_LATENCY.relative_to(ROOT).as_posix(),
                ],
                "protocol_sha256": rq4_manifest["protocol_sha256"],
                "benchmark_sha256": rq4_manifest["benchmark_sha256"],
                "corpus_sha256": rq4_manifest["corpus_sha256"],
                "source_commit": source_commit(RQ4_MANIFEST),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if the committed presentation JSON is stale.")
    args = parser.parse_args()
    rendered = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("frontend/data/research_results.json is stale")
        print("presentation results match authoritative artifacts")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
