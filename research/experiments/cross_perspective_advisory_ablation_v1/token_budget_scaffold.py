from __future__ import annotations

from typing import Any, Final
from pydantic import BaseModel, ConfigDict, Field


class TokenBudgetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    role: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    system_prompt_chars: int = Field(ge=0)
    user_payload_chars: int = Field(ge=0)
    chat_formatted_input_token_estimate: int | None = None
    max_context_tokens: int | None = None
    reserved_output_tokens: int | None = None
    remaining_margin_tokens: int | None = None
    status: str = Field(min_length=1)
    notes: str = ""


class TokenBudgetScaffold:
    """Offline-only token-budget scaffolding for cross-perspective advisory ablation study.
    
    Strict constraints:
    - Zero network calls.
    - Zero provider API calls.
    - Zero automatic downloads.
    - Reports NOT_YET_CLEARABLE when offline tokenizer/context metadata is unavailable.
    - Strictly forbids guessing token counts or truncating evidence.
    """

    MODEL_ASSIGNMENTS: Final[dict[str, str]] = {
        "governance": "THUDM/GLM-4-9B-0414",
        "critic": "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
        "evidence_specialist": "Qwen/Qwen3-8B",
        "coverage_auditor": "THUDM/GLM-4-9B-0414",
        "grounding_skeptic": "THUDM/GLM-Z1-9B-0414",
    }

    @classmethod
    def evaluate_role_budget(
        cls,
        role: str,
        question_id: str,
        system_prompt: str,
        user_payload: str,
        tokenizer: Any = None,
        max_context: int | None = None,
        reserved_output: int | None = None,
    ) -> TokenBudgetRecord:
        """Evaluate token budget for a single role-question cell offline."""
        model_id = cls.MODEL_ASSIGNMENTS.get(role, "unknown_model")
        sys_chars = len(system_prompt)
        user_chars = len(user_payload)

        # If tokenizer or context parameters are not provided offline, fail safe to NOT_YET_CLEARABLE
        if tokenizer is None or max_context is None or reserved_output is None:
            return TokenBudgetRecord(
                role=role,
                question_id=question_id,
                model_id=model_id,
                system_prompt_chars=sys_chars,
                user_payload_chars=user_chars,
                chat_formatted_input_token_estimate=None,
                max_context_tokens=max_context,
                reserved_output_tokens=reserved_output,
                remaining_margin_tokens=None,
                status="NOT_YET_CLEARABLE",
                notes="Offline tokenizer or context window metadata is not loaded; clearance deferred.",
            )

        # When a local tokenizer interface is explicitly provided (e.g. in synthetic testing)
        token_count = tokenizer(f"{system_prompt}\n{user_payload}")
        margin = max_context - (token_count + reserved_output)
        status = "CLEARED" if margin >= 0 else "EXCEEDS_CONTEXT_LIMIT"

        return TokenBudgetRecord(
            role=role,
            question_id=question_id,
            model_id=model_id,
            system_prompt_chars=sys_chars,
            user_payload_chars=user_chars,
            chat_formatted_input_token_estimate=token_count,
            max_context_tokens=max_context,
            reserved_output_tokens=reserved_output,
            remaining_margin_tokens=margin,
            status=status,
            notes="Evaluated using provided offline interface.",
        )
