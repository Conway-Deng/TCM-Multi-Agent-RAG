# CPAA1-PACKET-GOVERNANCE-AMENDMENT-V1: Formal Packet and Governance Conditioning Amendment

## Metadata
- **Amendment Identifier:** `CPAA1-PACKET-GOVERNANCE-AMENDMENT-V1`
- **Native Packet Contract:** `CPAA1-FROZEN-PACKET-LOSSLESS-V1`
- **Status:** `APPROVED_FOR_IMPLEMENTATION`
- **Specification Date:** 2026-09-29
- **Research Branch:** `research/cross-perspective-advisory-ablation-v1`
- **Pre-Amendment HEAD:** `b76da900abd465acab99890f03763f8d5d7f93ad`
- **Historical Baseline Commit:** `bb043bfe4505821e7e55e022f633e410e91ea5aa`
- **Historical Baseline Tag:** `cross-perspective-v0.4-patch3-dev`
- **Independent Astra Review Verdict:** `APPROVE AMENDMENT AS WRITTEN`
- **Required Astra Review Changes:** `NONE`

---

## 1. Executive Summary & Prospective Timing

This formal amendment specifies the lossless evidence packet construction contract (`CPAA1-FROZEN-PACKET-LOSSLESS-V1`) and research prompt adaptations for the Cross-Perspective MediRAG Advisory-Ablation Study v1. 

**Prospective Timing:** This amendment is enacted strictly **after** the completion and verification of the deterministic raw retrieval freeze (Phase 1C/1C-D) and strictly **before** formal packet materialization, upstream advisory execution, or Governance condition generation.

---

## 2. Frozen Input Retrieval Anchors

The amendment binds directly to the frozen raw retrieval outputs from Phase 1C:

- **TCM Raw Retrieval Artifact:** `research/experiments/cross_perspective_advisory_ablation_v1/retrieval/retrieval_tcm_r0_top4.jsonl`  
  **Byte SHA256:** `a82cd4894465cfabaf9de7fd47fde7afd2a956580230e14cf1797fe02ee97d40`  
  **Structure:** Exactly 48 question records, 192 total hit occurrences.
- **Western Raw Retrieval Artifact:** `research/experiments/cross_perspective_advisory_ablation_v1/retrieval/retrieval_western_r0_top4.jsonl`  
  **Byte SHA256:** `a1933bba57d2c28609af19473954064fee4d7f1429717dfd93fe0e06bdd2f379`  
  **Structure:** Exactly 48 question records, 192 total hit occurrences.
- **Question Manifest:** `research/experiments/cross_perspective_advisory_ablation_v1/question_manifest.jsonl`  
  **Byte SHA256:** `a7daead783134ef6c2d4e5632153c19a8aa4a826a3c172838de90172796f9bbf`  
  **Structure:** Exactly 48 selected questions.

---

## 3. Historical Context & Motivation

### 3.1 Historical Western `[:2000]` Truncation
In earlier pilot stages (such as Western Stage C runtime adapters), retrieved source chunks were subjected to character truncation (`[:2000]`). In the frozen Western retrieval dataset of 192 hits, exactly **20 hit occurrences exceed 2,000 characters**. Arbitrary string slicing risks severing clinical context, dosage qualifications, and contraindication statements mid-sentence.

### 3.2 Historical TCM Teaching / Template Distinction
In historical TCM prototypes, chunks were alternately represented through template-expanded summaries or raw dictionary records.

### 3.3 Prospective Full-Text Lossless Representation
Under `CPAA1-FROZEN-PACKET-LOSSLESS-V1`, all character slicing, string truncation, text stripping, sentence extraction, summarization, or rewrite transformations are **strictly prohibited**. The exact full-text byte content of each retrieved chunk is preserved verbatim into native evidence items.

---

## 4. Native Evidence & Packet Identity Contract

### 4.1 Native Evidence Items
Each of the 384 frozen retrieval hit occurrences maps one-to-one to an immutable `FrozenEvidenceItem`:
- Exact preservation of `rank` (1..4), `retrieval_score`, `score_is_zero`, `chunk_id`, and `corpus_record_ordinal`.
- Exact full `chunk_text`, verified via `chunk_text_sha256` and `chunk_record_canonical_sha256`.
- Exact preservation of all source metadata, DOI, PMCID, URL, licensing, and provenance records (including `None` values where absent).
- Research metadata fields:
  - `support_basis = "verbatim_source_copy"`
  - `semantic_support_status = "not_assessed"`

### 4.2 Deterministic Identifier Namespaces
- **Native Evidence ID:**
  `cpaa1:ev:<question_id>:<perspective>:R0:<rank>:<chunk_id>`
  *Semantics:* Identifies a specific question-retrieval hit occurrence. If the same chunk appears in two distinct questions, each occurrence receives a distinct, unique `evidence_id`.
- **Compatibility Wrapper Claim ID:**
  `cpaa1:sx:<evidence_id>`
- **Packet ID:**
  `cpaa1:packet:<question_id>:<perspective>`

---

## 5. Compatibility Projection & Structural-Only Status Semantics

### 5.1 Compatibility Source-Passage Wrapper
To maintain full backwards-compatibility with Patch 3 schemas without mutating production codebase pipelines, each `FrozenEvidenceItem` projects deterministically into a `PerspectiveClaim`:
- `claim_id = "cpaa1:sx:" + item.evidence_id`
- `claim_kind = "source_excerpt"`
- `claim_text = item.exact_chunk_text` (verbatim, untruncated)
- `support_status = "supported"`
- `evidence_refs = [EvidenceReference(...)]` linking exact chunk and source identifiers.

### 5.2 Crucial Semantic Clarification: Structural "Supported" vs. Semantic Entailment
In this research compatibility container:
- The legacy value `support_status="supported"` signifies **ONLY** that the item is a **STRUCTURALLY ELIGIBLE VERBATIM SOURCE EXCERPT** faithfully extracted from the frozen corpus.
- It does **NOT** signify:
  - That semantic entailment of every proposition in the passage was verified.
  - That any downstream inferred claim is true.
  - That the text is clinically correct or medically approved.
  - That human grounding review was conducted.
- No generated interpretations, missing-information claims, or synthetic derived claims are injected.

---

## 6. Research Prompt Adaptations

To condition upstream advisers, the Critic, and Governance to treat `source_excerpt` entries as passage containers rather than atomic claims, research-only prompt variants are constructed without modifying production prompt constants.

### 6.1 Shared Research Source-Passage Contract Clarification
All five research system prompts insert the following clarification **EXACTLY ONCE**, immediately following their opening role-identification sentence:

> "RESEARCH SOURCE-PASSAGE CONTRACT: Entries with claim_kind=\"source_excerpt\" are verbatim source-passage containers and may contain multiple propositions. Their claim_id identifies a passage occurrence, not an atomic semantic claim. For these entries, legacy support_status=\"supported\" means only that the passage was faithfully copied from and linked to the supplied frozen evidence. It does not mean that every proposition was semantically verified, that any generated statement is entailed, that the passage is clinically correct, or that human grounding review occurred. \"Usable\" means structurally eligible for consideration, not relevant or semantically certified. Assess what the passage actually supports for the assigned task; do not treat its status or citation presence as independent entailment certification. Retain the existing exact-ID rules and do not change packet statuses."

### 6.2 Evidence Specialist Exact Delta
- **Target to Replace:**
  `Your purpose is to identify the strongest and most useful ALREADY-SUPPORTED claims inside the supplied evidence packet.`
- **Replacement:**
  `Your purpose is to identify the strongest and most useful structurally eligible source-passage entries inside the supplied evidence packet.`

### 6.3 Grounding Skeptic Exact Delta
- **Target to Replace:**
  `Inspect claim_text against linked evidence excerpts in provenance to identify overstatement, weak support, ambiguity, partial support, or uncertainty, and flag insufficient claims where appropriate.`
- **Replacement:**
  `Inspect the supplied source passages and linked provenance to identify overstatement risks, limits of support, ambiguity, or uncertainty relevant to the question. Identical claim_text and provenance excerpt establish faithful copying only, not semantic support for an inferred answer. Report concerns through the existing advisory schema; do not rewrite passages or change packet statuses.`

### 6.4 Coverage Auditor, Critic, Governance Prompts
These three roles receive **only** the shared research source-passage clarification insertion. No other wording is altered.

---

## 7. Experimental Condition Invariance (G0–G3)

- **Section A Invariance:** Across all four study conditions (G0, G1, G2, G3), the Section A evidence projection received by Governance is strictly identical:
  - Identical passage IDs
  - Identical full `claim_text`
  - Identical `support_status` ("supported")
  - Identical `claim_kind` ("source_excerpt")
  - Identical presentation order
- **Advisory Modulation (Section B):**
  - **G0:** Section A = identical frozen evidence; Section B = present with empty/no visible advisory content (`perspective_advisory: {"tcm": [], "western": []}`, `critic_relations: []`).
  - **G1:** Local advisory signals included; Critic omitted (empty).
  - **G2:** Critic relational statements included; local advisory omitted (empty).
  - **G3:** Full advisory context (local advisory signals + Critic).

---

## 8. Token-Budget Stop Policy & Scaffolding

Given untruncated full-text passages (including 20 passages >2,000 characters), token consumption must be guarded.
- Offline preflight scaffolding inspects prompt length, estimated token counts, and model context limits without making network calls.
- If tokenizer or model context metadata is unavailable offline, the status must report `NOT_YET_CLEARABLE`.
- If prompt size exceeds safe context margins during later execution, execution must halt rather than truncate evidence.

---

## 9. Prospective Reference Units Timing & Lifecycle

The exact approved operational study lifecycle order is:
1. Formal packet generation
2. Packet freeze
3. Human reference-unit freeze (frozen BEFORE ANY downstream generated output)
4. Local-agent generation
5. Critic generation
6. Governance generation
7. Blinded human semantic evaluation

Reference units ($M_q \ge 1$) for evaluating the primary endpoint (usable, fully grounded coverage yield) are:
- Frozen strictly **BEFORE ANY downstream generated output** (prior to running local agents, Critic, or Governance).
- Human evaluation artifacts designed for blinded ground-truth assessment.
- Strictly **condition-independent** across G0, G1, G2, and G3.
- Completely **inaccessible to all research models** at all times.
- Bound to native evidence IDs and source spans where appropriate.
- **NOT** retrieval hits.
- **NOT** packet claims.

---

## 10. Narrowly Superseded Protocol Clauses

This amendment prospectively and narrowly supersedes relevant historical locks as follows:
1. **PROTOCOL.md §2.3 (Fixed Evidence Content Restriction):**
   - Historical evidence-content restriction is superseded **ONLY** to allow the approved full frozen source passages through the existing compatible projection fields (`claim_kind="source_excerpt"`, `claim_text = exact full frozen chunk text`, `support_status="supported"`).
   - Interpretation and provenance remain strictly omitted from Governance's existing Section A projection (`build_governance_payload`).
2. **PROTOCOL.md §5.1 (Historical Governance System-Prompt Lock):**
   - Historical Governance system-prompt lock is superseded **ONLY** by the approved CPAA1 research prompt variant (`CPAA1_GOVERNANCE_SYSTEM_PROMPT`).
   - Upstream role prompts are superseded **ONLY** by the explicitly approved research variants/deltas in `prompt_variants.py`.
   - No other prompt, schema, or objective change is authorized.
3. **Historical Truncation:**
   - Supersedes legacy Western runtime character slicing at 2,000 characters, requiring full-text lossless preservation across all 384 hit occurrences.

Historical text is preserved; the protocol is not rewritten as though the amendment existed from study start. All other components of PROTOCOL.md (endpoints, G0–G3 definitions, stratification, blinding architecture, statistical bootstrap analysis) remain strictly unchanged.

---

## 11. Implementation Prerequisites

Prior to executing formal packet generation, the following preflight requirements must be met:
1. Pure deterministic projection module implemented and unit tested.
2. Research prompt variants constructed and verified by exact UTF-8 hash map.
3. Test suite verifying all contract assertions passes.
4. Absence of formal packet files verified.
5. All raw retrieval artifacts remain local-only and uncommitted.
