# Cross-Perspective MediRAG v0.3 Development Notes

**DEVELOPMENT PROTOTYPE — NOT FORMAL EXPERIMENT**

## Status and scope

Cross-Perspective MediRAG v0.3 is an additive, local development prototype for transparent health-question orchestration across two existing evidence pathways: TCM and Western. It is not a formal evaluation, a clinically validated system, or a source of medical advice. No result from this prototype may be interpreted as a publication finding.

The implementation is isolated in `backend/cross_perspective/`. Existing `/api/tcm/consult` and `/api/western/consult` behavior is unchanged. Historical experiments, frozen results, frozen protocols, and frozen manuscripts are not inputs to or outputs from this runtime.

## Architecture

1. The router either accepts a deterministic forced perspective selection or selects relevant evidence pathways in automatic mode.
2. The TCM adapter calls the existing TCM consult pathway and converts its response without adding Western evidence.
3. The Western adapter calls `WesternEvidenceAgent` and converts its response without adding TCM evidence.
4. The governance agent receives only the original question and the two common evidence packets. It performs no retrieval and has no web access.
5. The response and development trace preserve the route, separate perspective packets, governance result, source links, model calls, failures, token counts when available, and stage latency.

The common packet records perspective identity, availability and execution status, an interpretation, claims, support status, uncertainty, missing information, limitations, and provenance. Each supported claim reference resolves through:

`final statement -> perspective -> claim_id -> chunk_id -> source_id`

The Western Phase 1B runtime explicitly does not establish sentence-level claim support. The adapter therefore preserves its generated answer claim as `insufficient` when it has no claim-level evidence IDs; it does not attach retrieved citations to that answer merely because they were retrieved. In addition, every retrieved Western chunk becomes a deterministic `source_excerpt` claim whose exact bounded excerpt and `(source_id, chunk_id)` pair are preserved. Retrieved Western provenance remains inspectable in the packet.

## Exact development model allocation

| Role | Model | Use |
|---|---|---|
| Router | `Qwen/Qwen3.5-4B` | Automatic pathway selection only; no health answer |
| TCM evidence generation | `Qwen/Qwen3-8B` | Existing TCM pathway |
| Western evidence generation | `Qwen/Qwen3-8B` | Existing `WesternEvidenceAgent` |
| Governance/final chatbot | `Qwen/Qwen3-8B` | Packet-only structured synthesis |

These choices establish a development configuration, not a claim of model superiority. No paid model, DeepSeek-V3.2, Xing4.0-29B primary model, or GPT-5.6 Sol runtime role is configured.

## Evidence packet contract

`PerspectiveEvidencePacket` contains:

- `perspective`: `tcm` or `western`
- `available` and `execution_status`
- `interpretation`
- claims with `claim_id`, `claim_text`, `evidence_refs`, and `support_status`
- `claim_kind` distinguishes `source_excerpt` from `derived_claim`
- `uncertainty`, `missing_information`, and `limitations`
- provenance records with source ID, chunk ID, title, evidence excerpt, locator/identifier, source type, section, and license where available
- an explicit failure record when a pathway is degraded or unavailable

Schema validation rejects a claim evidence reference that is absent from the packet provenance. A claim marked `supported` must contain at least one evidence reference.

## Router contract

`router_mode="forced"` bypasses the routing model and permits a controlled selection such as `perspectives=["tcm", "western"]`. `router_mode="auto"` uses only `Qwen/Qwen3.5-4B` and returns `use_tcm`, `use_western`, a concise reason summary, and the exact requested perspectives. The router prompt prohibits answering the health question or introducing medical advice.

## Governance contract

`CrossPerspectiveAnswer` contains an overall summary, separate TCM and Western summaries, agreements, differences or conflicts, evidence gaps, uncertainty, and a source map. Each source-map row includes its perspective, claim IDs, and explicit `evidence_refs` pairs. Independent source-ID and chunk-ID lists are not used.

`overall_supporting_claim_ids` is required whenever any selected perspective has a usable non-insufficient claim. Every represented perspective must have an exact source-map row for the overall summary. A perspective summary with usable claims must name non-empty supported claim IDs and have an exact source-map row; a perspective with no usable claims must use its deterministic no-claim status statement. An overall answer with no usable claims must use the deterministic overall no-claim status statement.

The governance model receives claims, support status, provenance, uncertainty, missing information, limitations, availability/execution status, and failure metadata. Packet `interpretation` text is retained in the full packet and trace for inspection but is omitted from the governance payload because it may be unverified presentation text. Only non-insufficient claims with linked provenance may support substantive final statements.

The governance prompt prohibits new substantive medical claims, equivalence between TCM and biomedical mechanisms, treating agreement as proof, hidden disagreement, certainty inflation, and fabricated identifiers. Post-generation validation rejects:

- unknown claim, source, or chunk IDs;
- `insufficient` claims presented as supported;
- agreement entries without claim support from both perspectives;
- empty agreements or agreements using insufficient claims;
- differences without non-empty, non-insufficient TCM and Western claim support;
- cross-perspective misuse of claim IDs; and
- source/chunk pairs not linked exactly to the stated claims;
- perspective summaries without matching source-map statements; and
- overall summaries without non-empty supporting IDs or exact source-map support for every represented perspective;
- source-map rows in which one of several mapped claims contributes no evidence reference; and
- agreement or difference statements without matching source-map support from both perspectives.

The first synthetic live smoke exposed a development integration issue in the Governance structured-output shape: the provider returned valid, non-truncated JSON from the requested Qwen3-8B model, but emitted `tcm` and `western` at the top level instead of nesting them under `perspectives`. The Governance prompt now includes the exact eight-field top-level contract, an explicit nested structural template, a top-level `source_map` requirement, and compact-output instructions. This was not a formal experiment result, and no provenance validator or safety rule was weakened.

The prototype exposes evidence provenance and concise rationale fields, not hidden chain-of-thought.

## Development endpoint

`POST /api/cross-perspective/consult`

Example forced-mode request:

```json
{
  "question": "What do the two evidence perspectives report about headache?",
  "perspectives": ["tcm", "western"],
  "router_mode": "forced",
  "question_id": "optional-development-id"
}
```

The endpoint is disabled on the cloud control-plane profile. Existing TCM and Western endpoints remain unchanged.

## Development trace logging

The append-only JSONL trace defaults to `backend/cross_perspective/runtime/consultations.jsonl`; that runtime directory is Git-ignored. `CROSS_PERSPECTIVE_TRACE_PATH` may select another local path. Each record contains:

- run ID, UTC timestamp, and optional question ID;
- router output and selected perspectives;
- retrieval source IDs and chunk IDs by perspective;
- both perspective packets;
- governance input and output;
- fixed role-to-model allocation;
- model-call events, provider status/failure classification, HTTP status when available, and retry markers;
- prompt/completion token counts when returned by the provider; and
- per-stage and total latency.

Persistent raw-question storage is controlled by `CROSS_PERSPECTIVE_TRACE_RAW_QUESTION`, which defaults to `false`. The default trace preserves `question_id` and a deterministic SHA-256 `question_hash`, but not the raw question. The live governance call still receives the actual question. Set the switch explicitly to enable raw-question storage for local development only. API keys, Authorization headers, environment secrets, and hidden chain-of-thought are never part of a schema, prompt trace, or log record. Evidence packets may contain source excerpts.

## Failure and retry policy

Router and governance calls permit at most one retry, and only after a retryable technical failure (`timeout`, rate limit, HTTP 5xx, or connectivity). Structured-output or provenance-validation failures are semantic failures and are not retried. The legacy TCM client may make a second compatibility request when a provider rejects `response_format` with HTTP 400/422; additive telemetry records every actual HTTP attempt, the compatibility retry, statuses, and retry count. This compatibility retry is not labeled as a successful first attempt. There is no silent model substitution and no paid fallback.

An unavailable perspective is represented by an explicit unavailable packet with no claims or provenance. Governance receives that packet and must not reconstruct the missing perspective. A Western generation failure after successful retrieval remains an available but `degraded` packet containing deterministic source-excerpt claims and the provider failure; only an unavailable evidence pathway/retrieval is marked unavailable. A degraded TCM local fallback is labeled `degraded` with its provider/configuration failure preserved rather than being silently presented as an ordinary model result.

The TCM adapter checks the additive provider-reported model field. A missing or mismatched successful provider model is explicitly degraded and its generated interpretation is rejected, while deterministic retrieval-grounded TCM claims and provenance are retained. Failure packets preserve the provider retry count and final HTTP status when available. Western successful responses are similarly checked against `Qwen/Qwen3-8B`; retrieved source-excerpt claims are retained and all model-derived claims are removed if the generated interpretation is rejected for model mismatch.

## Nutrition status

No NutritionAgent exists in v0.3. Requests selecting nutrition fail with the following fixed explanation:

> Nutrition perspective unavailable until a dedicated provenance-preserving nutrition evidence corpus is constructed.

Nutrition must remain disabled until such a corpus and its provenance contract are implemented and reviewed.

## Future work not implemented

- No formal experiment, preregistration, benchmark run, or publication analysis is included.
- No clinician or human-expert validation is included.
- No TCM/Western mechanism equivalence or consensus claim is implemented.
- No new retrieval corpus is created.
- No NutritionAgent or nutrition claims are created.
- `XingChenAGI/Xing4.0-29B` remains a future governance challenger placeholder only. Any Qwen3-8B versus Xing4.0-29B comparison requires separate operational smoke testing and a prospectively frozen evaluation design.
- `deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` and `THUDM/GLM-4-9B-0414` are documented only as possible future research candidates, not primary runtime models.
- GPT-5.6 Sol is reserved for later external, independent, blinded evidence-grounded evaluation and is not part of this runtime.
- Live connectivity is optional and limited to at most two non-formal development questions; it is not automated by the test suite and must never be treated as research data.

The development trace is intentionally capable of supporting later comparisons of single-perspective, dual-perspective, and governance-synthesis configurations, including evidence coverage, unsupported claims, contradictions, traceability, uncertainty, conflict representation, perspective coverage, latency, model-call burden, and token burden. That capability does not itself constitute an experiment.
