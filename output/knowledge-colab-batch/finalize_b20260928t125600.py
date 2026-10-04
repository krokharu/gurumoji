from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BATCH_ID = "b20260928t125600"
COMMITS = {
    f"{BATCH_ID}-01": "b1ef9d2746ce557a4650ce93ea8d593651f43d85f02eaeaa3749acf87749bb36",
    f"{BATCH_ID}-02": "3c8f81961feca6d4b1338d1be636162565c05ec2b8b06ef7dee501a34a010957",
}
REVIEWS = {
    f"{BATCH_ID}-01": (
        "Checked against the MDPI publisher article, Methods §2.5, pp. 14–15: it distinguishes the "
        "general four-step SCAT coding description from the six-step workflow used in this study. "
        "Step 3 assigns other terms to summarize each data group. This is limited to the study's "
        "reported implementation and does not replace the general SCAT definition. Accepted as an "
        "unapproved candidate; it supersedes the held draft in b20260928t124700-01."
    ),
    f"{BATCH_ID}-02": (
        "Checked against the MDPI publisher article, Methods §2.5, p. 15: the authors report that "
        "the analysis in their study was supervised by a researcher well-versed in SCAT. The wording "
        "is scoped to this single study. Accepted as an unapproved candidate; it supersedes the held "
        "draft in b20260928t124700-02."
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
    manifest_path = HERE / f"{BATCH_ID}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(manifest["jobs"]) != 2:
        raise RuntimeError("unexpected Job count")
    manifest["runtime_preflight"] = {
        "gpu": "NVIDIA A100-SXM4-40GB",
        "gpu_available": True,
        "transformers": "4.51.3",
        "tokenizers": "0.21.4",
        "huggingface_hub": "0.30.2",
    }
    supersedes = {
        f"{BATCH_ID}-01": "b20260928t124700-01",
        f"{BATCH_ID}-02": "b20260928t124700-02",
    }
    for job in manifest["jobs"]:
        result_path = HERE / "jobs" / job["job_id"] / f"Gurumoji_Result_{job['job_id']}_g1.zip"
        status_path = result_path.with_name(f"Gurumoji_Status_{job['job_id']}_g1.json")
        remote_status = json.loads(status_path.read_text(encoding="utf-8"))
        job["result_path"] = result_path.relative_to(ROOT).as_posix()
        job["result_sha256"] = remote_status["result_sha256"]
        job.update({
            "status": "accepted_unapproved_candidate_commit",
            "commit_sha256": COMMITS[job["job_id"]],
            "review": REVIEWS[job["job_id"]],
            "supersedes_job_id": supersedes[job["job_id"]],
            **claim_metadata(job),
        })
        job["gpu"] = "NVIDIA A100-SXM4-40GB"
    manifest["session_creation_history"] = [
        {
            "status": "service_unavailable_no_assignment",
            "detail": "The first two create requests returned Service Unavailable. After each, sessions/status/log showed no assignment or execution; no duplicate was present.",
        },
        {
            "status": "created_on_third_request",
            "detail": "A third request using the same session name created exactly one A100 Standard assignment. Both Jobs then completed sequentially.",
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
            "excludes": "runtime setup, package installation, model loading, and file transfers",
        },
        "resource_usage": {
            "compute_units_before": 85.49,
            "compute_units_after": 85.07,
            "compute_units_balance_delta": 0.42,
            "active_sessions_after_stop": 0,
            "session_stopped": True,
        },
        "review_summary": {
            "accepted_unapproved_candidates": 2,
            "held_for_revision": 0,
            "packs_approved_or_published": 0,
            "note": "Both revised claims correct the initial drafts' terminology or scope and are grounded in distinct passages of the same approved article.",
        },
    })
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
            "commit_sha256", "claim_id", "generation_metrics", "supersedes_job_id", "review"
        )} for job in manifest["jobs"]],
    }
    write_json(HERE / f"{BATCH_ID}-progress.json", progress)
    print(json.dumps(progress, ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
