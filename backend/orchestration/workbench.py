from __future__ import annotations

import asyncio
import subprocess
import time
import uuid

from agents import QueryPlannerAgent, build_agents
from config import get_settings
from corpus import corpus_version
from judges import run_judges
from prompts import prompt_metadata
from providers import get_provider_bundle
from providers.local import DeterministicMockLLM
from providers.openai_compatible import ProviderUnavailable
from retrieval import RetrievalEngine
from schemas.research import (
    CompareRequest,
    CompareResponse,
    ConditionId,
    DebateTrace,
    ResearchCitation,
    ResearchMode,
    ResearchRequest,
    ResearchRunResult,
    RunState,
    RunTrace,
    StageTiming,
)

from .conditions import CONDITIONS
from .debate import debate


_RUN_CACHE: dict[str, ResearchRunResult] = {}


def get_run(run_id: str) -> ResearchRunResult | None:
    return _RUN_CACHE.get(run_id)


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _condition_mode(condition_id: ConditionId) -> ResearchMode:
    if condition_id == ConditionId.C1:
        return ResearchMode.SINGLE_RAG
    if condition_id == ConditionId.C0:
        return ResearchMode.SINGLE_RAG
    return ResearchMode.MULTI_AGENT


def _agent_ids(request: ResearchRequest, required: list[str], multi_agent: bool) -> list[str]:
    if not multi_agent:
        return ["single_rag"]
    selected = request.active_agents or required
    if len(selected) < 2:
        selected = list(dict.fromkeys([*selected, "syndrome", "constitution", "dietary_therapy", "lifestyle_yangsheng"]))[:3]
    return selected


def _synthesis(outputs, condition: dict, debate_trace: DebateTrace, judges) -> tuple[str, list[str], list[str], float]:
    claims = [(output, claim) for output in outputs for claim in output.claims]
    if condition["aggregation"] == "deterministic_weighted":
        claims.sort(key=lambda pair: pair[0].confidence * pair[1].confidence, reverse=True)
    supported_pairs = [(output, claim) for output, claim in claims if claim.evidence_ids]
    unique_pairs = []
    seen_claims: set[tuple[str, tuple[str, ...]]] = set()
    for output, claim in supported_pairs:
        key = (claim.text, tuple(claim.evidence_ids))
        if key in seen_claims:
            continue
        seen_claims.add(key)
        unique_pairs.append((output, claim))
    if condition["aggregation"] == "independent":
        parts = [f"{output.agent_name}: {claim.text} " + " ".join(f"[{evidence_id}]" for evidence_id in claim.evidence_ids) for output, claim in unique_pairs[:8]]
    else:
        parts = [claim.text + " " + " ".join(f"[{evidence_id}]" for evidence_id in claim.evidence_ids) for _, claim in unique_pairs[:6]]
    if not parts:
        return "The system abstained because no evidence-linked claim passed the selected condition.", [], [], 0.0
    answer = "TCM educational synthesis: " + " ".join(parts)
    agreements = debate_trace.agreements
    disagreements = debate_trace.disagreements
    if disagreements:
        answer += " Disclosed specialist difference: " + " ".join(disagreements)
    mean_agent = sum(output.confidence for output in outputs) / max(1, len(outputs))
    judge_cap = min((result.score for result in judges), default=0.65)
    confidence = min(0.65, mean_agent, judge_cap if judges else mean_agent)
    return answer, agreements, disagreements, round(confidence, 4)


def _metrics(result: ResearchRunResult) -> dict[str, float | int | None]:
    claims = [claim for output in result.agent_outputs for claim in output.claims]
    supported = [claim for claim in claims if claim.evidence_ids]
    citation_ids = {citation.evidence_id for citation in result.citations}
    evidence_ids = {item.chunk_id for item in result.retrieval}
    return {
        "retrieved_count": len(result.retrieval),
        "claim_count": len(claims),
        "citation_coverage": len(supported) / max(1, len(claims)),
        "evidence_claim_coverage": len(supported) / max(1, len(claims)),
        "unsupported_claim_rate": 1 - len(supported) / max(1, len(claims)),
        "provenance_valid_rate": len(citation_ids & evidence_ids) / max(1, len(citation_ids)),
        "agreement_count": len(result.agreements),
        "disagreement_count": len(result.disagreements),
        "judge_count": len(result.judge_outputs),
        "confidence": result.confidence,
        "abstained": int(result.abstained),
        "safety_flag_count": len(result.safety_flags),
        "latency_ms": result.trace.latency_ms if result.trace else None,
        "provider_calls": result.trace.provider_calls if result.trace else 0,
    }


class ResearchWorkbench:
    def __init__(self, *, force_mock: bool = False) -> None:
        self.settings = get_settings()
        self.providers = get_provider_bundle(force_mock=force_mock)
        self.retriever = RetrievalEngine()
        self.planner = QueryPlannerAgent()

    async def run(self, request: ResearchRequest) -> ResearchRunResult:
        started = time.perf_counter()
        run_id = f"run-{uuid.uuid4().hex[:16]}"
        condition = CONDITIONS[request.condition_id]
        timings: list[StageTiming] = []

        stage = time.perf_counter()
        plan = self.planner.plan(request.question)
        timings.append(StageTiming(stage="planning", latency_ms=round((time.perf_counter() - stage) * 1000)))

        if plan.scope_state != RunState.SUPPORTED:
            answer = {
                RunState.SAFETY_CRITICAL: "This question triggered safety-critical routing. Seek urgent professional or emergency help appropriate to your location; the TCM research system will not generate a treatment answer.",
                RunState.OUT_OF_SCOPE: "The question is outside this educational TCM research scope, so the system abstained.",
                RunState.INSUFFICIENT_INFORMATION: "The system needs more context before evidence-grounded retrieval and has abstained.",
                RunState.EVIDENCE_INSUFFICIENT: "The limited corpus does not cover this question well enough, so the system abstained.",
            }[plan.scope_state]
            result = self._abstention(run_id, request, condition, plan, answer, timings, started)
            _RUN_CACHE[run_id] = result
            return result

        evidence = []
        iterative_used = False
        if condition["retrieval"]:
            stage = time.perf_counter()
            evidence, iterative_used = await self.retriever.search_with_reflection(
                request.question,
                strategy=request.retrieval_strategy,
                top_k=request.top_k,
                topics=plan.subdomains,
                enabled=request.iterative_retrieval,
            )
            timings.append(StageTiming(stage="retrieval", latency_ms=round((time.perf_counter() - stage) * 1000)))

        if request.condition_id == ConditionId.C0:
            stage = time.perf_counter()
            provider_errors: list[str] = []
            try:
                generated = await self.providers.llm.generate(
                    system="Direct no-retrieval TCM research control. Do not prescribe or claim evidence support.",
                    prompt=request.question,
                    temperature=0.0,
                )
            except ProviderUnavailable as exc:
                provider_errors.append(str(exc))
                generated = await DeterministicMockLLM().generate(
                    system="Direct no-retrieval TCM research control. Do not prescribe or claim evidence support.",
                    prompt=request.question,
                    temperature=0.0,
                )
            timings.append(StageTiming(stage="generation", latency_ms=round((time.perf_counter() - stage) * 1000)))
            final_answer = "Direct no-retrieval control: " + generated.text
            outputs = []
            debate_trace = DebateTrace()
            judges = []
            citations: list[ResearchCitation] = []
            confidence = 0.2
            provider_calls = 1
            token_usage = {"prompt_tokens": generated.prompt_tokens, "completion_tokens": generated.completion_tokens}
            fallback_used = self.providers.mock_mode or generated.fallback
        else:
            provider_errors = []
            fallback_used = self.providers.mock_mode
            stage = time.perf_counter()
            ids = _agent_ids(request, plan.required_agents, bool(condition["multi_agent"]))
            agents = build_agents(ids)
            outputs = await asyncio.gather(*[
                agent.answer(request.question, plan.language, evidence, provider=self.providers.llm.name, model=self.providers.llm.model)
                for agent in agents
            ])
            timings.append(StageTiming(stage="agents", latency_ms=round((time.perf_counter() - stage) * 1000)))
            stage = time.perf_counter()
            debate_trace = debate(outputs, request.debate_rounds if condition["debate"] else 0)
            timings.append(StageTiming(stage="debate", latency_ms=round((time.perf_counter() - stage) * 1000)))
            stage = time.perf_counter()
            judges = run_judges(outputs, evidence, debate_trace, request.active_judges) if condition["judges"] else []
            timings.append(StageTiming(stage="judges", latency_ms=round((time.perf_counter() - stage) * 1000)))
            final_answer, _, _, confidence = _synthesis(outputs, condition, debate_trace, judges)
            citations = list({(item.evidence_id, item.source_id): item for output in outputs for item in output.citations}.values())
            provider_calls = 0
            token_usage = {}

        versions, hashes = prompt_metadata()
        limitations = [
            "Research prototype only; no clinical correctness or safety conclusion is established.",
            "The corpus is provisional and not expert validated; source types are not treated as equal evidence strength.",
            "LLM-as-a-Judge scores are experimental signals, not objective ground truth.",
            "RQ3-TCM-within-paradigm is a proxy and does not answer cross-paradigm conflict.",
            "RQ6 requires actual human evaluation data and is not answered by automated metrics.",
        ]
        safety_flags = list(dict.fromkeys(flag for output in outputs for flag in output.safety_flags))
        total_latency = round((time.perf_counter() - started) * 1000)
        trace = RunTrace(
            run_id=run_id,
            git_commit=_git_commit(),
            corpus_version=corpus_version(),
            condition_id=request.condition_id,
            experiment_config=request.model_dump(mode="json", exclude={"question", "context"}),
            provider=self.providers.llm.name,
            model=self.providers.llm.model,
            embedding_model=self.providers.embedding.model,
            reranker=self.providers.rerank.model if request.retrieval_strategy.value == "R3" else "none",
            prompt_versions=versions,
            prompt_hashes=hashes,
            top_k=request.top_k,
            random_seed=request.random_seed,
            active_agents=[output.agent_id for output in outputs],
            active_judges=[item.judge_id for item in judges],
            retrieval_strategy=request.retrieval_strategy,
            retrieved_evidence_ids=[item.chunk_id for item in evidence],
            agent_outputs=[output.model_dump(mode="json") for output in outputs],
            judge_outputs=[item.model_dump(mode="json") for item in judges],
            final_answer=final_answer,
            confidence=confidence,
            abstention=False,
            latency_ms=total_latency,
            stage_timings=timings,
            token_usage=token_usage,
            provider_calls=provider_calls,
            provider_errors=provider_errors,
            fallback_usage=fallback_used,
            iterative_retrieval_used=iterative_used,
            raw_query_stored=False,
        )
        result = ResearchRunResult(
            run_id=run_id,
            mode=_condition_mode(request.condition_id),
            condition_id=request.condition_id,
            condition_name=condition["name"],
            scope_state=RunState.SUPPORTED,
            planner=plan,
            retrieval=evidence,
            agent_outputs=outputs,
            debate=debate_trace,
            judge_outputs=judges,
            final_answer=final_answer,
            citations=citations,
            agreements=debate_trace.agreements,
            disagreements=debate_trace.disagreements,
            unresolved_conflicts=debate_trace.unresolved_conflicts,
            limitations=limitations,
            safety_flags=safety_flags,
            confidence=confidence,
            trace=trace if request.include_trace else None,
            mock_mode=fallback_used,
        )
        result.metrics = _metrics(result)
        _RUN_CACHE[run_id] = result
        return result

    def _abstention(self, run_id, request, condition, plan, answer, timings, started) -> ResearchRunResult:
        trace = RunTrace(
            run_id=run_id,
            git_commit=_git_commit(),
            corpus_version=corpus_version(),
            condition_id=request.condition_id,
            experiment_config=request.model_dump(mode="json", exclude={"question", "context"}),
            provider=self.providers.llm.name,
            model=self.providers.llm.model,
            active_agents=[],
            active_judges=[],
            retrieval_strategy=request.retrieval_strategy,
            final_answer=answer,
            abstention=True,
            latency_ms=round((time.perf_counter() - started) * 1000),
            stage_timings=timings,
            fallback_usage=self.providers.mock_mode,
            raw_query_stored=False,
        )
        return ResearchRunResult(
            run_id=run_id,
            mode=_condition_mode(request.condition_id),
            condition_id=request.condition_id,
            condition_name=condition["name"],
            scope_state=plan.scope_state,
            planner=plan,
            final_answer=answer,
            limitations=["The system abstained under explicit scope, evidence, or safety routing."],
            safety_flags=["safety_critical"] if plan.safety_critical else [],
            confidence=0.0,
            abstained=True,
            abstention_reason=plan.scope_state.value,
            trace=trace if request.include_trace else None,
            mock_mode=self.providers.mock_mode,
            metrics={"abstained": 1, "latency_ms": trace.latency_ms},
        )

    async def compare(self, request: CompareRequest) -> CompareResponse:
        results = []
        for condition in request.conditions:
            results.append(await self.run(ResearchRequest(
                question=request.question,
                context=request.context,
                condition_id=condition,
                retrieval_strategy=request.retrieval_strategy,
                active_agents=request.active_agents,
                active_judges=request.active_judges,
                top_k=request.top_k,
                iterative_retrieval=request.iterative_retrieval,
                random_seed=request.random_seed,
            )))
        return CompareResponse(
            comparison_id=f"cmp-{uuid.uuid4().hex[:12]}",
            question=request.question,
            results=results,
            metric_comparison={result.condition_id.value: result.metrics for result in results},
            limitations=[
                "Condition differences are descriptive until evaluated on an expert-reviewed dataset.",
                "A TCM-only comparison cannot answer cross-paradigm RQ3.",
            ],
        )
