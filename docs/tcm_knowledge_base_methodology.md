# TCM Knowledge Base Methodology

The corpus is intentionally small and internally traceable. It is not a clinical encyclopedia.

Files:

- `backend/data/tcm_knowledge_base.json`
- `backend/data/tcm_sources.json`
- `backend/data/tcm_scope_rules.json`

Each knowledge entry contains:

- multilingual symptoms and keywords
- multilingual pattern label and rationale
- educational formula examples only
- safety notes
- source IDs
- evidence category
- review status

Source policy:

- Do not fabricate books, page numbers, URLs, trials, or citations.
- Do not claim that a terminology standard proves treatment efficacy.
- Separate terminology, traditional theory, educational summaries, modern evidence, and safety information.
- Mark unverified entries as `needs_human_review`.

All current knowledge entries are marked `needs_human_review`; qualified human medical/source review remains required before publication or clinical use.
