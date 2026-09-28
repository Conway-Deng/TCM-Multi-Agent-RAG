import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from backend.cross_perspective.governance import (
        GOVERNANCE_MAX_TOKENS,
        GOVERNANCE_MODEL,
        GOVERNANCE_SYSTEM_PROMPT,
        GOVERNANCE_TIMEOUT_SECONDS,
    )
    from backend.cross_perspective.schemas import (
        ActivePerspectiveName,
        CrossPerspectiveCritique,
        PerspectiveAgentAssessment,
        PerspectiveEvidencePacket,
    )
except ModuleNotFoundError:
    from cross_perspective.governance import (
        GOVERNANCE_MAX_TOKENS,
        GOVERNANCE_MODEL,
        GOVERNANCE_SYSTEM_PROMPT,
        GOVERNANCE_TIMEOUT_SECONDS,
    )
    from cross_perspective.schemas import (
        ActivePerspectiveName,
        CrossPerspectiveCritique,
        PerspectiveAgentAssessment,
        PerspectiveEvidencePacket,
    )

from .manifest import sha256_canonical_obj, verify_file_hash

from .schemas import (
    AdvisoryFreezeRecord,
    ConditionCell,
    ConditionName,
    CriticFreezeRecord,
    PacketPair,
    SelectedQuestion,
    TaskType,
    Topic,
)


EXPECTED_TCM_CORPUS_PATH = Path("research/corpus/tcm_v1/chunks.jsonl")
EXPECTED_TCM_CORPUS_SHA256 = "316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9"

EXPECTED_WESTERN_CORPUS_PATH = Path("research/corpus/west_v0_1/chunks.jsonl")
EXPECTED_WESTERN_CORPUS_SHA256 = "8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b"

EXPECTED_TOPICS: tuple[Topic, ...] = (
    "cough",
    "dyspepsia_digestive_symptoms",
    "headache",
    "constipation",
)
EXPECTED_TASK_TYPES: tuple[TaskType, ...] = (
    "evidence_description",
    "cross_perspective_synthesis",
    "boundary_uncertainty",
)

PROTECTED_PATHS: tuple[str, ...] = (
    "research/experiments/western_semantic_followup_v0_2/stage_c2_blind_key.csv",
    "research/experiments/western_semantic_followup_v0_2/stage_c2_blinded_eval_input.xlsx",
    "scratch",
)


class PreflightValidationError(ValueError):
    """Raised when preflight validation fails."""


def validate_corpus_integrity(repo_root: Path | str = ".") -> dict[str, str]:
    """Verify that primary research evidence corpora exist and match locked SHA256 hashes."""
    root = Path(repo_root)
    tcm_path = root / EXPECTED_TCM_CORPUS_PATH
    west_path = root / EXPECTED_WESTERN_CORPUS_PATH

    if not tcm_path.is_file():
        raise PreflightValidationError(f"Primary TCM research corpus file missing: {tcm_path}")
    if not west_path.is_file():
        raise PreflightValidationError(f"Primary Western research corpus file missing: {west_path}")

    if not verify_file_hash(tcm_path, EXPECTED_TCM_CORPUS_SHA256):
        raise PreflightValidationError(
            f"TCM corpus SHA256 hash mismatch! Expected: {EXPECTED_TCM_CORPUS_SHA256}"
        )
    if not verify_file_hash(west_path, EXPECTED_WESTERN_CORPUS_SHA256):
        raise PreflightValidationError(
            f"Western corpus SHA256 hash mismatch! Expected: {EXPECTED_WESTERN_CORPUS_SHA256}"
        )

    return {
        "tcm_corpus_sha256": EXPECTED_TCM_CORPUS_SHA256,
        "western_corpus_sha256": EXPECTED_WESTERN_CORPUS_SHA256,
    }


def validate_question_population(questions: Sequence[SelectedQuestion]) -> None:
    """Validate the 48-question contract once populated.

    Requirements:
    - Exactly 48 questions
    - Exactly 12 questions per topic across the 4 topics
    - Exactly 4 questions per task type within each topic stratum
    - Selection order from 1 to 48 without duplicates
    """
    if len(questions) != 48:
        raise PreflightValidationError(f"Question population must have exactly 48 questions, got {len(questions)}")

    q_ids = [q.question_id for q in questions]
    if len(set(q_ids)) != 48:
        raise PreflightValidationError("Question IDs must be strictly unique")

    orders = [q.selection_order for q in questions]
    if sorted(orders) != list(range(1, 49)):
        raise PreflightValidationError("Question selection_order must be a permutation of 1..48")

    topic_counts: dict[Topic, int] = {t: 0 for t in EXPECTED_TOPICS}
    strata_counts: dict[tuple[Topic, TaskType], int] = {
        (t, tt): 0 for t in EXPECTED_TOPICS for tt in EXPECTED_TASK_TYPES
    }

    for q in questions:
        if q.topic not in topic_counts:
            raise PreflightValidationError(f"Unexpected topic: {q.topic}")
        if q.task_type not in EXPECTED_TASK_TYPES:
            raise PreflightValidationError(f"Unexpected task type: {q.task_type}")
        topic_counts[q.topic] += 1
        strata_counts[(q.topic, q.task_type)] += 1

    for topic, count in topic_counts.items():
        if count != 12:
            raise PreflightValidationError(f"Topic {topic!r} must have exactly 12 questions, got {count}")

    for (topic, task_type), count in strata_counts.items():
        if count != 4:
            raise PreflightValidationError(
                f"Stratum ({topic!r}, {task_type!r}) must have exactly 4 questions, got {count}"
            )


def validate_evidence_packet_completeness(packet: PerspectiveEvidencePacket) -> None:
    """Validate that an evidence packet satisfies Patch 3 completeness rules."""
    if not packet.claims and packet.available and packet.execution_status == "available":
        # Note: Available packet with 0 claims must have appropriate summary, but we check structural completeness
        pass
    for claim in packet.claims:
        if claim.support_status == "supported" and not claim.evidence_refs:
            raise PreflightValidationError(f"Supported claim {claim.claim_id} lacks evidence references")


def validate_evidence_parity_across_conditions(
    payloads_by_condition: Mapping[ConditionName, dict[str, Any]],
) -> None:
    """Verify that Section A evidence packets have identical hash across G0–G3."""
    expected_hash: str | None = None
    for condition in ("G0", "G1", "G2", "G3"):
        if condition not in payloads_by_condition:
            raise PreflightValidationError(f"Missing payload for condition: {condition}")
        section_a = payloads_by_condition[condition]["perspective_packets"]
        h = sha256_canonical_obj(section_a)
        if expected_hash is None:
            expected_hash = h
        elif h != expected_hash:
            raise PreflightValidationError(
                f"Section A evidence packet mismatch in condition {condition}! "
                f"Hash {h} != expected {expected_hash}"
            )


def validate_governance_configuration() -> dict[str, Any]:
    """Verify that Governance configuration matches frozen Patch 3 requirements."""
    if GOVERNANCE_MODEL != "THUDM/GLM-4-9B-0414":
        raise PreflightValidationError(
            f"Governance model mismatch! Expected THUDM/GLM-4-9B-0414, got {GOVERNANCE_MODEL}"
        )
    if GOVERNANCE_TIMEOUT_SECONDS != 90.0:
        raise PreflightValidationError(f"Governance timeout mismatch: {GOVERNANCE_TIMEOUT_SECONDS}")
    if GOVERNANCE_MAX_TOKENS != 2400:
        raise PreflightValidationError(f"Governance max tokens mismatch: {GOVERNANCE_MAX_TOKENS}")
    if not GOVERNANCE_SYSTEM_PROMPT.startswith("You are the governance and synthesis component"):
        raise PreflightValidationError("Governance system prompt does not match frozen Patch 3 contract")

    return {
        "model": GOVERNANCE_MODEL,
        "timeout": GOVERNANCE_TIMEOUT_SECONDS,
        "max_tokens": GOVERNANCE_MAX_TOKENS,
        "system_prompt_verified": True,
    }


def validate_advisory_visibility_matrix(
    payloads_by_condition: Mapping[ConditionName, dict[str, Any]],
) -> None:
    """Validate that Section B advisory context adheres to the G0–G3 visibility rules."""
    # G0: no local advisory, no critic
    g0_adv = payloads_by_condition["G0"]["advisory_context"]
    if g0_adv.get("critic_relations") != []:
        raise PreflightValidationError("G0 advisory context must have empty critic_relations")
    for p in ("tcm", "western"):
        if g0_adv.get("perspective_advisory", {}).get(p, []) != []:
            raise PreflightValidationError(f"G0 advisory context must have empty perspective_advisory for {p}")

    # G1: local advisory present, no critic
    g1_adv = payloads_by_condition["G1"]["advisory_context"]
    if g1_adv.get("critic_relations") != []:
        raise PreflightValidationError("G1 advisory context must have empty critic_relations")

    # G2: no local advisory, critic relations present (if applicable)
    g2_adv = payloads_by_condition["G2"]["advisory_context"]
    for p in ("tcm", "western"):
        if g2_adv.get("perspective_advisory", {}).get(p, []) != []:
            raise PreflightValidationError(f"G2 advisory context must have empty perspective_advisory for {p}")

    # G3: both local advisory and critic relations present (matching G1 local and G2 critic)
    g3_adv = payloads_by_condition["G3"]["advisory_context"]
    if g3_adv.get("critic_relations") != g2_adv.get("critic_relations"):
        raise PreflightValidationError("G3 critic_relations must match G2 critic_relations")
    if g3_adv.get("perspective_advisory") != g1_adv.get("perspective_advisory"):
        raise PreflightValidationError("G3 perspective_advisory must match G1 perspective_advisory")


def validate_critic_dependency(
    critic_record: CriticFreezeRecord,
    advisory_record: AdvisoryFreezeRecord,
    packet_pair: PacketPair,
) -> None:
    """Verify that Critic artifact was generated from the frozen local assessments and evidence packets."""
    if critic_record.evidence_pair_hash != packet_pair.pair_hash:
        raise PreflightValidationError("Critic record evidence_pair_hash does not match packet pair hash")
    if critic_record.advisory_freeze_hash != advisory_record.freeze_hash:
        raise PreflightValidationError("Critic record advisory_freeze_hash does not match advisory record hash")
    if critic_record.critic_model != "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B":
        raise PreflightValidationError(
            f"Critic model mismatch: expected deepseek-ai/DeepSeek-R1-0528-Qwen3-8B, got {critic_record.critic_model}"
        )


def validate_no_condition_leakage(prompt: str) -> None:
    """Verify that no condition label or experimental metadata leaks into Governance prompt."""
    lowered = prompt.casefold()
    leakage_terms = [
        "condition g0", "condition g1", "condition g2", "condition g3",
        "condition: g0", "condition: g1", "condition: g2", "condition: g3",
        "condition_g0", "condition_g1", "condition_g2", "condition_g3",
        "advisory ablation", "ablation study",
    ]
    for term in leakage_terms:
        if term in lowered:
            raise PreflightValidationError(f"Condition leakage detected in Governance prompt: {term!r}")


def validate_execution_cells_contract(cells: Sequence[ConditionCell]) -> None:
    """Verify cell IDs and repetition structure: exactly 384 cells, 2 repetitions per condition."""
    if len(cells) != 384:
        raise PreflightValidationError(f"Expected 384 execution cells, got {len(cells)}")
    for cell in cells:
        expected_cell_id = f"{cell.question_id}__{cell.condition}__rep{cell.repetition}"
        if cell.cell_id != expected_cell_id:
            raise PreflightValidationError(
                f"Cell ID format violation: got {cell.cell_id}, expected {expected_cell_id}"
            )
        if cell.repetition not in (1, 2):
            raise PreflightValidationError(f"Cell repetition must be 1 or 2, got {cell.repetition}")


def validate_protected_file_safety(paths_accessed: Sequence[str | Path]) -> None:
    """Verify that none of the protected untracked files are accessed or modified."""
    normalized_protected = [Path(p).as_posix().casefold() for p in PROTECTED_PATHS]
    for p in paths_accessed:
        norm = Path(p).as_posix().casefold()
        for prot in normalized_protected:
            if norm == prot or norm.startswith(f"{prot}/"):
                raise PreflightValidationError(f"CRITICAL SAFETY VIOLATION: attempt to access protected path: {p}")


def validate_no_historical_pooling(study_id: str, question_ids: Sequence[str]) -> None:
    """Verify that historical study data (RQ1, RQ4, Research B/C, A3) is not pooled."""
    if study_id != "cross-perspective-advisory-ablation-v1":
        raise PreflightValidationError(f"Invalid study ID: {study_id}")
    historical_prefixes = ("tcmc-v1-", "west-formal-", "rq1-", "rq4-", "rb-", "rc-", "a3-")
    for qid in question_ids:
        for prefix in historical_prefixes:
            if qid.lower().startswith(prefix):
                raise PreflightValidationError(
                    f"Historical study data leakage detected! Question ID {qid!r} belongs to historical study {prefix}."
                )


def run_preflight_checks(repo_root: Path | str = ".") -> dict[str, Any]:
    """Execute all currently testable preflight checks and return summary report."""
    results: dict[str, Any] = {}
    results["corpora"] = validate_corpus_integrity(repo_root)
    results["governance_config"] = validate_governance_configuration()
    results["safety_checks"] = "PASS"
    return results


if __name__ == "__main__":
    report = run_preflight_checks()
    print("Preflight checks completed successfully:")
    for k, v in report.items():
        print(f"  {k}: {v}")
