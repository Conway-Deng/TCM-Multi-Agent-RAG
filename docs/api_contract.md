# API contract

Active endpoints:

- `GET /health`
- `POST /api/tcm/consult`
- `POST /api/tcm/multi-agent/consult`
- `POST /api/research/run`
- `POST /api/research/compare`
- `GET /api/research/conditions`, `/agents`, `/retrievers`, `/judges`
- `GET /api/research/runs/{run_id}` and `/metrics`
- `POST /api/retrieval/search`
- `GET /api/corpus/stats`

OpenAPI is at `/docs`. Corpus mutation has no public endpoint. The removed `/api/consensus/consult` route returns 404. No API key or authorization header is returned to the browser.
