"""Prepare one bounded GiNZA v5.2.0 component-role claim job."""
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
BATCH_ID = "b20260928t155500"
JOB_ID = f"{BATCH_ID}-01"
SESSION = "gurumoji-a100-ginza-v520-20260928-155500"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_ID = "RES-ginza-official"
SOURCE_URL = "https://raw.githubusercontent.com/megagonlabs/ginza/v5.2.0/README.md"
SOURCE_RECORD = HERE / "inputs" / "b20260928t025516" / SOURCE_ID / "source.json"
ANCHOR_ID = "ginza-framework-components"
TEXT = (
    "The official GiNZA v5.2.0 README identifies spaCy as GiNZA's key framework. It says SudachiPy provides "
    "tokenization and part-of-speech tagging. It separately states that the Transformer-based model ja_ginza_electra "
    "uses Hugging Face Transformers as the framework for pretrained models. These are the README's descriptions of "
    "component roles; they do not report measured accuracy or transcript-specific performance. (License section.)"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    source = json.loads(SOURCE_RECORD.read_text(encoding="utf-8"))
    if source.get("source_id") != SOURCE_ID or source.get("version") != "github-v5.2.0-readme-retrieved-2026-09-28-sha256-71652a6e50e94ee7":
        raise RuntimeError("unexpected GiNZA Source version")
    if source.get("license", {}).get("license_id") != "MIT" or "colab" not in source.get("rights", {}).get("allowed_routes", []):
        raise RuntimeError("GiNZA README is not approved for Colab processing")
    text_hash = sha256(TEXT.encode("utf-8"))
    source["anchors"].append({
        "anchor_id": ANCHOR_ID,
        "kind": "section",
        "start": "License: spaCy and SudachiPy component roles",
        "end": "Hugging Face Transformers framework for ja_ginza_electra",
        "extracted_text_sha256": text_hash,
    })
    source["adaptation_notice"] = (
        "A short paraphrase from the versioned README License section is used for draft Claim generation. "
        "Outputs must retain the README's component boundaries and make no performance claim."
    )

    input_dir = HERE / "inputs" / BATCH_ID / "jobs" / JOB_ID
    job_dir = HERE / "jobs" / JOB_ID
    if input_dir.exists() or job_dir.exists():
        raise FileExistsError(f"batch paths already exist for {JOB_ID}")
    input_dir.mkdir(parents=True)
    job_dir.mkdir(parents=True)
    excerpt = {
        "source_id": SOURCE_ID,
        "source_version": source["version"],
        "source_sha256": source["sha256"],
        "anchor_id": ANCHOR_ID,
        "extracted_text_sha256": text_hash,
        "text": TEXT,
    }
    write_json(input_dir / "source.json", source)
    write_json(input_dir / "approved_sources.json", {"schema_version": 1, "sources": [source]})
    write_json(input_dir / "excerpt.json", excerpt)

    bundle = job_dir / f"Gurumoji_Job_{JOB_ID}_g1.zip"
    command = [
        sys.executable, str(ROOT / "scripts" / "prepare_colab_claim_job.py"),
        "--data-dir", str(HERE / "state"),
        "--expert-id", "exp-japanese-text-preprocessing",
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
        "source_sha256": source["sha256"],
        "excerpt_sha256": text_hash,
        "expert_id": "exp-japanese-text-preprocessing",
        "anchor_id": ANCHOR_ID,
        "gpu": "NVIDIA A100-SXM4-80GB High-RAM",
        "model_reference": MODEL,
        "generation": 1,
        "status": "ready_for_user_started_colab",
    })

    template = (HERE / "jobs" / "b20260928t150300-01" / "colab_run_job.py").read_text(encoding="utf-8")
    template = template.replace("b20260928t150300-01", JOB_ID)
    template = re.sub(r'EXPECTED_BUNDLE_SHA256 = "[0-9a-f]{64}"',
                      f'EXPECTED_BUNDLE_SHA256 = "{job["bundle_sha256"]}"', template)
    (job_dir / "colab_run_job.py").write_text(template, encoding="utf-8")

    manifest = {
        "batch_id": BATCH_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gpu": "NVIDIA A100-SXM4-80GB High-RAM",
        "model_reference": MODEL,
        "session_name": SESSION,
        "status": "ready_for_user_started_colab",
        "total_jobs": 1,
        "expert_id": "exp-japanese-text-preprocessing",
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "source_license": "MIT",
        "source_document_sha256": source["sha256"],
        "evidence_snapshot": {
            "path": f"output/knowledge-colab-batch/sources-20260928/{BATCH_ID}-ginza-components.txt",
            "sha256": text_hash,
            "scope": "short paraphrase of the versioned README component roles",
        },
        "jobs": [job],
    }
    (ROOT / manifest["evidence_snapshot"]["path"]).write_text(TEXT + "\n", encoding="utf-8")
    write_json(HERE / f"{BATCH_ID}.json", manifest)

    runner = (HERE / "run_b20260928t150300.py").read_text(encoding="utf-8")
    runner = runner.replace("b20260928t150300.json", f"{BATCH_ID}.json")
    runner = runner.replace("gurumoji-a100-thematic-20260928-150300", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(runner, encoding="utf-8")
    print(json.dumps({
        "batch_id": BATCH_ID,
        "session_name": SESSION,
        "source_sha256": source["sha256"],
        "excerpt_sha256": text_hash,
        "bundle_sha256": job["bundle_sha256"],
        "deadline": job["deadline"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
