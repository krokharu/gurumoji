from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BATCH_ID = "b20260928t124700"
REVIEWS = {
    f"{BATCH_ID}-01": (
        "Held for revision: the candidate translates the study's step of rewording each data group as "
        "reconstruction, which can change the method described in the source."
    ),
    f"{BATCH_ID}-02": (
        "Held for revision: the wording can be read as covering multiple Shimizu studies, while the cited "
        "supervision statement describes one study. The claim needs to name that single study explicitly."
    ),
}


def main() -> None:
    path = HERE / f"{BATCH_ID}.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if len(manifest["jobs"]) != 2:
        raise RuntimeError("unexpected Job count")
    metrics = []
    for job in manifest["jobs"]:
        result_path = ROOT / "output" / "knowledge-colab-batch" / "jobs" / job["job_id"] / f"Gurumoji_Result_{job['job_id']}_g1.zip"
        actual_sha = hashlib.sha256(result_path.read_bytes()).hexdigest()
        status_path = result_path.with_name(f"Gurumoji_Status_{job['job_id']}_g1.json")
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("status") != "candidate_ready" or status.get("result_sha256") != actual_sha:
            raise RuntimeError(f"Status/result mismatch for {job['job_id']}")
        with zipfile.ZipFile(result_path) as archive:
            claims = [name for name in archive.namelist() if name.startswith("artifacts/claims/") and name.endswith(".json")]
            if len(claims) != 1:
                raise RuntimeError(f"expected one Claim for {job['job_id']}")
            claim = json.loads(archive.read(claims[0]).decode("utf-8"))
        method = claim["provenance"]["method"]
        item_metrics = {
            "input_tokens": int(method.split("input_tokens=")[1].split(";")[0]),
            "output_tokens": int(method.split("output_tokens=")[1].split(";")[0]),
            "elapsed_seconds": float(method.split("elapsed_seconds=")[1].split(";")[0]),
        }
        metrics.append(item_metrics)
        job.update({
            "result_path": result_path.relative_to(ROOT).as_posix(),
            "result_sha256": actual_sha,
            "colab_status": status,
            "generated_claim": claim["claim"],
            "claim_id": claim["claim_id"],
            "generation_metrics": item_metrics,
            "review": REVIEWS[job["job_id"]],
            "status": "hold_for_revision",
            "gpu": status["gpu"],
        })
    manifest.update({
        "status": "completed_with_holds",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_preflight": {
            "gpu": "NVIDIA A100-SXM4-40GB",
            "gpu_available": True,
            "transformers": "4.51.3",
            "tokenizers": "0.21.4",
            "huggingface_hub": "0.30.2",
        },
        "inference_metrics": {
            "input_tokens": sum(m["input_tokens"] for m in metrics),
            "output_tokens": sum(m["output_tokens"] for m in metrics),
            "elapsed_seconds": round(sum(m["elapsed_seconds"] for m in metrics), 3),
            "excludes": "runtime setup, package installation, and file transfers",
        },
        "resource_usage": {
            "compute_units_before": 85.77,
            "compute_units_after": 85.49,
            "compute_units_balance_delta": 0.28,
            "active_sessions_after_stop": 0,
            "session_stopped": True,
        },
        "review_summary": {
            "accepted_unapproved_candidates": 0,
            "held_for_revision": 2,
            "packs_approved_or_published": 0,
            "note": "Both initial drafts were withheld because their wording needs tighter methodological terminology or scope.",
        },
    })
    path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    progress = {
        "batch_id": BATCH_ID,
        "updated_at": manifest["updated_at"],
        "total_jobs": 2,
        "finished_jobs": 2,
        "candidate_ready": 0,
        "failed": 0,
        "held_for_revision": 2,
        "inference_metrics": manifest["inference_metrics"],
        "resource_usage": manifest["resource_usage"],
        "jobs": [{key: job.get(key) for key in (
            "job_id", "expert_id", "anchor_id", "status", "result_sha256", "claim_id",
            "generation_metrics", "review"
        )} for job in manifest["jobs"]],
    }
    (HERE / f"{BATCH_ID}-progress.json").write_text(
        json.dumps(progress, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(progress, ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
