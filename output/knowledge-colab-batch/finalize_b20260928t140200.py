from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BATCH_ID = "b20260928t140200"
COMMITS = {
    f"{BATCH_ID}-01": "de08b63b6dd338d4bc0a850f572e44315d65402f4abdd800a77cf581b232f957",
    f"{BATCH_ID}-02": "89159aa2aa11960902bf64c53760fd29173e653dc8a99dfc293a7487ba83b012",
}
REVIEWS = {
    f"{BATCH_ID}-01": (
        "Checked against the SciPy v1.18.0 official f_oneway API reference, equal_var parameter: "
        "True is the default standard one-way ANOVA with equal population variances; False selects Welch's ANOVA. "
        "The Claim states only API behavior, not that Gurumoji currently implements Welch ANOVA. "
        "Accepted as an unapproved candidate."
    ),
    f"{BATCH_ID}-02": (
        "Checked against the SciPy v1.18.0 official f_oneway API reference, nan_policy parameter: "
        "propagate, omit, and raise are supported, with propagate as the default. "
        "The Claim states API behavior; Gurumoji filters non-finite values before its current call. "
        "Accepted as an unapproved candidate."
    ),
}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def claim_metadata(job: dict) -> dict:
    result_path = ROOT / job["result_path"]
    result_bytes = result_path.read_bytes()
    result_sha = hashlib.sha256(result_bytes).hexdigest()
    if result_sha != job["result_sha256"]:
        raise RuntimeError(f"result hash mismatch for {job['job_id']}")
    status_path = result_path.with_name(f"Gurumoji_Status_{job['job_id']}_g1.json")
    remote_status = json.loads(status_path.read_text(encoding="utf-8"))
    if remote_status.get("status") != "candidate_ready" or remote_status.get("result_sha256") != result_sha:
        raise RuntimeError(f"Colab status mismatch for {job['job_id']}")
    bundle_path = ROOT / job["bundle_path"]
    if hashlib.sha256(bundle_path.read_bytes()).hexdigest() != job["bundle_sha256"]:
        raise RuntimeError(f"bundle hash mismatch for {job['job_id']}")
    excerpt_path = ROOT / job["excerpt_path"]
    excerpt = json.loads(excerpt_path.read_text(encoding="utf-8"))
    if hashlib.sha256(excerpt["text"].encode("utf-8")).hexdigest() != job["excerpt_sha256"]:
        raise RuntimeError(f"excerpt hash mismatch for {job['job_id']}")
    source_path = ROOT / job["source_record_path"]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if source["sha256"] != job["source_sha256"]:
        raise RuntimeError(f"Source record hash mismatch for {job['job_id']}")
    snapshot_path = ROOT / job["evidence_snapshot_path"]
    if hashlib.sha256(snapshot_path.read_bytes()).hexdigest() != job["evidence_snapshot_sha256"]:
        raise RuntimeError(f"evidence snapshot hash mismatch for {job['job_id']}")
    with zipfile.ZipFile(result_path) as archive:
        members = [name for name in archive.namelist()
                   if name.startswith("artifacts/claims/") and name.endswith(".json")]
        if len(members) != 1:
            raise RuntimeError(f"expected one Claim artifact for {job['job_id']}")
        claim = json.loads(archive.read(members[0]).decode("utf-8"))
    method = claim["provenance"]["method"]
    metrics = {
        "input_tokens": int(method.split("input_tokens=")[1].split(";")[0]),
        "output_tokens": int(method.split("output_tokens=")[1].split(";")[0]),
        "elapsed_seconds": float(method.split("elapsed_seconds=")[1].split(";")[0]),
    }
    return {
        "colab_status": remote_status,
        "claim_id": claim["claim_id"],
        "generated_claim": claim["claim"],
        "generation_metrics": metrics,
    }


def main() -> None:
    manifest_path = HERE / f"{BATCH_ID}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(manifest["jobs"]) != 2:
        raise RuntimeError("unexpected final Job count")
    for job in manifest["jobs"]:
        if job["job_id"] not in COMMITS or job.get("status") != "candidate_ready":
            raise RuntimeError(f"unexpected Job status: {job['job_id']} {job.get('status')}")
        job.update({
            "status": "accepted_unapproved_candidate_commit",
            "commit_sha256": COMMITS[job["job_id"]],
            "review": REVIEWS[job["job_id"]],
            **claim_metadata(job),
        })
        job["gpu"] = "NVIDIA A100-SXM4-40GB"

    metrics = [job["generation_metrics"] for job in manifest["jobs"]]
    manifest["runtime_preflight"] = {
        "gpu": "NVIDIA A100-SXM4-40GB",
        "gpu_available": True,
        "transformers": "4.51.3",
        "tokenizers": "0.21.4",
        "huggingface_hub": "0.30.2",
        "kernel_restarted_after_package_install": True,
        "versions_verified_after_restart": True,
    }
    manifest["session_creation_history"] = [
        {"attempt": 1, "status": "service_unavailable", "server_assignments_after_check": 0},
        {"attempt": 2, "status": "service_unavailable", "server_assignments_after_check": 0},
        {"attempt": 3, "status": "created_single_a100_standard_assignment"},
    ]
    manifest["status"] = "completed_unapproved_candidates"
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    manifest["inference_metrics"] = {
        "successful_candidate_outputs": len(metrics),
        "inference_attempts": 2,
        "input_tokens_with_result_metadata": sum(item["input_tokens"] for item in metrics),
        "output_tokens_with_result_metadata": sum(item["output_tokens"] for item in metrics),
        "elapsed_seconds_with_result_metadata": round(sum(item["elapsed_seconds"] for item in metrics), 3),
        "excludes": "runtime setup, package installation, model loading, and file transfers",
    }
    manifest["resource_usage"] = {
        "compute_units_before": 83.31,
        "compute_units_after": 83.13,
        "compute_units_balance_delta": 0.18,
        "active_sessions_after_stop": 0,
        "session_stopped": True,
    }
    manifest["review_summary"] = {
        "accepted_unapproved_candidates": 2,
        "held_for_revision": 0,
        "packs_approved_or_published": 0,
        "note": "Both Claims were checked against the SciPy v1.18.0 API page and accepted as unapproved candidates.",
    }
    write_json(manifest_path, manifest)
    progress = {
        "batch_id": BATCH_ID,
        "updated_at": manifest["updated_at"],
        "total_jobs": 2,
        "finished_jobs": 2,
        "candidate_ready": 2,
        "failed": 0,
        "held_for_revision": 0,
        "inference_metrics": manifest["inference_metrics"],
        "resource_usage": manifest["resource_usage"],
        "jobs": [{key: job.get(key) for key in (
            "job_id", "expert_id", "source_id", "anchor_id", "status", "result_sha256",
            "commit_sha256", "claim_id", "generation_metrics", "review"
        )} for job in manifest["jobs"]],
    }
    write_json(HERE / f"{BATCH_ID}-progress.json", progress)
    print(json.dumps(progress, ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
