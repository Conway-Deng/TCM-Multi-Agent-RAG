from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from config.settings import Settings
from orchestration import ResearchWorkbench
from providers import (
    M2_SPECIALIST_ROTATIONS,
    ProviderBundle,
    build_llm_provider,
    consensus_provider_for,
    specialist_provider_for,
)
from providers.base import GenerationResult
from providers.openai_compatible import OpenAICompatibleLLMProvider, ProviderUnavailable
from providers.openai_compatible import _chat_payload
from schemas.research import ConditionId, ModelProfile, ModelTarget, ResearchRequest, RetrievalStrategy


QWEN = "Qwen/Qwen3-8B"
GLM = "THUDM/GLM-Z1-9B-0414"
DEEPSEEK = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"


class FakeLLM:
    name = "siliconflow"

    def __init__(self, model: str, *, failure: ProviderUnavailable | None = None) -> None:
        self.model = model
        self.failure = failure
        self.calls = 0

    async def generate(self, **_) -> GenerationResult:
        self.calls += 1
        if self.failure:
            raise self.failure
        return GenerationResult(
            text="This source-constrained educational summary reports only the supplied evidence.",
            provider=self.name,
            model=self.model,
        )


class ScriptedLLM(FakeLLM):
    def __init__(self, model: str, results: list[GenerationResult | Exception]) -> None:
        super().__init__(model)
        self.results = list(results)
        self.call_arguments: list[dict] = []

    async def generate(self, **kwargs) -> GenerationResult:
        self.calls += 1
        self.call_arguments.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _bundle(
    *,
    glm_failure: ProviderUnavailable | None = None,
    qwen_provider: FakeLLM | None = None,
    glm_provider: FakeLLM | None = None,
    deepseek_provider: FakeLLM | None = None,
) -> ProviderBundle:
    qwen = qwen_provider or FakeLLM(QWEN)
    glm = glm_provider or FakeLLM(GLM, failure=glm_failure)
    deepseek = deepseek_provider or FakeLLM(DEEPSEEK)
    return ProviderBundle(
        llm=qwen,
        embedding=object(),
        rerank=object(),
        vector_store=object(),
        evaluator=qwen,
        mock_mode=False,
        qwen=qwen,
        glm=glm,
        deepseek=deepseek,
        consensus=FakeLLM(QWEN),
    )


def test_shared_builder_preserves_verified_qwen_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        llm_provider="siliconflow",
        llm_api_key="unit-test-placeholder",
        llm_base_url="https://api.siliconflow.cn/v1",
        llm_timeout_seconds=45,
        llm_max_tokens=1400,
    )
    monkeypatch.setattr("providers.factory.get_settings", lambda: settings)
    for model, timeout_override, expected_timeout in ((QWEN, None, 45), (GLM, None, 45), (DEEPSEEK, 90, 90)):
        provider = build_llm_provider(model, timeout_override=timeout_override)
        assert isinstance(provider, OpenAICompatibleLLMProvider)
        assert provider.name == "siliconflow"
        assert provider.api_key == "unit-test-placeholder"
        assert provider.base_url == "https://api.siliconflow.cn/v1"
        assert provider.timeout == expected_timeout
        assert provider.max_tokens == 1400
        assert provider.model == model
        assert _chat_payload(
            model=model,
            system="system",
            prompt="prompt",
            temperature=0.0,
            max_tokens=384,
            frequency_penalty=0.5,
        )["enable_thinking"] is False


def test_every_configured_remote_provider_uses_one_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    import providers.factory as factory

    settings = Settings(llm_provider="siliconflow", llm_api_key="unit-test-placeholder")
    constructed: list[tuple[str, float | None]] = []

    def fake_builder(model_id: str, *, timeout_override: float | None = None) -> FakeLLM:
        constructed.append((model_id, timeout_override))
        return FakeLLM(model_id)

    monkeypatch.setattr(factory, "get_settings", lambda: settings)
    monkeypatch.setattr(factory, "build_llm_provider", fake_builder)
    bundle = factory.get_provider_bundle()

    assert constructed == [
        (settings.llm_model, None),
        (settings.qwen_model, None),
        (settings.glm_model, None),
        (settings.deepseek_model, 90),
        (settings.consensus_model, None),
    ]
    assert bundle.llm.model == settings.llm_model
    assert bundle.qwen.model == QWEN
    assert bundle.glm.model == GLM
    assert bundle.deepseek.model == DEEPSEEK
    assert bundle.consensus.model == QWEN


def test_m1_m2_rotations_and_consensus_model_are_frozen() -> None:
    bundle = _bundle()
    assert [specialist_provider_for(bundle, ModelProfile.M1, seat_index=seat, rotation_id=1).model for seat in range(3)] == [QWEN] * 3
    expected = {
        1: [QWEN, GLM, DEEPSEEK],
        2: [GLM, DEEPSEEK, QWEN],
        3: [DEEPSEEK, QWEN, GLM],
    }
    assert M2_SPECIALIST_ROTATIONS == {
        1: ("qwen", "glm", "deepseek"),
        2: ("glm", "deepseek", "qwen"),
        3: ("deepseek", "qwen", "glm"),
    }
    for rotation_id, models in expected.items():
        assert [specialist_provider_for(bundle, ModelProfile.M2, seat_index=seat, rotation_id=rotation_id).model for seat in range(3)] == models
    assert consensus_provider_for(bundle).model == QWEN


@pytest.mark.parametrize("model_target, expected_model", [(ModelTarget.QWEN, QWEN), (ModelTarget.GLM, GLM), (ModelTarget.DEEPSEEK, DEEPSEEK)])
def test_each_configured_model_can_run_independently_and_traces_actual_model(model_target: ModelTarget, expected_model: str) -> None:
    async def run_once():
        workbench = ResearchWorkbench(force_mock=True)
        workbench.providers = _bundle()
        workbench.settings = workbench.settings.model_copy(update={
            "llm_provider": "siliconflow",
            "llm_api_key": "unit-test-placeholder",
            "research_real_llm_enabled": True,
        })
        return await workbench.run(ResearchRequest(
            question="Explain herbal formula concepts for insomnia in TCM teaching.",
            condition_id=ConditionId.C1,
            retrieval_strategy=RetrievalStrategy.R2,
            model_target=model_target,
        ))

    result = asyncio.run(run_once())
    assert result.trace is not None
    assert result.trace.provider_calls > 0
    assert result.trace.successful_provider_calls > 0
    assert result.trace.model == expected_model
    assert {attempt.model for attempt in result.trace.provider_attempts} == {expected_model}
    assert all(attempt.provider == "siliconflow" for attempt in result.trace.provider_attempts)


def test_model_target_and_profile_cannot_be_combined() -> None:
    with pytest.raises(ValueError, match="cannot be used together"):
        ResearchRequest(
            question="Explain insomnia in TCM teaching.",
            model_profile=ModelProfile.M2,
            model_target=ModelTarget.GLM,
        )


def test_finish_reason_stop_accepts_valid_unpunctuated_deepseek_text() -> None:
    text = "This source constrained educational summary reports only the supplied evidence"
    deepseek = ScriptedLLM(DEEPSEEK, [GenerationResult(text=text, provider="siliconflow", model=DEEPSEEK, finish_reason="stop")])

    async def run_once():
        workbench = ResearchWorkbench(force_mock=True)
        workbench.providers = _bundle(deepseek_provider=deepseek)
        workbench.settings = workbench.settings.model_copy(update={
            "llm_provider": "siliconflow",
            "llm_api_key": "unit-test-placeholder",
            "research_real_llm_enabled": True,
        })
        return await workbench.run(ResearchRequest(
            question="Explain herbal formula concepts for insomnia in TCM teaching.",
            condition_id=ConditionId.C1,
            retrieval_strategy=RetrievalStrategy.R2,
            model_target=ModelTarget.DEEPSEEK,
        ))

    result = asyncio.run(run_once())
    assert result.trace is not None
    assert result.trace.successful_provider_calls == 1
    assert len(result.trace.provider_attempts) == 1
    assert result.trace.provider_attempts[0].finish_reason == "stop"


def test_deepseek_length_retry_uses_larger_budget_and_traces_finish_reason() -> None:
    deepseek = ScriptedLLM(DEEPSEEK, [
        GenerationResult(text="This response is truncated before its final sentence", provider="siliconflow", model=DEEPSEEK, finish_reason="length"),
        GenerationResult(text="This source-constrained educational summary reports only the supplied evidence.", provider="siliconflow", model=DEEPSEEK, finish_reason="stop"),
    ])

    async def run_once():
        workbench = ResearchWorkbench(force_mock=True)
        workbench.providers = _bundle(deepseek_provider=deepseek)
        workbench.settings = workbench.settings.model_copy(update={
            "llm_provider": "siliconflow",
            "llm_api_key": "unit-test-placeholder",
            "research_real_llm_enabled": True,
        })
        return await workbench.run(ResearchRequest(
            question="Explain herbal formula concepts for insomnia in TCM teaching.",
            condition_id=ConditionId.C1,
            retrieval_strategy=RetrievalStrategy.R2,
            model_target=ModelTarget.DEEPSEEK,
        ))

    result = asyncio.run(run_once())
    assert [call["max_tokens"] for call in deepseek.call_arguments] == [384, 640]
    assert "Return one complete concise paragraph and end the final sentence with terminal punctuation." in deepseek.call_arguments[1]["system"]
    assert result.trace is not None
    assert [attempt.finish_reason for attempt in result.trace.provider_attempts] == ["length", "stop"]
    assert result.trace.provider_attempts[0].error == "truncated output (finish_reason=length)"
    assert result.trace.provider_attempts[1].success is True


@pytest.mark.parametrize("model_target, model", [(ModelTarget.QWEN, QWEN), (ModelTarget.GLM, GLM)])
def test_qwen_and_glm_retry_token_budget_is_unchanged(model_target: ModelTarget, model: str) -> None:
    provider = ScriptedLLM(model, [
        GenerationResult(text="This otherwise valid response has no terminal punctuation", provider="siliconflow", model=model, finish_reason="stop"),
        GenerationResult(text="This source-constrained educational summary reports only the supplied evidence.", provider="siliconflow", model=model, finish_reason="stop"),
    ])

    async def run_once():
        workbench = ResearchWorkbench(force_mock=True)
        providers = {"qwen_provider": provider} if model_target == ModelTarget.QWEN else {"glm_provider": provider}
        workbench.providers = _bundle(**providers)
        workbench.settings = workbench.settings.model_copy(update={
            "llm_provider": "siliconflow",
            "llm_api_key": "unit-test-placeholder",
            "research_real_llm_enabled": True,
        })
        return await workbench.run(ResearchRequest(
            question="Explain herbal formula concepts for insomnia in TCM teaching.",
            condition_id=ConditionId.C1,
            retrieval_strategy=RetrievalStrategy.R2,
            model_target=model_target,
        ))

    result = asyncio.run(run_once())
    assert [call["max_tokens"] for call in provider.call_arguments] == [384, 384]
    assert all("Return one complete concise paragraph" not in call["system"] for call in provider.call_arguments)
    assert result.trace is not None and result.trace.successful_provider_calls == 1


def test_legacy_request_uses_qwen_and_model_failure_is_isolated() -> None:
    async def run_pair():
        success = ResearchWorkbench(force_mock=True)
        success.providers = _bundle()
        success.settings = success.settings.model_copy(update={
            "llm_provider": "siliconflow",
            "llm_api_key": "unit-test-placeholder",
            "research_real_llm_enabled": True,
        })
        legacy = await success.run(ResearchRequest(
            question="Explain herbal formula concepts for insomnia in TCM teaching.",
            condition_id=ConditionId.C1,
            retrieval_strategy=RetrievalStrategy.R2,
        ))

        failure = ResearchWorkbench(force_mock=True)
        failure.providers = _bundle(glm_failure=ProviderUnavailable("GLM test failure", error_type="http_5xx", http_status=503))
        failure.settings = success.settings
        failed = await failure.run(ResearchRequest(
            question="Explain herbal formula concepts for insomnia in TCM teaching.",
            condition_id=ConditionId.C1,
            retrieval_strategy=RetrievalStrategy.R2,
            model_profile=ModelProfile.M2,
            model_rotation=2,
        ))
        return legacy, failed

    legacy, failed = asyncio.run(run_pair())
    assert legacy.trace is not None
    assert legacy.trace.model == QWEN
    assert {attempt.model for attempt in legacy.trace.provider_attempts} == {QWEN}
    assert failed.trace is not None
    assert failed.trace.fallback_usage is True
    assert failed.generation_mode == "deterministic_fallback"
    assert failed.trace.provider_attempts
    assert all(attempt.model == GLM for attempt in failed.trace.provider_attempts)
    assert all(attempt.provider == "siliconflow" for attempt in failed.trace.provider_attempts)
    assert all(attempt.http_status == 503 for attempt in failed.trace.provider_attempts)
    assert all(attempt.error_type == "http_5xx" for attempt in failed.trace.provider_attempts)
    assert all(attempt.error == "GLM test failure" for attempt in failed.trace.provider_attempts)
    assert any(f"model={GLM}" in error and "http_status=503" in error for error in failed.trace.provider_errors)
