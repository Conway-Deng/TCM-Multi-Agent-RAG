# Western Formal Study v0.1.5 — Final Study Status

## 1. Study identity

- Study: **Western Formal Study v0.1.5**
- Final scientific protocol identity: `western_formal_v0.1.5`
- Final Wave-2 archival commit: `d6415406bcdcae5f76c2fbd2d631cc01fcd5d860`
- Corpus: **MediRAG-West PMC Open Access Pilot Corpus**, version `medirag-west-v0.1-pilot`; 16 review articles and 271 deterministic chunks across four topic domains.
- Corpus chunks SHA256: `8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b`
- Corpus source registry SHA256: `722273140906b238e88cfdab4ddbb12d73c478f686ae23d0f501738ee6820703`
- Benchmark: **MediRAG-West Pilot Benchmark v0.1**, version `western-pilot-v0.1`; 48 cases across cough, dyspepsia/digestive symptoms, headache, and constipation.
- Benchmark SHA256: `29d4a2c08bd8529f77d7d9faff7e739a5c60775dd04d99711d0e254a7aa200c6`
- Benchmark manifest SHA256: `bd8fc5105329d5d325fa8910b8a642bac6ddc954a25df6b9e299158aa29a22ae`
- Frozen generator: provider `siliconflow`, model `Qwen/Qwen3-8B`, temperature `0.0`, maximum output `256` tokens, timeout `120` seconds, one generation per cell, retrieval top-k `4`, and the frozen WesternEvidenceAgent prompt contract.

### Protocol evolution

The initial `western-formal-v0.1` protocol and `western_formal_v0.1.1` were superseded before any formal cell was executed. `western_formal_v0.1.2` repaired pre-execution handling of local run and cache artifacts without changing the scientific design and governed the completed Stage A and Stage B runs. After the original Stage C judge route did not produce a valid formal semantic dataset, `western_formal_v0.1.3` prospectively introduced replacement-policy v1. `western_formal_v0.1.4` prospectively introduced the free-only Wave-1 policy. Following Wave-1 exhaustion, `western_formal_v0.1.5` prospectively defined the final zero-cost Wave-2 discovery, deterministic candidate-pool freeze, and terminal stopping rule. These Stage C amendments did not alter the frozen corpus, benchmark, Stage A, Stage B, generator, judge prompt, judge schema, or scientific research questions.

## 2. Research questions and availability

| Research question | Definition | Final availability |
|---|---|---|
| W-RQ1 | How do retrieval strategies affect gold-evidence retrieval within the frozen MediRAG-West pilot corpus? | Estimable; supported by the frozen Stage-A results. |
| W-RQ2 | With the generator held fixed, how do retrieval strategies affect evidence coverage and unsupported-claim behavior in generated Western pilot answers? | Semantic estimate unavailable in this study version. |
| W-RQ3 | How does the system behave when the frozen pilot corpus provides incomplete or insufficient evidence? | Semantic estimate unavailable in this study version. |

Stage A and Stage B remain valid. No W-RQ2 or W-RQ3 semantic conclusion is inferred from the absence of a qualified automated judge.

## 3. Stage A — retrieval

Frozen run: `western-formal-v0.1.2-stage-a-20260918-01`. All 192 retrieval cells completed, with zero technical failures. The headline retrieval denominator contains 42 supported or partially supported cases with non-empty primary gold evidence.

| Condition | Aggregate primary-gold chunk recall@4 | Aggregate primary-source recall@4 | Hit@4 | MRR |
|---|---:|---:|---:|---:|
| R0 | 0.428571 | 0.890909 | 0.595238 | 0.450397 |
| R1 | 0.634921 | 0.890909 | 0.785714 | 0.605159 |
| R2 | 0.539683 | 0.890909 | 0.738095 | 0.573413 |
| R3 | 0.523810 | 0.836364 | 0.690476 | 0.581349 |

Pairwise comparisons against R0 used the successful-pair intersection, with no zero imputation:

| Comparison | Mean recall difference | Bootstrap 95% CI | Exact two-sided McNemar p |
|---|---:|---:|---:|
| R1 − R0 | +0.206349 | [0.083333, 0.333333] | 0.0385742 |
| R2 − R0 | +0.0952381 | [0.0119048, 0.190476] | 0.03125 |
| R3 − R0 | +0.107143 | [0.0119048, 0.218254] | 0.2890625 |

R1 measured higher on the headline retrieval metrics in this frozen pilot. This does not establish global superiority or a general model ranking. Retrieval latency is confounded by cache state and execution order and is therefore not cleanly interpretable.

## 4. Stage B — generation

### Preserved original outage attempt

The Stage B attempt attached to `western-formal-v0.1.2-stage-a-20260918-01` is retained as an audited provider/infrastructure-outage epoch. It contains 192 terminal records: 106 completed and 86 technical failures. The failures form a consecutive suffix beginning at cell 107, with zero later successes. This attempt is excluded from primary semantic analysis and was never pooled with the repeat. Its sealed Stage B SHA256 is `89b1e4166daefa738be4572f84825711336147560945a93141b6a7569d61166f`.

### Frozen primary repeat

- Run ID: `western-formal-v0.1.2-stage-b-r1-20260919-01`
- Status: `stage_b_repeat_frozen_primary`
- Completion: 192/192 cells completed; 0 technical failures
- Raw/generation SHA256: `afc0665858b0493d9c4dfbc2d8990ccd89c663f2b63278221407cb876feaf17c`
- Run manifest SHA256: `32fbc0765fc91395af187abb46b92d2fb13b9eed3acbea016f8ac18a6bc00511`
- Repeat scope: all 192 cells; original successes were not reused

The Stage B generation dataset is complete and remains valid. Stage B alone provides no semantic quality claim because the formal automated semantic judging stage was not completed.

## 5. Stage C history

- The original `THUDM/GLM-Z1-9B-0414` judge route did not yield a valid formal semantic dataset. Its execution incident and readiness preflights remain preserved and ineligible for primary analysis.
- Replacement-policy v1 (`western_formal_v0.1.3`) governed a provider-candidate attempt under prospectively frozen rules; it did not create a valid formal Stage C semantic dataset.
- Free-only Wave 1 (`western_formal_v0.1.4`) exhausted its frozen candidate sequence without selecting a Primary Judge. Qualification outputs were not formal research data.
- Free-only Wave 2 (`western_formal_v0.1.5`) used timestamped provider-catalog, pricing, and capability discovery followed by offline deterministic eligibility processing. Discovery made no semantic or generation probes.
- The final Wave-2 candidate pool froze with `complete_eligible_model_ids = []`, `pool_size = 0`, and `selected_candidates = []`; no Primary Judge was selected.
- Wave 3 is prohibited. Automatic paid fallback is prohibited. In-study judge-interface redesign is prohibited. No Wave-2 formal Stage C run was created, and no valid formal semantic Stage C dataset exists.

Individual candidate outcomes are operational/readiness observations under frozen provider and interface conditions, not scientific judgments that a model is bad, incapable, or globally inferior.

## 6. Final Stage-C interpretation

The final prospectively governed zero-cost Wave-2 pool contained no model that satisfied every frozen eligibility requirement using the available non-semantic evidence. Automated semantic Stage C therefore terminated under the prospectively defined stopping rule.

This is not a model-quality conclusion. It records exhaustion of the governed automated-judge selection procedure under the study's frozen eligibility, cost, provider, and interface constraints.

## 7. Final research-question availability

- **W-RQ1:** available and supported by the frozen Stage-A results.
- **W-RQ2:** semantic estimate unavailable in this study version.
- **W-RQ3:** semantic estimate unavailable in this study version.
- **Preserved validity:** Stage A and the complete frozen primary Stage B generation dataset remain valid.

No W-RQ2 or W-RQ3 effect, quality, safety, or incomplete-evidence conclusion is estimated or implied.

## 8. Scientific limitations

- The Western corpus is a 16-review pilot corpus limited to four topic domains.
- The benchmark contains 48 cases and is specific to the frozen 271-chunk pilot corpus.
- Benchmark drafting and secondary adjudication were AI-assisted; no human, clinician, physician, or domain-expert adjudication was completed.
- Automated semantic judge qualification could not be completed, so no formal Stage C semantic dataset exists.
- The generator was fixed to `Qwen/Qwen3-8B`; findings do not estimate generator-family variability.
- Provider availability, account access, interface compatibility, and zero-cost constraints affected judge selection.
- Latency is confounded by cache state and execution order and is not cleanly interpretable.
- Results are pilot-specific and must not be presented as general medical-performance or model rankings.

## 9. Reproducibility anchors

| Frozen item | SHA256 |
|---|---|
| Western corpus chunks | `8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b` |
| Western source registry | `722273140906b238e88cfdab4ddbb12d73c478f686ae23d0f501738ee6820703` |
| Western Pilot Benchmark v0.1 | `29d4a2c08bd8529f77d7d9faff7e739a5c60775dd04d99711d0e254a7aa200c6` |
| Benchmark manifest | `bd8fc5105329d5d325fa8910b8a642bac6ddc954a25df6b9e299158aa29a22ae` |
| Protocol v0.1.2 (`protocol.json`) | `af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192` |
| Stage A retrieval/raw artifact | `91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e` |
| Primary Stage B raw/generation artifact | `afc0665858b0493d9c4dfbc2d8990ccd89c663f2b63278221407cb876feaf17c` |
| Primary Stage B run manifest | `32fbc0765fc91395af187abb46b92d2fb13b9eed3acbea016f8ac18a6bc00511` |
| Wave-2 policy | `5ac5b5bab86b853fe719303e92defcadc609015b29648630b29ed5db1191b596` |
| Wave-2 provider catalog | `f30ee7bbef701d60c20026d86803549a43bedf610af2201cb870d54a326c9da8` |
| Wave-2 pricing ledger | `1f91510871def6953e79138240a261030a90a211341fac85b5661778ce7cc211` |
| Wave-2 capability ledger | `dee463f0002b765b06a999005083cbffaf68884f5169b1cd704d98b7715cb68c` |
| Wave-2 eligibility ledger | `ca0e79020ec03abd9b7a18fb192211fc5fa829abeacbdd311f7de56082528a37` |
| Wave-2 candidate-pool freeze | `c94a4a062e3ef956b5a9454bcc778a86a225894a249449d96d547d645bd61484` |
| Wave-2 exhaustion | `9da09729c9ed4986fab05b6de979d25025bce42836b7b81fdb108207e2ce8886` |

## 10. Final study state

| Component | Final state | Research availability |
|---|---|---|
| Stage A | Complete and frozen | W-RQ1 available |
| Stage B | Complete; frozen primary repeat | Generation dataset available |
| Stage C | Prospectively terminated | W-RQ2/W-RQ3 semantic estimates unavailable |
| Wave 3 | Prohibited | Not applicable |
| Paid fallback | Prohibited | Not applicable |
