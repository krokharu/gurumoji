import json
from datetime import datetime, timezone
from pathlib import Path

here = Path(__file__).resolve().parent
manifest_path = here / "b20260928t103300.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
now = datetime.now(timezone.utc).isoformat()
job = manifest["jobs"][0]
job.update({
    "status": "accepted_unapproved_candidate_commit",
    "review_status": "imported_unapproved_candidate_commit",
    "review_note": "The Japanese Claim accurately paraphrases Section 2.2's proposed core functions (word/n-gram/POS/semantic-tag counts, KWIC with co-text, and word-distribution visualization) and retains that these are proposed/potential features, not confirmed implementation or evaluation.",
    "reviewed_at": now,
    "accepted_at": now,
    "commit_sha256": "3a477e60dc7e63a9d420e2f99bef1f342da777cb3a9c15fc5fa562e80cb6bdee",
    "colab_status": {
        "gpu": "NVIDIA A100-SXM4-80GB",
        "job_id": "b20260928t103300-01",
        "model_reference": "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8",
        "result_sha256": "631138a2f5fd067ab40668e56a857fd0b57e307017f043c114227cf26d97c83a",
        "result_size_bytes": 5931,
        "schema_version": 1,
        "status": "candidate_ready",
        "updated_at": "2026-09-28T10:39:13+00:00",
    },
})
manifest.update({
    "status": "reviewed_imported_unapproved",
    "runtime_preflight": {
        "gpu": "NVIDIA A100-SXM4-80GB",
        "gpu_available": True,
        "transformers": "4.51.3",
        "tokenizers": "0.21.4",
        "huggingface_hub": "0.30.2",
        "verified_modules_and_distributions": True,
    },
    "inference_metrics": {
        "elapsed_seconds": 24.079,
        "input_tokens": 869,
        "output_tokens": 119,
        "excludes": "runtime setup, package installation, and file transfers",
    },
    "colab_resource_usage": {
        "active_sessions_after_stop": 0,
        "compute_units_before": 88.70,
        "compute_units_after": 88.41,
        "estimated_batch_delta": 0.29,
        "session_stopped": True,
        "usage_rate_after_per_hour": 0.0,
    },
    "source_acquisition": {
        "source_url": "https://cronfa.swan.ac.uk/Record/cronfa70086/Download/70086__34939__f82a24c8c3ea49aaad5c813e2a7643c7.pdf",
        "retrieval": "The repository's public Version-of-Record PDF text was inspected through browser retrieval. Direct local downloads from Cardiff ORCA and Swansea Cronfa returned 403.",
        "hash_scope": "source_sha256 identifies a selected-section evidence-text snapshot derived from browser-rendered PDF text, not the original PDF bytes.",
    },
    "updated_at": now,
})
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
job_summary = {key: job.get(key) for key in ("job_id", "expert_id", "source_id", "anchor_id", "status", "result_sha256", "error")}
progress = {
    "batch_id": manifest["batch_id"],
    "updated_at": now,
    "total_jobs": len(manifest["jobs"]),
    "finished_jobs": len(manifest["jobs"]),
    "candidate_ready": 1,
    "failed": 0,
    "jobs": [job_summary],
}
(here / "b20260928t103300-progress.json").write_text(
    json.dumps(progress, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({"batch_id": manifest["batch_id"], "status": manifest["status"], "updated_at": now}, ensure_ascii=False))
