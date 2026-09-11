from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    status: Literal["queued", "running", "complete", "failed"]
    completed: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    current_condition: str | None = None
    current_case: str | None = None
    successful: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0, ge=0)
    resume_state: str = "not_started"
    replay_output_dir: str
    persistence: str = "process-local job state; replay files are not guaranteed durable on hosted ephemeral filesystems"
    error: str | None = None
