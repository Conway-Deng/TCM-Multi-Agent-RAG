# Legacy provisional corpus fixture

`tcm_knowledge_base.json` and `tcm_sources.json` contain the original 16-entry software-development corpus.

- Status: legacy provisional / test fixture
- Clinical status: not clinically validated
- Review status: all entries require qualified human review
- Runtime use: the legacy `/api/tcm/consult` compatibility endpoint and deterministic tests may continue to use it
- Research use: R0-R3 controlled research runs use TCM Research Corpus v1 when the local, license-gated build exists; otherwise the registry reports and uses this legacy fallback

Do not silently merge these researcher-created summaries into TCM Research Corpus v1. They remain isolated so tests are reproducible and source-derived research records are not confused with prototype content.
