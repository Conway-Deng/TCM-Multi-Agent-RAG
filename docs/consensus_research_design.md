# ARCHIVED PRE-V1: Consensus Research Design

Inactive historical design. Use `docs/experiment_design.md`.

The first controlled comparison is:

1. `tcm_single`: existing TCM-RAG only.
2. `concatenate`: TCM plus synthetic Western fixture, with no consensus claim.
3. `weighted`: transparent deterministic aggregation with evidence, fixture, safety, fallback, and abstention factors.
4. `same_model_debate`: a separately invoked Debate Agent using the same underlying model as other configured roles.
5. `same_model_debate_judge`: separate Debate, Evidence, Safety, Conflict, Confidence, and Synthesis calls.

Same-model multi-agent operation is valid because agent identity comes from independent invocations, narrow role prompts, inputs, outputs, and evaluation stages—not from requiring multiple providers. Later heterogeneous-model experiments can override each role model.

The design records evidence IDs per model stage and keeps the domain-agent evidence fixed across strategy comparisons. It preserves disagreement rather than forcing a unified diagnosis. Deterministic TCM urgent routing has higher priority than any LLM judge output.

The synthetic Western fixtures enable orchestration and failure-mode testing before MediRAG-West exists. They are not appropriate for evaluating clinical correctness, retrieval quality, or real guideline support.
