# Western Stage B repeat execution freeze v0.1.2-r1

This operational freeze preserves the original sealed Stage B attempt as a run-level provider-outage incident and authorizes one full 192-cell repeat. It does not alter the scientific protocol, benchmark, Stage A retrieval, retrieval conditions, generator prompt, provider/model, temperature, maximum tokens, timeout, or per-cell retry semantics.

## Original outage incident

- Original run ID: `western-formal-v0.1.2-stage-a-20260918-01`
- Original Stage B SHA256: `89b1e4166daefa738be4572f84825711336147560945a93141b6a7569d61166f`
- Original Stage B seal-manifest SHA256: `29ffec35f6e0f80a6543935b4ab248aefb8a8387f1ed392d2657cd5445feecb0`
- Original Stage B execution-manifest SHA256: `68d1435270c1b882f866042e644f71a2f21156dbfcafa061314a2759d5712939`
- Outcome: 192 terminal records; 106 completed; 86 technical failures; failures occupy the uninterrupted suffix beginning at position 107; zero later successes.
- Classification: audited provider-outage incident, preservation only.
- Primary semantic dataset eligibility: `false`
- Stage C eligibility: `false`
- Standard B-finalization: withheld.

The incident classification uses operational failure metadata only. The semantic content of the 106 successful answers was not inspected for this decision.

## Authorized repeat

- Repeat run ID: `western-formal-v0.1.2-stage-b-r1-20260919-01`
- Repeat ordinal: `1`
- Scope: all 192 Stage B cells in frozen order.
- Original successful answers reused: `false`
- Intended role after a successful non-outage finalization: primary Stage B semantic dataset.
- Selective regeneration after sealing: prohibited.
- Automatically authorized further repeat after r1: none.

The repeat derives its inputs from the canonical frozen Stage A run but writes to a separate repeat directory. It cannot mutate, resume, standard-finalize, or substitute records into the original sealed attempt.

## Pre-repeat readiness gate

Before any formal repeat record or execution manifest is created, the same configured provider and `Qwen/Qwen3-8B` model must return exactly `READY` for three sequential non-formal probes. Probes use temperature `0.0`, maximum tokens `16`, timeout `120.0` seconds, and a 10-second interval. All three must pass. The readiness receipt is single-use for the repeat start, SHA-bound into the repeat execution manifest, and excluded from formal JSONL data.

## Frozen repeat failure policy

The per-cell two-attempt rule remains unchanged. A repeat-level outage is classified when at least 20 consecutive terminal infrastructure failures form the final suffix and no success follows the first record in that suffix. Allowed infrastructure error types are connectivity, HTTP 5xx, malformed response, rate limit, and timeout. An outage-classified r1 is preserved as a separate audited incident, is ineligible for primary analysis and Stage C, and does not authorize a third automatic run. Isolated technical failures below the run-level outage rule remain ordinary protocol technical missingness.

## Reproducibility anchors

- Scientific protocol: `western_formal_v0.1.2`
- Protocol SHA256: `af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192`
- Stage A checkpoint commit: `5eb40146f026b42547220b0f0cfd077d72a75562`
- Stage A retrieval SHA256: `91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e`
- Original Stage B execution freeze commit: `7da777984bc6a3ffef0e0514598848142788e474`
- Repeat implementation commit: `8168531c6936f00fe5ab8bebadf8638a7772259c`
- Incident freeze SHA256: `79802297da6d06ff4ad6c1835434c29c43f6960800ea9a4ff38c0075a1d450bc`

The exact implementation file hashes are frozen in `execution.json`. The Git commit containing this directory is the repeat execution freeze commit resolved by the runtime verifier.

## Execution status

The formal repeat has not been executed. The provider readiness gate has not been run. Stage C has not been run.
