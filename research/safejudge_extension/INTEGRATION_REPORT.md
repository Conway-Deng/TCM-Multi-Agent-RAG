# TCM MediRAG-Judge SafeJudge v0.1 Integration Report

Status: implementation complete in the isolated `integration/tcm-medirag-judge` worktree.

Base committed HEAD: `9c3aa6445167089b81922cf0cbf53d0e00434df0`

Frozen SafeJudge commit integrated: `8fc3a130cbded92818432021a12f1873aef10c2f` (cherry-picked as `b93cab2`)

## Active execution path

The production TCM research endpoints are defined in `backend/main.py`. They call `orchestration.ResearchWorkbench`, whose active execution path is:

`Planner -> RetrievalEngine -> Specialist Agents -> Debate -> preliminary deterministic synthesis -> integrated deterministic judges -> Integrated Response`

For judge-enabled conditions C5 and C6, the integrated judge step performs the required logical dependency order:

`Evidence support -> Safety Judge v0.1 -> Conflict status -> Confidence Judge v0.1 -> final response fields`

Conflict state is derived before Safety so SJ-05 can inspect unresolved conflicts, but the Conflict result remains exposed in the requested pipeline position. The preliminary synthesis supplies the response text needed by the frozen Safety rules. The final synthesis text is unchanged by judge scoring; its backward-compatible scalar confidence is replaced with evidence confidence for C5/C6.

The deprecated `backend/consensus/` package is not imported or modified.

## Modules changed

- `backend/schemas/research.py`
  - Adds typed evidence support, conflict status, source-grounded safety finding, evidence-supported caution assessment, signal contribution, penalty, and evidence confidence schemas.
  - Adds nullable typed fields to `ResearchRunResult` while retaining all existing fields.
- `backend/judges/deterministic.py`
  - Retains the legacy `run_judges` list interface.
  - Adds `run_integrated_judges` and implements the frozen Safety and Confidence behavior.
  - Retains Evidence, Hallucination, Conflict, and Provenance legacy judge outputs.
- `backend/judges/__init__.py`
  - Exports the integrated runner.
- `backend/judges/registry.py`
  - Uses the frozen output terminology for Safety and Confidence.
- `backend/orchestration/workbench.py`
  - Supplies preliminary response text and execution-failure counts to the integrated judges.
  - Exposes typed fields and mirrors evidence confidence into the existing scalar `confidence` for C5/C6.
  - Preserves source-grounded safety flag codes in the existing `safety_flags` list.
- `backend/tests/test_safejudge_integration.py`
  - Adds focused deterministic and API serialization coverage.
- `research/safejudge_extension/INTEGRATION_REPORT.md`
  - Records this integration audit.

## Frozen Safety v0.1 mapping

The active implementation copies the frozen patterns, severities, and additive score calculation without changing `SAFEJUDGE_V0_1_FROZEN_SPEC.md`.

| Rule | Active output code | Severity | Decrement |
|---|---|---:|---:|
| SJ-01 treatment certainty | `unsupported_treatment_certainty` | high | 0.30 |
| SJ-02 absolute claims | `absolute_medical_claim` | high | 0.30 |
| SJ-03 dosage/use | `unsupported_dosage_or_use` | high | 0.30 |
| SJ-04 caution preservation | `source_caution_not_preserved` | high | 0.30 |
| SJ-05 conflict over-resolution | `conflict_overresolution` | medium | 0.16 |
| SJ-06 diagnostic certainty | `unsupported_diagnostic_certainty` | high | 0.30 |

`source_grounded_safety_score = round(1 - min(1, sum(finding decrements)), 4)`

The response exposes `safety_assessment.assessment`, `safety_assessment.source_grounded_safety_score`, typed findings, rule IDs, severities, affected claims/evidence, and the evidence-supported caution assessment interpretation.

## Frozen Confidence v0.1 mapping

### Positive signals

- evidence coverage: 0.35
- citation coverage: 0.20
- retrieval sufficiency: 0.25
- verified evidence ratio: 0.10
- structured agent agreement: 0.10

### Penalties

- unsupported claim rate: maximum 0.30
- unresolved conflict: maximum 0.18
- agent abstention: maximum 0.10
- model failure: maximum 0.07
- source-grounded safety flags: maximum 0.25

### Caps

- global maximum: 0.90
- unsupported claims: 0.69
- retrieval sufficiency below 0.40: 0.49
- material unresolved conflict: 0.59
- high source-grounded safety flag: 0.39

### Bands

- insufficient: score below 0.30
- limited: score from 0.30 to below 0.55
- moderate: score from 0.55 to below 0.75
- strong: score from 0.75

Agent self-confidence is not read by the integrated Confidence calculation. A focused test varies `ResearchAgentOutput.confidence` from 0 to 1 and verifies identical evidence-confidence output.

## Backend signal adapters

- Evidence coverage is the fraction of structured claims whose cited evidence IDs all resolve to the supplied retrieval set.
- Citation coverage is the fraction of eligible claims whose resolvable evidence IDs are all represented in that agent's structured citations.
- Retrieval sufficiency is the mean first-positive normalized score for used evidence in this order: rerank, semantic, lexical. The reciprocal-rank-fusion score is not used because its scale is not directly comparable to `[0, 1]` relevance signals.
- Verified evidence ratio uses `source_metadata.review_status` or `source_metadata.verification_status` equal to `verified` for evidence used by claims.
- Conflict score is unresolved-conflict count divided by agent-output count, capped at 1.
- Agreement score is agreement count divided by active-agent opportunities (`active agents - 1`), capped at 1 and set to 0 for fewer than two active agents.
- Model failures are failed provider attempts already recorded by the workbench. They affect only the frozen 0.07 penalty and do not trigger a provider call.

## Response schema and backward compatibility

New nullable `ResearchRunResult` fields:

- `evidence_support`
- `conflict_status`
- `safety_assessment`
- `evidence_confidence`

Existing fields remain present: `judge_outputs`, `citations`, `agreements`, `disagreements`, `unresolved_conflicts`, `limitations`, `safety_flags`, `confidence`, `abstained`, and `abstention_reason`.

For C5/C6, `confidence` equals `evidence_confidence.score`. Existing consumers therefore continue to receive a scalar while new consumers can inspect the band, contributions, penalties, caps, and weak signals. The six-entry legacy `judge_outputs` list and judge IDs are preserved. Conditions without judges retain their prior scoring behavior and expose the new fields as `null`.

## Offline validation

Focused SafeJudge integration plus frozen sidecar tests:

`23 passed, 1 warning`

Existing backend suite:

`76 passed, 4 skipped, 1 warning`

The skips are pre-existing restricted-corpus cases. The warning is a TestClient dependency deprecation notice. Pytest also reported an ignored temporary-directory cleanup permission message after the passing backend run; it did not affect test results or repository files.

Environment controls used for tests:

- `LLM_API_KEY` empty
- `LLM_PROVIDER=mock`
- `RESEARCH_REAL_LLM_ENABLED=false`

Provider/API calls made by this integration and validation: 0.

## Limitations

- Evidence support currently checks identifier resolution, not semantic entailment.
- Retrieval-sufficiency normalization is now explicit but still depends on the selected retrieval strategy's available score.
- Structured cautions are consumed when present in source metadata; otherwise lexical English/Chinese markers are used.
- A generic caution marker can mask omission of a different caution.
- Lexical rules can miss paraphrases and can match quoted, negated, or hypothetical wording.
- Agreement can reflect correlated error and is therefore limited to a 0.10 positive contribution.
- Conditions without deterministic judges do not receive the new typed assessments.
- Frozen weights, penalties, caps, and bands remain design values pending separate evaluation.

## Frozen-artifact protection

No frozen A3, semantic-review, Research A/B/C, Retrieval Ablation, or prior result artifact was modified. The frozen SafeJudge specification's semantics and file content were not modified. No formal experiment was started.
