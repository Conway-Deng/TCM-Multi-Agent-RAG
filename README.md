# MediRAG-Judge: TCM-RAG and MediConsensus Orchestration Pilot

This repository contains the functional Traditional Chinese Medicine retrieval module and an experimental, model-agnostic MediConsensus orchestration pilot for the MediRAG-Judge research internship.

Not implemented here:

- a real MediRAG-West backend or API
- clinically validated multi-agent recommendations
- verified Western Medicine retrieval in the current orchestration pilot

The TCM module is real local RAG. Western Medicine input in the consensus pilot is a synthetic fixture, disabled by default, and is never represented as a live API result.

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
- normalized cross-domain `AgentOutput` schema
- direct combination, deterministic weighted, debate, and debate-plus-judge strategies
- independently invoked Debate, Evidence, Safety, Conflict, Confidence, and Synthesis roles
- same-model defaults with role-specific model overrides for later heterogeneous experiments
- synthetic Western fixture adapter plus a safely failing future API adapter
- `POST /api/consensus/consult`
- deterministic no-LLM consensus evaluation scaffold

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

The health response reports whether consensus and Western fixtures are enabled, without exposing credentials.

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

## MediConsensus research configuration

The consensus pilot is enabled by default, but the synthetic Western fixture is not:

```dotenv
CONSENSUS_ENABLED=true
ALLOW_WEST_FIXTURE=false
CONSENSUS_TEMPERATURE=0
```

For local Both-mode research testing, explicitly set `ALLOW_WEST_FIXTURE=true`. Do not enable it in a production medical workflow. Consensus roles inherit `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`; optional `CONSENSUS_API_KEY` and `CONSENSUS_BASE_URL` override them. Role model variables such as `CONSENSUS_DEBATE_MODEL` and `CONSENSUS_SAFETY_JUDGE_MODEL` fall back to `LLM_MODEL`.

When LLM configuration is available, the `debate_judge` strategy makes separate calls for Debate, Evidence Judge, Safety Judge, Conflict Judge, Confidence Judge, and Consensus Synthesizer. Using the same underlying model for each role is still a multi-agent controlled condition; different providers are not required.

Example PowerShell request:

```powershell
$body = @{
  question = "I have trouble sleeping and lower back soreness."
  context = @{}
  strategy = "debate_judge"
  domains = @("tcm", "western_fixture")
  include_trace = $true
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/consensus/consult -ContentType "application/json" -Body $body
```

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

Consensus evaluation:

```powershell
cd D:\project\multi_agent_rag_research\TCM\backend
.\.venv\Scripts\python.exe -m evaluation.run_consensus_evaluation --no-llm
```

Outputs:

- `backend/evaluation/results/consensus_last_results.json`
- `backend/evaluation/results/consensus_manual_review.csv`
- `backend/evaluation/results/consensus_summary.md`

The consensus benchmark is synthetic and tests orchestration behavior, provenance labels, safety propagation, abstention, conflicts, and pipeline reliability. It does not measure clinical correctness.

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
- `docs/consensus_architecture.md`
- `docs/consensus_api_contract.md`
- `docs/consensus_research_design.md`
- `docs/consensus_evaluation_plan.md`
- `docs/consensus_limitations.md`

## Known limitations and review requirements

- The corpus is small and limited in scope.
- All current TCM knowledge entries are marked `needs_human_review`.
- Source details require human verification before publication.
- Formula names are educational examples only, not recommendations.
- No dose, preparation, prescription, or treatment plan is generated.
- Automated tests do not replace clinical validation.
