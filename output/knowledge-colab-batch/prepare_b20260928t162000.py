"""Prepare one bounded, study-scoped KJ-method Claim from a CC BY article."""
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
BATCH_ID = "b20260928t162000"
JOB_ID = f"{BATCH_ID}-01"
SESSION = "gurumoji-a100-kj-osa-20260928-162000"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_ID = "LIT-niu-2025-osa-kj"
SOURCE_URL = "https://www.frontiersin.org/journals/neurology/articles/10.3389/fneur.2025.1582173/full"
SOURCE_SHA256 = "72b0eee4e2b4f11586d6893156b8e0c76d5df91c20fc15050b693ce190fe086b"
SOURCE_CACHE = HERE / "source-cache" / f"{BATCH_ID}-frontiers-osa-kj.html"
ANCHOR_ID = "osa-kj-card-context-preservation"
TEXT = (
    "The official Frontiers article reports one qualitative study of patients with obstructive sleep apnea and their "
    "co-residents. In this study's KJ-method workflow, significant statements were coded with brief phrases or "
    "sentences; the original descriptions were retained in parentheses for context reference, and each coded item "
    "was recorded individually on a 3 cm by 4 cm card. This is the procedure reported for this one study, not a "
    "universal KJ-method requirement. (Publisher article, section 2.4, Data analysis.)"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    if not SOURCE_CACHE.is_file() or sha256(SOURCE_CACHE.read_bytes()) != SOURCE_SHA256:
        raise RuntimeError("Frontiers publisher page snapshot is missing or its SHA-256 changed")

    excerpt_hash = sha256(TEXT.encode("utf-8"))
    source = {
        "access_scope": "full_text",
        "adaptation_notice": (
            "A short paraphrase of section 2.4 is used for draft Claim generation. The Claim must remain limited to "
            "this single OSA dyadic study and must not state a universal KJ-method requirement. No article body is sent to Colab."
        ),
        "anchors": [{
            "anchor_id": ANCHOR_ID,
            "kind": "section",
            "start": "2.4 Data analysis: coding, context retention, and card recording",
            "end": "Coded content recorded individually on 3 cm by 4 cm cards",
            "extracted_text_sha256": excerpt_hash,
        }],
        "authors": ["Yuqi Niu", "Yefan Shao", "Linlin Chen", "Yali Wang", "Shanwen Sun", "Xiaochun Zhang"],
        "license": {
            "license_id": "CC-BY-4.0",
            "terms": "Creative Commons Attribution License (CC BY 4.0); credit the authors and cite the original publication.",
        },
        "license_url": {"kind": "https", "value": "https://creativecommons.org/licenses/by/4.0/"},
        "locator": {"kind": "doi", "value": "10.3389/fneur.2025.1582173"},
        "publication_year": 2025,
        "rights": {"allowed_routes": ["local", "colab", "export"], "classification": "licensed"},
        "schema_version": 1,
        "sha256": SOURCE_SHA256,
        "source_id": SOURCE_ID,
        "source_type": "paper",
        "title": "Social and environmental determinants of disease uncertainty in obstructive sleep apnea: a dyadic qualitative study on patients and co-residents",
        "version": f"frontiers-publisher-fulltext-html-retrieved-2026-09-28-sha256-{SOURCE_SHA256[:16]}",
    }

    input_dir = HERE / "inputs" / BATCH_ID / "jobs" / JOB_ID
    job_dir = HERE / "jobs" / JOB_ID
    expected_inputs = {"source.json", "approved_sources.json", "excerpt.json"}
    if input_dir.exists() and not {path.name for path in input_dir.iterdir()}.issubset(expected_inputs):
        raise FileExistsError(f"unexpected files already exist in the input path for {JOB_ID}")
    if job_dir.exists() and any(job_dir.iterdir()):
        raise FileExistsError(f"job output path is not empty for {JOB_ID}")
    input_dir.mkdir(parents=True, exist_ok=True)
    job_dir.mkdir(parents=True, exist_ok=True)
    excerpt = {
        "source_id": SOURCE_ID,
        "source_version": source["version"],
        "source_sha256": SOURCE_SHA256,
        "anchor_id": ANCHOR_ID,
        "extracted_text_sha256": excerpt_hash,
        "text": TEXT,
    }
    write_json(input_dir / "source.json", source)
    write_json(input_dir / "approved_sources.json", {"schema_version": 1, "sources": [source]})
    write_json(input_dir / "excerpt.json", excerpt)

    bundle = job_dir / f"Gurumoji_Job_{JOB_ID}_g1.zip"
    command = [
        sys.executable, str(ROOT / "scripts" / "prepare_colab_claim_job.py"),
        "--data-dir", str(HERE / "state"),
        "--expert-id", "exp-kj-method",
        "--source-json", str(input_dir / "source.json"),
        "--excerpt-json", str(input_dir / "excerpt.json"),
        "--approved-sources-json", str(input_dir / "approved_sources.json"),
        "--output", str(bundle), "--job-id", JOB_ID, "--ttl-minutes", "55",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    if result.returncode:
        raise RuntimeError(f"job preparation failed: {result.stdout}\n{result.stderr}")
    job = json.loads(result.stdout)
    job.update({
        "batch_id": BATCH_ID,
        "bundle_path": bundle.relative_to(ROOT).as_posix(),
        "source_id": SOURCE_ID,
        "source_record_path": (input_dir / "source.json").relative_to(ROOT).as_posix(),
        "approved_sources_path": (input_dir / "approved_sources.json").relative_to(ROOT).as_posix(),
        "excerpt_path": (input_dir / "excerpt.json").relative_to(ROOT).as_posix(),
        "source_sha256": SOURCE_SHA256,
        "excerpt_sha256": excerpt_hash,
        "expert_id": "exp-kj-method",
        "anchor_id": ANCHOR_ID,
        "gpu": "NVIDIA A100-SXM4-80GB High-RAM",
        "model_reference": MODEL,
        "generation": 1,
        "status": "ready_for_user_started_colab",
    })

    template = (HERE / "jobs" / "b20260928t155500-01" / "colab_run_job.py").read_text(encoding="utf-8")
    template = template.replace("b20260928t155500-01", JOB_ID)
    template = re.sub(r'EXPECTED_BUNDLE_SHA256 = "[0-9a-f]{64}"',
                      f'EXPECTED_BUNDLE_SHA256 = "{job["bundle_sha256"]}"', template)
    (job_dir / "colab_run_job.py").write_text(template, encoding="utf-8")

    evidence_path = f"output/knowledge-colab-batch/sources-20260928/{BATCH_ID}-osa-kj-card-context.txt"
    evidence_snapshot_hash = sha256((TEXT + "\n").encode("utf-8"))
    snapshot = ROOT / evidence_path
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(TEXT + "\n", encoding="utf-8")
    manifest = {
        "batch_id": BATCH_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gpu": "NVIDIA A100-SXM4-80GB High-RAM",
        "model_reference": MODEL,
        "session_name": SESSION,
        "status": "ready_for_user_started_colab",
        "total_jobs": 1,
        "expert_id": "exp-kj-method",
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "source_license": "CC-BY-4.0",
        "source_document_sha256": SOURCE_SHA256,
        "source_snapshot_path": SOURCE_CACHE.relative_to(ROOT).as_posix(),
        "evidence_snapshot": {
            "path": evidence_path,
            "sha256": evidence_snapshot_hash,
            "scope": "short study-specific paraphrase of publisher article section 2.4; no article body exported",
        },
        "jobs": [job],
    }
    write_json(HERE / f"{BATCH_ID}.json", manifest)

    runner = (HERE / "run_b20260928t155500.py").read_text(encoding="utf-8")
    runner = runner.replace("b20260928t155500.json", f"{BATCH_ID}.json")
    runner = runner.replace("gurumoji-a100-ginza-v520-20260928-155500", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(runner, encoding="utf-8")
    print(json.dumps({
        "batch_id": BATCH_ID,
        "session_name": SESSION,
        "source_sha256": SOURCE_SHA256,
        "evidence_snapshot_sha256": evidence_snapshot_hash,
        "bundle_sha256": job["bundle_sha256"],
        "deadline": job["deadline"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
