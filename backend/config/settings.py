from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)


class Settings(BaseModel):
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.siliconflow.cn/v1"
    llm_model: str = "Qwen/Qwen3-8B"
    qwen_model: str = "Qwen/Qwen3-8B"
    glm_model: str = "THUDM/GLM-Z1-9B-0414"
    deepseek_model: str = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
    consensus_model: str = "Qwen/Qwen3-8B"
    llm_timeout_seconds: float = 45.0
    deepseek_timeout_seconds: float = 90.0
    llm_max_tokens: int = 1400
    embedding_provider: str = "local"
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "local-hash-embedding-v1"
    rerank_provider: str = "local"
    rerank_api_key: str = ""
    rerank_base_url: str = "https://api.siliconflow.cn/v1"
    rerank_model: str = "local-overlap-reranker-v1"
    vector_store_provider: str = "local"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "tcm-research"
    research_mode: bool = True
    research_real_llm_enabled: bool = False
    research_max_parallel_calls: int = Field(default=4, ge=1, le=32)
    research_repeat_count: int = Field(default=1, ge=1, le=100)
    research_random_seed: int = 20260815
    research_store_raw_query: bool = False
    research_results_dir: Path = Path("research/results")
    strict_medical_safety: bool = True
    allow_unreviewed_sources: bool = False
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5500", "http://127.0.0.1:5500"])

    @property
    def provider_mode(self) -> str:
        if self.llm_provider == "mock" or not self.llm_api_key:
            return "mock"
        return self.llm_provider


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",") if item.strip()]
    legacy_model = os.getenv("LLM_MODEL", "Qwen/Qwen3-8B").strip() or "Qwen/Qwen3-8B"
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "mock").strip().casefold() or "mock",
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/"),
        llm_model=legacy_model,
        qwen_model=os.getenv("QWEN_MODEL", "").strip() or legacy_model,
        glm_model=os.getenv("GLM_MODEL", "THUDM/GLM-Z1-9B-0414").strip() or "THUDM/GLM-Z1-9B-0414",
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B").strip() or "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
        consensus_model=os.getenv("CONSENSUS_MODEL", "Qwen/Qwen3-8B").strip() or "Qwen/Qwen3-8B",
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "45")),
        deepseek_timeout_seconds=float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "90")),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1400")),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "local").strip().casefold() or "local",
        embedding_api_key=os.getenv("EMBEDDING_API_KEY", "").strip(),
        embedding_base_url=os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "local-hash-embedding-v1").strip(),
        rerank_provider=os.getenv("RERANK_PROVIDER", "local").strip().casefold() or "local",
        rerank_api_key=os.getenv("RERANK_API_KEY", "").strip(),
        rerank_base_url=os.getenv("RERANK_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/"),
        rerank_model=os.getenv("RERANK_MODEL", "local-overlap-reranker-v1").strip(),
        vector_store_provider=os.getenv("VECTOR_STORE_PROVIDER", "local").strip().casefold() or "local",
        qdrant_url=os.getenv("QDRANT_URL", "").strip(),
        qdrant_api_key=os.getenv("QDRANT_API_KEY", "").strip(),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "tcm-research").strip(),
        research_mode=_bool("RESEARCH_MODE", True),
        research_real_llm_enabled=_bool("RESEARCH_REAL_LLM_ENABLED", False),
        research_max_parallel_calls=int(os.getenv("RESEARCH_MAX_PARALLEL_CALLS", "4")),
        research_repeat_count=int(os.getenv("RESEARCH_REPEAT_COUNT", "1")),
        research_random_seed=int(os.getenv("RESEARCH_RANDOM_SEED", "20260815")),
        research_store_raw_query=_bool("RESEARCH_STORE_RAW_QUERY", False),
        research_results_dir=Path(os.getenv("RESEARCH_RESULTS_DIR", "research/results")),
        strict_medical_safety=_bool("STRICT_MEDICAL_SAFETY", True),
        allow_unreviewed_sources=_bool("ALLOW_UNREVIEWED_SOURCES", False),
        port=int(os.getenv("PORT", "8000")),
        cors_origins=origins,
    )
