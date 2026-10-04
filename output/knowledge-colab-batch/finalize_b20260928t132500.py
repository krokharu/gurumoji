from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BATCH_ID = "b20260928t132500"
COMMITS = {
    f"{BATCH_ID}-03": "b704029d9d69a6cd5fcf6206e9521cebb5e64c45b8f566bd52dcd1decae346a8",
    f"{BATCH_ID}-04": "98522e6519704f43b801a10f828f623078fb6bc21a5d3ad61338c728fe1c25f8",
    f"{BATCH_ID}-07": "fb9f88e8878eecfe59042eb58497bef3620924f5cfd6d4c9ca028a402333e306",
}
REVIEWS = {
    f"{BATCH_ID}-03": (
        "Checked against the SciPy v1.18.0 official pearsonr API reference, method parameter (lines 61-64): "
        "PermutationMethod and MonteCarloMethod select the corresponding resampling family for p-value calculation. "
        "This is an API capability statement; it does not establish independence, exchangeability, or suitability "
        "for a particular utterance-level design. Accepted as an unapproved candidate."
    ),
    f"{BATCH_ID}-04": (
        "Checked against the SciPy v1.18.0 official pearsonr API reference, confidence_interval description (lines 89-93): "
        "the default interval uses Fisher transformation and limits may be NaN when a resample is degenerate, a behavior "
        "the manual describes as typical for very small samples. The claim preserves the source's approximate scope and "
        "does not turn it into a minimum-n rule. Accepted as an unapproved candidate."
    ),
    f"{BATCH_ID}-07": (
        "Checked against the SciPy v1.18.0 official pearsonr API reference, confidence_interval description (line 92): "
        "the exact result method is confidence_interval, and supplying BootstrapMethod delegates calculation to "
        "scipy.stats.bootstrap with the provided configuration. Accepted as an unapproved candidate."
    ),
}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def claim_metadata(job: dict) -> dict:
    root_path = ROOT / job["result_path"]
    result_bytes = root_path.read_bytes()
    result_sha = hashlib.sha256(result_bytes).hexdigest()
    if result_sha != job["result_sha256"]:
        raise RuntimeError(f"result hash mismatch for {job['job_id']}")
    status_path = root_path.with_name(f"Gurumoji_Status_{job['job_id']}_g1.json")
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
    with zipfile.ZipFile(root_path) as archive:
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
    if len(manifest["jobs"]) != 7:
        raise RuntimeError("unexpected final Job count")
    for job in manifest["jobs"]:
        if job["job_id"] not in COMMITS:
            if job.get("status") != "hold_for_revision":
                raise RuntimeError(f"unexpected non-accepted job status: {job['job_id']} {job.get('status')}")
            continue
        if job.get("status") not in {"candidate_ready", "hold_for_revision"}:
            raise RuntimeError(f"accepted Job has an unexpected prior status: {job['job_id']} {job.get('status')}")
        if job.get("status") == "hold_for_revision":
            job["review_history"] = [{
                "status": "held_for_revision_before_narrower_review",
                "review": job.get("review", ""),
            }]
        job.update({
            "status": "accepted_unapproved_candidate_commit",
            "commit_sha256": COMMITS[job["job_id"]],
            "review": REVIEWS[job["job_id"]],
            **claim_metadata(job),
        })
        job["gpu"] = "NVIDIA A100-SXM4-40GB"

    manifest["runtime_preflight"] = {
        "gpu": "NVIDIA A100-SXM4-40GB",
        "gpu_available": True,
        "transformers": "4.51.3",
        "tokenizers": "0.21.4",
        "huggingface_hub": "0.30.2",
        "kernel_restarted_after_package_install": True,
        "versions_verified_after_restart": True,
    }
    # Metrics for all candidate outputs (accepted or held) are read from the downloaded Claim artifacts.
    all_result_metrics = []
    for job in manifest["jobs"]:
        if job.get("result_path"):
            result_path = ROOT / job["result_path"]
            with zipfile.ZipFile(result_path) as archive:
                member = next(name for name in archive.namelist()
                              if name.startswith("artifacts/claims/") and name.endswith(".json"))
                claim = json.loads(archive.read(member).decode("utf-8"))
            method = claim["provenance"]["method"]
            all_result_metrics.append({
                "input_tokens": int(method.split("input_tokens=")[1].split(";")[0]),
                "output_tokens": int(method.split("output_tokens=")[1].split(";")[0]),
                "elapsed_seconds": float(method.split("elapsed_seconds=")[1].split(";")[0]),
            })
    manifest["session_creation_history"] = [{
        "status": "created_single_a100_standard_assignment",
        "detail": "One colab new request created the named A100-SXM4-40GB Standard session. The client waited for readiness; server status confirmed exactly one assignment, and the session was stopped after all jobs.",
    }]
    manifest["status"] = "completed_unapproved_candidates"
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    manifest["inference_metrics"] = {
        "successful_candidate_outputs": len(all_result_metrics),
        "inference_attempts": 7,
        "input_tokens_with_result_metadata": sum(item["input_tokens"] for item in all_result_metrics),
        "output_tokens_with_result_metadata": sum(item["output_tokens"] for item in all_result_metrics),
        "elapsed_seconds_with_result_metadata": round(sum(item["elapsed_seconds"] for item in all_result_metrics), 3),
        "excludes": (
            "the first output rejected by the 48-character source-fragment guard (no successful Claim artifact or usage metadata), "
            "runtime setup, package installation, model loading, and file transfers"
        ),
    }
    manifest["resource_usage"] = {
        "compute_units_before": 85.07,
        "compute_units_after": 83.31,
        "compute_units_balance_delta": 1.76,
        "active_sessions_after_stop": 0,
        "session_stopped": True,
    }
    manifest["review_summary"] = {
        "accepted_unapproved_candidates": 3,
        "held_for_revision": 4,
        "packs_approved_or_published": 0,
        "note": (
            "Three claims were accepted after checking API scope and exact method behavior. Four drafts were held: "
            "one source-fragment guard rejection, one editorial instruction in an exception field, and two "
            "technically imprecise drafts corrected by later jobs."
        ),
    }
    write_json(manifest_path, manifest)
    progress = {
        "batch_id": BATCH_ID,
        "updated_at": manifest["updated_at"],
        "total_jobs": len(manifest["jobs"]),
        "finished_jobs": len(manifest["jobs"]),
        "candidate_ready": 3,
        "failed": 0,
        "held_for_revision": 4,
        "inference_metrics": manifest["inference_metrics"],
        "resource_usage": manifest["resource_usage"],
        "jobs": [{key: job.get(key) for key in (
            "job_id", "expert_id", "source_id", "anchor_id", "status", "result_sha256",
            "commit_sha256", "claim_id", "generation_metrics", "supersedes_job_id", "review"
        )} for job in manifest["jobs"]],
    }
    write_json(HERE / f"{BATCH_ID}-progress.json", progress)
    print(json.dumps(progress, ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
