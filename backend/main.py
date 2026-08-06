from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from tcm.agent import consult
from tcm.schemas import TCMConsultRequest, TCMConsultResponse
from consensus.adapters.base import AdapterError, AdapterUnavailableError, FixtureDisabledError
from consensus.orchestrator import ConsensusDisabledError, ConsensusOrchestrator, consensus_enabled
from consensus.schemas import ConsensusConsultRequest, ConsensusError, ConsensusResponse

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

app = FastAPI(
    title="MediConsensus TCM-RAG API",
    version="0.2.0",
    description="Research-only TCM-RAG plus model-agnostic consensus-orchestration pilot.",
)

def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500")
    return [item.strip() for item in raw.split(",") if item.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    question_error = next((item for item in errors if "question" in item.get("loc", ())), None)
    detail = "Please enter a health question of at least 3 characters." if question_error else "Please check the submitted fields and try again."
    return JSONResponse(status_code=422, content={"detail": detail, "errors": errors})


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "TCM-RAG",
        "version": app.version,
        "port_env": os.getenv("PORT", "not_set"),
        "consensus_enabled": consensus_enabled(),
        "west_fixture_enabled": os.getenv("ALLOW_WEST_FIXTURE", "false").strip().casefold() in {"1", "true", "yes", "on"},
    }


@app.post("/api/tcm/consult", response_model=TCMConsultResponse)
async def tcm_consult(request: TCMConsultRequest) -> TCMConsultResponse:
    return await consult(request)


@app.post(
    "/api/consensus/consult",
    response_model=ConsensusResponse,
    responses={
        403: {"model": ConsensusError, "description": "Fixture use is disabled."},
        503: {"model": ConsensusError, "description": "Consensus or an external adapter is unavailable."},
    },
    summary="Run the experimental MediConsensus orchestration pilot",
    description=(
        "Combines normalized domain-agent outputs with concatenate, deterministic weighted, debate, "
        "or debate-plus-judge strategies. Western fixtures are synthetic and disabled by default."
    ),
)
async def consensus_consult(request: ConsensusConsultRequest) -> ConsensusResponse:
    try:
        return await ConsensusOrchestrator().run(request)
    except FixtureDisabledError as exc:
        raise HTTPException(status_code=403, detail={"code": "fixture_disabled", "message": str(exc)}) from None
    except (AdapterUnavailableError, ConsensusDisabledError) as exc:
        raise HTTPException(status_code=503, detail={"code": "service_unavailable", "message": str(exc)}) from None
    except AdapterError:
        raise HTTPException(
            status_code=503,
            detail={"code": "adapter_failure", "message": "A domain adapter failed safely."},
        ) from None
