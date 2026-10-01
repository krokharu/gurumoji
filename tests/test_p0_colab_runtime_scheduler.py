import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import add_p0_colab_runtime_scheduler as scheduler


def _metadata(bundle):
    return {
        "job_id": "p0-test-job",
        "generation": 1,
        "bundle_sha256": hashlib.sha256(bundle).hexdigest(),
        "bundle_size_bytes": len(bundle),
        "worker_source_file_hashes": {path: "b" * 64 for path in scheduler.PINNED_WORKER_PATHS},
        "drive_uploads": [{
            "id": "bundle-id",
            "name": "Gurumoji_P0_Colab_Roundtrip_Bundle.zip",
            "sha256": hashlib.sha256(bundle).hexdigest(),
            "size_bytes": len(bundle),
        }],
    }


def _write_inputs(root, metadata=None):
    notebook_path = root / "Gurumoji_P0_A100_Roundtrip.ipynb"
    metadata_path = root / "p0_metadata.json"
    bundle = b"synthetic P0 bundle"
    (root / "p0_colab_roundtrip_bundle.zip").write_bytes(bundle)
    notebook_path.write_text(json.dumps({"cells": [
        {"cell_type": "markdown", "metadata": {},
         "source": ["# Gurumoji P0 A100 transport smoke\n"]},
        {"cell_type": "code", "execution_count": None, "metadata": {},
         "outputs": [], "source": [
             'print("P0_RESULT_ZIP_BASE64=" + base64.b64encode(result_zip).decode("ascii"))\n'
         ]},
    ]}), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata or _metadata(bundle)), encoding="utf-8")
    return notebook_path, metadata_path


def test_monitor_checks_hourly_and_audits_drive_every_80_minutes_with_small_health_probe():
    source = scheduler.MONITOR_SOURCE

    assert "STATUS_INTERVAL_SECONDS = 60 * 60" in source
    assert "DRIVE_AUDIT_INTERVAL_SECONDS = 80 * 60" in source
    assert '"a100_health_probe_when_no_job_is_running"' in source
    assert '"pinned_qwen3_model_job_running"' in source
    assert "run_a100_health_probe" not in source
    assert "hourly_a100_health_probe" not in source
    assert "torch.ones((256, 256)" in source
    assert "existing_sha256 != digest" in source
    assert "persisted integrity pin" in source
    reuse_function = source[
        source.index("def drive_upload_or_reuse("):source.index("# The synthetic P0 result")
    ]
    assert reuse_function.count("return existing, existing_bytes") >= 2
    first_reuse_return = reuse_function.index("return existing, existing_bytes")
    assert reuse_function.index("existing_sha256 = hashlib.sha256(existing_bytes).hexdigest()") < first_reuse_return
    assert reuse_function.index("prior_result_pins[0].get(\"sha256\")") < first_reuse_return


def test_add_monitor_embeds_valid_resumable_monitor_and_updates_metadata(tmp_path):
    notebook_path, metadata_path = _write_inputs(tmp_path)

    result = scheduler.add_monitor(tmp_path, "folder-id")

    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    monitor_cells = [cell for cell in notebook["cells"] if cell.get("cell_type") == "code"
                     and scheduler.MONITOR_MARKER in "".join(cell.get("source", []))]
    assert len(monitor_cells) == 1
    monitor_source = "".join(monitor_cells[0]["source"])
    compile(monitor_source, "<generated-monitor>", "exec")
    assert "STATUS_INTERVAL_SECONDS = 60 * 60" in monitor_source
    assert "DRIVE_AUDIT_INTERVAL_SECONDS = 80 * 60" in monitor_source
    assert "run_a100_health_probe" not in monitor_source
    assert 'DRIVE_FOLDER_ID = "folder-id"' in monitor_source
    assert 'EXPECTED_JOB_ID = "p0-test-job"' in monitor_source
    assert "EXPECTED_GENERATION = 1" in monitor_source
    assert "@JOB_ID" not in monitor_source

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["runtime_schedule"]["status_check_minutes"] == 60
    assert metadata["runtime_schedule"]["drive_integrity_check_minutes"] == 80
    assert metadata["runtime_schedule"]["hourly_gpu_work_when_queue_empty"] == "256x256_fp16_a100_health_probe_when_assigned"
    assert result["hourly_gpu_work_when_queue_empty"] == "256x256_fp16_a100_health_probe_when_assigned"


def test_add_monitor_rejects_code_injection_shaped_ids_without_changing_notebook(tmp_path):
    bad_folder = tmp_path / "bad-folder"
    bad_folder.mkdir()
    notebook_path, _ = _write_inputs(bad_folder)
    original = notebook_path.read_bytes()
    try:
        scheduler.add_monitor(bad_folder, 'folder-id";raise RuntimeError("injected");#')
    except ValueError as exc:
        assert "folder ID" in str(exc)
    else:
        raise AssertionError("malformed folder ID was accepted")
    assert notebook_path.read_bytes() == original

    bad_job = tmp_path / "bad-job"
    bad_job.mkdir()
    metadata = _metadata(b"synthetic P0 bundle")
    metadata["job_id"] = 'p0-test";raise RuntimeError("injected");#'
    notebook_path, _ = _write_inputs(bad_job, metadata)
    original = notebook_path.read_bytes()
    try:
        scheduler.add_monitor(bad_job, "folder-id")
    except ValueError as exc:
        assert "job ID" in str(exc)
    else:
        raise AssertionError("malformed job ID was accepted")
    assert notebook_path.read_bytes() == original
