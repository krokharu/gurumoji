"""Prepare two narrow A100 revisions for previously held claims."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t094700"
SESSION = "gurumoji-a100-deepknowledge-20260928-094700"
DATA_DIR = HERE / "state"
JOBS_DIR = HERE / "jobs"
INPUTS_DIR = HERE / "inputs" / BATCH_ID / "jobs"
BASE_RUNNER = JOBS_DIR / "b20260928t061000-01" / "colab_run_job.py"

TASKS = [
    {
        "expert_id": "exp-embedding-topic-exploration",
        "source_template": HERE / "inputs/b20260928t093710/jobs/b20260928t093710-03/source.json",
        "revises_job": "b20260928t093710-03",
        "anchor_id": "bertopic-five-plus-optional-sixth",
        "kind": "section",
        "start": "BERTopic v0.17.4 Visual Overview and Code Overview",
        "end": "Five main representation stages and optional Step 6 tuning",
        "text": (
            "BERTopic v0.17.4 describes five steps for producing topic representations: extract "
            "embeddings, reduce dimensionality, cluster, tokenize topics, and calculate topic "
            "weights. Its Code Overview labels representation tuning as an additional, optional "
            "sixth step. Representation tuning is therefore not mandatory."
        ),
        "adaptation_notice": (
            "Paraphrased, selected summary of the BERTopic v0.17.4 official algorithm documentation; "
            "the sixth representation-tuning step is explicitly optional."
        ),
    },
    {
        "expert_id": "exp-japanese-text-preprocessing",
        "source_template": HERE / "inputs/b20260928t093710/jobs/b20260928t093710-04/source.json",
        "revises_job": "b20260928t093710-04",
        "anchor_id": "ginza-electra-backbone-pretraining-lineage",
        "kind": "section",
        "start": "GiNZA v5.2.0 README Training Datasets: mC4",
        "end": "Pretraining source for the transformer backbone used by ja_ginza_electra",
        "text": (
            "The GiNZA v5.2.0 README says ja_ginza_electra is trained using the "
            "transformer-ud-japanese-electra-base-discriminator model; that underlying model was "
            "pretrained on more than 200 million Japanese sentences extracted from mC4. The "
            "more-than-200-million figure describes the underlying pretrained model."
        ),
        "adaptation_notice": (
            "Paraphrased, narrowly selected summary of the versioned GiNZA v5.2.0 README's Training "
            "Datasets section; the excerpt preserves the distinction between ja_ginza_electra and "
            "its pretrained transformer backbone."
        ),
    },
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        source["anchors"] = [{"anchor_id": task["anchor_id"], "kind": task["kind"],
                              "start": task["start"], "end": task["end"],
                              "extracted_text_sha256": digest(task["text"])}]
        source["adaptation_notice"] = task["adaptation_notice"]
        excerpt = {"anchor_id": task["anchor_id"], "extracted_text_sha256": digest(task["text"]),
                   "source_id": source["source_id"], "source_sha256": source["sha256"],
                   "source_version": source["version"], "text": task["text"]}
        input_dir = INPUTS_DIR / job_id
        write_json(input_dir / "source.json", source)
        write_json(input_dir / "approved_sources.json", {"schema_version": 1, "sources": [source]})
        write_json(input_dir / "excerpt.json", excerpt)
        bundle = job_dir / f"Gurumoji_Job_{job_id}_g1.zip"
        command = [sys.executable, str(ROOT / "scripts/prepare_colab_claim_job.py"),
                   "--data-dir", str(DATA_DIR), "--expert-id", task["expert_id"],
                   "--source-json", str(input_dir / "source.json"),
                   "--excerpt-json", str(input_dir / "excerpt.json"),
                   "--approved-sources-json", str(input_dir / "approved_sources.json"),
                   "--output", str(bundle), "--job-id", job_id, "--ttl-minutes", "55"]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        if result.returncode:
            raise RuntimeError(f"{job_id}: {result.stdout} {result.stderr}")
        record = json.loads(result.stdout)
        record.update({"bundle_path": bundle.relative_to(ROOT).as_posix(),
                       "source_id": source["source_id"],
                       "source_record_path": (input_dir / "source.json").relative_to(ROOT).as_posix(),
                       "excerpt_path": (input_dir / "excerpt.json").relative_to(ROOT).as_posix(),
                       "source_sha256": source["sha256"], "excerpt_sha256": excerpt["extracted_text_sha256"],
                       "expert_id": task["expert_id"], "anchor_id": task["anchor_id"],
                       "revises_job": task["revises_job"], "gpu": "NVIDIA A100-SXM4-80GB",
                       "model_reference": "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8",
                       "generation": 1, "status": "ready_for_user_started_colab"})
        jobs.append(record)
        runner = BASE_RUNNER.read_text(encoding="utf-8")
        runner = runner.replace("b20260928t061000-01", job_id)
        runner = runner.replace("5a1d56a4cdb1e016f6fa7bad40738199e5150ac94b56caad89b1dddecc646080",
                                record["bundle_sha256"])
        (job_dir / "colab_run_job.py").write_text(runner, encoding="utf-8")

    manifest = {"batch_id": BATCH_ID, "created_at": datetime.now(timezone.utc).isoformat(),
                "gpu": "NVIDIA A100-SXM4-80GB",
                "model_reference": "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8",
                "session_name": SESSION, "status": "ready_for_user_started_colab",
                "total_jobs": len(jobs), "jobs": jobs}
    write_json(manifest_path, manifest)
    write_json(HERE / f"{BATCH_ID}-progress.json", {
        "batch_id": BATCH_ID, "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_jobs": len(jobs), "finished_jobs": 0, "candidate_ready": 0, "failed": 0,
        "jobs": [{"job_id": job["job_id"], "expert_id": job["expert_id"],
                  "source_id": job["source_id"], "anchor_id": job["anchor_id"],
                  "status": job["status"], "result_sha256": None, "error": None} for job in jobs]})
    template = (HERE / "run_b20260928t061000.py").read_text(encoding="utf-8")
    template = template.replace("b20260928t061000.json", f"{BATCH_ID}.json")
    template = template.replace("gurumoji-a100-deepknowledge-20260928-061000", SESSION)
    run_path = HERE / f"run_{BATCH_ID}.py"
    run_path.write_text(template, encoding="utf-8")
    print(json.dumps({"batch_id": BATCH_ID, "jobs": len(jobs),
                      "manifest": manifest_path.name, "runner": run_path.name}, sort_keys=True))


if __name__ == "__main__":
    main()
