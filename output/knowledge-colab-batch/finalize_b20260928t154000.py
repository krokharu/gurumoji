"""Record reviewed unapproved-candidate decisions for the corrected Byrne jobs."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "b20260928t154000.json"
DB = HERE / "state" / "knowledge_builder" / "state.sqlite3"
DECISIONS = {
    "b20260928t154000-01": (
        "Accepted as an unapproved candidate. The revised output does not repeat the earlier incorrect author name; "
        "it accurately records the study's theoretical positioning and four continua."
    ),
    "b20260928t154000-02": (
        "Accepted as an unapproved candidate. The revised output removes the unsupported proficiency-improvement "
        "wording and retains iterative engagement with data and transparent recording of coding iterations."
    ),
}


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("batch_id") != "b20260928t154000":
        raise RuntimeError("unexpected batch manifest")
    uri = f"file:{DB.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        commits = {row[0]: row[1] for row in connection.execute(
            "SELECT job_id, manifest_sha256 FROM knowledge_commits WHERE generation=1"
        )}
        states = {row[0]: (row[1], row[2]) for row in connection.execute(
            "SELECT job_id, status, accepted_generation FROM knowledge_jobs"
        )}
    for job in manifest["jobs"]:
        job_id = job["job_id"]
        if job_id not in DECISIONS or job.get("status") != "candidate_ready":
            raise RuntimeError(f"job is not ready for review: {job_id}")
        status, accepted_generation = states.get(job_id, (None, None))
        if status != "accepted" or accepted_generation != job["generation"] or job_id not in commits:
            raise RuntimeError(f"accepted JobStore record missing: {job_id}")
        job["status"] = "accepted_unapproved_candidate_commit"
        job["commit_sha256"] = commits[job_id]
        job["review_note"] = DECISIONS[job_id]
    manifest["status"] = "accepted_unapproved_candidates"
    manifest["session_stopped"] = True
    manifest["active_sessions_after_stop"] = 0
    manifest["compute_units_before_batch"] = 81.93
    manifest["compute_units_after_batch"] = 81.37
    manifest["compute_units_delta"] = 0.56
    manifest["finalized_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    progress = {
        "batch_id": manifest["batch_id"],
        "updated_at": manifest["finalized_at"],
        "total_jobs": len(manifest["jobs"]),
        "finished_jobs": len(manifest["jobs"]),
        "candidate_ready": 2,
        "accepted_unapproved_candidate_commit": 2,
        "failed": 0,
        "jobs": [{k: job.get(k) for k in ("job_id", "expert_id", "source_id", "anchor_id", "status",
                                               "result_sha256", "commit_sha256", "review_note")}
                  for job in manifest["jobs"]],
    }
    (HERE / f"{manifest['batch_id']}-progress.json").write_text(
        json.dumps(progress, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(progress, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
