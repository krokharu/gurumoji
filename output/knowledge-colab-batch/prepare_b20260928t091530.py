"""Prepare four source-bound A100 knowledge claims from approved excerpts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t091530"
SESSION = "gurumoji-a100-deepknowledge-20260928-091530"
DATA_DIR = HERE / "state"
JOBS_DIR = HERE / "jobs"
INPUTS_DIR = HERE / "inputs" / BATCH_ID / "jobs"
BASE_RUNNER = JOBS_DIR / "b20260928t061000-01" / "colab_run_job.py"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


TASKS = [
    {
        "expert_id": "exp-conversation-timing",
        "source_template": HERE / "inputs/b20260928t025516/LIT-levinson-torreira-2015-timing/source.json",
        "anchor_id": "heldner-edlund-fto-mode",
        "kind": "page",
        "start": "6",
        "end": "6",
        "text": (
            "Levinson and Torreira review Heldner and Edlund (2010) across a Dutch dialogue corpus "
            "and English and Swedish Map Tasks. Their combined-scale floor-transfer-offset "
            "distribution has a mode of about 200 ms, described as a short gap. The paper "
            "distinguishes this mode from average FTO values and from the separately reported "
            "mean and median overlap durations."
        ),
        "adaptation_notice": (
            "Paraphrased, narrowly selected summary of publisher PDF p. 6, §5.1. The excerpt "
            "preserves the source's mode-versus-average distinction."
        ),
    },
    {
        "expert_id": "exp-framework-method",
        "source_template": HERE / "inputs/LIT-gale-2013-framework/source.json",
        "anchor_id": "caqdas-storage-not-analysis",
        "kind": "page",
        "start": "5",
        "end": "5",
        "text": (
            "In Framework Method stage 5, researchers index later transcripts using the categories "
            "and codes in the working framework. CAQDAS can facilitate this work and later data "
            "retrieval; entering data into a qualitative software package stores and organizes it "
            "but does not itself analyze the data."
        ),
        "adaptation_notice": (
            "Paraphrased, selected summary of Gale et al. (2013), publisher PDF p. 5, stage 5. "
            "The article is licensed CC BY 2.0."
        ),
    },
    {
        "expert_id": "exp-focus-group-interaction",
        "source_template": HERE / "inputs/b20260928t051400/LIT-hermann-2024-fg-interaction-coding/source.json",
        "anchor_id": "fg-coding-scheme-development-sample",
        "kind": "section",
        "start": "Study participants and focus-group sessions",
        "end": "Development and testing context of the interaction coding scheme",
        "text": (
            "Hermann et al. developed their focus-group interaction coding scheme using five "
            "face-to-face focus groups with 27 adolescents aged 15–18, then tried the scheme on "
            "separate focus-group data. These are the sample and testing conditions reported for "
            "this study."
        ),
        "adaptation_notice": (
            "Paraphrased, study-scoped summary of the full-text paper's participants and coding "
            "scheme testing sections; no participant-level data are included."
        ),
    },
    {
        "expert_id": "exp-m-gta",
        "source_template": HERE / "inputs/b20260928t051400/LIT-iseki-2023-mgta-process/source.json",
        "anchor_id": "mgta-study-output-scope",
        "kind": "section",
        "start": "Results: categories and concepts",
        "end": "M-GTA output reported for the clinical application",
        "text": (
            "In Iseki's clinical M-GTA application involving 21 adult women diagnosed with "
            "metastatic breast cancer and receiving pharmacotherapy, the analysis reported seven "
            "categories and 21 concepts. These counts describe the output of this study."
        ),
        "adaptation_notice": (
            "Paraphrased, study-scoped summary from the full-text article's Results section; the "
            "counts are not presented as general M-GTA requirements."
        ),
    },
]


def main() -> None:
    manifest_path = HERE / f"{BATCH_ID}.json"
    if manifest_path.exists():
        raise FileExistsError(BATCH_ID)
    jobs = []
    for index, task in enumerate(TASKS, 1):
        job_id = f"{BATCH_ID}-{index:02d}"
        job_dir = JOBS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        source = read_json(task["source_template"])
        source["anchors"] = [{
            "anchor_id": task["anchor_id"],
            "kind": task["kind"],
            "start": task["start"],
            "end": task["end"],
            "extracted_text_sha256": digest(task["text"]),
        }]
        source["adaptation_notice"] = task["adaptation_notice"]
        excerpt = {
            "anchor_id": task["anchor_id"],
            "extracted_text_sha256": digest(task["text"]),
            "source_id": source["source_id"],
            "source_sha256": source["sha256"],
            "source_version": source["version"],
            "text": task["text"],
        }
        input_dir = INPUTS_DIR / job_id
        write_json(input_dir / "source.json", source)
        write_json(input_dir / "approved_sources.json", {"schema_version": 1, "sources": [source]})
        write_json(input_dir / "excerpt.json", excerpt)
        bundle = job_dir / f"Gurumoji_Job_{job_id}_g1.zip"
        command = [
            sys.executable, str(ROOT / "scripts/prepare_colab_claim_job.py"),
            "--data-dir", str(DATA_DIR), "--expert-id", task["expert_id"],
            "--source-json", str(input_dir / "source.json"),
            "--excerpt-json", str(input_dir / "excerpt.json"),
            "--approved-sources-json", str(input_dir / "approved_sources.json"),
            "--output", str(bundle), "--job-id", job_id, "--ttl-minutes", "55",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        if completed.returncode:
            raise RuntimeError(f"{job_id}: {completed.stdout} {completed.stderr}")
        record = json.loads(completed.stdout)
        record.update({
            "bundle_path": bundle.relative_to(ROOT).as_posix(),
            "source_id": source["source_id"],
            "source_record_path": (input_dir / "source.json").relative_to(ROOT).as_posix(),
            "excerpt_path": (input_dir / "excerpt.json").relative_to(ROOT).as_posix(),
            "source_sha256": source["sha256"],
            "excerpt_sha256": excerpt["extracted_text_sha256"],
            "expert_id": task["expert_id"],
            "anchor_id": task["anchor_id"],
            "gpu": "NVIDIA A100-SXM4-80GB",
            "model_reference": "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8",
            "generation": 1,
            "status": "ready_for_user_started_colab",
        })
        jobs.append(record)
        runner = BASE_RUNNER.read_text(encoding="utf-8")
        runner = runner.replace("b20260928t061000-01", job_id)
        runner = runner.replace("5a1d56a4cdb1e016f6fa7bad40738199e5150ac94b56caad89b1dddecc646080",
                                record["bundle_sha256"])
        (job_dir / "colab_run_job.py").write_text(runner, encoding="utf-8")

    manifest = {
        "batch_id": BATCH_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gpu": "NVIDIA A100-SXM4-80GB",
        "model_reference": "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8",
        "session_name": SESSION,
        "status": "ready_for_user_started_colab",
        "total_jobs": len(jobs),
        "jobs": jobs,
    }
    write_json(manifest_path, manifest)
    progress = {
        "batch_id": BATCH_ID,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_jobs": len(jobs),
        "finished_jobs": 0,
        "candidate_ready": 0,
        "failed": 0,
        "jobs": [{"job_id": job["job_id"], "expert_id": job["expert_id"],
                  "source_id": job["source_id"], "anchor_id": job["anchor_id"],
                  "status": job["status"], "result_sha256": None, "error": None} for job in jobs],
    }
    write_json(HERE / f"{BATCH_ID}-progress.json", progress)
    template = (HERE / "run_b20260928t061000.py").read_text(encoding="utf-8")
    template = template.replace("b20260928t061000.json", f"{BATCH_ID}.json")
    template = template.replace("gurumoji-a100-deepknowledge-20260928-061000", SESSION)
    run_path = HERE / f"run_{BATCH_ID}.py"
    run_path.write_text(template, encoding="utf-8")
    print(json.dumps({"batch_id": BATCH_ID, "jobs": len(jobs),
                      "manifest": manifest_path.name, "runner": run_path.name}, sort_keys=True))


if __name__ == "__main__":
    main()
