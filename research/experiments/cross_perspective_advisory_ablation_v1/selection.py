from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .manifest import canonical_json_dumps, sha256_canonical_obj, sha256_text
from .schemas import SelectedQuestion, TaskType, Topic

SELECTION_ALGORITHM_ID = "CPAA1-SHA256-STRATIFIED-SELECTION-V1"
SELECTION_SEED = 20260928

TOPIC_CODE_TO_FULL: dict[str, Topic] = {
    "COU": "cough",
    "DYS": "dyspepsia_digestive_symptoms",
    "HEA": "headache",
    "CON": "constipation",
}
FULL_TO_TOPIC_CODE: dict[Topic, str] = {v: k for k, v in TOPIC_CODE_TO_FULL.items()}

TASK_CODE_TO_FULL: dict[str, TaskType] = {
    "ED": "evidence_description",
    "SC": "cross_perspective_synthesis",
    "BU": "boundary_uncertainty",
}
FULL_TO_TASK_CODE: dict[TaskType, str] = {v: k for k, v in TASK_CODE_TO_FULL.items()}

EXPECTED_TOPIC_CODES = ("COU", "DYS", "HEA", "CON")
EXPECTED_TASK_CODES = ("ED", "SC", "BU")

# SOURCE B - Approved revised CPAA1-DYS-SC-002 record
SOURCE_B_DYS_SC_002: dict[str, Any] = {
    "candidate_id": "CPAA1-DYS-SC-002",
    "topic": "DYS",
    "task_type": "SC",
    "question_text": "To what extent does the supplied evidence allow comparison of the time horizons addressed by digestive claims in the two streams?",
    "family_id": "DYS-TEMPORAL-SCOPE-ALIGNMENT",
    "substantive_target": "Cross-stream alignment of the temporal scope of digestive claims.",
    "scope_rationale": "Source-recorded indications and intervention findings may specify different temporal scopes or leave them unspecified. The question assesses available temporal information without presuming that either stream supplies duration data.",
    "allowed_answer_space": "Comparable temporal scope; partly comparable; not directly comparable; insufficient information to assess.",
    "prohibited_inference": "Inferring unspecified time horizons; treating indications as efficacy evidence; extrapolating persistence of benefit; assuming that matching time horizons establish equivalent claims.",
    "duplicate_risk_note": "Keep the task focused on comparing represented temporal scopes. Do not turn it into an assessment of how long benefits last.",
    "draft_eligibility": "ELIGIBLE_FOR_REVIEW",
    "independent_review_status": "PASS",
}


def compute_selection_hash(
    candidate_id: str,
    *,
    algorithm_id: str = SELECTION_ALGORITHM_ID,
    seed: int = SELECTION_SEED,
) -> str:
    """Compute UTF-8 SHA256 of EXACTLY: <algorithm_id>|<seed>|<candidate_id>."""
    key = f"{algorithm_id}|{seed}|{candidate_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_candidate_table_markdown(text: str) -> list[dict[str, Any]]:
    """Parse candidate table markdown into structured records."""
    rows: list[dict[str, Any]] = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("| CPAA1-"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 11:
                rows.append({
                    "candidate_id": parts[0],
                    "topic": parts[1],
                    "task_type": parts[2],
                    "question_text": parts[3],
                    "family_id": parts[4],
                    "substantive_target": parts[5],
                    "scope_rationale": parts[6],
                    "allowed_answer_space": parts[7],
                    "prohibited_inference": parts[8],
                    "duplicate_risk_note": parts[9],
                    "draft_eligibility": parts[10],
                    "independent_review_status": "PASS",
                })
    return rows


def validate_candidate_pool(candidates: Sequence[Mapping[str, Any]]) -> None:
    """Validate the 72-candidate pool contract.

    Mechanically verify:
    - exactly 72 records
    - exactly 72 unique candidate IDs
    - exactly four topics (COU, DYS, HEA, CON)
    - exactly three task categories (ED, SC, BU)
    - exactly six candidates per topic × task stratum
    - expected IDs in every stratum: 001, 002, 003, 004, 005, 006
    - all 72 records have independent-review status PASS
    - no records marked REVISION_REQUIRED, DUPLICATE_OR_REDUNDANT, SCOPE_VIOLATION, WRONG_TASK_CATEGORY
    """
    if len(candidates) != 72:
        raise ValueError(f"Candidate pool must contain exactly 72 records, got {len(candidates)}")

    c_ids = [c["candidate_id"] for c in candidates]
    if len(set(c_ids)) != 72:
        raise ValueError("Candidate IDs must be strictly unique across all 72 records")

    forbidden_statuses = {"REVISION_REQUIRED", "DUPLICATE_OR_REDUNDANT", "SCOPE_VIOLATION", "WRONG_TASK_CATEGORY"}

    strata_counts: dict[tuple[str, str], list[str]] = {
        (top, tt): [] for top in EXPECTED_TOPIC_CODES for tt in EXPECTED_TASK_CODES
    }

    for c in candidates:
        cid = c["candidate_id"]
        top = c["topic"]
        tt = c["task_type"]
        status = c.get("independent_review_status", "")

        if top not in EXPECTED_TOPIC_CODES:
            raise ValueError(f"Unexpected topic code {top!r} in candidate {cid}")
        if tt not in EXPECTED_TASK_CODES:
            raise ValueError(f"Unexpected task type code {tt!r} in candidate {cid}")

        if status != "PASS":
            raise ValueError(f"Candidate {cid} review status must be PASS, got {status!r}")

        for f_stat in forbidden_statuses:
            if c.get("draft_eligibility") == f_stat or status == f_stat:
                raise ValueError(f"Candidate {cid} has forbidden status: {f_stat}")

        strata_counts[(top, tt)].append(cid)

    for (top, tt), stratum_ids in strata_counts.items():
        if len(stratum_ids) != 6:
            raise ValueError(f"Stratum ({top}, {tt}) must have exactly 6 candidates, got {len(stratum_ids)}")
        expected_ids = [f"CPAA1-{top}-{tt}-{i:03d}" for i in range(1, 7)]
        if sorted(stratum_ids) != expected_ids:
            raise ValueError(f"Stratum ({top}, {tt}) expected IDs {expected_ids}, got {sorted(stratum_ids)}")


def run_deterministic_selection(
    candidates: Sequence[Mapping[str, Any]],
    *,
    algorithm_id: str = SELECTION_ALGORITHM_ID,
    seed: int = SELECTION_SEED,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Execute the locked stratified deterministic hash selection.

    Within EACH of the 12 topic × task strata:
    1. Obtain the six eligible candidate IDs.
    2. Sort candidate IDs lexicographically.
    3. Compute UTF-8 SHA256 of: <algorithm_id>|<seed>|<candidate_id>
    4. Interpret SHA256 hex digest as selection key.
    5. Sort ascending by SHA256 hex digest (candidate_id ascending as tie-breaker).
    6. Select the first 4.
    7. Remaining 2 are unselected.

    Returns:
        (selected_candidates, unselected_candidates, selection_ledger)
    """
    candidates_by_id = {c["candidate_id"]: dict(c) for c in candidates}
    selected: list[dict[str, Any]] = []
    unselected: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []

    for top in EXPECTED_TOPIC_CODES:
        for tt in EXPECTED_TASK_CODES:
            stratum_ids = [f"CPAA1-{top}-{tt}-{i:03d}" for i in range(1, 7)]
            stratum_ids.sort()

            scored: list[tuple[str, str]] = []
            for cid in stratum_ids:
                h = compute_selection_hash(cid, algorithm_id=algorithm_id, seed=seed)
                scored.append((h, cid))

            scored.sort(key=lambda x: (x[0], x[1]))

            for rank, (h, cid) in enumerate(scored, start=1):
                is_selected = rank <= 4
                cand_copy = dict(candidates_by_id[cid])
                cand_copy["selection_hash"] = h
                cand_copy["stratum_rank"] = rank
                cand_copy["selected"] = is_selected

                ledger.append({
                    "candidate_id": cid,
                    "topic": top,
                    "task_type": tt,
                    "selection_hash": h,
                    "rank_within_stratum": rank,
                    "selected": is_selected,
                })

                if is_selected:
                    selected.append(cand_copy)
                else:
                    unselected.append(cand_copy)

    return selected, unselected, ledger


def build_question_manifest(
    selected_candidates: Sequence[Mapping[str, Any]],
    *,
    frozen_timestamp: str = "2026-09-29T00:00:00Z",
) -> list[SelectedQuestion]:
    """Build the formal 48 SelectedQuestion records in deterministic order.

    Order:
    1. Topic order: COU, DYS, HEA, CON
    2. Task order: ED, SC, BU
    3. candidate_id ascending

    Derives formal question_id as candidate_id.lower() with full provenance
    preserved in selection_metadata.
    """
    ordered_selected: list[dict[str, Any]] = []

    for top in EXPECTED_TOPIC_CODES:
        for tt in EXPECTED_TASK_CODES:
            stratum_cands = [
                dict(c) for c in selected_candidates
                if c["topic"] == top and c["task_type"] == tt
            ]
            stratum_cands.sort(key=lambda c: c["candidate_id"])
            if len(stratum_cands) != 4:
                raise ValueError(f"Stratum ({top}, {tt}) has {len(stratum_cands)} selected candidates, expected 4")
            ordered_selected.extend(stratum_cands)

    questions: list[SelectedQuestion] = []
    for order, c in enumerate(ordered_selected, start=1):
        cid = c["candidate_id"]
        topic_full = TOPIC_CODE_TO_FULL[c["topic"]]
        task_full = TASK_CODE_TO_FULL[c["task_type"]]

        q = SelectedQuestion(
            question_id=cid.lower(),
            topic=topic_full,
            task_type=task_full,
            question_text=c["question_text"],
            selection_order=order,
            frozen_timestamp=frozen_timestamp,
            selection_metadata={
                "candidate_id": cid,
                "family_id": c["family_id"],
                "substantive_target": c["substantive_target"],
                "scope_rationale": c["scope_rationale"],
                "allowed_answer_space": c["allowed_answer_space"],
                "prohibited_inference": c["prohibited_inference"],
                "duplicate_risk_note": c["duplicate_risk_note"],
                "selection_hash": c.get("selection_hash", compute_selection_hash(cid)),
                "stratum_rank": c.get("stratum_rank", 0),
            },
        )
        questions.append(q)

    return questions
