from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BATCH_ID = "b20260928t120000"
MANIFEST_PATH = HERE / f"{BATCH_ID}.json"
COMMITS = {
    f"{BATCH_ID}-01": "2f4ffc9bf6b4c61945c2cebd317e83c22404f2ce2e693aeae9098b056aba1079",
    f"{BATCH_ID}-02": "7bd05f3dbcf6850052011af4abf8a612984957f9041937efb3842bbede309bc9",
}
REVIEWS = {
    f"{BATCH_ID}-01": (
        "Checked against the Frontiers publisher article, page 2, lines 251–252: the listed corpus "
        "differences and their effect on generalization are supported. This extends the existing "
        "single-corpus/single-language observation with a distinct cross-corpus challenge. "
        "Accepted as an unapproved candidate."
    ),
    f"{BATCH_ID}-02": (
        "Checked against the Frontiers publisher article, page 2, line 252: the review identifies an "
        "emotion classifier and domain-invariant feature extraction as two crucial steps in a basic "
        "cross-corpus SER system. The claim retains the basic-system scope. Accepted as an unapproved candidate."
    ),
}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def claim_metadata(job: dict) -> dict:
    result_path = ROOT / job["result_path"]
    raw = result_path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != job["result_sha256"]:
        raise RuntimeError(f"result SHA-256 mismatch for {job['job_id']}")
    status_path = result_path.with_name(f"Gurumoji_Status_{job['job_id']}_g1.json")
    remote_status = json.loads(status_path.read_text(encoding="utf-8"))
    if remote_status.get("status") != "candidate_ready" or remote_status.get("result_sha256") != actual_sha:
        raise RuntimeError(f"remote status mismatch for {job['job_id']}")
    with zipfile.ZipFile(result_path) as archive:
        members = [name for name in archive.namelist() if name.startswith("artifacts/claims/") and name.endswith(".json")]
        if len(members) != 1:
            raise RuntimeError(f"expected one Claim in {result_path}")
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
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if len(manifest["jobs"]) != 2:
        raise RuntimeError("unexpected Job count")
    manifest["runtime_preflight"] = {
        "gpu": "NVIDIA A100-SXM4-40GB",
        "gpu_available": True,
        "transformers": "4.51.3",
        "tokenizers": "0.21.4",
        "huggingface_hub": "0.30.2",
    }
    for job in manifest["jobs"]:
        result_path = HERE / "jobs" / job["job_id"] / f"Gurumoji_Result_{job['job_id']}_g1.zip"
        status_path = result_path.with_name(f"Gurumoji_Status_{job['job_id']}_g1.json")
        remote_status = json.loads(status_path.read_text(encoding="utf-8"))
        job["result_path"] = result_path.relative_to(ROOT).as_posix()
        job["result_sha256"] = remote_status["result_sha256"]
        job["colab_status"] = remote_status
        job.update({
            "status": "accepted_unapproved_candidate_commit",
            "commit_sha256": COMMITS[job["job_id"]],
            "review": REVIEWS[job["job_id"]],
            **claim_metadata(job),
        })
        job["gpu"] = "NVIDIA A100-SXM4-40GB"
    manifest["jobs"][1]["attempt_history"] = [
        {
            "status": "bundle_upload_stalled",
            "detail": "The CLI logged the second Job ZIP upload but did not return within several minutes; the Colab session remained IDLE and showed no Job 02 output. The local batch driver was stopped before any second inference began.",
        },
        {
            "status": "connection_lost_before_inference",
            "detail": "A direct execution attempt returned RuntimeError: Connection was lost; remote status remained IDLE and no Job 02 status or result existed.",
        },
        {
            "status": "recovered_and_candidate_ready",
            "detail": "Restarted the kernel, reran GPU and dependency preflight, then executed the already-uploaded Job 02 once. The returned result hash matched the downloaded result and status files.",
        },
    ]
    metrics = [job["generation_metrics"] for job in manifest["jobs"]]
    manifest.update({
        "status": "completed_unapproved_candidates",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "inference_metrics": {
            "input_tokens": sum(item["input_tokens"] for item in metrics),
            "output_tokens": sum(item["output_tokens"] for item in metrics),
            "elapsed_seconds": round(sum(item["elapsed_seconds"] for item in metrics), 3),
            "excludes": "runtime setup, package installation, and file transfers",
        },
        "resource_usage": {
            "compute_units_before": 87.33,
            "compute_units_after": 86.28,
            "compute_units_balance_delta": 1.05,
            "active_sessions_after_stop": 0,
            "session_stopped": True,
        },
        "review_summary": {
            "accepted_unapproved_candidates": 2,
            "held_for_revision": 0,
            "packs_approved_or_published": 0,
            "note": "Both claims add distinct cross-corpus knowledge. The first separates corpus-mismatch factors from the existing single-corpus evaluation observation; the second records the two components of a basic cross-corpus system.",
        },
    })
    write_json(MANIFEST_PATH, manifest)
    progress = {
        "batch_id": BATCH_ID,
        "updated_at": manifest["updated_at"],
        "total_jobs": len(manifest["jobs"]),
        "finished_jobs": len(manifest["jobs"]),
        "candidate_ready": len(manifest["jobs"]),
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
