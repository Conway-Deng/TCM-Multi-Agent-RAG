# Corpus methodology

The frozen provenance-aware corpus workflow, licence gate, schemas, build commands, validation, and current quantitative report are documented in [`tcm_corpus_v1.md`](tcm_corpus_v1.md). The generic ingestion notes below remain available for researcher-supplied material; they do not supersede the v1 source audit.

The active adapter exposes an auditable source registry and deterministic chunks. Source metadata records organization, type, year, language, reference, access note, evidence category, review status, reviewer, date, and notes. Chunk metadata records topic, syndrome, herb, meridian, constitution, dietary, lifestyle, safety, and review tags.

Current content is provisional and needs human review. Source-type labels do not imply equal scientific strength.

Ingestion accepts researcher-provided TXT, Markdown, JSON, JSONL, and CSV. It normalizes, validates sources, detects duplicates, chunks deterministically, creates deterministic IDs, and emits a versioned manifest. PDF ingestion is a future adapter; no copyrighted content is scraped automatically.

```powershell
$env:PYTHONPATH="$PWD\backend"
python -m ingestion.validate_corpus
python -m ingestion.corpus_stats
python -m ingestion.build_corpus --input researcher_files --sources source_registry.json --output built_corpus
```
