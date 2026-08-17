from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agents import AGENT_REGISTRY
from config import get_settings
from corpus import corpus_stats
from judges import JUDGE_REGISTRY
from orchestration import CONDITION_REGISTRY, ResearchWorkbench, get_run
from retrieval import RETRIEVER_REGISTRY, RetrievalEngine
from schemas.research import CompareRequest, CompareResponse, ResearchRequest, ResearchRunResult, RetrievalItem, RetrievalStrategy
from tcm.agent import OpenAICompatibleClient, consult
from tcm.schemas import TCMConsultRequest, TCMConsultResponse

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # In required local-research mode this loads and validates corpus selection
    # before the server accepts traffic. Missing artifacts fail startup loudly.
    corpus_stats()
    yield
    await OpenAICompatibleClient.close_shared_http_client()


app = FastAPI(
    title="TCM Multi-Agent RAG Research Workbench",
    version="1.0.0",
    description=(
        "TCM-only research platform for retrieval, specialist-agent, debate, LLM-as-a-Judge, "
        "safety, provenance, and reproducible experiment studies. Educational research use only."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
    expose_headers=["Server-Timing"],
)


@app.middleware("http")
async def add_server_timing(request: Request, call_next):
    started = perf_counter()
    response = await call_next(request)
    response.headers["Server-Timing"] = f"app;dur={(perf_counter() - started) * 1000:.3f}"
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "Please check the submitted research fields.", "errors": exc.errors()})


@app.get("/health")
async def health() -> dict[str, object]:
    corpus = corpus_stats()
    return {
        "status": "ok",
        "service": "TCM Multi-Agent RAG Research Workbench",
        "version": app.version,
        "scope": "tcm_only",
        "provider_mode": settings.provider_mode,
        "provider_configured": settings.llm_provider,
        "provider_ready": settings.provider_mode != "mock",
        "llm_execution_enabled": settings.research_real_llm_enabled and settings.provider_mode != "mock",
        "mock_mode": settings.provider_mode == "mock",
        "research_mode": settings.research_mode,
        "strict_medical_safety": settings.strict_medical_safety,
        "corpus_name": corpus["corpus_name"],
        "corpus_version": corpus["corpus_version"],
        "corpus_chunk_count": corpus["chunk_count"],
        "corpus_source_count": corpus["source_count"],
        "corpus_mode": corpus["corpus_mode"],
        "active_corpus": corpus["active_corpus"],
        "runtime_profile": corpus["runtime_profile"],
    }


@app.post("/api/tcm/consult", response_model=TCMConsultResponse, summary="Run the conventional TCM Single RAG interface")
async def tcm_consult(request: TCMConsultRequest) -> TCMConsultResponse:
    return await consult(request)


@app.post("/api/tcm/multi-agent/consult", response_model=ResearchRunResult, summary="Run a TCM specialist multi-agent condition")
async def multi_agent_consult(request: ResearchRequest) -> ResearchRunResult:
    return await ResearchWorkbench().run(request)


@app.post("/api/research/run", response_model=ResearchRunResult, summary="Run one controlled research condition")
async def research_run(request: ResearchRequest) -> ResearchRunResult:
    return await ResearchWorkbench().run(request)


@app.post("/api/research/compare", response_model=CompareResponse, summary="Compare multiple conditions on the same question")
async def research_compare(request: CompareRequest) -> CompareResponse:
    return await ResearchWorkbench().compare(request)


@app.get("/api/research/conditions")
async def research_conditions() -> list[dict]:
    return CONDITION_REGISTRY


@app.get("/api/research/agents")
async def research_agents() -> list[dict]:
    return AGENT_REGISTRY


@app.get("/api/research/retrievers")
async def research_retrievers() -> list[dict]:
    return RETRIEVER_REGISTRY


@app.get("/api/research/judges")
async def research_judges() -> list[dict]:
    return JUDGE_REGISTRY


@app.get("/api/research/runs/{run_id}", response_model=ResearchRunResult)
async def research_run_by_id(run_id: str) -> ResearchRunResult:
    result = get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Research run not found in this process.")
    return result


@app.get("/api/research/runs/{run_id}/metrics")
async def research_run_metrics(run_id: str) -> dict[str, float | int | None]:
    result = get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Research run not found in this process.")
    return result.metrics


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.R2
    top_k: int = Field(default=4, ge=1, le=20)
    topics: list[str] = Field(default_factory=list)


@app.post("/api/retrieval/search", response_model=list[RetrievalItem], summary="Inspect a retrieval strategy directly")
async def retrieval_search(request: RetrievalSearchRequest) -> list[RetrievalItem]:
    return await RetrievalEngine().search(request.query, strategy=request.retrieval_strategy, top_k=request.top_k, topics=request.topics)


@app.get("/api/corpus/stats")
async def api_corpus_stats() -> dict[str, object]:
    return corpus_stats()
