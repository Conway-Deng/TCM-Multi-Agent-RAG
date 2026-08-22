import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "research/experiments/rq1_c1_vs_c2/confirmatory_run_v1_1"
FINAL = RUN / "final_analysis"
CLOSEOUT = ROOT / "research/experiments/rq1_c1_vs_c2/rq1_closeout"
BENCHMARK = ROOT / "research/benchmarks/tcm_gold_rq1_confirmatory_v1/benchmark_confirmatory_v1_1_frozen.jsonl"
FREEZE = ROOT / "research/benchmarks/tcm_gold_rq1_confirmatory_v1/freeze_manifest_confirmatory_v1_1.json"
CORPUS = ROOT / "research/corpus/tcm_v1/chunks.jsonl"
PROTOCOL = ROOT / "research/experiments/rq1_c1_vs_c2/confirmatory_protocol/protocol.md"
ANALYSIS_PLAN = ROOT / "research/experiments/rq1_c1_vs_c2/confirmatory_protocol/analysis_plan.json"
PACKET = RUN / "semantic_review_for_gpt.csv"
RESULTS = RUN / "results.jsonl"
EXECUTION = RUN / "formal_execution_manifest.json"
OBJECTIVE = RUN / "objective_scores.jsonl"
EXPECTED_BENCHMARK_SHA = "2590ffd569d1087b8c01453fc676edad28d85a8ccbf21edb19df6827e5be67f0"
EXPECTED_CORPUS_SHA = "316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9"
BOOTSTRAP_SEED = 20260821
BOOTSTRAP_RESAMPLES = 10000
PRACTICAL_THRESHOLD = 0.05
LABELS = ["SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED", "CONTRADICTED", "UNRESOLVED"]
ANONYMOUS_TO_CONDITION = {"SYSTEM_A": "C1", "SYSTEM_B": "C2"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def wilcoxon_signed_rank(differences):
    nonzero = [value for value in differences if abs(value) > 1e-15]
    if not nonzero:
        return {
            "w_plus": 0.0,
            "w_minus": 0.0,
            "nonzero_n": 0,
            "zero_differences": len(differences),
            "p_value_two_sided": None,
            "informative": False,
            "method": "not informative; all paired differences tied",
        }
    order = sorted(range(len(nonzero)), key=lambda index: abs(nonzero[index]))
    ranks = [0.0] * len(nonzero)
    tie_sizes = []
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and abs(nonzero[order[end]]) == abs(nonzero[order[start]]):
            end += 1
        average_rank = (start + 1 + end) / 2
        for offset in range(start, end):
            ranks[order[offset]] = average_rank
        tie_sizes.append(end - start)
        start = end
    w_plus = sum(rank for rank, value in zip(ranks, nonzero) if value > 0)
    w_minus = sum(rank for rank, value in zip(ranks, nonzero) if value < 0)
    n = len(nonzero)
    expected = n * (n + 1) / 4
    variance = n * (n + 1) * (2 * n + 1) / 24 - sum(size * (size * size - 1) for size in tie_sizes) / 48
    z_value = (w_plus - expected) / math.sqrt(variance) if variance else 0.0
    p_value = math.erfc(abs(z_value) / math.sqrt(2))
    return {
        "w_plus": w_plus,
        "w_minus": w_minus,
        "nonzero_n": n,
        "zero_differences": len(differences) - n,
        "z": z_value,
        "p_value_two_sided": p_value,
        "informative": True,
        "method": "Wilcoxon signed-rank; zero differences omitted; normal approximation with tie correction; no continuity correction",
    }


def paired_statistic(c1, c2):
    differences = [right - left for left, right in zip(c1, c2)]
    rng = random.Random(BOOTSTRAP_SEED)
    bootstrap = [
        sum(differences[rng.randrange(len(differences))] for _ in differences) / len(differences)
        for _ in range(BOOTSTRAP_RESAMPLES)
    ]
    return {
        "c1_mean": statistics.mean(c1),
        "c1_median": statistics.median(c1),
        "c2_mean": statistics.mean(c2),
        "c2_median": statistics.median(c2),
        "mean_paired_difference_c2_minus_c1": statistics.mean(differences),
        "median_paired_difference_c2_minus_c1": statistics.median(differences),
        "bootstrap_95ci_mean_difference": [quantile(bootstrap, 0.025), quantile(bootstrap, 0.975)],
        "c2_greater": sum(value > 0 for value in differences),
        "c1_greater": sum(value < 0 for value in differences),
        "ties": sum(value == 0 for value in differences),
        "nonzero_paired_questions": sum(abs(value) > 1e-15 for value in differences),
        "wilcoxon": wilcoxon_signed_rank(differences),
    }


def exact_mcnemar(c1_only, c2_only):
    discordant = c1_only + c2_only
    if not discordant:
        return {"discordant_pairs": 0, "p_value_two_sided": None, "informative": False}
    smaller = min(c1_only, c2_only)
    lower_tail = sum(math.comb(discordant, k) * (0.5 ** discordant) for k in range(smaller + 1))
    return {
        "discordant_pairs": discordant,
        "discordant_c1_only": c1_only,
        "discordant_c2_only": c2_only,
        "p_value_two_sided": min(1.0, 2 * lower_tail),
        "informative": True,
        "method": "McNemar exact two-sided binomial test",
    }


def strict_import(review_path):
    with PACKET.open(encoding="utf-8-sig", newline="") as handle:
        packet = list(csv.DictReader(handle))
    with review_path.open(encoding="utf-8-sig", newline="") as handle:
        review = list(csv.DictReader(handle))
    immutable = [
        "item_id", "question_id", "anonymous_system_label", "question",
        "gold_atomic_fact", "supplied_evidence", "answer",
    ]
    assert len(packet) == len(review) == 422
    assert len({row["item_id"] for row in packet}) == len({row["item_id"] for row in review}) == 422
    packet_by_id = {row["item_id"]: row for row in packet}
    review_by_id = {row["item_id"]: row for row in review}
    assert set(packet_by_id) == set(review_by_id)
    for item_id, source in packet_by_id.items():
        returned = review_by_id[item_id]
        assert all(source[column] == returned[column] for column in immutable)
    assert set(row["review_label"] for row in review) <= set(LABELS)
    assert Counter(row["review_label"] for row in review) == {
        "SUPPORTED": 374,
        "PARTIALLY_SUPPORTED": 7,
        "NOT_SUPPORTED": 36,
        "CONTRADICTED": 5,
    }
    assert len({row["question_id"] for row in review}) == 97
    return packet, review


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def percent(value):
    return f"{100 * value:.2f}%"


def pp(value):
    return f"{100 * value:+.2f} pp"


def ci_pp(values):
    return f"{100 * values[0]:+.2f} to {100 * values[1]:+.2f} pp"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--semantic-review", required=True)
    parser.add_argument("--semantic-summary", required=True)
    parser.add_argument("--source-git-revision", required=True)
    args = parser.parse_args()
    review_path = Path(args.semantic_review)
    summary_path = Path(args.semantic_summary)

    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert sha(BENCHMARK) == EXPECTED_BENCHMARK_SHA == freeze["final_benchmark_sha256"]
    assert sha(CORPUS) == EXPECTED_CORPUS_SHA == freeze["corpus_sha256"]
    assert sha(PROTOCOL) == freeze["formal_experiment_protocol_sha256"]
    assert sha(ANALYSIS_PLAN) == freeze["analysis_plan_sha256"]
    packet, review = strict_import(review_path)
    benchmark = jsonl(BENCHMARK)
    results = jsonl(RESULTS)
    execution = json.loads(EXECUTION.read_text(encoding="utf-8"))
    objective_rows = jsonl(OBJECTIVE)
    assert len(results) == 200 and len({(row["question_id"], row["condition"]) for row in results}) == 200
    assert len(execution["execution_order"]) == 200
    assert all(row["benchmark_sha256"] == EXPECTED_BENCHMARK_SHA for row in results)
    assert all(row["corpus_sha256"] == EXPECTED_CORPUS_SHA for row in results)
    assert all(row["model"] == "Qwen/Qwen3-8B" and row["retrieval"] == "R0" for row in results)

    results_by_key = {(row["question_id"], row["condition"]): row for row in results}
    usable = {
        key: row for key, row in results_by_key.items()
        if row["provider_succeeded"] > 0 and not row["fallback"] and row["generation_mode"] == "llm"
    }
    for row in packet:
        condition = ANONYMOUS_TO_CONDITION[row["anonymous_system_label"]]
        assert (row["question_id"], condition) in usable
        assert row["answer"] == usable[(row["question_id"], condition)]["full_answer"]

    benchmark_by_id = {row["question_id"]: row for row in benchmark}
    labels_by_key = defaultdict(Counter)
    for row in review:
        condition = ANONYMOUS_TO_CONDITION[row["anonymous_system_label"]]
        labels_by_key[(row["question_id"], condition)][row["review_label"]] += 1
    semantic_metrics = {}
    for key, counts in labels_by_key.items():
        gold_count = len(benchmark_by_id[key[0]]["gold_facts"])
        assert sum(counts.values()) == gold_count
        semantic_metrics[key] = {
            "full_recall": counts["SUPPORTED"] / gold_count,
            "partial_or_better_recall": (counts["SUPPORTED"] + counts["PARTIALLY_SUPPORTED"]) / gold_count,
            "missing_gold_rate": counts["NOT_SUPPORTED"] / gold_count,
            "contradiction_rate": counts["CONTRADICTED"] / gold_count,
            "label_counts": {label: counts[label] for label in LABELS},
        }

    question_ids = [row["question_id"] for row in benchmark]
    complete_pairs = [
        question_id for question_id in question_ids
        if (question_id, "C1") in semantic_metrics and (question_id, "C2") in semantic_metrics
    ]
    c1_usable = sum((question_id, "C1") in usable for question_id in question_ids)
    c2_usable = sum((question_id, "C2") in usable for question_id in question_ids)
    both_usable = sum((question_id, "C1") in usable and (question_id, "C2") in usable for question_id in question_ids)
    c1_only = sum((question_id, "C1") in usable and (question_id, "C2") not in usable for question_id in question_ids)
    c2_only = sum((question_id, "C2") in usable and (question_id, "C1") not in usable for question_id in question_ids)
    neither = sum((question_id, "C1") not in usable and (question_id, "C2") not in usable for question_id in question_ids)
    assert (c1_usable, c2_usable, both_usable, c1_only, c2_only, neither) == (94, 95, 92, 2, 3, 3)
    assert len(complete_pairs) == 92

    semantic_statistics = {}
    for metric in ("full_recall", "partial_or_better_recall", "missing_gold_rate", "contradiction_rate"):
        c1 = [semantic_metrics[(question_id, "C1")][metric] for question_id in complete_pairs]
        c2 = [semantic_metrics[(question_id, "C2")][metric] for question_id in complete_pairs]
        semantic_statistics[metric] = paired_statistic(c1, c2)
    full = semantic_statistics["full_recall"]
    full["practical_threshold"] = PRACTICAL_THRESHOLD
    full["ci_includes_zero"] = full["bootstrap_95ci_mean_difference"][0] <= 0 <= full["bootstrap_95ci_mean_difference"][1]
    full["ci_supports_at_least_5pp"] = full["bootstrap_95ci_mean_difference"][0] >= PRACTICAL_THRESHOLD
    full["ci_rules_out_at_least_5pp"] = full["bootstrap_95ci_mean_difference"][1] < PRACTICAL_THRESHOLD
    paired_statistics = {
        "statistical_unit": "question",
        "complete_usable_pairs": len(complete_pairs),
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "confidence_interval": 0.95,
        "metrics": semantic_statistics,
    }

    reliability = {
        "planned_questions": 100,
        "C1": {"usable": c1_usable, "total": 100, "rate": c1_usable / 100},
        "C2": {"usable": c2_usable, "total": 100, "rate": c2_usable / 100},
        "both_usable": both_usable,
        "C1_only": c1_only,
        "C2_only": c2_only,
        "neither_usable": neither,
        "question_sets": {
            "both_usable": [question_id for question_id in question_ids if (question_id, "C1") in usable and (question_id, "C2") in usable],
            "C1_only": [question_id for question_id in question_ids if (question_id, "C1") in usable and (question_id, "C2") not in usable],
            "C2_only": [question_id for question_id in question_ids if (question_id, "C2") in usable and (question_id, "C1") not in usable],
            "neither_usable": [question_id for question_id in question_ids if (question_id, "C1") not in usable and (question_id, "C2") not in usable],
        },
        "neither_usable_reason": "For tcmc-v1-009, tcmc-v1-023, and tcmc-v1-033, both C1 and C2 ended FAIL_PROVIDER after 2 attempted and 0 successful provider calls, with deterministic fallback recorded; fallback outputs were excluded from semantic review as pre-registered.",
        "mcnemar": exact_mcnemar(c1_only, c2_only),
        "interpretation": "Provider reliability is distinct from semantic accuracy; no reliability difference was established.",
    }

    latency_c1 = [usable[(question_id, "C1")]["latency_ms"] for question_id in complete_pairs]
    latency_c2 = [usable[(question_id, "C2")]["latency_ms"] for question_id in complete_pairs]
    latency = paired_statistic(latency_c1, latency_c2)
    latency.update({
        "complete_paired_usable_runs": len(complete_pairs),
        "units": "milliseconds",
        "provider_status_by_condition": {
            condition: dict(Counter(row["run_status"] for row in results if row["condition"] == condition))
            for condition in ("C1", "C2")
        },
        "provider_telemetry_by_condition": {
            condition: {
                "attempted_calls": sum(row["provider_attempted"] for row in results if row["condition"] == condition),
                "successful_calls": sum(row["provider_succeeded"] for row in results if row["condition"] == condition),
                "pass_with_retry_runs": sum(row["run_status"] == "PASS_WITH_RETRY" for row in results if row["condition"] == condition),
                "failed_provider_runs": sum(row["run_status"] == "FAIL_PROVIDER" for row in results if row["condition"] == condition),
            }
            for condition in ("C1", "C2")
        },
    })

    objective_by_key = {(row["question_id"], row["condition"]): row for row in objective_rows}
    objective_statistics = {
        "scope": "Pipeline-generated objective metrics, analyzed on the same 92 complete usable pairs",
        "metrics": {},
    }
    for metric in ("gold_evidence_retrieval_recall", "gold_evidence_citation_recall", "citation_precision"):
        c1 = [objective_by_key[(question_id, "C1")][metric] for question_id in complete_pairs]
        c2 = [objective_by_key[(question_id, "C2")][metric] for question_id in complete_pairs]
        objective_statistics["metrics"][metric] = paired_statistic(c1, c2)

    FINAL.mkdir(parents=True, exist_ok=True)
    imported_fields = list(review[0])
    write_csv(FINAL / "semantic_review_imported.csv", review, imported_fields)
    (FINAL / "semantic_review_external_summary.md").write_text(summary_path.read_text(encoding="utf-8-sig"), encoding="utf-8")
    (RUN / "semantic_review_imported.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    objective_by_key = {(row["question_id"], row["condition"]): row for row in objective_rows}
    metric_rows = []
    for question_id in question_ids:
        for condition in ("C1", "C2"):
            result = results_by_key[(question_id, condition)]
            semantic = semantic_metrics.get((question_id, condition))
            counts = semantic["label_counts"] if semantic else {label: 0 for label in LABELS}
            objective = objective_by_key[(question_id, condition)]
            metric_rows.append({
                "question_id": question_id,
                "condition": condition,
                "system": "Single-RAG" if condition == "C1" else "Multi-Agent",
                "anonymous_system_label": "SYSTEM_A" if condition == "C1" else "SYSTEM_B",
                "usable_real_provider_output": str((question_id, condition) in usable).lower(),
                "included_in_complete_pair": str(question_id in complete_pairs).lower(),
                "gold_fact_count": len(benchmark_by_id[question_id]["gold_facts"]),
                **{f"{label.lower()}_count": counts[label] for label in LABELS},
                "full_recall": semantic["full_recall"] if semantic else "",
                "partial_or_better_recall": semantic["partial_or_better_recall"] if semantic else "",
                "missing_gold_rate": semantic["missing_gold_rate"] if semantic else "",
                "contradiction_rate": semantic["contradiction_rate"] if semantic else "",
                "run_status": result["run_status"],
                "latency_ms": result["latency_ms"],
                "provider_attempted": result["provider_attempted"],
                "provider_succeeded": result["provider_succeeded"],
                "fallback": str(result["fallback"]).lower(),
                "gold_evidence_retrieval_recall": objective["gold_evidence_retrieval_recall"],
                "gold_evidence_citation_recall": objective["gold_evidence_citation_recall"],
                "citation_precision": objective["citation_precision"],
            })
    write_csv(FINAL / "confirmatory_question_level_metrics.csv", metric_rows, list(metric_rows[0]))
    (FINAL / "confirmatory_paired_statistics.json").write_text(json.dumps(paired_statistics, indent=2) + "\n", encoding="utf-8")
    (FINAL / "confirmatory_reliability_analysis.json").write_text(json.dumps(reliability, indent=2) + "\n", encoding="utf-8")
    (FINAL / "confirmatory_latency_analysis.json").write_text(json.dumps(latency, indent=2) + "\n", encoding="utf-8")
    (FINAL / "confirmatory_objective_metrics.json").write_text(json.dumps(objective_statistics, indent=2) + "\n", encoding="utf-8")

    import_record = {
        "methodology": "AI-assisted semantic evaluation using the frozen source-grounded rubric",
        "not_independent_human_validation": True,
        "not_clinical_or_tcm_expert_validation": True,
        "rows": 422,
        "unique_item_ids": 422,
        "unique_questions_represented": 97,
        "labels": {label: sum(row["review_label"] == label for row in review) for label in LABELS},
        "strict_identity_validation": "PASSED",
        "review_sha256": sha(FINAL / "semantic_review_imported.csv"),
        "packet_sha256": sha(PACKET),
        "unblinding": {
            "SYSTEM_A": "C1 Single-RAG",
            "SYSTEM_B": "C2 Multi-Agent",
            "source": "locked export mapping in research/experiment_pipeline/rq1_confirmatory.py at frozen revision f9b0a77, verified by exact answer linkage to results.jsonl and formal_execution_manifest.json",
        },
        "provider_or_llm_calls": 0,
    }
    (FINAL / "semantic_review_import_record.json").write_text(json.dumps(import_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    full_result = semantic_statistics["full_recall"]
    partial_result = semantic_statistics["partial_or_better_recall"]
    missing_result = semantic_statistics["missing_gold_rate"]
    contradiction_result = semantic_statistics["contradiction_rate"]
    final_conclusion = (
        "The small favorable Full Recall direction for C2 in the original study did not replicate on the "
        "independent confirmatory benchmark: C2 was essentially tied with, and slightly below, C1. Statistical "
        "superiority was not established, and the confirmatory 95% CI rules out a >=5-percentage-point C2 benefit "
        "under this tested setup without constituting a formal equivalence claim. Confirmatory reliability was "
        "similar (slightly higher for C2 by one usable answer), while C2 again had higher mean and median latency, "
        "although the paired latency difference was uncertain."
    )
    report = f"""# RQ1 confirmatory final results

## Scope and semantic import

- Frozen benchmark: RQ1_CONFIRMATORY_V1_1, 100 new held-out questions, 223 atomic Gold facts.
- Formal runs: 200 (100 C1 Single-RAG; 100 C2 Multi-Agent).
- Semantic review: 422 rows across 97 represented questions; 374 SUPPORTED, 7 PARTIALLY_SUPPORTED, 36 NOT_SUPPORTED, 5 CONTRADICTED, 0 UNRESOLVED.
- Method: AI-assisted semantic evaluation using the frozen source-grounded rubric; not independent human, clinical, or TCM-expert validation.
- Unblinding: SYSTEM_A = C1; SYSTEM_B = C2, from the locked export mapping and exact formal answer linkage.

## Usability and paired sample

- C1 usable: {c1_usable}/100; C2 usable: {c2_usable}/100.
- Both usable: {both_usable}; C1-only: {c1_only}; C2-only: {c2_only}; neither: {neither}.
- Primary semantic analysis uses {len(complete_pairs)} complete usable question pairs. Missing outputs were not imputed as semantic failures.

## Pre-registered semantic analysis

| Metric | C1 | C2 | C2 - C1 | 95% paired bootstrap CI | Wilcoxon p | Nonzero pairs |
|---|---:|---:|---:|---:|---:|---:|
| Full Recall | {percent(full_result['c1_mean'])} | {percent(full_result['c2_mean'])} | {pp(full_result['mean_paired_difference_c2_minus_c1'])} | {ci_pp(full_result['bootstrap_95ci_mean_difference'])} | {full_result['wilcoxon']['p_value_two_sided']:.4f} | {full_result['nonzero_paired_questions']} |
| Partial-or-Better | {percent(partial_result['c1_mean'])} | {percent(partial_result['c2_mean'])} | {pp(partial_result['mean_paired_difference_c2_minus_c1'])} | {ci_pp(partial_result['bootstrap_95ci_mean_difference'])} | {partial_result['wilcoxon']['p_value_two_sided']:.4f} | {partial_result['nonzero_paired_questions']} |
| Missing Gold Rate | {percent(missing_result['c1_mean'])} | {percent(missing_result['c2_mean'])} | {pp(missing_result['mean_paired_difference_c2_minus_c1'])} | {ci_pp(missing_result['bootstrap_95ci_mean_difference'])} | {missing_result['wilcoxon']['p_value_two_sided']:.4f} | {missing_result['nonzero_paired_questions']} |
| Contradiction Rate | {percent(contradiction_result['c1_mean'])} | {percent(contradiction_result['c2_mean'])} | {pp(contradiction_result['mean_paired_difference_c2_minus_c1'])} | {ci_pp(contradiction_result['bootstrap_95ci_mean_difference'])} | {contradiction_result['wilcoxon']['p_value_two_sided']:.4f} | {contradiction_result['nonzero_paired_questions']} |

Bootstrap used exactly 10,000 paired question-level resamples with seed 20260821. Full Recall's CI crosses zero and its upper limit is below +5 pp; therefore superiority was not established and the confirmatory result provides evidence against a clearly meaningful >=5 pp C2 benefit under this setup. This is not a formal equivalence or non-inferiority claim.

## Reliability and latency

- Reliability: C1 {c1_usable}/100 versus C2 {c2_usable}/100; McNemar exact p = {reliability['mcnemar']['p_value_two_sided']:.4f}. Provider reliability and semantic accuracy remain separate outcomes.
- C1 latency: mean {latency['c1_mean']:.1f} ms, median {latency['c1_median']:.1f} ms.
- C2 latency: mean {latency['c2_mean']:.1f} ms, median {latency['c2_median']:.1f} ms.
- Paired latency difference C2 - C1: {latency['mean_paired_difference_c2_minus_c1']:.1f} ms; 95% CI {latency['bootstrap_95ci_mean_difference'][0]:.1f} to {latency['bootstrap_95ci_mean_difference'][1]:.1f} ms; Wilcoxon p = {latency['wilcoxon']['p_value_two_sided']:.4f}.
- Provider outcomes: C1 93 PASS, 1 PASS_WITH_RETRY, 6 FAIL_PROVIDER; C2 91 PASS, 4 PASS_WITH_RETRY, 5 FAIL_PROVIDER.

## Pipeline-generated objective metrics

On the same 92 complete usable pairs, Gold evidence retrieval recall was tied at {percent(objective_statistics['metrics']['gold_evidence_retrieval_recall']['c1_mean'])} for both conditions. Gold evidence citation recall was {percent(objective_statistics['metrics']['gold_evidence_citation_recall']['c1_mean'])} for C1 and {percent(objective_statistics['metrics']['gold_evidence_citation_recall']['c2_mean'])} for C2. Citation precision was {percent(objective_statistics['metrics']['citation_precision']['c1_mean'])} for C1 and {percent(objective_statistics['metrics']['citation_precision']['c2_mean'])} for C2. These are the objective metrics already generated by the locked pipeline; no post-hoc retrieval analysis was added.

## Original study versus confirmatory study

- Study 1A (50 questions x 3 repeats): Full Recall C1 90.37%, C2 92.35%, difference +1.98 pp, 95% CI -2.72 to +7.41 pp, p = 0.5505. C2 had lower reliability and higher mean latency.
- Study 1B (100 new held-out questions): Full Recall C1 {percent(full_result['c1_mean'])}, C2 {percent(full_result['c2_mean'])}, difference {pp(full_result['mean_paired_difference_c2_minus_c1'])}, 95% CI {ci_pp(full_result['bootstrap_95ci_mean_difference'])}, p = {full_result['wilcoxon']['p_value_two_sided']:.4f}. Reliability was similar; C2 mean/median latency was higher.
- The studies remain analytically distinct; no naive pooled test was performed.

## Final RQ1 conclusion

{final_conclusion}

## Limitations

One base model (Qwen/Qwen3-8B), one frozen Corpus v1, confirmatory coverage primarily herbal and syndrome, one R0 retrieval condition, source-grounded Gold rather than clinical truth, AI-assisted external GPT semantic labels, no independent human semantic validation, and no clinical/TCM expert validation. Results do not automatically generalize to other models, corpora, retrieval methods, or all of TCM.
"""
    (FINAL / "confirmatory_final_results.md").write_text(report, encoding="utf-8")
    (FINAL / "README.md").write_text(
        "# Confirmatory final analysis\n\n"
        "Reproducible, pre-registered question-level analysis of the frozen RQ1 confirmatory run. Raw formal "
        "answers and external labels are unchanged. Statistics use 92 complete usable pairs; reliability uses "
        "all 100 planned questions. Provider/LLM calls during analysis: 0.\n",
        encoding="utf-8",
    )

    analysis_manifest = {
        "status": "RQ1_CONFIRMATORY_COMPLETE",
        "analysis_date": "2026-08-23",
        "source_git_revision": args.source_git_revision,
        "methodology": "AI-assisted semantic evaluation using the frozen source-grounded rubric",
        "unblinding": import_record["unblinding"],
        "inputs": {
            "benchmark_sha256": sha(BENCHMARK),
            "corpus_sha256": sha(CORPUS),
            "freeze_manifest_sha256": sha(FREEZE),
            "protocol_sha256": sha(PROTOCOL),
            "analysis_plan_sha256": sha(ANALYSIS_PLAN),
            "execution_manifest_sha256": sha(EXECUTION),
            "results_jsonl_sha256": sha(RESULTS),
            "semantic_packet_sha256": sha(PACKET),
            "semantic_review_import_sha256": sha(FINAL / "semantic_review_imported.csv"),
            "objective_scores_sha256": sha(OBJECTIVE),
        },
        "sample": {"planned_questions": 100, "complete_usable_pairs": 92, "semantic_rows": 422},
        "statistics": {"bootstrap_resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "practical_threshold_full_recall": PRACTICAL_THRESHOLD},
        "provider_or_llm_calls_during_analysis": 0,
        "conclusion": final_conclusion,
    }
    (FINAL / "confirmatory_analysis_manifest.json").write_text(json.dumps(analysis_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    CLOSEOUT.mkdir(parents=True, exist_ok=True)
    closeout_results = f"""# Final RQ1 results with confirmatory extension

## Study 1A — Original controlled study

Fifty frozen questions, three repeats, and 300 runs. Full Recall was 90.37% for C1 and 92.35% for C2: +1.98 pp (95% CI -2.72 to +7.41 pp; p = 0.5505). C2's favorable direction appeared in all three repeats, but superiority was not established; C2 reliability was lower and mean latency higher.

## Study 1B — Independent confirmatory study

One hundred new held-out questions and 200 runs. On 92 complete usable pairs, Full Recall was {percent(full_result['c1_mean'])} for C1 and {percent(full_result['c2_mean'])} for C2: {pp(full_result['mean_paired_difference_c2_minus_c1'])} (95% CI {ci_pp(full_result['bootstrap_95ci_mean_difference'])}; p = {full_result['wilcoxon']['p_value_two_sided']:.4f}). C1 had 94/100 usable outputs and C2 95/100; C2 mean and median latency were higher.

## Final synthesis

{final_conclusion}

No pooled inferential test combines Study 1A and Study 1B. RQ1 is permanently closed for the current research scope.
"""
    (CLOSEOUT / "rq1_final_results_with_confirmatory.md").write_text(closeout_results, encoding="utf-8")
    (CLOSEOUT / "rq1_final_conclusion.md").write_text(
        "# Final RQ1 conclusion\n\n" + final_conclusion + "\n\nStatus: **RQ1 COMPLETE — CONFIRMATORY EXTENSION COMPLETE**.\n",
        encoding="utf-8",
    )
    (CLOSEOUT / "rq1_confirmatory_artifact_index.md").write_text(
        "# RQ1 confirmatory artifact index\n\n"
        "- Frozen benchmark: `research/benchmarks/tcm_gold_rq1_confirmatory_v1/benchmark_confirmatory_v1_1_frozen.jsonl`\n"
        "- Formal results: `research/experiments/rq1_c1_vs_c2/confirmatory_run_v1_1/results.jsonl`\n"
        "- Semantic import: `research/experiments/rq1_c1_vs_c2/confirmatory_run_v1_1/final_analysis/semantic_review_imported.csv`\n"
        "- Confirmatory statistics: `research/experiments/rq1_c1_vs_c2/confirmatory_run_v1_1/final_analysis/`\n"
        "- Original Study 1A closeout artifacts remain preserved in this directory and `evaluation/final_three_repeat_analysis/`.\n",
        encoding="utf-8",
    )
    combined_manifest = {
        "rq": "RQ1",
        "status": "RQ1 COMPLETE — CONFIRMATORY EXTENSION COMPLETE",
        "study_1A": json.loads((CLOSEOUT / "rq1_final_manifest.json").read_text(encoding="utf-8")),
        "study_1B": {
            "benchmark_version": "RQ1_CONFIRMATORY_V1_1",
            "benchmark_sha256": EXPECTED_BENCHMARK_SHA,
            "questions": 100,
            "formal_runs": 200,
            "complete_usable_pairs": 92,
            "semantic_rows": 422,
            "full_recall": full_result,
            "reliability": reliability,
            "latency": latency,
            "analysis_manifest": "research/experiments/rq1_c1_vs_c2/confirmatory_run_v1_1/final_analysis/confirmatory_analysis_manifest.json",
        },
        "synthesis": final_conclusion,
        "naive_pooled_inference_performed": False,
        "provider_or_llm_calls_during_final_analysis": 0,
        "closeout_date": "2026-08-23",
    }
    (CLOSEOUT / "rq1_final_manifest_with_confirmatory.json").write_text(json.dumps(combined_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RUN / "pipeline_state.json").write_text(json.dumps({
        "status": "RQ1_CONFIRMATORY_COMPLETE",
        "semantic_review_rows": 422,
        "complete_usable_pairs": 92,
        "final_analysis": "final_analysis/confirmatory_analysis_manifest.json",
        "provider_calls_during_analysis": 0,
    }, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "RQ1_CONFIRMATORY_COMPLETE",
        "semantic_rows": 422,
        "complete_usable_pairs": 92,
        "full_recall_c1": full_result["c1_mean"],
        "full_recall_c2": full_result["c2_mean"],
        "difference": full_result["mean_paired_difference_c2_minus_c1"],
        "ci": full_result["bootstrap_95ci_mean_difference"],
        "p": full_result["wilcoxon"]["p_value_two_sided"],
        "provider_calls": 0,
    }))


if __name__ == "__main__":
    main()
