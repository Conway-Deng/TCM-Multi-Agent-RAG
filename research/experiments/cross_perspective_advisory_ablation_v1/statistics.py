from __future__ import annotations

import math
import random
from typing import Any, Mapping, Sequence

from .schemas import (
    AnalysisRecord,
    ConditionName,
    QuestionScore,
    ScoredClaim,
    SecondaryComparisonResult,
    Topic,
)


DEFAULT_BOOTSTRAP_RESAMPLES = 20000
DEFAULT_BOOTSTRAP_SEED = 20260928


def calculate_usable_fully_grounded_coverage_yield(
    *,
    is_structurally_usable: bool,
    has_substantive_content: bool,
    scored_claims: Sequence[ScoredClaim],
    reference_units_total_m_q: int,
    reference_units_fully_conveyed: int,
) -> float:
    """Calculate the locked primary endpoint score for a single generated output.

    Gate Rule:
    If the output:
    - is structurally usable (valid JSON matching schema)
    - has substantive content (not an empty placeholder)
    - and EVERY scored substantive claim is fully supported ('supported')
    then:
      score = reference_units_fully_conveyed / reference_units_total_m_q
    otherwise:
      score = 0.0

    Terminal generation failure -> 0
    Structurally invalid -> 0
    Zero substantive claims -> 0
    Unsupported claim -> 0
    Contradicted claim -> 0
    Partially supported claim -> fails full-grounding gate -> 0
    """
    if reference_units_total_m_q <= 0:
        raise ValueError(f"reference_units_total_m_q must be >= 1, got {reference_units_total_m_q}")

    if not is_structurally_usable:
        return 0.0

    if not has_substantive_content:
        return 0.0

    if not scored_claims:
        return 0.0

    # Every scored substantive claim must be strictly 'supported'
    for claim in scored_claims:
        if claim.rating != "supported":
            return 0.0
        if not claim.evidence_grounding_verified:
            return 0.0

    conveyed = max(0, min(reference_units_fully_conveyed, reference_units_total_m_q))
    return round(conveyed / reference_units_total_m_q, 6)


def aggregate_question_scores(
    question_outputs: Mapping[tuple[str, ConditionName], Sequence[float]],
    question_topics: Mapping[str, Topic],
    question_task_types: Mapping[str, Any],
) -> list[QuestionScore]:
    """Average the two nested repetitions per (question, condition) cell.

    The QUESTION is the independent analysis unit.
    The two repetitions are nested repeated observations and must NEVER
    be treated as independent questions.
    """
    by_question: dict[str, dict[ConditionName, float]] = {}

    for (qid, condition), scores in question_outputs.items():
        if len(scores) != 2:
            raise ValueError(
                f"Each question-condition cell must have exactly 2 scheduled repetitions, "
                f"got {len(scores)} for ({qid}, {condition})"
            )
        avg_score = round(sum(scores) / len(scores), 6)
        by_question.setdefault(qid, {})[condition] = avg_score

    question_scores: list[QuestionScore] = []
    for qid, cond_map in sorted(by_question.items()):
        for expected_cond in ("G0", "G1", "G2", "G3"):
            if expected_cond not in cond_map:
                raise KeyError(f"Question {qid} is missing condition {expected_cond}")
        question_scores.append(
            QuestionScore(
                question_id=qid,
                topic=question_topics[qid],
                task_type=question_task_types[qid],
                condition_scores=cond_map,
            )
        )

    return question_scores


def topic_stratified_question_bootstrap(
    question_scores: Sequence[QuestionScore],
    left_condition: ConditionName,
    right_condition: ConditionName,
    *,
    resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> tuple[float, float, float, float, float]:
    """Perform topic-stratified question bootstrap for paired difference (right - left).

    Whole-question resampling:
    When a question is resampled, all conditions and nested repetitions travel with it.

    Returns:
    (left_mean, right_mean, paired_difference_mean, ci_lower_95, ci_upper_95)
    """
    if len(question_scores) != 48:
        raise ValueError(f"Bootstrap requires exactly 48 questions, got {len(question_scores)}")

    by_topic: dict[Topic, list[QuestionScore]] = {}
    for q in question_scores:
        by_topic.setdefault(q.topic, []).append(q)

    for topic, qs in by_topic.items():
        if len(qs) != 12:
            raise ValueError(f"Topic {topic} must have exactly 12 questions, got {len(qs)}")

    n_total = len(question_scores)
    actual_left_mean = sum(q.condition_scores[left_condition] for q in question_scores) / n_total
    actual_right_mean = sum(q.condition_scores[right_condition] for q in question_scores) / n_total
    actual_diff_mean = actual_right_mean - actual_left_mean

    rng = random.Random(seed)
    topics = sorted(by_topic.keys())
    resampled_diffs: list[float] = []

    for _ in range(resamples):
        resampled_questions: list[QuestionScore] = []
        for topic in topics:
            topic_pool = by_topic[topic]
            # Draw 12 questions with replacement within stratum
            sample = [rng.choice(topic_pool) for _ in range(len(topic_pool))]
            resampled_questions.extend(sample)

        diff = sum(
            q.condition_scores[right_condition] - q.condition_scores[left_condition]
            for q in resampled_questions
        ) / n_total
        resampled_diffs.append(diff)

    resampled_diffs.sort()
    lower_idx = int(0.025 * resamples)
    upper_idx = min(resamples - 1, int(0.975 * resamples))

    ci_lower = round(resampled_diffs[lower_idx], 6)
    ci_upper = round(resampled_diffs[upper_idx], 6)

    return (
        round(actual_left_mean, 6),
        round(actual_right_mean, 6),
        round(actual_diff_mean, 6),
        ci_lower,
        ci_upper,
    )


def run_full_statistical_analysis(
    question_scores: Sequence[QuestionScore],
    *,
    resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    secondary_component_metrics: Mapping[str, Any] | None = None,
) -> AnalysisRecord:
    """Execute the locked primary confirmatory comparison (G3 - G0) and secondary mechanism comparisons."""
    # 1. Primary confirmatory comparison: G3 - G0
    g0_mean, g3_mean, primary_diff, primary_ci_lower, primary_ci_upper = (
        topic_stratified_question_bootstrap(
            question_scores,
            left_condition="G0",
            right_condition="G3",
            resamples=resamples,
            seed=seed,
        )
    )

    # 2. Secondary mechanism comparisons (strictly exploratory)
    secondary_contrasts: list[tuple[str, ConditionName, ConditionName]] = [
        ("G1 - G0", "G0", "G1"),
        ("G2 - G0", "G0", "G2"),
        ("G3 - G1", "G1", "G3"),
        ("G3 - G2", "G2", "G3"),
    ]

    secondary_results: list[SecondaryComparisonResult] = []
    for contrast_name, left, right in secondary_contrasts:
        _, _, diff, ci_low, ci_high = topic_stratified_question_bootstrap(
            question_scores,
            left_condition=left,
            right_condition=right,
            resamples=resamples,
            seed=seed,
        )
        secondary_results.append(
            SecondaryComparisonResult(
                contrast=contrast_name,
                mean_difference=diff,
                ci_lower_95=ci_low,
                ci_upper_95=ci_high,
                is_exploratory=True,
            )
        )

    return AnalysisRecord(
        study_id="cross-perspective-advisory-ablation-v1",
        sample_size_questions=len(question_scores),
        total_cells=len(question_scores) * 4 * 2,
        primary_comparison_name="G3 - G0",
        g0_mean=g0_mean,
        g3_mean=g3_mean,
        primary_mean_difference=primary_diff,
        bootstrap_95_ci_lower=primary_ci_lower,
        bootstrap_95_ci_upper=primary_ci_upper,
        bootstrap_resamples=resamples,
        bootstrap_seed=seed,
        stratified=True,
        secondary_comparisons=secondary_results,
        secondary_component_metrics=dict(secondary_component_metrics or {}),
    )
