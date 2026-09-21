#!/usr/bin/env python3
"""Deterministic deblinding and analysis for Western Semantic Follow-up v0.2.

This script is intentionally offline: it reads the frozen blinded judgment
workbook and local blind key, performs schema checks before joining, and
writes only derived analysis artifacts.  It never calls a provider or model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook


EXPECTED_WORKBOOK_SHA = "81b260b4ad424d6f52a36414e30fd8e7bd22068d8f3e02496a39d7320593fc80"
EXPECTED_BLIND_KEY_SHA = "6a7a287754ba14651a1b6fe61a4e0a49d2815fe96e013e564cf6b75a44f1f4e5"
EXPECTED_EXPORT_MANIFEST_SHA = "3eaa05cf1bd7d0eda39a0599abaa26569662020b715753295df982d01eaef343"
EXPECTED_CONDITIONS = ("R0", "R1", "R2", "R3")
EXPECTED_ANSWERABILITY = ("supported", "partially_supported", "insufficient")
EXPECTED_LABELS = ("covered", "partially_covered", "not_covered", "contradicted")
INSUFFICIENT_LABELS = (
    "appropriate_abstention",
    "appropriate_bounded_insufficiency",
    "substantive_answer_without_insufficiency_acknowledgement",
    "overclaim_beyond_pilot_evidence",
)
BOOTSTRAP_SEED = 20260815
BOOTSTRAP_RESAMPLES = 10_000

EVALUATION_HEADERS = [
    "blind_id",
    "question",
    "answerability",
    "expected_evidence_points",
    "insufficiency_context",
    "evidence_1",
    "evidence_2",
    "evidence_3",
    "evidence_4",
    "generated_answer",
    "expected_point_judgments",
    "n_expected_points",
    "n_fully_covered",
    "n_partially_covered",
    "n_not_covered",
    "n_contradicted",
    "full_coverage_score",
    "partial_credit_coverage_score",
    "unsupported_claim_present",
    "unsupported_claim_count",
    "contradiction_present",
    "insufficient_handling",
    "judge_confidence",
    "judge_rationale",
]

SEMANTIC_FIELDS = [
    "expected_evidence_points",
    "expected_point_judgments",
    "n_expected_points",
    "n_fully_covered",
    "n_partially_covered",
    "n_not_covered",
    "n_contradicted",
    "full_coverage_score",
    "partial_credit_coverage_score",
    "unsupported_claim_present",
    "unsupported_claim_count",
    "contradiction_present",
    "insufficient_handling",
    "judge_confidence",
    "judge_rationale",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def norm(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def as_int(value: Any, field: str, row_id: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{row_id}: {field} must be an integer")
    if int(value) != value:
        raise ValueError(f"{row_id}: {field} must be an integer")
    return int(value)


def as_bool(value: Any, field: str, row_id: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise ValueError(f"{row_id}: {field} must be boolean")


def parse_judgments(value: Any, row_id: str) -> dict[str, str]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{row_id}: expected_point_judgments is required")
    parsed: dict[str, str] = {}
    for part in value.split(";"):
        if "=" not in part:
            raise ValueError(f"{row_id}: malformed expected point judgment")
        point, label = [x.strip() for x in part.split("=", 1)]
        if not re.fullmatch(r"P\d+", point) or label not in EXPECTED_LABELS:
            raise ValueError(f"{row_id}: invalid expected point judgment")
        if point in parsed:
            raise ValueError(f"{row_id}: duplicate expected point judgment")
        parsed[point] = label
    return parsed


def validate_workbook(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"judgment workbook does not exist: {path}")
    actual_sha = sha256(path)
    if actual_sha != EXPECTED_WORKBOOK_SHA:
        raise ValueError(
            f"judgment workbook SHA mismatch: expected {EXPECTED_WORKBOOK_SHA}, got {actual_sha}"
        )
    wb = load_workbook(path, read_only=True, data_only=True)
    if wb.sheetnames != ["evaluation", "rubric"]:
        raise ValueError(f"unexpected workbook sheets: {wb.sheetnames}")
    ws = wb["evaluation"]
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) != 193:
        raise ValueError(f"expected 193 evaluation rows including header, got {len(rows)}")
    headers = [norm(x) for x in rows[0]]
    if headers != EVALUATION_HEADERS:
        raise ValueError("evaluation workbook schema mismatch")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows[1:]:
        rec = {headers[i]: norm(raw[i]) for i in range(len(headers))}
        blind_id = rec["blind_id"]
        if not isinstance(blind_id, str) or not re.fullmatch(r"EV\d{4}", blind_id):
            raise ValueError(f"invalid blind_id: {blind_id!r}")
        if blind_id in seen:
            raise ValueError(f"duplicate blind_id: {blind_id}")
        seen.add(blind_id)
        answerability = rec["answerability"]
        if answerability not in EXPECTED_ANSWERABILITY:
            raise ValueError(f"{blind_id}: invalid answerability")
        # No condition labels may appear in the blinded structure or values.
        if any(re.fullmatch(r"R[0-3]", str(v)) for v in rec.values() if v is not None):
            raise ValueError(f"{blind_id}: retrieval-condition label leaked into workbook")
        rec["unsupported_claim_present"] = as_bool(
            rec["unsupported_claim_present"], "unsupported_claim_present", blind_id
        )
        rec["contradiction_present"] = as_bool(
            rec["contradiction_present"], "contradiction_present", blind_id
        )
        rec["judge_confidence"] = rec["judge_confidence"]
        if rec["judge_confidence"] not in ("high", "medium", "low"):
            raise ValueError(f"{blind_id}: invalid judge_confidence")
        insufficient_handling = rec["insufficient_handling"]
        if answerability == "insufficient":
            if insufficient_handling not in INSUFFICIENT_LABELS:
                raise ValueError(f"{blind_id}: invalid insufficient_handling")
            n_expected = as_int(rec["n_expected_points"], "n_expected_points", blind_id)
            if n_expected == 0:
                if rec["expected_point_judgments"] not in (None, ""):
                    raise ValueError(f"{blind_id}: zero-point insufficient row has judgments")
                for field in ("full_coverage_score", "partial_credit_coverage_score"):
                    if rec[field] is not None:
                        raise ValueError(f"{blind_id}: zero-point insufficient row has nonblank {field}")
                for field in ("n_fully_covered", "n_partially_covered", "n_not_covered", "n_contradicted"):
                    if as_int(rec[field], field, blind_id) != 0:
                        raise ValueError(f"{blind_id}: zero-point insufficient row has nonzero {field}")
            else:
                parsed = parse_judgments(rec["expected_point_judgments"], blind_id)
                if len(parsed) != n_expected:
                    raise ValueError(f"{blind_id}: insufficient point count does not match n_expected_points")
                counts = Counter(parsed.values())
                for field, label in (("n_fully_covered", "covered"), ("n_partially_covered", "partially_covered"), ("n_not_covered", "not_covered"), ("n_contradicted", "contradicted")):
                    if as_int(rec[field], field, blind_id) != counts[label]:
                        raise ValueError(f"{blind_id}: insufficient {field} inconsistent with labels")
                for field in ("full_coverage_score", "partial_credit_coverage_score"):
                    if not isinstance(rec[field], (int, float)) or isinstance(rec[field], bool) or not 0 <= rec[field] <= 1:
                        raise ValueError(f"{blind_id}: insufficient {field} outside [0,1]")
        else:
            if insufficient_handling not in (None, ""):
                raise ValueError(f"{blind_id}: answerable row has insufficient_handling")
            n_expected = as_int(rec["n_expected_points"], "n_expected_points", blind_id)
            if n_expected <= 0:
                raise ValueError(f"{blind_id}: answerable row must have positive expected points")
            parsed = parse_judgments(rec["expected_point_judgments"], blind_id)
            if len(parsed) != n_expected:
                raise ValueError(f"{blind_id}: point count does not match n_expected_points")
            counts = Counter(parsed.values())
            expected_counts = {
                "n_fully_covered": counts["covered"],
                "n_partially_covered": counts["partially_covered"],
                "n_not_covered": counts["not_covered"],
                "n_contradicted": counts["contradicted"],
            }
            for field, expected in expected_counts.items():
                if as_int(rec[field], field, blind_id) != expected:
                    raise ValueError(f"{blind_id}: {field} inconsistent with labels")
            for field in ("full_coverage_score", "partial_credit_coverage_score"):
                value = rec[field]
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
                    raise ValueError(f"{blind_id}: {field} outside [0,1]")
            if not math.isclose(
                rec["full_coverage_score"], expected_counts["n_fully_covered"] / n_expected, abs_tol=1e-12
            ):
                raise ValueError(f"{blind_id}: full_coverage_score inconsistent")
            partial_expected = (
                expected_counts["n_fully_covered"] + 0.5 * expected_counts["n_partially_covered"]
            ) / n_expected
            if not math.isclose(rec["partial_credit_coverage_score"], partial_expected, abs_tol=1e-12):
                raise ValueError(f"{blind_id}: partial_credit_coverage_score inconsistent")
        unsupported_count = as_int(rec["unsupported_claim_count"], "unsupported_claim_count", blind_id)
        if unsupported_count < 0:
            raise ValueError(f"{blind_id}: unsupported_claim_count is negative")
        records.append(rec)
    if len(records) != 192 or len(seen) != 192:
        raise ValueError("evaluation row/ID count mismatch")
    return records


def read_key(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_fields = ["blind_id", "experiment_id", "case_id", "retrieval_condition", "original_stage_b_row_index"]
    if not rows or list(rows[0]) != expected_fields:
        raise ValueError("blind key schema mismatch")
    if len(rows) != 192:
        raise ValueError(f"expected 192 blind-key rows, got {len(rows)}")
    blind_ids = [r["blind_id"] for r in rows]
    if len(set(blind_ids)) != 192:
        raise ValueError("blind key has duplicate blind IDs")
    if set(blind_ids) != {f"EV{i:04d}" for i in range(1, 193)}:
        raise ValueError("blind key blind-ID set is not EV0001-EV0192")
    conditions = Counter(r["retrieval_condition"] for r in rows)
    if conditions != Counter({c: 48 for c in EXPECTED_CONDITIONS}):
        raise ValueError(f"unexpected condition counts: {conditions}")
    cases = defaultdict(set)
    for row in rows:
        if row["retrieval_condition"] not in EXPECTED_CONDITIONS:
            raise ValueError("invalid retrieval condition in blind key")
        cases[row["case_id"]].add(row["retrieval_condition"])
    if len(cases) != 48 or any(set(EXPECTED_CONDITIONS) != conds for conds in cases.values()):
        raise ValueError("each of 48 cases must contain exactly R0/R1/R2/R3")
    if len({(r["case_id"], r["retrieval_condition"]) for r in rows}) != 192:
        raise ValueError("duplicate case-condition pair in blind key")
    return rows


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate percentile of empty values")
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def bootstrap_ci(values: list[float]) -> list[float]:
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(values)
    estimates = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        estimates.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def summary(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "mean": statistics.mean(values) if values else None,
        "sd": statistics.stdev(values) if len(values) > 1 else None,
        "median": statistics.median(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def exact_mcnemar(b: int, c: int) -> float:
    discordant = b + c
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, k) for k in range(min(b, c) + 1)) / (2 ** discordant)
    return min(1.0, 2.0 * tail)


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda kv: (kv[1], kv[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    m = len(ordered)
    for rank, (name, p_value) in enumerate(ordered, start=1):
        running = max(running, min(1.0, (m - rank + 1) * p_value))
        adjusted[name] = running
    return adjusted


def csv_write(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fieldnames})
    content = handle.getvalue().encode("utf-8")
    if path.exists() and path.read_bytes() == content:
        return
    path.write_bytes(content)


def fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument(
        "--blind-key",
        type=Path,
        default=Path("research/experiments/western_semantic_followup_v0_2/stage_c2_blind_key.csv"),
    )
    parser.add_argument(
        "--export-manifest",
        type=Path,
        default=Path("research/experiments/western_semantic_followup_v0_2/stage_c2_export_manifest.json"),
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("research/experiments/western_semantic_followup_v0_2/analysis_plan_predeblind.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/experiments/western_semantic_followup_v0_2"),
    )
    args = parser.parse_args()
    output_dir = args.output_dir
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    # The plan must have existed before the key is consumed; the plan is never rewritten here.
    if not args.plan.exists():
        raise ValueError("pre-deblind analysis plan is missing")
    plan_sha = sha256(args.plan)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if plan.get("status") != "frozen_before_blind_key_access":
        raise ValueError("analysis plan is not frozen before blind-key access")

    if not args.export_manifest.exists():
        raise ValueError(f"export manifest does not exist: {args.export_manifest}")
    export_manifest_sha = sha256(args.export_manifest)
    if export_manifest_sha != EXPECTED_EXPORT_MANIFEST_SHA:
        raise ValueError("export manifest SHA mismatch")
    if sha256(args.blind_key) != EXPECTED_BLIND_KEY_SHA:
        raise ValueError("blind key SHA mismatch")
    export_manifest = json.loads(args.export_manifest.read_text(encoding="utf-8"))
    if export_manifest.get("outputs", {}).get("blind_key", {}).get("sha256") != EXPECTED_BLIND_KEY_SHA:
        raise ValueError("export manifest blind-key hash does not match frozen expected hash")
    records = validate_workbook(args.workbook)
    key_rows = read_key(args.blind_key)
    record_by_id = {r["blind_id"]: r for r in records}
    key_by_id = {r["blind_id"]: r for r in key_rows}
    if set(record_by_id) != set(key_by_id):
        raise ValueError("blind-key and workbook IDs do not match")
    joined: list[dict[str, Any]] = []
    for blind_id in sorted(record_by_id):
        row = record_by_id[blind_id]
        key = key_by_id[blind_id]
        joined.append(
            {
                "blind_id": blind_id,
                "case_id": key["case_id"],
                "retrieval_condition": key["retrieval_condition"],
                "answerability": row["answerability"],
                **{field: row[field] for field in SEMANTIC_FIELDS},
            }
        )

    # Preserve the annotation fields but not question/evidence/full answer text.
    deblinded_path = output_dir / "stage_c2_deblinded_judgments.csv"
    csv_write(deblinded_path, ["blind_id", "case_id", "retrieval_condition", "answerability", *SEMANTIC_FIELDS], joined)

    answerable = [r for r in joined if r["answerability"] in ("supported", "partially_supported")]
    insufficient = [r for r in joined if r["answerability"] == "insufficient"]
    if len({r["case_id"] for r in answerable}) != 42 or len(answerable) != 168:
        raise ValueError("W-RQ2 population does not have 42 cases / 168 rows")
    if len({r["case_id"] for r in insufficient}) != 6 or len(insufficient) != 24:
        raise ValueError("W-RQ3 population does not have 6 cases / 24 rows")

    by_condition = {c: [r for r in answerable if r["retrieval_condition"] == c] for c in EXPECTED_CONDITIONS}
    by_case_condition = {(r["case_id"], r["retrieval_condition"]): r for r in answerable}

    primary_rows = []
    partial_rows = []
    unsupported_presence_rows = []
    unsupported_count_rows = []
    contradictions_rows = []
    label_rows = []
    for condition in EXPECTED_CONDITIONS:
        rows = by_condition[condition]
        primary_rows.append({"retrieval_condition": condition, **summary([r["full_coverage_score"] for r in rows])})
        partial_rows.append({"retrieval_condition": condition, **summary([r["partial_credit_coverage_score"] for r in rows])})
        present = sum(1 for r in rows if r["unsupported_claim_present"])
        unsupported_presence_rows.append(
            {"retrieval_condition": condition, "true_count": present, "false_count": len(rows) - present, "rate": present / len(rows), "n": len(rows)}
        )
        unsupported_count_rows.append({"retrieval_condition": condition, **summary([r["unsupported_claim_count"] for r in rows])})
        contradicted = sum(1 for r in rows if r["contradiction_present"])
        contradictions_rows.append(
            {"retrieval_condition": condition, "true_count": contradicted, "false_count": len(rows) - contradicted, "rate": contradicted / len(rows), "total_n_contradicted": sum(r["n_contradicted"] for r in rows), "n": len(rows)}
        )
        label_count = Counter()
        for r in rows:
            label_count.update(parse_judgments(r["expected_point_judgments"], r["blind_id"]).values())
        label_rows.append({"retrieval_condition": condition, **{label: label_count[label] for label in EXPECTED_LABELS}, "total_expected_points": sum(r["n_expected_points"] for r in rows), "n_cases": len({r["case_id"] for r in rows})})

    pairwise_primary = []
    pairwise_partial = []
    pairwise_count = []
    mcnemar_rows = []
    raw_p: dict[str, float] = {}
    for condition in EXPECTED_CONDITIONS[1:]:
        pairs = [(by_case_condition[(case, condition)], by_case_condition[(case, "R0")]) for case in sorted({r["case_id"] for r in answerable})]
        primary_diff = [a["full_coverage_score"] - b["full_coverage_score"] for a, b in pairs]
        partial_diff = [a["partial_credit_coverage_score"] - b["partial_credit_coverage_score"] for a, b in pairs]
        count_diff = [a["unsupported_claim_count"] - b["unsupported_claim_count"] for a, b in pairs]
        pairwise_primary.append({"comparison": f"{condition} - R0", "comparison_condition": condition, "n": len(pairs), "mean_difference": statistics.mean(primary_diff), "median_difference": statistics.median(primary_diff), "bootstrap_ci_95_low": bootstrap_ci(primary_diff)[0], "bootstrap_ci_95_high": bootstrap_ci(primary_diff)[1], "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_resamples": BOOTSTRAP_RESAMPLES})
        pairwise_partial.append({"comparison": f"{condition} - R0", "comparison_condition": condition, "n": len(pairs), "mean_difference": statistics.mean(partial_diff), "median_difference": statistics.median(partial_diff), "bootstrap_ci_95_low": bootstrap_ci(partial_diff)[0], "bootstrap_ci_95_high": bootstrap_ci(partial_diff)[1], "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_resamples": BOOTSTRAP_RESAMPLES})
        pairwise_count.append({"comparison": f"{condition} - R0", "comparison_condition": condition, "n": len(pairs), "mean_difference": statistics.mean(count_diff), "bootstrap_ci_95_low": bootstrap_ci(count_diff)[0], "bootstrap_ci_95_high": bootstrap_ci(count_diff)[1], "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_resamples": BOOTSTRAP_RESAMPLES})
        b = sum(1 for a, base in pairs if not base["unsupported_claim_present"] and a["unsupported_claim_present"])
        c = sum(1 for a, base in pairs if base["unsupported_claim_present"] and not a["unsupported_claim_present"])
        p_value = exact_mcnemar(b, c)
        raw_p[condition] = p_value
        mcnemar_rows.append({"comparison": f"{condition} vs R0", "comparison_condition": condition, "r0_false_comparison_true": b, "r0_true_comparison_false": c, "discordant_total": b + c, "exact_two_sided_mcnemar_p_raw": p_value})
    adjusted = holm_adjust(raw_p)
    for row in mcnemar_rows:
        row["holm_adjusted_p"] = adjusted[row["comparison_condition"]]
        row["holm_family_size"] = 3

    wrq3_rows = [r for r in joined if r["answerability"] == "insufficient"]
    wrq3_dist = []
    wrq3_case = []
    for condition in EXPECTED_CONDITIONS:
        rows = [r for r in wrq3_rows if r["retrieval_condition"] == condition]
        counts = Counter(r["insufficient_handling"] for r in rows)
        wrq3_dist.append({"retrieval_condition": condition, "n": len(rows), **{label: counts[label] for label in INSUFFICIENT_LABELS}, **{f"{label}_proportion": counts[label] / len(rows) for label in INSUFFICIENT_LABELS}})
        for r in sorted(rows, key=lambda x: x["case_id"]):
            wrq3_case.append({"case_id": r["case_id"], "retrieval_condition": condition, "insufficient_handling": r["insufficient_handling"]})

    table_specs = {
        "w_rq2_primary_coverage_by_condition.csv": (["retrieval_condition", "n", "mean", "sd", "median", "min", "max"], primary_rows),
        "w_rq2_primary_pairwise_vs_r0.csv": (list(pairwise_primary[0]), pairwise_primary),
        "w_rq2_partial_credit_by_condition.csv": (["retrieval_condition", "n", "mean", "sd", "median", "min", "max"], partial_rows),
        "w_rq2_partial_credit_pairwise_vs_r0.csv": (list(pairwise_partial[0]), pairwise_partial),
        "w_rq2_unsupported_presence_by_condition.csv": (["retrieval_condition", "true_count", "false_count", "rate", "n"], unsupported_presence_rows),
        "w_rq2_unsupported_mcnemar_vs_r0.csv": (list(mcnemar_rows[0]), mcnemar_rows),
        "w_rq2_unsupported_count_by_condition.csv": (["retrieval_condition", "n", "mean", "sd", "median", "min", "max"], unsupported_count_rows),
        "w_rq2_unsupported_count_pairwise_vs_r0.csv": (list(pairwise_count[0]), pairwise_count),
        "w_rq2_contradictions_by_condition.csv": (["retrieval_condition", "true_count", "false_count", "rate", "total_n_contradicted", "n"], contradictions_rows),
        "w_rq2_expected_point_labels_by_condition.csv": (["retrieval_condition", *EXPECTED_LABELS, "total_expected_points", "n_cases"], label_rows),
        "w_rq3_insufficient_label_distribution.csv": (["retrieval_condition", "n", *INSUFFICIENT_LABELS, *[f"{label}_proportion" for label in INSUFFICIENT_LABELS]], wrq3_dist),
        "w_rq3_case_by_condition.csv": (["case_id", "retrieval_condition", "insufficient_handling"], wrq3_case),
    }
    table_paths: dict[str, Path] = {}
    for name, (fields, rows) in table_specs.items():
        path = tables_dir / name
        csv_write(path, fields, rows)
        table_paths[name] = path

    # Deterministic, timestamp-free results document.
    primary_lookup = {r["retrieval_condition"]: r for r in primary_rows}
    partial_lookup = {r["retrieval_condition"]: r for r in partial_rows}
    presence_lookup = {r["retrieval_condition"]: r for r in unsupported_presence_rows}
    contradiction_lookup = {r["retrieval_condition"]: r for r in contradictions_rows}
    lines = [
        "# Western Semantic Follow-up v0.2 — Blinded GPT-5.6 Sol Evaluation",
        "",
        "## Study identity",
        "",
        "This is a new Western Semantic Follow-up v0.2. It is not a reopening of the closed Western Formal Study v0.1.5 and does not constitute Wave 3. It reuses the frozen benchmark, Stage-A retrieval outputs, and primary Stage-B generated answers. A single GPT-5.6 Sol evaluator supplied evidence-grounded semantic annotations using only the frozen expected evidence points, supplied passages, and generated answer. Retrieval-condition identity was concealed from the evaluator.",
        "",
        "## Analysis populations",
        "",
        f"W-RQ2 contains 42 answerable cases (supported or partially_supported), 168 cells, and no missing semantic judgments. W-RQ3 contains 6 insufficient-evidence cases and 24 cells. Insufficient cases are excluded from W-RQ2 and are not treated as zeros.",
        "",
        "## W-RQ2 primary endpoint",
        "",
        "The primary endpoint is the case-level macro mean of full_coverage_score. No micro-total across evidence points was used.",
        "",
        "| Condition | n | Mean | SD | Median | Min | Max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for c in EXPECTED_CONDITIONS:
        r = primary_lookup[c]
        lines.append(f"| {c} | {r['n']} | {fmt(r['mean'])} | {fmt(r['sd'])} | {fmt(r['median'])} | {fmt(r['min'])} | {fmt(r['max'])} |")
    lines += ["", "Paired comparisons use case_id, with 42 paired cases for each comparison and 10,000 case-resamples (seed 20260815). The observed paired mean difference and percentile interval are descriptive:", "", "| Comparison | n | Mean difference | Median difference | 95% bootstrap CI |", "|---|---:|---:|---:|---:|"]
    for r in pairwise_primary:
        lines.append(f"| {r['comparison']} | {r['n']} | {fmt(r['mean_difference'])} | {fmt(r['median_difference'])} | [{fmt(r['bootstrap_ci_95_low'])}, {fmt(r['bootstrap_ci_95_high'])}] |")
    lines += ["", "## W-RQ2 secondary findings", "", "Partial-credit coverage, unsupported-claim measures, contradictions, and expected-point labels are descriptive secondary analyses; no composite score was created.", "", "Partial-credit coverage:", "", "| Condition | n | Mean | SD | Median | Min | Max |", "|---|---:|---:|---:|---:|---:|---:|"]
    for c in EXPECTED_CONDITIONS:
        r = partial_lookup[c]
        lines.append(f"| {c} | {r['n']} | {fmt(r['mean'])} | {fmt(r['sd'])} | {fmt(r['median'])} | {fmt(r['min'])} | {fmt(r['max'])} |")
    lines += ["", "Paired partial-credit differences versus R0:", "", "| Comparison | n | Mean difference | Median difference | 95% bootstrap CI |", "|---|---:|---:|---:|---:|"]
    for r in pairwise_partial:
        lines.append(f"| {r['comparison']} | {r['n']} | {fmt(r['mean_difference'])} | {fmt(r['median_difference'])} | [{fmt(r['bootstrap_ci_95_low'])}, {fmt(r['bootstrap_ci_95_high'])}] |")
    lines += ["", "Unsupported-claim presence rates:", "", "| Condition | TRUE | FALSE | Rate | n |", "|---|---:|---:|---:|---:|"]
    for c in EXPECTED_CONDITIONS:
        r = presence_lookup[c]
        lines.append(f"| {c} | {r['true_count']} | {r['false_count']} | {fmt(r['rate'])} | {r['n']} |")
    lines += ["", "Exact two-sided McNemar p-values and Holm adjustment across the three pre-specified comparisons:", "", "| Comparison | R0 FALSE/comparison TRUE | R0 TRUE/comparison FALSE | Discordant | Raw p | Holm-adjusted p |", "|---|---:|---:|---:|---:|---:|"]
    for r in mcnemar_rows:
        lines.append(f"| {r['comparison']} | {r['r0_false_comparison_true']} | {r['r0_true_comparison_false']} | {r['discordant_total']} | {fmt(r['exact_two_sided_mcnemar_p_raw'])} | {fmt(r['holm_adjusted_p'])} |")
    lines += ["", "Unsupported-claim count summaries:", "", "| Condition | Mean | SD | Median | Min | Max |", "|---|---:|---:|---:|---:|---:|"]
    for c in EXPECTED_CONDITIONS:
        r = {x["retrieval_condition"]: x for x in unsupported_count_rows}[c]
        lines.append(f"| {c} | {fmt(r['mean'])} | {fmt(r['sd'])} | {fmt(r['median'])} | {fmt(r['min'])} | {fmt(r['max'])} |")
    lines += ["", "Paired unsupported-claim count differences versus R0:", "", "| Comparison | Mean difference | 95% bootstrap CI |", "|---|---:|---:|"]
    for r in pairwise_count:
        lines.append(f"| {r['comparison']} | {fmt(r['mean_difference'])} | [{fmt(r['bootstrap_ci_95_low'])}, {fmt(r['bootstrap_ci_95_high'])}] |")
    lines += ["", "Contradiction summaries:", "", "| Condition | TRUE | FALSE | Rate | Total n_contradicted |", "|---|---:|---:|---:|---:|"]
    for c in EXPECTED_CONDITIONS:
        r = contradiction_lookup[c]
        lines.append(f"| {c} | {r['true_count']} | {r['false_count']} | {fmt(r['rate'])} | {r['total_n_contradicted']} |")
    lines += ["", "Expected-point label totals:", "", "| Condition | Covered | Partially covered | Not covered | Contradicted | Total points |", "|---|---:|---:|---:|---:|---:|"]
    for r in label_rows:
        lines.append(f"| {r['retrieval_condition']} | {r['covered']} | {r['partially_covered']} | {r['not_covered']} | {r['contradicted']} | {r['total_expected_points']} |")
    lines += ["", "These secondary quantities were not used to create a new inferential endpoint; expected points remain nested within cases.", "", "## W-RQ3 insufficient-evidence handling", "", "The four frozen labels are reported by condition with n=6 per condition; no hypothesis test or composite endpoint was used.", "", "| Condition | n | Appropriate abstention | Bounded insufficiency | Substantive answer without acknowledgement | Overclaim beyond pilot evidence |", "|---|---:|---:|---:|---:|---:|"]
    for r in wrq3_dist:
        lines.append(f"| {r['retrieval_condition']} | {r['n']} | {r['appropriate_abstention']} | {r['appropriate_bounded_insufficiency']} | {r['substantive_answer_without_insufficiency_acknowledgement']} | {r['overclaim_beyond_pilot_evidence']} |")
    lines += ["", "The case-by-condition labels are in `tables/w_rq3_case_by_condition.csv`.", "", "## Interpretation boundaries", "", "This follow-up estimates evidence-grounded semantic behavior under a single GPT-5.6 Sol evaluator. It does not establish clinical correctness, clinical safety, diagnostic validity, physician agreement, human-expert agreement, or a general advantage of any medical system over another. The evaluator is not a human or clinician. These annotations do not constitute clinical validation.", "", "## Evaluator and blinding limitations", "", "One evaluator, GPT-5.6 Sol, applied the frozen rubric. There was no human or clinician adjudicator, no inter-rater reliability estimate, and no judge-family robustness estimate. The semantic labels therefore depend on this evaluator's application of the frozen rubric.", "", "Retrieval-condition identity was concealed from the evaluator, but the answer and supplied evidence could indirectly reveal differences in retrieval quality or content. Condition-label concealment does not establish that the evaluator could not infer such differences.", "", "## Relationship to Stage A", "", "Stage A measured retrieval performance. This follow-up measures evidence-grounded semantic behavior under one evaluator. Any descriptive alignment between those results does not establish that retrieval performance caused differences in generated-answer quality.", "", "## Relationship to Western Formal Study v0.1.5", "", "Western Formal Study v0.1.5 remains historically unchanged. Its original automated Stage C remains prospectively terminated, and W-RQ2/W-RQ3 semantic estimates remain unavailable within that study version. Western Semantic Follow-up v0.2 separately provides new post-study semantic estimates for the same frozen Stage-B answer set and does not rewrite the historical study status.", "", "## Scientific conclusion", "", "Within this frozen 16-review, 48-case pilot and under a single blinded GPT-5.6 Sol evidence-grounded evaluator, semantic evidence coverage and unsupported-claim behavior differed descriptively across retrieval conditions.", "", "## Reproducibility", "", "The exact input hashes, frozen pre-deblind plan hash, deblinded dataset hash, table hashes, and script hash are recorded in `stage_c2_analysis_manifest.json`. The analysis is offline and uses no provider, model, or network call. The populated judgment workbook was supplied outside the repository and verified by its required SHA256; the repository retains the separate blank blinded template.", ""]
    results_path = output_dir / "STAGE_C2_RESULTS_v0.2.md"
    results_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")

    manifest = {
        "followup_study": "Western Semantic Follow-up v0.2",
        "evaluator": "GPT-5.6 Sol",
        "evaluator_blinded": True,
        "evaluator_blindness_statement": "Retrieval-condition identity was concealed from the evaluator, which was instructed to use only frozen expected points, supplied evidence, and generated answer. Answer or evidence content could still indirectly reveal retrieval characteristics.",
        "analysis_plan": {"path": str(args.plan).replace("\\", "/"), "sha256": plan_sha},
        "predeblind_order": {
            "plan_created_at_utc": plan.get("created_at_utc"),
            "plan_status": plan.get("status"),
            "procedural_record": "The analysis session recorded the plan as written and hashed before blind-key parsing.",
            "independent_timestamp_limitation": "Filesystem timestamps establish plan creation before derived analysis outputs but do not independently record or prove the first blind-key read event.",
        },
        "judgment_workbook": {
            "path": str(args.workbook).replace("\\", "/"),
            "sha256": sha256(args.workbook),
            "export_manifest_recorded_sha256": export_manifest.get("outputs", {}).get("workbook", {}).get("sha256"),
            "export_manifest_hash_note": "The frozen export manifest points to the repository's blank blinded template; the supplied populated judgment workbook is verified against the required follow-up SHA.",
            "repository_expected_path": str(output_dir / "stage_c2_gpt56sol_judgments.xlsx").replace("\\", "/"),
            "repository_expected_path_present": (output_dir / "stage_c2_gpt56sol_judgments.xlsx").exists(),
        },
        "blind_key": {"path": str(args.blind_key).replace("\\", "/"), "sha256": sha256(args.blind_key)},
        "export_manifest": {"path": str(args.export_manifest).replace("\\", "/"), "sha256": sha256(args.export_manifest)},
        "populations": {"w_rq2": {"n_cases": 42, "n_cells": 168}, "w_rq3": {"n_cases": 6, "n_cells": 24}},
        "condition_counts": {c: 48 for c in EXPECTED_CONDITIONS},
        "missingness_policy": "Missing semantic judgments remain missing; no zero imputation or condition pooling; paired analyses use endpoint-specific successful case intersections.",
        "primary_endpoint": "full_coverage_score case-level macro mean",
        "bootstrap": {"seed": BOOTSTRAP_SEED, "resamples": BOOTSTRAP_RESAMPLES, "unit": "cases with replacement", "ci": "percentile 95%"},
        "mcnemar": {"definition": "exact two-sided binomial test on paired discordant presence indicators", "holm_family_size": 3},
        "outputs": {},
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    output_paths = {"deblinded_dataset": deblinded_path, **{f"table:{name}": path for name, path in table_paths.items()}, "results_document": results_path}
    for name, path in output_paths.items():
        manifest["outputs"][name] = {"path": str(path).replace("\\", "/"), "sha256": sha256(path), "size_bytes": path.stat().st_size}
    script_path = Path(__file__).resolve()
    manifest["analysis_script"] = {"path": str(script_path).replace("\\", "/"), "sha256": sha256(script_path)}
    write_json(output_dir / "stage_c2_analysis_manifest.json", manifest)


if __name__ == "__main__":
    main()
