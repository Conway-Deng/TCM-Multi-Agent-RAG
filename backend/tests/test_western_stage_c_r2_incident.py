from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from western import formal_eval as f


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "research/experiments/western_formal_v0_1/runs" / f.STAGE_C_RUN_ID


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def copied_r2(tmp_path: Path) -> f.StageCDirectory:
    destination = tmp_path / f.STAGE_C_RUN_ID
    shutil.copytree(SOURCE, destination)
    (destination / "stage_c_incident_manifest.json").unlink(missing_ok=True)
    (destination / "STAGE_C_EXECUTION_INCIDENT.md").unlink(missing_ok=True)
    return f.StageCDirectory(destination)


def test_actual_r2_source_is_exact_stable_prefix_with_observed_incident_counts() -> None:
    stage_c = f.StageCDirectory(SOURCE)
    records, counts = f._verify_stage_c_r2_incident_source(ROOT, stage_c)
    assert len(records) == 39
    assert counts == {
        "row_count": 39,
        "completed": 0,
        "output_schema_failure": 19,
        "technical_failure": 20,
        "timeout_final_error": 20,
        "first_experiment_id": records[0]["experiment_id"],
        "last_experiment_id": records[-1]["experiment_id"],
        "unique_experiment_ids": 39,
        "exact_primary_stage_b_prefix": True,
    }
    assert _sha(stage_c.stage_path()) == f.STAGE_C_R2_JUDGMENTS_SHA256
    assert _sha(stage_c.execution_manifest_path()) == f.STAGE_C_R2_EXECUTION_MANIFEST_SHA256


def test_incident_finalization_preserves_every_source_byte_and_is_non_overwriting(copied_r2: f.StageCDirectory) -> None:
    before_raw = copied_r2.stage_path().read_bytes()
    before_execution = copied_r2.execution_manifest_path().read_bytes()
    hashes = f.finalize_stage_c_r2_incident(ROOT, copied_r2)
    assert copied_r2.stage_path().read_bytes() == before_raw
    assert copied_r2.execution_manifest_path().read_bytes() == before_execution
    assert hashes["stage_c_judge.jsonl"] == f.STAGE_C_R2_JUDGMENTS_SHA256
    assert hashes["stage_c_execution_manifest.json"] == f.STAGE_C_R2_EXECUTION_MANIFEST_SHA256
    manifest = json.loads(copied_r2.incident_manifest_path().read_text(encoding="utf-8"))
    assert manifest["status"] == "stage_c_execution_incident"
    assert manifest["reported_interruption_snapshot"] == f.STAGE_C_R2_REPORTED_SNAPSHOT
    assert manifest["preserved_counts"]["row_count"] == 39
    assert manifest["snapshot_discrepancy"]["additional_rows_in_stable_preserved_file"] == 6
    assert manifest["eligible_as_primary_stage_c"] is False
    assert manifest["eligible_for_merged_final_analysis"] is False
    assert manifest["preservation_only"] is True
    assert not copied_r2.stage_manifest_path().exists()
    with pytest.raises(FileExistsError, match="already exist"):
        f.finalize_stage_c_r2_incident(ROOT, copied_r2)


def test_incident_has_two_nonsemantic_failure_classifications(copied_r2: f.StageCDirectory) -> None:
    f.finalize_stage_c_r2_incident(ROOT, copied_r2)
    manifest = f._verify_stage_c_r2_incident_artifacts(ROOT, copied_r2)
    schema = manifest["incident_classes"]["provider_schema_incompatibility"]
    latency = manifest["incident_classes"]["provider_latency_timeout"]
    assert schema["terminal_rows"] == 19
    assert schema["outer_markdown_envelope_removed"] is True
    assert "not_semantic_quality" in schema["classification"]
    assert latency["terminal_rows"] == 20
    assert latency["final_error_type"] == "timeout"
    assert latency["allowed_attempts_exhausted"] is True
    assert latency["configured_timeout_seconds"] == 120.0


def test_preserved_incident_cannot_resume_ordinary_finalize_or_merge(copied_r2: f.StageCDirectory) -> None:
    f.finalize_stage_c_r2_incident(ROOT, copied_r2)
    with pytest.raises(f.FatalFormalRunError, match="cannot be resumed"):
        asyncio.run(f.run_stage_c_primary(ROOT, copied_r2))
    with pytest.raises(f.FatalFormalRunError, match="cannot be ordinary-finalized"):
        f.finalize_stage_c_run(ROOT, copied_r2)
    with pytest.raises(f.FatalFormalRunError, match="cannot be merged-finalized"):
        f.finalize_run(ROOT, copied_r2)


def test_incident_source_hash_mismatch_is_fatal_without_repair(copied_r2: f.StageCDirectory) -> None:
    with copied_r2.stage_path().open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(f.FatalFormalRunError, match="source mismatch"):
        f.finalize_stage_c_r2_incident(ROOT, copied_r2)
    assert not copied_r2.incident_manifest_path().exists()
    assert not copied_r2.incident_markdown_path().exists()
