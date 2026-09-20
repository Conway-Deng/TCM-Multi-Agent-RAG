# Western Stage C execution freeze v0.1.2-r2

This prospective operational amendment supersedes Stage C execution r1 before formal execution. Stage C r1 was never formally executed, and no formal Stage C records or run directory existed before this amendment.

## Pre-execution observation

A synthetic, non-formal provider integration smoke test reached `THUDM/GLM-Z1-9B-0414` and observed an otherwise structured JSON response inside one outer JSON-labelled Markdown code fence. The smoke test was not formal data and was used only to identify response-envelope behavior. No formal Stage C result was observed before r2 was frozen.

Amendment reason: `pre-execution synthetic integration test observed single outer Markdown JSON fence`.

## Prospective identity and immutable parents

- Stage C r2 run ID: `western-formal-v0.1.2-stage-c-r2-20260920-01`
- Stage C r2 execution version: `western-stage-c-execution-v0.1.2-r2`
- Superseded execution version: `western-stage-c-execution-v0.1.2-r1`
- Superseded r1 freeze commit: `c376635432f985bce31ce43be91a94c0243ca1a6`
- Formal Stage C cells before amendment: `0`
- Protocol: `western_formal_v0.1.2`
- Protocol SHA256: `af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192`
- Frozen Stage A run: `western-formal-v0.1.2-stage-a-20260918-01`
- Frozen Stage A retrieval SHA256: `91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e`
- Primary Stage B run: `western-formal-v0.1.2-stage-b-r1-20260919-01`
- Primary Stage B SHA256: `afc0665858b0493d9c4dfbc2d8990ccd89c663f2b63278221407cb876feaf17c`
- Implementation commit: `7f680930179e837f92229df87121a0d1d346ffde`
- Analysis JSON SHA256: `123322b8a416697cd814561b66b3722291d421206ff6310de6667b9d31b79ec8`

The original Stage B outage attempt remains incident-only, preservation-only, ineligible as primary data, and prohibited as Stage C input.

## Scientific contract unchanged

The scientific protocol, statistical analysis, frozen Stage A, finalized primary Stage B, expected evidence points, semantic labels, and all W-RQ2/W-RQ3 definitions remain unchanged. The r2 `analysis.json` reproduces the r1 preregistered analysis plan without redefining any endpoint.

The scientific judge instructions and `JUDGE_SYSTEM_PROMPT` are unchanged. The judge remains:

- Provider: `siliconflow`
- Model: `THUDM/GLM-Z1-9B-0414`
- Temperature: `0.0`
- Maximum output tokens: `1200`
- Timeout: `120.0` seconds
- Thinking: disabled

## Envelope normalization contract

Normalization policy version: `western-judge-json-envelope-v1`.

The execution layer accepts raw JSON or removes exactly one complete outer JSON-labelled or unlabelled Markdown code fence. Surrounding whitespace outside that single complete envelope may be ignored.

No other extraction or repair is permitted. In particular, the implementation does not search for a JSON substring, extract braces from prose, accept prose before or after a fence, combine multiple blocks, unwrap nested or incomplete fences, repair malformed JSON, add or remove JSON fields, change values or labels, or coerce semantic output.

After optional envelope removal, the existing strict `json.loads`, Pydantic `FormalJudgeOutput` validation, extra-field prohibition, claim rules, evidence-point rules, insufficiency rules, and Stage C semantic invariants apply unchanged. Envelope removal is local deterministic serialization normalization and never consumes a retry.

Every Stage C terminal record carries `judge_output_normalization` as `none`, `outer_json_markdown_fence_removed`, or null according to whether parsing used raw JSON, removed the permitted envelope, or never reached model-output parsing.

## Retry and execution safety unchanged

Retry remains limited to one second attempt for connectivity, timeout, HTTP 5xx, or malformed transport response. Markdown normalization, malformed model JSON, schema-invalid model JSON, rate limiting, truncation, unsupported finish reasons, and semantic validation failures do not create a retry.

Formal Stage C r2 requires the exact r2 run ID, exact r2 execution freeze commit as HEAD, a clean worktree, exact implementation and scientific hashes, exact frozen Stage A and primary Stage B anchors, exact ordered 192-cell identity, and continued incident-only status for the original Stage B outage attempt. The r1 run identity is not executable through the r2 formal path.

## Launch status at freeze

`FORMAL STAGE C NOT EXECUTED — ZERO FORMAL CELLS`
