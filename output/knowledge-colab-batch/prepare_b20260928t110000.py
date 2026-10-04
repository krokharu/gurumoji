"""Prepare two FreeTxt evidence jobs for the A100."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t110000"
SESSION = "gurumoji-a100-deepknowledge-20260928-110000"
PDF_URL = "https://cronfa.swan.ac.uk/Record/cronfa70086/Download/70086__34939__f82a24c8c3ea49aaad5c813e2a7643c7.pdf"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SNAPSHOT = HERE / "sources-20260928" / f"{BATCH_ID}-LIT-knight-2024-freetxt-sections-3-2-3-4-4-evidence.txt"

SNAPSHOT_TEXT = """Knight, Dawn; Khallaf, Nouran; Rayson, Paul; El-Haj, Mahmoud; Ezeani, Ignatius; Morris, Steve (2024).
FreeTxt: A corpus-based bilingual free-text survey and questionnaire data analysis toolkit.
Applied Corpus Linguistics 4(3), 100103. DOI: 10.1016/j.acorp.2024.100103.
Version of Record PDF, selected Sections 3.2, 3.4, and 4.
Source reviewed from the university repository's browser-rendered PDF text on 2026-09-28.
This retained evidence-text snapshot is a curated paraphrase, not a verbatim transcription and not the PDF binary. Its SHA-256 pins only this local snapshot.
License: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
Attribution: Knight et al. (2024), DOI above.

Evidence note for Section 3.2 (sentiment pipeline):
The paper describes FreeTxt's pipeline as using a multilingual BERT sentiment model. It reports the model page's English-text accuracy as about 95%; the authors' own experiments on manually annotated Welsh reviews found about 73%, which they say leaves room for improvement.

Evidence note for Sections 3.4 and 4 (summarisation and release limitations):
The paper describes the summariser as extractive. Project partners tested it on policy and other institutional documents, and the authors report that it proved more useful for long-form documents than for survey/feedback data, listing this as a shortcoming of the current release.
"""

EXCERPTS = [
    {
        "expert_id": "exp-quantitative-text-analysis",
        "anchor_id": "freetxt-sentiment-accuracy-english-welsh-section-3-2",
        "start": "Section 3.2, sentiment-analysis pipeline",
        "end": "English model-page estimate and manually annotated Welsh-review experiment",
        "text": (
            "In the article's description of FreeTxt's sentiment pipeline, the selected multilingual "
            "BERT model's page is cited as reporting about 95% accuracy on English text; the authors' "
            "experiments on manually annotated Welsh reviews found about 73%, which they identify as "
            "leaving room for improvement. These are distinct evidence bases, and the Welsh estimate "
            "is specific to their experiment."
        ),
    },
    {
        "expert_id": "exp-quantitative-text-analysis",
        "anchor_id": "freetxt-summariser-long-form-limitation-sections-3-4-4",
        "start": "Section 3.4, extractive summarisation",
        "end": "Section 4, current-release shortcoming from partner feedback",
        "text": (
            "Knight et al. report that FreeTxt's partners found its extractive summariser more useful "
            "for long-form documents than for survey or feedback data, and list this as a shortcoming "
            "of the current version. This is the authors' report about their partners and the described "
            "release."
        ),
    },
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    if (HERE / f"{BATCH_ID}.json").exists():
        raise FileExistsError(BATCH_ID)
    snapshot_bytes = SNAPSHOT_TEXT.encode("utf-8")
    SNAPSHOT.write_bytes(snapshot_bytes)
    source_sha = sha(snapshot_bytes)
    anchors = []
    for task in EXCERPTS:
        task["excerpt_sha256"] = sha(task["text"].encode("utf-8"))
        anchors.append({
            "anchor_id": task["anchor_id"],
            "kind": "section",
            "start": task["start"],
            "end": task["end"],
            "extracted_text_sha256": task["excerpt_sha256"],
        })
    source = {
        "schema_version": 1,
        "source_id": "LIT-knight-2024-freetxt",
        "version": f"repository-vor-sections-3.2-3.4-4-evidence-snapshot-2026-09-28-sha256-{source_sha[:16]}",
        "sha256": source_sha,
        "title": "FreeTxt: A corpus-based bilingual free-text survey and questionnaire data analysis toolkit",
        "authors": ["Dawn Knight", "Nouran Khallaf", "Paul Rayson", "Mahmoud El-Haj", "Ignatius Ezeani", "Steve Morris"],
        "publication_year": 2024,
        "source_type": "paper",
        "locator": {"kind": "url", "value": PDF_URL},
        "access_scope": "full_text",
        "license": {"license_id": "CC-BY-4.0", "terms": "CC BY 4.0; attribution and change indication required"},
        "license_url": {"kind": "https", "value": "https://creativecommons.org/licenses/by/4.0/"},
        "anchors": anchors,
        "rights": {"classification": "licensed", "allowed_routes": ["local", "colab", "export"]},
        "adaptation_notice": (
            "The retained Source version is a curated evidence-text snapshot paraphrasing selected "
            "browser-rendered Version-of-Record PDF sections; it is not a verbatim transcription or "
            "the PDF binary. Its SHA-256 pins this local snapshot only. The Colab excerpts are "
            "paraphrases with attribution to Knight et al. (2024)."
        ),
    }
    jobs = []
    for index, task in enumerate(EXCERPTS, 1):
        job_id = f"{BATCH_ID}-{index:02d}"
        input_dir = HERE / "inputs" / BATCH_ID / "jobs" / job_id
        job_dir = HERE / "jobs" / job_id
        if input_dir.exists() or job_dir.exists():
            raise FileExistsError(job_id)
        input_dir.mkdir(parents=True)
        job_dir.mkdir(parents=True)
        excerpt = {
            "source_id": source["source_id"],
            "source_version": source["version"],
            "source_sha256": source_sha,
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
            "--expert-id", task["expert_id"],
            "--source-json", str(input_dir / "source.json"),
            "--excerpt-json", str(input_dir / "excerpt.json"),
            "--approved-sources-json", str(input_dir / "approved_sources.json"),
            "--output", str(bundle),
            "--job-id", job_id,
            "--ttl-minutes", "55",
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        if result.returncode:
            raise RuntimeError(f"{job_id}: {result.stdout} {result.stderr}")
        prepared = json.loads(result.stdout)
        prepared.update({
            "batch_id": BATCH_ID,
            "bundle_path": bundle.relative_to(ROOT).as_posix(),
            "source_id": source["source_id"],
            "source_record_path": (input_dir / "source.json").relative_to(ROOT).as_posix(),
            "excerpt_path": (input_dir / "excerpt.json").relative_to(ROOT).as_posix(),
            "source_snapshot_path": SNAPSHOT.relative_to(ROOT).as_posix(),
            "source_sha256": source_sha,
            "excerpt_sha256": task["excerpt_sha256"],
            "expert_id": task["expert_id"],
            "anchor_id": task["anchor_id"],
            "gpu": "NVIDIA A100-SXM4-80GB",
            "model_reference": MODEL,
            "generation": 1,
            "status": "ready_for_user_started_colab",
        })
        runner = (HERE / "jobs" / "b20260928t061000-01" / "colab_run_job.py").read_text(encoding="utf-8")
        runner = runner.replace("b20260928t061000-01", job_id)
        runner = runner.replace("5a1d56a4cdb1e016f6fa7bad40738199e5150ac94b56caad89b1dddecc646080",
                                prepared["bundle_sha256"])
        (job_dir / "colab_run_job.py").write_text(runner, encoding="utf-8")
        jobs.append(prepared)
    manifest = {
        "batch_id": BATCH_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gpu": "NVIDIA A100-SXM4-80GB",
        "model_reference": MODEL,
        "session_name": SESSION,
        "status": "ready_for_user_started_colab",
        "total_jobs": len(jobs),
        "source_snapshot": {
            "path": SNAPSHOT.relative_to(ROOT).as_posix(),
            "sha256": source_sha,
            "note": "SHA-256 pins this curated evidence-text snapshot only, not original PDF bytes.",
        },
        "source_acquisition": {
            "source_url": PDF_URL,
            "method": "Selected sections reviewed from the university repository's browser-rendered Version-of-Record PDF text.",
            "download_limitation": "Direct local PDF downloads returned HTTP 403 in the prior batch.",
            "correction_status": "not_checked in the literature record; candidates remain unapproved.",
        },
        "jobs": jobs,
    }
    write_json(HERE / f"{BATCH_ID}.json", manifest)
    run_script = (HERE / "run_b20260928t094700.py").read_text(encoding="utf-8")
    run_script = run_script.replace("b20260928t094700.json", f"{BATCH_ID}.json")
    run_script = run_script.replace("gurumoji-a100-deepknowledge-20260928-094700", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(run_script, encoding="utf-8")
    print(json.dumps({
        "batch_id": BATCH_ID,
        "session_name": SESSION,
        "jobs": [{
            "job_id": job["job_id"],
            "anchor_id": job["anchor_id"],
            "bundle_path": job["bundle_path"],
            "bundle_sha256": job["bundle_sha256"],
            "excerpt_sha256": job["excerpt_sha256"],
            "deadline": job["deadline"],
        } for job in jobs],
        "source_sha256": source_sha,
        "source_sha256_scope": "curated evidence-text snapshot only, not original PDF bytes",
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()