from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.research import ConditionId, ModelTarget, RetrievalStrategy


RunMode = Literal["one_case", "paired", "full_benchmark"]


class FormalRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    run_mode: RunMode
    condition: str | None = None
    case_id: str | None = None
    confirm_full_benchmark: bool = False

    @model_validator(mode="after")
    def validate_mode_fields(self):
        if self.run_mode == "full_benchmark" and not self.confirm_full_benchmark:
            raise ValueError("Full benchmark replay requires explicit confirmation")
        if self.run_mode == "paired" and self.condition is not None:
            raise ValueError("Paired replay determines both conditions from the paper protocol")
        return self


class FormalRunStatus(BaseModel):
    run_id: str
    experiment_id: str
    run_mode: RunMode
    status: Literal["queued", "running", "stop_requested", "stopped", "complete", "failed"]
    completed: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    current_condition: str | None = None
    current_case: str | None = None
    successful: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0, ge=0)
    resume_state: str = "not_started"
    replay_output_dir: str = Field(description="Worker-relative replay workspace; never a web-service filesystem path")
    persistence: str = "PostgreSQL source of truth; execution is performed by a separate cloud worker"
    error: str | None = None
    stop_requested: bool = False
    stop_requested_at: float | None = None
    stopped_at: float | None = None


class CustomRunRequest(BaseModel):
    """Exploratory batch configuration executed only by the cloud worker."""

    model_config = ConfigDict(extra="forbid")

    questions: list[str] = Field(min_length=1, max_length=100)
    condition_id: ConditionId = ConditionId.C2
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.R2
    specialist_model_targets: list[ModelTarget] = Field(min_length=1, max_length=6)
    consensus_model_target: ModelTarget
    active_agents: list[str] = Field(default_factory=list)
    active_judges: list[str] = Field(default_factory=list)
    top_k: int = Field(default=4, ge=1, le=20)
    debate_rounds: int = Field(default=1, ge=0, le=3)
    include_trace: bool = True

    @model_validator(mode="after")
    def clean_questions(self):
        cleaned = [question.strip() for question in self.questions]
        if any(len(question) < 3 for question in cleaned):
            raise ValueError("Each custom question must contain at least 3 characters")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Custom questions must be unique within one batch")
        self.questions = cleaned
        return self


class CustomRunStatus(BaseModel):
    run_id: str
    status: Literal["queued", "running", "stop_requested", "stopped", "complete", "failed"]
    completed: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    current_stage: str | None = None
    current_case: str | None = None
    successful: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0, ge=0)
    resume_state: str = "not_started"
    persistence: str = "durable PostgreSQL queue/results"
    error: str | None = None
    stop_requested: bool = False
    stop_requested_at: float | None = None
    stopped_at: float | None = None
