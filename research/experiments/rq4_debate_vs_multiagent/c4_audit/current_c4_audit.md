# Current C4 audit

Audit classification before this RQ4 change: **B. DETERMINISTIC_AGGREGATION_ONLY**.

## Proven execution path

- Entry: `backend.main.research_run` → `ResearchWorkbench.run`.
- Routing: `_agent_ids` selected planner/request specialists and previously forced at least two multi-agent specialists.
- Initial generation: `ResearchWorkbench._run_agent` made one real specialist call, with one bounded retry, for each non-abstaining specialist.
- Old debate: `orchestration.debate.debate` counted shared evidence and emitted templated critique/revision summaries in Python.
- Peer visibility: no specialist prompt received another specialist's output.
- Critique model call: none.
- Revision model call: none.
- Consensus: `_synthesis` concatenated evidence-linked claims deterministically.
- Old debate-added model calls: 0. Total calls were only initial specialist calls.
- Fallback: rejected/failed specialist calls could become deterministic specialist fallback; old C4 did not expose required-stage failure semantics.

Relevant files/functions: `backend/orchestration/conditions.py::CONDITION_REGISTRY`, `backend/orchestration/workbench.py::ResearchWorkbench.run`, `ResearchWorkbench._run_agent`, `_agent_ids`, `_synthesis`, and `backend/orchestration/debate.py::debate`.

Conclusion: the prior C4 name described a trace format, not genuine LLM-mediated inter-agent debate.
