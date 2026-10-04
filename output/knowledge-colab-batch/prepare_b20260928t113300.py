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
BATCH_ID = "b20260928t113300"
SESSION = "gurumoji-a100-deepknowledge-20260928-113300"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_ID = "RES-scipy-describe"
SOURCE_SHA = "66566c9dfdc18383000a0badfd29d550f8073edfd85c2686f8162d299e84960a"
SOURCE_URL = "https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.describe.html"
SOURCE_INPUT = HERE / "inputs" / "b20260928t070100" / "jobs" / "b20260928t070100-01" / "source.json"
SOURCE_RECORD = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-source.json"
EVIDENCE_SNAPSHOT = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-selected-evidence.txt"
TASKS = [
    {
        "job_id": f"{BATCH_ID}-01",
        "anchor_id": "describe-axis-default-and-whole-array-scope",
        "start": "SciPy stats.describe axis parameter",
        "end": "Default axis 0 versus axis=None over the whole input array",
        "text": (
            "The SciPy v1.18.0 stats.describe reference specifies axis=0 as the default. "
            "When axis=None, the calculations are performed over the whole input array."
        ),
    },
    {
        "job_id": f"{BATCH_ID}-02",
        "anchor_id": "describe-bias-option-skewness-kurtosis",
        "start": "SciPy stats.describe bias parameter",
        "end": "bias=False applies statistical bias corrections to skewness and kurtosis",
        "text": (
            "The SciPy v1.18.0 stats.describe reference gives bias=True as the default. "
            "Setting bias=False applies corrections for statistical bias to the skewness and kurtosis calculations. "
            "This parameter concerns skewness and kurtosis, not the separate ddof option for variance."
        ),
    },
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    manifest_path = HERE / f"{BATCH_ID}.json"
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    source = json.loads(SOURCE_INPUT.read_text(encoding="utf-8"))
    if source["source_id"] != SOURCE_ID or source["sha256"] != SOURCE_SHA or source["locator"]["value"] != SOURCE_URL:
        raise RuntimeError("approved SciPy Source registry mismatch")
    if "colab" not in source["rights"]["allowed_routes"]:
        raise RuntimeError("Colab processing is not allowed by the Source registry")
    source["adaptation_notice"] = (
        "Paraphrased, narrowly selected summaries of the SciPy v1.18.0 official stats.describe API reference. "
        "The selected excerpts preserve the distinction between the aggregation axis and the bias-correction option."
    )

    evidence_text = (
        "SciPy community (2026). SciPy v1.18.0 Manual: scipy.stats.describe.\n"
        "Official API page: " + SOURCE_URL + "\n"
        "Document SHA-256: " + SOURCE_SHA + ". License: BSD-3-Clause; attributed paraphrases only.\n"
        "Evidence paraphrase A: axis defaults to 0; axis=None computes over the entire input array.\n"
        "Evidence paraphrase B: bias defaults to True; bias=False requests statistical bias correction for skewness and kurtosis, separately from ddof for variance.\n"
        "This local evidence text is a curated paraphrase. Its own SHA-256 is separate from the official-page document hash.\n"
    )
    EVIDENCE_SNAPSHOT.write_text(evidence_text, encoding="utf-8")
    evidence_snapshot_sha = digest(evidence_text.encode("utf-8"))
    for task in TASKS:
        task["excerpt_sha256"] = digest(task["text"].encode("utf-8"))
        source["anchors"].append({
            "anchor_id": task["anchor_id"],
            "kind": "section",
            "start": task["start"],
            "end": task["end"],
            "extracted_text_sha256": task["excerpt_sha256"],
        })
    write_json(SOURCE_RECORD, source)

    jobs = []
    for task in TASKS:
        job_id = task["job_id"]
        input_dir = HERE / "inputs" / BATCH_ID / "jobs" / job_id
        job_dir = HERE / "jobs" / job_id
        if input_dir.exists() or job_dir.exists():
            raise FileExistsError(job_id)
        input_dir.mkdir(parents=True)
        job_dir.mkdir(parents=True)
        excerpt = {
            "source_id": source["source_id"],
            "source_version": source["version"],
            "source_sha256": source["sha256"],
            "anchor_id": task["anchor_id"],
            "extracted_text_sha256": task["excerpt_sha256"],
            "text": task["text"],
        }
        write_json(input_dir / "source.json", source)
        write_json(input_dir / "approved_sources.json", {"schema_version": 1, "sources": [source]})
        write_json(input_dir / "excerpt.json", excerpt)
        bundle = job_dir / f"Gurumoji_Job_{job_id}_g1.zip"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "prepare_colab_claim_job.py"),
            "--data-dir", str(HERE / "state"),
            "--expert-id", "exp-descriptive-statistics",
            "--source-json", str(input_dir / "source.json"),
            "--excerpt-json", str(input_dir / "excerpt.json"),
            "--approved-sources-json", str(input_dir / "approved_sources.json"),
            "--output", str(bundle),
            "--job-id", job_id,
            "--ttl-minutes", "55",
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        if result.returncode:
            raise RuntimeError(f"{job_id} preparation failed: {result.stdout}\n{result.stderr}")
        prepared = json.loads(result.stdout)
        prepared.update({
            "batch_id": BATCH_ID,
            "bundle_path": bundle.relative_to(ROOT).as_posix(),
            "source_id": source["source_id"],
            "source_record_path": SOURCE_RECORD.relative_to(ROOT).as_posix(),
            "excerpt_path": (input_dir / "excerpt.json").relative_to(ROOT).as_posix(),
            "evidence_snapshot_path": EVIDENCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "evidence_snapshot_sha256": evidence_snapshot_sha,
            "source_sha256": SOURCE_SHA,
            "excerpt_sha256": task["excerpt_sha256"],
            "expert_id": "exp-descriptive-statistics",
            "anchor_id": task["anchor_id"],
            "gpu": "NVIDIA A100-SXM4-80GB",
            "model_reference": MODEL,
            "generation": 1,
            "status": "ready_for_user_started_colab",
        })
        template = (HERE / "jobs" / "b20260928t112200-01" / "colab_run_job.py").read_text(encoding="utf-8")
        template = template.replace("b20260928t112200-01", job_id)
        template = re.sub(
            r'EXPECTED_BUNDLE_SHA256 = "[0-9a-f]{64}"',
            f'EXPECTED_BUNDLE_SHA256 = "{prepared["bundle_sha256"]}"',
            template,
        )
        (job_dir / "colab_run_job.py").write_text(template, encoding="utf-8")
        jobs.append(prepared)

    manifest = {
        "batch_id": BATCH_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gpu": "NVIDIA A100-SXM4-80GB",
        "model_reference": MODEL,
        "session_name": SESSION,
        "status": "ready_for_user_started_colab",
        "total_jobs": len(jobs),
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "source_license": "BSD-3-Clause",
        "source_document_sha256": SOURCE_SHA,
        "evidence_snapshot": {
            "path": EVIDENCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "sha256": evidence_snapshot_sha,
            "scope": "curated paraphrase; not a verbatim transcription",
        },
        "jobs": jobs,
    }
    write_json(manifest_path, manifest)
    run_template = (HERE / "run_b20260928t112200.py").read_text(encoding="utf-8")
    run_template = run_template.replace("b20260928t112200.json", f"{BATCH_ID}.json")
    run_template = run_template.replace("gurumoji-a100-deepknowledge-20260928-112200", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(run_template, encoding="utf-8")
    print(json.dumps({
        "batch_id": BATCH_ID,
        "session_name": SESSION,
        "source_document_sha256": SOURCE_SHA,
        "evidence_snapshot_sha256": evidence_snapshot_sha,
        "jobs": [{
            "job_id": job["job_id"], "anchor_id": job["anchor_id"],
            "bundle_path": job["bundle_path"], "bundle_sha256": job["bundle_sha256"],
            "excerpt_sha256": job["excerpt_sha256"], "deadline": job["deadline"],
        } for job in jobs],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
