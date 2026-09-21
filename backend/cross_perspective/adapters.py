from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Awaitable, Callable, Protocol

from tcm.agent import OpenAICompatibleClient, consult as tcm_consult
from tcm.schemas import TCMConsultRequest, TCMConsultResponse
from western.agent import WESTERN_MODEL, WesternEvidenceAgent
from western.schemas import WesternConsultRequest, WesternConsultResponse

from .schemas import (
    EvidenceReference,
    ModelCallEvent,
    PerspectiveClaim,
    PerspectiveEvidencePacket,
    PerspectiveFailure,
    ProvenanceRecord,
)


TCM_MODEL = "Qwen/Qwen3-8B"


class EvidenceAdapter(Protocol):
    perspective: str

    async def collect(self, question: str) -> "AdapterOutcome": ...


class PerspectiveAdapterError(RuntimeError):
    def __init__(
        self,
        role: str,
        message: str,
        *,
        failure_type: str = "unexpected",
        http_status: int | None = None,
        retry_count: int = 0,
        events: list[ModelCallEvent] | None = None,
    ) -> None:
        super().__init__(message)
        self.role = role
        self.failure_type = failure_type
        self.http_status = http_status
        self.retry_count = retry_count
        self.events = events or []


@dataclass(frozen=True)
class AdapterOutcome:
    packet: PerspectiveEvidencePacket
    events: list[ModelCallEvent]
    latency_ms: float


def _tcm_failure_type(message: str) -> str:
    lowered = message.casefold()
    if "key is missing" in lowered:
        return "configuration"
    if "timed out" in lowered:
        return "timeout"
    if "http" in lowered:
        return "http"
    if "network" in lowered or "provider" in lowered:
        return "provider"
    return "unexpected"


def _tcm_events(response: TCMConsultResponse) -> list[ModelCallEvent]:
    """Translate additive legacy telemetry into one event per HTTP attempt."""
    attempts = response.provider_attempts
    if attempts <= 0:
        return []
    statuses = response.provider_http_statuses
    elapsed = response.timings.llm_ms / attempts if attempts else 0.0
    events: list[ModelCallEvent] = []
    for index in range(attempts):
        status = statuses[index] if index < len(statuses) else None
        compatibility_failure = response.provider_compatibility_retry and index == 0 and status in {400, 422}
        success = index == attempts - 1 and not response.llm_error and not compatibility_failure
        failure_class = None
        error_summary = None
        if compatibility_failure:
            failure_class = "http"
            error_summary = "Provider rejected response_format; compatibility retry was attempted."
        elif not success:
            failure_class = _tcm_failure_type(response.llm_error or "provider attempt failed")
            error_summary = response.llm_error or "Provider attempt failed."
        events.append(
            ModelCallEvent(
                role="tcm",
                attempt=index + 1,
                provider=response.llm_provider or "unknown",
                requested_model=TCM_MODEL,
                reported_model=response.llm_provider_model if success else None,
                success=success,
                latency_ms=elapsed,
                http_status=status,
                failure_class=failure_class,  # type: ignore[arg-type]
                error_summary=error_summary,
                retry_performed=index > 0,
            )
        )
    return events


class TCMEvidenceAdapter:
    perspective = "tcm"

    def __init__(
        self,
        consult_fn: Callable[[TCMConsultRequest], Awaitable[TCMConsultResponse]] | None = None,
    ) -> None:
        self.consult_fn = consult_fn or tcm_consult
        self._uses_default_consult = consult_fn is None

    async def collect(self, question: str) -> AdapterOutcome:
        started = perf_counter()
        if self._uses_default_consult:
            configured_model = OpenAICompatibleClient().model
            if configured_model != TCM_MODEL:
                raise PerspectiveAdapterError(
                    "tcm",
                    f"TCM model configuration must be {TCM_MODEL} for this prototype.",
                    failure_type="configuration",
                )
        try:
            response = await self.consult_fn(TCMConsultRequest(question=question))
        except PerspectiveAdapterError:
            raise
        except Exception as exc:
            raise PerspectiveAdapterError(
                "tcm", "TCM evidence pathway failed unexpectedly.", failure_type="unexpected"
            ) from exc

        citations = {item.source_id: item for item in response.citations}
        evidence_by_id = {item.evidence_id: item for item in response.evidence}
        provenance: list[ProvenanceRecord] = []
        seen_pairs: set[tuple[str, str]] = set()
        for evidence in response.evidence:
            for source_id in evidence.source_ids:
                pair = (source_id, evidence.evidence_id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                citation = citations.get(source_id)
                provenance.append(
                    ProvenanceRecord(
                        source_id=source_id,
                        chunk_id=evidence.evidence_id,
                        title=citation.title if citation else evidence.title,
                        source_url=citation.url_or_identifier if citation else "",
                        source_type=citation.source_type if citation else evidence.source_type,
                        section=citation.section if citation else "",
                        excerpt=evidence.snippet,
                        identifier=citation.url_or_identifier if citation else "",
                        license="",
                    )
                )

        claims: list[PerspectiveClaim] = []
        for claim in response.claims:
            refs: list[EvidenceReference] = []
            review_statuses: list[str] = []
            for evidence_id in claim.evidence_ids:
                evidence = evidence_by_id.get(evidence_id)
                if evidence is None:
                    continue
                review_statuses.append(evidence.review_status)
                for source_id in evidence.source_ids:
                    citation = citations.get(source_id)
                    refs.append(
                        EvidenceReference(
                            source_id=source_id,
                            chunk_id=evidence_id,
                            title=citation.title if citation else evidence.title,
                        )
                    )
            if not refs:
                support_status = "insufficient"
            elif any(status == "needs_human_review" for status in review_statuses):
                support_status = "partially_supported"
            else:
                support_status = "supported"
            claims.append(
                PerspectiveClaim(
                    claim_id=f"tcm:{claim.claim_id}",
                    claim_text=claim.text,
                    evidence_refs=refs,
                    support_status=support_status,
                )
            )

        events: list[ModelCallEvent] = _tcm_events(response)
        failure = None
        execution_status = "abstained" if response.abstained else "available"
        uncertainty = [response.confidence.reason]
        if response.llm_error:
            failure_type = _tcm_failure_type(response.llm_error)
            failure = PerspectiveFailure(
                role="tcm",
                failure_type=failure_type,  # type: ignore[arg-type]
                error_summary=response.llm_error,
                http_status=(
                    response.provider_http_statuses[-1]
                    if response.provider_http_statuses
                    else None
                ),
                retry_count=response.provider_retry_count,
            )
            execution_status = "degraded"
            uncertainty.append(
                "The TCM language-generation call was unavailable; the packet preserves the existing deterministic retrieval-grounded fallback and records that degradation."
            )

        model_mismatch = (
            response.generation_source == "siliconflow_llm"
            and response.llm_provider_model != TCM_MODEL
        )
        if model_mismatch:
            mismatch_detail = (
                "TCM provider-reported model was missing."
                if not response.llm_provider_model
                else f"TCM provider-reported model {response.llm_provider_model!r} did not match {TCM_MODEL}."
            )
            failure = PerspectiveFailure(
                role="tcm",
                failure_type="configuration",
                error_summary=mismatch_detail,
                retry_count=response.provider_retry_count,
            )
            execution_status = "degraded"
            uncertainty.append(mismatch_detail)
            if events:
                events[-1] = events[-1].model_copy(
                    update={
                        "success": False,
                        "failure_class": "configuration",
                        "error_summary": mismatch_detail,
                        "reported_model": response.llm_provider_model,
                    }
                )
            interpretation = "TCM generated interpretation was rejected because provider model identity could not be verified."
        else:
            interpretation = response.summary

        missing_information: list[str] = []
        abstention_reason = getattr(response, "abstention_reason", None)
        if abstention_reason:
            missing_information.append(str(abstention_reason))
        if not response.evidence:
            missing_information.append("No TCM evidence chunk was available for this routed question.")

        packet = PerspectiveEvidencePacket(
            perspective="tcm",
            available=True,
            execution_status=execution_status,  # type: ignore[arg-type]
            interpretation=interpretation,
            claims=claims,
            uncertainty=uncertainty,
            missing_information=missing_information,
            limitations=list(response.limitations),
            provenance=provenance,
            failure=failure,
        )
        return AdapterOutcome(
            packet=packet,
            events=events,
            latency_ms=round((perf_counter() - started) * 1000, 3),
        )


def _western_failure_type(error_type: str | None) -> str:
    if error_type == "timeout":
        return "timeout"
    if error_type in {"rate_limit", "http_4xx", "http_5xx"}:
        return "http"
    if error_type in {"output_quality_rejection", "malformed_response"}:
        return "semantic"
    if error_type == "connectivity":
        return "provider"
    return "unexpected"


class WesternEvidenceAdapter:
    perspective = "western"

    def __init__(self, agent: WesternEvidenceAgent | None = None) -> None:
        self.agent = agent or WesternEvidenceAgent()

    async def collect(self, question: str) -> AdapterOutcome:
        started = perf_counter()
        if self.agent.provider.model != WESTERN_MODEL:
            raise PerspectiveAdapterError(
                "western",
                f"Western model configuration must be {WESTERN_MODEL} for this prototype.",
                failure_type="configuration",
            )
        try:
            response = await self.agent.consult(WesternConsultRequest(question=question, top_k=4))
        except Exception as exc:
            raise PerspectiveAdapterError(
                "western", "Western evidence pathway failed unexpectedly.", failure_type="unexpected"
            ) from exc
        return self._convert(response, round((perf_counter() - started) * 1000, 3))

    @staticmethod
    def _convert(response: WesternConsultResponse, latency_ms: float) -> AdapterOutcome:
        evidence_by_id = {item.chunk_id: item for item in response.retrieval}
        provenance = [
            ProvenanceRecord(
                source_id=item.source_id,
                chunk_id=item.chunk_id,
                title=item.article_title,
                source_url=item.source_url,
                source_type="PMC Open Access review",
                section=item.section,
                excerpt=item.text[:2000],
                identifier=item.doi or item.pmcid,
                license=item.license,
            )
            for item in response.retrieval
        ]
        claims: list[PerspectiveClaim] = [
            PerspectiveClaim(
                claim_id=f"western:evidence:{item.chunk_id}",
                claim_text=item.text[:2000],
                evidence_refs=[
                    EvidenceReference(
                        source_id=item.source_id,
                        chunk_id=item.chunk_id,
                        title=item.article_title,
                    )
                ],
                support_status="supported",
                claim_kind="source_excerpt",
            )
            for item in response.retrieval
        ]
        for claim in response.claims:
            refs = [
                EvidenceReference(
                    source_id=evidence_by_id[evidence_id].source_id,
                    chunk_id=evidence_id,
                    title=evidence_by_id[evidence_id].article_title,
                )
                for evidence_id in claim.evidence_ids
                if evidence_id in evidence_by_id
            ]
            # Phase 1B explicitly does not verify sentence-level claim support.
            claims.append(
                PerspectiveClaim(
                    claim_id=f"western:{claim.claim_id}",
                    claim_text=claim.text,
                    evidence_refs=refs,
                    support_status="insufficient" if not refs else "partially_supported",
                    claim_kind="derived_claim",
                )
            )

        events: list[ModelCallEvent] = []
        if response.trace is not None:
            token_usage = response.trace.token_usage
            for attempt in response.trace.provider_attempts:
                events.append(
                    ModelCallEvent(
                        role="western",
                        attempt=attempt.attempt,
                        provider=attempt.provider,
                        requested_model=WESTERN_MODEL,
                        reported_model=attempt.model if attempt.success else None,
                        success=attempt.success,
                        latency_ms=attempt.elapsed_ms,
                        http_status=attempt.http_status,
                        failure_class=(
                            None if attempt.success else _western_failure_type(attempt.error_type)
                        ),  # type: ignore[arg-type]
                        error_summary=attempt.error,
                        retry_performed=attempt.retry_performed,
                        prompt_tokens=token_usage.get("prompt_tokens", 0) if attempt.success else 0,
                        completion_tokens=token_usage.get("completion_tokens", 0) if attempt.success else 0,
                    )
                )

        successful_models = [
            attempt.model
            for attempt in (response.trace.provider_attempts if response.trace else [])
            if attempt.success
        ]
        model_mismatch = response.generation_mode == "llm" and (
            response.model != WESTERN_MODEL
            or any(model != WESTERN_MODEL for model in successful_models)
        )
        actual_mismatching_model = next(
            (
                model
                for model in [response.model, *successful_models]
                if model
                and model.casefold() not in {"none", "unknown"}
                and model != WESTERN_MODEL
            ),
            "unknown",
        )
        mismatch_detail = (
            f"Western provider-reported model {actual_mismatching_model!r} did not match {WESTERN_MODEL}."
            if model_mismatch
            else ""
        )
        if model_mismatch and events:
            mismatch_event_index = next(
                (
                    index
                    for index in range(len(events) - 1, -1, -1)
                    if events[index].reported_model and events[index].reported_model != WESTERN_MODEL
                ),
                len(events) - 1,
            )
            events[mismatch_event_index] = events[mismatch_event_index].model_copy(
                update={
                    "success": False,
                    "failure_class": "configuration",
                    "error_summary": mismatch_detail,
                    "reported_model": actual_mismatching_model,
                }
            )
        generation_failed = response.generation_mode == "generation_failure"
        failure = None
        if model_mismatch:
            # Retrieved source excerpts remain deterministic evidence. Any
            # claims emitted by the mismatched generation are never usable,
            # even if a future response supplies evidence IDs for them.
            claims = [claim for claim in claims if claim.claim_kind == "source_excerpt"]
            failure = PerspectiveFailure(
                role="western",
                failure_type="configuration",
                error_summary=mismatch_detail,
                retry_count=sum(1 for event in events if event.attempt == 2),
            )
        elif generation_failed:
            last = response.trace.provider_attempts[-1] if response.trace and response.trace.provider_attempts else None
            failure = PerspectiveFailure(
                role="western",
                failure_type=_western_failure_type(last.error_type if last else None),  # type: ignore[arg-type]
                error_summary=last.error if last and last.error else "Western generation failed.",
                http_status=last.http_status if last else None,
                retry_count=sum(1 for event in events if event.attempt == 2),
            )

        uncertainty = [response.support_signal_definition]
        uncertainty.extend(response.safety_flags)
        missing_information = []
        if response.abstention_reason:
            missing_information.append(response.abstention_reason)
        if not response.retrieval:
            missing_information.append("No Western evidence chunk was available for this routed question.")

        evidence_available = bool(response.retrieval)
        pathway_unavailable = generation_failed and not evidence_available
        packet = PerspectiveEvidencePacket(
            perspective="western",
            available=not pathway_unavailable,
            execution_status=(
                "unavailable"
                if pathway_unavailable
                else "degraded"
                if generation_failed or model_mismatch
                else "abstained"
                if response.abstained
                else "available"
            ),
            interpretation=(
                mismatch_detail
                if model_mismatch
                else "Western generated interpretation was unavailable; retrieved source-backed evidence is preserved."
                if generation_failed
                else response.answer or response.abstention_reason or "Western perspective produced no interpretation."
            ),
            claims=claims,
            uncertainty=uncertainty,
            missing_information=missing_information,
            limitations=list(response.limitations),
            provenance=provenance,
            failure=failure,
        )
        return AdapterOutcome(packet=packet, events=events, latency_ms=latency_ms)
