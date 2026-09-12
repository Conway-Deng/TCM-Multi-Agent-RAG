from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
import httpx
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from agents import AGENT_REGISTRY
from config import get_settings
from corpus import corpus_stats
from judges import JUDGE_REGISTRY
from formal_experiments import formal_jobs, public_registry
from formal_experiments.jobs import custom_jobs
from formal_experiments.schemas import CustomRunRequest, CustomRunStatus, FormalRunRequest, FormalRunStatus
from orchestration import CONDITION_REGISTRY, ResearchWorkbench, get_run
from retrieval import RETRIEVER_REGISTRY, RetrievalEngine
from schemas.research import CompareRequest, CompareResponse, ResearchRequest, ResearchRunResult, RetrievalItem, RetrievalStrategy
from tcm.agent import OpenAICompatibleClient, consult
from tcm.schemas import TCMConsultRequest, TCMConsultResponse

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))
settings = get_settings()


def _control_plane_only() -> bool:
    return os.getenv("RENDER_API_CONTROL_PLANE_ONLY", "").strip().casefold() in {"1", "true", "yes", "on"}


async def _wake_worker() -> bool:
    url = os.getenv("FORMAL_WORKER_PUBLIC_URL", "").strip().rstrip("/")
    if not url:
        return False
    token = os.getenv("FORMAL_WORKER_WAKE_TOKEN", "").strip()
    headers = {"X-Worker-Wake-Token": token} if token else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{url}/wake", headers=headers)
            response.raise_for_status()
        return True
    except httpx.HTTPError:
        # The durable job remains queued. The periodic heartbeat or the
        # worker's next cold start can claim it safely.
        return False


async def _worker_keepalive() -> None:
    interval = max(120, min(300, int(os.getenv("FORMAL_WORKER_HEARTBEAT_SECONDS", "180"))))
    while True:
        await asyncio.sleep(interval)
        if formal_jobs.store.active_count() > 0:
            await _wake_worker()


@asynccontextmanager
async def lifespan(_: FastAPI):
    keepalive_task = None
    if _control_plane_only():
        formal_jobs.store.initialize()
        keepalive_task = asyncio.create_task(_worker_keepalive())
    else:
        # Local execution mode validates its selected corpus before accepting traffic.
        corpus_stats()
    try:
        yield
    finally:
        if keepalive_task is not None:
            keepalive_task.cancel()
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass
        formal_jobs.store.close()
        custom_jobs.store.close()
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
    if _control_plane_only():
        return {
            "status": "ok",
            "service": "TCM Multi-Agent RAG control plane",
            "version": app.version,
            "scope": "tcm_only",
            "runtime_profile": "cloud_control_plane",
            "corpus_mode": "worker_only",
            "corpus_name": "Loaded by experiment worker only",
            "corpus_version": "worker_managed",
            "corpus_chunk_count": 0,
            "corpus_source_count": 0,
            "active_corpus": "not_loaded_in_api",
            "provider_mode": "worker_managed",
            "provider_configured": "worker_managed",
            "provider_ready": bool(os.getenv("FORMAL_WORKER_PUBLIC_URL", "").strip()),
            "llm_execution_enabled": False,
            "mock_mode": False,
            "research_mode": True,
            "strict_medical_safety": settings.strict_medical_safety,
        }
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
    if _control_plane_only():
        raise HTTPException(status_code=503, detail="Direct execution is disabled on the cloud control plane.")
    return await consult(request)


@app.post("/api/tcm/multi-agent/consult", response_model=ResearchRunResult, summary="Run a TCM specialist multi-agent condition")
async def multi_agent_consult(request: ResearchRequest) -> ResearchRunResult:
    if _control_plane_only():
        raise HTTPException(status_code=503, detail="Queue a Custom experiment for the cloud worker.")
    return await ResearchWorkbench().run(request)


@app.post("/api/research/run", response_model=ResearchRunResult, summary="Run one controlled research condition")
async def research_run(request: ResearchRequest) -> ResearchRunResult:
    if _control_plane_only():
        raise HTTPException(status_code=503, detail="Queue a Custom experiment for the cloud worker.")
    return await ResearchWorkbench().run(request)


@app.post("/api/research/compare", response_model=CompareResponse, summary="Compare multiple conditions on the same question")
async def research_compare(request: CompareRequest) -> CompareResponse:
    if _control_plane_only():
        raise HTTPException(status_code=503, detail="Direct comparison is disabled on the cloud control plane.")
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
    if _control_plane_only():
        raise HTTPException(status_code=503, detail="Retrieval executes only on the cloud experiment worker.")
    return await RetrievalEngine().search(request.query, strategy=request.retrieval_strategy, top_k=request.top_k, topics=request.topics)


@app.get("/api/corpus/stats")
async def api_corpus_stats() -> dict[str, object]:
    if _control_plane_only():
        return {
            "corpus_name": "Loaded by experiment worker only", "corpus_version": "worker_managed",
            "chunk_count": 0, "source_count": 0, "corpus_mode": "worker_only",
            "active_corpus": "not_loaded_in_api", "runtime_profile": "cloud_control_plane",
        }
    return corpus_stats()


@app.get("/api/formal-experiments", summary="List paper-locked experiment protocols")
async def formal_experiments() -> list[dict]:
    return public_registry()


@app.post("/api/formal-runs", response_model=FormalRunStatus, status_code=202, summary="Start a new replay of a frozen paper protocol")
async def create_formal_run(request: FormalRunRequest) -> dict:
    try:
        status = formal_jobs.create(request)
        await _wake_worker()
        return status
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/formal-runs/{run_id}", response_model=FormalRunStatus, summary="Read replay job status")
async def formal_run_status(run_id: str) -> dict:
    try:
        return formal_jobs.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Formal replay run not found.") from exc


@app.get("/api/formal-runs/{run_id}/results", summary="Read replay results without historical paper outputs")
async def formal_run_results(run_id: str, after: int = 0) -> dict:
    try:
        return formal_jobs.results(run_id, after=max(0, after))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Formal replay run not found.") from exc


@app.post("/api/formal-runs/{run_id}/stop", response_model=FormalRunStatus, status_code=202, summary="Request a cooperative stop at the next safe execution boundary")
async def stop_formal_run(run_id: str) -> dict:
    try:
        status = formal_jobs.stop(run_id)
        if status["status"] == "stop_requested":
            await _wake_worker()
        return status
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Formal replay run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/formal-runs/{run_id}/resume", response_model=FormalRunStatus, status_code=202, summary="Resume a failed replay from its isolated output directory")
async def resume_formal_run(run_id: str) -> dict:
    try:
        status = formal_jobs.resume(run_id)
        await _wake_worker()
        return status
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Formal replay run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/formal-runs/{run_id}/files/{file_path:path}", summary="Download a generated replay artifact")
async def formal_run_file(run_id: str, file_path: str):
    try:
        media_type, content = formal_jobs.file(run_id, file_path)
        filename = Path(file_path).name.replace('"', "")
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Formal replay run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/custom-runs", response_model=CustomRunStatus, status_code=202, summary="Queue an exploratory Custom Workbench batch")
async def create_custom_run(request: CustomRunRequest) -> dict:
    status = custom_jobs.create(request)
    await _wake_worker()
    return status


@app.get("/api/custom-runs/{run_id}", response_model=CustomRunStatus, summary="Read Custom batch status")
async def custom_run_status(run_id: str) -> dict:
    try:
        return custom_jobs.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Custom run not found.") from exc


@app.get("/api/custom-runs/{run_id}/results", summary="Read incremental Custom batch results")
async def custom_run_results(run_id: str, after: int = 0) -> dict:
    try:
        return custom_jobs.results(run_id, after=max(0, after))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Custom run not found.") from exc


@app.post("/api/custom-runs/{run_id}/stop", response_model=CustomRunStatus, status_code=202, summary="Request a cooperative stop after the active question")
async def stop_custom_run(run_id: str) -> dict:
    try:
        status = custom_jobs.stop(run_id)
        if status["status"] == "stop_requested":
            await _wake_worker()
        return status
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Custom run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/custom-runs/{run_id}/files/{file_path:path}", summary="Download a Custom batch artifact")
async def custom_run_file(run_id: str, file_path: str):
    try:
        media_type, content = custom_jobs.file(run_id, file_path)
        filename = Path(file_path).name.replace('"', "")
        return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Custom run file not found.") from exc
