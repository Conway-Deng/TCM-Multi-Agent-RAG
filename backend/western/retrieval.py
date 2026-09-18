from __future__ import annotations

from pathlib import Path

from retrieval import RetrievalEngine
from schemas.research import RetrievalStrategy

from .corpus import WesternRuntimeCorpus, load_runtime_corpus
from .schemas import WesternRetrievalEvidence, WesternTopic


class WesternRetriever:
    def __init__(
        self,
        *,
        corpus: WesternRuntimeCorpus | None = None,
        corpus_path: str | Path | None = None,
    ) -> None:
        self.corpus = corpus or load_runtime_corpus(corpus_path)
        self.engine = RetrievalEngine(chunks=self.corpus.chunks, sources=self.corpus.sources)
        self._chunks_by_id = {item.chunk_id: item for item in self.corpus.chunks}

    async def search(self, question: str, topic: WesternTopic, *, top_k: int = 4) -> list[WesternRetrievalEvidence]:
        results = await self.engine.search(
            question,
            strategy=RetrievalStrategy.R0,
            top_k=top_k,
            topics=[topic.value],
        )
        evidence: list[WesternRetrievalEvidence] = []
        for item in results:
            chunk = self._chunks_by_id.get(item.chunk_id)
            source = self.corpus.sources.get(item.source_id)
            if chunk is None or source is None or chunk.domain != "western":
                raise RuntimeError("Western retrieval returned evidence outside the injected pilot corpus")
            if topic.value not in chunk.topics:
                raise RuntimeError("Western retrieval returned evidence outside the routed pilot topic")
            evidence.append(WesternRetrievalEvidence(
                chunk_id=chunk.chunk_id,
                source_id=source.source_id,
                rank=item.rank,
                lexical_score=float(item.lexical_score or 0.0),
                article_title=source.title,
                section=chunk.section,
                pmcid=source.pmcid,
                doi=source.doi,
                source_url=source.source_url,
                license=source.license,
                topic=topic,
                text=chunk.text,
                provenance={
                    "source_type": source.source_type,
                    "organization_or_journal": source.organization_or_journal,
                    "publication_year": source.publication_year,
                    "license_url": source.license_url,
                    "evidence_category": source.evidence_category,
                    "review_status": source.review_status,
                },
            ))
        return evidence
