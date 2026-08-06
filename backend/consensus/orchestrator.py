from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from pydantic import ValidationError

from .adapters import TCMAdapter, WestAPIAdapter, WestFixtureAdapter
from .adapters.base import AdapterError
from .client import ConsensusLLMClient, ConsensusLLMError
from .judges import judge_confidence, judge_conflicts, judge_evidence, judge_safety
from .schemas import (
    AgentOutput,
    ConfidenceJudgeResult,
    ConfidenceSummary,
    ConflictJudgeResult,
    ConsensusConsultRequest,
    ConsensusResponse,
    ConsensusStrategy,
    DebateResult,
    EvidenceJudgeResult,
    IntegratedResponse,
    JudgeResults,
    ModelTraceEntry,
    SafetyJudgeResult,
)
from .strategies import concatenate, weighted


class ConsensusDisabledError(Exception):
    pass


def consensus_enabled() -> bool:
    return os.getenv("CONSENSUS_ENABLED", "true").strip().casefold() in {"1", "true", "yes", "on"}


def _all_evidence_ids(agents: list[AgentOutput]) -> list[str]:
    return list(dict.fromkeys(item.evidence_id for agent in agents for item in agent.evidence))


def _payload(question: str, context: dict[str, Any], agents: list[AgentOutput], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "question": question,
        "context": context,
        "agents": [agent.model_dump(mode="json") for agent in agents],
        "fixture_notice": "Any source_type=fixture output is synthetic and not verified clinical evidence.",
    }
    if extra:
        result.update(extra)
    return result


def _deterministic_debate(agents: list[AgentOutput]) -> DebateResult:
    conflict = judge_conflicts(agents)
    unsupported = [claim.claim_id for agent in agents for claim in agent.claims if not claim.evidence_ids]
    missing = []
    if any(agent.abstained for agent in agents):
        missing.append("At least one domain agent abstained; additional information or evidence is required.")
    return DebateResult(
        agreements=conflict.agreements,
        disagreements=[item.description for item in conflict.conflicts],
        complementary_points=conflict.complementary_points,
        unsupported_assertions=unsupported,
        missing_information=missing,
        unresolved_conflicts=[item.description for item in conflict.conflicts if not item.resolvable],
        recommendations_not_to_merge=["Do not merge fixture claims into verified medical conclusions."],
        confidence_reductions=["Synthetic fixture provenance reduces confidence."] if any(agent.source_type.value == "fixture" for agent in agents) else [],
        reasoning_summary="Deterministic debate fallback compares provenance, abstention, evidence links, safety, and explicit conflicts.",
        generation_source="deterministic_fallback",
    )


def _deterministic_synthesis(
    agents: list[AgentOutput],
    debate: DebateResult,
    judges: JudgeResults,
) -> IntegratedResponse:
    confidence = judges.confidence or ConfidenceJudgeResult(score=0.2, level="low", reason="Confidence judge unavailable.")
    safety = judges.safety or judge_safety(agents)
    summaries = [f"{agent.domain.value} ({agent.source_type.value}): {agent.summary}" for agent in agents]
    limitations = list(dict.fromkeys(item for agent in agents for item in agent.limitations))
    if any(agent.source_type.value == "fixture" for agent in agents):
        limitations.insert(0, "Western Medicine content is a synthetic fixture for orchestration testing, not a live RAG/API result.")
    return IntegratedResponse(
        summary=" ".join(summaries),
        agreements=debate.agreements,
        disagreements=debate.disagreements or debate.unresolved_conflicts,
        safety_notes=list(dict.fromkeys(safety.safety_flags + (["Seek urgent professional medical care now."] if safety.urgent else []))),
        limitations=limitations,
        unresolved_questions=debate.missing_information + debate.unresolved_conflicts,
        confidence=ConfidenceSummary(score=confidence.score, level=confidence.level, reason=confidence.reason),
    )


class ConsensusOrchestrator:
    def __init__(self, *, llm_client: ConsensusLLMClient | None = None, allow_fixture: bool | None = None) -> None:
        self.llm = llm_client or ConsensusLLMClient()
        self.allow_fixture = allow_fixture

    async def _agents(self, request: ConsensusConsultRequest) -> list[AgentOutput]:
        adapters = []
        for domain in request.domains:
            if domain == "tcm":
                adapters.append(TCMAdapter())
            elif domain == "western_fixture":
                adapters.append(WestFixtureAdapter(allow_fixture=self.allow_fixture))
            elif domain == "western_api":
                adapters.append(WestAPIAdapter())
        results = await asyncio.gather(
            *(adapter.run(request.question, request.context) for adapter in adapters),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, AdapterError):
                raise result
            if isinstance(result, Exception):
                raise AdapterError("A domain adapter failed safely.") from result
        return [result for result in results if isinstance(result, AgentOutput)]

    async def _debate(self, request: ConsensusConsultRequest, agents: list[AgentOutput]) -> DebateResult:
        fallback = _deterministic_debate(agents)
        if not self.llm.configured:
            return fallback
        try:
            result = await self.llm.call_json(
                "debate",
                _payload(request.question, request.context.model_dump(), agents),
                evidence_ids=_all_evidence_ids(agents),
            )
            debate = DebateResult.model_validate(result.data)
            debate.generation_source = "llm"
            debate.unsupported_assertions = list(dict.fromkeys(debate.unsupported_assertions + fallback.unsupported_assertions))
            debate.missing_information = list(dict.fromkeys(debate.missing_information + fallback.missing_information))
            debate.unresolved_conflicts = list(dict.fromkeys(debate.unresolved_conflicts + fallback.unresolved_conflicts))
            debate.recommendations_not_to_merge = list(
                dict.fromkeys(debate.recommendations_not_to_merge + fallback.recommendations_not_to_merge)
            )
            return debate
        except (ConsensusLLMError, ValidationError):
            return fallback

    async def _llm_judge(
        self,
        role: str,
        model_type: type[EvidenceJudgeResult] | type[SafetyJudgeResult] | type[ConflictJudgeResult] | type[ConfidenceJudgeResult],
        request: ConsensusConsultRequest,
        agents: list[AgentOutput],
        debate: DebateResult,
        fallback: Any,
        judges: JudgeResults,
    ) -> Any:
        if not self.llm.configured:
            return fallback
        extra = {"debate": debate.model_dump(), "previous_judges": judges.model_dump(exclude_none=True)}
        try:
            result = await self.llm.call_json(
                role,
                _payload(request.question, request.context.model_dump(), agents, extra),
                evidence_ids=_all_evidence_ids(agents),
            )
            return model_type.model_validate(result.data)
        except (ConsensusLLMError, ValidationError):
            return fallback

    async def _run_judges(self, request: ConsensusConsultRequest, agents: list[AgentOutput], debate: DebateResult) -> JudgeResults:
        deterministic_evidence = judge_evidence(agents)
        evidence = await self._llm_judge("evidence_judge", EvidenceJudgeResult, request, agents, debate, deterministic_evidence, JudgeResults())
        evidence.unsupported_claim_ids = list(
            dict.fromkeys(evidence.unsupported_claim_ids + deterministic_evidence.unsupported_claim_ids)
        )
        evidence.supported_claim_ids = [
            claim_id for claim_id in evidence.supported_claim_ids if claim_id not in evidence.unsupported_claim_ids
        ]
        evidence.citation_issues = list(dict.fromkeys(evidence.citation_issues + deterministic_evidence.citation_issues))
        evidence.evidence_coverage_score = min(evidence.evidence_coverage_score, deterministic_evidence.evidence_coverage_score)
        deterministic_safety = judge_safety(agents)
        safety = await self._llm_judge("safety_judge", SafetyJudgeResult, request, agents, debate, deterministic_safety, JudgeResults(evidence=evidence))
        safety.urgent = safety.urgent or deterministic_safety.urgent
        safety.safety_flags = list(dict.fromkeys(deterministic_safety.safety_flags + safety.safety_flags))
        if deterministic_safety.urgent:
            safety.reasoning_summary = "Deterministic urgent routing is authoritative. " + safety.reasoning_summary
        deterministic_conflict = judge_conflicts(agents)
        conflict = await self._llm_judge("conflict_judge", ConflictJudgeResult, request, agents, debate, deterministic_conflict, JudgeResults(evidence=evidence, safety=safety))
        known_conflicts = {(tuple(item.claim_ids), item.type, item.description) for item in conflict.conflicts}
        conflict.conflicts.extend(
            item
            for item in deterministic_conflict.conflicts
            if (tuple(item.claim_ids), item.type, item.description) not in known_conflicts
        )
        conflict.agreements = list(dict.fromkeys(conflict.agreements + deterministic_conflict.agreements))
        conflict.complementary_points = list(
            dict.fromkeys(conflict.complementary_points + deterministic_conflict.complementary_points)
        )
        conflict.conflict_score = max(conflict.conflict_score, deterministic_conflict.conflict_score)
        deterministic_confidence = judge_confidence(agents, evidence, safety, conflict, model_failure_count=self.llm.failure_count)
        confidence = await self._llm_judge(
            "confidence_judge",
            ConfidenceJudgeResult,
            request,
            agents,
            debate,
            deterministic_confidence,
            JudgeResults(evidence=evidence, safety=safety, conflict=conflict),
        )
        confidence.score = min(confidence.score, deterministic_confidence.score)
        confidence.level = "high" if confidence.score >= 0.75 else "medium" if confidence.score >= 0.45 else "low"
        confidence.penalties = list(dict.fromkeys(confidence.penalties + deterministic_confidence.penalties))
        return JudgeResults(evidence=evidence, safety=safety, conflict=conflict, confidence=confidence)

    async def _synthesize(
        self,
        request: ConsensusConsultRequest,
        agents: list[AgentOutput],
        debate: DebateResult,
        judges: JudgeResults,
    ) -> IntegratedResponse:
        fallback = _deterministic_synthesis(agents, debate, judges)
        if not self.llm.configured:
            return fallback
        try:
            result = await self.llm.call_json(
                "synthesis",
                _payload(
                    request.question,
                    request.context.model_dump(),
                    agents,
                    {"debate": debate.model_dump(), "judges": judges.model_dump(exclude_none=True)},
                ),
                evidence_ids=_all_evidence_ids(agents),
            )
            integrated = IntegratedResponse.model_validate(result.data)
            if judges.safety and judges.safety.urgent:
                integrated.safety_notes = list(dict.fromkeys(["Seek urgent professional medical care now.", *integrated.safety_notes]))
            integrated.agreements = list(dict.fromkeys(integrated.agreements + debate.agreements))
            preserved_disagreements = list(debate.disagreements + debate.unresolved_conflicts)
            if judges.conflict:
                preserved_disagreements.extend(item.description for item in judges.conflict.conflicts)
            integrated.disagreements = list(dict.fromkeys(integrated.disagreements + preserved_disagreements))
            if any(agent.source_type.value == "fixture" for agent in agents):
                integrated.limitations = list(dict.fromkeys(["Western Medicine content is a synthetic fixture for orchestration testing, not verified clinical evidence.", *integrated.limitations]))
            if judges.confidence:
                integrated.confidence.score = min(integrated.confidence.score, judges.confidence.score)
                integrated.confidence.level = "high" if integrated.confidence.score >= 0.75 else "medium" if integrated.confidence.score >= 0.45 else "low"
            return integrated
        except (ConsensusLLMError, ValidationError):
            return fallback

    async def run(self, request: ConsensusConsultRequest) -> ConsensusResponse:
        if not consensus_enabled():
            raise ConsensusDisabledError("Consensus orchestration is disabled by configuration.")
        started = time.perf_counter()
        agents = await self._agents(request)
        fixture_used = any(agent.source_type.value == "fixture" for agent in agents)
        domain_trace: list[ModelTraceEntry] = []
        domain_api_call_count = 0
        domain_failure_count = 0
        for agent in agents:
            llm_error = str(agent.metadata.get("llm_error") or "")
            attempted = agent.generation_source == "siliconflow_llm" or (
                agent.generation_source == "mock_fallback" and llm_error and llm_error != "LLM_API_KEY is missing"
            )
            if not attempted:
                continue
            domain_api_call_count += 1
            failed = agent.generation_source != "siliconflow_llm"
            domain_failure_count += int(failed)
            domain_trace.append(
                ModelTraceEntry(
                    role=agent.agent_id,
                    model=agent.model,
                    status="fallback" if failed else "success",
                    latency_ms=agent.latency_ms,
                    evidence_ids_received=[item.evidence_id for item in agent.evidence],
                    error=llm_error or None,
                )
            )
        debate: DebateResult | None = None
        judges = JudgeResults()
        weights = []
        selected: list[str] = []
        excluded: list[str] = []

        if request.strategy == ConsensusStrategy.CONCATENATE:
            integrated, judges = concatenate(agents)
        elif request.strategy == ConsensusStrategy.WEIGHTED:
            integrated, judges, weights, selected, excluded = weighted(agents)
        elif request.strategy == ConsensusStrategy.DEBATE:
            debate = await self._debate(request, agents)
            evidence = judge_evidence(agents)
            safety = judge_safety(agents)
            conflict = judge_conflicts(agents)
            confidence = judge_confidence(agents, evidence, safety, conflict, model_failure_count=self.llm.failure_count)
            judges = JudgeResults(confidence=confidence)
            integrated = _deterministic_synthesis(agents, debate, JudgeResults(evidence=evidence, safety=safety, conflict=conflict, confidence=confidence))
        else:
            debate = await self._debate(request, agents)
            judges = await self._run_judges(request, agents, debate)
            integrated = await self._synthesize(request, agents, debate, judges)

        return ConsensusResponse(
            strategy=request.strategy,
            question=request.question,
            agents=agents,
            debate=debate,
            judges=judges,
            integrated_response=integrated,
            agent_weights=weights,
            selected_claim_ids=selected,
            excluded_claim_ids=excluded,
            fixture_used=fixture_used,
            experimental=True,
            latency_ms=round((time.perf_counter() - started) * 1000),
            api_call_count=domain_api_call_count + self.llm.call_count,
            model_call_failure_count=domain_failure_count + self.llm.failure_count,
            model_trace=[*domain_trace, *self.llm.trace] if request.include_trace else [],
        )
