# Evaluation-only benchmark area

Benchmark questions, reference answers, labels, and source articles are never retrieval-corpus inputs. External benchmark files belong under the gitignored `external/` directory only after their licences and upstream rights are verified. Run `python -m ingestion.check_benchmark_contamination` before any experiment and retain its scoped report; absence of detected overlap is not an unconditional zero-leakage claim.
