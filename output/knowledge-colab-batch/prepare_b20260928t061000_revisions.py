"""Prepare narrowly scoped retries for two candidates that lost qualifiers."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t061000"
DATA_DIR = HERE / "state"
JOBS_DIR = HERE / "jobs"
INPUTS_DIR = HERE / "inputs" / BATCH_ID / "jobs"

TASKS = [
    {
        "job_id": f"{BATCH_ID}-07", "expert_id": "exp-kj-method",
        "source_path": "output/knowledge-colab-batch/inputs/b20260928t042558/LIT-kanzaki-sakai-2025-kj-medrxiv/source-v3-case-scoped.json",
        "source_id": "LIT-kanzaki-sakai-2025-kj-medrxiv", "anchor_id": "kj-card-grouping-case-scope-v2",
        "start": "This study's KJ method steps: theme extraction and card arrangement",
        "end": "This study's six major themes and spatial arrangement",
        "text": "For these reasons, this study adopted the KJ method to analyze the data, and the specific steps of this process are as follows. Theme extraction: (1) All members read the cards five times to determine which are related to the theme. (2) After understanding the contents of each card, they grouped those with similar contents, summarized them, and added an A title. (3) The A-title group was treated as a whole together with the small cards in that group. The number of small cards in a group was not to exceed half of the initial number of cards in that round. Then the small cards with similar contents were regrouped and given a B title. By analogy, groups of B, C, and D titles were formed, ultimately extracting six major themes. For the six themes, physical cards were created and iteratively rearranged on a background sheet until their spatial arrangement reflected logical relationships. Various symbols were used to annotate connections among themes.",
        "kind": "paragraph",
    },
    {
        "job_id": f"{BATCH_ID}-08", "expert_id": "exp-speech-emotion-recognition",
        "source_path": "output/knowledge-colab-batch/inputs/b20260928t042558/LIT-zhang-2021-cross-corpus-ser/source-v1.json",
        "source_id": "LIT-zhang-2021-cross-corpus-ser", "anchor_id": "ser-majority-single-corpus-qualifier",
        "start": "Cross-corpus SER: majority of existing systems and corpus differences",
        "end": "Training and test corpus differences that can impede generalization",
        "text": "The authors note that the majority of existing speech emotion recognition systems are trained and evaluated on a single corpus and in a single-language setting. They then explain that in practical applications training and testing corpora can differ in language, culture, distribution mode, data scale, and other respects. These cross-corpus differences can result in idiosyncratic variations that impede generalization of current speech emotion recognition techniques.",
        "kind": "paragraph",
    },
]


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def main() -> None:
    manifest_path = HERE / f"{BATCH_ID}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runner_template = (JOBS_DIR / f"{BATCH_ID}-01" / "colab_run_job.py").read_text(encoding="utf-8")
    existing_ids = {job["job_id"] for job in manifest["jobs"]}
    holds = {
        f"{BATCH_ID}-04": "Candidate omits that the grouping rule and workflow are specific to this cited study.",
        f"{BATCH_ID}-06": "Candidate drops the source qualifier that this applies to the majority of systems.",
    }
    for job in manifest["jobs"]:
        if job["job_id"] in holds:
            job["status"] = "hold_for_revision"
            job["review_reason"] = holds[job["job_id"]]
    for task in TASKS:
        job_id = task["job_id"]
        if job_id in existing_ids:
            raise ValueError(f"retry job already exists: {job_id}")
        source = json.loads((ROOT / task["source_path"]).read_text(encoding="utf-8"))
        excerpt_hash = hashlib.sha256(task["text"].encode("utf-8")).hexdigest()
        source["anchors"] = [{"anchor_id": task["anchor_id"], "kind": task["kind"],
                              "start": task["start"], "end": task["end"],
                              "extracted_text_sha256": excerpt_hash}]
        if task["source_id"] == "LIT-zhang-2021-cross-corpus-ser":
            source["adaptation_notice"] = (
                "Publisher PDF text extracted with pypdf; line-wrap hyphenation and whitespace normalized; selected page-2 sentences only."
            )
        excerpt = {"anchor_id": task["anchor_id"], "extracted_text_sha256": excerpt_hash,
                   "source_id": source["source_id"], "source_sha256": source["sha256"],
                   "source_version": source["version"], "text": task["text"]}
        job_dir = JOBS_DIR / job_id
        input_dir = INPUTS_DIR / job_id
        source_path = input_dir / "source.json"
        excerpt_path = input_dir / "excerpt.json"
        approved_path = input_dir / "approved_sources.json"
        bundle_path = job_dir / f"Gurumoji_Job_{job_id}_g1.zip"
        write_json(source_path, source)
        write_json(excerpt_path, excerpt)
        write_json(approved_path, {"schema_version": 1, "sources": [source]})
        job_dir.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, str(ROOT / "scripts" / "prepare_colab_claim_job.py"),
                   "--data-dir", str(DATA_DIR), "--expert-id", task["expert_id"],
                   "--source-json", str(source_path), "--excerpt-json", str(excerpt_path),
                   "--approved-sources-json", str(approved_path), "--output", str(bundle_path),
                   "--ttl-minutes", "55", "--retry-limit", "1", "--job-id", job_id]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", check=False)
        if completed.returncode:
            raise RuntimeError(f"prepare failed for {job_id}: {completed.stdout}\n{completed.stderr}")
        record = json.loads(completed.stdout)
        if record.get("status") != "ready_for_user_started_colab":
            raise RuntimeError(f"prepare rejected {job_id}: {completed.stdout}")

        old_id = f"{BATCH_ID}-01"
        remote_runner = runner_template.replace(old_id, job_id)
        remote_runner = remote_runner.replace("b20260928t025516-01", job_id)

        # The result runner is bound to both the new job ID and this bundle hash.
        import re
        remote_runner, replacements = re.subn(
            r'EXPECTED_BUNDLE_SHA256 = "[0-9a-f]{64}"',
            f'EXPECTED_BUNDLE_SHA256 = "{record["bundle_sha256"]}"',
            remote_runner, count=1,
        )
        if replacements != 1 or f'EXPECTED_JOB_ID = "{job_id}"' not in remote_runner:
            raise ValueError(f"runner binding failed for {job_id}")
        remote_path = job_dir / "colab_run_job.py"
        remote_path.write_text(remote_runner, encoding="utf-8")
        manifest["jobs"].append({
            "job_id": job_id, "generation": record["generation"],
            "expert_id": task["expert_id"], "source_id": source["source_id"],
            "anchor_id": task["anchor_id"], "status": "ready_for_user_started_colab",
            "source_record_path": source_path.relative_to(ROOT).as_posix(),
            "source_sha256": source["sha256"], "source_version": source["version"],
            "excerpt_path": excerpt_path.relative_to(ROOT).as_posix(),
            "excerpt_sha256": excerpt_hash,
            "approved_sources_path": approved_path.relative_to(ROOT).as_posix(),
            "bundle_path": bundle_path.relative_to(ROOT).as_posix(),
            "bundle_sha256": record["bundle_sha256"],
            "runner_path": remote_path.relative_to(ROOT).as_posix(),
            "result_path": (job_dir / f"Gurumoji_Result_{job_id}_g1.zip").relative_to(ROOT).as_posix(),
            "status_path": (job_dir / f"Gurumoji_Status_{job_id}_g1.json").relative_to(ROOT).as_posix(),
            "local_registry_path": str(bundle_path.with_name(bundle_path.stem + ".local-approved-sources.json")),
            "gpu": "NVIDIA A100-SXM4-80GB",
            "model_reference": "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        existing_ids.add(job_id)

    manifest["total_jobs"] = len(manifest["jobs"])
    manifest["status"] = "ready_for_user_started_colab"
    write_json(manifest_path, manifest)
    write_json(HERE / f"{BATCH_ID}-progress.json", {
        "batch_id": BATCH_ID, "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_jobs": len(manifest["jobs"]), "finished_jobs": 6,
        "candidate_ready": sum(job["status"] == "candidate_ready" for job in manifest["jobs"]),
        "failed": sum(job["status"] == "failed" for job in manifest["jobs"]),
        "jobs": [{k: job.get(k) for k in ("job_id", "expert_id", "source_id", "anchor_id", "status", "error")}
                 for job in manifest["jobs"]],
    })
    print(json.dumps({"batch_id": BATCH_ID, "added_jobs": [task["job_id"] for task in TASKS]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
