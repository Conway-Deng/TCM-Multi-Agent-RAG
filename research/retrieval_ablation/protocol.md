# TCM Retrieval Ablation v1 — preregistered protocol

Status: **PREREGISTERED_NOT_STARTED**. No formal retrieval result or provider response existed when this protocol and split were created.

## Question

Does improved evidence retrieval increase source-grounded TCM question-answering performance relative to the existing R0 lexical baseline?

## Immutable inputs and fixed variables

The study reuses the frozen 100-question RQ1 confirmatory benchmark and TCM Corpus v1. Gold means source-grounded reference, not medical or clinical truth. Corpus, benchmark, Qwen/Qwen3-8B, C1 Single-RAG architecture, the existing `_agent_prompt`, temperature 0.0, max tokens 384, frequency penalty 0.5 on the initial attempt and 1.0 on retry, final top-k=4, candidate depth=12, no iterative retrieval, and manifest ordering remain fixed. Retrieval-provider requests have zero automatic retries: a failure is recorded as unusable and fails closed; identity-guarded manual resume is permitted. If Stage 2 occurs, the frozen C1 policy permits at most two specialist-generation attempts triggered only by provider failure or grounding/output-quality rejection, and fallback is preserved as failure. Only retrieval method may vary.

R0 is the existing deterministic BM25-like baseline. R1 must use SiliconFlow `BAAI/bge-m3`; R2 is RRF of R0 and validated R1; R3 reranks the fixed R2 candidate set with SiliconFlow `BAAI/bge-reranker-v2-m3`. Formal execution is fail-closed. Local hash embeddings, local overlap reranking, legacy reranker stubs, malformed/partial provider responses, and silent fallback are forbidden.

## Stage 1: retrieval only

All 100 questions are evaluated under R0/R1/R2/R3, producing 400 paired query-condition records and zero Qwen generations. Metrics are chunk Recall@1/@4/@8, Gold evidence recall, Hit@1/@4/@8, source recall where meaningful, retrieval latency, usability, and failure/fallback counts.

The deterministic split assigns 40 questions to method selection and 60 to untouched confirmation. The selection set preserves domain composition at herbal=24, syndrome=10, multi-target=6. Every question is assigned exactly once.

## Advanced-method gate

Only the 40 selection questions choose among R1/R2/R3. Ranking is mean Recall@4 descending, then mean Gold evidence recall descending, mean retrieval latency ascending, and condition ID ascending. A method qualifies only if Recall@4 is strictly higher than R0, Gold evidence recall is not worse than R0, strict-mode usability is 100%, and fallback count is zero. Exactly one qualifying method is selected. If none qualifies, Stage 2 does not run. No superiority claim is made from the selection set.

## Stage 2: generation, preregistered but not executed

If a method qualifies, the untouched 60-question confirmation set receives C1 generation under R0 and the selected method only: at most 120 Qwen generations. Required metrics are question-level Gold Fact Recall/Full Recall, citation recall/precision, usable rate, retrieval latency, and total latency. Conditions differ only in retrieval.

## Statistics

The question is the paired unit. R0-versus-advanced comparisons report paired differences, 10,000 paired bootstrap confidence intervals, paired permutation/Wilcoxon tests where valid, McNemar tests for binary Hit@k, and Holm correction across the three confirmatory retrieval comparisons where appropriate. Stage 2 uses only the untouched confirmation set and reports paired downstream effects plus latency tradeoffs.

## Execution boundary

This preregistration creates no provider calls, does not warm embeddings, does not execute Stage 1 or Stage 2, and does not alter Research A, B, or C.
