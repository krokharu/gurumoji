from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t132500"
JOB_ID = f"{BATCH_ID}-04"
ANCHOR_ID = "pearsonr-confidence-interval-methods-paraphrase"
SESSION = "gurumoji-a100-correlation-20260928-132500"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_ID = "RES-scipy-pearsonr"
SOURCE_SHA = "9999856b875cf15abcad22654b16bd3d2801f89eef28b42a048114e93eac68c3"
SOURCE_PATH = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-source.json"
SOURCE_URL = "https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.pearsonr.html"
EXCERPT_TEXT = (
    "For confidence limits from a PearsonRResult, Fisher's transformation is the default route. Supplying a "
    "BootstrapMethod object instead delegates interval construction to scipy.stats.bootstrap with the object's "
    "settings. A resample with a degenerate distribution can yield NaN limits; the manual describes this as "
    "common in very small samples and gives roughly six observations as an example."
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    manifest_path = HERE / f"{BATCH_ID}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if any(job["job_id"] == JOB_ID for job in manifest["jobs"]):
        raise FileExistsError(JOB_ID)
    previous = next(job for job in manifest["jobs"] if job["job_id"] == f"{BATCH_ID}-02")
    if previous.get("status") != "candidate_ready":
        raise RuntimeError("the initial confidence-interval job is not in the expected state")
    previous.update({
        "status": "hold_for_revision",
        "review": (
            "The API facts were correct, but the generated exception field included an editorial instruction "
            "rather than a source-backed fact. Corrective Job 04 restates the small-sample caveat declaratively."
        ),
    })
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    if source["source_id"] != SOURCE_ID or source["sha256"] != SOURCE_SHA:
        raise RuntimeError("SciPy source hash mismatch")
    excerpt_sha = digest(EXCERPT_TEXT.encode("utf-8"))
    source["anchors"].append({
        "anchor_id": ANCHOR_ID,
        "kind": "section",
        "start": "PearsonRResult confidence interval methods",
        "end": "Default interval, bootstrap option, and small-sample degeneracy",
        "extracted_text_sha256": excerpt_sha,
    })
    input_dir = HERE / "inputs" / BATCH_ID / "jobs" / JOB_ID
    job_dir = HERE / "jobs" / JOB_ID
    if input_dir.exists() or job_dir.exists():
        raise FileExistsError(JOB_ID)
    input_dir.mkdir(parents=True)
    job_dir.mkdir(parents=True)
    excerpt = {
        "source_id": SOURCE_ID,
        "source_version": source["version"],
        "source_sha256": SOURCE_SHA,
        "anchor_id": ANCHOR_ID,
        "extracted_text_sha256": excerpt_sha,
        "text": EXCERPT_TEXT,
    }
    write_json(input_dir / "source.json", source)
    write_json(input_dir / "approved_sources.json", {"schema_version": 1, "sources": [source]})
    write_json(input_dir / "excerpt.json", excerpt)
    bundle = job_dir / f"Gurumoji_Job_{JOB_ID}_g1.zip"
    command = [
        sys.executable, str(ROOT / "scripts" / "prepare_colab_claim_job.py"),
        "--data-dir", str(HERE / "state"),
        "--expert-id", "exp-correlation",
        "--source-json", str(input_dir / "source.json"),
        "--excerpt-json", str(input_dir / "excerpt.json"),
        "--approved-sources-json", str(input_dir / "approved_sources.json"),
        "--output", str(bundle), "--job-id", JOB_ID, "--ttl-minutes", "55",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    if result.returncode:
        raise RuntimeError(f"{JOB_ID} preparation failed: {result.stdout}\n{result.stderr}")
    prepared = json.loads(result.stdout)
    evidence_path = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-confidence-revision.txt"
    evidence_text = (
        f"SciPy v1.18.0 pearsonr official API page: {SOURCE_URL}\n"
        f"Official page SHA-256: {SOURCE_SHA}; BSD-3-Clause.\n"
        "Curated paraphrase: the result object's interval method defaults to Fisher transformation; a bootstrap "
        "configuration delegates calculation to SciPy's bootstrap routine. Degenerate resamples can return NaN "
        "confidence limits, and this is common for very small samples, with about six observations offered as an example.\n"
    )
    evidence_path.write_bytes(evidence_text.encode("utf-8"))
    prepared.update({
        "batch_id": BATCH_ID,
        "bundle_path": bundle.relative_to(ROOT).as_posix(),
        "source_id": SOURCE_ID,
        "source_record_path": SOURCE_PATH.relative_to(ROOT).as_posix(),
        "excerpt_path": (input_dir / "excerpt.json").relative_to(ROOT).as_posix(),
        "evidence_snapshot_path": evidence_path.relative_to(ROOT).as_posix(),
        "evidence_snapshot_sha256": digest(evidence_text.encode("utf-8")),
        "source_sha256": SOURCE_SHA,
        "excerpt_sha256": excerpt_sha,
        "expert_id": "exp-correlation",
        "anchor_id": ANCHOR_ID,
        "gpu": "NVIDIA A100-SXM4-40GB",
        "model_reference": MODEL,
        "generation": 1,
        "status": "ready_for_user_started_colab",
        "supersedes_job_id": previous["job_id"],
        "review_context": "Corrective excerpt after the first draft included a non-evidential instruction in its exception field.",
    })
    template = (HERE / "jobs" / f"{BATCH_ID}-02" / "colab_run_job.py").read_text(encoding="utf-8")
    template = template.replace(f"{BATCH_ID}-02", JOB_ID)
    template = re.sub(
        r'EXPECTED_BUNDLE_SHA256 = "[0-9a-f]{64}"',
        f'EXPECTED_BUNDLE_SHA256 = "{prepared["bundle_sha256"]}"',
        template,
    )
    (job_dir / "colab_run_job.py").write_text(template, encoding="utf-8")
    manifest["jobs"].append(prepared)
    manifest["total_jobs"] = len(manifest["jobs"])
    manifest["status"] = "ready_for_user_started_colab"
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(manifest_path, manifest)
    progress = {
        "batch_id": BATCH_ID,
        "updated_at": manifest["updated_at"],
        "total_jobs": len(manifest["jobs"]),
        "finished_jobs": sum(job.get("status") in {
            "candidate_ready", "accepted_unapproved_candidate_commit", "failed", "hold_for_revision"
        } for job in manifest["jobs"]),
        "candidate_ready": sum(job.get("status") in {
            "candidate_ready", "accepted_unapproved_candidate_commit"
        } for job in manifest["jobs"]),
        "failed": sum(job.get("status") == "failed" for job in manifest["jobs"]),
        "held_for_revision": sum(job.get("status") == "hold_for_revision" for job in manifest["jobs"]),
        "jobs": [{key: job.get(key) for key in (
            "job_id", "expert_id", "source_id", "anchor_id", "status", "result_sha256", "error", "review"
        )} for job in manifest["jobs"]],
    }
    write_json(HERE / f"{BATCH_ID}-progress.json", progress)
    print(json.dumps({
        "job_id": JOB_ID, "anchor_id": ANCHOR_ID,
        "bundle_path": prepared["bundle_path"],
        "bundle_sha256": prepared["bundle_sha256"],
        "excerpt_sha256": excerpt_sha,
        "source_sha256": SOURCE_SHA,
        "status": prepared["status"],
    }, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
