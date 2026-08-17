# TCM corpus and research-runtime audit — 2026-08-17

## Verified corpus artifact

The authorized local artifact is `research/corpus/tcm_v1/chunks.jsonl` (JSONL). It contains 4,461 chunks from two sources: TCMBank 3,531 and SymMap v2 930; categories are herbal medicine 4,228 and syndrome differentiation 233. SHA-256 is `316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9`. Current schema, provenance, source-link, duplicate-ID, and nonempty-text validation passes. The artifact and its raw/normalized inputs remain gitignored and must not be deployed or redistributed without permission.

## Runtime/corpus matrix

| Runtime or endpoint | Mode | Actual corpus | Chunks | Silent fallback? |
|---|---|---:|---:|---|
| `/api/tcm/consult` compatibility endpoint | legacy implementation | provisional fixture | 16 | No v1 path exists for this endpoint |
| `/api/research/run`, `/api/research/compare`, experiment runner (default/public) | `legacy` | provisional fixture | 16 | No; the default is explicit |
| Research endpoints/runner using local startup script | `required` | TCM Research Corpus v1 | 4,461 | No; missing/invalid v1 stops startup |
| Render production after this change | `legacy` unless explicitly overridden | provisional fixture | 16 | No restricted artifact is packaged |

`tcm_yangsheng_001` is an ID from `backend/data/tcm_knowledge_base.json`, the 16-entry fixture. Its appearance proves that run used the legacy corpus.

## Condition semantics

| Condition | Shape | Retrieval | Specialist/provider calls with real execution enabled | Aggregation | Debate | Judges | Final synthesis |
|---|---|---|---|---|---|---|---|
| C0 | single direct control | none | one direct LLM call | direct | no | no | direct LLM |
| C1 | single RAG | selected R0-R3 | one if evidence-backed | single | no | no | deterministic evidence-linked |
| C2 | multi-agent independent | selected R0-R3 | one per non-abstaining specialist | independent | no | no | deterministic evidence-linked |
| C3 | multi-agent weighted | selected R0-R3 | one per non-abstaining specialist | deterministic support weighting | no | no | deterministic evidence-linked |
| C4 | multi-agent debate | selected R0-R3 | one per non-abstaining specialist | critique/revision | deterministic | no | deterministic evidence-linked |
| C5 | multi-agent judge | selected R0-R3 | one per non-abstaining specialist | judge arbitration | no | deterministic rubrics | deterministic evidence-linked |
| C6 | multi-agent debate+judge | selected R0-R3 | one per non-abstaining specialist | debate+judge | deterministic | deterministic rubrics | deterministic evidence-linked |

With `RESEARCH_REAL_LLM_ENABLED=false`, all conditions make zero external calls (C0 uses the configured mock provider when that is the active provider, or returns an explicit deterministic control message when a real provider is configured but research execution is disabled). Before this audit, only C0 attempted a provider call; C1-C6 were deterministic while the UI inferred “live” from configuration. The UI now separately reports configured provider, actually called model, call attempts/success/failure, generation mode, and fallback/mock state. Intentional deterministic C1-C6 execution is not labelled as a fallback or mock.

## Scores and routing

For each supported specialist claim, `claim_support = min(0.62, 0.30 + 0.40 * signal)`. The current code selects the first nonzero score in this order: rerank, semantic, lexical; it does not use the RRF fusion score for this heuristic. Specialist support is the mean claim support; an irrelevant specialist abstains and receives zero. Integrated support is the mean over selected agents, including abstentions, capped at 0.65 and capped by the lowest deterministic judge score when judges run. It is an evidence-support heuristic—not medical correctness, probability, or expert validation—and the UI now labels it accordingly.

Routing now uses corpus topic metadata first. Keyword matching is only a bounded fallback. The previous raw substring rule included the single Chinese character `方`, which also occurs in `生活方式`; it incorrectly sent Yangsheng evidence to the Herbal specialist. Single-character CJK substring routing was removed. Corpus v1 herbal chunks now route to Herbal, syndrome chunks to Syndrome, and irrelevant specialists abstain.

## Retrieval semantics

| ID | Implementation | Actual default embedding | Actual default reranker |
|---|---|---|---|
| R0 | BM25-like lexical score | none | none |
| R1 | cosine similarity over embeddings | `local-hash-embedding-v1` | none |
| R2 | reciprocal-rank fusion of R0 and R1 | `local-hash-embedding-v1` | none |
| R3 | R2 candidate fusion then rerank | `local-hash-embedding-v1` | `local-overlap-reranker-v1` |

The configured BAAI models are not used in this safe default path. No remote bulk embedding job was started.

## Local workflow and observability

Run `./scripts/start-local-research.ps1 -RequireLlm`. The script loads ignored `backend/.env`, requires the exact v1 artifact, validates it, asserts 4,461 chunks, requires a configured non-mock provider/key without exposing the secret, then starts Uvicorn. `-PreflightOnly` verifies configuration without starting the server. `/health` and `/api/corpus/stats` expose corpus name/version/counts/mode and runtime profile. Research technical details include run/condition/retrieval IDs, corpus, provider configuration and actual calls, actual embedding/reranker, generation mode, fallback, evidence/source IDs, participants/abstainers, deterministic debate/judge state, latency, and the score formula.

Observed local verification (4,461 chunks, R2, six results requested) used these representative runs:

| Run | Evidence/source | Participating / abstaining | Calls/model/mode | Latency |
|---|---|---|---|---:|
| Herbal C1 `run-f6b521a4df6949b2` | `tcmv1-cc2d…`, `fe6954…`, `571c17…`, `941c9c…`, `c7f084…`, `b49736…`; TCMBank | `single_rag` / none | 0 / none / deterministic | 772 ms |
| Same herbal question C2 `run-0dfcecc745274043` | exactly the same six IDs; TCMBank | Herbal / Syndrome, Constitution | 0 / none / deterministic | 774 ms |
| Syndrome C2 `run-029e6c3ef8db4a47` | six `tcmv1-*` IDs; SymMap v2 | Syndrome / Constitution, Dietary | 0 / none / deterministic | 734 ms |

The herbal R2 run retrieved multiple records, satisfying the multi-record pipeline check, but its ranking did not place the exact Red Ginseng records first because the local hash baseline is weak. R0 did place the two exact Red Ginseng chunks first (`tcmv1-010f829f0c703d4a98d24324` and `tcmv1-0aaba1cbd4c4296e8ce6e234`). This is a retrieval-quality limitation to evaluate, not evidence that a neural embedding model ran. A browser-level R0/C2 run confirmed the same two records, Corpus v1/4,461, Herbal participation, five correct abstentions, zero attempted calls, deterministic generation, and fallback/mock false.

## Pilot gate

The deterministic Corpus v1 pipeline and C1/C2 same-retrieval test are verified. A genuine same-model, real-call local C1/C2 pilot remains blocked until `LLM_API_KEY` is stored locally in ignored `backend/.env`; no key was available in the local process during this audit. Do not paste it into chat. After local configuration, run the startup command and require both traces to show corpus count 4,461, configured provider `siliconflow`, model `Qwen/Qwen2.5-7B-Instruct`, successful provider calls greater than zero, and no fallback.
