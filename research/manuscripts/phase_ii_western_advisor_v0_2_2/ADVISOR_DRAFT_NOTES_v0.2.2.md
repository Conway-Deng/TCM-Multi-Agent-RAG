# Advisor Draft Notes — Phase II Western Manuscript v0.2.2

## Version boundary

This advisor-facing draft is a presentation and manuscript-assembly version only. It does not create a new experiment version, alter Western Formal Study v0.1.5, alter Western Semantic Follow-up v0.2, or modify frozen Phase II Western Manuscript v0.2.1.

## Reorganization

- Reorganized the frozen manuscript into one continuous advisor-facing paper with the requested 15 numbered sections and References.
- Separated system architecture, corpus, benchmark, retrieval protocol, Stage-A evaluation methods, Stage-B generation, historical Stage-C termination, and follow-up methods into a conventional Methods-to-Results sequence.
- Consolidated experimental findings under Section 11 while retaining the historical study/follow-up boundary.
- Embedded all three frozen main tables so the draft is readable without opening package files.
- Added relative-path callouts for the three frozen publication figures; no figure was copied or regenerated.
- Created a separate supplement containing the three frozen supplementary tables.

## Prose shortened or consolidated

- Removed repository-path and drafting-control language from the narrative manuscript.
- Replaced audit-style repetition of complete table rows with headline values and direct references to tables or supplement sections.
- Kept the primary Stage-A and semantic paired differences in prose because they carry the central scientific narrative.
- Moved full Stage-A discordance statistics, partial-credit distributions, unsupported-claim count distributions, expected-point totals, and complete W-RQ3 cell labels to the supplement.
- Consolidated repeated statements about missing v0.1.5 semantic estimates while retaining them in the Abstract, research-question table, historical Stage-C section, Results, and Conclusion where the boundary is scientifically necessary.

## Figure insertion points

1. **Figure 1** follows Section 3, after the system architecture and overall study-design explanation. It visually separates Western Formal Study v0.1.5 from the later Western Semantic Follow-up v0.2 and shows the follow-up branching from frozen Stage-B answers.
2. **Figure 2** appears in Section 11.2 immediately after the Stage-A paired-difference discussion.
3. **Figure 3** appears in Section 11.4 immediately after the follow-up full-coverage paired-difference discussion.

All image references point to `../phase_ii_western_v0_2_1/publication_package/figures/`.

## Table insertion points

1. **Table 1**, Stage-A headline retrieval metrics, appears in Section 11.2.
2. **Table 2**, follow-up full-coverage descriptive results, appears in Section 11.4.
3. **Table 3**, unsupported-claim and contradiction outcomes, appears in Section 11.5.
4. **Tables S1–S3** are reproduced in `SUPPLEMENT_v0.2.2.md` in the order frozen by the publication package.

## Supplement construction

The supplement reproduces the frozen publication-package Markdown tables without changing their numerical contents:

- Table S1: complete Stage-A paired retrieval statistics;
- Table S2: partial-credit coverage, unsupported-claim counts, and expected-point labels;
- Table S3: W-RQ3 condition distributions and all 24 case-condition labels.

No supplementary analysis, figure, endpoint, comparison, or derived statistic was added.

## Title decision

The frozen title was retained unchanged:

> **Corpus-Bounded Western Evidence Retrieval in MediRAG: A Reproducible Pilot and Blinded Semantic Follow-up**

It is scientifically suitable for an advisor-facing draft, identifies the bounded pilot and blinded follow-up, and does not imply clinical validation. No alternative title is proposed.

## Abstract changes

- Converted the opening summary into a conventional structured abstract with Background, Objective, Methods, Results, and Conclusions.
- Preserved the frozen corpus, benchmark, retrieval, generation, evaluator, endpoint, bootstrap, and result values.
- Made the separate post-study nature of Follow-up v0.2 explicit.
- Retained pilot-scale, single-evaluator, non-causal, and non-clinical qualifications.

## Readability and terminology changes

- Added transitions between study architecture, experimental stages, and the later follow-up.
- Standardized references to “Western Formal Study v0.1.5,” “Western Semantic Follow-up v0.2,” “automated Stage C,” and the “primary Stage-B repeat.”
- Used neutral comparison language and avoided winner, superiority, optimality, binary-significance, causal, and clinical-safety language.
- Clarified that condition-label concealment is not perfect perceptual blinding because answer and evidence content could indirectly signal retrieval characteristics.
- Retained that semantic labels were produced by one GPT-5.6 Sol evidence-grounded evaluator without human or clinician adjudication, inter-rater reliability, or judge-family robustness assessment.

## Scientific-integrity confirmation

- No Stage-A, Stage-B, Stage-C, or semantic-evaluation experiment was rerun.
- No frozen experimental artifact, manuscript v0.2.1 file, publication-package file, statistical method, semantic judgment, or reference was modified.
- No numerical scientific result was changed or newly derived.
- The approved 10-reference bibliography and DOI identities were preserved.
- v0.2.2 is solely an advisor-facing presentation version.

## Final review correction

The final presentation review normalized the three embedded main-table title separators to match the frozen publication-package titles. No prose claim, table value, caption value, statistical statement, or scientific interpretation changed.
