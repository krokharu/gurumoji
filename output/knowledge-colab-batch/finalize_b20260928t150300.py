from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BATCH_ID = "b20260928t150300"
ACCEPT = {
    f"{BATCH_ID}-02": (
        "The source supports a recursive, iterative process and movement among phases as interpretations change. "
        "Accepted as an unapproved candidate; broader methodology use still requires the expert-level evaluation gate."
    ),
    f"{BATCH_ID}-04": (
        "The source supports interpreted shared meaning and rejects code/data-item counts as the basis for theme salience. "
        "The exception field is retained as a misuse warning for later review. Accepted as an unapproved candidate."
    ),
    f"{BATCH_ID}-05": (
        "The source supports relating themes to the dataset and research question and giving them coherent, distinct contributions. "
        "Accepted as an unapproved candidate; reporting details remain available in the source excerpt for later evaluation."
    ),
}
HOLD = {
    f"{BATCH_ID}-01": (
        "Hold: the candidate misrenders author Byrne as ブライアン. The study details are supported, but attribution must be corrected before adoption."
    ),
    f"{BATCH_ID}-03": (
        "Hold: the candidate says 熟練度の向上, which overstates the source's point about growing familiarity with the data."
    ),
}


def write_json(path: Path, value: dict) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def claim_metadata(job: dict) -> tuple[dict, dict]:
    result_path = ROOT / job["result_path"]
    result_bytes = result_path.read_bytes()
    result_sha = digest(result_bytes)
    if result_sha != job["result_sha256"]:
        raise RuntimeError(f"result hash mismatch for {job['job_id']}")
    status_path = result_path.with_name(f"Gurumoji_Status_{job['job_id']}_g1.json")
    remote_status = json.loads(status_path.read_text(encoding="utf-8"))
    if remote_status.get("status") != "candidate_ready" or remote_status.get("result_sha256") != result_sha:
        raise RuntimeError(f"Colab status mismatch for {job['job_id']}")
    bundle_path = ROOT / job["bundle_path"]
    if digest(bundle_path.read_bytes()) != job["bundle_sha256"]:
        raise RuntimeError(f"bundle hash mismatch for {job['job_id']}")
    registry_path = bundle_path.with_name(job["local_registry_file_name"])
    if digest(registry_path.read_bytes()) != job["local_registry_sha256"]:
        raise RuntimeError(f"approved Source registry hash mismatch for {job['job_id']}")
    excerpt_path = ROOT / job["excerpt_path"]
    excerpt = json.loads(excerpt_path.read_text(encoding="utf-8"))
    if digest(excerpt["text"].encode("utf-8")) != job["excerpt_sha256"]:
        raise RuntimeError(f"excerpt hash mismatch for {job['job_id']}")
    source_path = ROOT / job["source_record_path"]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if source["sha256"] != job["source_sha256"]:
        raise RuntimeError(f"Source record hash mismatch for {job['job_id']}")
    anchor = next(item for item in source["anchors"] if item["anchor_id"] == job["anchor_id"])
    if anchor["extracted_text_sha256"] != job["excerpt_sha256"]:
        raise RuntimeError(f"Source anchor mismatch for {job['job_id']}")
    snapshot_path = ROOT / job["evidence_snapshot_path"]
    if digest(snapshot_path.read_bytes()) != job["evidence_snapshot_sha256"]:
        raise RuntimeError(f"evidence snapshot hash mismatch for {job['job_id']}")
    with zipfile.ZipFile(result_path) as archive:
        members = [name for name in archive.namelist()
                   if name.startswith("artifacts/claims/") and name.endswith(".json")]
        if len(members) != 1:
            raise RuntimeError(f"expected one Claim artifact for {job['job_id']}")
        claim = json.loads(archive.read(members[0]).decode("utf-8"))
    if claim["status"] != "candidate" or claim["expert_id"] != job["expert_id"]:
        raise RuntimeError(f"unexpected Claim status or expert for {job['job_id']}")
    if not any(item["source_id"] == job["source_id"] and item["anchor_id"] == job["anchor_id"]
               for item in claim["evidence"]):
        raise RuntimeError(f"Claim does not cite its assigned source anchor for {job['job_id']}")
    method = claim["provenance"]["method"]
    metrics = {
        "input_tokens": int(method.split("input_tokens=")[1].split(";")[0]),
        "output_tokens": int(method.split("output_tokens=")[1].split(";")[0]),
        "elapsed_seconds": float(method.split("elapsed_seconds=")[1].split(";")[0]),
    }
    return claim, {
        "colab_status": remote_status,
        "claim_id": claim["claim_id"],
        "generated_claim": claim["claim"],
        "generation_metrics": metrics,
    }


def main() -> None:
    manifest_path = HERE / f"{BATCH_ID}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(manifest["jobs"]) != 5:
        raise RuntimeError("unexpected final Job count")

    checked: dict[str, tuple[dict, dict]] = {}
    for job in manifest["jobs"]:
        if job.get("status") not in {"candidate_ready", "accepted_unapproved_candidate_commit", "hold_for_revision"}:
            raise RuntimeError(f"unexpected Job status: {job['job_id']} {job.get('status')}")
        checked[job["job_id"]] = claim_metadata(job)

    accepted_sources = []
    for job in manifest["jobs"]:
        job_id = job["job_id"]
        _, metadata = checked[job_id]
        job.update(metadata)
        job["gpu"] = job["colab_status"].get("gpu")
        if job_id in ACCEPT:
            if job.get("status") != "accepted_unapproved_candidate_commit":
                bundle_path = ROOT / job["bundle_path"]
                registry_path = bundle_path.with_name(job["local_registry_file_name"])
                command = [
                    sys.executable, str(ROOT / "scripts" / "accept_colab_claim_job.py"),
                    "--data-dir", str(HERE / "state"),
                    "--result-zip", str(ROOT / job["result_path"]),
                    "--approved-sources-json", str(registry_path),
                ]
                completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
                if completed.returncode:
                    raise RuntimeError(f"acceptance failed for {job_id}: {completed.stdout}\n{completed.stderr}")
                accepted = json.loads(completed.stdout)
                if accepted.get("status") != "accepted_unapproved_candidate_commit":
                    raise RuntimeError(f"unexpected acceptance response for {job_id}: {accepted}")
                job["commit_sha256"] = accepted["commit_sha256"]
                job["accepted_result_zip_sha256"] = accepted["result_zip_sha256"]
            job["status"] = "accepted_unapproved_candidate_commit"
            job["review"] = ACCEPT[job_id]
            accepted_sources.append(job_id)
        else:
            job["status"] = "hold_for_revision"
            job["review"] = HOLD[job_id]

    metrics = [metadata["generation_metrics"] for _, metadata in checked.values()]
    manifest["runtime_preflight"] = {
        "gpu": "NVIDIA A100-SXM4-80GB",
        "gpu_memory_bytes": 85094825984,
        "gpu_available": True,
        "cuda_version": "12.8",
        "transformers": "4.51.3",
        "tokenizers": "0.21.4",
        "huggingface_hub": "0.30.2",
        "autoawq": "0.2.9",
        "kernel_restarted_after_package_install": True,
        "versions_verified_after_restart": True,
    }
    manifest["session_creation_history"] = [{"attempt": 1, "status": "created_single_a100_high_ram_assignment"}]
    manifest["status"] = "completed_with_unapproved_candidates_and_holds"
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    manifest["inference_metrics"] = {
        "successful_candidate_outputs": len(metrics),
        "inference_attempts": len(metrics),
        "input_tokens_with_result_metadata": sum(item["input_tokens"] for item in metrics),
        "output_tokens_with_result_metadata": sum(item["output_tokens"] for item in metrics),
        "elapsed_seconds_with_result_metadata": round(sum(item["elapsed_seconds"] for item in metrics), 3),
        "excludes": "runtime setup, package installation, model loading, and file transfers",
    }
    manifest["resource_usage"] = {
        "compute_units_before": 82.75,
        "compute_units_after": 81.93,
        "compute_units_balance_delta": 0.82,
        "active_sessions_after_stop": 0,
        "session_stopped": True,
    }
    manifest["review_summary"] = {
        "accepted_unapproved_candidates": len(accepted_sources),
        "held_for_revision": len(HOLD),
        "packs_approved_or_published": 0,
        "note": "Three source-grounded Claims were committed as unapproved candidates; two candidates were held for factual or semantic correction.",
    }
    write_json(manifest_path, manifest)
    progress = {
        "batch_id": BATCH_ID,
        "updated_at": manifest["updated_at"],
        "total_jobs": len(manifest["jobs"]),
        "finished_jobs": len(manifest["jobs"]),
        "candidate_ready": len(accepted_sources),
        "failed": 0,
        "held_for_revision": len(HOLD),
        "inference_metrics": manifest["inference_metrics"],
        "resource_usage": manifest["resource_usage"],
        "jobs": [{key: job.get(key) for key in (
            "job_id", "expert_id", "source_id", "anchor_id", "status", "result_sha256",
            "commit_sha256", "claim_id", "generation_metrics", "review"
        )} for job in manifest["jobs"]],
    }
    write_json(HERE / f"{BATCH_ID}-progress.json", progress)
    print(json.dumps(progress, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
