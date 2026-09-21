# Western Stage-A publication package v0.1.5

This directory is a derived publication package for frozen Western Formal Study Stage A. It addresses W-RQ1 only. The frozen Stage-A raw retrieval evidence remains authoritative, and generating this package does not constitute a new experimental run or rerun retrieval.

W-RQ2 and W-RQ3 semantic estimates remain unavailable in this study version. No Stage-B generation content or Stage-C qualification output is used here.

## Regeneration

From the repository root, using the existing project environment:

```text
.venv\Scripts\python.exe scripts\build-western-stage-a-publication.py
```

The builder verifies all frozen input hashes, calls the existing Stage-A metric implementations, checks the recomputed values against the sealed results, and then recreates the CSV, SVG, PNG, Markdown, and provenance outputs. The PNG exports are 300 dpi. The figures are generated from the publication CSV tables after those tables are derived from frozen Stage-A data.

## Interpretation boundary

The package describes retrieval outcomes within a 16-review, 271-chunk, four-topic pilot corpus and a 48-case benchmark. The headline denominator is 42. Latency is intentionally excluded from comparative conclusions because cache state and execution order confound it. The package contains no answer-quality, clinical-quality, W-RQ2, or W-RQ3 inference.
