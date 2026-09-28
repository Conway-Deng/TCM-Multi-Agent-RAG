from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .schemas import ConditionCell, ConditionName, SelectedQuestion, Topic, TaskType


CONDITIONS: tuple[ConditionName, ...] = ("G0", "G1", "G2", "G3")
REPETITIONS: tuple[int, ...] = (1, 2)
EXPECTED_QUESTION_COUNT = 48
EXPECTED_CELL_COUNT = EXPECTED_QUESTION_COUNT * len(CONDITIONS) * len(REPETITIONS)  # 384


def build_cell_id(question_id: str, condition: ConditionName, repetition: int) -> str:
    """Build a deterministic cell ID."""
    return f"{question_id}__{condition}__rep{repetition}"


def generate_execution_plan(
    questions: Sequence[SelectedQuestion],
) -> list[ConditionCell]:
    """Generate the complete 384-cell execution plan for 48 questions.

    Requirements:
    - Exactly 48 questions
    - 4 conditions per question (G0, G1, G2, G3)
    - 2 repetitions per condition
    - Total: 384 cells
    - Nested observations: repetitions belong strictly to their question-condition cell
    - No execution of any cells or models
    """
    if len(questions) != EXPECTED_QUESTION_COUNT:
        raise ValueError(
            f"Execution plan requires exactly {EXPECTED_QUESTION_COUNT} questions, got {len(questions)}"
        )

    seen_qids = set()
    cells: list[ConditionCell] = []
    for question in questions:
        if question.question_id in seen_qids:
            raise ValueError(f"Duplicate question_id: {question.question_id}")
        seen_qids.add(question.question_id)

        for condition in CONDITIONS:
            for rep in REPETITIONS:
                cell_id = build_cell_id(question.question_id, condition, rep)
                cells.append(
                    ConditionCell(
                        cell_id=cell_id,
                        question_id=question.question_id,
                        topic=question.topic,
                        task_type=question.task_type,
                        condition=condition,
                        repetition=rep,  # type: ignore[arg-type]
                    )
                )

    if len(cells) != EXPECTED_CELL_COUNT:
        raise RuntimeError(
            f"Plan generation error: expected {EXPECTED_CELL_COUNT} cells, generated {len(cells)}"
        )

    return cells


def validate_execution_plan(cells: Sequence[ConditionCell]) -> None:
    """Validate structural constraints of the 384-cell execution plan."""
    if len(cells) != EXPECTED_CELL_COUNT:
        raise ValueError(
            f"Execution plan must contain exactly {EXPECTED_CELL_COUNT} cells, got {len(cells)}"
        )

    cell_ids = [c.cell_id for c in cells]
    if len(set(cell_ids)) != len(cell_ids):
        raise ValueError("Cell IDs in execution plan must be strictly unique")

    by_question: dict[str, list[ConditionCell]] = {}
    for cell in cells:
        by_question.setdefault(cell.question_id, []).append(cell)

    if len(by_question) != EXPECTED_QUESTION_COUNT:
        raise ValueError(
            f"Plan must cover exactly {EXPECTED_QUESTION_COUNT} questions, found {len(by_question)}"
        )

    for qid, q_cells in by_question.items():
        if len(q_cells) != len(CONDITIONS) * len(REPETITIONS):
            raise ValueError(
                f"Question {qid} must have exactly {len(CONDITIONS) * len(REPETITIONS)} cells, got {len(q_cells)}"
            )
        cond_rep_pairs = {(c.condition, c.repetition) for c in q_cells}
        expected_pairs = {(cond, rep) for cond in CONDITIONS for rep in REPETITIONS}
        if cond_rep_pairs != expected_pairs:
            raise ValueError(f"Question {qid} does not have all expected (condition, rep) pairs")


def export_execution_plan(cells: Sequence[ConditionCell], target_path: str | Path) -> None:
    """Export the validated execution plan to JSON."""
    validate_execution_plan(cells)
    data = [c.model_dump(mode="json") for c in cells]
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_execution_plan(source_path: str | Path) -> list[ConditionCell]:
    """Load and validate an execution plan from JSON."""
    path = Path(source_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cells = [ConditionCell.model_validate(item) for item in data]
    validate_execution_plan(cells)
    return cells
