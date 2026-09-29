# Reference-Unit Mechanical Infrastructure

## Protocol Anchor
- **Protocol ID**: `CPAA1-REFERENCE-UNIT-PROTOCOL-V1`
- **Study ID**: `cross-perspective-advisory-ablation-v1`
- **Specification**: `../REFERENCE_UNIT_PROTOCOL_V1.md`
- **Frozen Protocol SHA256**: `5ab2f681e605f3bc75ef6e91fa8d864a102aa60e6b14efdda132448845dcb46b`

---

## CRITICAL BOUNDARY NOTICE

**THIS INFRASTRUCTURE DOES NOT VERIFY SEMANTIC SUPPORT.**

This infrastructure is strictly mechanical. It does not possess, simulate, or substitute for human clinical or semantic judgment.

### What Mechanical Infrastructure Verifies
1. **Schema Conformity**: Exact fields, versions, study constants, and enum values.
2. **Identifier & Hash Integrity**: Correct syntax of `cpaa1:ru:<question_id>:<ordinal>`, SHA256 length/format, packet canonical hash alignment, and chunk text hash alignment against frozen packets.
3. **Span Coordinates**: Valid offset bounds (`0 <= start < end <= text_length`) in unmodified Unicode code points.
4. **Structural Protocol Relationships**:
   - `perspective_scope="both"` requires pertinent anchors from both TCM and Western streams.
   - `support_scope="packet_bounded_absence"` requires `unit_type` in `{"evidence_gap", "limitation"}` and complete 8-evidence `scope_audit` coverage.
   - `review_status="reconciled"` and final ID assignment for final-candidate validation mode.

### What Human Reviewers Exclusively Decide
Human reviewers (Reviewer A and Reviewer B, and the third adjudicator where required) exclusively determine:
- Question relevance
- Semantic support from frozen evidence
- Unit decomposition and granularity
- Deduplication and substantive distinctness
- Cross-perspective comparability and conflict/agreement
- Limitation eligibility and necessity
- Reconciliation and final reference unit consensus

**No language model, agent, or automated tooling may populate, rewrite, merge, split, select, label, or adjudicate actual reference units.**

---

## Directory Structure

```
reference_units/
├── README.md                           # This boundary document
├── __init__.py                         # Package exports
├── reference_unit_schema.py            # Pydantic schemas for EvidenceSpan, EvidenceAnchor, ReferenceUnitRecord
├── reference_unit_validation.py        # Mechanical validators and FrozenPacketAnchorIndex
└── templates/                          # Non-data blank templates
    ├── reference_unit_record.template.json
    ├── reviewer_A_submission.template.jsonl
    └── reviewer_B_submission.template.jsonl
```

---

## Validation Modes

1. **`mode="draft"`**:
   Permits work-in-progress annotation records during independent human annotation (Reviewer A / B). Allows `review_status` of `draft` or `disputed`, and permits unassigned or temporary `reference_unit_id`.

2. **`mode="final_candidate"`**:
   Enforces strict readiness criteria for final frozen reference candidates. Requires `review_status="reconciled"`, a deterministic final identifier matching `cpaa1:ru:<question_id>:<three-digit ordinal>`, non-empty substantive unit text, non-empty support rationale, and full structural anchor compliance.
