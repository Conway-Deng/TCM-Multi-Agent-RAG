# Research overview

## Supervisor-document alignment

The supervisor specification defines the wider MediRAG-Judge cluster: multi-paradigm retrieval, multi-agent deliberation, LLM-as-a-Judge governance, evidence, safety, conflict, confidence, and explainability. Project 2 assigns TCM-RAG work on syndrome differentiation, herbal medicine, acupuncture, meridian theory, constitution analysis, knowledge representation, retrieval quality, consistency, and explainability.

This repository specializes those mechanisms to TCM. It does not claim that the supervisor document defines a TCM-only multi-agent architecture.

## Implemented

- TCM Single RAG baseline and TCM specialist multi-agent paths
- C0-C6 condition registry and R0-R3 retrieval registry
- query planner plus six specialist roles
- debate, critique/revision traces, deterministic weighting, and judge arbitration
- evidence, hallucination, safety, conflict, confidence, and provenance judges
- reproducibility traces, prompt hashes, datasets, experiment runner, exports, and analysis
- human-review templates and agreement utilities
- deterministic no-key provider mode

## Boundaries

- `RQ3-TCM-within-paradigm proxy` studies disagreement among TCM specialists; it is not cross-paradigm evidence.
- RQ6 infrastructure collects human ratings, but RQ6 remains unanswered without real participants.
- TCM source categories are recorded, not treated as equally strong scientific evidence.
- No clinical validity, trust, or safety conclusion follows from passing tests.
