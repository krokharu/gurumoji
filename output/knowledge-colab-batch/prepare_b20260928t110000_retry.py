from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t110000"
JOB_ID = f"{BATCH_ID}-03"
ANCHOR_ID = "freetxt-summariser-comparison-direction-section-4"
SOURCE_PATH = HERE / "inputs" / BATCH_ID / "jobs" / f"{BATCH_ID}-02" / "source.json"
SNAPSHOT_PATH = HERE / "sources-20260928" / f"{BATCH_ID}-LIT-knight-2024-freetxt-sections-3-2-3-4-4-evidence.txt"
MANIFEST_PATH = HERE / f"{BATCH_ID}.json"
SESSION = "gurumoji-a100-deepknowledge-20260928-110000"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if len(manifest["jobs"]) != 2 or any(job["job_id"] == JOB_ID for job in manifest["jobs"]):
        raise RuntimeError("unexpected batch state")

    first, reversed_candidate = manifest["jobs"]
    if first.get("status") != "candidate_ready":
        raise RuntimeError("first candidate is not in the expected state")
    first.update({
        "status": "accepted_unapproved_candidate_commit",
        "commit_sha256": "533663e8c194532ee44dacdd161feac4465c288d5fa2a329b0066c234a007edf",
        "review": "Evidence-matched candidate accepted into local JobStore; not approved for release.",
    })
    reversed_candidate.update({
        "status": "hold_for_revision",
        "review": "Not imported: generated Claim reverses the comparison direction in the source excerpt.",
    })

    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    excerpt_text = (
        "著者らは、FreeTxtの抽出型要約機能について、アンケートやフィードバックデータに対してよりも、"
        "長文ドキュメントに対して有用だったと報告しています。比較の向きは、"
        "「長文ドキュメントに対する有用性 > アンケート／フィードバックデータに対する有用性」です。"
        "これはパートナーの評価に基づく、当時の現行版の短所として記載されています。"
    )
    excerpt_hash = hashlib.sha256(excerpt_text.encode("utf-8")).hexdigest()
    source["anchors"].append({
        "anchor_id": ANCHOR_ID,
        "kind": "section",
        "start": "Section 3.4, extractive summarisation",
        "end": "Section 4, direction of partner feedback on current-release shortcoming",
        "extracted_text_sha256": excerpt_hash,
    })

    input_dir = HERE / "inputs" / BATCH_ID / "jobs" / JOB_ID
    job_dir = HERE / "jobs" / JOB_ID
    if input_dir.exists() or job_dir.exists():
        raise FileExistsError(JOB_ID)
    input_dir.mkdir(parents=True)
    job_dir.mkdir(parents=True)
    excerpt = {
        "source_id": source["source_id"],
        "source_version": source["version"],
        "source_sha256": source["sha256"],
        "anchor_id": ANCHOR_ID,
        "extracted_text_sha256": excerpt_hash,
        "text": excerpt_text,
    }
    write_json(input_dir / "source.json", source)
    write_json(input_dir / "approved_sources.json", {"schema_version": 1, "sources": [source]})
    write_json(input_dir / "excerpt.json", excerpt)

    bundle = job_dir / f"Gurumoji_Job_{JOB_ID}_g1.zip"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "prepare_colab_claim_job.py"),
        "--data-dir", str(HERE / "state"),
        "--expert-id", "exp-quantitative-text-analysis",
        "--source-json", str(input_dir / "source.json"),
        "--excerpt-json", str(input_dir / "excerpt.json"),
        "--approved-sources-json", str(input_dir / "approved_sources.json"),
        "--output", str(bundle),
        "--job-id", JOB_ID,
        "--ttl-minutes", "55",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    if result.returncode:
        raise RuntimeError(f"Job preparation failed: {result.stdout}\n{result.stderr}")
    prepared = json.loads(result.stdout)
    prepared.update({
        "batch_id": BATCH_ID,
        "bundle_path": bundle.relative_to(ROOT).as_posix(),
        "source_id": source["source_id"],
        "source_record_path": (input_dir / "source.json").relative_to(ROOT).as_posix(),
        "excerpt_path": (input_dir / "excerpt.json").relative_to(ROOT).as_posix(),
        "source_snapshot_path": SNAPSHOT_PATH.relative_to(ROOT).as_posix(),
        "source_sha256": source["sha256"],
        "excerpt_sha256": excerpt_hash,
        "expert_id": "exp-quantitative-text-analysis",
        "anchor_id": ANCHOR_ID,
        "gpu": "NVIDIA A100-SXM4-80GB",
        "model_reference": manifest["model_reference"],
        "generation": 1,
        "status": "ready_for_user_started_colab",
        "review_context": "Corrective generation after job 02 reversed the explicitly stated comparison direction.",
    })

    template = (HERE / "jobs" / f"{BATCH_ID}-01" / "colab_run_job.py").read_text(encoding="utf-8")
    template = template.replace(f"{BATCH_ID}-01", JOB_ID)
    template = template.replace(first["bundle_sha256"], prepared["bundle_sha256"])
    (job_dir / "colab_run_job.py").write_text(template, encoding="utf-8")
    manifest["jobs"].append(prepared)
    manifest["total_jobs"] = len(manifest["jobs"])
    manifest["status"] = "ready_for_user_started_colab"
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(MANIFEST_PATH, manifest)

    done = [job for job in manifest["jobs"] if job.get("status") in {
        "candidate_ready", "accepted_unapproved_candidate_commit", "failed", "hold_for_revision"
    }]
    progress = {
        "batch_id": BATCH_ID,
        "updated_at": manifest["updated_at"],
        "total_jobs": len(manifest["jobs"]),
        "finished_jobs": len(done),
        "candidate_ready": sum(job.get("status") in {
            "candidate_ready", "accepted_unapproved_candidate_commit"
        } for job in manifest["jobs"]),
        "failed": sum(job.get("status") == "failed" for job in manifest["jobs"]),
        "jobs": [{key: job.get(key) for key in (
            "job_id", "expert_id", "source_id", "anchor_id", "status", "result_sha256", "error", "review"
        )} for job in manifest["jobs"]],
    }
    write_json(HERE / f"{BATCH_ID}-progress.json", progress)
    print(json.dumps({
        "job_id": JOB_ID,
        "anchor_id": ANCHOR_ID,
        "bundle_path": prepared["bundle_path"],
        "bundle_sha256": prepared["bundle_sha256"],
        "excerpt_sha256": excerpt_hash,
        "source_sha256_scope": "curated evidence-text snapshot, not original PDF bytes",
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
