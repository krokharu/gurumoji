from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t112200"
MANIFEST_PATH = HERE / f"{BATCH_ID}.json"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def generated_claim_metadata(job: dict) -> dict:
    result_path = HERE.parent.parent / job["result_path"]
    with zipfile.ZipFile(result_path) as archive:
        claim_members = [name for name in archive.namelist() if name.startswith("artifacts/claims/")]
        if len(claim_members) != 1:
            raise RuntimeError(f"expected exactly one Claim in {result_path}")
        claim = json.loads(archive.read(claim_members[0]).decode("utf-8"))
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
    if len(manifest["jobs"]) != 2:
        raise RuntimeError("unexpected Job count")
    commit_sha = {
        f"{BATCH_ID}-01": "f6e966d7d971179a9c02d6c91b5c5a1f0c7a465fc5c377b82046dba4583d0550",
        f"{BATCH_ID}-02": "8d9970f0dd06e8d8cbcacc905f79a5402f2ebbd8b6c0c08dd8a269473a8c44a6",
    }
    for job in manifest["jobs"]:
        job.update({
            "status": "accepted_unapproved_candidate_commit",
            "commit_sha256": commit_sha[job["job_id"]],
            "review": "Numerator, denominator, sample scope, and evidence anchor checked against publisher full text; accepted as an unapproved candidate.",
            **generated_claim_metadata(job),
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
            "compute_units_before": 87.88,
            "compute_units_after": 87.55,
            "compute_units_balance_delta": 0.33,
            "active_sessions_after_stop": 0,
            "session_stopped": True,
        },
        "review_summary": {
            "accepted_unapproved_candidates": 2,
            "held_for_revision": 0,
            "packs_approved_or_published": 0,
            "note": "The 30.1% floor-transfer statistic and 95.3% nonsilent-speech statistic retain their distinct denominators.",
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
