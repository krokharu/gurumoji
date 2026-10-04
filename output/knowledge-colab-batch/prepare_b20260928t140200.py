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
BATCH_ID = "b20260928t140200"
SESSION = "gurumoji-a100-groupstats-20260928-140200"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_ID = "RES-scipy-f-oneway"
SOURCE_SHA = "f1f260998e47f0d7d994c8a08574901fdaa828cba0ce80fc47af47e125ce43a7"
SOURCE_URL = "https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.f_oneway.html"
SOURCE_VERSION = "scipy-v1.18.0-manual-f_oneway-retrieved-2026-09-28"
SOURCE_RECORD = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-source.json"
EVIDENCE_SNAPSHOT = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-selected-evidence.txt"
TASKS = [
    {
        "job_id": f"{BATCH_ID}-01",
        "anchor_id": "f-oneway-welch-anova-equal-var",
        "start": "f_oneway equal_var parameter",
        "end": "Standard and Welch one-way ANOVA selection",
        "text": (
            "In the SciPy v1.18.0 f_oneway API, equal_var=True is the default and selects standard one-way ANOVA "
            "with an equal-population-variance assumption. Setting equal_var=False selects Welch's ANOVA, which "
            "does not assume equal population variances. The option was added in SciPy 1.16.0."
        ),
    },
    {
        "job_id": f"{BATCH_ID}-02",
        "anchor_id": "f-oneway-nan-policy-axis-slices",
        "start": "f_oneway nan_policy parameter",
        "end": "NaN policies and omission within each axis slice",
        "text": (
            "SciPy v1.18.0 f_oneway supports three nan_policy choices: propagate, omit, and raise; propagate is "
            "the default. Under omit, missing values are removed separately within each axis slice. If too little "
            "data remains in a slice after omission, that slice's result is NaN."
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
    source = {
        "schema_version": 1,
        "source_id": SOURCE_ID,
        "source_type": "web",
        "title": "SciPy v1.18.0 stats.f_oneway API reference",
        "authors": ["SciPy community"],
        "publication_year": 2026,
        "version": SOURCE_VERSION,
        "sha256": SOURCE_SHA,
        "locator": {"kind": "url", "value": SOURCE_URL},
        "access_scope": "official_page",
        "license": {"license_id": "BSD-3-Clause", "terms": "BSD 3-Clause License; preserve notices and conditions"},
        "license_url": {"kind": "https", "value": "https://opensource.org/license/bsd-3-clause/"},
        "rights": {"classification": "licensed", "allowed_routes": ["local", "colab", "export"]},
        "adaptation_notice": "Pinned official SciPy API documentation page only; selected facts are paraphrased. No user or research data is included.",
        "anchors": [],
    }
    evidence_parts = [
        "SciPy community. SciPy v1.18.0 stats.f_oneway API reference.",
        f"Official API page: {SOURCE_URL}",
        f"Document SHA-256: {SOURCE_SHA}. License: BSD-3-Clause.",
        "Evidence paraphrase A: the default equal_var=True selects standard one-way ANOVA with equal population variances; equal_var=False selects Welch's ANOVA without that equal-variance assumption. This parameter was introduced in version 1.16.0.",
        "Evidence paraphrase B: nan_policy supports propagate, omit, and raise. Propagate is the default. Omit removes missing values separately within each axis slice; a slice with insufficient data after omission returns NaN.",
        "These are version-scoped API behaviors, not evidence that the method is implemented in Gurumoji or valid for every utterance-level research design.",
        "This local evidence text is a curated paraphrase, not a verbatim transcription; its hash is separate from the official page hash.",
    ]
    evidence_text = "\n".join(evidence_parts) + "\n"
    EVIDENCE_SNAPSHOT.write_bytes(evidence_text.encode("utf-8"))
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
            "source_id": SOURCE_ID,
            "source_version": SOURCE_VERSION,
            "source_sha256": SOURCE_SHA,
            "anchor_id": task["anchor_id"],
            "extracted_text_sha256": task["excerpt_sha256"],
            "text": task["text"],
        }
        write_json(input_dir / "source.json", source)
        write_json(input_dir / "approved_sources.json", {"schema_version": 1, "sources": [source]})
        write_json(input_dir / "excerpt.json", excerpt)
        bundle = job_dir / f"Gurumoji_Job_{job_id}_g1.zip"
        command = [
            sys.executable, str(ROOT / "scripts" / "prepare_colab_claim_job.py"),
            "--data-dir", str(HERE / "state"),
            "--expert-id", "exp-group-comparison-statistics",
            "--source-json", str(input_dir / "source.json"),
            "--excerpt-json", str(input_dir / "excerpt.json"),
            "--approved-sources-json", str(input_dir / "approved_sources.json"),
            "--output", str(bundle), "--job-id", job_id, "--ttl-minutes", "55",
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        if result.returncode:
            raise RuntimeError(f"{job_id} preparation failed: {result.stdout}\n{result.stderr}")
        prepared = json.loads(result.stdout)
        prepared.update({
            "batch_id": BATCH_ID,
            "bundle_path": bundle.relative_to(ROOT).as_posix(),
            "source_id": SOURCE_ID,
            "source_record_path": SOURCE_RECORD.relative_to(ROOT).as_posix(),
            "excerpt_path": (input_dir / "excerpt.json").relative_to(ROOT).as_posix(),
            "evidence_snapshot_path": EVIDENCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "evidence_snapshot_sha256": evidence_snapshot_sha,
            "source_sha256": SOURCE_SHA,
            "excerpt_sha256": task["excerpt_sha256"],
            "expert_id": "exp-group-comparison-statistics",
            "anchor_id": task["anchor_id"],
            "gpu": "NVIDIA A100",
            "model_reference": MODEL,
            "generation": 1,
            "status": "ready_for_user_started_colab",
        })
        template = (HERE / "jobs" / "b20260928t132500-03" / "colab_run_job.py").read_text(encoding="utf-8")
        template = template.replace("b20260928t132500-03", job_id)
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
        "gpu": "NVIDIA A100",
        "model_reference": MODEL,
        "session_name": SESSION,
        "status": "ready_for_user_started_colab",
        "total_jobs": len(jobs),
        "expert_id": "exp-group-comparison-statistics",
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "source_license": "BSD-3-Clause",
        "source_document_sha256": SOURCE_SHA,
        "evidence_snapshot": {
            "path": EVIDENCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "sha256": evidence_snapshot_sha,
            "scope": "curated paraphrases; not verbatim documentation text",
        },
        "jobs": jobs,
    }
    write_json(manifest_path, manifest)
    run_template = (HERE / "run_b20260928t132500.py").read_text(encoding="utf-8")
    run_template = run_template.replace("b20260928t132500.json", f"{BATCH_ID}.json")
    run_template = run_template.replace("gurumoji-a100-correlation-20260928-132500", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(run_template, encoding="utf-8")
    print(json.dumps({
        "batch_id": BATCH_ID,
        "session_name": SESSION,
        "source_sha256": SOURCE_SHA,
        "evidence_snapshot_sha256": evidence_snapshot_sha,
        "jobs": [{key: job[key] for key in (
            "job_id", "expert_id", "anchor_id", "bundle_path", "bundle_sha256", "excerpt_sha256", "deadline"
        )} for job in jobs],
    }, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
