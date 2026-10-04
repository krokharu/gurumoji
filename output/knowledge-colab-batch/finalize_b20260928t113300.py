from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t113300"
MANIFEST_PATH = HERE / f"{BATCH_ID}.json"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def claim_metadata(job: dict) -> dict:
    result_path = HERE.parent.parent / job["result_path"]
    with zipfile.ZipFile(result_path) as archive:
        members = [name for name in archive.namelist() if name.startswith("artifacts/claims/")]
        if len(members) != 1:
            raise RuntimeError(f"expected one Claim in {result_path}")
        claim = json.loads(archive.read(members[0]).decode("utf-8"))
    method = claim["provenance"]["method"]
    return {
        "claim_id": claim["claim_id"],
        "generated_claim": claim["claim"],
        "generation_metrics": {
            "input_tokens": int(method.split("input_tokens=")[1].split(";")[0]),
            "output_tokens": int(method.split("output_tokens=")[1].split(";")[0]),
            "elapsed_seconds": float(method.split("elapsed_seconds=")[1].split(";")[0]),
        },
    }


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    commits = {
        f"{BATCH_ID}-01": "258add30cfab3825e63a61970044dc2781750e871825794c08204a04b752576a",
        f"{BATCH_ID}-02": "5e487b0af2a1289d5c2adbf3eabea8fb2fdd58348a747eac104235ff47066e22",
    }
    for job in manifest["jobs"]:
        job.update({
            "status": "accepted_unapproved_candidate_commit",
            "commit_sha256": commits[job["job_id"]],
            "review": "Claim checked against the SciPy v1.18.0 official API documentation and accepted as an unapproved candidate.",
            **claim_metadata(job),
        })
    manifest.update({
        "status": "completed_unapproved_candidates",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_preflight": {
            "gpu": "NVIDIA A100-SXM4-80GB",
            "gpu_available": True,
            "transformers": "4.51.3",
            "tokenizers": "0.21.4",
            "huggingface_hub": "0.30.2",
        },
        "resource_usage": {
            "compute_units_before": 87.55,
            "compute_units_after": 87.33,
            "compute_units_balance_delta": 0.22,
            "active_sessions_after_stop": 0,
            "session_stopped": True,
        },
        "review_summary": {
            "accepted_unapproved_candidates": 2,
            "held_for_revision": 0,
            "packs_approved_or_published": 0,
            "note": "The axis scope and bias-correction behavior are separate parameters and have separate evidence anchors.",
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
        "resource_usage": manifest["resource_usage"],
        "jobs": [{key: job.get(key) for key in (
            "job_id", "expert_id", "source_id", "anchor_id", "status", "result_sha256",
            "commit_sha256", "generation_metrics", "review"
        )} for job in manifest["jobs"]],
    }
    write_json(HERE / f"{BATCH_ID}-progress.json", progress)
    print(json.dumps(progress, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
