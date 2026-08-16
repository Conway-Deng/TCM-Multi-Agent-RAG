# Reproducibility

Each result records run ID, timestamp, Git commit, corpus/dataset version, condition, sanitized config, provider/model aliases, embedding/rerank identities, prompt versions/hashes, temperature, top-k, seed, agents/judges, evidence IDs, final answer, confidence, abstention, timing, tokens, errors, and fallback use.

Raw ad-hoc health questions are not written by default. `store_raw_query` is explicit opt-in. API memory retains recent runs. Batch experiments write to gitignored `research/results/<run_id>/` unless reviewed summaries are intentionally published with `research.publish_results --confirm-reviewed`.

Seed datasets are synthetic, provisional, researcher-created, and not expert validated.

TCM Corpus v1 records audited source-file hashes, versions, deterministic transformation timestamps, chunk IDs, counts, exclusions, and code revision in `research/corpus/manifests/tcm_v1_manifest.json`. Restricted raw/derived data is intentionally local-only; follow [`tcm_corpus_v1.md`](tcm_corpus_v1.md) to reacquire and rebuild it. Evaluation files remain outside the corpus and are checked separately for contamination.
