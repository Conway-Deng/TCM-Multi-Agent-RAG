from __future__ import annotations

import os

from pydantic import BaseModel


class ModelRoleConfig(BaseModel):
    planner: str
    specialist: str
    debate: str
    critic: str
    revision: str
    evidence_judge: str
    hallucination_judge: str
    safety_judge: str
    conflict_judge: str
    confidence_judge: str
    provenance_judge: str
    synthesis: str
    external_evaluator: str


def load_model_roles(default_model: str) -> ModelRoleConfig:
    def role(name: str) -> str:
        return os.getenv(name, "").strip() or default_model

    return ModelRoleConfig(
        planner=role("PLANNER_MODEL"), specialist=role("SPECIALIST_MODEL"), debate=role("DEBATE_MODEL"),
        critic=role("CRITIC_MODEL"), revision=role("REVISION_MODEL"), evidence_judge=role("EVIDENCE_JUDGE_MODEL"),
        hallucination_judge=role("HALLUCINATION_JUDGE_MODEL"), safety_judge=role("SAFETY_JUDGE_MODEL"),
        conflict_judge=role("CONFLICT_JUDGE_MODEL"), confidence_judge=role("CONFIDENCE_JUDGE_MODEL"),
        provenance_judge=role("PROVENANCE_JUDGE_MODEL"), synthesis=role("SYNTHESIS_MODEL"),
        external_evaluator=role("EXTERNAL_EVALUATOR_MODEL"),
    )
