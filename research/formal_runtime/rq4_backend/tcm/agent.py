from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from time import perf_counter
from typing import Any, ClassVar

import httpx

from .knowledge_base import FORMULA_WARNING, KNOWLEDGE_BASE, SOURCE_REGISTRY, KnowledgeEntry, SourceRecord
from .language import detect_language
from .localization import FORMULA_WARNINGS, localized_entry_display, localized_entry_safety, localized_formula_display
from .retriever import RetrievalDiagnostics, RetrievalResult, analyse_query, retrieve
from .safety import check_emergency
from .schemas import (
    Citation,
    Claim,
    Confidence,
    EvidenceChunk,
    GenerationSource,
    LocalizedResultContent,
    LocalizedResultFormula,
    LocalizedResultPattern,
    PossiblePattern,
    QueryAnalysis,
    RelatedHerbOrFormula,
    RequestTimings,
    ResponseLanguage,
    RetrievalMetadata,
    ScopeStatus,
    TCMConsultRequest,
    TCMConsultResponse,
)
from .scope import ScopeDecision, classify_scope


DISCLAIMER = (
    "For educational and research purposes only. This is not a medical diagnosis or a "
    "prescription and does not replace care from a qualified healthcare professional or "
    "licensed TCM practitioner. Do not start, stop, or change prescribed medicine based on this response."
)

BASE_SAFETY_NOTES_LOCALIZED: dict[ResponseLanguage, list[str]] = {
    "en": [
        "Do not stop or change prescribed medication without speaking with the prescribing clinician.",
        "Herbs and formulas can cause side effects and interact with medicines; product quality and correct identification also matter.",
        "Pregnancy or breastfeeding, allergies, liver or kidney disease, bleeding disorders, and planned surgery require individual professional review before any herbal product is used.",
    ],
    "zh": [
        "不要在未咨询开药医生的情况下停用或更改处方药。",
        "中药材和方剂可能产生副作用并与药物相互作用，产品质量与品种鉴别也很重要。",
        "妊娠或哺乳期、过敏、肝肾疾病、出血性疾病及计划手术者，在使用任何中药产品前都需要个体化专业评估。",
    ],
    "ko": [
        "처방약은 처방한 의료진과 상의하지 않고 중단하거나 변경하지 마세요.",
        "한약재와 처방 예시는 부작용이나 약물 상호작용이 있을 수 있으며, 제품 품질과 정확한 감별도 중요합니다.",
        "임신·수유, 알레르기, 간·신장 질환, 출혈성 질환, 수술 예정이 있는 경우 한약 제품 사용 전 개별 전문 평가가 필요합니다.",
    ],
}

RESULT_COPY: dict[ResponseLanguage, dict[str, Any]] = {
    "en": {
        "status": {
            "siliconflow_llm": "AI grounded by retrieved evidence",
            "mock_fallback": "Local evidence fallback",
            "safety_rule": "Safety-rule response",
            "scope_rule": "Scope-rule abstention",
            "evidence_gate": "Evidence-insufficient abstention",
        },
        "summary_title": "TCM perspective summary",
        "grounding": {
            "siliconflow_llm": "This LLM answer is grounded only in the local evidence retrieved for this question.",
            "mock_fallback": "The AI provider is unavailable or not configured, so this answer uses the local TCM medical library only.",
            "safety_rule": "Safety rules took priority over TCM interpretation.",
            "scope_rule": "The current TCM-RAG scope took priority over generation.",
            "evidence_gate": "The evidence gate blocked generation because no meaningful local evidence was retrieved.",
        },
        "state_title": {
            "supported": "",
            "insufficient_information": "More symptom detail is needed",
            "out_of_scope": "Out of current TCM-RAG scope",
            "safety_critical": "Safety-first response",
            "evidence_insufficient": "Insufficient retrieved evidence",
        },
        "patterns_title": "Most relevant possibilities",
        "examples_title": "Educational examples from retrieved sources",
        "safety_title": "Key safety notes",
        "evidence_title": "Retrieved evidence",
        "evidence_empty": "No evidence is shown because this response abstained.",
        "evidence_summary": "Based on {count} local evidence match(es). Strongest match: {score}%.",
    },
    "zh": {
        "status": {
            "siliconflow_llm": "AI 已基于检索证据生成",
            "mock_fallback": "本地证据回退",
            "safety_rule": "安全规则回复",
            "scope_rule": "范围规则回避回答",
            "evidence_gate": "证据不足回避回答",
        },
        "summary_title": "中医视角摘要",
        "grounding": {
            "siliconflow_llm": "本次 LLM 回答只基于本地检索到的证据生成。",
            "mock_fallback": "AI 服务暂不可用或未配置，已暂时使用本地中医医学库为您解答。",
            "safety_rule": "安全规则优先于中医辨证解释。",
            "scope_rule": "当前 TCM-RAG 研究范围优先于模型生成。",
            "evidence_gate": "由于没有检索到足够相关的本地证据，系统已阻断生成。",
        },
        "state_title": {
            "supported": "",
            "insufficient_information": "需要补充更多症状信息",
            "out_of_scope": "超出当前 TCM-RAG 范围",
            "safety_critical": "安全优先回复",
            "evidence_insufficient": "检索证据不足",
        },
        "patterns_title": "最相关的可能方向",
        "examples_title": "检索资料中的教学示例",
        "safety_title": "关键安全提示",
        "evidence_title": "检索证据",
        "evidence_empty": "本次为回避回答，因此不展示证据卡。",
        "evidence_summary": "基于 {count} 条本地证据匹配。最高匹配度：{score}%。",
    },
    "ko": {
        "status": {
            "siliconflow_llm": "검색 근거 기반 AI 생성",
            "mock_fallback": "로컬 근거 기반 대체 응답",
            "safety_rule": "안전 규칙 응답",
            "scope_rule": "범위 규칙에 따른 답변 보류",
            "evidence_gate": "근거 부족으로 답변 보류",
        },
        "summary_title": "한의학 관점 요약",
        "grounding": {
            "siliconflow_llm": "이 LLM 답변은 이 질문에 대해 검색된 로컬 근거에만 기반합니다.",
            "mock_fallback": "AI 제공자가 사용할 수 없거나 설정되지 않아, 현재는 로컬 한의학 지식베이스로 답변합니다.",
            "safety_rule": "안전 규칙이 한의학적 해석보다 우선 적용되었습니다.",
            "scope_rule": "현재 TCM-RAG 연구 범위가 생성보다 우선 적용되었습니다.",
            "evidence_gate": "의미 있는 로컬 근거가 검색되지 않아 생성이 차단되었습니다.",
        },
        "state_title": {
            "supported": "",
            "insufficient_information": "증상 정보가 더 필요합니다",
            "out_of_scope": "현재 TCM-RAG 범위를 벗어남",
            "safety_critical": "안전 우선 응답",
            "evidence_insufficient": "검색 근거 부족",
        },
        "patterns_title": "가장 관련 있는 가능 방향",
        "examples_title": "검색 자료의 교육용 예시",
        "safety_title": "주요 안전 안내",
        "evidence_title": "검색된 근거",
        "evidence_empty": "이번 응답은 답변 보류 상태이므로 근거 카드를 표시하지 않습니다.",
        "evidence_summary": "로컬 근거 {count}개와 매칭되었습니다. 최고 매칭도: {score}%.",
    },
}

LIMITATIONS_LOCALIZED: dict[ResponseLanguage, list[str]] = {
    "en": [
        "The local corpus is limited and every knowledge entry is marked needs_human_review.",
        "Pattern differentiation normally requires history, examination, and often tongue and pulse findings.",
        "Formula names are educational examples only and are not treatment recommendations.",
    ],
    "zh": [
        "本地语料范围有限，所有知识条目均标记为 needs_human_review。",
        "中医辨证通常需要完整病史、检查，以及舌脉等信息。",
        "方剂名称仅作教学示例，不构成治疗建议。",
    ],
    "ko": [
        "로컬 말뭉치는 제한적이며 모든 지식 항목은 needs_human_review로 표시되어 있습니다.",
        "한의학적 변증은 보통 병력, 진찰, 설진·맥진 등의 정보가 필요합니다.",
        "처방 이름은 교육용 예시일 뿐 치료 권고가 아닙니다.",
    ],
}


@dataclass(frozen=True)
class LLMGeneration:
    raw_content: str
    parsed_json: dict[str, Any] | None
    model: str


class LLMProviderError(Exception):
    """A safe, user-displayable provider error with no secrets attached."""


def _context_text(request: TCMConsultRequest) -> str:
    return " ".join(
        value
        for value in request.context.model_dump().values()
        if isinstance(value, str) and value.strip()
    )


class OpenAICompatibleClient:
    _shared_http_client: ClassVar[httpx.AsyncClient | None] = None

    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "siliconflow").strip() or "siliconflow"
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "Qwen/Qwen3-8B").strip()
        self.timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1400"))

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def _http_client(self) -> httpx.AsyncClient:
        shared = type(self)._shared_http_client
        if shared is None or shared.is_closed:
            shared = httpx.AsyncClient(timeout=self.timeout)
            type(self)._shared_http_client = shared
        return shared

    @classmethod
    async def close_shared_http_client(cls) -> None:
        if cls._shared_http_client is not None and not cls._shared_http_client.is_closed:
            await cls._shared_http_client.aclose()
        cls._shared_http_client = None

    async def _post_chat(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        client = self._http_client()
        response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        if response.status_code in {400, 422} and "response_format" in payload:
            retry_payload = dict(payload)
            retry_payload.pop("response_format", None)
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=retry_payload)
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError("LLM provider returned an unreadable response") from exc
        if not isinstance(data, dict):
            raise LLMProviderError("LLM provider returned an unexpected response")
        return data

    async def generate(
        self,
        request: TCMConsultRequest,
        results: list[RetrievalResult],
        citations: list[Citation],
    ) -> LLMGeneration:
        language = detect_language(request.question)
        context_payload = {
            key: value
            for key, value in request.context.model_dump().items()
            if isinstance(value, str) and value.strip()
        }
        evidence_payload = [
            {
                "evidence_id": item.entry.entry_id,
                "matched_terms": list(item.matched_terms),
                "relevance_score": item.score,
                "pattern": item.entry.pattern,
                "rationale": item.entry.rationale,
                "symptoms": item.entry.symptoms,
                "source_ids": list(item.entry.source_ids),
                "evidence_category": item.entry.evidence_category,
                "review_status": item.entry.review_status,
            }
            for item in results
        ]
        citation_payload = [item.model_dump() for item in citations]
        system_prompt = (
            "You are the TCM summary component of a research-only RAG prototype. "
            "Use only the supplied retrieved evidence and source registry. Do not use outside medical knowledge. "
            "Do not diagnose, prescribe, name additional herbs/formulas/acupuncture points, give doses, or recommend starting/stopping medicines. "
            "Every concrete claim must be supportable by the supplied evidence IDs. "
            "If evidence is weak, explicitly say this is only an educational TCM pattern direction. "
            "Return strict JSON with localized_result.en.summary, localized_result.zh.summary, localized_result.ko.summary, and optional claims. "
            "Chinese must be natural Simplified Chinese. Korean must be natural Korean. English must be natural English. "
            "Avoid malformed mixed phrases such as 'CM', '主要CM认为', or English technical labels inside Chinese/Korean prose."
        )
        user_prompt = (
            f"Detected user question language: {language}. Respond to the user's main summary in the same language as the question, "
            "while also providing the three localized summaries requested by the JSON schema.\n\n"
            f"User question:\n{request.question}\n\n"
            f"Optional non-identifying context:\n{json.dumps(context_payload or {'provided': 'none'}, ensure_ascii=False)}\n\n"
            f"Retrieved evidence JSON:\n{json.dumps(evidence_payload, ensure_ascii=False)}\n\n"
            f"Source registry JSON:\n{json.dumps(citation_payload, ensure_ascii=False)}\n\n"
            "Return exactly this shape, with concise 2-3 sentence summaries: "
            '{"localized_result":{"en":{"summary":"..."},"zh":{"summary":"..."},"ko":{"summary":"..."}},"claims":[{"text":"...","evidence_ids":["..."],"claim_type":"pattern_hypothesis"}]}'
        )
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "frequency_penalty": 0.2,
            "max_tokens": min(max(self.max_tokens, 1000), 1800),
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response_data = await self._post_chat(payload, headers)
        except httpx.TimeoutException as exc:
            raise LLMProviderError("LLM provider request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(f"LLM provider returned HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise LLMProviderError("Network error while contacting LLM provider") from exc

        try:
            content = response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("LLM provider returned an unexpected response") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError("LLM provider returned an empty response")
        raw_content = content.strip()
        return LLMGeneration(raw_content=raw_content, parsed_json=_parse_json_object(raw_content), model=self.model)


def _parse_json_object(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = cleaned.replace("**", "").replace("*", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.replace("\ufffd", "")


def _fallback_summaries(results: list[RetrievalResult]) -> dict[ResponseLanguage, str]:
    if not results:
        return {
            "en": "The local TCM knowledge base did not retrieve enough meaningful evidence, so no TCM pattern direction is generated.",
            "zh": "本地中医知识库没有检索到足够相关的证据，因此本次不生成中医辨证方向。",
            "ko": "로컬 한의학 지식베이스에서 충분히 관련 있는 근거를 찾지 못해 한의학적 방향을 생성하지 않습니다.",
        }
    patterns = {
        language: "、".join(item.entry.pattern[language] for item in results[:2]) if language == "zh" else ", ".join(item.entry.pattern[language] for item in results[:2])
        for language in ("en", "zh", "ko")
    }
    return {
        "en": (
            f"Based on the retrieved local evidence, the description overlaps most with {patterns['en']}. "
            "These are educational TCM pattern directions, not diagnoses; more history, examination, tongue and pulse information would be needed."
        ),
        "zh": (
            f"基于本地检索证据，当前描述与{patterns['zh']}等方向有一定重合。"
            "这只是教学性的中医辨证方向，不是诊断；仍需要补充病程、寒热、饮食二便、舌脉和专业评估。"
        ),
        "ko": (
            f"검색된 로컬 근거에 따르면 현재 설명은 {patterns['ko']} 방향과 일부 겹칩니다. "
            "이는 교육용 한의학적 가능 방향이지 진단이 아니며, 병력·진찰·설진·맥진 정보가 더 필요합니다."
        ),
    }


def _extract_localized_summaries(
    generation: LLMGeneration,
    results: list[RetrievalResult],
    response_language: ResponseLanguage,
) -> dict[ResponseLanguage, str]:
    summaries = _fallback_summaries(results)
    parsed = generation.parsed_json or {}
    root = parsed.get("localized_result", parsed) if isinstance(parsed, dict) else {}
    if isinstance(root, dict):
        for language in ("en", "zh", "ko"):
            value = root.get(language)
            candidate = ""
            if isinstance(value, dict):
                candidate = str(value.get("summary", "")).strip()
            elif isinstance(value, str):
                candidate = value.strip()
            if candidate:
                summaries[language] = _clean_text(candidate)
    elif generation.raw_content:
        summaries[response_language] = _clean_text(generation.raw_content)

    if generation.parsed_json is None and generation.raw_content and not generation.raw_content.lstrip().startswith(("{", "[")):
        summaries[response_language] = _clean_text(generation.raw_content)
    return summaries


def _citation_from_source(source: SourceRecord) -> Citation:
    return Citation(
        source_id=source.source_id,
        title=source.title,
        organization=source.organization,
        year=source.year,
        url_or_identifier=source.url_or_identifier,
        section=source.section,
        source_type=source.source_type,
        verification_status="verified" if source.verification_status == "verified" else "needs_review",
    )


def _citations(results: list[RetrievalResult]) -> list[Citation]:
    seen: set[str] = set()
    citations: list[Citation] = []
    for result in results:
        for source_id in result.entry.source_ids:
            if source_id in seen:
                continue
            seen.add(source_id)
            source = SOURCE_REGISTRY.get(source_id)
            if source:
                citations.append(_citation_from_source(source))
    return citations


def _evidence(results: list[RetrievalResult]) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    for result in results:
        first_source = SOURCE_REGISTRY.get(result.entry.source_ids[0]) if result.entry.source_ids else None
        chunks.append(
            EvidenceChunk(
                evidence_id=result.entry.entry_id,
                source=first_source.title if first_source else "Local TCM source registry entry missing",
                source_ids=list(result.entry.source_ids),
                title=result.entry.title("en"),
                source_type=result.entry.source_type,
                snippet=result.entry.snippet("en"),
                relevance_score=result.score,
                matched_terms=list(result.matched_terms),
                evidence_category=result.entry.evidence_category,
                review_status=result.entry.review_status,
                localized=localized_entry_display(result.entry),
            )
        )
    return chunks


def _patterns(results: list[RetrievalResult]) -> list[PossiblePattern]:
    patterns: list[PossiblePattern] = []
    for result in results:
        displays = localized_entry_display(result.entry)
        patterns.append(
            PossiblePattern(
                pattern=result.entry.pattern["en"],
                rationale=result.entry.rationale["en"],
                matching_symptoms=list(result.matched_terms) or list(result.entry.symptoms["en"][:3]),
                evidence_ids=[result.entry.entry_id],
                localized={
                    language: {"pattern": display["pattern"], "rationale": display["rationale"]}
                    for language, display in displays.items()
                },
            )
        )
    return patterns


def _formulas(results: list[RetrievalResult]) -> list[RelatedHerbOrFormula]:
    formulas: list[RelatedHerbOrFormula] = []
    seen: set[str] = set()
    for result in results:
        for formula in result.entry.educational_examples:
            name_en = str(formula.get("name", {}).get("en", ""))
            if not name_en or name_en in seen:
                continue
            seen.add(name_en)
            localized = localized_formula_display(result.entry, formula)
            formulas.append(
                RelatedHerbOrFormula(
                    name=name_en,
                    type=formula.get("type", "formula"),
                    purpose=str(formula.get("description", {}).get("en", "")),
                    safety_warning=FORMULA_WARNING,
                    evidence_ids=[result.entry.entry_id],
                    localized=localized,
                )
            )
    return formulas


def _localized_safety_notes(request: TCMConsultRequest, results: list[RetrievalResult]) -> dict[ResponseLanguage, list[str]]:
    localized = {language: list(notes) for language, notes in BASE_SAFETY_NOTES_LOCALIZED.items()}
    if request.context.medications.strip():
        localized["en"].append("Because current medication was reported, a clinician or pharmacist should check every educational herb/formula example for interactions.")
        localized["zh"].append("由于已填写目前用药，所有教学性中药或方剂示例都应由医生或药师核查相互作用。")
        localized["ko"].append("현재 복용 약이 입력되었으므로 모든 교육용 한약·처방 예시는 의료진 또는 약사가 상호작용을 확인해야 합니다.")
    if request.context.pregnancy.strip() and request.context.pregnancy.casefold() not in {"no", "not pregnant", "n/a"}:
        localized["en"].append("Pregnancy or breastfeeding status was reported; do not use herbal products without obstetric and qualified TCM review.")
        localized["zh"].append("已填写妊娠或哺乳相关信息；未经产科与合格中医专业评估，不要使用中药产品。")
        localized["ko"].append("임신 또는 수유 관련 정보가 입력되었습니다. 산과 및 자격 있는 한의학적 검토 없이 한약 제품을 사용하지 마세요.")
    if request.context.allergies.strip():
        localized["en"].append("Allergies were reported; every ingredient and excipient needs professional verification.")
        localized["zh"].append("已填写过敏信息；每一种成分和辅料都需要专业核对。")
        localized["ko"].append("알레르기 정보가 입력되었습니다. 모든 성분과 부형제는 전문적으로 확인해야 합니다.")
    for language in ("en", "zh", "ko"):
        for result in results:
            note = localized_entry_safety(result.entry, language)
            if note and note not in localized[language]:
                localized[language].append(note)
        localized[language] = localized[language][:8]
    return localized


def _safety_notes_en(localized_safety: dict[ResponseLanguage, list[str]]) -> list[str]:
    return localized_safety.get("en", [])[:8]


def _claims(results: list[RetrievalResult], language: ResponseLanguage, *, abstention: str = "") -> list[Claim]:
    if abstention:
        return [Claim(claim_id="claim_1", text=abstention, evidence_ids=[], claim_type="abstention_reason")]
    claims: list[Claim] = []
    for index, result in enumerate(results[:3], start=1):
        if language == "zh":
            text = f"用户描述与本地证据 {result.entry.entry_id} 中的“{result.entry.pattern['zh']}”教学方向存在重合。"
        elif language == "ko":
            text = f"사용자 설명은 로컬 근거 {result.entry.entry_id}의 '{result.entry.pattern['ko']}' 교육 방향과 일부 겹칩니다."
        else:
            text = f"The user's description overlaps with the educational direction '{result.entry.pattern['en']}' in local evidence {result.entry.entry_id}."
        claims.append(
            Claim(
                claim_id=f"claim_{index}",
                text=text,
                evidence_ids=[result.entry.entry_id],
                claim_type="pattern_hypothesis",
            )
        )
    if results:
        claims.append(
            Claim(
                claim_id=f"claim_{len(claims) + 1}",
                text={
                    "en": "The retrieved sources are terminology or educational summaries and do not establish clinical treatment efficacy.",
                    "zh": "检索来源属于术语或教学资料摘要，不能证明具体治疗有效性。",
                    "ko": "검색된 자료는 용어 또는 교육 요약이며 특정 치료 효과를 입증하지 않습니다.",
                }[language],
                evidence_ids=[item.entry.entry_id for item in results[:3]],
                claim_type="evidence_limitation",
            )
        )
    return claims


def _confidence(status: ScopeStatus, diagnostics: RetrievalDiagnostics, results: list[RetrievalResult]) -> Confidence:
    if status == "safety_critical":
        return Confidence(level="high", score=0.99, reason="A deterministic safety-critical rule matched the question.")
    if status in {"out_of_scope", "insufficient_information"}:
        return Confidence(level="high", score=0.92, reason=f"A deterministic scope rule routed the request to {status}.")
    if status == "evidence_insufficient":
        return Confidence(
            level="medium",
            score=0.74,
            reason=(
                "Retrieval ran, but no evidence passed the configured relevance threshold "
                f"({diagnostics.min_relevance_score:.2f}); generation was blocked."
            ),
        )
    meaningful = diagnostics.meaningful_match_count
    source_diversity = len({source_id for result in results for source_id in result.entry.source_ids})
    score = 0.26 + diagnostics.top_relevance_score * 0.42 + min(meaningful, 4) * 0.06 + min(source_diversity, 3) * 0.03
    if any(result.entry.review_status == "needs_human_review" for result in results):
        score = min(score, 0.68)
    score = round(min(0.86, score), 2)
    if score >= 0.72:
        level = "high"
    elif score >= 0.48:
        level = "medium"
    else:
        level = "low"
    reason = (
        f"Experimental confidence from retrieval signals: {meaningful} meaningful evidence match(es), "
        f"top relevance {diagnostics.top_relevance_score:.2f}, {source_diversity} source id(s). "
        "Confidence is capped when entries still need human review."
    )
    return Confidence(level=level, score=score, reason=reason)


def _retrieval_metadata(diagnostics: RetrievalDiagnostics) -> RetrievalMetadata:
    return RetrievalMetadata(
        retrieval_method=diagnostics.retrieval_method,  # type: ignore[arg-type]
        candidate_count=diagnostics.candidate_count,
        meaningful_match_count=diagnostics.meaningful_match_count,
        top_relevance_score=diagnostics.top_relevance_score,
        min_relevance_score=diagnostics.min_relevance_score,
        retrieval_notes=list(diagnostics.notes),
    )


def _localized_patterns(patterns: list[PossiblePattern], language: ResponseLanguage) -> list[LocalizedResultPattern]:
    items: list[LocalizedResultPattern] = []
    for pattern in patterns[:2]:
        display = pattern.localized.get(language) or pattern.localized.get("en")
        items.append(
            LocalizedResultPattern(
                name=display.pattern if display else pattern.pattern,
                rationale=display.rationale if display else pattern.rationale,
                matched_symptoms=pattern.matching_symptoms[:4],
            )
        )
    return items


def _localized_formulas(formulas: list[RelatedHerbOrFormula], language: ResponseLanguage) -> list[LocalizedResultFormula]:
    items: list[LocalizedResultFormula] = []
    for formula in formulas[:2]:
        display = formula.localized.get(language) or formula.localized.get("en")
        items.append(
            LocalizedResultFormula(
                name=display.name if display else formula.name,
                description=display.purpose if display else formula.purpose,
                warning=display.safety_warning if display else formula.safety_warning,
            )
        )
    return items


def _evidence_summary(language: ResponseLanguage, evidence: list[EvidenceChunk], diagnostics: RetrievalDiagnostics) -> str:
    copy = RESULT_COPY[language]
    if not evidence:
        return copy["evidence_empty"]
    return copy["evidence_summary"].format(count=len(evidence), score=round(diagnostics.top_relevance_score * 100))


def _build_localized_result(
    *,
    generation_source: GenerationSource,
    scope_status: ScopeStatus,
    summaries: dict[ResponseLanguage, str],
    patterns: list[PossiblePattern],
    formulas: list[RelatedHerbOrFormula],
    localized_safety_notes: dict[ResponseLanguage, list[str]],
    evidence: list[EvidenceChunk],
    diagnostics: RetrievalDiagnostics,
) -> dict[ResponseLanguage, LocalizedResultContent]:
    localized: dict[ResponseLanguage, LocalizedResultContent] = {}
    for language in ("en", "zh", "ko"):
        copy = RESULT_COPY[language]
        localized[language] = LocalizedResultContent(
            status_label=copy["status"][generation_source],
            summary_title=copy["summary_title"],
            grounding=copy["grounding"][generation_source],
            summary=summaries[language],
            state_title=copy["state_title"][scope_status],
            state_body=summaries[language] if scope_status != "supported" else "",
            patterns_title=copy["patterns_title"],
            patterns=[] if scope_status != "supported" else _localized_patterns(patterns, language),
            examples_title=copy["examples_title"],
            formulas=[] if scope_status != "supported" else _localized_formulas(formulas, language),
            safety_title=copy["safety_title"],
            safety_notes=localized_safety_notes.get(language, [])[:3],
            evidence_summary=_evidence_summary(language, evidence, diagnostics),
            evidence_title=copy["evidence_title"],
        )
    return localized


def _abstention_summaries(status: ScopeStatus, language: ResponseLanguage, decision: ScopeDecision | None = None) -> dict[ResponseLanguage, str]:
    clarifying = decision.clarifying_questions if decision else ()
    joined_en = " ".join(f"{idx}. {q}" for idx, q in enumerate(clarifying, start=1))
    joined_zh = " ".join(f"{idx}. {q}" for idx, q in enumerate(clarifying, start=1))
    joined_ko = " ".join(f"{idx}. {q}" for idx, q in enumerate(clarifying, start=1))
    if status == "safety_critical":
        return {
            "en": "This question contains safety-critical warning signs. Do not wait for a TCM interpretation; seek urgent professional medical help now.",
            "zh": "这个问题包含可能需要紧急医学评估的危险信号。请不要等待中医辨证解释，应立即寻求专业医疗帮助。",
            "ko": "이 질문에는 긴급 의학적 평가가 필요한 위험 신호가 포함되어 있습니다. 한의학적 해석을 기다리지 말고 즉시 전문 의료 도움을 받으세요.",
        }
    if status == "out_of_scope":
        return {
            "en": "This question is outside the current limited TCM-RAG scope, so the system will not generate TCM patterns, formulas, or treatment advice. Please seek professional assessment or route this to a more appropriate medical module.",
            "zh": "这个问题超出当前 TCM-RAG 的有限研究范围，因此系统不会生成中医证型、方剂或治疗建议。建议优先寻求专业评估，或后续转交更合适的医学模块处理。",
            "ko": "이 질문은 현재 제한된 TCM-RAG 범위를 벗어나므로 한의학적 변증, 처방 예시, 치료 조언을 생성하지 않습니다. 전문 평가를 받거나 더 적절한 의료 모듈로 라우팅해야 합니다.",
        }
    if status == "insufficient_information":
        return {
            "en": "There is not enough symptom detail for evidence-grounded TCM retrieval. Please add a few details before the system attempts a pattern direction. " + joined_en,
            "zh": "目前症状信息不足，无法进行有证据约束的中医检索。请先补充少量关键信息，再尝试生成辨证方向。" + joined_zh,
            "ko": "현재 증상 정보가 부족해 근거 기반 한의학 검색을 수행하기 어렵습니다. 변증 방향을 시도하기 전에 몇 가지 정보를 더 알려주세요. " + joined_ko,
        }
    return {
        "en": "The system did not retrieve meaningful local TCM evidence above the configured threshold, so it abstained instead of asking the LLM to answer from unsupported knowledge.",
        "zh": "系统没有检索到超过阈值的相关本地中医证据，因此选择回避回答，而不是让 LLM 基于无证据知识自由生成。",
        "ko": "설정된 기준을 넘는 관련 로컬 한의학 근거가 검색되지 않아, LLM이 근거 없는 지식으로 답하지 않도록 답변을 보류했습니다.",
    }


def _base_response(
    *,
    request: TCMConsultRequest,
    scope_status: ScopeStatus,
    generation_mode: str,
    generation_source: GenerationSource,
    summaries: dict[ResponseLanguage, str],
    diagnostics: RetrievalDiagnostics,
    results: list[RetrievalResult],
    llm_model: str,
    llm_error: str | None,
    urgent: bool = False,
    abstained: bool = False,
    claims: list[Claim] | None = None,
) -> TCMConsultResponse:
    language = detect_language(request.question)
    evidence = [] if abstained else _evidence(results)
    patterns = [] if abstained else _patterns(results)
    formulas = [] if abstained else _formulas(results)
    citations = [] if abstained else _citations(results)
    localized_safety = _localized_safety_notes(request, [] if urgent else results)
    localized_result = _build_localized_result(
        generation_source=generation_source,
        scope_status=scope_status,
        summaries=summaries,
        patterns=patterns,
        formulas=formulas,
        localized_safety_notes=localized_safety,
        evidence=evidence,
        diagnostics=diagnostics,
    )
    keywords, domains = analyse_query(results)
    metadata = _retrieval_metadata(diagnostics)
    summary = summaries[language]
    return TCMConsultResponse(
        scope_status=scope_status,
        abstained=abstained,
        generation_mode=generation_mode,  # type: ignore[arg-type]
        generation_source=generation_source,
        response_language=language,
        llm_model=llm_model,
        llm_error=llm_error,
        urgent=urgent,
        query_analysis=QueryAnalysis(keywords=keywords, possible_domains=domains),
        summary=summary,
        tcm_perspective=summary,
        claims=claims or _claims(results, language, abstention=summary if abstained else ""),
        patterns=patterns,
        educational_examples=formulas,
        possible_patterns=patterns,
        related_herbs_or_formulas=formulas,
        evidence=evidence,
        citations=citations,
        safety_notes=_safety_notes_en(localized_safety),
        localized_safety_notes=localized_safety,
        localized_result=localized_result,
        confidence=_confidence(scope_status, diagnostics, results),
        limitations=LIMITATIONS_LOCALIZED[language],
        retrieval_metadata=metadata,
        retrieval_method=metadata.retrieval_method,
        candidate_count=metadata.candidate_count,
        meaningful_match_count=metadata.meaningful_match_count,
        top_relevance_score=metadata.top_relevance_score,
        disclaimer=DISCLAIMER,
    )


def _not_run_diagnostics(note: str = "") -> RetrievalDiagnostics:
    return RetrievalDiagnostics(
        retrieval_method="not_run",
        candidate_count=0,
        meaningful_match_count=0,
        top_relevance_score=0.0,
        min_relevance_score=0.0,
        notes=(note,) if note else (),
    )


async def consult(request: TCMConsultRequest) -> TCMConsultResponse:
    started = perf_counter()
    preprocessing_ms = 0.0
    retrieval_ms = 0.0
    embedding_ms = 0.0
    reranking_ms = 0.0
    llm_ms = 0.0

    def finish(response: TCMConsultResponse, post_started: float) -> TCMConsultResponse:
        response.timings = RequestTimings(
            preprocessing_ms=round(preprocessing_ms, 3),
            retrieval_ms=round(retrieval_ms, 3),
            embedding_ms=round(embedding_ms, 3),
            reranking_ms=round(reranking_ms, 3),
            llm_ms=round(llm_ms, 3),
            post_processing_ms=round((perf_counter() - post_started) * 1000, 3),
            total_ms=round((perf_counter() - started) * 1000, 3),
        )
        return response

    preprocessing_started = perf_counter()
    language = detect_language(request.question)
    client = OpenAICompatibleClient()
    llm_model = client.model
    safety = check_emergency(f"{request.question} {_context_text(request)}")
    if safety.urgent:
        preprocessing_ms = (perf_counter() - preprocessing_started) * 1000
        summaries = _abstention_summaries("safety_critical", language)
        post_started = perf_counter()
        response = _base_response(
            request=request,
            scope_status="safety_critical",
            generation_mode="safety",
            generation_source="safety_rule",
            summaries=summaries,
            diagnostics=_not_run_diagnostics(safety.reason),
            results=[],
            llm_model=llm_model,
            llm_error=None,
            urgent=True,
            abstained=True,
        )
        return finish(response, post_started)

    scope = classify_scope(request.question)
    if scope.status in {"out_of_scope", "insufficient_information"}:
        preprocessing_ms = (perf_counter() - preprocessing_started) * 1000
        summaries = _abstention_summaries(scope.status, language, scope)
        post_started = perf_counter()
        response = _base_response(
            request=request,
            scope_status=scope.status,
            generation_mode="rule",
            generation_source="scope_rule",
            summaries=summaries,
            diagnostics=_not_run_diagnostics(scope.reason),
            results=[],
            llm_model=llm_model,
            llm_error=None,
            abstained=True,
        )
        return finish(response, post_started)

    preprocessing_ms = (perf_counter() - preprocessing_started) * 1000
    results, diagnostics = await retrieve(request.question, _context_text(request), entries=KNOWLEDGE_BASE)
    retrieval_ms = diagnostics.total_ms
    embedding_ms = diagnostics.semantic_ms
    reranking_ms = diagnostics.reranking_ms
    if not results:
        summaries = _abstention_summaries("evidence_insufficient", language, scope)
        post_started = perf_counter()
        response = _base_response(
            request=request,
            scope_status="evidence_insufficient",
            generation_mode="abstention",
            generation_source="evidence_gate",
            summaries=summaries,
            diagnostics=diagnostics,
            results=[],
            llm_model=llm_model,
            llm_error=None,
            abstained=True,
        )
        return finish(response, post_started)

    preparation_started = perf_counter()
    summaries = _fallback_summaries(results)
    generation_mode = "mock"
    generation_source: GenerationSource = "mock_fallback"
    llm_error: str | None = None
    citations = _citations(results)
    preprocessing_ms += (perf_counter() - preparation_started) * 1000
    generation: LLMGeneration | None = None
    if client.configured:
        llm_started = perf_counter()
        try:
            generation = await client.generate(request, results, citations)
        except LLMProviderError as exc:
            llm_error = str(exc)
        finally:
            llm_ms = (perf_counter() - llm_started) * 1000
    else:
        llm_error = "LLM_API_KEY is missing"

    post_started = perf_counter()
    if generation is not None:
        summaries = _extract_localized_summaries(generation, results, language)
        generation_mode = "llm"
        generation_source = "siliconflow_llm"
        llm_model = generation.model

    response = _base_response(
        request=request,
        scope_status="supported",
        generation_mode=generation_mode,
        generation_source=generation_source,
        summaries=summaries,
        diagnostics=diagnostics,
        results=results,
        llm_model=llm_model,
        llm_error=llm_error,
        abstained=False,
    )
    return finish(response, post_started)
