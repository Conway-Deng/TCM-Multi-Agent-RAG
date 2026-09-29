# Cross-Perspective MediRAG Advisory-Ablation Study v1

> [!CAUTION]
> **PREFLIGHT INFRASTRUCTURE ONLY — FORMAL EXECUTION HAS NOT STARTED.**  
> No provider API calls have been made, no formal retrieval has run, no questions have been finalized, no evidence packets have been generated, and no evaluations have been scored. This directory contains offline preflight and verification infrastructure only.

---

## 1. Scientific Purpose

This study investigates whether exposing structured perspective-local advisory signals and cross-perspective relational criticism to the Governance synthesis agent improves the yield of usable, fully grounded medical information in cross-perspective health consultation.

The experiment tests four conditions:
- **G0 (Baseline):** Section A = identical frozen evidence; Section B = present with empty/no visible advisory content (`perspective_advisory: {"tcm": [], "western": []}`, `critic_relations: []`).
- **G1 (Local Advisory Only):** Governance receives fixed evidence packets and frozen local advisory signals (Evidence Specialist, Coverage Auditor, Grounding Skeptic) from both TCM and Western perspectives; Critic omitted.
- **G2 (Critic Only):** Governance receives fixed evidence packets and frozen Cross-Perspective Critic relational statements (without local advisory context visible to Governance). *Note: The Critic itself was produced upstream using the frozen local assessments.*
- **G3 (Full Pipeline):** Governance receives fixed evidence packets, frozen local advisory signals, and frozen Cross-Perspective Critic relational statements.

The primary confirmatory comparison is **G3 minus G0** on the **usable, fully grounded coverage yield** endpoint.

---

## 2. Experimental Phase Order

The exact approved operational study lifecycle order is:
1. **Question Population Selection (Pre-Retrieval):**
   - 48 questions selected across 4 topic domains (cough, dyspepsia, headache, constipation; 12 per topic).
   - Stratified across 3 task types (evidence description, cross-perspective synthesis, boundary/uncertainty; 4 per topic).
   - Prospective lock: No question may be substituted after retrieval.
2. **Formal Evidence Retrieval & Freeze (`CPAA1-R0-LEXICAL-V1`):**
   - Run R0 BM25 lexical retrieval once per perspective on complete, verified research corpora (`top_k = 4`).
   - Query text: EXACT frozen question text (no rewriting, no topic filtering, no synonym expansion).
   - Candidate universes: Complete TCM Research Corpus v1 (4,461 chunks) and complete Western PMC Pilot Corpus v0.1 (271 chunks).
   - Zero-score retention: zero-score chunks are retained up to `top_k=4`; ties broken by ascending corpus-record ordinal.
   - Weak retrieval remains observed benchmark output; questions must not be replaced or rewritten after retrieval.
   - Raw retrieval records archived before downstream evidence packet construction.
3. **Formal Packet Generation & Packet Freeze:**
   - Deterministically project raw retrieval hits into immutable native `FrozenEvidencePacket` pairs and compatibility wrappers.
   - Validate integrity and canonical SHA256 hashes.
4. **Human Reference-Unit Freeze:**
   - Prospectively define reference units ($M_q \ge 1$) for each question.
   - Frozen strictly **BEFORE ANY downstream generated output** (prior to running local agents, Critic, or Governance).
   - Human evaluation artifacts designed for blinded ground-truth assessment.
   - Strictly condition-independent, inaccessible to all research models, bound to evidence IDs/source spans where appropriate.
   - **NOT** retrieval hits, **NOT** packet claims.
5. **Perspective-Local Advisory Freeze:**
   - Execute Evidence Specialist (`Qwen3-8B`), Coverage Auditor (`GLM-4-9B-0414`), and Grounding Skeptic (`GLM-Z1-9B-0414`) once per perspective.
   - Freeze all assessments and failure states.
6. **Cross-Perspective Critic Freeze:**
   - Execute Cross-Perspective Critic (`DeepSeek-R1-0528-Qwen3-8B`) once per eligible question using frozen packets and assessments.
   - Freeze critique and precondition status.
7. **Governance Execution Matrix (G0–G3, 384 Cells):**
   - 48 questions $\times$ 4 conditions (G0, G1, G2, G3) $\times$ 2 repetitions = 384 Governance cells.
   - Model held fixed: `THUDM/GLM-4-9B-0414`.
8. **Blinding & Evaluation Export:**
   - Strip condition and repetition identifiers; generate deterministic opaque `blind_id`s.
   - Store blind key separately.
9. **Blinded Human Scoring & Audit:**
   - Reviewer A scores all 384 blinded outputs.
   - Reviewer B audits a stratified sample of 12 questions (96 outputs).
10. **Reconciliation & Full Second Review Gate Check:**
    - Calculate discrepancy rate between Reviewer A and Reviewer B.
    - If $> 10\%$ primary score delta on audit sample, trigger `FULL_SECOND_REVIEW_REQUIRED`.
11. **Unblinding & Statistical Analysis:**
    - Average the two repetitions per question $\times$ condition cell.
    - Compute paired $G3 - G0$ differences and 20,000-resample topic-stratified question bootstrap 95% CIs.

---

## 3. What Is Frozen

- **Baseline Code & Orchestration:** Commit `bb043bfe4505821e7e55e022f633e410e91ea5aa` (tag `cross-perspective-v0.4-patch3-dev`).
- **Research Corpora:**
  - TCM Research Corpus v1: 4,461 chunks, SHA256 `316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9`.
  - MediRAG-West v0.1 Pilot Corpus: 271 chunks, SHA256 `8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b`.
- **Model Assignments:**
  - Governance: `THUDM/GLM-4-9B-0414`
  - Critic: `deepseek-ai/DeepSeek-R1-0528-Qwen3-8B`
  - Evidence Specialist: `Qwen/Qwen3-8B`
  - Coverage Auditor: `THUDM/GLM-4-9B-0414`
  - Grounding Skeptic: `THUDM/GLM-Z1-9B-0414`
- **Schemas and Prompts:** Patch 3 Governance and Critic schemas and prompt contracts.
- **Statistical Specification:** Question-level paired analysis, 20,000 bootstrap resamples, nested repetitions.

---

## 4. What Is NOT Yet Generated

- The final 48 questions (only empty template / schemas exist).
- Formal evidence retrieval outputs and packet pairs.
- Upstream advisory assessments and Critic outputs.
- Governance outputs for the 384 cells.
- The final blind key and human evaluation scores.

---

## 5. Commands for Future Execution Stages

Once the prospective study is approved and real reviewers are confirmed, future execution will proceed in strict order:

```bash
# 1. Preflight validation of corpora, schemas, and environment
python -m pytest backend/tests/test_advisory_ablation_study.py

# 2. Preflight verification tool
python -m research.experiments.cross_perspective_advisory_ablation_v1.preflight

# 3. Generate execution plan (384 deterministic cells)
python -m research.experiments.cross_perspective_advisory_ablation_v1.execution_plan --export-plan

# 4. (FUTURE) Formal retrieval freeze
# python -m research.experiments.cross_perspective_advisory_ablation_v1.runners.freeze_retrieval

# 5. (FUTURE) Upstream advisory & critic freeze
# python -m research.experiments.cross_perspective_advisory_ablation_v1.runners.freeze_advisory

# 6. (FUTURE) Governance cell execution
# python -m research.experiments.cross_perspective_advisory_ablation_v1.runners.run_governance_cells

# 7. (FUTURE) Blinding export for human reviewers
# python -m research.experiments.cross_perspective_advisory_ablation_v1.blinding --export-blinded

# 8. (FUTURE) Reconciliation & statistical analysis
# python -m research.experiments.cross_perspective_advisory_ablation_v1.statistics --run-analysis
```

---

## 6. Phase 1E: Packet & Governance Amendment Implementation

Under amendment `CPAA1-PACKET-GOVERNANCE-AMENDMENT-V1` and native contract `CPAA1-FROZEN-PACKET-LOSSLESS-V1`:
- **Dry Preflight Command:**
  ```powershell
  $env:PYTHONPATH="backend;."; .\.venv\Scripts\python.exe research/experiments/cross_perspective_advisory_ablation_v1/packet_runner.py
  ```
- **Formal Packet Generation Unauthorized:** Formal packet generation is **NOT** authorized in Phase 1E. The execution guard `--execute-formal-packet-generation` fails closed.
- **Local-Only Future Packet Artifacts:** The future formal packet JSONL artifacts (`packets/tcm_packets.jsonl` and `packets/western_packets.jsonl`) will contain source-derived full passage texts and **must remain strictly local-only** (uncommitted and untracked). Only safe, text-free metadata receipts (`packet_manifest.json` or `packet_freeze_receipt.json`) may be committed.
