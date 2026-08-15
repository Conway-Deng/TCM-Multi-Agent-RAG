# ARCHIVED PRE-V1: MediConsensus Pilot Limitations

Inactive historical design. Use `docs/safety_and_limitations.md`.

- The TCM corpus is small and still requires human source and clinical review.
- Western Medicine output is synthetic fixture data, not a real API, RAG system, guideline search, diagnosis, or verified citation set.
- Same-model roles can share correlated errors and self-consistency bias.
- Judges may be biased, prompt-sensitive, over-agree, over-conflict, or miss unsupported and unsafe claims.
- Debate can create false consensus or amplify repeated errors; it does not guarantee correctness.
- Deterministic lexical support checks are not equivalent to expert semantic or clinical verification.
- Malformed JSON and provider failures trigger fallbacks, which reduce confidence but may reduce output richness.
- Multiple calls increase latency, cost, and provider-failure surface.
- Confidence scores are experimental orchestration indicators, not calibrated medical probabilities.
- Synthetic evaluation labels test system behavior and cannot establish clinical accuracy.
- Human and clinical review remain necessary before any real-world medical use.
