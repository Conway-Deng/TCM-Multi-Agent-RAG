from __future__ import annotations

from typing import Any

import httpx

from .base import GenerationResult


class ProviderUnavailable(RuntimeError):
    def __init__(self, message: str, *, error_type: str = "unknown", http_status: int | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.http_status = http_status


def _supports_thinking_toggle(model: str) -> bool:
    return model in {
        "Qwen/Qwen3-8B",
        "THUDM/GLM-Z1-9B-0414",
        "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
    }


def _chat_payload(
    *,
    model: str,
    system: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    frequency_penalty: float,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": temperature,
        "frequency_penalty": frequency_penalty,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if _supports_thinking_toggle(model):
        payload["enable_thinking"] = False
    return payload


def _extract_chat_content(data: dict[str, Any]) -> str:
    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise TypeError("provider response content must be a non-empty string")
    return content


def _extract_finish_reason(data: dict[str, Any]) -> str | None:
    finish_reason = data["choices"][0].get("finish_reason")
    if finish_reason is not None and not isinstance(finish_reason, str):
        raise TypeError("provider finish_reason must be a string or null")
    return finish_reason


class OpenAICompatibleLLMProvider:
    _shared_http_client: httpx.AsyncClient | None = None

    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: float, max_tokens: int, provider_name: str = "openai_compatible") -> None:
        self.name = provider_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.enable_thinking = False if _supports_thinking_toggle(model) else None

    async def generate(
        self,
        *,
        system: str,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        frequency_penalty: float = 0.0,
    ) -> GenerationResult:
        if not self.api_key:
            raise ProviderUnavailable("LLM API key is missing")
        payload = _chat_payload(
            model=self.model,
            system=system,
            prompt=prompt,
            temperature=temperature,
            max_tokens=min(max_tokens, self.max_tokens) if max_tokens is not None else self.max_tokens,
            frequency_penalty=frequency_penalty,
        )
        try:
            if self.__class__._shared_http_client is None or getattr(self.__class__._shared_http_client, "is_closed", False):
                self.__class__._shared_http_client = httpx.AsyncClient(timeout=None)
            response = await self.__class__._shared_http_client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            content = _extract_chat_content(data)
            finish_reason = _extract_finish_reason(data)
            usage = data.get("usage", {})
            return GenerationResult(
                text=content,
                provider=self.name,
                model=self.model,
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                finish_reason=finish_reason,
                metadata={"finish_reason": finish_reason},
            )
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("LLM request timed out", error_type="timeout") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            error_type = "rate_limit" if status == 429 else "http_4xx" if 400 <= status < 500 else "http_5xx" if status >= 500 else "unknown"
            raise ProviderUnavailable(f"LLM provider returned HTTP {status}", error_type=error_type, http_status=status) from exc
        except (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            raise ProviderUnavailable("LLM provider connectivity error", error_type="connectivity") from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderUnavailable("LLM provider returned a malformed response", error_type="malformed_response") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable("LLM provider unavailable", error_type="unknown") from exc

    @classmethod
    async def close_shared_http_client(cls) -> None:
        if cls._shared_http_client is not None and not getattr(cls._shared_http_client, "is_closed", False):
            close = getattr(cls._shared_http_client, "aclose", None)
            if close is not None:
                await close()
        cls._shared_http_client = None
