from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from tcm.agent import consult
from tcm.schemas import TCMConsultRequest, TCMConsultResponse

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

app = FastAPI(
    title="MediConsensus TCM-RAG API",
    version="0.2.0",
    description="Research-only, evidence-gated TCM retrieval and answer-generation prototype.",
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
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "TCM-RAG",
        "version": app.version,
        "port_env": os.getenv("PORT", "not_set"),
    }


@app.post("/api/tcm/consult", response_model=TCMConsultResponse)
async def tcm_consult(request: TCMConsultRequest) -> TCMConsultResponse:
    return await consult(request)
