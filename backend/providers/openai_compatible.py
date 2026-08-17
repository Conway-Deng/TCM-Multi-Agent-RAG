from __future__ import annotations

from typing import Any

import httpx

from .base import GenerationResult


class ProviderUnavailable(RuntimeError):
    pass


class OpenAICompatibleLLMProvider:
    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: float, max_tokens: int, provider_name: str = "openai_compatible") -> None:
        self.name = provider_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    async def generate(self, *, system: str, prompt: str, temperature: float = 0.0) -> GenerationResult:
        if not self.api_key:
            raise ProviderUnavailable("LLM API key is missing")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            content = str(data["choices"][0]["message"]["content"])
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
