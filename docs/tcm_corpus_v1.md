# TCM Research Corpus v1

## Status and scope

TCM Research Corpus v1 is a deterministic, provenance-aware research corpus for controlled RAG experiments. It is not a benchmark, clinical reference, diagnosis system, or authoritative statement that traditional claims are scientifically established. Every source claim remains attributable to its source, and qualified TCM/source review is still required.

The 2026-08-16 local build contains 4,461 entity chunks from 10,127 inspected raw rows: 4,228 herb records and 233 syndrome records. Nine exact within-source duplicates were removed; cross-source aliases, near-duplicate candidates, and 406 conflicting field groups were preserved for audit. There are no accepted relation records in v1.

The former 16-entry corpus remains in `backend/data/tcm_knowledge_base.json` as a labelled provisional test fixture. It is not counted as TCM Corpus v1 and remains the runtime fallback when the local v1 artifact is absent.

## Source and rights gate

The source audit is recorded in `research/corpus/reports/source_audit.md` before any acquisition. V1 accepts only:

- SymMap v2 herb and syndrome workbooks, locally, with source-level attribution. Its publication describes expert curation, but no separate database redistribution licence was located.
- TCMBank's official herb workbook, locally. The article is CC BY-NC 3.0, but that article licence is not assumed to license the database contents.

Raw files and all source-derived normalized/chunk data are therefore gitignored. Only aggregate manifests, audit decisions, validation statistics, and reproducible acquisition/build code are committed. TCMM code is reference-only because its repository has no licence and includes LLM-derived processing. CPMCP is deferred until official access and database rights can be verified. ZhongJing resources are evaluation-only and never corpus inputs.

## Layout and separation

```text
research/corpus/raw/            local source downloads; gitignored
research/corpus/normalized/     canonical records and private dedup details; gitignored
research/corpus/tcm_v1/         retrieval chunks; gitignored
research/corpus/manifests/      aggregate build manifest; tracked
research/corpus/reports/        audit and aggregate validation reports; tracked
research/benchmarks/external/   evaluation-only external files; gitignored
research/datasets/              internal synthetic evaluation datasets; never ingested
```

This separation is enforced by `.gitignore` and by the contamination checker. A clean clone cannot silently reconstruct or redistribute restricted data; it prints precise acquisition instructions instead.

## Canonical schemas

`backend/corpus/v1_models.py` defines three Pydantic models:

- `CanonicalSourceRecord`: official and repository URLs, institution/authors, citation, access method/files, licence status, redistribution/academic-use/attribution decisions, review claims, limitations, proposed use, and gate status.
- `NormalizedRecord`: stable source and record IDs, version/URL/title/citation/licence/access date, category/entity/aliases/language, structured facts and optional relation fields, review status, source review claim, transformation history, deterministic ingestion timestamp, corpus version, original source record, and conflict IDs.
- `ResearchChunk`: retrieval text plus the same field-level provenance, excluding the full original record.

Original source strings are retained in local normalized records. Unicode is normalized with NFKC and whitespace is collapsed. Upstream strings containing replacement markers remain in structured local provenance but are excluded from retrieval text. Deterministic templates select and label source fields; no LLM creates, translates, completes, or reconciles facts.

## Import, deduplication, and conflict policy

`backend/ingestion/tabular.py` supports CSV, TSV, XLSX, JSON, JSONL, and read-only SQLite. Source-specific importers validate required identifiers/names and require at least one substantive evidence field for herb records. Sparse rows are excluded and counted.

Deduplication is intentionally conservative:

1. Exact fingerprints remove identical records only within the same source.
2. Normalized names and aliases identify equivalence groups without merging records.
3. Token Jaccard flags near-duplicate candidates; it does not delete them.
4. Conflicting source fields are retained on every record and linked by deterministic conflict-group IDs.

The tracked dedup report contains counts only. Source-derived names, IDs, and group details remain in the gitignored normalized directory.

## Reproduce a local build

Use the audited acquisition helper; it performs no download unless `--download` is explicit:

```powershell
$env:PYTHONPATH="$PWD\backend"
python -m ingestion.acquire_tcm_sources
python -m ingestion.acquire_tcm_sources --download
python -m ingestion.build_tcm_corpus_v1 --config research/corpus/configs/tcm_v1.yaml
python -m ingestion.validate_tcm_corpus_v1 --config research/corpus/configs/tcm_v1.yaml
python -m ingestion.check_benchmark_contamination
python -m ingestion.run_retrieval_pilot
```

The manifest records source versions, file hashes and sizes, deterministic ingestion timestamp, transformation module, Git commit, counts, exclusions, and the fact that no remote embeddings were built. Rebuilding the same files/config produces stable normalized content and chunk IDs; the wall-clock manifest build timestamp is intentionally operational metadata.

## Runtime integration

The safe default is `TCM_CORPUS_MODE=legacy`, which always uses the 16-entry fixture even when a local restricted artifact exists. Local research must set `TCM_CORPUS_MODE=required`; startup then fails if v1 is missing or invalid. `TCM_CORPUS_PATH` may point to an authorized external artifact location. The convenience command `./scripts/start-local-research.ps1 -RequireLlm` performs the corpus preflight and requires locally configured LLM credentials without printing them.

Existing retrieval IDs are unchanged: R0 lexical, R1 dense, R2 hybrid, and R3 hybrid plus reranking. Lexical indexes and document vectors are reused per engine. Bulk remote document embeddings are blocked unless `ALLOW_BULK_REMOTE_EMBEDDING=true`; the v1 pilot used deterministic local hash embeddings and no paid API.

The retrieval-only pilot is a pipeline check, not a clinical or research conclusion. Its four entity-lookup questions produced Hit@5 of 1.0 for lexical/hybrid modes and 0.25 for the local-hash dense baseline. See `research/corpus/reports/tcm_v1_retrieval_pilot.md` for full metrics and limitations.

## Validation and known gaps

Validation checks schema parsing, unique chunk IDs, category values, source-record linkage, required provenance, URLs, corrupted retrieval text, aggregate dedup/conflict counts, and available benchmark overlaps. The local v1 build passed with 100% required provenance completeness and no overlap against the two available internal benchmark files. This is not a zero-leakage claim: external ZhongJing data was absent and its licensing is unresolved.

V1 is herb-heavy. It lacks accepted prescription/formula, acupuncture, independent meridian-theory, constitution-analysis, and comprehensive safety/contraindication sources. It has no accepted bulk relations. Source-level expert-review claims cover only part of the corpus and do not validate every field.

## Phase 2b acquisition plan

1. Obtain written redistribution/reuse clarification from SymMap and TCMBank before publishing or deploying source-derived chunks.
2. Obtain CPMCP's current official exports and explicit database-use terms; add formula, patent medicine, symptom, and safety importers only after the gate passes.
3. Identify independently licensed, auditable sources for acupuncture points, meridian theory, constitution standards, contraindications, interactions, and toxicity.
4. Add field-level provenance and explicit relation types; never infer missing relations with an LLM.
5. Arrange qualified TCM/source review, record reviewer scope and adjudication, and version reviewed annotations separately.
6. Acquire licensed external evaluation resources independently, keep them under `research/benchmarks`, and rerun contamination checks before experiments.
