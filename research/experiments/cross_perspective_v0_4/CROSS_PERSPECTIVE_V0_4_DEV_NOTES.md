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
