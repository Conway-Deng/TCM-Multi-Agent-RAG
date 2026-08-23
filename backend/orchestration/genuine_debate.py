from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from providers.openai_compatible import ProviderUnavailable
from schemas.research import DebateTrace, ProviderAttempt, ResearchAgentOutput, RetrievalItem


class CritiquePayload(BaseModel):
    reviewer_id: str
    agreements: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    citation_issues: list[str] = Field(default_factory=list)


class RevisionPayload(BaseModel):
    agent_id: str
    revised_position: str
    evidence_ids: list[str] = Field(default_factory=list)


class ConsensusPayload(BaseModel):
    final_answer: str
    evidence_ids: list[str] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)


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
    def __init__(self, stage: str, attempts: list[ProviderAttempt], reason: str) -> None:
        super().__init__(f"C4 required stage {stage} failed: {reason}")
        self.stage = stage
        self.attempts = attempts


class OutputRejected(ValueError):
    pass


def _json_payload(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("provider response must be a JSON object")
    return value


async def _structured_call(provider, *, stage: str, system: str, payload: dict[str, Any], schema, validator: Callable[[Any], str | None] | None = None):
    attempts: list[ProviderAttempt] = []
    for attempt in (1, 2):
        started = time.perf_counter()
        try:
            generated = await provider.generate(
                system=system,
                prompt=json.dumps(payload, ensure_ascii=False),
                temperature=0.0,
                max_tokens=384,
                frequency_penalty=0.5 if attempt == 1 else 1.0,
            )
            parsed = schema.model_validate(_json_payload(generated.text))
            rejection = validator(parsed) if validator else None
            if rejection:
                raise OutputRejected(rejection)
        except ProviderUnavailable as exc:
            attempts.append(ProviderAttempt(
                attempt=attempt, provider=provider.name, model=provider.model,
                elapsed_ms=round((time.perf_counter() - started) * 1000), success=False,
                http_status=exc.http_status, error_type=exc.error_type, error=str(exc),
                retry_performed=attempt == 1,
            ))
            if attempt == 2:
                raise DebateStageFailure(stage, attempts, str(exc)) from exc
            continue
        except OutputRejected as exc:
            attempts.append(ProviderAttempt(
                attempt=attempt, provider=provider.name, model=provider.model,
                elapsed_ms=round((time.perf_counter() - started) * 1000), success=False,
                error_type="output_quality_rejection", error=str(exc), retry_performed=attempt == 1,
            ))
            if attempt == 2:
                raise DebateStageFailure(stage, attempts, str(exc)) from exc
            continue
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            attempts.append(ProviderAttempt(
                attempt=attempt, provider=provider.name, model=provider.model,
                elapsed_ms=round((time.perf_counter() - started) * 1000), success=False,
                error_type="malformed_response", error=str(exc), retry_performed=attempt == 1,
            ))
            if attempt == 2:
                raise DebateStageFailure(stage, attempts, str(exc)) from exc
            continue
        attempts.append(ProviderAttempt(
            attempt=attempt, provider=generated.provider, model=generated.model,
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


async def run_genuine_debate(
    provider,
    *,
    question: str,
    evidence: list[RetrievalItem],
    outputs: list[ResearchAgentOutput],
    rounds: int = 1,
    answer_validator: Callable[[str], str | None] | None = None,
) -> DebateExecution:
    """Run exactly one bounded, evidence-only critique/revision/consensus round."""
    if rounds != 1:
        raise ValueError("formal C4 permits exactly one debate round")
    active = [output for output in outputs if not output.abstained]
    if not active:
        raise ValueError("C4 debate requires at least one active specialist")
    evidence_payload = [{"evidence_id": item.chunk_id, "text": item.chunk_text} for item in evidence]
    allowed_ids = {item.chunk_id for item in evidence}
    initial = [_public_output(item) for item in active]
    traces: list[ProviderAttempt] = []
    stage_statuses: list[dict[str, Any]] = []
    critiques: list[CritiquePayload] = []
    tokens = [0, 0]

    for output in active:
        single = len(active) == 1
        reviewer = "grounding_critic" if single else output.agent_id
        peers = initial if single else [item for item in initial if item["agent_id"] != output.agent_id]
        parsed, attempts, generated = await _structured_call(
            provider,
            stage=f"critique:{reviewer}",
            system=(
                "You are an evidence-only Grounding Critic." if single else
                "You are a TCM research specialist peer reviewer."
            ) + " Inspect only supplied evidence and peer outputs. Do not add outside knowledge or hidden reasoning. "
                "Return JSON with reviewer_id, agreements, challenges, unsupported_claims, missing_evidence, citation_issues.",
            payload={"question": question, "reviewer_id": reviewer, "reviewed_outputs": peers, "evidence": evidence_payload},
            schema=CritiquePayload,
        )
        critiques.append(parsed)
        traces.extend(attempts)
        tokens[0] += generated.prompt_tokens
        tokens[1] += generated.completion_tokens
        stage_statuses.append({"stage": f"critique:{reviewer}", "status": "PASS", "attempts": len(attempts)})

    revisions: list[RevisionPayload] = []
    for output in active:
        relevant = [item.model_dump(mode="json") for item in critiques]
        parsed, attempts, generated = await _structured_call(
            provider,
            stage=f"revision:{output.agent_id}",
            system="Revise the specialist position using only supplied evidence and structured critiques. Return JSON with agent_id, revised_position, evidence_ids. Do not expose hidden reasoning.",
            payload={"question": question, "agent_id": output.agent_id, "initial_output": _public_output(output), "critiques": relevant, "evidence": evidence_payload},
            schema=RevisionPayload,
            validator=lambda value: "revision cited evidence outside retrieval set" if not value.revised_position.strip() or not set(value.evidence_ids) <= allowed_ids else None,
        )
        revisions.append(parsed)
        traces.extend(attempts)
        tokens[0] += generated.prompt_tokens
        tokens[1] += generated.completion_tokens
        stage_statuses.append({"stage": f"revision:{output.agent_id}", "status": "PASS", "attempts": len(attempts)})

    consensus, attempts, generated = await _structured_call(
        provider,
        stage="consensus",
        system="Produce a concise evidence-grounded consensus from revised positions. Use no outside knowledge. Return JSON with final_answer, evidence_ids, agreements, disagreements, unresolved_conflicts. Do not expose hidden reasoning.",
        payload={"question": question, "initial_outputs": initial, "critiques": [x.model_dump(mode="json") for x in critiques], "revisions": [x.model_dump(mode="json") for x in revisions], "evidence": evidence_payload},
        schema=ConsensusPayload,
        validator=lambda value: (
            "empty answer or evidence outside retrieval set" if not value.final_answer.strip() or not set(value.evidence_ids) <= allowed_ids
            else answer_validator(value.final_answer) if answer_validator else None
        ),
    )
    traces.extend(attempts)
    tokens[0] += generated.prompt_tokens
    tokens[1] += generated.completion_tokens
    stage_statuses.append({"stage": "consensus", "status": "PASS", "attempts": len(attempts)})
    trace = DebateTrace(
        enabled=True, rounds=1, architecture="genuine_llm_structured_debate",
        selected_agents=[item.agent_id for item in active], critic_invoked=len(active) == 1,
        initial_outputs=initial,
        critiques=[x.model_dump(mode="json") for x in critiques],
        revisions=[x.model_dump(mode="json") for x in revisions],
        final_consensus=consensus.model_dump(mode="json"), stage_statuses=stage_statuses,
        provider_attempts=[x.model_dump(mode="json") for x in traces],
        agreements=consensus.agreements, disagreements=consensus.disagreements,
        unresolved_conflicts=consensus.unresolved_conflicts,
    )
    return DebateExecution(
        trace=trace, final_answer=consensus.final_answer.strip(), evidence_ids=consensus.evidence_ids,
        provider_calls=len(traces), successful_provider_calls=sum(x.success for x in traces),
        prompt_tokens=tokens[0], completion_tokens=tokens[1],
    )
