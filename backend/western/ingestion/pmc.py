from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
import time
from typing import Iterable, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from western.models import WesternKnowledgeChunk, WesternSourceRecord


EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CHUNKING_VERSION = "jats-structural-paragraph-groups-v1"
EXCLUDED_SECTION_TERMS = {
    "acknowledgment", "acknowledgments", "acknowledgement", "acknowledgements",
    "references", "bibliography", "supplementary material", "supplemental material",
    "author contributions", "funding", "conflict of interest", "competing interests",
}
TITLE_STOPWORDS = {
    "about", "after", "among", "article", "based", "between", "clinical", "effects",
    "from", "into", "review", "systematic", "that", "their", "these", "this", "using", "with",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _element_text(element: ET.Element | None) -> str:
    return _clean_text(" ".join(element.itertext())) if element is not None else ""


def _first(root: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in root.iter() if _local(item.tag) == name), None)


def _all(root: ET.Element, name: str) -> list[ET.Element]:
    return [item for item in root.iter() if _local(item.tag) == name]


def _article_id(article_meta: ET.Element, kind: str) -> str:
    accepted_kinds = {kind.casefold()}
    if kind.casefold() == "pmc":
        accepted_kinds.add("pmcid")
    for item in _all(article_meta, "article-id"):
        if item.attrib.get("pub-id-type", "").casefold() in accepted_kinds:
            return _element_text(item)
    return ""


def _canonical_license(url: str, text: str) -> str:
    lowered = f"{url} {text}".casefold()
    patterns = [
        ("by-nc-nd/4.0", "CC BY-NC-ND 4.0"),
        ("by-nc-sa/4.0", "CC BY-NC-SA 4.0"),
        ("by-nc/4.0", "CC BY-NC 4.0"),
        ("by-nd/4.0", "CC BY-ND 4.0"),
        ("by-sa/4.0", "CC BY-SA 4.0"),
        ("by/4.0", "CC BY 4.0"),
        ("by-nc/3.0", "CC BY-NC 3.0"),
        ("by/3.0", "CC BY 3.0"),
        ("publicdomain/zero", "CC0"),
        ("public domain", "Public Domain"),
    ]
    for marker, label in patterns:
        if marker in lowered:
            return label
    if "creative commons" in lowered:
        return "Creative Commons (version not stated)"
    return ""


def _license_metadata(article_meta: ET.Element) -> tuple[str, str, str]:
    license_element = _first(article_meta, "license")
    if license_element is None:
        return "", "", ""
    license_text = _element_text(license_element)
    license_url = ""
    for key, value in license_element.attrib.items():
        if key == "href" or key.endswith("}href"):
            license_url = value.strip()
            break
    if not license_url:
        link = _first(license_element, "ext-link")
        if link is not None:
            for key, value in link.attrib.items():
                if key == "href" or key.endswith("}href"):
                    license_url = value.strip()
                    break
    if not license_url:
        match = re.search(r"https?://creativecommons\.org/(?:licenses|publicdomain)/[^\s<>()]+", license_text, re.IGNORECASE)
        if match:
            license_url = match.group(0).rstrip(".,;:")
    return _canonical_license(license_url, license_text), license_url, license_text


def _is_reusable_license(license_name: str, license_url: str, license_text: str) -> bool:
    lowered = f"{license_name} {license_url} {license_text}".casefold()
    return (
        bool(license_name)
        and "all rights reserved" not in lowered
        and ("creative commons" in lowered or "creativecommons.org/" in lowered or "public domain" in lowered or license_name == "CC0")
    )


def _source_type(article: ET.Element, title: str) -> str:
    searchable = " ".join([title, *(_element_text(item) for item in _all(article, "subject"))]).casefold()
    article_type = article.attrib.get("article-type", "").casefold()
    if "protocol" in title.casefold():
        return "peer_reviewed_article"
    if "systematic review" in searchable or "meta-analysis" in searchable or "meta analysis" in searchable:
        return "systematic_review"
    if article_type == "review-article" or " review" in f" {searchable}":
        return "review_article"
    return "peer_reviewed_article"


def _section_paragraphs(article: ET.Element) -> list[tuple[str, str]]:
    body = _first(article, "body")
    if body is None:
        return []
    result: list[tuple[str, str]] = []

    def visit(container: ET.Element, path: list[str]) -> None:
        direct_title = next((child for child in container if _local(child.tag) == "title"), None)
        title = _element_text(direct_title) or (path[-1] if path else "Body")
        next_path = [*path, title] if not path or title != path[-1] else path
        section_name = " > ".join(next_path[-3:])
        if any(term in title.casefold() for term in EXCLUDED_SECTION_TERMS):
            return
        for child in container:
            tag = _local(child.tag)
            if tag == "p":
                text = _element_text(child)
                if len(text) >= 120:
                    result.append((section_name, text))
            elif tag == "sec":
                visit(child, next_path)

    for child in body:
        if _local(child.tag) == "p":
            text = _element_text(child)
            if len(text) >= 120:
                result.append(("Body", text))
        elif _local(child.tag) == "sec":
            visit(child, [])
    return result


def _split_long_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            words = sentence.split()
            segment = ""
            for word in words:
                candidate = f"{segment} {word}".strip()
                if segment and len(candidate) > max_chars:
                    parts.append(segment)
                    segment = word
                else:
                    segment = candidate
            if current:
                parts.append(current)
                current = ""
            if segment:
                parts.append(segment)
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            parts.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _group_paragraphs(
    paragraphs: list[tuple[str, str]],
    *,
    target_chars: int = 1800,
    max_chars: int = 2600,
) -> list[tuple[str, str]]:
    expanded = [(section, part) for section, text in paragraphs for part in _split_long_text(text, max_chars)]
    groups: list[tuple[str, str]] = []
    current_section = ""
    current_parts: list[str] = []
    current_length = 0

    def flush() -> None:
        nonlocal current_section, current_parts, current_length
        if current_parts:
            groups.append((current_section, "\n\n".join(current_parts)))
        current_section, current_parts, current_length = "", [], 0

    for section, text in expanded:
        projected = current_length + len(text) + (2 if current_parts else 0)
        if current_parts and (section != current_section or projected > target_chars):
            flush()
        current_section = section
        current_parts.append(text)
        current_length += len(text) + (2 if len(current_parts) > 1 else 0)
        if current_length >= max_chars:
            flush()
    flush()
    return groups


@dataclass
class ParsedPMCArticle:
    source: WesternSourceRecord
    paragraphs: list[tuple[str, str]]
    raw_xml: bytes


def parse_pmc_articles(xml_data: bytes, *, topic: str, retrieved_at: str | None = None) -> list[ParsedPMCArticle]:
    root = ET.fromstring(xml_data)
    timestamp = retrieved_at or datetime.now(timezone.utc).isoformat()
    articles = [root] if _local(root.tag) == "article" else [item for item in root.iter() if _local(item.tag) == "article"]
    parsed: list[ParsedPMCArticle] = []
    for article in articles:
        front = _first(article, "front")
        article_meta = _first(front, "article-meta") if front is not None else None
        if article_meta is None:
            continue
        raw_pmcid = _article_id(article_meta, "pmc")
        if not raw_pmcid:
            continue
        pmcid = raw_pmcid.upper()
        if not pmcid.startswith("PMC"):
            pmcid = f"PMC{pmcid}"
        title = _element_text(_first(article_meta, "article-title"))
        journal = _element_text(_first(front, "journal-title")) if front is not None else ""
        doi = _article_id(article_meta, "doi")
        year_text = _element_text(_first(article_meta, "year"))
        publication_year = int(year_text[:4]) if re.fullmatch(r"\d{4}.*", year_text) else None
        license_name, license_url, license_text = _license_metadata(article_meta)
        if not title or not _is_reusable_license(license_name, license_url, license_text):
            continue
        paragraphs = _section_paragraphs(article)
        if not paragraphs:
            continue
        source = WesternSourceRecord(
            source_id=f"west-pmc-{pmcid[3:]}",
            title=title,
            source_type=_source_type(article, title),
            organization_or_journal=journal or "Journal metadata unavailable",
            publication_year=publication_year,
            source_url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
            pmcid=pmcid,
            doi=doi,
            license=license_name,
            license_url=license_url,
            license_text=license_text,
            retrieved_at=timestamp,
            topics=[topic],
            notes="Metadata and full text retrieved from NCBI PMC Open Access through E-utilities EFetch.",
        )
        parsed.append(ParsedPMCArticle(source=source, paragraphs=paragraphs, raw_xml=ET.tostring(article, encoding="utf-8")))
    return parsed


T = TypeVar("T")


def _evenly_limit(values: list[T], limit: int) -> list[T]:
    if len(values) <= limit:
        return values
    indices = [round(index * (len(values) - 1) / (limit - 1)) for index in range(limit)]
    return [values[index] for index in indices]


def chunk_article(article: ParsedPMCArticle, *, max_chunks: int = 18) -> list[WesternKnowledgeChunk]:
    groups = _evenly_limit(_group_paragraphs(article.paragraphs), max_chunks)
    title_words = [
        word for word in re.findall(r"[a-z][a-z-]{3,}", article.source.title.casefold())
        if word not in TITLE_STOPWORDS
    ][:10]
    topic_keywords = [word for topic in article.source.topics for word in re.findall(r"[a-z][a-z-]{2,}", topic.casefold())]
    keywords = list(dict.fromkeys([*article.source.topics, *topic_keywords, *title_words]))
    chunks: list[WesternKnowledgeChunk] = []
    for index, (section, text) in enumerate(groups, 1):
        identity = f"{article.source.pmcid}\0{section}\0{index}\0{text}".encode("utf-8")
        digest = hashlib.sha256(identity).hexdigest()[:20]
        chunks.append(WesternKnowledgeChunk(
            chunk_id=f"west-pmc-{article.source.pmcid[3:].casefold()}-{digest}",
            source_id=article.source.source_id,
            section=section,
            text=text,
            topics=list(article.source.topics),
            keywords=keywords,
            pmcid=article.source.pmcid,
            doi=article.source.doi,
            source_url=article.source.source_url,
        ))
    return chunks


class NCBIClient:
    def __init__(self, *, email: str, tool: str, api_key: str = "", min_interval_seconds: float = 0.55) -> None:
        if not email.strip():
            raise ValueError("NCBI_EMAIL is required")
        if not tool.strip():
            raise ValueError("NCBI_TOOL is required")
        if min_interval_seconds < 0.5:
            raise ValueError("NCBI requests must be limited to at most 2 per second")
        self.email = email.strip()
        self.tool = tool.strip()
        self.api_key = api_key.strip()
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at = 0.0

    def _request(self, endpoint: str, parameters: dict[str, str | int]) -> bytes:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        params = {**parameters, "tool": self.tool, "email": self.email}
        if self.api_key:
            params["api_key"] = self.api_key
        url = f"{EUTILS_BASE}/{endpoint}?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": f"{self.tool}/0.1 (NCBI contact configured)"})
        try:
            with urlopen(request, timeout=90) as response:
                payload = response.read()
        except HTTPError as exc:
            raise RuntimeError(f"NCBI request failed with HTTP status {exc.code}") from None
        except URLError:
            raise RuntimeError("NCBI request failed due to a network error") from None
        finally:
            self._last_request_at = time.monotonic()
        return payload

    def search_pmcs(self, query: str, *, retmax: int = 12) -> list[str]:
        payload = self._request("esearch.fcgi", {
            "db": "pmc", "term": query, "retmode": "xml", "retmax": retmax, "sort": "relevance",
        })
        root = ET.fromstring(payload)
        return [_element_text(item) for item in _all(root, "Id") if _element_text(item)]

    def fetch_pmcs(self, identifiers: Iterable[str]) -> bytes:
        ids = [str(item).removeprefix("PMC") for item in identifiers]
        if not ids:
            return b"<pmc-articleset />"
        return self._request("efetch.fcgi", {
            "db": "pmc", "id": ",".join(ids), "retmode": "xml", "rettype": "full",
        })
