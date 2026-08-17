from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Any

import httpx

from tcm.agent import LLMProviderError, OpenAICompatibleClient, _parse_json_object

from .prompts import ROLE_PROMPTS
from .schemas import ModelTraceEntry


ROLE_MODEL_ENV = {
    "debate": "CONSENSUS_DEBATE_MODEL",
    "evidence_judge": "CONSENSUS_EVIDENCE_JUDGE_MODEL",
    "safety_judge": "CONSENSUS_SAFETY_JUDGE_MODEL",
    "conflict_judge": "CONSENSUS_CONFLICT_JUDGE_MODEL",
    "confidence_judge": "CONSENSUS_CONFIDENCE_JUDGE_MODEL",
    "synthesis": "CONSENSUS_SYNTHESIS_MODEL",
}


class ConsensusLLMError(Exception):
    """Safe provider/parsing failure without secret material."""


@dataclass(frozen=True)
class LLMRoleResult:
    data: dict[str, Any]
    model: str
    latency_ms: int


class ConsensusLLMClient:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "siliconflow").strip() or "siliconflow"
        self.api_key = os.getenv("CONSENSUS_API_KEY", "").strip() or os.getenv("LLM_API_KEY", "").strip()
        self.base_url = (
            os.getenv("CONSENSUS_BASE_URL", "").strip()
            or os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1").strip()
        ).rstrip("/")
        self.default_model = os.getenv("LLM_MODEL", "Qwen/Qwen3-8B").strip()
        self.timeout = float(os.getenv("CONSENSUS_TIMEOUT_SECONDS", "45"))
        self.max_tokens = int(os.getenv("CONSENSUS_MAX_TOKENS", "1400"))
        self.temperature = float(os.getenv("CONSENSUS_TEMPERATURE", "0"))
        self.call_count = 0
        self.failure_count = 0
        self.trace: list[ModelTraceEntry] = []

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.default_model)

    def model_for(self, role: str) -> str:
        override_name = ROLE_MODEL_ENV.get(role, "")
        return os.getenv(override_name, "").strip() or self.default_model

    async def call_json(
        self,
        role: str,
        payload: dict[str, Any],
        *,
        evidence_ids: list[str],
    ) -> LLMRoleResult:
        model = self.model_for(role)
        if not self.configured:
            self.trace.append(
                ModelTraceEntry(
                    role=role,
                    model=model,
                    status="skipped",
                    evidence_ids_received=evidence_ids,
                    error="LLM_API_KEY is missing",
                )
            )
            raise ConsensusLLMError("LLM_API_KEY is missing")

        client = OpenAICompatibleClient()
        client.api_key = self.api_key
        client.base_url = self.base_url
        client.model = model
        client.timeout = self.timeout
        request_payload = {
            "model": model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": ROLE_PROMPTS[role]},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        started = time.perf_counter()
        self.call_count += 1
        try:
            response = await client._post_chat(request_payload, headers)
            content = response["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ConsensusLLMError("LLM role returned an empty response")
            parsed = _parse_json_object(content)
            if parsed is None:
                raise ConsensusLLMError("LLM role returned malformed JSON")
        except ConsensusLLMError as exc:
            self.failure_count += 1
            latency_ms = round((time.perf_counter() - started) * 1000)
            self.trace.append(ModelTraceEntry(role=role, model=model, status="fallback", latency_ms=latency_ms, evidence_ids_received=evidence_ids, error=str(exc)))
            raise
        except httpx.TimeoutException as exc:
            self.failure_count += 1
            latency_ms = round((time.perf_counter() - started) * 1000)
            self.trace.append(ModelTraceEntry(role=role, model=model, status="fallback", latency_ms=latency_ms, evidence_ids_received=evidence_ids, error="LLM role request timed out"))
            raise ConsensusLLMError("LLM role request timed out") from exc
        except httpx.HTTPStatusError as exc:
            self.failure_count += 1
            latency_ms = round((time.perf_counter() - started) * 1000)
            message = f"LLM role returned HTTP {exc.response.status_code}"
            self.trace.append(ModelTraceEntry(role=role, model=model, status="fallback", latency_ms=latency_ms, evidence_ids_received=evidence_ids, error=message))
            raise ConsensusLLMError(message) from exc
        except (LLMProviderError, httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            self.failure_count += 1
            latency_ms = round((time.perf_counter() - started) * 1000)
            message = "LLM role provider returned an unexpected response"
            self.trace.append(ModelTraceEntry(role=role, model=model, status="fallback", latency_ms=latency_ms, evidence_ids_received=evidence_ids, error=message))
            raise ConsensusLLMError(message) from exc

        latency_ms = round((time.perf_counter() - started) * 1000)
        self.trace.append(ModelTraceEntry(role=role, model=model, status="success", latency_ms=latency_ms, evidence_ids_received=evidence_ids))
        return LLMRoleResult(data=parsed, model=model, latency_ms=latency_ms)
