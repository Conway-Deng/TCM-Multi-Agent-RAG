from __future__ import annotations

import json
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, TypeVar

from pydantic import BaseModel, ValidationError

from providers.base import LLMProvider
from providers.openai_compatible import ProviderUnavailable

from .schemas import ActivePerspectiveName, ModelCallEvent


T = TypeVar("T", bound=BaseModel)
Role = Literal[
    "router",
    "governance",
    "evidence_specialist",
    "coverage_auditor",
    "grounding_skeptic",
]
RETRYABLE_FAILURES = {"timeout", "rate_limit", "http_5xx", "connectivity"}


class StructuredOutputError(RuntimeError):
    """The provider responded, but its output violated the frozen local contract."""


class StructuredModelCallFailure(RuntimeError):
    def __init__(self, message: str, *, events: list[ModelCallEvent]) -> None:
        super().__init__(message)
        self.events = events


@dataclass(frozen=True)
class StructuredCallResult:
    value: BaseModel
    events: list[ModelCallEvent]


def _json_object(text: str) -> dict:
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError("model output was not a valid JSON object") from exc
    if not isinstance(value, dict):
        raise StructuredOutputError("model output was not a JSON object")
    return value


def _failure_class(exc: Exception) -> tuple[str, str, int | None]:
    if isinstance(exc, ProviderUnavailable):
        if exc.error_type == "timeout":
            failure_class = "timeout"
        elif exc.error_type.startswith("http_") or exc.error_type == "rate_limit":
            failure_class = "http"
        elif exc.error_type in {"malformed_response", "output_quality_rejection"}:
            failure_class = "semantic"
        elif exc.error_type == "connectivity":
            failure_class = "provider"
        else:
            failure_class = "configuration" if "key is missing" in str(exc).casefold() else "provider"
        return failure_class, str(exc), exc.http_status
    if isinstance(exc, (StructuredOutputError, ValidationError)):
        return "semantic", "Model output failed the structured-output contract.", None
    return "unexpected", "Unexpected model-call failure.", None


async def call_structured_model(
    *,
    provider: LLMProvider,
    role: Role,
    response_model: type[T],
    system: str,
    prompt: str,
    max_tokens: int,
    perspective: ActivePerspectiveName | None = None,
) -> StructuredCallResult:
    """Call a fixed provider with at most one retry for technical failures."""
    events: list[ModelCallEvent] = []
    for attempt in (1, 2):
        started = perf_counter()
        try:
            generated = await provider.generate(
                system=system,
                prompt=prompt,
                temperature=0.0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            if generated.model != provider.model:
                raise StructuredOutputError(
                    f"provider reported model {generated.model!r}, expected {provider.model!r}"
                )
            value = response_model.model_validate(_json_object(generated.text))
            events.append(
                ModelCallEvent(
                    role=role,
                    attempt=attempt,
                    provider=generated.provider,
                    requested_model=provider.model,
                    reported_model=generated.model,
                    success=True,
                    latency_ms=round((perf_counter() - started) * 1000, 3),
                    retry_performed=attempt == 2,
                    prompt_tokens=generated.prompt_tokens,
                    completion_tokens=generated.completion_tokens,
                    perspective=perspective,
                )
            )
            return StructuredCallResult(value=value, events=events)
        except Exception as exc:
            failure_class, error_summary, http_status = _failure_class(exc)
            provider_error_type = exc.error_type if isinstance(exc, ProviderUnavailable) else "semantic"
            should_retry = attempt == 1 and provider_error_type in RETRYABLE_FAILURES
            events.append(
                ModelCallEvent(
                    role=role,
                    attempt=attempt,
                    provider=provider.name,
                    requested_model=provider.model,
                    success=False,
                    latency_ms=round((perf_counter() - started) * 1000, 3),
                    http_status=http_status,
                    failure_class=failure_class,  # type: ignore[arg-type]
                    error_summary=error_summary,
                    retry_performed=should_retry,
                    perspective=perspective,
                )
            )
            if not should_retry:
                raise StructuredModelCallFailure(error_summary, events=events) from exc
    raise AssertionError("unreachable")
