from __future__ import annotations

import re
from time import perf_counter
from typing import Any

from providers import build_llm_provider
from providers.base import LLMProvider
from providers.openai_compatible import ProviderUnavailable
from schemas.research import ProviderAttempt
from tcm.safety import check_emergency

from .corpus import WesternRuntimeCorpus, western_corpus_stats
from .retrieval import WesternRetriever
from .routing import route_western_scope
from .schemas import (
    WesternCitation,
    WesternClaim,
    WesternConsultRequest,
    WesternConsultResponse,
    WesternRetrievalEvidence,
    WesternTrace,
)


WESTERN_MODEL = "Qwen/Qwen3-8B"
WESTERN_TIMEOUT_SECONDS = 120.0
WESTERN_MAX_TOKENS = 256
WESTERN_EVIDENCE_EXCERPT_CHARS = 1000
WESTERN_MAX_ANSWER_WORDS = 180
PILOT_LIMITATION = (
    "Coverage is limited to the four Phase 1B pilot topics: cough, dyspepsia/digestive symptoms, "
    "headache/migraine, and constipation."
)
STANDARD_LIMITATIONS = [
    PILOT_LIMITATION,
    "The PMC Open Access pilot is not clinically comprehensive or clinically validated.",
    "Source-reported evidence does not establish clinical certainty; this educational research output is not medical advice.",
]
SYSTEM_PROMPT = (
    "You are the single Western Evidence Agent in a research prototype. Use ONLY the supplied evidence. "
    "Write a concise educational answer of approximately 100 to 140 words. Do not diagnose the user, prescribe treatment, "
    "recommend individualized dosing, or invent facts absent from the evidence. Preserve uncertainty and distinguish "
    "source-reported evidence from clinical certainty. Do not claim that this pilot corpus is clinically comprehensive. "
    "State that the automated output is not medical advice. Return only the educational answer in plain text. "
    "Do not output citations, evidence labels, PMCID, DOI, URLs, source IDs, internal identifiers, or Markdown references."
)

_PROVENANCE_PATTERNS = (
    re.compile(r"https?://\S+", re.IGNORECASE),
    re.compile(r"\b(?:doi\s*:\s*)?10\.\d{4,9}/[-._;()/:a-z0-9]+", re.IGNORECASE),
    re.compile(r"\bPMC\d+\b", re.IGNORECASE),
    re.compile(r"\bwest-[a-z0-9-]+\b", re.IGNORECASE),
    re.compile(r"\[(?:evidence\s+)?[a-z0-9]+\]", re.IGNORECASE),
)


def _safe_provider_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, ProviderUnavailable):
        return exc.error_type, str(exc)
    return "unknown", "Unexpected provider failure"


def _strip_provenance_like_text(value: str) -> str:
    cleaned = value
    for pattern in _PROVENANCE_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _validated_answer(value: str) -> str:
    answer = _strip_provenance_like_text(value)
    if not answer:
        raise ProviderUnavailable("Provider returned an empty answer", error_type="output_quality_rejection")
    if len(answer.split()) > WESTERN_MAX_ANSWER_WORDS:
        raise ProviderUnavailable("Provider answer exceeded the Western word limit", error_type="output_quality_rejection")
    sentences = [
        re.sub(r"\W+", " ", part.casefold()).strip()
        for part in re.split(r"(?<=[.!?])\s+", answer)
        if part.strip()
    ]
    repeated = {sentence for sentence in sentences if sentence and sentences.count(sentence) >= 3}
    words = re.findall(r"[a-z0-9]+", answer.casefold())
    unusually_repetitive = len(words) >= 20 and len(set(words)) / len(words) < 0.2
    if repeated or unusually_repetitive:
        raise ProviderUnavailable("Provider answer was malformed or repetitive", error_type="output_quality_rejection")
    return answer


def _generation_prompt(question: str, topic: str, evidence: list[WesternRetrievalEvidence]) -> str:
    blocks = []
    for index, item in enumerate(evidence):
        label = chr(ord("A") + index)
        excerpt = _strip_provenance_like_text(item.text[:WESTERN_EVIDENCE_EXCERPT_CHARS])
        blocks.append(
            f"Evidence {label}:\n"
            f"Title: {_strip_provenance_like_text(item.article_title)}\n"
            f"Section: {_strip_provenance_like_text(item.section)}\n"
            f"Excerpt: {excerpt}"
        )
    return "\n\n".join((
        f"Question: {question}",
        f"Routed pilot topic: {topic}",
        *blocks,
    ))


def _citations(evidence: list[WesternRetrievalEvidence]) -> list[WesternCitation]:
    return [
        WesternCitation(
            evidence_id=item.chunk_id,
            source_id=item.source_id,
            article_title=item.article_title,
            section=item.section,
            pmcid=item.pmcid,
            doi=item.doi,
            source_url=item.source_url,
            license=item.license,
            provenance_valid=True,
        )
        for item in evidence
    ]


class WesternEvidenceAgent:
    def __init__(
        self,
        *,
        provider: LLMProvider | None = None,
        retriever: WesternRetriever | None = None,
        corpus: WesternRuntimeCorpus | None = None,
    ) -> None:
        self.provider = provider or build_llm_provider(WESTERN_MODEL, timeout_override=WESTERN_TIMEOUT_SECONDS)
        self.retriever = retriever or WesternRetriever(corpus=corpus)

    def _trace(
        self,
        evidence: list[WesternRetrievalEvidence],
        attempts: list[ProviderAttempt],
        *,
        token_usage: dict[str, int] | None = None,
    ) -> WesternTrace:
        stats = western_corpus_stats(self.retriever.corpus.root)
        return WesternTrace(
            corpus_name=str(stats["corpus_name"]),
            corpus_version=str(stats["corpus_version"]),
            corpus_chunk_count=int(stats["chunk_count"]),
            corpus_source_count=int(stats["source_count"]),
            retrieved_evidence_ids=[item.chunk_id for item in evidence],
            provider_attempts=attempts,
            fallback_usage=False,
            token_usage=token_usage or {},
        )

    async def consult(self, request: WesternConsultRequest) -> WesternConsultResponse:
        started = perf_counter()
        decision = route_western_scope(request.question)
        if not decision.supported:
            return WesternConsultResponse(
                question=request.question,
                topic=None,
                limitations=[PILOT_LIMITATION],
                abstained=True,
                abstention_reason=decision.reason,
                generation_mode="scope_abstention",
                latency_ms=round((perf_counter() - started) * 1000),
            )

        topic = decision.topic
        assert topic is not None
        safety = check_emergency(request.question)
        if safety.urgent:
            return WesternConsultResponse(
                question=request.question,
                topic=topic,
                limitations=STANDARD_LIMITATIONS,
                safety_flags=[f"Urgent safety signal: {safety.reason}"],
                abstained=True,
                abstention_reason="The question contains a possible urgent safety signal; seek immediate qualified medical help.",
                generation_mode="safety_abstention",
                latency_ms=round((perf_counter() - started) * 1000),
            )

        evidence = await self.retriever.search(request.question, topic, top_k=request.top_k)
        if not evidence:
            return WesternConsultResponse(
                question=request.question,
                topic=topic,
                retrieval=[],
                limitations=STANDARD_LIMITATIONS,
                abstained=True,
                abstention_reason="No evidence was retrieved from the routed Western pilot topic.",
                generation_mode="retrieval_abstention",
                latency_ms=round((perf_counter() - started) * 1000),
                trace=self._trace([], []),
            )

        prompt = _generation_prompt(request.question, topic.value, evidence)
        attempt_started = perf_counter()
        try:
            generated = await self.provider.generate(
                system=SYSTEM_PROMPT,
                prompt=prompt,
                temperature=0.0,
                max_tokens=WESTERN_MAX_TOKENS,
            )
            answer = _validated_answer(generated.text)
        except Exception as exc:
            error_type, error_message = _safe_provider_error(exc)
            attempt = ProviderAttempt(
                attempt=1,
                provider=self.provider.name,
                model=self.provider.model,
                elapsed_ms=round((perf_counter() - attempt_started) * 1000),
                success=False,
                http_status=exc.http_status if isinstance(exc, ProviderUnavailable) else None,
                error_type=error_type,
                error=error_message,
                retry_performed=False,
            )
            return WesternConsultResponse(
                question=request.question,
                topic=topic,
                retrieval=evidence,
                citations=_citations(evidence),
                limitations=STANDARD_LIMITATIONS,
                abstained=True,
                abstention_reason="Western answer generation failed; retrieved evidence is preserved for inspection.",
                provider=self.provider.name,
                model=self.provider.model,
                generation_mode="generation_failure",
                latency_ms=round((perf_counter() - started) * 1000),
                trace=self._trace(evidence, [attempt]),
            )

        attempt = ProviderAttempt(
            attempt=1,
            provider=generated.provider,
            model=generated.model,
            elapsed_ms=round((perf_counter() - attempt_started) * 1000),
            success=True,
            finish_reason=generated.finish_reason,
            retry_performed=False,
        )
        citations = _citations(evidence)
        return WesternConsultResponse(
            question=request.question,
            topic=topic,
            answer=answer,
            retrieval=evidence,
            claims=[WesternClaim(claim_id="western-answer-1", text=answer, evidence_ids=[])],
            citations=citations,
            limitations=STANDARD_LIMITATIONS,
            safety_flags=[],
            evidence_support_signal=0.0,
            abstained=False,
            provider=generated.provider,
            model=generated.model,
            generation_mode="llm",
            latency_ms=round((perf_counter() - started) * 1000),
            trace=self._trace(
                evidence,
                [attempt],
                token_usage={
                    "prompt_tokens": generated.prompt_tokens,
                    "completion_tokens": generated.completion_tokens,
                },
            ),
        )
