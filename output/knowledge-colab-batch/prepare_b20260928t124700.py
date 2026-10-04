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
BATCH_ID = "b20260928t124700"
SESSION = "gurumoji-a100-deepknowledge-20260928-124700"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_ID = "LIT-shimizu-2023-scat-application"
SOURCE_SHA = "b7d8fe5964a2de5d8a6c5c858d41468baff10bd8e0d40ce5245add6656266612"
SOURCE_URL = "https://www.mdpi.com/2673-9259/3/1/2"
SOURCE_REGISTRY = (
    HERE / "jobs" / "b20260928t061000-05" /
    "Gurumoji_Job_b20260928t061000-05_g1.local-approved-sources.json"
)
SOURCE_RECORD = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-source.json"
EVIDENCE_SNAPSHOT = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-selected-evidence.txt"
TASKS = [
    {
        "job_id": f"{BATCH_ID}-01",
        "expert_id": "exp-scat",
        "anchor_id": "scat-six-step-study-implementation",
        "start": "The analysis involves the following steps (see Supplementary Materials)",
        "end": "Theory-writing: posit a theory based on the conceptualization",
        "text": (
            "Shimizu et al. separately describe SCAT's general four-step coding process and the six steps "
            "used in this study: entering text in the SCAT form; grouping individual data strips by similarity; "
            "rewording each group; conceptualizing potential themes from relationships between groups; writing "
            "a storyline incorporating all data; and writing a theory from the conceptualization. Treat this as "
            "the study's reported implementation, not a replacement for the general SCAT description."
        ),
    },
    {
        "job_id": f"{BATCH_ID}-02",
        "expert_id": "exp-scat",
        "anchor_id": "scat-analysis-supervision-by-experienced-researcher",
        "start": "The data analysis process was supervised by a researcher",
        "end": "well-versed in SCAT analysis",
        "text": (
            "In Shimizu et al.'s study, the data analysis process was supervised by a researcher experienced "
            "in SCAT. This is a reported arrangement in that study, not a universal SCAT requirement."
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
    registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    matches = [source for source in registry["sources"] if source.get("source_id") == SOURCE_ID]
    if len(matches) != 1:
        raise RuntimeError("approved Shimizu Source registry mismatch")
    source = matches[0]
    if source["sha256"] != SOURCE_SHA or source["locator"]["value"] != "10.3390/jal3010002":
        raise RuntimeError("approved Shimizu Source hash or DOI mismatch")
    if "colab" not in source["rights"]["allowed_routes"] or source["rights"]["classification"] != "licensed":
        raise RuntimeError("Colab processing is not allowed by the Source registry")
    source["adaptation_notice"] = (
        "Selected Methods findings paraphrased from the CC BY 4.0 MDPI article. No interview transcripts, "
        "personal data, or verbatim article passages are included."
    )

    evidence_text = (
        "Shimizu, N., et al. (2023). Qualitative Study on Important Elements of Life for Japanese and Thai Older Adults. "
        "Journal of Ageing and Longevity, 3(1), 11–32.\n"
        f"Publisher article: {SOURCE_URL}\n"
        f"Document SHA-256: {SOURCE_SHA}. License: CC BY 4.0; attributed paraphrases only.\n"
        "Evidence paraphrase A: the article distinguishes its general four-step SCAT coding description from the "
        "six-step workflow reported for this study: SCAT form entry, grouping individual data strips by similarity, "
        "rewording groups, conceptualizing themes from group relationships, writing a storyline with all data, and "
        "writing a theory from the conceptualization.\n"
        "Evidence paraphrase B: the authors report that a researcher experienced in SCAT supervised this study's analysis.\n"
        "This local evidence text is a curated paraphrase, not a verbatim transcription; its hash is separate "
        "from the publisher PDF hash.\n"
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
            "expert_id": task["expert_id"],
            "anchor_id": task["anchor_id"],
            "gpu": "NVIDIA A100",
            "model_reference": MODEL,
            "generation": 1,
            "status": "ready_for_user_started_colab",
        })
        template = (HERE / "jobs" / "b20260928t120000-01" / "colab_run_job.py").read_text(encoding="utf-8")
        template = template.replace("b20260928t120000-01", job_id)
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
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "source_license": "CC-BY-4.0",
        "source_document_sha256": SOURCE_SHA,
        "evidence_snapshot": {
            "path": EVIDENCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "sha256": evidence_snapshot_sha,
            "scope": "curated paraphrase; not a verbatim transcription",
        },
        "jobs": jobs,
    }
    write_json(manifest_path, manifest)
    run_template = (HERE / "run_b20260928t122300.py").read_text(encoding="utf-8")
    run_template = run_template.replace("b20260928t122300.json", f"{BATCH_ID}.json")
    run_template = run_template.replace("gurumoji-a100-deepknowledge-20260928-122300", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(run_template, encoding="utf-8")
    print(json.dumps({
        "batch_id": BATCH_ID,
        "session_name": SESSION,
        "source_document_sha256": SOURCE_SHA,
        "evidence_snapshot_sha256": evidence_snapshot_sha,
        "jobs": [{
            "job_id": job["job_id"], "expert_id": job["expert_id"], "anchor_id": job["anchor_id"],
            "bundle_path": job["bundle_path"], "bundle_sha256": job["bundle_sha256"],
            "excerpt_sha256": job["excerpt_sha256"], "deadline": job["deadline"],
        } for job in jobs],
    }, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
