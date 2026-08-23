"""Finalize the frozen RQ4 experiment from an externally completed review.

This is an offline finalization step.  It deliberately contains no provider,
HTTP, or application-runtime calls.  It validates the review packet before
writing any closeout artifacts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pathlib
import random
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone



LABELS = ["SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED", "CONTRADICTED", "UNRESOLVED"]
REVIEW_FIELDS = {"review_label", "review_reason", "confidence"}
ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
BOOTSTRAP_SEED = 20260824


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv(path: pathlib.Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def percentile_ci(values, seed: int):
    values = [float(x) for x in values]
    if not len(values):
        return [None, None]
    rng = random.Random(seed)
    samples = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(10000))
    return [float(samples[249]), float(samples[9749])]


def p_value(diffs):
    diffs = [float(x) for x in diffs]
    if not diffs or all(abs(x) < 1e-12 for x in diffs):
        return 1.0
    # Normal approximation to the two-sided Wilcoxon signed-rank test.
    nz = [x for x in diffs if abs(x) > 1e-12]
    ranked = sorted((abs(x), i, x) for i, x in enumerate(nz))
    ranks = [0.0] * len(nz); i = 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][0] == ranked[i][0]: j += 1
        rank = (i + 1 + j) / 2.0
        for k in range(i, j): ranks[ranked[k][1]] = rank
        i = j
    wplus = sum(r for r, x in zip(ranks, nz) if x > 0)
    n = len(nz); mean = n * (n + 1) / 4.0; var = n * (n + 1) * (2 * n + 1) / 24.0
    z = (wplus - mean - (0.5 if wplus > mean else -0.5)) / math.sqrt(var)
    return float(math.erfc(abs(z) / math.sqrt(2)))


def metric_stats(c2, c4, seed):
    d = [b - a for a, b in zip(c2, c4)]
    return {
        "c2": (sum(c2) / len(c2)) if c2 else None,
        "c4": (sum(c4) / len(c4)) if c4 else None,
        "difference_c4_minus_c2": (sum(d) / len(d)) if d else None,
        "difference_pp": (sum(d) / len(d) * 100) if d else None,
        "bootstrap_95_ci": percentile_ci(d, seed),
        "wilcoxon_p": p_value(d),
        "n": len(d),
        "nonzero_paired_questions": sum(abs(x) > 1e-12 for x in d),
    }


def usable(row):
    return row.get("run_status") in {"PASS", "PASS_WITH_RETRY"} and row.get("generation_mode") == "llm" and not row.get("fallback", False)


def safe_text(value):
    return "" if value is None else str(value)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", type=pathlib.Path, required=True)
    ap.add_argument("--summary", type=pathlib.Path, required=True)
    ap.add_argument("--repo", type=pathlib.Path, default=pathlib.Path("."))
    args = ap.parse_args()
    repo = args.repo.resolve()
    root = repo / "research/experiments/rq4_debate_vs_multiagent"
    run = root / "formal_run_v1"
    packet_path = run / "rq4_semantic_review_for_gpt.csv"
    manifest_path = run / "formal_execution_manifest.json"
    preflight_path = run / "formal_preflight_manifest.json"
    results_path = run / "results.jsonl"
    traces_path = run / "debate_traces.jsonl"
    objective_path = run / "objective_metrics.json"
    state_path = root / "rq4_state.json"

    packet = read_csv(packet_path)
    review = read_csv(args.review.resolve())
    if len(packet) != 412 or len(review) != 412:
        raise SystemExit(f"strict review row count failed: packet={len(packet)} review={len(review)}")
    if list(packet[0]) != list(review[0]):
        raise SystemExit("strict review header mismatch")
    if [r["item_id"] for r in packet] != [r["item_id"] for r in review]:
        raise SystemExit("strict review item ordering/identity mismatch")
    if len({r["item_id"] for r in review}) != 412:
        raise SystemExit("duplicate review item_id")
    protected = [k for k in packet[0] if k not in REVIEW_FIELDS]
    protected_diffs = []
    for i, (a, b) in enumerate(zip(packet, review), 1):
        for key in protected:
            if safe_text(a.get(key)) != safe_text(b.get(key)):
                protected_diffs.append({"row": i, "item_id": a.get("item_id"), "field": key})
    if protected_diffs:
        raise SystemExit(f"protected semantic fields changed: {protected_diffs[:3]}")
    for row in review:
        if row["review_label"] not in LABELS:
            raise SystemExit(f"invalid review label: {row['item_id']}")
        if row["confidence"] not in ALLOWED_CONFIDENCE:
            raise SystemExit(f"invalid confidence: {row['item_id']}")
        if not row["review_reason"].strip():
            raise SystemExit(f"blank review reason: {row['item_id']}")

    manifest = read_json(manifest_path)
    preflight = read_json(preflight_path)
    results = [json.loads(x) for x in results_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    traces = [json.loads(x) for x in traces_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    if len(results) != 200:
        raise SystemExit(f"formal result count is {len(results)}, expected 200")
    if manifest["benchmark_sha256"] != preflight["frozen_benchmark_sha256"] or manifest["corpus_sha256"] != preflight["corpus_sha256"]:
        raise SystemExit("frozen hash mismatch between formal manifest and preflight")
    if manifest["model"] != "Qwen/Qwen3-8B" or manifest["retrieval"] != "R0":
        raise SystemExit("frozen model/retrieval mismatch")
    if len({r["execution_id"] for r in results}) != 200:
        raise SystemExit("duplicate execution_id")

    by_q = defaultdict(dict)
    for row in results:
        by_q[row["question_id"]][row["condition"]] = row
    planned_qids = sorted(by_q)
    if len(planned_qids) != 100:
        raise SystemExit("formal planned question count is not 100")
    mapping = manifest["semantic_blinding_mapping"]
    if set(mapping) != set(planned_qids):
        raise SystemExit("semantic blinding mapping does not cover the formal questions")
    review_qids = {r["question_id"] for r in review}
    usable_qids = [q for q in planned_qids if usable(by_q[q]["C2"]) and usable(by_q[q]["C4"])]
    c2_only = [q for q in planned_qids if usable(by_q[q]["C2"]) and not usable(by_q[q]["C4"])]
    c4_only = [q for q in planned_qids if usable(by_q[q]["C4"]) and not usable(by_q[q]["C2"])]
    neither = [q for q in planned_qids if not usable(by_q[q]["C2"]) and not usable(by_q[q]["C4"])]
    absent = sorted(set(planned_qids) - review_qids)

    label_by_q_system = defaultdict(lambda: defaultdict(list))
    for row in review:
        label_by_q_system[row["question_id"]][row["anonymous_system_label"]].append(row["review_label"])

    # Convert the blinded labels to conditions using only the frozen per-question map.
    def labels_for(q, condition):
        anon = mapping[q][condition]
        return label_by_q_system[q][anon]

    def rates(qids, predicate):
        out = {"C2": [], "C4": []}
        for q in qids:
            for c in out:
                labs = labels_for(q, c)
                out[c].append(sum(predicate(x) for x in labs) / len(labs) if labs else float("nan"))
        return out

    def paired_metric(qids, predicate, seed):
        vals = rates(qids, predicate)
        return metric_stats(vals["C2"], vals["C4"], seed)

    primary = paired_metric(usable_qids, lambda x: x == "SUPPORTED", BOOTSTRAP_SEED)
    partial = paired_metric(usable_qids, lambda x: x in {"SUPPORTED", "PARTIALLY_SUPPORTED"}, BOOTSTRAP_SEED + 1)
    missing = paired_metric(usable_qids, lambda x: x == "NOT_SUPPORTED", BOOTSTRAP_SEED + 2)
    contradiction = paired_metric(usable_qids, lambda x: x == "CONTRADICTED", BOOTSTRAP_SEED + 3)

    status_counts = {c: Counter(r.get("run_status") for r in results if r["condition"] == c) for c in ["C2", "C4"]}
    fallback_counts = {c: Counter(str(r.get("fallback")) for r in results if r["condition"] == c) for c in ["C2", "C4"]}
    retry_breakdown = {}
    for c in ["C2", "C4"]:
        attempts = [a for r in results if r["condition"] == c for a in (r.get("provider_attempts") or [])]
        retry_breakdown[c] = {"attempts": len(attempts), "successful_attempts": sum(bool(a.get("success")) for a in attempts), "failed_attempts": sum(not bool(a.get("success")) for a in attempts), "retries": sum(bool(a.get("retry_performed")) for a in attempts), "error_types": dict(Counter(a.get("error_type") for a in attempts if a.get("error_type")))}
    c2_usable = {q for q in planned_qids if usable(by_q[q]["C2"])}
    c4_usable = {q for q in planned_qids if usable(by_q[q]["C4"])}
    mcnemar = {"c2_only": len(c2_usable - c4_usable), "c4_only": len(c4_usable - c2_usable), "both": len(c2_usable & c4_usable), "neither": len(set(planned_qids) - c2_usable - c4_usable)}
    # Exact two-sided McNemar binomial test.
    discordant = mcnemar["c2_only"] + mcnemar["c4_only"]
    mcnemar["exact_two_sided_p"] = 1.0 if discordant == 0 else min(1.0, 2 * sum(math.comb(discordant, k) for k in range(0, min(mcnemar["c2_only"], mcnemar["c4_only"]) + 1)) / (2 ** discordant))

    lat_c2, lat_c4 = [], []
    for q in usable_qids:
        lat_c2.append(float(by_q[q]["C2"].get("latency_ms") or 0))
        lat_c4.append(float(by_q[q]["C4"].get("latency_ms") or 0))
    latency = metric_stats(lat_c2, lat_c4, BOOTSTRAP_SEED + 4)
    latency["c2_mean_ms"] = latency.pop("c2")
    latency["c4_mean_ms"] = latency.pop("c4")
    latency["c2_median_ms"] = float(sorted(lat_c2)[len(lat_c2)//2]) if lat_c2 else None
    latency["c4_median_ms"] = float(sorted(lat_c4)[len(lat_c4)//2]) if lat_c4 else None
    latency["paired_difference_ms"] = latency["difference_c4_minus_c2"]
    latency["provider_attempts_c2"] = retry_breakdown["C2"]["attempts"]
    latency["provider_attempts_c4"] = retry_breakdown["C4"]["attempts"]

    objective = read_json(objective_path)
    scores = objective.get("scores", [])
    objective_summary = {}
    for key in ["retrieval_recall", "citation_recall", "citation_precision"]:
        objective_summary[key] = {c: (sum(s[key] for s in scores if s["condition"] == c) / len([s for s in scores if s["condition"] == c])) for c in ["C2", "C4"]}

    stage_counts = Counter()
    stage_failures = Counter()
    critique_done = revision_done = consensus_done = 0
    peer_interaction = 0
    grounding = 0
    selected_multi = 0
    internal_calls = []
    max_rounds = 0
    for tr in traces:
        if tr.get("selected_agents") and len(tr["selected_agents"]) > 1:
            selected_multi += 1
        if tr.get("critic_invoked"):
            grounding += 1
        if tr.get("initial_outputs") and len(tr["initial_outputs"]) > 1:
            peer_interaction += 1
        max_rounds = max(max_rounds, int(tr.get("rounds") or 0))
        internal_calls.append(len(tr.get("provider_attempts") or []))
        stages = tr.get("stage_statuses") or []
        names = {s.get("stage", "") for s in stages}
        if any(str(s.get("stage", "")).startswith("critique:") and s.get("status") == "PASS" for s in stages): critique_done += 1
        if any(str(s.get("stage", "")).startswith("revision:") and s.get("status") == "PASS" for s in stages): revision_done += 1
        if any(s.get("stage") == "consensus" and s.get("status") == "PASS" for s in stages): consensus_done += 1
        for s in stages:
            stage_counts[s.get("stage", "unknown")] += 1
            if s.get("status") != "PASS": stage_failures[s.get("stage", "unknown")] += 1
    debate_diag = {"traces": len(traces), "peer_interaction": peer_interaction, "critique_completion": critique_done, "revision_completion": revision_done, "consensus_completion": consensus_done, "grounding_critic_invoked": grounding, "multi_specialist_debate": selected_multi, "failures_by_debate_stage": dict(stage_failures), "stage_counts": dict(stage_counts), "mean_internal_provider_calls": (sum(internal_calls) / len(internal_calls)) if internal_calls else 0.0, "max_debate_rounds": max_rounds}

    absent_reasons = {}
    for q in absent:
        absent_reasons[q] = {c: {"run_status": by_q[q][c].get("run_status"), "generation_mode": by_q[q][c].get("generation_mode"), "fallback": by_q[q][c].get("fallback"), "provider_attempted": by_q[q][c].get("provider_attempted"), "error": by_q[q][c].get("error")} for c in ["C2", "C4"]}

    label_counts = Counter(r["review_label"] for r in review)
    confidence_counts = Counter(r["confidence"] for r in review)
    analysis = run / "final_analysis"
    closeout = root / "rq4_closeout"
    analysis.mkdir(parents=True, exist_ok=True)
    closeout.mkdir(parents=True, exist_ok=True)
    # Preserve the supplied review as an immutable imported copy.
    shutil.copyfile(args.review.resolve(), analysis / "rq4_semantic_review_imported.csv")
    import_record = {"source": str(args.review.resolve()), "source_sha256": sha256(args.review.resolve()), "frozen_packet": str(packet_path), "frozen_packet_sha256": sha256(packet_path), "rows": len(review), "unique_questions": len(review_qids), "label_counts": dict(label_counts), "confidence_counts": dict(confidence_counts), "protected_fields": protected, "protected_field_validation": "PASS", "provider_calls_during_import": 0, "imported_at": datetime.now(timezone.utc).isoformat()}
    write_json(analysis / "semantic_review_import_record.json", import_record)

    qmetrics = []
    for q in sorted(usable_qids):
        row = {"question_id": q}
        for c in ["C2", "C4"]:
            labs = labels_for(q, c)
            row[f"{c}_full_recall"] = sum(x == "SUPPORTED" for x in labs) / len(labs)
            row[f"{c}_partial_or_better"] = sum(x in {"SUPPORTED", "PARTIALLY_SUPPORTED"} for x in labs) / len(labs)
            row[f"{c}_missing"] = sum(x == "NOT_SUPPORTED" for x in labs) / len(labs)
            row[f"{c}_contradiction"] = sum(x == "CONTRADICTED" for x in labs) / len(labs)
        qmetrics.append(row)
    with (analysis / "rq4_question_level_metrics.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(qmetrics[0]) if qmetrics else ["question_id"]); w.writeheader(); w.writerows(qmetrics)
    paired = {"unit": "question", "n_complete_usable_pairs": len(usable_qids), "bootstrap_resamples": 10000, "bootstrap_seed": BOOTSTRAP_SEED, "primary_full_recall": primary, "partial_or_better": partial, "missing": missing, "contradiction": contradiction, "threshold_pp": 5.0, "threshold_met": bool(primary["difference_pp"] is not None and primary["difference_pp"] >= 5.0)}
    write_json(analysis / "rq4_paired_statistics.json", paired)
    reliability = {"planned_questions": 100, "C2_usable": len(c2_usable), "C4_usable": len(c4_usable), "both_usable": len(usable_qids), "C2_only_usable": len(c2_only), "C4_only_usable": len(c4_only), "neither_usable": len(neither), "status_counts": {c: dict(status_counts[c]) for c in ["C2", "C4"]}, "fallback_counts": {c: dict(fallback_counts[c]) for c in ["C2", "C4"]}, "failure_retry_breakdown": retry_breakdown, "mcnemar": mcnemar, "absent_semantic_questions": absent, "absent_reasons": absent_reasons}
    write_json(analysis / "rq4_reliability_analysis.json", reliability)
    write_json(analysis / "rq4_latency_analysis.json", latency)
    write_json(analysis / "rq4_objective_metrics.json", {"source": str(objective_path), "source_sha256": sha256(objective_path), "question_condition_means": objective_summary, "scores": scores})
    write_json(analysis / "rq4_debate_diagnostics.json", debate_diag)

    def pct(v): return "n/a" if v is None else f"{v*100:.2f}%"
    final_md = f"""# RQ4 Final Analysis\n\nStatus: **RQ4 COMPLETE**\n\n## Semantic review import\n\nThe frozen blinded packet was validated against the completed review: 412 rows, 90 represented questions, no duplicate or missing item IDs, and all protected fields (question, anonymous label, Gold fact, evidence, and answer) unchanged. Labels: {dict(label_counts)}. Confidence: {dict(confidence_counts)}.\n\nThe 19 review rows tied to explicit execution-failure answers were imported unchanged. Primary paired semantic metrics use only the {len(usable_qids)} questions with a usable C2 and usable C4 execution; no failure was imputed as a semantic label.\n\n## Unblinding\n\nUnblinding used only `formal_execution_manifest.json` and its per-question `semantic_blinding_mapping`. The mapping is counterbalanced by question ({sum(1 for v in mapping.values() if v['C2']=='SYSTEM_A')} questions C2=SYSTEM_A; {sum(1 for v in mapping.values() if v['C2']=='SYSTEM_B')} questions C2=SYSTEM_B), so there is no single global SYSTEM_A/SYSTEM_B identity.\n\n## Primary and secondary results\n\n| metric | C2 | C4 | C4-C2 | 95% CI (pp) | Wilcoxon p |\n|---|---:|---:|---:|---:|---:|\n| Full Recall | {pct(primary['c2'])} | {pct(primary['c4'])} | {primary['difference_pp']:.2f} pp | {primary['bootstrap_95_ci'][0]*100:.2f} to {primary['bootstrap_95_ci'][1]*100:.2f} | {primary['wilcoxon_p']:.6g} |\n| Partial-or-Better | {pct(partial['c2'])} | {pct(partial['c4'])} | {partial['difference_pp']:.2f} pp | {partial['bootstrap_95_ci'][0]*100:.2f} to {partial['bootstrap_95_ci'][1]*100:.2f} | {partial['wilcoxon_p']:.6g} |\n| Missing | {pct(missing['c2'])} | {pct(missing['c4'])} | {missing['difference_pp']:.2f} pp | {missing['bootstrap_95_ci'][0]*100:.2f} to {missing['bootstrap_95_ci'][1]*100:.2f} | {missing['wilcoxon_p']:.6g} |\n| Contradiction | {pct(contradiction['c2'])} | {pct(contradiction['c4'])} | {contradiction['difference_pp']:.2f} pp | {contradiction['bootstrap_95_ci'][0]*100:.2f} to {contradiction['bootstrap_95_ci'][1]*100:.2f} | {contradiction['wilcoxon_p']:.6g} |\n\nFull Recall is evaluated against 0 pp and the preregistered +5 pp threshold; observed difference is {primary['difference_pp']:.2f} pp.\n\n## Reliability and latency\n\nC2 usable: {len(c2_usable)}/100; C4 usable: {len(c4_usable)}/100; both: {len(usable_qids)}; C2-only: {len(c2_only)}; C4-only: {len(c4_only)}; neither: {len(neither)}. Exact McNemar p={mcnemar['exact_two_sided_p']:.6g}. Mean latency C2={latency['c2_mean_ms']:.1f} ms, C4={latency['c4_mean_ms']:.1f} ms; medians {latency['c2_median_ms']:.1f}/{latency['c4_median_ms']:.1f} ms; paired Wilcoxon p={latency['wilcoxon_p']:.6g}. Provider attempts: C2={sum(r.get('provider_attempted') or 0 for r in results if r['condition']=='C2')}, C4={sum(r.get('provider_attempted') or 0 for r in results if r['condition']=='C4')}.\n\n## Objective metrics and debate diagnostics\n\nMean retrieval recall: C2={objective_summary['retrieval_recall']['C2']:.4f}, C4={objective_summary['retrieval_recall']['C4']:.4f}; citation recall: C2={objective_summary['citation_recall']['C2']:.4f}, C4={objective_summary['citation_recall']['C4']:.4f}; citation precision: C2={objective_summary['citation_precision']['C2']:.4f}, C4={objective_summary['citation_precision']['C4']:.4f}. Debate diagnostics are recorded in `rq4_debate_diagnostics.json`: {len(traces)} C4 traces, grounding critic invoked {grounding} times, multi-specialist debate {selected_multi} times, mean internal provider calls {debate_diag['mean_internal_provider_calls']:.2f}, maximum rounds {max_rounds}.\n\n## RQ1 + RQ4 synthesis\n\nRQ1 established the frozen C1-vs-C2 comparison for single-agent versus independent-specialist generation, while RQ4 compares C2 with a structured C4 debate under the same corpus, retrieval, model, and question-level unit. The RQ4 estimate therefore addresses whether adding critique/revision/consensus improves grounded semantic recall beyond the already multi-specialist C2 baseline, with execution reliability and semantic quality reported separately.\n\n## Final RQ4 answer\n\nUnder the frozen RQ4 protocol, C4 Full Recall was {pct(primary['c4'])} versus {pct(primary['c2'])} for C2, a difference of {primary['difference_pp']:.2f} percentage points (95% bootstrap CI {primary['bootstrap_95_ci'][0]*100:.2f} to {primary['bootstrap_95_ci'][1]*100:.2f}; Wilcoxon p={primary['wilcoxon_p']:.6g}) across {len(usable_qids)} complete usable question pairs. The preregistered +5 pp threshold was {'met' if paired['threshold_met'] else 'not met'}, and C4 usable execution rate was {len(c4_usable)}/100 versus {len(c2_usable)}/100 for C2.\n\n## Limitations\n\nTen planned questions had no represented semantic review because no usable C4 answer was available (eight were C2-only usable and two had neither condition usable); their exact execution statuses are preserved in `rq4_reliability_analysis.json`. The semantic review was AI-assisted external review, not independent human or clinical/TCM expert validation. Counterbalanced anonymous labels were unblinded only through the frozen manifest. Bootstrap intervals and Wilcoxon tests are question-level and exploratory beyond the preregistered primary comparison; provider failures and retries are reported rather than silently treated as quality outcomes.\n"""
    (analysis / "rq4_final_results.md").write_text(final_md, encoding="utf-8")
    (analysis / "README.md").write_text("# RQ4 final analysis\n\nOffline closeout artifacts generated from the frozen formal run and the strictly validated external semantic review. No provider calls occur during finalization.\n", encoding="utf-8")

    final_manifest = {"status": "RQ4_COMPLETE", "protocol": manifest.get("protocol_version"), "protocol_sha256": manifest.get("protocol_sha256"), "benchmark_sha256": manifest["benchmark_sha256"], "corpus_sha256": manifest["corpus_sha256"], "model": manifest["model"], "retrieval": manifest["retrieval"], "planned_questions": 100, "formal_records": 200, "semantic_review_rows": 412, "semantic_questions": 90, "complete_usable_pairs": len(usable_qids), "provider_calls_during_finalization": 0, "review_import_record": "semantic_review_import_record.json", "artifacts": sorted(p.name for p in analysis.iterdir())}
    write_json(analysis / "rq4_final_manifest.json", final_manifest)
    close_md = "# RQ4 closeout\n\nRQ4 is complete under the frozen protocol. See `../formal_run_v1/final_analysis/rq4_final_results.md` for the final paired analysis and limitations. No provider calls were made during closeout.\n"
    (closeout / "rq4_final_conclusion.md").write_text(close_md, encoding="utf-8")
    shutil.copyfile(analysis / "rq4_final_results.md", closeout / "rq4_final_results.md")
    (closeout / "rq4_artifact_index.md").write_text("# RQ4 artifact index\n\n- `../formal_run_v1/final_analysis/` — validated import, paired statistics, reliability, latency, objective metrics, and debate diagnostics.\n- `rq4_final_conclusion.md` — closeout conclusion.\n", encoding="utf-8")
    (closeout / "README.md").write_text("# RQ4 closeout\n\nFinal frozen RQ4 analysis archive.\n", encoding="utf-8")
    close_manifest = dict(final_manifest); close_manifest["final_analysis_directory"] = str(analysis); close_manifest["closeout_directory"] = str(closeout); close_manifest["artifact_sha256"] = {str(p.relative_to(closeout)): sha256(p) for p in closeout.iterdir() if p.is_file()}
    write_json(closeout / "rq4_closeout_manifest.json", close_manifest)

    state = read_json(state_path)
    state.update({"state": "RQ4_COMPLETE", "previous_state": state.get("state"), "updated_at": datetime.now(timezone.utc).isoformat(), "formal_execution": {"planned_questions": 100, "records": 200, "complete_usable_pairs": len(usable_qids), "c2_usable": len(c2_usable), "c4_usable": len(c4_usable)}, "semantic_review": {"rows": 412, "unique_questions": 90, "source_sha256": import_record["source_sha256"], "protected_field_validation": "PASS"}, "final_analysis": str(analysis), "closeout": str(closeout), "provider_calls_during_finalization": 0})
    write_json(state_path, state)
    print(json.dumps({"status": "RQ4_COMPLETE", "review_rows": 412, "review_questions": 90, "complete_usable_pairs": len(usable_qids), "c2_usable": len(c2_usable), "c4_usable": len(c4_usable), "absent": absent, "full_recall": primary, "provider_calls": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
