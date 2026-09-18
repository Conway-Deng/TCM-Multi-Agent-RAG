# Protocol Operational Amendment v0.1.2

`western_formal_v0.1.2` supersedes `western_formal_v0.1.1` before formal execution.

- `superseded_before_formal_execution = true`
- `formal_cells_executed_under_v0_1_1 = 0`
- `formal_cells_executed_under_v0_1 = 0`
- `scientific_design_changed = false`
- Reason: pre-execution clean-worktree gate failure caused by unignored local formal execution artifacts (`runs/**`, `cache/**`)

This defect was identified before formal Stage A execution. No formal result existed or was inspected, no benchmark question or formal cell was executed under v0.1 or v0.1.1, and no algorithm or prompt was modified. The benchmark, gold evidence, corpus, retrieval definitions, parameters, generator, judge, metrics, balanced 192-cell execution order, and statistical comparison families remain identical to v0.1 and v0.1.1.

## Defect analysis: clean-worktree gate vs. local execution artifacts

The frozen evaluation runner enforces a strict clean Git worktree gate before and during execution to guarantee reproducibility and freeze compliance. However:

1. `RunDirectory.create()` successfully passes the initial clean-worktree gate when the repository is clean.
2. It then creates `research/experiments/western_formal_v0_1/runs/<run_id>/run_manifest.json`.
3. `run_stage_a()` immediately calls `run.verify_run_manifest()`, which executes a clean-worktree check (`git status --porcelain`).
4. Because `research/experiments/western_formal_v0_1/runs/**` was not ignored in `.gitignore`, the newly created run manifest was detected as an untracked file, marking the repository dirty.
5. Consequently, Stage A failed its own cleanliness check before any retrieval cell was executed.
6. In addition, dense retrieval builds and writes a persistent embedding cache under `research/experiments/western_formal_v0_1/cache/`. Because `cache/**` was also not ignored, cache writes similarly marked the worktree dirty, causing resume and finalization checks to fail.

## Operational resolution

1. `.gitignore` is updated to ignore:
   - `research/experiments/western_formal_v0_1/runs/**`
   - `research/experiments/western_formal_v0_1/cache/**`
2. The clean-worktree safety gate in `RunDirectory.create()` and `verify_run_manifest()` is preserved in full force and is NOT weakened. Any unrelated tracked modifications or untracked development files outside the ignored paths continue to trigger immediate fatal rejection (`FatalFormalRunError`).
3. The protocol directories `protocol/`, `protocol_v0_1_1/`, and `protocol_v0_1_2/` remain fully tracked in Git.

## Copyright and publication safety

`runs/**` is ignored by Git in part because Stage A raw retrieval output contains source evidence excerpts extracted from the frozen corpus. These raw excerpts must not be inadvertently committed or pushed to public version control.

- Raw Stage A results and run directories must never be force-added or committed to Git.
- If formal metrics, manifests, or summary tables are to be published following formal Stage A execution, selected excerpt-free artifacts must be copied or materialized into an explicitly reviewed, separately tracked publication/results directory.
- This operational amendment maintains and reinforces existing copyright safeguards.
