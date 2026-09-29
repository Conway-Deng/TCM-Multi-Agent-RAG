# Final Human Reference-Unit Protocol Specification

## Identification and Administrative Provenance

- **Protocol ID**: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
- **Study**: cross-perspective-advisory-ablation-v1
- **Status**: FROZEN BEFORE FORMAL REFERENCE CONSTRUCTION
- **Packet Freeze Implementation Commit**: ff582c9db59966fa5282420d9c4480b16158736b
- **Packet Metadata Checkpoint Commit**: 9d0f25869b284bc5d47baa3af142d3001373199c

---

## Section A: Operational Definition

A reference unit is one question-relevant, independently scorable substantive information target that a high-quality answer could reasonably convey, supported solely by the supplied frozen evidence and retaining all qualifications necessary for faithful meaning.

“Substantive” means materially answering the frozen question or establishing a specific boundary on what the evidence permits answering.

“Independently scorable” means full conveyance of the target can be judged without requiring another independently valuable information target. Necessary attribution, scope, and qualifications remain part of the target.

References apply to the frozen 48 questions and their paired TCM/Western packets. They are constructed after packet freeze and frozen before any downstream generated output.

---

## Section B: Inclusion/Exclusion

Every proposed unit must pass five human assessments:

1. Relevance to the actual frozen question.
2. Support for its complete meaning from the frozen evidence.
3. Preservation of necessary scope and qualifications.
4. Distinctness from other included targets.
5. Consistent scorability.

Apply these evidence rules:

| Evidence situation | Inclusion rule |
|---|---|
| Direct support | Include the supported, relevant proposition. |
| Partial or qualified support | Include only a fully supported narrower or qualified target. |
| Contradictory evidence | Preserve relevant opposing findings and justified relationships without choosing a preferred conclusion. |
| Specific uncertainty or limitation | Include when independently informative and supported. |
| Missing requested information | Include a substantive packet-bounded boundary only after the required inspection and justification. |
| Irrelevant content | Exclude regardless of rank, detail, or apparent truth. |

Outside medical knowledge cannot supply missing content or inferential premises. Retrieval rank and structural `support_status` do not establish relevance or semantic support.

The reference set represents information needed to answer the question, rather than a summary of every retrieved passage.

---

## Section C: Decomposition/Granularity

Use the smallest self-contained, question-relevant information target that preserves necessary attribution, scope, and qualifications.

Split a compound only when each resulting target contributes distinct information beyond qualifying or restating the other. Grammatical separability alone does not justify splitting.

An inherently relational target may remain one unit even when expressing it requires both constituent propositions. When full coverage of that relationship necessarily conveys those propositions, they receive no separate denominator credit. Only additional, independently relevant content may be counted separately.

Apply these defaults:

| Combination | Treatment |
|---|---|
| Effect + population | One population-qualified target. |
| Effect + time horizon | One temporally scoped target. |
| Intervention + outcome | One intervention–outcome target; independently relevant distinct outcomes may be separate. |
| Finding + indispensable limitation | One qualified target. |
| Benefit + harm | Separate when each is independently relevant and supported. |
| TCM indication + indispensable evidence qualification | One appropriately attributed and qualified target. |
| Western finding + certainty qualifier | One qualified target. |
| Explicit cross-stream disagreement | One relational target when the relationship is the substantive target. |

A separate methodological or population boundary is eligible only when it adds information beyond what is required to cover another unit.

Record disputed decompositions and their resolutions. Granularity must never be chosen to obtain a preferred unit count.

---

## Section D: Cross-Perspective Rules

Relevant TCM-only and Western-only information may enter independently. Neither equal numbers nor symmetry are required.

Before asserting agreement or conflict, humans assess these dimensions where relevant:

- construct or proposition;
- intervention/exposure;
- outcome;
- population;
- temporal scope;
- epistemic status, including indication, description, association, intervention finding, or uncertainty.

Record each applicable dimension as `compatible`, `incompatible`, or `unspecified` in the support rationale or local audit record.

Agreement is limited to shared supported scope. Conflict requires incompatible propositions within sufficiently shared scope. Silence, missing evidence, different terminology, and different evidence types alone do not establish conflict. Similarity or lack of conflict does not establish equivalence.

Complementary information can be represented without asserting comparability.

A non-comparability or insufficient-information target does not require successful prior alignment. It must identify the specific incompatible or missing dimension preventing the requested comparison.

---

## Section E: Limitations/Uncertainty

A limitation is eligible when it is specific, question-relevant, supported, independently informative, and non-duplicative.

Source-stated limitations require supporting spans. Packet-derived boundaries require documented inspection and reasoning limited explicitly to the supplied evidence.

Distinguish:

- no relevant information;
- insufficient information to establish the requested conclusion;
- conflicting information.

These are different evidential situations. Conflicting findings must not be relabeled as absence.

A separate limitation unit is permitted only when it adds information beyond what must already be conveyed for full coverage of another content, relationship, or limitation unit.

If covering an existing unit necessarily conveys the proposed limitation, merge it or omit the separate count. Apply this rule to broad limitations and their narrower components.

Generic “more research is needed” is ineligible without a specific, supported, relevant boundary.

---

## Section F: Deduplication

Deduplicate substantive meaning with its necessary scope.

Repeated passages, multiple sources, near-duplicate conclusions, and repeated limitations do not create additional units. One unit may have several supporting anchors.

A proposition appearing in both streams remains one unit when its substantive target and scope are the same. Preserve both streams’ anchors. Distinct attribution or scope warrants separate units only when that distinction independently contributes to answering the question.

Do not retain a compound or relational unit alongside constituent targets that it necessarily covers. Do not merge meaningfully distinct populations, outcomes, or boundaries merely because wording is similar.

Humans decide semantic duplication. Mechanical tools may flag exact matches for review.

---

## Section G: Evidence Anchoring

Each evidence anchor contains:

| Field | Contract |
|---|---|
| `packet_id` | Exact frozen packet ID. |
| `packet_canonical_sha256` | Frozen packet self-hash. |
| `perspective` | `tcm` or `western`. |
| `evidence_id` | Exact evidence occurrence ID. |
| `chunk_text_sha256` | Hash of the anchored frozen text. |
| `anchor_role` | `supporting_span`, `contrasting_span`, or `scope_audit`. |
| `spans` | Array of `{start, end}` coordinates. |

Coordinates are zero-based, half-open Unicode code-point offsets into the parsed, unmodified `exact_chunk_text`. They are neither UTF-8 byte positions nor UTF-16 positions. Require valid non-empty intervals within the text. No normalization is allowed.

Ordinary content requires supporting spans. Multiple discontiguous spans and multiple evidence items are permitted. Relational targets require pertinent evidence from both streams.

For `cross_span_synthesis`, the human rationale states what each span contributes and the limited inference connecting them. It cannot supply an unstated medical premise. Anchors must retain sufficient context for qualification and attribution.

For `packet_bounded_absence`, record:

- the precise requested information assessed;
- all eight inspected evidence IDs;
- why the frozen evidence does not establish that information.

Use `scope_audit` anchors for the inspection universe; their span arrays may be empty. An empty array does not establish absence by itself.

Provenance metadata may establish identity, attribution, and recorded scope. Metadata alone cannot establish efficacy, substantive findings, certainty, or cross-stream agreement/conflict.

Reference text remains accountable to its anchors. An unsupported reference is invalid even if its coordinates and hashes are mechanically correct.

---

## Section H: Schema

Retain the existing semantic fields:

| Field | Meaning / permitted values |
|---|---|
| `schema_version` | `cpaa1_reference_unit_v1` |
| `study_id` | `cross-perspective-advisory-ablation-v1` |
| `question_id` | Exact frozen question ID. |
| `reference_unit_id` | Deterministic final ID. |
| `unit_text` | Human-authored information target. |
| `unit_type` | `content`, `relationship`, `limitation`, `evidence_gap` |
| `perspective_scope` | `tcm`, `western`, `both` |
| `evidence_anchors` | Non-empty array under Section G. |
| `support_scope` | `source_explicit`, `cross_span_synthesis`, `packet_bounded_absence` |
| `required_qualifiers` | Indispensable semantic qualifications; empty only when none are necessary. |
| `support_rationale` | Human explanation of support, synthesis, comparison, or absence. |
| `review_status` | `draft`, `disputed`, `reconciled` |

Only `reconciled` records enter the final reference freeze.

`perspective_scope` describes the substantive target. It does not describe every perspective inspected during `scope_audit`. Thus, a TCM-specific gap may still have audit anchors covering all eight passages.

A substantive `both` target requires pertinent anchors from both streams. `packet_bounded_absence` is restricted to `evidence_gap` or `limitation`.

Final IDs use `cpaa1:ru:<question_id>:<three-digit ordinal>`, with colon escaping consistent with the packet identifier contract. Final ordinals are assigned after reconciliation.

Keep reviewer identities, original submissions, exclusions, additions, and split/merge decisions in the local audit record. Do not include condition labels or future output identities.

Mechanical integrity hashes may accompany serialized records as specified in Section Q; they introduce no additional semantic target.

---

## Section I: M_q Rule

$M_q$ is the number of distinct, eligible, reconciled, frozen reference units for question $q$.

All units receive equal weight. Indispensable qualifiers and additional supporting anchors do not increase $M_q$. The same frozen $M_q$ applies to every condition and repetition.

Retain $M_q \ge 1$. No fixed unit quota is imposed.

A substantive limitation may be the only unit if it independently passes relevance, support, distinctness, and scorability tests. It cannot be manufactured to satisfy the denominator requirement.

If no eligible substantive target can be established, assign `REFERENCE_SET_UNESTABLISHABLE` and apply Section S.

---

## Section J: Reviewer Workflow

Reviewer A and Reviewer B independently construct complete reference sets from scratch for all 48 questions using identical frozen inputs.

Record their qualifications and conflicts. Do not describe the work as clinician adjudication unless clinicians actually perform it.

Neither reviewer sees the other’s annotations until both submissions are locked and hashed. Preserve both original submissions.

Construction, reconciliation, and final reference freeze occur before any local-adviser, Critic, Governance, or G0–G3 output. This reference workflow leaves the existing downstream blinded output-scoring design unchanged.

---

## Section K: Reconciliation/Adjudication

Compare A’s and B’s substantive targets, including omissions, wording, eligibility, anchors, decomposition, type, and perspective scope.

Perform a question-to-evidence completeness check across all eight frozen passages. Every passage need not produce a unit.

Any newly identified target must be recorded as a reconciliation addition, supported by frozen evidence, accompanied by relevance/support reasoning, and explicitly reviewed by both A and B.

The final set is not an automatic union. Reconciliation must not target maximum agreement, either reviewer’s denominator, or a preferred count.

Unresolved disagreements go to a prospectively designated third human adjudicator. The adjudicator applies frozen rules and records a reasoned resolution. The adjudicator cannot invent eligibility, granularity, weighting, or scoring rules.

If resolving a dispute requires a new methodological rule, stop reference freeze. Record and freeze a prospective clarification, preserve earlier submissions, and apply it consistently to every affected question before resuming.

---

## Section L: Blinding/Leakage

Construction reviewers may see frozen questions, both packets, and interpretation-relevant provenance. They cannot see downstream outputs, condition identities, model answers, or scoring results.

Reference material remains inaccessible to research models.

Reference-semantic information includes unit texts, qualifiers, rationales, counts/$M_q$, and reconciliation decisions. It cannot influence prompts, examples, adviser/Critic/Governance instructions, condition implementation, output selection, retries, or regeneration decisions.

Personnel with reference access may participate in execution preparation only through mechanical work that does not use reference semantics. Document this boundary when personnel overlap.

Before downstream generation, mechanically validate every model-visible input against the approved input allowlist. Reference information must not enter prompts, indexes, model-accessible files, payloads, examples, or model-visible logs.

Blinded evaluators may access the frozen references for scoring. They cannot access condition/repetition keys. Every output uses the same frozen reference version. Reference access must not reveal condition identity.

Separate construction and scoring personnel remain optional.

---

## Section M: Wording

Use concise, neutral wording faithful to evidence and relevant to the question.

Preserve population, intervention/exposure, outcome, direction, temporal scope, attribution, certainty, and boundaries whenever omission changes meaning. Distinguish traditional indications from intervention findings.

Do not imply stronger efficacy, persistence, causality, equivalence, safety, or generalizability than the evidence supports.

`unit_text` and `required_qualifiers` contain only semantic information required for coverage. Evidence anchors and rationales explain justification; reproducing them is not an additional answer-content requirement.

---

## Section N: Later Coverage Relation

A generated answer fully covers a unit when it conveys the complete target and indispensable qualifications without material distortion. Semantic equivalence is sufficient; exact wording is unnecessary.

Information may appear across multiple answer locations. Partial mention, omitted mandatory qualifications, or citation presence alone does not count. A quotation alone, rejection of the target, or material contradiction does not establish full coverage.

Count each unit at most once per output. Keep semantic coverage separate from grounding.

The existing endpoint remains:

$$\operatorname{Yield}(Y) = \begin{cases} K_q / M_q, & \text{if the existing usability, substantive-content, and full-grounding gates pass}, \\ 0, & \text{otherwise}. \end{cases}$$

No accepted wording or mandatory qualifier may be added after outputs are seen. A subsequently discovered reference defect triggers an incident and suspension of affected scoring. Do not silently revise unit text, $M_q$, or scoring requirements.

---

## Section O: Calibration

Use prospectively defined human-authored synthetic or other non-study material. Do not consume any of the 48 formal questions or alter the frozen candidate population.

Calibration must cover qualifications, decomposition, repeated evidence, conflicts, non-comparability, and packet-bounded absence.

A and B annotate independently and reconcile rule disagreements. Resolve all calibration rule disagreements before formal construction. No arbitrary agreement percentage is required.

If calibration requires clarification, record and refreeze the affected protocol/template rules before formal construction. Calibration annotations never contribute to formal denominators.

---

## Section P: Automation Boundary

Mechanical infrastructure may display/export packets, calculate coordinates, assign IDs, validate schemas and anchors, flag exact duplicates, count records, calculate hashes, and create separate reviewer files.

Human reviewers author targets, determine support and relevance, assess comparability, split/merge units, reconcile, and adjudicate.

Models must not generate, rewrite, merge, split, select, semantically label, or adjudicate actual reference units. Tooling cannot prepopulate proposed semantic content or make relevance decisions.

---

## Section Q: Freeze Artifacts

Eventually freeze:

- `reference_units.jsonl` — local-only.
- Original reviewer submissions and reconciliation/adjudication audit — local-only.
- `reference_unit_manifest.json` — potentially Git-safe after actual-content inspection.
- `reference_unit_freeze_receipt.json` — potentially Git-safe after actual-content inspection.
- Protocol and blank schema/template — Git-safe if free of populated source-derived content.

Order final units by frozen question-manifest order, then reconciled ordinal. Do not reorder during later verification.

Retain CPython 3.12.14 canonical serialization: `ensure_ascii=False`, `sort_keys=True`, `separators=(",", ":")`, `allow_nan=False`; strict UTF-8, no BOM, physical LF termination.

For final serialized unit records, the mechanical field `reference_unit_canonical_sha256` contains the canonical hash after removing only that field. The ordered aggregate hashes the array of complete records with only their self-hash fields removed, without a trailing newline. File byte hashes use exact bytes. Manifest canonical and byte hashes are distinct. The receipt’s byte hash is calculated externally; the receipt has no self-reference.

Manifest/receipt metadata bind:

- frozen protocol and schema/template hashes;
- question-manifest hash;
- both packet byte and aggregate hashes;
- packet-manifest byte/canonical hashes and external packet-receipt hash;
- packet implementation commit `ff582c9db59966fa5282420d9c4480b16158736b`;
- reference-freeze implementation identity;
- 48-question completeness, per-question $M_q$, total units, and type/scope counts;
- completed independent review, reconciliation, and pre-generation freeze attestations.

Git-safe metadata excludes unit texts, qualifiers, rationales, quotations, source metadata, and passage offsets. Exact failure explanations remain local-only; study-status metadata may record affected opaque question IDs, non-semantic reason codes, and local audit hashes.

No unit counts are predetermined.

---

## Section R: Freeze Order

1. Record and freeze this final protocol specification.
2. Freeze schema, blank templates, calibration materials/procedure, and audit structures.
3. Complete non-study reviewer calibration.
4. Resolve and refreeze any necessary clarifications before formal construction.
5. A and B independently construct all 48 reference sets.
6. Lock and hash both submissions.
7. Reconcile, perform completeness checks, and adjudicate.
8. Validate and freeze final reference units, manifest, and receipt.
9. Permit downstream generation only after reference freeze and clearance of all remaining execution gates.

The existing token-budget gate continues to block downstream model execution while `NOT_YET_CLEARABLE`; it does not block human annotation.

---

## Section S: Study-Readiness Failure Policy

`REFERENCE_SET_UNESTABLISHABLE` is a study-readiness failure, not a question-exclusion criterion.

If unresolved for any frozen question:

- block final reference-set freeze and downstream generation;
- retain all 48 questions;
- report that no confirmatory primary estimate is available under the current protocol;
- record affected IDs and reasons;
- do not analyze a reduced population, impute $M_q$, assign workaround zero yields, or drop/replace questions.

Proceeding under a different population or denominator requires a separately identified prospective scientific amendment that discloses the original readiness failure.

Unresolved disputes requiring new methodological rules similarly block freeze until the prospective clarification is recorded and consistently applied.

---

## Section T: Administrative Freeze Statement

- This protocol was frozen prospectively prior to formal reference construction.
- No formal reference units, candidate reference units, or populated unit texts existed at the time of this freeze.
- No downstream generated outputs (G0/G1/G2/G3) existed at the time of this freeze.
- No local adviser, Cross-Perspective Critic, or Governance model outputs existed at the time of this freeze.
- After this protocol freeze, any methodological clarification required before formal reference construction must be documented prospectively, the affected protocol/template rules must be refrozen before formal construction resumes, and the clarification must be applied consistently to all affected questions. Any change to the frozen question population, M_q/denominator policy, or other locked confirmatory design element requires a separately identified prospective scientific amendment.
- All subsequent human reference construction, calibration, reconciliation, and scoring must adhere strictly to this frozen protocol specification.
