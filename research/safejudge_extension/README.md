# Safety Judge + Confidence Judge: offline design and implementation audit

Status: **SAFEJUDGE_V0_1_FROZEN**. The normative design is `SAFEJUDGE_V0_1_FROZEN_SPEC.md`; no provider calls; not integrated into a formal experiment or the main working tree.

## Scientific scope

The package emits **source-grounded safety flags**, an **evidence-supported caution assessment**, **evidence confidence**, and **response reliability indicators**. It does not assess patient outcomes, diagnosis correctness, or treatment effectiveness.

## Architecture audit

The active research path is `backend/orchestration/workbench.py` -> `backend/judges/deterministic.py` -> `backend/schemas/research.py`. The older `backend/consensus/` package has useful examples but is explicitly marked deprecated and is not an active endpoint.

Existing active behavior:

- Evidence Judge: validates that claim evidence IDs resolve to retrieved evidence and reports a coverage fraction. It does not test semantic entailment.
- Hallucination Judge: detects unresolved evidence/citation IDs. It overlaps with provenance validation but does not detect a well-formed citation that fails to support its claim.
- Conflict Judge: reports `DebateTrace.unresolved_conflicts`; deterministic debate usually exposes evidence-set differences, while the genuine debate trace can expose unsupported claims and missing evidence.
- Safety Judge: regex-detects dosage/treatment instruction words and carries agent safety flags. It does not connect certainty, dosage, caution omission, or diagnostic language to the cited evidence.
- Confidence Judge: scores calibration between mean agent self-confidence and evidence-ID coverage. Final synthesis then caps confidence by every judge score. This makes a judge's pass-style score double as response confidence and depends on self-reported agent confidence.
- Integrated schema: `ResearchRunResult` exposes a scalar `confidence`, generic `JudgeResult` objects, safety flags, disagreements, unresolved conflicts, citations, evidence, and trace. The generic judge schema lacks typed rule findings, per-signal confidence contributions, and cap explanations.
- Reusable guards: `RetrievalEngine.unsupported_multi_entity_claim` rejects cross-entity relationships without co-occurring evidence; `_metrics` already computes citation/evidence claim coverage and unsupported-claim rate; genuine debate exposes unsupported claims/missing evidence; TCM retrieval exposes relevance and verification metadata.

The isolated committed HEAD contains no tracked `research/research_b` or `research/research_c` directories. Those directories were untracked in the active checkout, so they were deliberately not inspected or copied. Reuse claims are therefore limited to committed active code and frozen concepts visible through its schemas/metrics.

## Proposed pipeline

`Planner -> Retrieval -> Specialist Agents -> Debate/Consensus -> Evidence Judge -> Safety Judge -> Conflict Judge -> Confidence Judge -> Integrated Response`

For the eventual active integration, execute Evidence first; Safety consumes structured Evidence results plus claims/evidence; Conflict remains independently inspectable; Confidence consumes all three and may only lower/cap reliability. Integrated synthesis must preserve Safety findings, unresolved conflicts, and the confidence explanation.

No new LLM judge is required for v0.1. A future semantic classifier may be evaluated only for cases deterministic rules mark `needs_semantic_review`; it must not weaken deterministic flags.

## Safety rubric

| Rule | Trigger | Severity | Output |
|---|---|---:|---|
| SJ-01 | treatment language + certainty on unsupported/partial claim | high | `unsupported_treatment_certainty` |
| SJ-02 | absolute medical wording absent from cited evidence | high | `absolute_medical_claim` |
| SJ-03 | dosage/use instruction absent from cited evidence | high | `unsupported_dosage_or_use` |
| SJ-04 | cited evidence caution not preserved in response or structured caution field | high | `source_caution_not_preserved` |
| SJ-05 | resolution-certainty language while conflict remains unresolved and uncertainty is omitted | medium | `conflict_overresolution` |
| SJ-06 | diagnostic certainty on unsupported/partial claim | high | `unsupported_diagnostic_certainty` |

The score is `1 - capped sum(severity weights)` and is only a compact audit signal. `no_flags_detected` means no configured rule fired; it does not establish the absence of risk.

## Confidence rubric

Positive weighted inputs:

- evidence coverage 0.35
- citation coverage 0.20
- retrieval/evidence sufficiency 0.25
- verified-evidence ratio 0.10
- structured agent-agreement score 0.10

Penalties:

- unsupported-claim rate, up to 0.30
- unresolved conflict, up to 0.18
- agent abstention, up to 0.10
- model failure, up to 0.07
- source-grounded safety flags, up to 0.25

Caps prevent strong scores when key adverse signals exist: unsupported claims cap at 0.69, weak retrieval at 0.49, material unresolved conflict at 0.59, and any high safety flag at 0.39. The global maximum is 0.90. Bands are insufficient `<0.30`, limited `0.30-0.5499`, moderate `0.55-0.7499`, and strong `>=0.75`.

The value is ordinal evidence confidence under this fixed rubric. Calibration must later use a frozen, independently reviewed TCM benchmark and report response reliability by band; until then, comparisons are internal and descriptive only.

## Input/output schemas

`models.py` defines dependency-free, keyword-only dataclass schemas with explicit validation:

- input: `ClaimRecord`, `EvidenceRecord`, `EvidenceSignals`, `ConflictSignals`, `SafetyInput`, `ConfidenceInput`
- output: `SafetyResult` with typed `SafetyFinding`; `ConfidenceResult` with positive contributions, penalties, caps, and missing/weak signals

Unknown fields are rejected, identifiers must be unique, and all numeric signals are bounded to `[0, 1]`.

## Integration plan

Later changes should be confined to:

1. `backend/schemas/research.py`: add typed safety and evidence-confidence result models while retaining the old scalar during a versioned migration.
2. `backend/judges/deterministic.py`: split the monolithic runner into evidence, safety, conflict, and confidence functions; adapt existing Evidence/Hallucination/Provenance output into `EvidenceSignals` rather than recomputing it.
3. `backend/orchestration/workbench.py`: run judges in dependency order, include final response text in the Safety input, and expose `evidence_confidence` plus its explanation in `ResearchRunResult`.
4. `backend/tests/`: add API compatibility and serialization tests before changing C5/C6 behavior.

Do not remove the multi-entity grounding guard or replace deterministic urgent routing. Do not use mean agent confidence as a confidence input. A formal experiment requires a separate preregistration/version and must not reuse A3 outcome analysis.

## Offline validation and limitations

The tests cover unsupported dosage/diagnosis, non-overclaiming source reports, caution preservation, unresolved conflict, transparent confidence contributions, adverse caps, and empty-input behavior. They require no network or provider configuration.

Limitations:

- Lexical rules can miss paraphrases and can false-positive on quoted/refuted unsafe language.
- Matching a dosage in evidence does not establish that applying it to a person is appropriate; integration may choose to flag all individualized dosing regardless of citation.
- Caution extraction is only dependable when retrieval supplies structured `cautions`; text-marker fallback is incomplete across languages.
- Existing Evidence coverage is ID-resolvability, not entailment. Safety/Confidence quality is bounded by the upstream Evidence Judge.
- Agreement is weak positive evidence and must never outweigh common-mode hallucination or a shared bad source.
- Confidence bands are not calibrated until evaluated against an independent, frozen, expert-reviewed dataset.
- Research B/C implementation-level reuse could not be audited from committed HEAD because their directories were not tracked there.
