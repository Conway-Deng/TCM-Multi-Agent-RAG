# CPAA1 Calibration Fixture Authorship Amendment V1

**Amendment ID**: `CPAA1-CALIBRATION-FIXTURE-AUTHORSHIP-AMENDMENT-V1`  
**Protocol ID**: `CPAA1-REFERENCE-UNIT-PROTOCOL-V1`  
**Frozen Protocol SHA256**: `5ab2f681e605f3bc75ef6e91fa8d864a102aa60e6b14efdda132448845dcb46b`  
**Study ID**: `cross-perspective-advisory-ablation-v1`  
**Effective Date**: 2026-09-30  
**Status**: APPROVED AND FROZEN PROSPECTIVE AMENDMENT  

---

## 1. Prospective and Additive Scope

1. This amendment is strictly prospective and additive.
2. This amendment does NOT edit, replace, or mutate the existing frozen reference-unit protocol (`CPAA1-REFERENCE-UNIT-PROTOCOL-V1`, byte SHA256 `5ab2f681e605f3bc75ef6e91fa8d864a102aa60e6b14efdda132448845dcb46b`). The frozen protocol remains byte-for-byte unchanged.
3. This amendment supersedes ONLY the phrase and rule in Section O of the protocol requiring that the non-study calibration fixture wording itself must be human-authored.

---

## 2. Permitted AI Drafting Boundary

For the eight fictional NON-STUDY Phase 2C-C calibration cases (`CAL-2CC-01` through `CAL-2CC-08`) ONLY:

1. **Permitted AI Drafting**: AI models MAY draft candidate question wording and candidate evidence passages (four synthetic TCM-side passages and four synthetic Western-side passages per case) for the eight planned calibration challenge cases.
2. **Candidate Status**: AI-drafted wording constitutes only raw candidate calibration material. It possesses no scientific or normative authority on its own.
3. **Strict Human Review and Approval**: Before any AI-drafted calibration fixture pack can be frozen, every final case must receive independent human review and explicit human approval across all eight required methodological boundaries.
4. **Honest Authorship Recording**: Human review and approval does NOT permit an AI-drafted fixture to be falsely described, labeled, or attested as "human-authored". The infrastructure must maintain and record truthful provenance reflecting `ai_drafted_human_approved` origin.

---

## 3. Strict Prohibitions on AI Role

AI systems and models MUST NOT:
1. Generate calibration reference units.
2. Annotate or suggest calibration reference units.
3. Provide an answer key or target responses for calibration cases.
4. Provide expected unit counts, distributions, or quotas.
5. Decide unit eligibility, granularity, or boundaries.
6. Decide semantic support, qualifier necessity, or contradiction.
7. Merge, split, or normalize reference units.
8. Classify reviewer disagreements (Type-A vs Type-B).
9. Reconcile or adjudicate reviewer differences.
10. Generate, annotate, or reconcile formal reference units for the study.

Reviewer A and Reviewer B remain strictly HUMAN semantic annotators.
Formal 48-question reference-unit authoring and reconciliation remains strictly HUMAN-ONLY.

---

## 4. Formal Material Isolation and Non-Contamination

1. **Zero Exposure to Formal 48 Material**: Formal 48 question text, packet text, retrieved source passages, formal reference units, or downstream model outputs must NEVER be supplied to the drafting model, included in prompts, or used to construct calibration fixtures.
2. **Fictional and Non-Medical Character**: All calibration challenge cases must remain strictly fictional, synthetic, and non-medical. They must be constructed around artificial or non-clinical domains to exercise protocol boundaries without clinical bias or domain familiarity shortcuts.
3. **No Leakage into Formal Evaluation**: Calibration annotations, exercises, and artifacts never enter formal $M_q$ reference sets.

---

## 5. Invariance of Formal Protocol and Scientific Controls

The following remain entirely unchanged, unamended, and strictly preserved:
1. **Formal Denominator and Endpoints**: No change to formal reference-unit definitions, evaluation endpoints, or metrics.
2. **Formal 48 Study Packets**: No change to formal TCM or Western packets, retrieval outputs, question manifests, or freeze receipts.
3. **Human Reconciliation Controls**: No change to B2A/B2B reconciliation audit infrastructure or frozen human reconciliation rules.
4. **Dual-Submission Lock**: Reviewer A and Reviewer B must independently annotate and mechanically lock their submissions prior to any comparison.
5. **Fail-Closed Mechanical Architecture**: Dual locks, exact duplicate logic, disagreement log hash bindings, and completion gates remain fully enforced.
