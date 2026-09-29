# Cross-Perspective MediRAG Advisory-Ablation Study v1

## Status: FINAL PROTOCOL — IMPLEMENTATION LOCK

**Study ID:** `cross-perspective-advisory-ablation-v1`  
**Repository:** `Conway-Deng/TCM-Multi-Agent-RAG`  
**Frozen Baseline Tag:** `cross-perspective-v0.4-patch3-dev`  
**Frozen Baseline Commit:** `bb043bfe4505821e7e55e022f633e410e91ea5aa`  
**Research Branch:** `research/cross-perspective-advisory-ablation-v1`  

---

## 1. Scientific Objective & Boundaries

### 1.1 Objective
This study investigates the mechanistic contribution of Governance-visible advisory signals to multi-agent cross-perspective health consultation synthesis. Specifically, it evaluates whether exposing prospective-local advisory signals (Evidence Specialist, Coverage Auditor, Grounding Skeptic) and cross-perspective relational critique (Cross-Perspective Critic) to the Governance agent improves the yield of usable, fully grounded medical information compared to an unguided baseline.

### 1.2 Fixed Conditioning
The main study estimates the effect of Governance-visible advisory context conditional on:
1. Fixed evidence packets retrieved once before synthesis.
2. One realized perspective-local advisory assessment set per question.
3. One realized Cross-Perspective Critic artifact per question.

A separate, later robustness study may explore variability arising from upstream artifact regeneration. Such robustness analyses must remain separate from this primary study and cannot be pooled.

### 1.3 Scope & Medical Boundaries
- This is a research-only computational benchmark evaluating multi-agent orchestration and grounding fidelity.
- It makes **no clinical efficacy claims**, **no treatment recommendations**, and **no medical superiority inferences**.
- Historical study observations from RQ1, RQ4, Research B, and Research C are independent and must **not** be pooled with this study. Prior study A3 remains incomplete and is not treated as a result.

---

## 2. Evidence Layer & Retrieval Freeze

### 2.1 Research Evidence Corpora
- **TCM Evidence Asset:**
  - Corpus: **TCM Research Corpus v1**
  - Chunks: ~4,461 chunks
  - Frozen SHA256: `316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9`
  - Location: `research/corpus/tcm_v1/chunks.jsonl`
  - *Constraint:* The 16-entry Patch 3 compatibility fixture (`backend/tcm/knowledge_base.py`) is for runtime/demo compatibility only and must **NOT** be used as the formal-study TCM evidence population. Raw/source TCM material is restricted local research infrastructure; redistribution is prohibited.
- **Western Evidence Asset:**
  - Corpus: **MediRAG-West PMC Open Access Pilot Corpus** (`medirag-west-v0.1-pilot`)
  - Sources: 16 systematic review articles across 4 topics
  - Chunks: 271 chunks
  - Frozen SHA256: `8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b`
  - Location: `research/corpus/west_v0_1/chunks.jsonl`

### 2.2 Retrieval Protocol
- **Retrieval Algorithm ID:** `CPAA1-R0-LEXICAL-V1`
- **Candidate Universes:**
  - **TCM:** Complete, verified TCM Research Corpus v1 (4,461 chunks).
  - **Western:** Complete, verified MediRAG-West PMC Open Access Pilot Corpus v0.1 (271 chunks).
  - Full-corpus unfiltered search (`topics=None`). No topic routing, no candidate filtering, no threshold gating, no source diversification, no fallback corpus.
- **Query Contract:**
  - `query_text` is the EXACT frozen `question_text`.
  - Prohibitions: No strip rewriting, no LLM rewriting, no synonym expansion, no translation, no topic/task prefixes, no router substitution, no entity-anchor query, no reflection search.
  - Topic and task type are archival metadata only and must NOT constrain retrieval.
- **Scoring & Ranking Contract:**
  - Primary strategy: R0 BM25 lexical ($k_1 = 1.5, b = 0.75$, exposed scores rounded to 6 decimal places).
  - Primary parameter: `top_k = 4` per question per perspective.
  - Ties broken strictly by ascending original corpus-record ordinal (0-indexed order of nonblank records in SHA-bound JSONL).
  - Zero-score retention: zero-score records are retained and ranked (ranks filled up to 4). Zero-score retrieval is a valid weak outcome, not an error.
  - Raw retrieval records must be fully archived before downstream evidence packet construction.
  - Weak retrieval remains observed benchmark output; questions must NOT be replaced or rewritten after retrieval.
- **Retrieval Invariance:**
  - Retrieval configuration, exact query string, text preprocessing, ordering, tie-breaking, filters, selected chunks, and provenance links are executed **once** and frozen.
  - Retrieval occurs **strictly prior to condition execution**. Conditions G0–G3 must **NEVER** rerun retrieval.

### 2.3 Fixed Evidence Unit
- The immutable unit is the complete validated pair:
  $$\text{Evidence Unit}_q = \langle \text{PerspectiveEvidencePacket}_{\text{TCM}}, \text{PerspectiveEvidencePacket}_{\text{Western}} \rangle$$
- Each packet preserves:
  - Exact claim IDs and claim text
  - Support status (`supported`, `partially_supported`, `insufficient`)
  - Evidence references and provenance records (source ID, chunk ID, URL, license, section, excerpt)
  - Missing information, limitations, uncertainty
  - Failure metadata (if any)
  - Deterministic canonical serialization hash
- Governance evidence boundary: Governance continues to use the existing Patch 3 packet projection (`build_governance_payload`, omitting interpretation and provenance while projecting usable claims). Governance evidence boundary must not be expanded.

### 2.4 Prospective Amendment Linkage: CPAA1-PACKET-GOVERNANCE-AMENDMENT-V1
> [!NOTE]
> **PROSPECTIVE AMENDMENT NOTICE (Approved 2026-09-29):**
> Under independent review by Astra (verdict: `APPROVE AMENDMENT AS WRITTEN`, required changes: `NONE`), the study enacts formal amendment [`CPAA1-PACKET-GOVERNANCE-AMENDMENT-V1`](PACKET_GOVERNANCE_AMENDMENT_V1.md) governing the evidence packet layer and research prompt adaptations.
>
> **Prospectively Superseded Clauses:**
> 1. **§2.3 (Fixed Evidence Content Restriction):**
>    Historical evidence-content restriction is superseded **ONLY** to allow the approved full frozen source passages through the existing compatible projection fields (`claim_kind="source_excerpt"`, `claim_text = exact full frozen chunk text`, `support_status="supported"`). Interpretation and provenance remain strictly omitted from Governance's existing Section A projection (`build_governance_payload`).
> 2. **§5.1 (Historical Governance System-Prompt Lock):**
>    Historical Governance system-prompt lock is superseded **ONLY** by the approved CPAA1 research prompt variant (`CPAA1_GOVERNANCE_SYSTEM_PROMPT`). Upstream role prompts are superseded **ONLY** by the explicitly approved research variants/deltas in `prompt_variants.py`. No other prompt, schema, or objective change is authorized.
> 3. **Historical Truncation:**
>    Supersedes legacy Western runtime character slicing at 2,000 characters, requiring full-text lossless preservation across all 384 hit occurrences (including 20 passages >2,000 characters).
>
> Historical text is preserved; the protocol is not rewritten as though the amendment existed from study start. All other protocol definitions (endpoints, G0–G3 definitions, stratification, blinding architecture, statistical bootstrap analysis) remain strictly unchanged.

---

## 3. Question Population & Topic Stratification

### 3.1 Population Size & Structure
The study population consists of exactly **48 questions** balanced across four medical topic domains (12 questions per topic):
1. **Cough** ($n = 12$)
2. **Dyspepsia / Digestive Symptoms** ($n = 12$)
3. **Headache** ($n = 12$)
4. **Constipation** ($n = 12$)

### 3.2 Task-Type Balance
Within each topic domain ($n = 12$), questions are equally allocated across three task types (4 questions each):
- **Evidence-description questions** ($n = 4$): Inquire about direct evidence findings within individual frameworks.
- **Cross-perspective synthesis / comparability questions** ($n = 4$): Inquire about relationship, agreement, or divergence across frameworks.
- **Limitation / uncertainty / boundary questions** ($n = 4$): Inquire about evidence gaps, boundary conditions, or unanswerable aspects.

### 3.3 Prospective Selection Rule
- Question selection occurs **strictly before** formal retrieval.
- **No question may be replaced** after selection due to weak retrieval, non-comparability, inconvenient results, or poor model performance.

---

## 4. Advisory & Critic Freeze

### 4.1 Perspective-Local Advisory Suite
For each question $q$, the six advisory roles are executed exactly **once** on the frozen evidence packets:
- **TCM:**
  1. Evidence Specialist (`Qwen/Qwen3-8B`)
  2. Coverage Auditor (`THUDM/GLM-4-9B-0414`)
  3. Grounding Skeptic (`THUDM/GLM-Z1-9B-0414`)
- **Western:**
  1. Evidence Specialist (`Qwen/Qwen3-8B`)
  2. Coverage Auditor (`THUDM/GLM-4-9B-0414`)
  3. Grounding Skeptic (`THUDM/GLM-Z1-9B-0414`)
- **Immutability:**
  - Advisory assessments are frozen upon generation.
  - Roles are **never** regenerated due to poor or incomplete answers.
  - Failures and missing roles are recorded in `failed_roles` and preserved.

### 4.2 Cross-Perspective Critic
- Executed exactly **once** per eligible question using frozen packets and frozen local assessments.
- **Model:** `deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` (strictly enforced; no model substitution; DeepSeek-V3.2 is prohibited).
- **Settings:** `thinking_behavior = "send_false"`, `timeout = 240.0s`, `max_tokens = 1400`.
- **Preconditions & Failure Isolation:**
  - Evaluated deterministically (`not_applicable`, `skipped_insufficient_assessments`, `completed`, `failed`).
  - Valid empty relation sets (`{"relations": []}`) are preserved.
  - Critic failure or skipped state is preserved; no semantic repair or fallback critic is permitted.

---

## 5. Experimental Conditions (G0–G3 Contract)

The four experimental conditions manipulate **only** what Governance can see. All other pipeline elements (prompts, evidence packets, model configuration, retry logic) are 100% identical.

| Condition | Fixed Evidence Packets | Local Advisory Projection | Critic Critique Projection | Description |
| :--- | :---: | :---: | :---: | :--- |
| **G0** | Yes (Section A) | **None** (`{}`) | **None** (`None`) | Baseline Governance without advisory context; Section A = identical frozen evidence; Section B = present with empty/no visible advisory content |
| **G1** | Yes (Section A) | **Frozen Local** | **None** (`None`) | Governance with perspective-local advisory signals only |
| **G2** | Yes (Section A) | **None** (`{}`) | **Frozen Critic** | Governance with cross-perspective critic signals only* |
| **G3** | Yes (Section A) | **Frozen Local** | **Frozen Critic** | Full advisory pipeline |

*\*Important:* In G2, the Critic artifact was still generated upstream using the frozen local advisory assessments. G2 must **not** be described as an architecture developed without local agents; it is an ablation of Governance-visible advisory context.

### 5.1 Governance Configuration
- **Model:** `THUDM/GLM-4-9B-0414`
- **Settings:** `thinking_behavior = "omit"`, `timeout = 90.0s`, `max_tokens = 2400`.
- **Prompts & Schemas:** Governed by research prompt variant `CPAA1_GOVERNANCE_SYSTEM_PROMPT` (narrowly superseding the historical lock per §2.4) and `CrossPerspectiveDraft` schema.
- **Zero Leakage:** No condition-specific prompt rewriting or condition indicators may leak into Governance prompts.

---

## 6. Execution Matrix & Unit of Analysis

### 6.1 Repetitions & Cells
- **Design:** 48 questions $\times$ 4 conditions (G0, G1, G2, G3) $\times$ 2 repetitions = **384 Governance cells**.
- **Unit of Analysis:** The **QUESTION** is the independent analysis unit.
- **Nested Observations:** The two repetitions per (question, condition) cell are **nested repeated observations**, not independent cases. Output scores are averaged at the question level prior to statistical comparison.

---

## 7. Endpoints & Metrics

### 7.1 Primary Confirmatory Endpoint: Usable, Fully Grounded Coverage Yield

The exact approved operational study lifecycle order is:
1. Formal packet generation
2. Packet freeze
3. Human reference-unit freeze (frozen BEFORE ANY downstream generated output)
4. Local-agent generation
5. Critic generation
6. Governance generation
7. Blinded human semantic evaluation

For each question $q$, a set of $M_q \ge 1$ reference units is defined prospectively:
- Frozen strictly **BEFORE ANY downstream generated output** (prior to running local agents, Critic, or Governance).
- Human evaluation artifacts designed for blinded ground-truth assessment.
- Strictly **condition-independent** across G0, G1, G2, and G3.
- Completely **inaccessible to all research models** at all times.
- Bound to native evidence IDs and source spans where appropriate.
- **NOT** retrieval hits.
- **NOT** packet claims.

For a generated Governance output $Y_{q, c, r}$:
$$\text{Yield}(Y_{q, c, r}) = \begin{cases} \frac{\text{Fully Conveyed Reference Units}}{M_q} & \text{if Output passes Full-Grounding Gate} \\ 0 & \text{otherwise} \end{cases}$$

**Full-Grounding Gate Conditions:**
An output passes the gate if and only if:
1. It is structurally usable (valid JSON conforming to `CrossPerspectiveAnswer`).
2. It contains substantive content (non-empty substantive summaries/agreements/differences).
3. **EVERY** scored substantive claim is fully supported by the underlying source evidence.

**Zero-Score Hard Gates:**
- Terminal generation failure $\to 0$
- Structurally invalid / contract violation $\to 0$
- Zero substantive claims $\to 0$
- Any unsupported substantive claim $\to 0$
- Any contradicted substantive claim $\to 0$
- Any partially supported substantive claim $\to 0$ (fails full-grounding gate)

### 7.2 Secondary Metrics
- Unsupported + contradicted substantive claim fraction
- Partially supported substantive claim fraction
- Unconditional reference coverage
- Conditional coverage among usable outputs
- Packet adherence
- Original-source grounding
- TCM and Western perspective representation
- Agreement / difference / non-comparability representation
- Uncertainty preservation
- Source-map / structural traceability (kept separate from semantic support)
- Usable-answer rate
- Failure classes, retry counts, latencies, tokens, and model call counts
- Answer length and atomic claim counts

---

## 8. Statistical Analysis Plan

### 8.1 Confirmatory Primary Comparison
The **ONLY** confirmatory hypothesis test is:
$$\Delta_{\text{primary}} = \text{Mean}(\text{Yield}_{G3}) - \text{Mean}(\text{Yield}_{G0})$$
evaluated on the question-level paired differences:
$$D_q = \bar{Y}_{q, G3} - \bar{Y}_{q, G0} \quad \text{where } \bar{Y}_{q, c} = \frac{1}{2}\sum_{r=1}^2 \text{Yield}(Y_{q, c, r})$$

### 8.2 Primary Reporting
- G0 question-level mean
- G3 question-level mean
- Paired question-level mean difference ($G3 - G0$)
- 95% topic-stratified question bootstrap confidence interval (percentile bootstrap, 20,000 resamples, frozen deterministic seed)
- Whole questions are resampled with all conditions and repetitions attached.
- No label-swap randomization test. No Holm correction on the single primary comparison.

### 8.3 Secondary Mechanism Comparisons
- $G1 - G0$
- $G2 - G0$
- $G3 - G1$
- $G3 - G2$
All secondary comparisons are strictly **exploratory and descriptive**.

---

## 9. Blinded Human Evaluation & Audit Protocol

### 9.1 Evaluation Mode
Primary semantic scoring is conducted via **blinded human source-grounded evaluation**. Automated language models (including GPT-5.6 Sol or GPT-6 Astra) are **prohibited** as formal evaluators.

### 9.2 Blinding Architecture
- Outputs are decoupled from condition labels ($G0, G1, G2, G3$) and repetition indices ($r1, r2$) using deterministic opaque IDs.
- Blind keys are stored separately from evaluation workbooks.

### 9.3 Reviewer Roles & Independent Audit
- **Reviewer A:** Performs primary blinded scoring across all 384 outputs.
- **Reviewer B:** Conducts independent blinded audit on a prospectively selected stratified sample:
  - 12 questions total (3 questions randomly selected from each of the 4 topics).
  - All 8 outputs per selected question ($4 \text{ conditions} \times 2 \text{ repetitions}$).
  - Total audited outputs = **96**.
  - Reviewer B also audits any cases flagged with explicit uncertainty by Reviewer A.

### 9.4 Reconciliation & Full Second Review Gate
- Discrepancies between Reviewer A and Reviewer B are reviewed and reconciled.
- If reconciliation changes the primary yield score for **more than 10% of audited outputs** ($> 9$ out of 96 outputs):
  $$\text{Status} \gets \textbf{FULL\_SECOND\_REVIEW\_REQUIRED}$$
  Final unblinding and analysis are blocked until all 384 outputs undergo complete double scoring and reconciliation.

---

## 10. Operational Dependency Notice

> [!WARNING]
> **UNRESOLVED OPERATIONAL DEPENDENCY:**  
> A qualified human Reviewer B must be formally identified and contracted prior to the initiation of human semantic evaluation.  
> The research software and preflight verification infrastructure may be built now. However, formal semantic evaluation must **NOT** be declared operational until this second human reviewer requirement is satisfied or a separately approved prospective protocol amendment is enacted.

---

## 11. Serialization & Packet Writer Status (Phase 1F Non-Execution Checkpoint)

- **Serialization Contract:** Linked to `CPAA1-PACKET-SERIALIZATION-V1` (canonical JSON, UTF-8, no BOM, LF-only, exact 48-question physical manifest sequence).
- **Writer Implementation:** Pure deterministic packet writer (`packet_writer.py`) and serialization library (`packet_serialization.py`) exist and have passed comprehensive preflight and tampering regression validation.
- **Authorization Gate:** Formal packet generation remains **unauthorized** in Phase 1F. Real packet output files do not yet exist.
- **Next Step:** SOL review of writer implementation before prospective authorization of formal packet generation.
