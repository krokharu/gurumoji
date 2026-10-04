"""Prepare six additional hash-bound A100 claims from reviewed sources."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t070100"
SESSION = "gurumoji-a100-deepknowledge-20260928-070100"
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


def load_template(job_id: str) -> tuple[dict, dict]:
    source_dir = HERE / "inputs" / "b20260928t061000" / "jobs" / job_id
    return read_json(source_dir / "source.json"), read_json(source_dir / "excerpt.json")


TASKS = [
    {
        "expert_id": "exp-descriptive-statistics",
        "template_job": "b20260928t061000-01",
        "anchor_id": "describe-omit-counts-by-slice",
        "kind": "section",
        "start": "SciPy describe nan_policy omit behavior",
        "end": "Observation counts are reported separately for each axis slice",
        "text": (
            "In scipy.stats.describe, nan_policy defaults to 'propagate', which returns NaN "
            "for results affected by NaN values; 'raise' raises an error. With nan_policy='omit', "
            "NaN values are ignored and the number of observations is counted separately for each "
            "axis slice."
        ),
    },
    {
        "expert_id": "exp-embedding-topic-exploration",
        "template_job": "b20260928t061000-02",
        "anchor_id": "bertopic-class-tfidf-normalization",
        "kind": "section",
        "start": "Class-based term-frequency representation",
        "end": "L1 normalization for topic size and optional BM25 weighting",
        "text": (
            "BERTopic forms a class-based term-frequency representation from the words in each "
            "cluster and L1-normalizes it to account for differences in topic size. Its modified "
            "inverse-frequency representation uses the average number of words per class and the "
            "frequency of each word across classes. ClassTfidfTransformer also offers optional "
            "BM25 weighting."
        ),
    },
    {
        "expert_id": "exp-japanese-text-preprocessing",
        "template_job": "b20260928t061000-03",
        "anchor_id": "ginza-v5-ner-training-data-and-labels",
        "kind": "section",
        "start": "GiNZA v5 Training Datasets: named-entity-recognition model",
        "end": "GSK2014-A BCCWJ edition and the NER label systems",
        "text": (
            "The GiNZA v5 official README states that its named-entity-recognition model was "
            "trained on part of the 2019 BCCWJ edition of GSK2014-A. It uses Sekine's Extended "
            "Named Entity Hierarchy together with an extended OntoNotes 5 label system. These are "
            "the README's statements about the NER model; its parsing-model and ja_ginza_electra "
            "training data are described separately."
        ),
    },
    {
        "expert_id": "exp-kj-method",
        "template_job": "b20260928t061000-07",
        "anchor_id": "kj-twin-fathers-study-specific-card-process",
        "kind": "paragraph",
        "start": "Data analysis procedure adopted in the twin-fathers study",
        "end": "The study's reported card-grouping workflow and six themes",
        "adaptation_notice": (
            "Paraphrased, study-scoped summary of the selected medRxiv v1 Methods passage. "
            "It describes this paper's workflow and is not a general KJ-method instruction."
        ),
        "text": (
            "In this study of fathers raising twins, the authors adopted the KJ method. Their "
            "reported procedure selected representative statements, condensed and coded them, "
            "transferred coded quotes onto cards, and iteratively grouped related cards under "
            "headings. The authors report that this study's process yielded six major themes; "
            "they then arranged theme cards on a background sheet to show relationships."
        ),
    },
    {
        "expert_id": "exp-scat",
        "template_job": "b20260928t061000-05",
        "anchor_id": "scat-application-comparison-and-supervision",
        "kind": "section",
        "start": "Methods 2.5: analysis of participants' data",
        "end": "Methods 2.6: repeated analysis and SCAT-experienced supervision",
        "text": (
            "In this study of 14 older adults (seven in Japan and seven in Thailand), the authors "
            "examined participants' data individually, compared participants to identify "
            "similarities and differences, repeated data collection and analysis, and assigned "
            "category names by tracing relationships. They report that a researcher experienced "
            "in SCAT supervised the analysis. These are details of this application study."
        ),
    },
    {
        "expert_id": "exp-speech-emotion-recognition",
        "template_job": "b20260928t061000-08",
        "anchor_id": "ser-cross-corpus-variation-factors",
        "kind": "paragraph",
        "start": "Cross-corpus speech emotion recognition: differences between training and test corpora",
        "end": "Language, culture, distribution mode, and data-scale variation",
        "text": (
            "Zhang et al.'s review notes that the majority of existing speech-emotion-recognition "
            "systems use a single corpus and a single-language setting for training and evaluation. "
            "For cross-corpus applications, training and test corpora may differ in language, "
            "culture, distribution mode, or data scale; the review says such differences can create "
            "variations that impede generalization."
        ),
    },
]


def main() -> None:
    if (HERE / f"{BATCH_ID}.json").exists():
        raise FileExistsError(BATCH_ID)
    jobs = []
    for index, task in enumerate(TASKS, 1):
        job_id = f"{BATCH_ID}-{index:02d}"
        job_dir = JOBS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        source, _ = load_template(task["template_job"])
        source["anchors"] = [{
            "anchor_id": task["anchor_id"],
            "kind": task["kind"],
            "start": task["start"],
            "end": task["end"],
            "extracted_text_sha256": digest(task["text"]),
        }]
        if task.get("adaptation_notice"):
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
        old_id = "b20260928t061000-01"
        old_hash = "5a1d56a4cdb1e016f6fa7bad40738199e5150ac94b56caad89b1dddecc646080"
        runner = runner.replace(old_id, job_id).replace(old_hash, record["bundle_sha256"])
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
    write_json(HERE / f"{BATCH_ID}.json", manifest)
    template = (HERE / "run_b20260928t061000.py").read_text(encoding="utf-8")
    template = template.replace("b20260928t061000.json", f"{BATCH_ID}.json")
    template = template.replace("gurumoji-a100-deepknowledge-20260928-061000", SESSION)
    run_path = HERE / f"run_{BATCH_ID}.py"
    run_path.write_text(template, encoding="utf-8")
    print(json.dumps({"batch_id": BATCH_ID, "jobs": len(jobs),
                      "manifest": manifest["batch_id"] + ".json",
                      "runner": run_path.name}, sort_keys=True))


if __name__ == "__main__":
    main()
