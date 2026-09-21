# Phase II Western Manuscript v0.2.1 — FROZEN

## 1. Manuscript Identity and Freeze Metadata

- Manuscript identity: **Phase II Western Manuscript v0.2.1**
- Freeze timestamp: `2026-09-21T12:50:00+08:00` (`2026-09-21T04:50:00Z`)
- Branch: `feature/medirag-west-v0.1`
- Parent HEAD: `9e9b56f20db6aec097041dc1c5a77eb3d2a259cd`
- Manuscript path: `research/manuscripts/phase_ii_western_v0_2_1/PHASE_II_MANUSCRIPT_v0.2.1.md`
- Claim-map path: `research/manuscripts/phase_ii_western_v0_2_1/CLAIM_EVIDENCE_MAP_v0.2.1.md`
- External-reference-register path: `research/manuscripts/phase_ii_western_v0_2_1/EXTERNAL_REFERENCE_REGISTER_v0.2.1.md`
- Manuscript word count: `4,906`
- Claim-map entries: `59`
- Repository claim IDs: `C01-C53` (53 entries)
- External claim IDs: `E01-E06` (6 entries, all `externally-supported`)
- External references: `R1-R10` (10 unique approved references)
- Unique DOI count: `10`
- Citation placeholders remaining: `0`

## 2. Review and Audit Completion

Phase II Western Manuscript v0.2.1 has successfully completed:
1. Scientific manuscript review
2. External literature selection
3. Citation integration
4. Final literature-to-claim audit

### Final Literature-Audit Statement
> **ALL EXTERNAL CITATIONS SUPPORT THEIR ASSIGNED BOUNDED CLAIMS.**

## 3. Scientific Identity

The manuscript integrates two scientifically distinct components:

### A. Western Formal Study v0.1.5
- Stage A completed (192 retrieval cells across 48 cases and 4 frozen conditions R0–R3).
- Stage B completed (192 primary answer generation cells with fixed `Qwen/Qwen3-8B` generator).
- Original automated Stage C prospectively terminated under defined stopping rules without qualifying a Primary Judge.

### B. Western Semantic Follow-up v0.2
- Separate post-study semantic evaluation.
- Reused unchanged frozen Stage-B answers.
- Single GPT-5.6 Sol evidence-grounded evaluator.
- Retrieval-condition identity concealed during annotation (blinded evaluation).
- W-RQ2 semantic estimates available (168 cells across 42 answerable cases).
- W-RQ3 descriptive estimates available (24 cells across 6 insufficient-evidence cases).

**Explicit Non-Reopening Statement:**
The follow-up does not retroactively reopen or complete automated Stage C within Western Formal Study v0.1.5.

## 4. Scientific Boundaries and Limitations

- **Pilot corpus:** 16 systematic reviews / 271 chunks across 4 symptom domains.
- **Benchmark:** 48 cases (42 answerable, 6 insufficient-evidence).
- **One fixed generator:** Single generator model (`Qwen/Qwen3-8B`).
- **One semantic evaluator:** Single GPT-5.6 Sol evaluator applying frozen rubrics.
- **No human adjudication:** No human graders participated in scoring.
- **No clinician adjudication:** No medical doctors or clinical experts evaluated answers.
- **No inter-rater reliability:** Multi-judge agreement was not estimated.
- **No judge-family robustness estimate:** Alternative evaluator model families were not tested.
- **Evidence-grounded semantic evaluation is not clinical validation:** Measures textual grounding against supplied excerpts, not medical correctness or clinical validity.
- **Unsupported-claim annotation is not a validated general hallucination metric:** Rubric-based judgment against supplied corpus excerpts only.
- **No causal inference between retrieval and answer quality:** Observational descriptive alignment only; design does not establish causal transfer from retrieval to generation.
- **No clinical safety/correctness conclusion:** Findings do not demonstrate clinical effectiveness, diagnostic accuracy, or patient safety.

### Strongest Allowed Conclusion
> "Within this frozen 16-review, 48-case pilot and under a single blinded GPT-5.6 Sol evidence-grounded evaluator, semantic evidence coverage and unsupported-claim behavior differed descriptively across retrieval conditions."

## 5. Literature Provenance and Claim Mapping

The six external claims (E01–E06) are mapped to approved references (R1–R10) as follows:

- **E01:**
  - R1: Zhao et al. 2026 (*J Med Internet Res*, DOI: `10.2196/90046`)
  - R2: Samuel et al. 2026 (*Proc ACM SIGIR ICTIR*, DOI: `10.1145/3805713.3820424`)
- **E02:**
  - R3: Wu et al. 2025 (*Nat Commun*, DOI: `10.1038/s41467-025-58551-6`)
  - R4: Carl et al. 2026 (*Eur J Cancer*, DOI: `10.1016/j.ejca.2025.116168`)
- **E03:**
  - R5: Liu et al. 2020 (*BMJ*, DOI: `10.1136/bmj.m3164`)
  - R6: Vasey et al. 2022 (*Nat Med*, DOI: `10.1038/s41591-022-01772-9`)
- **E04:**
  - R7: Ru et al. 2024 (*NeurIPS 2024*, DOI: `10.52202/079017-0692`)
  - R2: Samuel et al. 2026 (*Proc ACM SIGIR ICTIR*, DOI: `10.1145/3805713.3820424`)
- **E05:**
  - R8: Pattnayak & Bhatia 2026 (*ACL 2026 Short Papers*, DOI: `10.18653/v1/2026.acl-short.22`)
  - R9: Bavaresco et al. 2025 (*ACL 2025 Short Papers*, DOI: `10.18653/v1/2025.acl-short.20`)
- **E06:**
  - R9: Bavaresco et al. 2025 (*ACL 2025 Short Papers*, DOI: `10.18653/v1/2025.acl-short.20`)
  - R10: Xu et al. 2025 (*EMNLP 2025 Findings*, DOI: `10.18653/v1/2025.findings-emnlp.1036`)

*Note: Article full texts are not copied into the repository; bibliographic metadata, DOIs, and exact bounded roles are cataloged in `EXTERNAL_REFERENCE_REGISTER_v0.2.1.md`.*

## 6. Immutable Artifact Provenance Hashes

| Manuscript artifact | Relative path | SHA256 |
|---|---|---|
| Manuscript text | `research/manuscripts/phase_ii_western_v0_2_1/PHASE_II_MANUSCRIPT_v0.2.1.md` | `64b82b310546b57fb2342fc416bf4cf7b3167941d1805a69834df8da8699525c` |
| Claim-evidence map | `research/manuscripts/phase_ii_western_v0_2_1/CLAIM_EVIDENCE_MAP_v0.2.1.md` | `0bc12aa9b899fdae715f2b54ede1d55fad2342c2d281f34d2f44bd939e0eb749` |
| External reference register | `research/manuscripts/phase_ii_western_v0_2_1/EXTERNAL_REFERENCE_REGISTER_v0.2.1.md` | `8a20e6b640eed17b636a5ed6aa4851628da7ad49c4a20459bad647bb1d1d9bb3` |
