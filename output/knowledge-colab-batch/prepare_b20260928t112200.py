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
BATCH_ID = "b20260928t112200"
SESSION = "gurumoji-a100-deepknowledge-20260928-112200"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_ID = "LIT-levinson-torreira-2015-timing"
SOURCE_SHA = "bda17c1efd9ad7914fca32e9b444141b2a7c6fc5f55ffc37678b08627205dd96"
SOURCE_URL = "https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2015.00731/full"
PDF_PATH = HERE / "sources" / "b20260928t051400" / "timing-levinson-torreira-2015.pdf"
SOURCE_INPUT = HERE / "inputs" / "b20260928t091530" / "jobs" / "b20260928t091530-01" / "source.json"
SOURCE_RECORD = HERE / "sources-20260928" / f"{BATCH_ID}-LIT-levinson-torreira-selected-sections-source.json"
EVIDENCE_SNAPSHOT = HERE / "sources-20260928" / f"{BATCH_ID}-LIT-levinson-torreira-sections-5-2-1-5-2-2-evidence.txt"
TASKS = [
    {
        "job_id": f"{BATCH_ID}-01",
        "anchor_id": "nxt-switchboard-between-overlap-share-of-floor-transfers-section-5-2-2",
        "start": "Section 5.2.2, findings on between-overlap floor transfer offsets",
        "end": "30.1% of all floor transfers in the analyzed sample",
        "text": (
            "Levinson and Torreira (2015) analyzed 348 NXT-Switchboard conversations with no timing errors "
            "(about 38 hours). In Section 5.2.2, negative floor-transfer offsets, called between-overlaps, "
            "represented 30.1% of all floor transfers. The denominator is all floor transfers, not speech-signal time."
        ),
    },
    {
        "job_id": f"{BATCH_ID}-02",
        "anchor_id": "nxt-switchboard-single-speaker-share-of-speech-signal-section-5-2-2",
        "start": "Section 5.2.1–5.2.2, single-speaker speech after silent-part exclusion",
        "end": "95.3% of the speech signal after excluding silent parts",
        "text": (
            "In the same 348-conversation analysis, after silent parts were excluded, 95.3% of the remaining "
            "speech signal corresponded to speech by one speaker only. The denominator for 95.3% is the speech "
            "signal after excluding silence, not the full recorded signal."
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

    pdf_hash = digest(PDF_PATH.read_bytes())
    if pdf_hash != SOURCE_SHA:
        raise RuntimeError(f"local publisher PDF SHA-256 mismatch: {pdf_hash}")
    source = json.loads(SOURCE_INPUT.read_text(encoding="utf-8"))
    if source["source_id"] != SOURCE_ID or source["sha256"] != SOURCE_SHA:
        raise RuntimeError("source registry does not match the reviewed article record")
    source["adaptation_notice"] = (
        "Paraphrased, narrowly selected summaries of publisher PDF pp. 6–7, Sections 5.2.1–5.2.2. "
        "The excerpts preserve the distinction between the floor-transfer denominator and speech-signal denominator."
    )

    evidence_text = (
        "Levinson, Stephen C.; Torreira, Francisco (2015). Timing in turn-taking and its implications for processing models of language. "
        "Frontiers in Psychology 6:731. DOI: 10.3389/fpsyg.2015.00731. Publisher PDF SHA-256: " + SOURCE_SHA + ".\n"
        "Official article: " + SOURCE_URL + "\n"
        "License: CC BY 4.0; attributed paraphrases only.\n"
        "Selected sections: 5.2.1–5.2.2, publisher PDF pp. 6–7.\n"
        "Evidence paraphrase A: In the analysis of 348 NXT-Switchboard conversations (about 38 hours), between-overlaps (negative FTOs) made up 30.1% of all floor transfers; the denominator is floor transfers.\n"
        "Evidence paraphrase B: After silent parts were excluded from that sample's signal, 95.3% of the remaining speech signal was speech by one speaker only; the denominator excludes silence.\n"
        "This local text is a curated paraphrase, not a verbatim transcription. Its own SHA-256 is separate from the publisher PDF hash.\n"
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
            "--expert-id", "exp-conversation-timing",
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
            "expert_id": "exp-conversation-timing",
            "anchor_id": task["anchor_id"],
            "gpu": "NVIDIA A100-SXM4-80GB",
            "model_reference": MODEL,
            "generation": 1,
            "status": "ready_for_user_started_colab",
        })
        template_path = HERE / "jobs" / "b20260928t091530-01" / "colab_run_job.py"
        template = template_path.read_text(encoding="utf-8")
        template = template.replace("b20260928t091530-01", job_id)
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
        "source_license": "CC-BY-4.0",
        "source_pdf_path": PDF_PATH.relative_to(ROOT).as_posix(),
        "source_pdf_sha256": SOURCE_SHA,
        "evidence_snapshot": {
            "path": EVIDENCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "sha256": evidence_snapshot_sha,
            "scope": "curated paraphrase of selected publisher-PDF material; not the PDF bytes or verbatim transcription",
        },
        "jobs": jobs,
    }
    write_json(manifest_path, manifest)
    run_template = (HERE / "run_b20260928t110000.py").read_text(encoding="utf-8")
    run_template = run_template.replace("b20260928t110000.json", f"{BATCH_ID}.json")
    run_template = run_template.replace("gurumoji-a100-deepknowledge-20260928-110000", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(run_template, encoding="utf-8")
    print(json.dumps({
        "batch_id": BATCH_ID,
        "session_name": SESSION,
        "source_pdf_sha256": SOURCE_SHA,
        "evidence_snapshot_sha256": evidence_snapshot_sha,
        "jobs": [{
            "job_id": job["job_id"],
            "anchor_id": job["anchor_id"],
            "bundle_path": job["bundle_path"],
            "bundle_sha256": job["bundle_sha256"],
            "excerpt_sha256": job["excerpt_sha256"],
            "deadline": job["deadline"],
        } for job in jobs],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
