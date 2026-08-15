# Reproducibility

Each result records run ID, timestamp, Git commit, corpus/dataset version, condition, sanitized config, provider/model aliases, embedding/rerank identities, prompt versions/hashes, temperature, top-k, seed, agents/judges, evidence IDs, final answer, confidence, abstention, timing, tokens, errors, and fallback use.

Raw ad-hoc health questions are not written by default. `store_raw_query` is explicit opt-in. API memory retains recent runs. Batch experiments write to gitignored `research/results/<run_id>/` unless reviewed summaries are intentionally published with `research.publish_results --confirm-reviewed`.

Seed datasets are synthetic, provisional, researcher-created, and not expert validated.
