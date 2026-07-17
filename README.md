# MediRAG-Judge Project 2: TCM-RAG

This folder contains the standalone Traditional Chinese Medicine retrieval module for the MediRAG-Judge research internship. It is limited to the TCM-RAG stage only.

Not implemented here:

- MediRAG-West
- full Multi-Agent Debate
- full SafeJudge layer
- final integrated dual-medicine response

The module is a research prototype, not a diagnosis or prescription system.

## What is completed

- Static frontend with EN / 中文 / KR UI switching
- FastAPI backend
- `POST /api/tcm/consult`
- SiliconFlow/OpenAI-compatible LLM integration
- safe local fallback when no API key or provider failure
- structured local TCM knowledge base in JSON
- source registry
- scope rules and abstention policy
- lexical retrieval baseline with optional semantic/reranker hooks
- relevance thresholding and evidence gate
- safety-critical routing
- structured API response for future Debate/Judge integration
- evaluation dataset and metrics scaffold
- tests for routing, fallback, LLM parsing, evidence gating, source integrity, and `.env` safety

## Project structure

```text
.
├── index.html
├── app.js
├── styles.css
├── backend
│   ├── main.py
│   ├── .env.example
│   ├── data
│   │   ├── tcm_knowledge_base.json
│   │   ├── tcm_sources.json
│   │   └── tcm_scope_rules.json
│   ├── evaluation
│   │   ├── tcm_eval_questions.json
│   │   ├── metrics.py
│   │   └── run_evaluation.py
│   ├── tcm
│   │   ├── agent.py
│   │   ├── scope.py
│   │   ├── safety.py
│   │   ├── validation.py
│   │   └── retrieval
│   └── tests
└── docs
```

## Run backend

PowerShell:

```powershell
cd D:\project\multi_agent_rag_research\TCM\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

If your local `.venv` launcher is broken, recreate it:

```powershell
cd D:\project\multi_agent_rag_research\TCM\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Health check:

```text
http://localhost:8000/health
```

## Run frontend

Open a second PowerShell window:

```powershell
cd D:\project\multi_agent_rag_research\TCM
python -m http.server 5500
```

Open:

```text
http://localhost:5500
```

The static frontend defaults to `http://localhost:8000`. For deployment, set before `app.js` loads:

```html
<script>window.MEDIRAG_API_BASE_URL = "https://your-api.example.com";</script>
```

## SiliconFlow configuration

Copy `backend/.env.example` to `backend/.env` and edit locally. Do not commit `.env`.

Default free SiliconFlow models:

```dotenv
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
EMBEDDING_MODEL=BAAI/bge-m3
RERANK_MODEL=BAAI/bge-reranker-v2-m3
```

If `LLM_API_KEY` is missing:

- `generation_source = "mock_fallback"`
- `llm_error = "LLM_API_KEY is missing"`

If the LLM call fails:

- local fallback is used
- the UI shows that the local medical library is being used
- the technical panel shows a short safe error message

## Retrieval and evidence gate

Default retrieval config:

```dotenv
RETRIEVAL_MODE=hybrid
ENABLE_SEMANTIC_RETRIEVAL=false
ENABLE_REMOTE_RERANK=false
TOP_K_CANDIDATES=10
TOP_K_EVIDENCE=4
MIN_RELEVANCE_SCORE=0.18
```

Because remote semantic retrieval is disabled by default, the backend reports `retrieval_method = "lexical"`. If no evidence passes the threshold, the system returns:

- `scope_status = "evidence_insufficient"`
- `abstained = true`
- empty `evidence`
- empty `patterns`
- empty `educational_examples`
- no LLM generation

## API states

`scope_status`:

- `supported`
- `insufficient_information`
- `out_of_scope`
- `safety_critical`
- `evidence_insufficient`

`generation_source`:

- `siliconflow_llm`
- `mock_fallback`
- `safety_rule`
- `scope_rule`
- `evidence_gate`

The response includes `claims[]` with `evidence_ids`, citations, confidence, limitations, retrieval metadata, and localized result content in EN / zh / ko.

## Tests

From the project root or backend folder:

```powershell
python -m pytest
```

In this Codex environment, the project `.venv` package folder was usable but its launcher was broken, so tests were run with bundled Python plus `.venv\Lib\site-packages`.

## Evaluation

```powershell
cd D:\project\multi_agent_rag_research\TCM\backend
python -m evaluation.run_evaluation --no-llm
```

Outputs:

- `backend/evaluation/results/last_results.json`
- `backend/evaluation/results/manual_review.csv`

Evaluation focuses on routing, retrieval, grounding structure, citation coverage, abstention, safety, and language behavior. It does not prove clinical correctness.

## Documentation

See:

- `docs/tcm_scope.md`
- `docs/tcm_architecture.md`
- `docs/tcm_api_contract.md`
- `docs/tcm_knowledge_base_methodology.md`
- `docs/tcm_retrieval_experiments.md`
- `docs/tcm_evaluation_plan.md`
- `docs/limitations.md`

## Known limitations and review requirements

- The corpus is small and limited in scope.
- All current TCM knowledge entries are marked `needs_human_review`.
- Source details require human verification before publication.
- Formula names are educational examples only, not recommendations.
- No dose, preparation, prescription, or treatment plan is generated.
- Automated tests do not replace clinical validation.
