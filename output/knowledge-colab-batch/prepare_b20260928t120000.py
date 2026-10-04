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
BATCH_ID = "b20260928t120000"
SESSION = "gurumoji-a100-deepknowledge-20260928-120000"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_ID = "LIT-zhang-2021-cross-corpus-ser"
SOURCE_SHA = "2f3b80d1cd0247d0b36e99cbdff14c5f14ee680a08b35ada4a46c4a43c7b9d81"
SOURCE_URL = "https://doi.org/10.3389/fnbot.2021.784514"
SOURCE_INPUT = HERE / "inputs" / "b20260928t070100" / "jobs" / "b20260928t070100-06" / "source.json"
SOURCE_RECORD = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-source.json"
EVIDENCE_SNAPSHOT = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-selected-evidence.txt"
TASKS = [
    {
        "job_id": f"{BATCH_ID}-01",
        "expert_id": "exp-speech-emotion-recognition",
        "anchor_id": "ser-cross-corpus-mismatch-generalization",
        "start": "Cross-corpus variation between training and test speech corpora",
        "end": "Language, culture, distribution mode, or data scale can impede generalization",
        "text": (
            "Zhang et al.'s review explains that training and test speech corpora in cross-corpus "
            "speech emotion recognition may differ in language, culture, distribution mode, or data "
            "scale. Such cross-corpus differences can create idiosyncratic variation that impedes "
            "the generalization of current SER techniques."
        ),
    },
    {
        "job_id": f"{BATCH_ID}-02",
        "expert_id": "exp-speech-emotion-recognition",
        "anchor_id": "ser-basic-cross-corpus-system-components",
        "start": "Two crucial steps in a basic cross-corpus SER system",
        "end": "Emotion classifier and domain-invariant feature extraction",
        "text": (
            "The review describes two crucial steps in a basic cross-corpus speech emotion "
            "recognition system: an emotion classifier and domain-invariant feature extraction."
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
    if (source["source_id"] != SOURCE_ID or source["sha256"] != SOURCE_SHA
            or source["locator"]["value"] != "10.3389/fnbot.2021.784514"):
        raise RuntimeError("approved Frontiers Source registry mismatch")
    if "colab" not in source["rights"]["allowed_routes"]:
        raise RuntimeError("Colab processing is not allowed by the Source registry")
    if source["rights"]["classification"] != "licensed":
        raise RuntimeError("Source is not classified as licensed")
    source["adaptation_notice"] = (
        "Selected page-2 claims paraphrased from the open-access Frontiers review; no article wording, "
        "speech recordings, or personal data are included in the Colab excerpts."
    )

    evidence_text = (
        "Zhang, S., Liu, R., Tao, X., & Zhao, X. (2021). Deep Cross-Corpus Speech Emotion Recognition: "
        "Recent Advances and Perspectives. Frontiers in Neurorobotics, 15, 784514.\n"
        "Publisher article: https://www.frontiersin.org/journals/neurorobotics/articles/10.3389/fnbot.2021.784514/full\n"
        f"Document SHA-256: {SOURCE_SHA}. License: CC BY 4.0; attributed paraphrases only.\n"
        "Evidence paraphrase A: training and test speech corpora may differ in language, culture, "
        "distribution mode, or data scale; these differences can impede generalization.\n"
        "Evidence paraphrase B: the review describes a basic cross-corpus SER system as using an "
        "emotion classifier and domain-invariant feature extraction.\n"
        "This is a curated paraphrase, not a verbatim transcription; its hash is separate from the source PDF hash.\n"
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
            "gpu": "NVIDIA A100-SXM4-40GB",
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
        "gpu": "NVIDIA A100-SXM4-40GB",
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
