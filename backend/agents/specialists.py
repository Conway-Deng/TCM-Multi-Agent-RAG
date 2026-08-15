from __future__ import annotations

import hashlib
import time

from schemas.research import ResearchAgentOutput, ResearchCitation, RetrievalItem, StructuredClaim


COMMON_LIMITATIONS = [
    "The corpus is small, provisional, and not expert validated.",
    "Traditional TCM concepts are reported as educational source content, not established biomedical fact.",
    "This output is not a diagnosis, prescription, or treatment instruction.",
]


class SpecialistAgent:
    agent_id = "base"
    agent_name = "TCM Specialist"
    subdomain = "general"
    version = "1.0.0"
    prompt_version = "v1"
    focus_terms: tuple[str, ...] = ()

    def _supports(self, item: RetrievalItem) -> bool:
        haystack = item.chunk_text.casefold()
        return not self.focus_terms or any(term.casefold() in haystack for term in self.focus_terms)

    def _statement(self, item: RetrievalItem, language: str) -> str:
        lines = [line.strip() for line in item.chunk_text.splitlines() if line.strip()]
        if self.agent_id == "herbal":
            examples = [line for line in lines[9:] if len(line) > 40]
            if examples:
                return examples[0]
        rationale_index = {"en": 2, "zh": 5, "ko": 8}.get(language, 2)
        return lines[rationale_index] if len(lines) > rationale_index else lines[-1]

    async def answer(self, question: str, language: str, evidence: list[RetrievalItem], *, provider: str, model: str) -> ResearchAgentOutput:
        started = time.perf_counter()
        relevant = [item for item in evidence if self._supports(item)]
        claims: list[StructuredClaim] = []
        citations: list[ResearchCitation] = []
        for index, item in enumerate(relevant[:3], 1):
            statement = self._statement(item, language)
            claim_id = f"{self.agent_id}-{hashlib.sha256((question + item.chunk_id).encode('utf-8')).hexdigest()[:10]}"
            signal = item.rerank_score or item.semantic_score or item.lexical_score or 0.0
            claims.append(
                StructuredClaim(
                    claim_id=claim_id,
                    text=statement,
                    evidence_ids=[item.chunk_id],
                    claim_type="traditional_educational",
                    reasoning_summary=f"Selected because retrieved chunk {item.chunk_id} matched the {self.subdomain} scope.",
                    confidence=min(0.62, 0.30 + float(signal) * 0.4),
                )
            )
            citations.append(
                ResearchCitation(
                    evidence_id=item.chunk_id,
                    source_id=item.source_id,
                    title=str(item.source_metadata.get("title", item.source_id)),
                    locator=str(item.source_metadata.get("notes", "")),
                    provenance_valid=True,
                )
            )
        abstained = not claims
        safety_flags: list[str] = []
        lowered = question.casefold()
        if any(term in lowered for term in ("dose", "dosage", "prescribe", "处方", "剂量", "用量", "복용량")):
            safety_flags.append("Individualized prescribing or dosing request blocked.")
        confidence = sum(claim.confidence for claim in claims) / len(claims) if claims else 0.0
        return ResearchAgentOutput(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            agent_version=self.version,
            question=question,
            language=language,
            subdomain=self.subdomain,
            claims=claims,
            evidence_ids=list(dict.fromkeys(item.chunk_id for item in relevant[:3])),
            citations=citations,
            uncertainties=["A complete TCM assessment normally requires history and examination details not available here."],
            limitations=[*COMMON_LIMITATIONS, *self.extra_limitations()],
            safety_flags=safety_flags,
            confidence=round(confidence, 4),
            abstained=abstained,
            abstention_reason="No retrieved evidence matched this specialist scope." if abstained else None,
            latency_ms=round((time.perf_counter() - started) * 1000),
            provider=provider,
            model=model,
            prompt_version=self.prompt_version,
            reasoning_summary=f"Evidence selection and structured claim mapping for {self.subdomain}; no hidden reasoning tokens are stored.",
        )

    def extra_limitations(self) -> list[str]:
        return []


class SyndromeDifferentiationAgent(SpecialistAgent):
    agent_id = "syndrome"
    agent_name = "Syndrome Differentiation Agent"
    subdomain = "syndrome_differentiation"
    focus_terms = ("pattern", "syndrome", "辨证", "证", "deficiency", "stagnation")


class HerbalKnowledgeAgent(SpecialistAgent):
    agent_id = "herbal"
    agent_name = "Herbal Knowledge Agent"
    subdomain = "herbal_knowledge"
    focus_terms = ("formula", "herb", "方", "汤", "丸", "散")

    def extra_limitations(self) -> list[str]:
        return ["No dosing, individualized formula, or prescribing instruction is generated."]


class AcupunctureMeridianAgent(SpecialistAgent):
    agent_id = "acupuncture_meridian"
    agent_name = "Acupuncture and Meridian Agent"
    subdomain = "acupuncture_meridian"
    focus_terms = ("acupuncture", "meridian", "针", "经络", "point")

    def extra_limitations(self) -> list[str]:
        return ["No needling locations, depths, techniques, or procedural instructions are generated."]


class ConstitutionAgent(SpecialistAgent):
    agent_id = "constitution"
    agent_name = "Constitution Agent"
    subdomain = "constitution"
    focus_terms = ("constitution", "体质", "deficiency", "heat", "cold")


class DietaryTherapyAgent(SpecialistAgent):
    agent_id = "dietary_therapy"
    agent_name = "TCM Dietary Therapy Agent"
    subdomain = "dietary_therapy"
    focus_terms = ("food", "diet", "digestion", "食", "胃", "脾")

    def extra_limitations(self) -> list[str]:
        return ["Traditional food-property concepts are distinct from modern nutritional evidence."]


class LifestyleYangshengAgent(SpecialistAgent):
    agent_id = "lifestyle_yangsheng"
    agent_name = "Lifestyle and Yangsheng Agent"
    subdomain = "lifestyle_yangsheng"
    focus_terms = ("sleep", "stress", "fatigue", "season", "失眠", "压力", "乏力")

    def extra_limitations(self) -> list[str]:
        return ["Any lifestyle content is conservative educational information, not a clinical prescription."]


class SingleRAGAgent(SpecialistAgent):
    agent_id = "single_rag"
    agent_name = "TCM Single RAG Baseline"
    subdomain = "general_tcm_rag"
