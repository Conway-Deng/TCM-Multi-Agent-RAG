from __future__ import annotations

from typing import Any

import httpx

from .base import GenerationResult


class ProviderUnavailable(RuntimeError):
    pass


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
    return payload


def _extract_chat_content(data: dict[str, Any]) -> str:
    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise TypeError("provider response content must be a non-empty string")
    return content


class OpenAICompatibleLLMProvider:
    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: float, max_tokens: int, provider_name: str = "openai_compatible") -> None:
        self.name = provider_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            content = _extract_chat_content(data)
            usage = data.get("usage", {})
            return GenerationResult(
                text=content,
                provider=self.name,
                model=self.model,
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
            )
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderUnavailable("OpenAI-compatible provider unavailable") from exc
