"""Resume a pinned, checkpointed A100 batch and import each completed result locally."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PILOT_RUNNER = (ROOT / "output/knowledge-colab-instruction-pilot/colab_run_job.py").read_text(encoding="utf-8")
CLI = "/home/kurok/.local/bin/colab"
SESSION = "gurumoji-knowledge-batch"


def wsl_path(path: Path) -> str:
    absolute = path.resolve()
    return "/mnt/" + absolute.drive[0].lower() + absolute.as_posix()[2:]


def run(*command: str, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)


def colab(*arguments: str, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return run("wsl.exe", "-d", "Ubuntu-24.04", "--exec", CLI, *arguments, timeout=timeout)


def record_progress(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def download(remote: str, local: Path) -> bool:
    local.parent.mkdir(parents=True, exist_ok=True)
    outcome = colab("download", "--session", SESSION, remote, wsl_path(local), timeout=120)
    return outcome.returncode == 0 and local.is_file()


def runner_for(job: dict, target: Path) -> None:
    job_id = job["job_id"]
    replacements = {
        "/content/gurumoji_pilot_job_r3.zip": f"/content/gurumoji_batch_{job_id}.zip",
        "/content/gurumoji_pilot_result_r3.zip": f"/content/gurumoji_batch_result_{job_id}.zip",
        "/content/gurumoji_pilot_status_r3.json": f"/content/gurumoji_batch_status_{job_id}.json",
        "/content/gurumoji_pilot_generated_r3.json": f"/content/gurumoji_batch_generated_{job_id}.json",
        "/content/gurumoji_pilot_generator_error_r3.json": f"/content/gurumoji_batch_generator_error_{job_id}.json",
        "8a2c45f207aea475af608b62d535a2e8f03b7c9b14b35e7f8ae7f62eb0846f9a": job["bundle_sha256"],
        "pilot-hermann-20260927-r3": job_id,
    }
    source = PILOT_RUNNER
    for old, new in replacements.items():
        assert old in source
        source = source.replace(old, new)
    target.write_text(source, encoding="utf-8")


def main(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    progress_path = HERE / f"{manifest['batch_id']}-progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.is_file() else {
        "batch_id": manifest["batch_id"], "jobs": {}}
    for job in manifest["jobs"]:
        job_id = job["job_id"]
        if progress["jobs"].get(job_id, {}).get("status") == "accepted_unapproved_candidate_commit":
            print(json.dumps({"job_id": job_id, "status": "already_accepted"}), flush=True)
            continue
        bundle = ROOT / job["bundle_path"]
        if hashlib.sha256(bundle.read_bytes()).hexdigest() != job["bundle_sha256"]:
            raise RuntimeError(f"{job_id}: local bundle hash changed")
        job_dir = bundle.parent
        runner = job_dir / "colab_run_job.py"
        runner_for(job, runner)
        remote_bundle = f"/content/gurumoji_batch_{job_id}.zip"
        remote_result = f"/content/gurumoji_batch_result_{job_id}.zip"
        remote_status = f"/content/gurumoji_batch_status_{job_id}.json"
        uploaded = colab("upload", "--session", SESSION, wsl_path(bundle), remote_bundle, timeout=120)
        if uploaded.returncode:
            raise RuntimeError(f"{job_id}: Colab upload failed: {uploaded.stderr[-400:]}")
        progress["jobs"][job_id] = {"status": "uploaded", "expert_id": job["expert_id"],
                                    "source_id": job["source_id"]}
        record_progress(progress_path, progress)
        print(json.dumps({"job_id": job_id, "status": "uploaded"}), flush=True)

        status = None
        for attempt in range(1, 3):
            outcome = colab("exec", "--session", SESSION, "--timeout", "600",
                            "-f", wsl_path(runner), timeout=660)
            (job_dir / f"colab-attempt-{attempt}.log").write_text(
                (outcome.stdout + "\n" + outcome.stderr)[-25000:], encoding="utf-8")
            status_file = job_dir / "status.json"
            for _ in range(18):
                if download(remote_status, status_file):
                    status = json.loads(status_file.read_text(encoding="utf-8"))
                    if status.get("status") in {"candidate_ready", "failed"}:
                        break
                time.sleep(10)
            if status and status.get("status") == "candidate_ready":
                break
            error_file = job_dir / "generator_error.json"
            download(f"/content/gurumoji_batch_generator_error_{job_id}.json", error_file)
            print(json.dumps({"job_id": job_id, "attempt": attempt, "status": status,
                              "cli_exit": outcome.returncode}), flush=True)

        if not status or status.get("status") != "candidate_ready":
            progress["jobs"][job_id]["status"] = "failed"
            progress["jobs"][job_id]["detail"] = status
            record_progress(progress_path, progress)
            continue
        result = job_dir / f"Gurumoji_Result_{job_id}_g1.zip"
        if not download(remote_result, result):
            raise RuntimeError(f"{job_id}: completed result cannot be downloaded")
        actual_hash = hashlib.sha256(result.read_bytes()).hexdigest()
        if actual_hash != status["result_sha256"]:
            raise RuntimeError(f"{job_id}: result hash mismatch")
        accepted = run(sys.executable, str(ROOT / "scripts/accept_colab_claim_job.py"),
                       "--data-dir", str(HERE / "state"), "--result-zip", str(result),
                       "--approved-sources-json",
                       str(bundle.with_name(bundle.stem + ".local-approved-sources.json")), timeout=120)
        if accepted.returncode:
            raise RuntimeError(f"{job_id}: local acceptance failed: {accepted.stdout} {accepted.stderr}")
        acceptance = json.loads(accepted.stdout)
        progress["jobs"][job_id].update(acceptance)
        progress["jobs"][job_id]["result_path"] = str(result.relative_to(ROOT)).replace("\\", "/")
        record_progress(progress_path, progress)
        print(json.dumps({"job_id": job_id, "status": acceptance["status"],
                          "result_sha256": actual_hash}), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
