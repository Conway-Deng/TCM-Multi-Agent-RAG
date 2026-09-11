from __future__ import annotations

from .retrieval import RetrievalDiagnostics, RetrievalResult, retrieve


def analyse_query(results: list[RetrievalResult]) -> tuple[list[str], list[str]]:
    keywords: list[str] = []
    domains: list[str] = []
    for result in results:
        for term in result.matched_terms:
            if term not in keywords:
                keywords.append(term)
        for domain in (result.entry.topic, *result.entry.tags):
            if domain not in domains:
                domains.append(domain)
    return keywords[:12], domains[:8]


__all__ = ["RetrievalDiagnostics", "RetrievalResult", "analyse_query", "retrieve"]
