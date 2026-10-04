from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t110000"
MANIFEST_PATH = HERE / f"{BATCH_ID}.json"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def generated_claim_metadata(job: dict) -> dict:
    result_path = HERE.parent.parent / job["result_path"]
    with zipfile.ZipFile(result_path) as archive:
        claims = [name for name in archive.namelist() if name.startswith("artifacts/claims/")]
        if len(claims) != 1:
            raise RuntimeError(f"expected one Claim in {result_path}")
        claim = json.loads(archive.read(claims[0]).decode("utf-8"))
    provenance = claim["provenance"]
    return {
        "claim_id": claim["claim_id"],
        "generation_metrics": {
            "input_tokens": int(provenance["method"].split("input_tokens=")[1].split(";")[0]),
            "output_tokens": int(provenance["method"].split("output_tokens=")[1].split(";")[0]),
            "elapsed_seconds": float(provenance["method"].split("elapsed_seconds=")[1].split(";")[0]),
        },
        "generated_claim": claim["claim"],
    }


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_id = {job["job_id"]: job for job in manifest["jobs"]}

    accepted = {
        f"{BATCH_ID}-01": "533663e8c194532ee44dacdd161feac4465c288d5fa2a329b0066c234a007edf",
        f"{BATCH_ID}-03": "5b7864050cf8b7aab6e0b4112b8ef8f6b55e592151f7533f5a826f0270bf633b",
    }
    for job_id, commit_sha in accepted.items():
        job = by_id[job_id]
        job.update({
            "status": "accepted_unapproved_candidate_commit",
            "commit_sha256": commit_sha,
            "review": "Evidence-matched candidate accepted into the local JobStore; not approved for release.",
            **generated_claim_metadata(job),
        })
    held = by_id[f"{BATCH_ID}-02"]
    held.update({
        "status": "hold_for_revision",
        "review": "Not imported: the generated Claim reverses the source's comparison direction (survey/feedback was incorrectly stated as more useful than long-form documents).",
        **generated_claim_metadata(held),
    })

    manifest.update({
        "status": "completed_with_held_candidate",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_preflight": {
            "gpu": "NVIDIA A100-SXM4-80GB",
            "gpu_available": True,
            "transformers": "4.51.3",
            "tokenizers": "0.21.4",
            "huggingface_hub": "0.30.2",
        },
        "resource_usage": {
            "compute_units_before": 88.41,
            "compute_units_after": 87.88,
            "compute_units_balance_delta": 0.53,
            "active_sessions_after_stop": 0,
            "session_stopped": True,
        },
        "review_summary": {
            "accepted_unapproved_candidates": 2,
            "held_for_revision": 1,
            "packs_approved_or_published": 0,
            "note": "Job 02 reversed the comparison direction; corrective Job 03 stated the inequality explicitly and matched the selected-section evidence.",
        },
    })
    write_json(MANIFEST_PATH, manifest)

    jobs = manifest["jobs"]
    progress = {
        "batch_id": BATCH_ID,
        "updated_at": manifest["updated_at"],
        "total_jobs": len(jobs),
        "finished_jobs": len(jobs),
        "candidate_ready": sum(job["status"] == "accepted_unapproved_candidate_commit" for job in jobs),
        "failed": sum(job["status"] == "failed" for job in jobs),
        "held_for_revision": sum(job["status"] == "hold_for_revision" for job in jobs),
        "jobs": [{key: job.get(key) for key in (
            "job_id", "expert_id", "source_id", "anchor_id", "status", "result_sha256",
            "commit_sha256", "error", "review", "generation_metrics"
        )} for job in jobs],
        "resource_usage": manifest["resource_usage"],
    }
    write_json(HERE / f"{BATCH_ID}-progress.json", progress)
    print(json.dumps(progress, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
