# Human evaluation

`HumanReview` includes anonymous reviewer ID/role, evidence support, completeness, explainability, safety, uncertainty communication, trustworthiness, preference, and notes. Defaults use 1-5 Likert scales.

Experiments export `human_review_template.csv`. `backend/evaluation/human.py` validates imports, aggregates descriptively, and calculates Cohen's kappa for paired categorical ratings.

Validate and aggregate a completed file with `python -m research.human_evaluation path/to/completed_reviews.csv`.

Manual decisions remain: ethics/consent, recruitment, expertise criteria, randomization, blinding, order effects, sample-size justification, missing-data rules, and final interpretation. Likert data are ordinal; means are descriptive. No responses are fabricated.
