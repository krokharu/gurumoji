"""Prepare two corrected, hash-bound Byrne claims for A100 review."""
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
BATCH_ID = "b20260928t154000"
SESSION = "gurumoji-a100-tarevision-20260928-154000"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_RECORD = HERE / "inputs" / "b20260928t150300" / "jobs" / "b20260928t150300-01" / "source.json"
SOURCE_ID = "LIT-byrne-2022-reflexive-ta"
SOURCE_URL = "https://link.springer.com/article/10.1007/s11135-021-01182-y"

TASKS = [
    {
        "job_id": f"{BATCH_ID}-01",
        "anchor_id": "ta-byrne-study-context-and-assumptions",
        "text": (
            "Author attribution: the author is David Byrne (2022); the surname is Byrne. The worked example comes "
            "from the qualitative phase of a mixed-methods study of Irish post-primary educators' attitudes toward "
            "promoting student social and emotional wellbeing. It used 11 semi-structured interviews lasting about "
            "25–30 minutes, with core-curriculum teachers, wellbeing-curriculum teachers, pastoral-care members, "
            "and senior managers. These figures describe this one study, not a recommended sample size for reflexive "
            "thematic analysis. Byrne situates the example in interpretivism and constructivism and discusses the "
            "researcher's position across four continua: essentialist–constructionist epistemology, experiential–critical "
            "orientation, inductive–deductive analysis, and semantic–latent coding, in relation to the research question. "
            "(Publisher PDF pp. 1394–1397.)"
        ),
    },
    {
        "job_id": f"{BATCH_ID}-02",
        "anchor_id": "ta-byrne-code-iteration-tracking",
        "text": (
            "Byrne describes coding as iterative: as a researcher becomes more familiar with the dataset through "
            "repeated engagement, interpretations may change. Here familiarity means becoming familiar with the data; "
            "the passage does not claim that the researcher's skill or competence increases. Researchers should document "
            "coding iterations so changes to codes and prospective themes remain transparent and earlier analytic paths "
            "can be revisited. In the worked example, a spreadsheet placed data items in rows and successive coding "
            "iterations in columns; original transcripts were consulted again as familiarity with the data grew. The "
            "author revised, merged, generalized, or discarded codes when later interpretation showed an earlier label "
            "was too vague, too specific, or less useful. This spreadsheet is an example of an audit aid, not a required "
            "software or data structure. (Publisher PDF pp. 1400–1402.)"
        ),
    },
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    source_base = json.loads(SOURCE_RECORD.read_text(encoding="utf-8"))
    if source_base.get("source_id") != SOURCE_ID or source_base.get("sha256") != "fbe98aa82d7caea73f1bad2785eabe70c88c58a6f4b4037d8cb1d331f3abab3c":
        raise RuntimeError("Byrne full-text Source record mismatch")
    if source_base.get("license", {}).get("license_id") != "CC-BY-4.0" or "colab" not in source_base.get("rights", {}).get("allowed_routes", []):
        raise RuntimeError("Byrne Source is not approved for Colab processing")

    jobs = []
    for task in TASKS:
        excerpt_hash = sha256(task["text"].encode("utf-8"))
        source = json.loads(json.dumps(source_base))
        anchor = next(item for item in source["anchors"] if item["anchor_id"] == task["anchor_id"])
        anchor["extracted_text_sha256"] = excerpt_hash
        source["adaptation_notice"] = (
            "Two short, source-linked paraphrase excerpts from the verified full article are used for corrected draft "
            "Claim generation. The paraphrases clarify author attribution and the meaning of familiarity with data; "
            "model outputs must remain source-scoped. No standalone article text is exported."
        )

        input_dir = HERE / "inputs" / BATCH_ID / "jobs" / task["job_id"]
        job_dir = HERE / "jobs" / task["job_id"]
        if input_dir.exists() or job_dir.exists():
            raise FileExistsError(f"batch paths already exist for {task['job_id']}")
        input_dir.mkdir(parents=True)
        job_dir.mkdir(parents=True)
        excerpt = {
            "source_id": SOURCE_ID,
            "source_version": source["version"],
            "source_sha256": source["sha256"],
            "anchor_id": task["anchor_id"],
            "extracted_text_sha256": excerpt_hash,
            "text": task["text"],
        }
        write_json(input_dir / "source.json", source)
        write_json(input_dir / "approved_sources.json", {"schema_version": 1, "sources": [source]})
        write_json(input_dir / "excerpt.json", excerpt)

        bundle = job_dir / f"Gurumoji_Job_{task['job_id']}_g1.zip"
        command = [
            sys.executable, str(ROOT / "scripts" / "prepare_colab_claim_job.py"),
            "--data-dir", str(HERE / "state"),
            "--expert-id", "exp-thematic-analysis",
            "--source-json", str(input_dir / "source.json"),
            "--excerpt-json", str(input_dir / "excerpt.json"),
            "--approved-sources-json", str(input_dir / "approved_sources.json"),
            "--output", str(bundle), "--job-id", task["job_id"], "--ttl-minutes", "55",
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        if result.returncode:
            raise RuntimeError(f"{task['job_id']} preparation failed: {result.stdout}\n{result.stderr}")
        prepared = json.loads(result.stdout)
        prepared.update({
            "batch_id": BATCH_ID,
            "bundle_path": bundle.relative_to(ROOT).as_posix(),
            "source_id": SOURCE_ID,
            "source_record_path": (input_dir / "source.json").relative_to(ROOT).as_posix(),
            "approved_sources_path": (input_dir / "approved_sources.json").relative_to(ROOT).as_posix(),
            "excerpt_path": (input_dir / "excerpt.json").relative_to(ROOT).as_posix(),
            "source_sha256": source["sha256"],
            "excerpt_sha256": excerpt_hash,
            "expert_id": "exp-thematic-analysis",
            "anchor_id": task["anchor_id"],
            "gpu": "NVIDIA A100-SXM4-80GB High-RAM",
            "model_reference": MODEL,
            "generation": 1,
            "status": "ready_for_user_started_colab",
        })

        template = (HERE / "jobs" / "b20260928t150300-03" / "colab_run_job.py").read_text(encoding="utf-8")
        template = template.replace("b20260928t150300-03", task["job_id"])
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
        "gpu": "NVIDIA A100-SXM4-80GB High-RAM",
        "model_reference": MODEL,
        "session_name": SESSION,
        "status": "ready_for_user_started_colab",
        "total_jobs": len(jobs),
        "expert_id": "exp-thematic-analysis",
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "source_license": "CC-BY-4.0",
        "source_document_sha256": source_base["sha256"],
        "evidence_snapshot": {
            "path": f"output/knowledge-colab-batch/sources-20260928/{BATCH_ID}-corrected-evidence.txt",
            "sha256": sha256("\n\n".join(task["text"] for task in TASKS).encode("utf-8")),
            "scope": "two short source-linked paraphrases correcting the author attribution and data-familiarity interpretation",
        },
        "jobs": jobs,
    }
    snapshot = ROOT / manifest["evidence_snapshot"]["path"]
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("\n\n".join(task["text"] for task in TASKS) + "\n", encoding="utf-8")
    manifest_path = HERE / f"{BATCH_ID}.json"
    write_json(manifest_path, manifest)

    runner = (HERE / "run_b20260928t150300.py").read_text(encoding="utf-8")
    runner = runner.replace("b20260928t150300.json", f"{BATCH_ID}.json")
    runner = runner.replace("gurumoji-a100-thematic-20260928-150300", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(runner, encoding="utf-8")
    print(json.dumps({
        "batch_id": BATCH_ID,
        "session_name": SESSION,
        "source_sha256": source_base["sha256"],
        "evidence_snapshot_sha256": manifest["evidence_snapshot"]["sha256"],
        "jobs": [{key: job[key] for key in ("job_id", "anchor_id", "bundle_sha256", "excerpt_sha256", "deadline")} for job in jobs],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
