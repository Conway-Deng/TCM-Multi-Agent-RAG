# Publication Package Freeze Record — Phase II Western Manuscript v0.2.1

- **Freeze Timestamp (ISO-8601 UTC):** 2026-09-21T06:01:17Z
- **Branch:** eature/medirag-west-v0.1
- **Parent HEAD:** 983be960629547f7a0b655fabb9d08840b75bf2
- **Model:** Antigravity

---

## 1. Package Inventory
- **Main Figures:** 3
  - igures/Figure_1_study_flow.svg / .png
  - igures/Figure_2_stage_a_paired_recall.svg / .png
  - igures/Figure_3_semantic_full_coverage.svg / .png
- **Main Tables:** 3
  - 	ables/Table_1_stage_a_headline_metrics.md / .csv
  - 	ables/Table_2_semantic_full_coverage.md / .csv
  - 	ables/Table_3_unsupported_and_contradictions.md / .csv
- **Supplementary Tables:** 3
  - supplement/Table_S1_stage_a_complete_pairwise.md / .csv
  - supplement/Table_S2_semantic_secondary_outcomes.md / .csv
  - supplement/Table_S3_insufficient_evidence.md / .csv
- **Supplementary Figures:** 0
- **Captions:** CAPTIONS_v0.2.1.md
- **Source Data:** source_data/README.md + 14 derived compact CSV files

---

## 2. Visual Audit Results
- **Figure 1 (Study Flow Architecture):** PASS
  - The Western Semantic Follow-up v0.2 correctly branches from frozen Stage-B answers and does NOT visually appear to resume or complete terminated automated Stage C.
- **Figure 2 (Stage-A Paired Primary-Gold Chunk Recall Differences):** PASS
  - Stage-A paired recall differences and confidence intervals are visually clear, neutral, and contain no winner or binary significance annotations.
- **Figure 3 (Follow-up Full Evidence Coverage Paired Differences):** PASS
  - Semantic full-coverage paired differences and bootstrap confidence intervals are visually clear, neutral, and correctly represent R2 lower CI bound at zero. No clinical, causal, or winner interpretation is visually implied.

---

## 3. Methodological and Verification Integrity
- **Numerical Verification:** All displayed numerical estimates, paired differences, confidence intervals, McNemar tests, and case counts were programmatically verified against authoritative frozen CSV results.
- **Deterministic Rerun:** Execution into dual independent scratch directories confirmed 100% byte-identical outputs across all 34 publication artifacts.
- **Data Protection & License Audit:**
  - No Western source passage was copied into the publication package.
  - No generated answer full text was copied into the publication package.
  - No blind key mapping (stage_c2_blind_key.csv) was copied.
  - No protected evaluation workbook (stage_c2_blinded_eval_input.xlsx) was copied.
  - No raw Stage-B generation dataset was copied.
- **Experimental Integrity:** No Stage A, Stage B, Stage C, or semantic annotation experiment was rerun.
