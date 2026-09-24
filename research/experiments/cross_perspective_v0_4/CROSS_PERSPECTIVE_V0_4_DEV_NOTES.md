# Cross-Perspective MediRAG v0.4 Development Notes

## Baseline Reference

- **Frozen v0.3 baseline commit**: `184632557c35b335fb88fbad349db0456be76500`
- **Frozen v0.3 baseline tag**: `cross-perspective-v0.3-dev-baseline`
- **Current branch**: `feature/medirag-multi-agent-v0.4`

## Patch 2 Purpose: Perspective-Local Structured Advisory Agents

Patch 2 introduces an advisory reasoning layer after perspective evidence collection has concluded and prior to Governance synthesis:

- **Evidence Pathway Execution**: TCM and Western evidence packets are retrieved and built from fixed, provenance-linked evidence records.
- **Perspective-Local Advisory Analysis**: Active and available packets are independently and concurrently analyzed by three specialized advisory agents.
- **Fixed Baseline Synthesis**: Governance receives the exact same baseline evidence packets as in v0.3.

### Three Perspective Advisory Roles

1. **Evidence Specialist** (`evidence_specialist`):
   - Identifies the strongest and most useful already-supported claims within the packet.
   - May select only existing claim IDs with `support_status != "insufficient"`.
   - Constrained to the smallest sufficient subset of claims while preserving uncertainty.
   - Prohibited from inventing medical facts, adding new claims, changing support status, or retrieving new evidence.

2. **Coverage Auditor** (`coverage_auditor`):
   - Inspects whether the available packet contains useful claims that may be overlooked, visible redundancy, or visible coverage gaps inside the supplied packet.
   - Constrained to coverage gaps detectable from within the supplied packet (not external medical knowledge).
   - Prohibited from using outside medical knowledge to declare missing content.

3. **Grounding Skeptic** (`grounding_skeptic`):
   - Challenges weak or overstated claim-to-evidence relationships by comparing claim text against linked evidence excerpts.
   - Identifies overstatement, weak support, ambiguity, partial support, or uncertainty, and flags insufficient claims.
   - Prohibited from determining clinical truth, introducing outside knowledge, or rewriting claims.

### Fixed Development Model Assignments

- **Evidence Specialist**: `Qwen/Qwen3-8B` (`thinking_behavior: "send_false"`)
- **Coverage Auditor**: `THUDM/GLM-4-9B-0414` (`thinking_behavior: "omit"`)
- **Grounding Skeptic**: `THUDM/GLM-Z1-9B-0414` (`thinking_behavior: "send_false"`)

Model identities are strictly verified upon provider response.

### Scientific Boundaries & Governance Isolation in Patch 2

- **Advisory Outputs Are NOT Evidence**: The original packet claims and provenance remain the only substantive evidence anchors. Advisory outputs do not become citations, chunks, or evidence rows.
- **Zero Governance Impact**: Perspective assessments are trace and research data only in Patch 2. Governance inputs, prompts, source-map construction, and grounding validators remain scientifically identical to the v0.3 baseline.
- **Deterministic Validation Outside LLM**: All advisory outputs are strictly validated outside the model for perspective match, role match, claim ID existence, non-insufficient references, and issue claim existence. Unknown claim IDs cause hard semantic failure without retry.
- **Local Failure Isolation**: A failure in any advisory agent role is isolated to that role, marked in `failed_roles` as `{perspective}:{role}`, and does not halt sibling advisory roles, the opposing perspective, or baseline Governance.

### Methodological Scope

- **No Formal Experiment**: This patch represents development runtime and orchestration implementation only; no formal benchmark or experiment has started.
- **No Clinical Correctness Claims**: No clinical or medical validity claims are made.
- **No Model Superiority Inferences**: Passing tests and telemetry observations establish structural and runtime software correctness only, and do not support claims of model superiority or inferiority.

---

## Patch 3: Cross-Perspective Critic and Controlled Advisory Integration with Governance

### Overview

Patch 3 introduces the cross-perspective critic agent (`cross_perspective_critic`) and controlled advisory signal integration into Governance synthesis, completing the v0.4 advisory pipeline.

### Scientific Role & Boundaries of Cross-Perspective Critic

1. **Role and Purpose**:
   - Compares evidence-supported claims and local advisory audit signals across TCM and Western perspectives.
   - Identifies cross-perspective relations of three strict types:
     - `possible_agreement`: both perspectives present evidence supporting compatible conclusions.
     - `possible_difference_or_conflict`: perspectives offer differing, divergent, or conflicting conclusions/mechanisms.
     - `not_directly_comparable`: perspective claims address distinct aspects of the condition/question and cannot be directly equated or contrasted.
2. **Strict Grounding Constraints**:
   - Must cite exact claim IDs from both perspectives (1 to 4 claims per perspective).
   - Only claims with `support_status != "insufficient"` may be cited.
   - Maximum 4 relations total; empty list returned when no relations apply.
   - Prohibited from inventing claims, medical facts, mechanisms, citations, or evidence.
   - Validated deterministically outside the LLM; invalid IDs or extra fields result in hard semantic failure without retry.

### Fixed Critic Model Assignment

- **Model**: `deepseek-ai/DeepSeek-R1-0528-Qwen3-8B`
- **Thinking Behavior**: `send_false`
- **Timeout**: 240.0 seconds
- **Max Tokens**: 1400

### Deterministic Critic Preconditions

Critic execution is governed by explicit preconditions:
- `not_applicable`: When either perspective packet is not available, not selected, has execution_status in {"unavailable", "not_selected"}, or contains 0 usable (`support_status != "insufficient"`) claims. Degraded-but-usable packets with non-null failure metadata remain eligible if usable claims exist.
- `skipped_insufficient_assessments`: When both packets are usable, but either perspective produced 0 successful local advisory assessments.
- When all preconditions pass, the Critic runs. Successful execution produces status `"completed"`; failure produces status `"failed"`.

### Controlled Governance Advisory Context Projection

Governance synthesis receives two explicitly separated prompt sections:
1. **Section A (Primary Evidence)**: The compact semantic evidence packets. These remain the **only** substantive evidence anchors for answer generation.
2. **Section B (Advisory Context)**: Controlled advisory signals to guide synthesis attention:
   - Perspective-local advisory `assessment_summary` is strictly omitted.
   - Unanchored issue descriptions (where `claim_ids == []`) are omitted; only `issue_type` and `claim_ids: []` are passed to prevent ungrounded prose leakage.
   - Anchored issue descriptions (where `claim_ids != []`) are included with their referenced claim IDs.
   - Critic relations provide structured cross-perspective comparison statements anchored to exact claim IDs.
   - Advisory signals MUST NOT be cited in `supported_claim_ids` or used to introduce new claims.
   - Deterministic source-map construction (`build_deterministic_source_map`) and grounding validation (`validate_governance_grounding`) remain grounded exclusively in Section A evidence packets.

### Perspective-Local Boundary Enforcement

All local advisory system prompts (`evidence_specialist`, `coverage_auditor`, `grounding_skeptic`) explicitly enforce perspective-local boundaries:
- Must evaluate only their assigned perspective packet.
- Must not evaluate whether the other perspective is present or missing.
- Must not evaluate whether the other perspective is correct, incorrect, or adequately addressed.
- Cross-perspective comparison is strictly reserved for the Critic.

### Critic Failure Isolation

- A failure in Critic execution (timeout, rate limit, schema error, or validation failure) is isolated to `"cross_perspective_critic"` in `failed_roles`.
- Critic failure does not block Governance synthesis and does not fabricate a replacement critique.
- Trace and consult response record `critic_status="failed"` and `cross_perspective_critique=None`.

### Critic Operational Timeout Diagnostic and Runtime Findings

During development validation of the Cross-Perspective Critic:
- Targeted production Critic validation at 90 seconds timed out twice.
- A controlled single-call diagnostic with a 240-second timeout succeeded.
- Successful diagnostic latency was approximately 75.6 seconds (`75,563 ms`).
- Requested and reported model matched exactly: `deepseek-ai/DeepSeek-R1-0528-Qwen3-8B`.
- The provider returned `reasoning_content` despite `thinking_behavior="send_false"` (`enable_thinking=false`).
- Final visible output was: `{"relations": []}`.
- JSON parsing passed.
- Pydantic validation passed.
- Deterministic Critic validation passed.
- An empty relations list (`[]`) is valid and was not treated as a failure.
- This is development runtime evidence only and does NOT establish model quality or superiority.

### Methodological Scope

- **No Formal Experiment**: This patch represents development runtime and orchestration implementation only; no formal benchmark or experiment has started.
- **No Clinical Correctness Claims**: No clinical or medical validity claims are made.
- **No Model Superiority Inferences**: Passing tests and telemetry observations establish structural and runtime software correctness only, and do not support claims of model superiority or inferiority.

---

## Patch 3 Release-Blocking Correction Pass

### Observed Final-Smoke Defects

Following final full live smoke `cross-perspective-v0.4-dev-baf423f5-97de-47aa-84cb-3eb8f33a9043`, three release-blocking defects were identified:

1. **Governance DifferenceOrConflict Output Shape**:
   The Governance model emitted `differences_or_conflicts` as a 2-element list `["not_directly_comparable", "..."]` instead of a list of objects conforming to the frozen `DifferenceOrConflict` schema (`{"statement": "...", "tcm_claim_ids": [...], "western_claim_ids": [...]}`).
2. **Critic Relation Proposition-Level Under-Anchoring**:
   The Critic emitted a relation covering both neuroimaging and "sleep studies", but only cited an MEG claim (`west-pmc-11794981-35724a28f8d4e70963c0`) without citing the supporting sleep studies claim from the packet.
3. **Local Perspective-Boundary Leakage & Advisory Contamination**:
   The Western `coverage_auditor` evaluated TCM content embedded in derived claim `western:western-answer-1` (`"The derived claim on TCM perspective is unsupported by the provided evidence."`), which violated perspective-local isolation.
4. **Permissive Downstream Advisory Issue Projection**:
   Because `issue.claim_ids` was non-empty (`["western:western-answer-1"]`), the previous downstream projection rule passed this cross-perspective evaluation description downstream to both the Critic and Governance.

### Implemented Hardening Corrections

1. **Governance Difference/Conflict Shape Hardening**:
   - `GOVERNANCE_SYSTEM_PROMPT` and `CrossPerspectiveGovernanceAgent.synthesize` user prompt were hardened with explicit rules specifying that every element of `differences_or_conflicts` MUST be a JSON object with `statement`, `tcm_claim_ids`, and `western_claim_ids`.
   - Explicitly forbids tuple/list encodings such as `["relation_type", "statement"]`.
   - Explicitly clarifies that the Critic relation schema and Governance DifferenceOrConflict schema are different contracts; `relation_type` is advisory metadata and must not be placed inside `differences_or_conflicts`.
   - Added rule that claims with `support_status == "insufficient"` cannot support substantive synthesis, cannot be copied/paraphrased as substantive evidence, and must not introduce cross-perspective content.
2. **Critic Clause-Level Anchor Completeness Hardening**:
   - `CRITIC_SYSTEM_PROMPT` and `build_critic_user_prompt` were hardened with explicit rules requiring that every substantive factual clause in `relation.statement` MUST be supported by the claim IDs inside that same relation.
   - Forbids enriching relations with uncited packet claims.
   - Requires that if multiple concepts (e.g. MEG and sleep architecture) are mentioned, claim IDs supporting both concepts must be cited; if cited IDs support only MEG, the statement must say only MEG.
3. **Critic Usable-Claims-Only Evidence Projection**:
   - Hardened `build_critic_payload` so that evidence packet `claims` contains *only* claims where `support_status != "insufficient"`.
   - Insufficient claims (such as `western:western-answer-1`) and their text are completely omitted from the Critic input payload.
4. **Local Perspective-Boundary Strengthening**:
   - Strengthened all three local advisory agent prompts (`evidence_specialist`, `coverage_auditor`, `grounding_skeptic`) to explicitly state that any cross-perspective content appearing inside an assigned packet remains strictly out of scope.
   - Prohibits assessing whether another perspective is present, missing, supported, unsupported, correct, incorrect, adequately addressed, clinically valid, or incomplete.
   - Prohibits creating issues whose description evaluates the other perspective.
5. **Downstream Advisory Safety Projection (Usable-Anchors Only)**:
   - Refined both Critic advisory projection (`build_critic_payload`) and Governance advisory context (`build_governance_advisory_context`) so that an issue description is passed downstream *only if* `issue.claim_ids` is non-empty AND every referenced issue claim exists in the perspective packet AND every referenced issue claim has `support_status != "insufficient"`.
   - Otherwise, only `issue_type` and `claim_ids` are passed, and `description` is omitted.
   - Stored assessments and packets remain completely immutable and unfiltered.
6. **Governance Advisory Builder Signature Update**:
   - Updated `build_governance_advisory_context` to accept `packets` mapping. Updated all call sites in `service.py`, `governance.py`, and test suites consistently.

### Methodological Scope

These are development hardening corrections. No formal experiment result was generated or changed. No clinical claims are established.

---

## Patch 3 Structural Canonical Critic Relation Materialization

### Observed Live Failure Patterns

Repeated targeted live validations demonstrated that prompt-only instruction was insufficient to prevent Critic free-text semantic overreach and clause-level grounding drifts:
1. In the first run, the Critic cited an MEG claim but introduced uncited "sleep studies" into the free-form statement.
2. In the subsequent run after prompt hardening, the Critic cited a sleep/EEG claim but introduced uncited "neuroimaging" into the free-form statement.

Prompt-only clause-level grounding constraints proved inherently unreliable for free-form relational statement generation under open-ended language model decoding.

### Architectural Correction

Therefore, before formal experiment freeze, substantive free-form Critic statement generation was structurally removed:

1. **Semantic Responsibility Split**:
   - **Model Decision**: The model (`deepseek-ai/DeepSeek-R1-0528-Qwen3-8B`) strictly decides `relation_type` (`possible_agreement`, `possible_difference_or_conflict`, or `not_directly_comparable`), `tcm_claim_ids`, and `western_claim_ids`.
   - **Deterministic Python Materialization**: Python deterministically materializes `statement` using frozen canonical non-substantive templates:
     - `possible_agreement`: `"The cited TCM and Western claims may reflect a possible agreement."`
     - `possible_difference_or_conflict`: `"The cited TCM and Western claims may reflect a possible difference or conflict."`
     - `not_directly_comparable`: `"The cited TCM and Western claims may not be directly comparable."`
2. **Schema Separation**:
   - Internal strict draft schema (`CriticDraft`, `CriticRelationDraft`) has `extra="forbid"` and contains only `relation_type`, `tcm_claim_ids`, and `western_claim_ids`, strictly rejecting any model-generated `statement` or prose fields.
   - External materialized API contract (`CrossPerspectiveCritique`, `CrossPerspectiveRelation`) preserves the `statement` field for downstream consumer compatibility.
3. **Deterministic Validation**:
   - `validate_critic_critique` enforces `relation.statement == CRITIC_CANONICAL_STATEMENTS[relation.relation_type]`. Any non-canonical statement raises `CriticValidationError`.
4. **Governance Advisory Navigation**:
   - Governance receives canonical statements in advisory context, but Governance prompts explicitly state that Critic canonical statements contain no substantive evidence content and must not be copied as evidence. Substantive differences/conflicts must be grounded independently in Section A evidence packet claims.

### Scientific Scope and Freeze Notice

- This change represents pre-release development hardening prior to formal experiment freeze.
- No formal experiment was run in this step.
- No prior formal experiment result is altered or superseded.
- No claim of medical correctness, clinical efficacy, or model superiority is implied.

---

## Patch 3 Governance Evidence-Gaps and Uncertainty Wording Hardening

### Pre-Freeze Review Finding

Final static review of the integrated runtime output identified an overbroad evidence-gap sentence:
`"No direct TCM insights are provided for the specific case of recurrent mild headache."`

This statement conflated:
1. "available evidence is educational, terminology-based, or not clinically validated for treatment efficacy"
with:
2. "the perspective provides no perspective-specific insight"

In fact, the TCM packet provided usable case-related educational pattern directions (`Liver yang rising` and `Blood deficiency headache`), while the actual evidence gap was the lack of clinical treatment efficacy data and full physical examination findings.

### Governance Prompt Hardening

Governance system and user prompts were hardened before Patch 3 freeze to enforce that `evidence_gaps` and `uncertainty`:
1. Must remain strictly grounded in usable Section A claims, `missing_information`, `limitations`, and packet `uncertainty`.
2. Must never introduce, paraphrase, or copy content from claims with `support_status == "insufficient"`, advisory text, Critic text, or outside knowledge.
3. Must not contradict `overall_summary`, `perspectives.tcm.summary`, or `perspectives.western.summary`.
4. Must explicitly distinguish between (a) "no evidence/information exists" and (b) "evidence exists but is educational, indirect, incomplete, or not sufficient for clinical confirmation".

### Scientific Scope and Freeze Notice

- No formal experiment was rerun.
- No prior experiment result changed.
- No claim of clinical correctness, medical efficacy, or model superiority is implied.

---

## Patch 3 Final Structural Usable-Only Governance Projection

### Observed Failure and Safety Correction

During targeted Governance validation of the hardened prompt, despite explicit prompt-only instructions prohibiting the use or citation of insufficient claims, the Governance model cited `western:western-answer-1` (`support_status: "insufficient"`) inside `overall_supporting_claim_ids`. The deterministic grounding validator correctly intercepted the violation and failed closed (`GovernanceContractError`).

To guarantee grounding safety structurally rather than relying solely on prompt adherence:
1. **Governance Section A Usable-Only Projection**: `build_governance_payload(...)` was updated to project only claims with `support_status != "insufficient"`. Unusable claims are strictly omitted from the Governance-visible evidence surface.
2. **Advisory Unusable-ID Suppression**: `build_governance_advisory_context(...)` was updated so that any advisory issue anchored partly or wholly to insufficient/unusable claims projects `claim_ids: []` and omits `description`, preventing unusable claim IDs from appearing as advisory anchors.
3. **Data Integrity**: Original `PerspectiveEvidencePacket` and `PerspectiveAgentAssessment` instances remain authoritative, immutable, and preserved in full in telemetry and runtime logs. Source-map materialization continues to resolve provenance deterministically from the authoritative packets.
4. **Validation Uncompromised**: No output repair was introduced, and no validator was weakened.

### Scientific Scope and Freeze Notice

- This correction was implemented and validated prior to the formal Patch 3 freeze.
- No formal experiment was rerun.
- No prior formal experiment result changed.
- No claim of medical correctness, clinical efficacy, or model superiority is implied.
