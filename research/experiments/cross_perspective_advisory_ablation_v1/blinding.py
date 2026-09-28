from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any, Mapping, Sequence

from .schemas import (
    AuditRecord,
    AuditReconciliationRecord,
    AuditSampleSummary,
    BlindedAnswerRecord,
    BlindKeyRecord,
    ConditionCell,
    HumanScoringRecord,
    SelectedQuestion,
    Topic,
)


BLIND_SALT_DEFAULT = "cpaa_v1_blinding_salt_20260928"


def make_opaque_blind_id(cell_id: str, salt: str = BLIND_SALT_DEFAULT) -> str:
    """Generate a deterministic opaque answer ID from cell_id and salt."""
    raw = f"{salt}::{cell_id}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:16]
    return f"blind-{digest}"


def create_blinded_record(
    cell: ConditionCell,
    question: SelectedQuestion,
    answer_dict: dict[str, Any],
    salt: str = BLIND_SALT_DEFAULT,
) -> tuple[BlindedAnswerRecord, BlindKeyRecord]:
    """Create a blinded record and separate key record from a completed cell output.

    CRITICAL RULES:
    - Blinded record strictly strips condition label, repetition index, and cell_id.
    - Blind key record stores the mapping securely for post-evaluation unblinding.
    """
    blind_id = make_opaque_blind_id(cell.cell_id, salt=salt)

    blinded = BlindedAnswerRecord(
        blind_id=blind_id,
        question_id=cell.question_id,
        question_text=question.question_text,
        topic=cell.topic,
        task_type=cell.task_type,
        overall_summary=answer_dict.get("overall_summary", ""),
        overall_supporting_claim_ids=answer_dict.get("overall_supporting_claim_ids", []),
        perspectives=answer_dict.get("perspectives", {}),
        agreements=answer_dict.get("agreements", []),
        differences_or_conflicts=answer_dict.get("differences_or_conflicts", []),
        evidence_gaps=answer_dict.get("evidence_gaps", []),
        uncertainty=answer_dict.get("uncertainty", []),
        source_map=answer_dict.get("source_map", []),
        is_terminal_failure=answer_dict.get("is_terminal_failure", False),
        failure_reason=answer_dict.get("failure_reason"),
    )

    key = BlindKeyRecord(
        blind_id=blind_id,
        question_id=cell.question_id,
        condition=cell.condition,
        repetition=cell.repetition,
        cell_id=cell.cell_id,
    )

    return blinded, key


def select_audit_questions(
    questions: Sequence[SelectedQuestion],
    *,
    seed: int = 20260928,
) -> list[SelectedQuestion]:
    """Select exactly 12 audit questions (3 per topic stratum) deterministically.

    All 8 outputs per selected question will be audited by Reviewer B (96 outputs total).
    """
    by_topic: dict[Topic, list[SelectedQuestion]] = {}
    for q in questions:
        by_topic.setdefault(q.topic, []).append(q)

    rng = random.Random(seed)
    selected_audit_questions: list[SelectedQuestion] = []
    for topic in sorted(by_topic.keys()):
        topic_qs = sorted(by_topic[topic], key=lambda x: x.question_id)
        chosen = rng.sample(topic_qs, 3)
        selected_audit_questions.extend(chosen)

    if len(selected_audit_questions) != 12:
        raise RuntimeError(f"Expected exactly 12 audit questions, got {len(selected_audit_questions)}")

    return selected_audit_questions


def select_audit_blind_ids(
    audit_questions: Sequence[SelectedQuestion],
    all_keys: Sequence[BlindKeyRecord],
) -> set[str]:
    """Return the 96 blind_ids corresponding to the 12 selected audit questions."""
    audit_qids = {q.question_id for q in audit_questions}
    audit_blind_ids = {k.blind_id for k in all_keys if k.question_id in audit_qids}
    if len(audit_blind_ids) != 96:
        raise ValueError(
            f"Expected exactly 96 audit blind IDs (12 questions * 8 outputs), got {len(audit_blind_ids)}"
        )
    return audit_blind_ids


def reconcile_audit(
    reviewer_a_scores: Mapping[str, HumanScoringRecord],
    reviewer_b_audits: Mapping[str, AuditRecord],
    reconciled_scores: Mapping[str, float],
) -> tuple[list[AuditReconciliationRecord], AuditSampleSummary]:
    """Reconcile primary scores between Reviewer A and Reviewer B on the 96 audit outputs.

    If reconciliation changes the primary yield score for > 10% of audited outputs (> 9 of 96):
    triggers FULL_SECOND_REVIEW_REQUIRED.
    """
    if len(reviewer_b_audits) != 96:
        raise ValueError(f"Audit sample must contain exactly 96 outputs, got {len(reviewer_b_audits)}")

    reconciled_records: list[AuditReconciliationRecord] = []
    changed_count = 0

    for blind_id, audit in reviewer_b_audits.items():
        if blind_id not in reviewer_a_scores:
            raise KeyError(f"Missing Reviewer A score for audited blind_id: {blind_id}")
        if blind_id not in reconciled_scores:
            raise KeyError(f"Missing reconciled score for audited blind_id: {blind_id}")

        score_a = reviewer_a_scores[blind_id].primary_usable_grounded_coverage_yield
        score_b = audit.primary_usable_grounded_coverage_yield
        score_rec = reconciled_scores[blind_id]

        score_changed = abs(score_rec - score_a) > 1e-5
        if score_changed:
            changed_count += 1

        reconciled_records.append(
            AuditReconciliationRecord(
                blind_id=blind_id,
                reviewer_a_score=score_a,
                reviewer_b_score=score_b,
                reconciled_score=score_rec,
                score_changed_by_reconciliation=score_changed,
                score_absolute_delta=abs(score_rec - score_a),
            )
        )

    changed_fraction = changed_count / len(reviewer_b_audits)
    full_second_review_required = changed_fraction > 0.10
    audit_status = (
        "FULL_SECOND_REVIEW_REQUIRED" if full_second_review_required else "PASSED_AUDIT_GATE"
    )

    summary = AuditSampleSummary(
        total_audit_questions=12,
        total_audit_outputs=96,
        reconciled_outputs_changed_count=changed_count,
        reconciled_outputs_changed_fraction=round(changed_fraction, 6),
        full_second_review_required=full_second_review_required,
        audit_status=audit_status,
    )

    return reconciled_records, summary
