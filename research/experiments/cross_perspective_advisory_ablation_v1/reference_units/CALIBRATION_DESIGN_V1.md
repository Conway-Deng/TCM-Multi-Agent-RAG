# CPAA1 Human Reference-Unit Calibration Design V1

Design ID: `CPAA1-REFERENCE-UNIT-CALIBRATION-DESIGN-V1`
Protocol ID: `CPAA1-REFERENCE-UNIT-PROTOCOL-V1`
Protocol Hash: `5ab2f681e605f3bc75ef6e91fa8d864a102aa60e6b14efdda132448845dcb46b`
Study ID: `cross-perspective-advisory-ablation-v1`
Namespace: `cal2cc:`
Status: DESIGN ONLY (INFRASTRUCTURE APPROVED; FIXTURE AUTHORSHIP AMENDMENT APPROVED)
Amendment ID: `CPAA1-CALIBRATION-FIXTURE-AUTHORSHIP-AMENDMENT-V1`

---

## CRITICAL NOTICE: CALIBRATION FIXTURE AUTHORSHIP AND BOUNDARIES

> **AUTHORSHIP AMENDMENT NOTICE**:
> Pursuant to approved prospective amendment `CPAA1-CALIBRATION-FIXTURE-AUTHORSHIP-AMENDMENT-V1`, the earlier requirement that the non-study calibration fixture wording itself must be human-authored is prospectively superseded.
>
> For the eight fictional NON-STUDY Phase 2C-C calibration cases ONLY, candidate question wording and synthetic evidence passages MAY be AI-drafted under strict provenance tracking (`text_origin="ai_drafted_human_approved"`). Prior to freeze, all eight cases require explicit per-case and pack-level HUMAN review, validation, and approval. Human approval does NOT permit describing the text as human-authored.
>
> AI systems MUST NOT generate, annotate, suggest, or reconcile reference units, answer keys, or expected unit counts. Reviewer A and Reviewer B remain strictly HUMAN annotators, and formal 48-question study reference-unit authoring remains strictly HUMAN-ONLY.
>
> All preliminary or synthetic case prose in earlier planning documents (including SOL exploration text) was unverified planning material and MUST NOT be copied into tracked files without passing formal drafting and human approval.

---

## 1. Objective and Scientific Scope

The purpose of this calibration phase (Phase 2C-C) is to establish operational alignment between Reviewer A and Reviewer B on edge cases, boundary distinctions, qualifier attachment, decomposition, and ambiguity handling prior to commencing formal 48-question reference-unit annotation.

Calibration exercises human judgment across exactly eight planned methodological challenge cases. Software tools provide:
- Structural validation of human-authored fixture packs.
- Enforcement of independent reviewer isolation.
- Cryptographic submission snapshotting and locking.
- Gatekeeper verification preventing comparison before dual lock.
- Structured disagreement logging with strict Type-A / Type-B ambiguity tracking.
- Fail-closed verification of completion prerequisites.

The software does NOT:
- Decide unit eligibility, wording, merging, or splitting.
- Adjudicate reviewer disagreements.
- Calculate arbitrary reviewer agreement percentages or select preferred denominators.
- Generate or suggest answer keys.

---

## 2. Eight Planned Calibration Cases and Coverage

The calibration pack requires exactly eight cases designed to stress specific boundaries of `CPAA1-REFERENCE-UNIT-PROTOCOL-V1`:

| Case ID | Primary Methodological Focus | Key Protocol Boundary |
|---|---|---|
| `CAL-2CC-01` | Indispensable qualifiers & source-explicit support | Section D: Qualifier necessity vs optional context; explicit textual support |
| `CAL-2CC-02` | Decomposition & limitation anti-double-counting | Section D & E: Atomic unit boundaries vs over-decomposition; limitation containment |
| `CAL-2CC-03` | Repeated evidence & deduplication | Section F: Handling duplicate facts across multiple passages; deduplication rules |
| `CAL-2CC-04` | Cross-perspective agreement & relational counting | Section G & H: Identifying genuine agreement across paradigms; relational counting |
| `CAL-2CC-05` | Genuine cross-perspective conflict | Section G & H: Direct contradictory claims with overlapping scope |
| `CAL-2CC-06` | Non-comparability & incompatible scope | Section G: Distinguishing non-comparable concepts from contradictory claims |
| `CAL-2CC-07` | No relevant information & packet-bounded absence | Section I: Recognizing complete absence of relevant data within packet bounds |
| `CAL-2CC-08` | Relevant but insufficient information | Section I: Distinguishing insufficient evidence from absence (`07`) or conflict (`05`) |

---

## 3. Reviewer Independence Procedure

1. **Isolation**: Reviewer A and Reviewer B must annotate all eight calibration cases independently without mutual consultation, shared notes, or intermediate comparisons.
2. **Dedicated Workspaces**: Reviewer A operates within a Reviewer A calibration workspace; Reviewer B operates within a Reviewer B calibration workspace.
3. **No Intermediate Peeking**: The software structurally prohibits cross-workspace viewing or comparison until BOTH reviewers have formally locked their submissions.

---

## 4. Submission Locking and Hashing

Prior to comparison or reconciliation, each reviewer must execute a mechanical submission lock:
1. Every case (`CAL-2CC-01` through `CAL-2CC-08`) must be marked `annotation_complete == True`.
2. Each case must have either:
   - One or more structurally valid reference-unit records, OR
   - A non-empty, human-authored `no_supportable_unit_reason`.
3. Every record must structurally validate against the frozen synthetic fixture pack using strict anchor and span coordinates.
4. A deterministic canonical SHA256 hash (`submission_hash`) is computed over the entire submission payload (excluding only `submission_hash`).
5. Once locked, the snapshot is immutable for ordinary API use. Any subsequent edits require creating a newly incremented `submission_version` and relocking.

---

## 5. A/B Comparison Gate

A calibration comparison view may be constructed ONLY when:
- Reviewer A locked snapshot exists and cryptographically verifies.
- Reviewer B locked snapshot exists and cryptographically verifies.
- Both snapshots bind the exact same `fixture_pack_hash` and `calibration_design_id`.
- Roles are strictly confirmed as `reviewer_a` and `reviewer_b`.
- All eight planned case IDs are covered.

If any prerequisite fails, comparison fails closed.

---

## 6. Disagreement Logging and Classification

When Reviewers A and B compare locked calibration submissions, all disagreements are recorded in a Local-Only Calibration Disagreement Log.

Each disagreement must be classified into one of two mutually exclusive categories:
- **`A_CASE_LEVEL`**: Disagreement regarding evidence interpretation, qualifier necessity, or unit scoping under existing frozen rules. Resolved through bilateral reviewer consensus discussion.
- **`B_METHODOLOGICAL_AMBIGUITY`**: Disagreement arising from an unaddressed edge case, ambiguity, or gap in `CPAA1-REFERENCE-UNIT-PROTOCOL-V1`.

### Critical Rule for Type-B Ambiguity
A Type-B disagreement CANNOT be resolved by reviewer consensus alone. It requires:
1. Prospective formulation of an administrative clarification or protocol amendment.
2. A valid, non-empty `clarification_refreeze_id`.
3. An explicit human attestation: `clarification_refreeze_attested == True`.

Until these conditions are met, the disagreement remains OPEN and blocks calibration completion.

---

## 7. No Default Third-Adjudicator Workflow

Calibration is an alignment mechanism between primary reviewers. Unlike the formal study reconciliation protocol (Section K), calibration does NOT employ a third-adjudicator workflow. Disagreements must either be resolved by consensus under existing rules (`A_CASE_LEVEL`) or escalated to formal prospective clarification (`B_METHODOLOGICAL_AMBIGUITY`).

---

## 8. Exit Criteria and Completion Checklist

Calibration completion requires satisfying ALL mechanical prerequisites and human process attestations:
1. Valid frozen human-authored fixture pack (8 cases, 16 packets, 64 evidence items, strictly non-formal IDs).
2. Reviewer A locked submission verified.
3. Reviewer B locked submission verified against the identical fixture pack hash.
4. Zero open disagreements in the disagreement log.
5. All Type-B disagreements accompanied by clarification refreeze ID and attestation.
6. Explicit human attestations confirmed:
   - All eight planned boundary cases reviewed (`all_eight_boundaries_reviewed == True`).
   - The critical `CAL-2CC-05` (conflict) vs `CAL-2CC-07` (absence) vs `CAL-2CC-08` (insufficient) distinction explicitly reviewed (`boundary_05_07_08_distinction_reviewed == True`).
   - Both reviewers agree they can consistently apply the rules (`reviewers_agree_rules_applicable == True`).
   - No calibration artifacts are exposed to downstream research models (`no_calibration_artifact_model_exposed == True`).
   - No numerical agreement threshold or denominator manipulation was used (`no_numerical_agreement_threshold_used == True`).
   - Dual human sign-off (`attestor_a`, `attestor_b`, `attestation_notes`).

---

## 9. Stop Conditions

The mechanical flag `calibration_ready_for_formal_annotation` defaults to `False`. It transitions to `True` ONLY upon successful validation of the complete checklist above.

If any gate fails, formal 48-question reference-unit annotation remains strictly blocked.

---

## 10. Formal Material Separation and Repository Hygiene

- **Strict Namespace Isolation**: All calibration packets use `cal2cc:packet:`, and evidence items use `cal2cc:ev:`. Formal prefixes (`cpaa1:packet:`, `cpaa1:ev:`) and formal question IDs are mechanically rejected.
- **Git-Safe Tracking**: Only design documentation, blank schemas, and neutral synthetic test fixtures are Git-tracked.
- **Local-Only Artifacts**: Populated calibration fixture packs, reviewer submissions, and disagreement logs are strictly Local-Only.
