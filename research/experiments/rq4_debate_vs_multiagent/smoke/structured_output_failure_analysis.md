# RQ4 smoke pass 2 structured-output failure analysis

This audit uses only the 17 persisted failed provider attempts from `smoke_provider_attempts.jsonl`; no new provider call was made.

## Malformed structured responses (13)

| Category | Provider responses | Evidence in persisted error |
|---|---:|---|
| Arrays contained objects where the critique schema required strings | 6 | Pydantic `string_type` failures in `agreements`, `missing_evidence`, or `unsupported_claims` |
| Incomplete/invalid JSON | 7 | Five `Unterminated string` errors and two `Expecting value` errors |
| Fenced JSON | 0 | Not observed in the persisted failures |
| Prose wrapper | 0 | Not observed in the persisted failures |
| Missing required field | 0 | Not observed in the persisted failures |
| Invalid evidence-ID shape | 0 | Not observed in the persisted failures |

The object-versus-string failures came from an under-specified item contract: the prompt named list fields but did not say that every item had to be a plain string. The returned claim/evidence objects were semantically natural but incompatible with the schema. The seven syntax failures occurred with the former 384-token structured-stage limit and ended around JSON string/value boundaries. The artifacts do not retain provider finish reasons or failed-attempt token usage, so provider-side token truncation cannot be proven; the pattern is consistent with insufficient structured-output budget and is not labeled as proven truncation.

## Timeouts (4)

- Three occurred in `critique:grounding_critic`.
- One occurred on the first `consensus` attempt and succeeded on its one retry.
- Each failure was the backend provider client's 45-second request timeout (`LLM request timed out`).
- No persisted failure was the runner's former 120-second whole-request timeout.

## Repair boundary

The repair simplifies each stage to one flat JSON object with one canonical type per field, supplies exact JSON examples, rejects missing/extra/incompatible semantic fields, tolerates only harmless syntactic wrappers, records the exact stage on every attempt, and retains one retry per required stage. It does not invent content or tune answer quality.
