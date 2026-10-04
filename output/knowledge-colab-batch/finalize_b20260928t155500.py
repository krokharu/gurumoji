"""Record the reviewed unapproved-candidate decision for the GiNZA job."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "b20260928t155500.json"
DB = HERE / "state" / "knowledge_builder" / "state.sqlite3"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("batch_id") != "b20260928t155500" or len(manifest.get("jobs", [])) != 1:
        raise RuntimeError("unexpected GiNZA batch manifest")
    job = manifest["jobs"][0]
    if job["job_id"] != "b20260928t155500-01" or job.get("status") != "candidate_ready":
        raise RuntimeError("GiNZA job is not ready for review")
    uri = f"file:{DB.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        status, generation = connection.execute(
            "SELECT status, accepted_generation FROM knowledge_jobs WHERE job_id=?", (job["job_id"],)
        ).fetchone()
        commit_sha = connection.execute(
            "SELECT manifest_sha256 FROM knowledge_commits WHERE job_id=? AND generation=1", (job["job_id"],)
        ).fetchone()[0]
    if status != "accepted" or generation != job["generation"]:
        raise RuntimeError("accepted JobStore record missing")
    job["status"] = "accepted_unapproved_candidate_commit"
    job["commit_sha256"] = commit_sha
    job["review_note"] = (
        "Accepted as an unapproved candidate. The claim distinguishes SudachiPy's tokenization and POS role from "
        "Hugging Face Transformers as the pretrained-model framework for ja_ginza_electra; no performance claim is made."
    )
    manifest["status"] = "accepted_unapproved_candidates"
    manifest["session_stopped"] = True
    manifest["active_sessions_after_stop"] = 0
    manifest["compute_units_before_batch"] = 81.37
    manifest["compute_units_after_batch"] = 81.15
    manifest["compute_units_delta"] = 0.22
    manifest["finalized_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    progress = {
        "batch_id": manifest["batch_id"],
        "updated_at": manifest["finalized_at"],
        "total_jobs": 1,
        "finished_jobs": 1,
        "candidate_ready": 1,
        "accepted_unapproved_candidate_commit": 1,
        "failed": 0,
        "jobs": [{k: job.get(k) for k in ("job_id", "expert_id", "source_id", "anchor_id", "status",
                                               "result_sha256", "commit_sha256", "review_note")}],
    }
    (HERE / f"{manifest['batch_id']}-progress.json").write_text(
        json.dumps(progress, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(progress, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
