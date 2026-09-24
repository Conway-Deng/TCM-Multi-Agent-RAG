from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from .adapters import (
    AdapterOutcome,
    EvidenceAdapter,
    PerspectiveAdapterError,
    TCMEvidenceAdapter,
    WesternEvidenceAdapter,
)
from .cross_perspective_critic import (
    CRITIC_MODEL,
    CrossPerspectiveCriticAgent,
    check_critic_preconditions,
)
from .governance import (
    CrossPerspectiveGovernanceAgent,
    GOVERNANCE_MODEL,
    build_governance_advisory_context,
    build_governance_payload,
)
from .model_calls import StructuredModelCallFailure
from .perspective_agents import (
    COVERAGE_AUDITOR_MODEL,
    EVIDENCE_SPECIALIST_MODEL,
    GROUNDING_SKEPTIC_MODEL,
    PerspectiveAdvisorySuite,
)
from .router import CrossPerspectiveRouter, ROUTER_MODEL
from .schemas import (
    ActivePerspectiveName,
    CriticExecutionStatus,
    CrossPerspectiveAnswer,
    CrossPerspectiveConsultRequest,
    CrossPerspectiveConsultResponse,
    CrossPerspectiveCritique,
    CrossPerspectiveTrace,
    ModelCallEvent,
    NUTRITION_UNAVAILABLE_MESSAGE,
    PerspectiveAgentAssessment,
    PerspectiveEvidencePacket,
    PerspectiveFailure,
    RoutingDecision,
)
from .tracing import DevelopmentTraceLogger, TraceSink


class NutritionUnavailableError(ValueError):
    pass


class CrossPerspectiveRunError(RuntimeError):
    def __init__(self, message: str, *, trace: CrossPerspectiveTrace) -> None:
        super().__init__(message)
        self.trace = trace


def _not_selected_packet(perspective: ActivePerspectiveName) -> PerspectiveEvidencePacket:
    return PerspectiveEvidencePacket(
        perspective=perspective,
        available=False,
        execution_status="not_selected",
        interpretation=f"The {perspective} perspective was not selected by the router.",
        uncertainty=[],
        missing_information=[f"No {perspective} evidence pathway was run."],
        limitations=[],
        provenance=[],
    )


def _failed_packet(
    perspective: ActivePerspectiveName,
    exc: Exception,
) -> PerspectiveEvidencePacket:
    if isinstance(exc, PerspectiveAdapterError):
        failure_type = exc.failure_type
        error_summary = str(exc)
        http_status = exc.http_status
        retry_count = exc.retry_count
    else:
        failure_type = "unexpected"
        error_summary = f"{perspective.capitalize()} evidence pathway failed unexpectedly."
        http_status = None
        retry_count = 0
    return PerspectiveEvidencePacket(
        perspective=perspective,
        available=False,
        execution_status="unavailable",
        interpretation=f"The {perspective} perspective is unavailable for this consultation.",
        uncertainty=["No claims may be inferred for this unavailable perspective."],
        missing_information=[error_summary],
        limitations=["This perspective failure must not be replaced by another model or fabricated by governance."],
        provenance=[],
        failure=PerspectiveFailure(
            role=perspective,
            failure_type=failure_type,  # type: ignore[arg-type]
            error_summary=error_summary,
            http_status=http_status,
            retry_count=retry_count,
        ),
    )


class CrossPerspectiveService:
    def __init__(
        self,
        *,
        router: CrossPerspectiveRouter | None = None,
        tcm_adapter: EvidenceAdapter | None = None,
        western_adapter: EvidenceAdapter | None = None,
        advisory_suite: PerspectiveAdvisorySuite | None = None,
        critic: CrossPerspectiveCriticAgent | None = None,
        governance: CrossPerspectiveGovernanceAgent | None = None,
        trace_sink: TraceSink | None = None,
    ) -> None:
        self.router = router or CrossPerspectiveRouter()
        self.adapters: dict[ActivePerspectiveName, EvidenceAdapter] = {
            "tcm": tcm_adapter or TCMEvidenceAdapter(),
            "western": western_adapter or WesternEvidenceAdapter(),
        }
        self.advisory_suite = advisory_suite or PerspectiveAdvisorySuite()
        self.critic = critic or CrossPerspectiveCriticAgent()
        self.governance = governance or CrossPerspectiveGovernanceAgent()
        self.trace_sink = trace_sink or DevelopmentTraceLogger()

    async def consult(self, request: CrossPerspectiveConsultRequest) -> CrossPerspectiveConsultResponse:
        if "nutrition" in request.perspectives:
            raise NutritionUnavailableError(NUTRITION_UNAVAILABLE_MESSAGE)

        run_id = f"cross-perspective-v0.4-dev-{uuid4()}"
        timestamp = datetime.now(timezone.utc)
        started = perf_counter()
        events: list[ModelCallEvent] = []
        latency_by_stage: dict[str, float] = {}

        router_started = perf_counter()
        if request.router_mode == "forced":
            forced = [item for item in request.perspectives if item in {"tcm", "western"}]
            routing = self.router.route_forced(forced)  # type: ignore[arg-type]
        else:
            try:
                route_result = await self.router.route_auto(request.question)
                routing = route_result.value
                assert isinstance(routing, RoutingDecision)
                events.extend(route_result.events)
            except StructuredModelCallFailure as exc:
                events.extend(exc.events)
                latency_by_stage["router"] = round((perf_counter() - router_started) * 1000, 3)
                trace = self._trace(
                    run_id=run_id,
                    timestamp=timestamp,
                    request=request,
                    routing=None,
                    packets={},
                    answer=None,
                    events=events,
                    latency_by_stage=latency_by_stage,
                    total_started=started,
                    failed_roles=["router"],
                    perspective_assessments={},
                    critic_status="not_applicable",
                    cross_perspective_critique=None,
                )
                self.trace_sink.write(trace)
                raise CrossPerspectiveRunError("Router model call failed; no evidence pathway was selected.", trace=trace) from exc
        latency_by_stage["router"] = round((perf_counter() - router_started) * 1000, 3)

        selected = list(routing.requested_perspectives)
        tasks = [self.adapters[perspective].collect(request.question) for perspective in selected]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        packets: dict[ActivePerspectiveName, PerspectiveEvidencePacket] = {
            "tcm": _not_selected_packet("tcm"),
            "western": _not_selected_packet("western"),
        }
        failed_roles: list[str] = []
        for perspective, result in zip(selected, results, strict=True):
            if isinstance(result, BaseException):
                exception = result if isinstance(result, Exception) else RuntimeError("adapter cancelled")
                packets[perspective] = _failed_packet(perspective, exception)
                failed_roles.append(perspective)
                if isinstance(exception, PerspectiveAdapterError):
                    events.extend(exception.events)
                latency_by_stage[perspective] = 0.0
                continue
            assert isinstance(result, AdapterOutcome)
            packets[perspective] = result.packet
            events.extend(result.events)
            latency_by_stage[perspective] = result.latency_ms
            if not result.packet.available or result.packet.failure is not None:
                failed_roles.append(perspective)

        advisory_result = await self.advisory_suite.analyze(
            question=request.question,
            packets=packets,
        )
        events.extend(advisory_result.events)
        latency_by_stage.update(advisory_result.latency_by_role)
        failed_roles.extend(advisory_result.failed_roles)
        perspective_assessments = advisory_result.assessments

        critic_eligible, initial_critic_status = check_critic_preconditions(
            packets=packets,
            assessments=perspective_assessments,
        )
        critic_status: CriticExecutionStatus = initial_critic_status
        cross_perspective_critique: CrossPerspectiveCritique | None = None
        if critic_eligible:
            critic_started = perf_counter()
            try:
                critic_result = await self.critic.critique(
                    question=request.question,
                    packets=packets,
                    assessments=perspective_assessments,
                )
                cross_perspective_critique = critic_result.value
                assert isinstance(cross_perspective_critique, CrossPerspectiveCritique)
                events.extend(critic_result.events)
                critic_status = "completed"
            except StructuredModelCallFailure as exc:
                events.extend(exc.events)
                failed_roles.append("cross_perspective_critic")
                critic_status = "failed"
            except Exception:
                failed_roles.append("cross_perspective_critic")
                critic_status = "failed"
            latency_by_stage["cross_perspective_critic"] = round((perf_counter() - critic_started) * 1000, 3)

        governance_started = perf_counter()
        answer: CrossPerspectiveAnswer | None = None
        try:
            governance_result = await self.governance.synthesize(
                question=request.question,
                packets=packets,
                assessments=perspective_assessments,
                critique=cross_perspective_critique,
            )
            answer = governance_result.value
            assert isinstance(answer, CrossPerspectiveAnswer)
            events.extend(governance_result.events)
        except StructuredModelCallFailure as exc:
            events.extend(exc.events)
            failed_roles.append("governance")
        latency_by_stage["governance"] = round((perf_counter() - governance_started) * 1000, 3)

        trace = self._trace(
            run_id=run_id,
            timestamp=timestamp,
            request=request,
            routing=routing,
            packets=packets,
            answer=answer,
            events=events,
            latency_by_stage=latency_by_stage,
            total_started=started,
            failed_roles=failed_roles,
            perspective_assessments=perspective_assessments,
            critic_status=critic_status,
            cross_perspective_critique=cross_perspective_critique,
        )
        self.trace_sink.write(trace)
        status = "failed" if answer is None else "partial_failure" if failed_roles else "completed"
        return CrossPerspectiveConsultResponse(
            run_id=run_id,
            status=status,
            routing=routing,
            perspective_packets=packets,
            answer=answer,
            failed_roles=list(dict.fromkeys(failed_roles)),
            perspective_assessments=perspective_assessments,
            critic_status=critic_status,
            cross_perspective_critique=cross_perspective_critique,
            trace=trace,
        )

    @staticmethod
    def _trace(
        *,
        run_id: str,
        timestamp: datetime,
        request: CrossPerspectiveConsultRequest,
        routing: RoutingDecision | None,
        packets: dict[ActivePerspectiveName, PerspectiveEvidencePacket],
        answer: CrossPerspectiveAnswer | None,
        events: list[ModelCallEvent],
        latency_by_stage: dict[str, float],
        total_started: float,
        failed_roles: list[str],
        perspective_assessments: dict[ActivePerspectiveName, list[PerspectiveAgentAssessment]],
        critic_status: CriticExecutionStatus = "not_applicable",
        cross_perspective_critique: CrossPerspectiveCritique | None = None,
    ) -> CrossPerspectiveTrace:
        source_ids = {
            name: list(dict.fromkeys(item.source_id for item in packet.provenance))
            for name, packet in packets.items()
        }
        chunk_ids = {
            name: list(dict.fromkeys(item.chunk_id for item in packet.provenance))
            for name, packet in packets.items()
        }
        governance_input = {
            "perspective_packets": build_governance_payload(packets),
            "advisory_context": build_governance_advisory_context(
                perspective_assessments, cross_perspective_critique, packets=packets
            ),
        }
        question_hash = hashlib.sha256(request.question.encode("utf-8")).hexdigest()
        governance_input["question_hash"] = question_hash
        if os.getenv("CROSS_PERSPECTIVE_TRACE_RAW_QUESTION", "false").strip().casefold() in {
            "1", "true", "yes", "on"
        }:
            governance_input["question"] = request.question
        return CrossPerspectiveTrace(
            run_id=run_id,
            timestamp=timestamp,
            question_id=request.question_id,
            question_hash=question_hash,
            router_output=routing,
            selected_perspectives=list(routing.requested_perspectives) if routing else [],
            retrieval_source_ids=source_ids,
            retrieval_chunk_ids=chunk_ids,
            perspective_packets=packets,
            governance_input=governance_input,
            governance_output=answer,
            model_ids={
                "router": ROUTER_MODEL,
                "tcm": "Qwen/Qwen3-8B",
                "western": "Qwen/Qwen3-8B",
                "evidence_specialist": EVIDENCE_SPECIALIST_MODEL,
                "coverage_auditor": COVERAGE_AUDITOR_MODEL,
                "grounding_skeptic": GROUNDING_SKEPTIC_MODEL,
                "cross_perspective_critic": CRITIC_MODEL,
                "governance": GOVERNANCE_MODEL,
            },
            model_calls=len(events),
            latency_by_stage_ms=latency_by_stage,
            total_latency_ms=round((perf_counter() - total_started) * 1000, 3),
            provider_events=events,
            retry_count=sum(1 for event in events if event.attempt == 2),
            failed_roles=list(dict.fromkeys(failed_roles)),
            perspective_assessments=perspective_assessments,
            critic_status=critic_status,
            cross_perspective_critique=cross_perspective_critique,
        )
