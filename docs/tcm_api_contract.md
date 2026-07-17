# TCM-RAG API Contract

Endpoint: `POST /api/tcm/consult`

Request:

```json
{
  "question": "我有点失眠，最近腰酸",
  "context": {
    "age": "",
    "gender": "",
    "duration": "",
    "medications": "",
    "pregnancy": "",
    "allergies": ""
  }
}
```

Stable response fields for future Query Planner, Debate, and Judge layers:

- `agent`
- `scope_status`
- `abstained`
- `summary`
- `claims[]` with `evidence_ids`
- `patterns[]`
- `educational_examples[]`
- `evidence[]`
- `citations[]`
- `safety_notes[]`
- `confidence`
- `limitations[]`
- `retrieval_metadata`
- `generation_source`, `llm_model`, `llm_error`

Backward-compatible fields are also retained:

- `tcm_perspective`
- `possible_patterns`
- `related_herbs_or_formulas`
- `retrieval_method`
- `candidate_count`
- `meaningful_match_count`
- `top_relevance_score`

Valid `scope_status` values:

- `supported`
- `insufficient_information`
- `out_of_scope`
- `safety_critical`
- `evidence_insufficient`

Valid `generation_source` values:

- `siliconflow_llm`
- `mock_fallback`
- `safety_rule`
- `scope_rule`
- `evidence_gate`

Every visible evidence item must include an `evidence_id`, `source_ids`, `evidence_category`, and `review_status`. Every source ID must resolve to `backend/data/tcm_sources.json`.
