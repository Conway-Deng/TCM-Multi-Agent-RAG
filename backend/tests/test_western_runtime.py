from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from providers.base import GenerationResult
from providers.openai_compatible import ProviderUnavailable
from western.agent import (
    PILOT_LIMITATION,
    WESTERN_EVIDENCE_EXCERPT_CHARS,
    WESTERN_MAX_TOKENS,
    WESTERN_MODEL,
    WESTERN_TIMEOUT_SECONDS,
    WesternEvidenceAgent,
)
from western.corpus import (
    DEFAULT_CORPUS_ROOT,
    WesternCorpusError,
    active_corpus_root,
    clear_runtime_cache,
    load_runtime_corpus,
    western_corpus_stats,
)
from western.models import WesternKnowledgeChunk
from western.retrieval import WesternRetriever
from western.routing import route_western_scope
from western.schemas import WesternConsultRequest, WesternTopic


class SuccessProvider:
    name = "siliconflow"
    model = WESTERN_MODEL

    def __init__(self) -> None:
        self.calls = 0
        self.last_system = ""
        self.last_prompt = ""
        self.last_temperature: float | None = None
        self.last_max_tokens: int | None = None

    async def generate(self, *, system: str, prompt: str, temperature: float = 0.0, max_tokens=None, frequency_penalty=0.0):
        self.calls += 1
        self.last_system = system
        self.last_prompt = prompt
        self.last_temperature = temperature
        self.last_max_tokens = max_tokens
        text = (
            "The supplied reviews describe source-reported findings for this pilot topic. "
            "The evidence remains limited and should not be treated as comprehensive clinical guidance. "
            "This automated educational summary is not medical advice."
        )
        return GenerationResult(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=100,
            completion_tokens=30,
            finish_reason="stop",
        )


class FailureProvider:
    name = "siliconflow"
    model = WESTERN_MODEL

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        raise ProviderUnavailable("LLM provider connectivity error", error_type="connectivity")


class NoCitationProvider:
    name = "siliconflow"
    model = WESTERN_MODEL

    async def generate(self, **kwargs):
        return GenerationResult(
            text="The supplied reviews describe educational source-reported findings. This automated output is not medical advice.",
            provider=self.name,
            model=self.model,
            finish_reason="stop",
        )


class TextProvider:
    name = "siliconflow"
    model = WESTERN_MODEL

    def __init__(self, text: str) -> None:
        self.text = text

    async def generate(self, **kwargs):
        return GenerationResult(text=self.text, provider=self.name, model=self.model, finish_reason="stop")


class TimeoutProvider:
    name = "siliconflow"
    model = WESTERN_MODEL

    async def generate(self, **kwargs):
        raise ProviderUnavailable("LLM request timed out", error_type="timeout")


class NeverCallProvider:
    name = "stub"
    model = WESTERN_MODEL

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        raise AssertionError("out-of-scope and safety abstentions must not call a provider")


class NeverSearchRetriever:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("out-of-scope and safety abstentions must not retrieve")


def test_runtime_loader_validates_and_reports_phase_1a_corpus() -> None:
    clear_runtime_cache()
    corpus = load_runtime_corpus()
    stats = western_corpus_stats()
    assert len(corpus.sources) == 16
    assert len(corpus.chunks) == 271
    assert stats["corpus_version"] == "medirag-west-v0.1-pilot"
    assert stats["topic_count"] == 4
    assert stats["validation_errors"] == []


def test_western_corpus_path_accepts_directory_or_chunks_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WESTERN_CORPUS_PATH", str(DEFAULT_CORPUS_ROOT))
    assert active_corpus_root() == DEFAULT_CORPUS_ROOT
    monkeypatch.setenv("WESTERN_CORPUS_PATH", str(DEFAULT_CORPUS_ROOT / "chunks.jsonl"))
    assert active_corpus_root() == DEFAULT_CORPUS_ROOT


@pytest.mark.parametrize(("question", "topic"), [
    ("What does research report about chronic cough?", WesternTopic.COUGH),
    ("What is functional dyspepsia?", WesternTopic.DYSPEPSIA),
    ("What do reviews report about migraine?", WesternTopic.HEADACHE),
    ("What does research report about constipation?", WesternTopic.CONSTIPATION),
])
def test_scope_router_supports_only_the_four_pilot_topics(question: str, topic: WesternTopic) -> None:
    decision = route_western_scope(question)
    assert decision.supported is True
    assert decision.topic == topic


def test_scope_router_abstains_outside_or_across_topics() -> None:
    assert route_western_scope("What does research say about diabetes?").supported is False
    ambiguous = route_western_scope("How are cough and constipation studied?")
    assert ambiguous.supported is False
    assert len(ambiguous.matched_topics) == 2


def test_out_of_scope_abstention_uses_no_retrieval_or_provider() -> None:
    provider = NeverCallProvider()
    retriever = NeverSearchRetriever()
    result = asyncio.run(WesternEvidenceAgent(provider=provider, retriever=retriever).consult(
        WesternConsultRequest(question="What does research say about diabetes?")
    ))
    assert result.abstained is True
    assert result.generation_mode == "scope_abstention"
    assert result.retrieval == []
    assert PILOT_LIMITATION in result.limitations
    assert provider.calls == 0
    assert retriever.calls == 0


def test_emergency_abstention_uses_no_retrieval_or_provider() -> None:
    provider = NeverCallProvider()
    retriever = NeverSearchRetriever()
    result = asyncio.run(WesternEvidenceAgent(provider=provider, retriever=retriever).consult(
        WesternConsultRequest(question="I am coughing and cannot breathe")
    ))
    assert result.abstained is True
    assert result.generation_mode == "safety_abstention"
    assert result.safety_flags
    assert provider.calls == 0
    assert retriever.calls == 0


@pytest.mark.parametrize(("topic", "query"), [
    (WesternTopic.COUGH, "cough causes diagnosis treatment"),
    (WesternTopic.DYSPEPSIA, "dyspepsia digestive symptoms diagnosis treatment"),
    (WesternTopic.HEADACHE, "headache migraine diagnosis treatment"),
    (WesternTopic.CONSTIPATION, "constipation diagnosis treatment"),
])
def test_four_topic_r0_retrieval_contains_only_western_evidence(topic: WesternTopic, query: str) -> None:
    results = asyncio.run(WesternRetriever().search(query, topic, top_k=4))
    assert len(results) == 4
    assert all(item.chunk_id.startswith("west-pmc-") for item in results)
    assert all(item.source_id.startswith("west-pmc-") for item in results)
    assert all(item.topic == topic for item in results)
    assert all(item.pmcid.startswith("PMC") and item.source_url and item.license for item in results)
    assert all(not item.chunk_id.startswith("tcmv1-") for item in results)


def test_successful_agent_uses_anonymous_prompt_and_deterministic_provenance() -> None:
    provider = SuccessProvider()
    result = asyncio.run(WesternEvidenceAgent(provider=provider).consult(
        WesternConsultRequest(question="What do systematic reviews report about cough?", top_k=4)
    ))
    assert result.abstained is False
    assert result.topic == WesternTopic.COUGH
    assert result.provider == "siliconflow"
    assert result.model == WESTERN_MODEL
    assert result.generation_mode == "llm"
    assert len(result.retrieval) == 4
    assert len(result.citations) == 4
    assert result.claims[0].evidence_ids == []
    assert result.claims[0].support_status == "not_individually_verified"
    assert result.support_status == "not_individually_verified"
    assert result.evidence_support_signal == 0.0
    assert [item.evidence_id for item in result.citations] == [item.chunk_id for item in result.retrieval]
    assert all(item.source_url and item.pmcid and item.license and item.provenance_valid for item in result.citations)
    assert provider.calls == 1
    assert provider.last_temperature == 0.0
    assert provider.last_max_tokens == WESTERN_MAX_TOKENS == 256
    assert "ONLY the supplied evidence" in provider.last_system
    assert "chain-of-thought" not in provider.last_system
    assert "Do not output citations" in provider.last_system
    assert all(f"Evidence {label}:" in provider.last_prompt for label in "ABCD")
    for item in result.retrieval:
        assert item.chunk_id not in provider.last_prompt
        assert item.source_id not in provider.last_prompt
        assert item.pmcid not in provider.last_prompt
        assert item.source_url not in provider.last_prompt
        if item.doi:
            assert item.doi not in provider.last_prompt
    excerpts = [line.removeprefix("Excerpt: ") for line in provider.last_prompt.splitlines() if line.startswith("Excerpt: ")]
    assert len(excerpts) == 4
    assert all(len(item) <= WESTERN_EVIDENCE_EXCERPT_CHARS for item in excerpts)


def test_provider_failure_preserves_retrieval_without_fabricated_answer() -> None:
    provider = FailureProvider()
    result = asyncio.run(WesternEvidenceAgent(provider=provider).consult(
        WesternConsultRequest(question="What does research report about constipation?", top_k=4)
    ))
    assert result.abstained is True
    assert result.answer == ""
    assert len(result.retrieval) == 4
    assert result.claims == []
    assert [item.evidence_id for item in result.citations] == [item.chunk_id for item in result.retrieval]
    assert result.generation_mode == "generation_failure"
    assert result.trace is not None and result.trace.fallback_usage is False
    assert result.trace.provider_attempts[0].error_type == "connectivity"
    assert provider.calls == 1


def test_application_attaches_provenance_when_model_omits_markers() -> None:
    result = asyncio.run(WesternEvidenceAgent(provider=NoCitationProvider()).consult(
        WesternConsultRequest(question="What does research report about constipation?", top_k=4)
    ))
    assert result.abstained is False
    assert result.generation_mode == "llm"
    assert len(result.citations) == 4
    assert result.evidence_support_signal == 0.0
    assert result.claims[0].evidence_ids == []
    assert result.support_status == "not_individually_verified"
    assert all(item.evidence_id not in result.answer for item in result.citations)


def test_model_generated_provenance_like_text_is_sanitized_and_never_authoritative() -> None:
    provider = TextProvider(
        "The supplied review reports limited findings [west-pmc-fabricated-123]. "
        "See https://example.invalid/fake, PMC999999, and doi:10.9999/fabricated. "
        "This educational summary is not medical advice."
    )
    result = asyncio.run(WesternEvidenceAgent(provider=provider).consult(
        WesternConsultRequest(question="What does research report about constipation?", top_k=4)
    ))
    assert result.abstained is False
    assert "west-pmc-fabricated" not in result.answer
    assert "example.invalid" not in result.answer
    assert "PMC999999" not in result.answer
    assert "10.9999/fabricated" not in result.answer
    assert [item.evidence_id for item in result.citations] == [item.chunk_id for item in result.retrieval]
    assert result.claims[0].evidence_ids == []


@pytest.mark.parametrize("text", [
    "Repeated provider corruption. Repeated provider corruption. Repeated provider corruption.",
    "word " * 181,
])
def test_malformed_or_unbounded_provider_output_fails_safely(text: str) -> None:
    result = asyncio.run(WesternEvidenceAgent(provider=TextProvider(text)).consult(
        WesternConsultRequest(question="What does research report about constipation?", top_k=4)
    ))
    assert result.abstained is True
    assert result.answer == ""
    assert result.generation_mode == "generation_failure"
    assert len(result.retrieval) == len(result.citations) == 4
    assert result.trace is not None
    assert result.trace.provider_attempts[0].error_type == "output_quality_rejection"


def test_timeout_preserves_retrieval_and_deterministic_provenance() -> None:
    result = asyncio.run(WesternEvidenceAgent(provider=TimeoutProvider()).consult(
        WesternConsultRequest(question="What does research report about constipation?", top_k=4)
    ))
    assert result.abstained is True
    assert result.answer == ""
    assert len(result.retrieval) == len(result.citations) == 4
    assert result.trace is not None
    assert result.trace.provider_attempts[0].error_type == "timeout"
    assert result.trace.fallback_usage is False


def test_western_timeout_is_an_agent_only_override(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, float | None]] = []

    class Provider:
        name = "stub"
        model = WESTERN_MODEL

    def fake_builder(model: str, *, timeout_override: float | None = None):
        captured.append((model, timeout_override))
        return Provider()

    monkeypatch.setattr("western.agent.build_llm_provider", fake_builder)
    WesternEvidenceAgent(retriever=NeverSearchRetriever())
    assert captured == [(WESTERN_MODEL, WESTERN_TIMEOUT_SECONDS)]
    assert WESTERN_TIMEOUT_SECONDS == 120.0


def test_missing_corpus_fails_clearly(tmp_path: Path) -> None:
    clear_runtime_cache()
    with pytest.raises(WesternCorpusError, match="missing required artifact"):
        load_runtime_corpus(tmp_path)


def test_invalid_corpus_fails_before_retrieval(tmp_path: Path) -> None:
    invalid_chunk = WesternKnowledgeChunk(
        chunk_id="west-pmc-1-invalid",
        source_id="west-pmc-missing",
        section="Background",
        text="A sufficiently explicit but unreferenced Western pilot chunk.",
        topics=["cough"],
        keywords=["cough"],
        pmcid="PMC1",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC1/",
    )
    (tmp_path / "source_registry.json").write_text("[]\n", encoding="utf-8")
    (tmp_path / "chunks.jsonl").write_text(invalid_chunk.model_dump_json() + "\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("{}\n", encoding="utf-8")
    clear_runtime_cache()
    with pytest.raises(WesternCorpusError, match="validation failed"):
        load_runtime_corpus(tmp_path)
