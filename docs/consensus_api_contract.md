# ARCHIVED PRE-V1: MediConsensus API Contract

Inactive historical design. Use `docs/api_contract.md`; no active runtime imports this Western/TCM contract.

Endpoint: `POST /api/consensus/consult`

```json
{
  "question": "I have trouble sleeping and lower back soreness.",
  "context": {"age": "", "gender": "", "duration": "", "medications": "", "pregnancy": "", "allergies": ""},
  "strategy": "debate_judge",
  "domains": ["tcm", "western_fixture"],
  "include_trace": true
}
```

Strategies are `concatenate`, `weighted`, `debate`, and `debate_judge`. Domains are `tcm`, `western_fixture`, and the future `western_api` placeholder.

The response contains normalized agents, debate output when applicable, structured judges, integrated response, fixture and experimental flags, latency, API-call counts, model-call failures, optional model trace, weights, and selected/excluded claims.

Fixture use returns HTTP 403 unless `ALLOW_WEST_FIXTURE=true`. A missing or unimplemented future Western API returns HTTP 503. Validation errors return HTTP 422. Errors do not expose stack traces or credentials.

`POST /api/tcm/consult` remains unchanged. `GET /health` additionally reports `consensus_enabled` and `west_fixture_enabled`, not secret values.
