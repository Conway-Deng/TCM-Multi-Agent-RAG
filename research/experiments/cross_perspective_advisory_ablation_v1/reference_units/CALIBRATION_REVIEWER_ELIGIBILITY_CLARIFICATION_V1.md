# CPAA1 Calibration Reviewer Eligibility Clarification V1

**Clarification ID**: `CPAA1-CALIBRATION-REVIEWER-ELIGIBILITY-CLARIFICATION-V1`  
**Study ID**: `cross-perspective-advisory-ablation-v1`  
**Status**: `PROPOSED — AWAITING HUMAN APPROVAL`  

**Bound Protocol SHA256**: `5ab2f681e605f3bc75ef6e91fa8d864a102aa60e6b14efdda132448845dcb46b`  
**Bound Authorship Amendment SHA256**: `9de5635eaf62a6346789f7be1f291c0e88d6d8f8b3266daaa45a942a66c98dfa`  
**Bound Fixture Content Canonical SHA256**: `9f9a724676857a72d12d6da585a247e70087494e2bc14225b66bdc2562f2b0ea`  
**Bound Fixture Pack Canonical SHA256**: `0df8db31c0435e38f6414656445598b49b09c31719771d1518c0fc315eb964d9`  

---

## 1. Purpose and Governance Context

1. **Procedural Clarification**: This document establishes a narrow, prospective procedural clarification regarding human reviewer eligibility and prior-exposure disqualification for the human calibration phase (`CAL-2CC-01` through `CAL-2CC-08`) under study `cross-perspective-advisory-ablation-v1`.
2. **Current Status**: This document is currently `PROPOSED — AWAITING HUMAN APPROVAL`. It is not yet binding and shall not take effect until formally approved by the study researcher binding its exact externally computed byte SHA256 hash.
3. **Hierarchy of Authority**: This clarification operates strictly under `CPAA1-REFERENCE-UNIT-PROTOCOL-V1` (byte SHA256 `5ab2f681e605f3bc75ef6e91fa8d864a102aa60e6b14efdda132448845dcb46b`) and `CPAA1-CALIBRATION-FIXTURE-AUTHORSHIP-AMENDMENT-V1` (byte SHA256 `9de5635eaf62a6346789f7be1f291c0e88d6d8f8b3266daaa45a942a66c98dfa`), governing the frozen calibration fixture pack (`fixture_pack_canonical_sha256`: `0df8db31c0435e38f6414656445598b49b09c31719771d1518c0fc315eb964d9`).

---

## 2. Reviewer Disqualification from Internal Case-Specific Metadata

1. **Disqualification Rule**: Any individual previously exposed to case-specific internal calibration-purpose metadata for cases `CAL-2CC-01` through `CAL-2CC-08` is strictly NOT eligible to serve as Reviewer A or Reviewer B for that frozen fixture.
2. **Definition of Prohibited Case-Specific Internal-Purpose Metadata**: Prohibited exposure includes, but is not limited to:
   - Internal calibration target concepts;
   - Assigned methodological boundary or case-to-boundary mapping;
   - Case-specific AI methodology audits;
   - Case-specific audit rationale or commentary;
   - Preferred interpretation, target resolution, or intended analysis;
   - Answer-key-like guidance, hints, or heuristics;
   - Expected reference-unit count, unit distributions, or quotas.
3. **Irreversibility of Exposure**: Prior exposure to case-specific internal metadata cannot be cleansed, unlearned, or mitigated by procedural blinding declarations. Once exposed to internal case metadata, the individual is permanently disqualified from acting as an annotating reviewer for this calibration fixture pack.

---

## 3. Permitted Pre-Calibration Exposure and Reviewer Orientation

1. **Generic Protocol Exposure Permitted**: Familiarity with or exposure to the generic reference-unit protocol (`CPAA1-REFERENCE-UNIT-PROTOCOL-V1`), general reference-unit definitions, annotation guidelines, or boundary rules does NOT disqualify an individual from serving as Reviewer A or Reviewer B.
2. **Generic Examples Permitted**: Reading generic instructions or examining generic, completely unrelated practice examples does NOT disqualify a reviewer.
3. **Sanitized Reviewer-Facing Fixture Permitted**: Reading the sanitized, blinded reviewer-facing calibration input (`calibration_reviewer_view_frozen_v1.json` containing only case IDs, question text, synthetic TCM/Western packets, and mechanical IDs/hashes) does NOT disqualify a reviewer.

---

## 4. Reviewer Independence and Dual-Reviewer Architecture

1. **Two Distinct Humans**: Reviewer A and Reviewer B must be two distinct human beings.
2. **No AI Substitution**: AI systems or models MUST NOT substitute for either Reviewer A or Reviewer B, nor provide semantic annotation assistance, pre-annotations, or suggestions.
3. **Independent Construction**: Reviewer A and Reviewer B must independently read the fixture cases and independently author reference-unit annotations without conferring or collaborating.
4. **Isolated Workspaces**: Reviewer A and Reviewer B must operate in strictly segregated reviewer workspaces.
5. **Byte-Identical Input**: Both reviewers must receive byte-identical sanitized reviewer-facing fixture input.
6. **Blinding Prior to Verified Dual Lock**: Neither reviewer shall have any visibility into the other reviewer's annotations, unit count, or progress prior to mechanical verification of dual locked submissions.
7. **Mandatory Declarations**: Prior to reviewer onboarding and workspace release, each prospective reviewer must formally record:
   - Full human identity;
   - Relevant background/qualifications (clinical degrees/physician credentials are NOT required);
   - Conflict-of-interest declarations;
   - Formal prior-exposure declarations confirming zero exposure to prohibited case-specific internal metadata.

---

## 5. Role Separation for Study Researchers and Fixture Approvers

1. **Role Boundary**: An individual who has approved the fixture pack or who has had access to internal calibration design targets may continue to perform administrative, protocol, and coordinating functions, but is barred from semantic annotation:
   - Permitted Roles: Study researcher, protocol coordinator, fixture approver, procedure approver.
   - Prohibited Roles: Reviewer A, Reviewer B.
2. **Specific Determination for Conway Deng**:
   - Conway Deng has previously reviewed or otherwise been exposed to internal calibration targets, case-to-boundary mappings, and AI logic audits.
   - Conway Deng is therefore explicitly NOT eligible to serve as Reviewer A or Reviewer B for `CAL-2CC-01` through `CAL-2CC-08`.
   - This ineligibility is a standard methodological separation of duties and does NOT invalidate Conway Deng's Phase 2C-C2C human approval of the calibration fixture pack.
3. **Requirement for Two Separate Eligible Reviewers**: Formal execution of human calibration requires onboarding two other eligible human annotators who meet all eligibility criteria.

---

## 6. Procedural Approval, Transparency, and Prospective Activation

1. **Authority to Propose and Approve**: The study researcher / protocol owner (Conway Deng) possesses procedural authority to propose and approve this narrow administrative clarification.
2. **Truthful Characterization**: Any approval executed by the study researcher must be truthfully reported as protocol owner approval and MUST NOT be represented or mischaracterized as independent external audit or third-party validation.
3. **Binding Requirements**: This clarification document shall become active and binding if and only if all of the following conditions are met:
   - Exact final document text is authored and recorded;
   - The file byte SHA256 is externally computed;
   - Conway Deng explicitly approves that exact document byte SHA256 without wording modifications;
   - A formal approval receipt binds the exact document hash;
   - The approved clarification and all affected procedures/templates are prospectively frozen prior to releasing workspaces to Reviewer A and Reviewer B.
4. **No Backdating**: Neither approval nor freeze events shall be backdated under any circumstances.

---

## 7. Stop Conditions and Remediation Protocol

1. **Pre-Release Stop Condition**: If reviewer eligibility, independence, or absence of prohibited prior exposure cannot be verified for either prospective reviewer:
   - **NO REVIEWER RELEASE SHALL OCCUR**. Reviewer workspaces remain blocked.
2. **Post-Release Discovery of Prohibited Exposure**: If prohibited prior exposure is discovered after reviewer release or during calibration execution:
   - All affected reviewer activity must STOP immediately;
   - All existing reviewer workspaces and raw submission files must be preserved for audit;
   - No claim of restored blinding may be made for the compromised reviewer;
   - Replacement of the disqualified reviewer and subsequent restart must be documented prospectively in a formal audit record.
3. **Methodological Ambiguity During Calibration**: If unforeseen methodological ambiguity arises after reviewer work begins:
   - Affected annotation work must be paused immediately;
   - Existing draft submissions must be sealed/preserved;
   - A versioned prospective clarification must be drafted, reviewed, approved, and frozen before resuming work;
   - The frozen clarification must be applied consistently to all affected materials.

---

## 8. Invariance of Formal Study Baseline and Evaluation Metrics

This clarification is strictly limited to reviewer eligibility for non-study calibration cases. It does NOT modify:
1. Calibration challenge case text, prompts, synthetic evidence passages, or fixture content/pack hashes;
2. Truthful AI authorship provenance (`ai_drafted_human_approved`);
3. Reference-unit definitions, decomposition rules, semantic support criteria, or atomicity boundaries;
4. The formal 48 study questions, formal packet text, retrieval outputs, or frozen baseline manifests;
5. Formal $M_q$ reference set rules or calculation methodologies;
6. Formal statistical endpoints, hypothesis tests, or evaluation procedures;
7. Model ablation configurations ($G_0, G_1, G_2, G_3$);
8. Downstream model leakage controls.

Calibration reference-unit exercises and logs remain strictly non-study artifacts and shall NEVER contribute to or alter the formal study denominator ($M_q$).
