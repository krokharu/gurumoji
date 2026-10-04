"""Run pending hash-bound method jobs sequentially through the active Colab A100."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "b20260928t040043.json"
SESSION = "gurumoji-a100-v3-retry-20260928-040043"
COLAB = "/home/kurok/.local/bin/colab"


def wsl_path(path: Path) -> str:
    value = str(path.resolve())
    drive, rest = value.split(":", 1)
    return f"/mnt/{drive.lower()}{rest.replace(chr(92), '/')}"


def run_colab(args: list[str], *, timeout: float = 3600) -> subprocess.CompletedProcess[str]:
    command = ["wsl.exe", "-d", "Ubuntu-24.04", "--", COLAB, *args]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, check=False)


def save_manifest(value: dict) -> None:
    temp = MANIFEST.with_name(MANIFEST.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    temp.replace(MANIFEST)


def update_progress(manifest: dict) -> None:
    done = [job for job in manifest["jobs"] if job.get("status") in {
        "candidate_ready", "accepted_unapproved_candidate_commit", "failed"}]
    record = {
        "batch_id": manifest["batch_id"], "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_jobs": len(manifest["jobs"]), "finished_jobs": len(done),
        "candidate_ready": sum(job.get("status") in {"candidate_ready", "accepted_unapproved_candidate_commit"}
                                for job in manifest["jobs"]),
        "failed": sum(job.get("status") == "failed" for job in manifest["jobs"]),
        "jobs": [{k: job.get(k) for k in ("job_id", "expert_id", "source_id", "anchor_id", "status",
                                             "result_sha256", "error")}
                 for job in manifest["jobs"]],
    }
    (HERE / f"{manifest['batch_id']}-progress.json").write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures = 0
    for index, job in enumerate(manifest["jobs"], 1):
        if job.get("status") not in {"ready_for_user_started_colab", "failed"}:
            continue
        job_id = job["job_id"]
        job_dir = (ROOT / job["bundle_path"]).parent
        bundle_path = ROOT / job["bundle_path"]
        runner = job_dir / "colab_run_job.py"
        result_path = job_dir / f"Gurumoji_Result_{job_id}_g1.zip"
        status_path = job_dir / f"Gurumoji_Status_{job_id}_g1.json"
        print(f"[{index}/{len(manifest['jobs'])}] starting {job_id} {job['expert_id']} / {job['anchor_id']}",
              flush=True)

        upload = run_colab(["upload", wsl_path(bundle_path),
                            f"/content/Gurumoji_Job_{job_id}_g1.zip", "--session", SESSION], timeout=180)
        if upload.returncode:
            job.update({"status": "failed", "error": "upload_failed", "error_detail": upload.stderr[-1200:]})
            failures += 1
            save_manifest(manifest); update_progress(manifest)
            print(f"[{index}/{len(manifest['jobs'])}] upload failed {job_id}: {upload.stderr[-500:]}", flush=True)
            continue

        execution = run_colab(["exec", "--session", SESSION, "--file", wsl_path(runner), "--timeout", "3600"],
                              timeout=3600)
        if execution.returncode:
            job["execution_returncode"] = execution.returncode
        print(f"[{index}/{len(manifest['jobs'])}] execution returned for {job_id}", flush=True)

        status_download = run_colab(["download", f"/content/Gurumoji_Status_{job_id}_g1.json",
                                     wsl_path(status_path), "--session", SESSION], timeout=180)
        if status_download.returncode or not status_path.is_file():
            job.update({"status": "failed", "error": "status_download_failed",
                        "error_detail": (status_download.stderr or execution.stderr)[-1200:]})
            failures += 1
            save_manifest(manifest); update_progress(manifest)
            print(f"[{index}/{len(manifest['jobs'])}] missing status for {job_id}", flush=True)
            continue

        remote_status = json.loads(status_path.read_text(encoding="utf-8"))
        job["colab_status"] = remote_status
        if remote_status.get("status") != "candidate_ready":
            job.update({"status": "failed", "error": remote_status.get("error_type", remote_status.get("status")),
                        "error_detail": remote_status.get("error", "")})
            failures += 1
            save_manifest(manifest); update_progress(manifest)
            print(f"[{index}/{len(manifest['jobs'])}] candidate failed {job_id}: {job['error']}", flush=True)
            continue

        result_download = run_colab(["download", f"/content/Gurumoji_Result_{job_id}_g1.zip",
                                     wsl_path(result_path), "--session", SESSION], timeout=180)
        if result_download.returncode or not result_path.is_file():
            job.update({"status": "failed", "error": "result_download_failed",
                        "error_detail": result_download.stderr[-1200:]})
            failures += 1
            save_manifest(manifest); update_progress(manifest)
            print(f"[{index}/{len(manifest['jobs'])}] missing result for {job_id}", flush=True)
            continue

        import hashlib
        result_sha = hashlib.sha256(result_path.read_bytes()).hexdigest()
        if result_sha != remote_status.get("result_sha256"):
            job.update({"status": "failed", "error": "result_hash_mismatch",
                        "result_sha256": result_sha})
            failures += 1
            save_manifest(manifest); update_progress(manifest)
            print(f"[{index}/{len(manifest['jobs'])}] result hash mismatch {job_id}", flush=True)
            continue

        job.update({"status": "candidate_ready", "result_path": result_path.relative_to(ROOT).as_posix(),
                    "result_sha256": result_sha, "gpu": remote_status.get("gpu"),
                    "model_reference": remote_status.get("model_reference"),
                    "updated_at": datetime.now(timezone.utc).isoformat()})
        save_manifest(manifest); update_progress(manifest)
        print(f"[{index}/{len(manifest['jobs'])}] candidate_ready {job_id} sha256={result_sha}", flush=True)

    print(json.dumps({"batch_id": manifest["batch_id"], "candidate_ready": sum(
        job.get("status") in {"candidate_ready", "accepted_unapproved_candidate_commit"} for job in manifest["jobs"]),
        "failed": sum(job.get("status") == "failed" for job in manifest["jobs"]),
        "remaining_failures": failures}, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
