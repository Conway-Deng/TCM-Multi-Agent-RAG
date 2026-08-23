from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, ValidationError

from providers.openai_compatible import ProviderUnavailable
from schemas.research import DebateTrace, ProviderAttempt, ResearchAgentOutput, RetrievalItem


PER_STAGE_TIMEOUT_SECONDS = 50.0
WHOLE_DEBATE_TIMEOUT_SECONDS = 300.0


class CritiquePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agreements: list[str]
    challenges: list[str]
    unsupported_claims: list[str]
    missing_evidence: list[str]
    evidence_issues: list[str]


class RevisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revised_claims: list[str]
    evidence_ids: list[str]
    changes_made: list[str]


class ConsensusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    evidence_ids: list[str]


@dataclass
class DebateExecution:
    trace: DebateTrace
    final_answer: str
    evidence_ids: list[str]
    provider_calls: int
    successful_provider_calls: int
    prompt_tokens: int
    completion_tokens: int


class DebateStageFailure(RuntimeError):
    def __init__(self, stage: str, attempts: list[ProviderAttempt], reason: str, *, trace: DebateTrace | None = None) -> None:
        super().__init__(f"C4 required stage {stage} failed: {reason}")
        self.stage = stage
        self.attempts = attempts
        self.trace = trace


class OutputRejected(ValueError):
    pass


def _balanced_json_objects(text: str) -> list[str]:
    """Return complete top-level JSON objects without repairing their contents."""
    objects: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            if depth == 0:
                start = index
            depth += 1
        elif character == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start:index + 1])
                start = None
    return objects


def _json_payload(text: str) -> dict[str, Any]:
    """Parse one unambiguous JSON object; tolerate wrappers, never semantic damage."""
    cleaned = text.strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as direct_error:
        decoded: list[dict[str, Any]] = []
        for candidate in _balanced_json_objects(cleaned):
            try:
                candidate_value = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate_value, dict):
                decoded.append(candidate_value)
        if len(decoded) != 1:
            reason = "no complete JSON object" if not decoded else "multiple JSON objects are ambiguous"
            raise ValueError(f"provider response contains {reason}") from direct_error
        value = decoded[0]
    if not isinstance(value, dict):
        raise ValueError("provider response must be a JSON object")
    return value


async def _structured_call(
    provider,
    *,
    stage: str,
    system: str,
    payload: dict[str, Any],
    schema,
    max_tokens: int,
    stage_timeout_seconds: float,
    validator: Callable[[Any], str | None] | None = None,
):
    attempts: list[ProviderAttempt] = []
    for attempt in (1, 2):
        started = time.perf_counter()
        try:
            generated = await asyncio.wait_for(
                provider.generate(
                    system=system,
                    prompt=json.dumps(payload, ensure_ascii=False),
                    temperature=0.0,
                    max_tokens=max_tokens,
                    frequency_penalty=0.0,
                ),
                timeout=stage_timeout_seconds,
            )
            parsed = schema.model_validate(_json_payload(generated.text))
            rejection = validator(parsed) if validator else None
            if rejection:
                raise OutputRejected(rejection)
        except (ProviderUnavailable, asyncio.TimeoutError) as exc:
            provider_error = exc if isinstance(exc, ProviderUnavailable) else None
            message = str(exc) if provider_error else f"stage exceeded {stage_timeout_seconds:g}-second timeout"
            attempts.append(ProviderAttempt(
                stage=stage, attempt=attempt, provider=provider.name, model=provider.model,
                elapsed_ms=round((time.perf_counter() - started) * 1000), success=False,
                http_status=provider_error.http_status if provider_error else None,
                error_type=provider_error.error_type if provider_error else "timeout",
                error=message, retry_performed=attempt == 1,
            ))
            if attempt == 2:
                raise DebateStageFailure(stage, attempts, message) from exc
            continue
        except OutputRejected as exc:
            attempts.append(ProviderAttempt(
                stage=stage, attempt=attempt, provider=provider.name, model=provider.model,
                elapsed_ms=round((time.perf_counter() - started) * 1000), success=False,
                error_type="output_quality_rejection", error=str(exc), retry_performed=attempt == 1,
            ))
            if attempt == 2:
                raise DebateStageFailure(stage, attempts, str(exc)) from exc
            continue
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            attempts.append(ProviderAttempt(
                stage=stage, attempt=attempt, provider=provider.name, model=provider.model,
                elapsed_ms=round((time.perf_counter() - started) * 1000), success=False,
                error_type="malformed_response", error=str(exc), retry_performed=attempt == 1,
            ))
            if attempt == 2:
                raise DebateStageFailure(stage, attempts, str(exc)) from exc
            continue
        attempts.append(ProviderAttempt(
            stage=stage, attempt=attempt, provider=generated.provider, model=generated.model,
            elapsed_ms=round((time.perf_counter() - started) * 1000), success=True,
        ))
        return parsed, attempts, generated
    raise AssertionError("bounded two-attempt loop exhausted")


def _public_output(output: ResearchAgentOutput) -> dict[str, Any]:
    return {
        "agent_id": output.agent_id,
        "claims": [{"text": claim.text, "evidence_ids": claim.evidence_ids} for claim in output.claims],
        "evidence_ids": output.evidence_ids,
        "uncertainties": output.uncertainties,
    }


def _trace(active, initial, critiques, revisions, consensus, stage_statuses, attempts) -> DebateTrace:
    agreements = [item for critique in critiques for item in critique.get("agreements", [])]
    disagreements = [item for critique in critiques for item in critique.get("challenges", [])]
    unresolved = [item for critique in critiques for field in ("unsupported_claims", "missing_evidence", "evidence_issues") for item in critique.get(field, [])]
    return DebateTrace(
        enabled=True, rounds=1, architecture="genuine_llm_structured_debate",
        selected_agents=[item.agent_id for item in active], critic_invoked=len(active) == 1,
        initial_outputs=initial, critiques=critiques, revisions=revisions,
        final_consensus=consensus or {}, stage_statuses=stage_statuses,
        provider_attempts=[item.model_dump(mode="json") for item in attempts],
        agreements=agreements, disagreements=disagreements, unresolved_conflicts=unresolved,
    )


async def _run_debate_round(provider, *, question, evidence, outputs, answer_validator, stage_timeout_seconds) -> DebateExecution:
    active = [output for output in outputs if not output.abstained]
    if not active:
        raise ValueError("C4 debate requires at least one active specialist")
    evidence_payload = [{"evidence_id": item.chunk_id, "text": item.chunk_text} for item in evidence]
    allowed_ids = {item.chunk_id for item in evidence}
    initial = [_public_output(item) for item in active]
    attempts: list[ProviderAttempt] = []
    stage_statuses: list[dict[str, Any]] = []
    critiques: list[dict[str, Any]] = []
    revisions: list[dict[str, Any]] = []
    prompt_tokens = 0
    completion_tokens = 0

    async def critique_one(output: ResearchAgentOutput):
        single = len(active) == 1
        reviewer = "grounding_critic" if single else output.agent_id
        reviewed_outputs = initial if single else [item for item in initial if item["agent_id"] != output.agent_id]
        exact_shape = ('{"agreements":["plain string"],"challenges":["plain string"],'
                       '"unsupported_claims":["plain string"],"missing_evidence":["plain string"],'
                       '"evidence_issues":["plain string"]}')
        parsed, call_attempts, generated = await _structured_call(
            provider, stage=f"critique:{reviewer}",
            system=(("You are an evidence-only Grounding Critic. " if single else "You are a TCM research specialist peer reviewer. ")
                    + "Use only supplied evidence and reviewed outputs. Do not add outside knowledge or hidden reasoning. "
                    + f"Return exactly one JSON object shaped as {exact_shape}. All five keys are required. "
                    + "Every array item must be a concise plain string, never an object or array. Use at most three items per array and no Markdown fences, prose, or extra keys."),
            payload={"question": question, "reviewed_outputs": reviewed_outputs, "evidence": evidence_payload},
            schema=CritiquePayload, max_tokens=512, stage_timeout_seconds=stage_timeout_seconds,
        )
        return ({"reviewer_id": reviewer, **parsed.model_dump(mode="json"),
                 "reviewed_peer_outputs": [] if single else reviewed_outputs,
                 "reviewed_output_agent_ids": [item["agent_id"] for item in reviewed_outputs]}, call_attempts, generated)

    critique_results = await asyncio.gather(*(critique_one(output) for output in active), return_exceptions=True)
    failures: list[DebateStageFailure] = []
    for result in critique_results:
        if isinstance(result, DebateStageFailure):
            failures.append(result); attempts.extend(result.attempts)
            stage_statuses.append({"stage": result.stage, "status": "FAIL_PROVIDER", "attempts": len(result.attempts)})
        elif isinstance(result, BaseException):
            raise result
        else:
            critique, call_attempts, generated = result
            critiques.append(critique); attempts.extend(call_attempts)
            prompt_tokens += generated.prompt_tokens; completion_tokens += generated.completion_tokens
            stage_statuses.append({"stage": f"critique:{critique['reviewer_id']}", "status": "PASS", "attempts": len(call_attempts)})
    if failures:
        first = failures[0]
        raise DebateStageFailure(first.stage, attempts, str(first), trace=_trace(active, initial, critiques, revisions, None, stage_statuses, attempts))

    async def revision_one(output: ResearchAgentOutput):
        peer_outputs = [item for item in initial if item["agent_id"] != output.agent_id]
        exact_shape = '{"revised_claims":["plain string"],"evidence_ids":["tcmv1-id"],"changes_made":["plain string"]}'
        parsed, call_attempts, generated = await _structured_call(
            provider, stage=f"revision:{output.agent_id}",
            system=("Revise this specialist position using only supplied evidence, peer outputs, and structured critiques. Do not add outside knowledge or hidden reasoning. "
                    + f"Return exactly one JSON object shaped as {exact_shape}. All three keys are required. revised_claims and changes_made contain concise plain strings only. "
                    + "evidence_ids contains exact supplied evidence IDs only. Use at most four revised claims and three changes. Return no Markdown fences, prose, or extra keys."),
            payload={"question": question, "initial_output": _public_output(output), "peer_outputs": peer_outputs, "critiques": critiques, "evidence": evidence_payload},
            schema=RevisionPayload, max_tokens=384, stage_timeout_seconds=stage_timeout_seconds,
            validator=lambda value: ("revision must contain claims and valid retrieved evidence IDs"
                                     if not value.revised_claims or not value.evidence_ids or not set(value.evidence_ids) <= allowed_ids else None),
        )
        return ({"agent_id": output.agent_id, **parsed.model_dump(mode="json"), "peer_outputs": peer_outputs,
                 "critiques_used": [item["reviewer_id"] for item in critiques]}, call_attempts, generated)

    revision_results = await asyncio.gather(*(revision_one(output) for output in active), return_exceptions=True)
    failures = []
    for result in revision_results:
        if isinstance(result, DebateStageFailure):
            failures.append(result); attempts.extend(result.attempts)
            stage_statuses.append({"stage": result.stage, "status": "FAIL_PROVIDER", "attempts": len(result.attempts)})
        elif isinstance(result, BaseException):
            raise result
        else:
            revision, call_attempts, generated = result
            revisions.append(revision); attempts.extend(call_attempts)
            prompt_tokens += generated.prompt_tokens; completion_tokens += generated.completion_tokens
            stage_statuses.append({"stage": f"revision:{revision['agent_id']}", "status": "PASS", "attempts": len(call_attempts)})
    if failures:
        first = failures[0]
        raise DebateStageFailure(first.stage, attempts, str(first), trace=_trace(active, initial, critiques, revisions, None, stage_statuses, attempts))

    exact_shape = '{"answer":"concise grounded answer","evidence_ids":["tcmv1-id"]}'
    try:
        consensus, call_attempts, generated = await _structured_call(
            provider, stage="consensus",
            system=("Produce a concise evidence-grounded consensus from the supplied revised positions. Use no outside knowledge and do not expose hidden reasoning. "
                    + f"Return exactly one JSON object shaped as {exact_shape}. Both keys are required; evidence_ids contains exact supplied evidence IDs only. "
                    + "Return no Markdown fences, prose, or extra keys."),
            payload={"question": question, "revised_positions": revisions, "evidence": evidence_payload},
            schema=ConsensusPayload, max_tokens=512, stage_timeout_seconds=stage_timeout_seconds,
            validator=lambda value: ("consensus must contain an answer and valid retrieved evidence IDs"
                                     if not value.answer.strip() or not value.evidence_ids or not set(value.evidence_ids) <= allowed_ids
                                     else answer_validator(value.answer) if answer_validator else None),
        )
    except DebateStageFailure as exc:
        all_attempts = [*attempts, *exc.attempts]
        stage_statuses.append({"stage": exc.stage, "status": "FAIL_PROVIDER", "attempts": len(exc.attempts)})
        raise DebateStageFailure(exc.stage, all_attempts, str(exc), trace=_trace(active, initial, critiques, revisions, None, stage_statuses, all_attempts)) from exc
    attempts.extend(call_attempts)
    prompt_tokens += generated.prompt_tokens; completion_tokens += generated.completion_tokens
    stage_statuses.append({"stage": "consensus", "status": "PASS", "attempts": len(call_attempts)})
    consensus_trace = {**consensus.model_dump(mode="json"), "revised_positions_received": [item["agent_id"] for item in revisions], "revisions_input": revisions}
    trace = _trace(active, initial, critiques, revisions, consensus_trace, stage_statuses, attempts)
    return DebateExecution(trace=trace, final_answer=consensus.answer.strip(), evidence_ids=consensus.evidence_ids,
                           provider_calls=len(attempts), successful_provider_calls=sum(item.success for item in attempts),
                           prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)


async def run_genuine_debate(
    provider, *, question: str, evidence: list[RetrievalItem], outputs: list[ResearchAgentOutput],
    rounds: int = 1, answer_validator: Callable[[str], str | None] | None = None,
    stage_timeout_seconds: float = PER_STAGE_TIMEOUT_SECONDS,
    whole_debate_timeout_seconds: float = WHOLE_DEBATE_TIMEOUT_SECONDS,
) -> DebateExecution:
    """Run exactly one bounded, evidence-only critique/revision/consensus round."""
    if rounds != 1:
        raise ValueError("formal C4 permits exactly one debate round")
    try:
        return await asyncio.wait_for(
            _run_debate_round(provider, question=question, evidence=evidence, outputs=outputs,
                              answer_validator=answer_validator, stage_timeout_seconds=stage_timeout_seconds),
            timeout=whole_debate_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise DebateStageFailure("debate_total", [], f"whole debate exceeded {whole_debate_timeout_seconds:g}-second timeout") from exc
