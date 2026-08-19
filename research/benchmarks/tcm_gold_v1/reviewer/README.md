# Local human reviewer

From `research/benchmarks/tcm_gold_v1`, launch:

```powershell
python reviewer/reviewer_server.py
```

Open <http://127.0.0.1:8765>. The server reads `benchmark_v1.jsonl`, serves one question at a time, and writes only reviewer decisions to `human_review.json`. It has no research API, LLM, SiliconFlow, or external network integration.

Review order prioritizes multi-target questions, liver-yang, Red Ginseng, remaining hard items, medium items, then easy items. Use `APPROVED`, `REVISE`, or `REMOVE`; fact-level `SUPPORTED`, `UNCLEAR`, and `UNSUPPORTED` labels are optional.
