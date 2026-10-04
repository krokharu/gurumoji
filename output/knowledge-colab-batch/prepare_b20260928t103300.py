"""Prepare the FreeTxt §2.2 text-extract A100 claim job."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t103300"
SESSION = "gurumoji-a100-deepknowledge-20260928-103300"
JOB_ID = f"{BATCH_ID}-01"
DATA_DIR = HERE / "state"
INPUT_DIR = HERE / "inputs" / BATCH_ID / "jobs" / JOB_ID
JOB_DIR = HERE / "jobs" / JOB_ID
SOURCE_SNAPSHOT = HERE / "sources-20260928" / f"{JOB_ID}-freetxt-section-2-2-text-extract.txt"
PDF_URL = "https://cronfa.swan.ac.uk/Record/cronfa70086/Download/70086__34939__f82a24c8c3ea49aaad5c813e2a7643c7.pdf"
PDF_TEXT_CAPTURE = """Knight, Dawn; Khallaf, Nouran; Rayson, Paul; El-Haj, Mahmoud; Ezeani, Ignatius; Morris, Steve (2024).
FreeTxt: A corpus-based bilingual free-text survey and questionnaire data analysis toolkit.
Applied Corpus Linguistics 4(3), 100103. DOI: 10.1016/j.acorp.2024.100103.
Version-of-record PDF, Section 2.2 “Core functionalities”, PDF pages 3–4.
Public university repository browser text extraction captured 2026-09-28.
This retained text extract is not the PDF binary; its SHA-256 identifies this exact local text snapshot only.
License: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
Attribution: Knight et al. (2024), DOI above. Text extraction line breaks and hyphenation normalized.

Section 2.2 states that core functionalities were identified for FreeTxt to provisionally include. Its feature list frames the following as functions the toolkit could potentially perform, based on existing corpus-linguistic and NLP tools:
- Word and n-gram frequency: basic counts of words, n-grams, part-of-speech tags, and semantic tags in a dataset.
- Keyword in context (KWIC): lexical searches that return all instances of a search term with its immediate co-text.
- Text visualisation: pictorial representations of word distributions, proposed for implementation using available Python text and visualisation libraries.
"""

EXCERPT_TEXT = (
    "Knight et al. describe FreeTxt's proposed core functionalities as potential features, not as "
    "confirmed implementation or validation: basic dataset counts of words, n-grams, part-of-speech "
    "tags and semantic tags; KWIC searches listing a search term's occurrences with nearby co-text; "
    "and visual displays of word distributions. This scope is from the article's Section 2.2 design "
    "description."
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    for path in (HERE / f"{BATCH_ID}.json", JOB_DIR, INPUT_DIR):
        if path.exists():
            raise FileExistsError(str(path))
    snapshot_bytes = PDF_TEXT_CAPTURE.encode("utf-8")
    SOURCE_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_SNAPSHOT.write_bytes(snapshot_bytes)
    source_hash = digest(snapshot_bytes)
    excerpt_hash = digest(EXCERPT_TEXT.encode("utf-8"))
    anchor_id = "freetxt-proposed-core-functions-section-2-2"
    source = {
        "schema_version": 1,
        "source_id": "LIT-knight-2024-freetxt",
        "version": f"repository-vor-section-2.2-text-extract-2026-09-28-sha256-{source_hash[:16]}",
        "sha256": source_hash,
        "title": "FreeTxt: A corpus-based bilingual free-text survey and questionnaire data analysis toolkit",
        "authors": ["Dawn Knight", "Nouran Khallaf", "Paul Rayson", "Mahmoud El-Haj", "Ignatius Ezeani", "Steve Morris"],
        "publication_year": 2024,
        "source_type": "paper",
        "locator": {"kind": "url", "value": PDF_URL},
        "access_scope": "full_text",
        "license": {"license_id": "CC-BY-4.0", "terms": "CC BY 4.0; attribution and change indication required"},
        "license_url": {"kind": "https", "value": "https://creativecommons.org/licenses/by/4.0/"},
        "anchors": [{
            "anchor_id": anchor_id,
            "kind": "section",
            "start": "Section 2.2 Core functionalities, PDF page 3",
            "end": "Section 2.2 proposed feature list, PDF pages 3–4",
            "extracted_text_sha256": excerpt_hash,
        }],
        "rights": {"classification": "licensed", "allowed_routes": ["local", "colab", "export"]},
        "adaptation_notice": (
            "The retained local Source version is a browser-extracted text snapshot of selected "
            "Version-of-Record PDF content, not the PDF binary; its SHA-256 pins this text snapshot. "
            "The Colab excerpt is a paraphrase. Attribution to Knight et al. (2024) is retained."
        ),
    }
    excerpt = {
        "source_id": source["source_id"],
        "source_version": source["version"],
        "source_sha256": source_hash,
        "anchor_id": anchor_id,
        "extracted_text_sha256": excerpt_hash,
        "text": EXCERPT_TEXT,
    }
    INPUT_DIR.mkdir(parents=True)
    write_json(INPUT_DIR / "source.json", source)
    write_json(INPUT_DIR / "approved_sources.json", {"schema_version": 1, "sources": [source]})
    write_json(INPUT_DIR / "excerpt.json", excerpt)
    bundle = JOB_DIR / f"Gurumoji_Job_{JOB_ID}_g1.zip"
    JOB_DIR.mkdir(parents=True)
    command = [
        sys.executable, str(ROOT / "scripts" / "prepare_colab_claim_job.py"),
        "--data-dir", str(DATA_DIR),
        "--expert-id", "exp-quantitative-text-analysis",
        "--source-json", str(INPUT_DIR / "source.json"),
        "--excerpt-json", str(INPUT_DIR / "excerpt.json"),
        "--approved-sources-json", str(INPUT_DIR / "approved_sources.json"),
        "--output", str(bundle),
        "--job-id", JOB_ID,
        "--ttl-minutes", "55",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    if result.returncode:
        raise RuntimeError(f"prepare_colab_claim_job failed: {result.stdout} {result.stderr}")
    prepared = json.loads(result.stdout)
    prepared.update({
        "batch_id": BATCH_ID,
        "bundle_path": bundle.relative_to(ROOT).as_posix(),
        "source_id": source["source_id"],
        "source_record_path": (INPUT_DIR / "source.json").relative_to(ROOT).as_posix(),
        "excerpt_path": (INPUT_DIR / "excerpt.json").relative_to(ROOT).as_posix(),
        "source_snapshot_path": SOURCE_SNAPSHOT.relative_to(ROOT).as_posix(),
        "source_sha256": source_hash,
        "excerpt_sha256": excerpt_hash,
        "expert_id": "exp-quantitative-text-analysis",
        "anchor_id": anchor_id,
        "gpu": "NVIDIA A100-SXM4-80GB",
        "model_reference": "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8",
        "generation": 1,
        "status": "ready_for_user_started_colab",
    })
    runner = (HERE / "jobs" / "b20260928t061000-01" / "colab_run_job.py").read_text(encoding="utf-8")
    runner = runner.replace("b20260928t061000-01", JOB_ID)
    runner = runner.replace("5a1d56a4cdb1e016f6fa7bad40738199e5150ac94b56caad89b1dddecc646080",
                            prepared["bundle_sha256"])
    (JOB_DIR / "colab_run_job.py").write_text(runner, encoding="utf-8")
    manifest = {
        "batch_id": BATCH_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gpu": "NVIDIA A100-SXM4-80GB",
        "model_reference": "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8",
        "session_name": SESSION,
        "status": "ready_for_user_started_colab",
        "total_jobs": 1,
        "source_snapshot": {
            "path": SOURCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "sha256": source_hash,
            "note": "SHA-256 pins the retained browser text extraction, not original PDF bytes.",
        },
        "jobs": [prepared],
    }
    write_json(HERE / f"{BATCH_ID}.json", manifest)
    run_template = (HERE / "run_b20260928t094700.py").read_text(encoding="utf-8")
    run_template = run_template.replace("b20260928t094700.json", f"{BATCH_ID}.json")
    run_template = run_template.replace("gurumoji-a100-deepknowledge-20260928-094700", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(run_template, encoding="utf-8")
    print(json.dumps({
        "batch_id": BATCH_ID,
        "job_id": JOB_ID,
        "bundle_path": prepared["bundle_path"],
        "bundle_sha256": prepared["bundle_sha256"],
        "source_sha256": source_hash,
        "source_snapshot_sha256_scope": "retained browser text extraction only; not original PDF bytes",
        "excerpt_sha256": excerpt_hash,
        "deadline": prepared["deadline"],
        "session_name": SESSION,
        "manifest": (HERE / f"{BATCH_ID}.json").relative_to(ROOT).as_posix(),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()