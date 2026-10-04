"""Prepare a hash-bound A100 batch for under-covered analysis domains."""
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
BATCH_ID = "b20260928t061000"
SESSION = "gurumoji-a100-deepknowledge-20260928-061000"
DATA_DIR = HERE / "state"
JOBS_DIR = HERE / "jobs"
INPUTS_DIR = HERE / "inputs" / BATCH_ID / "jobs"
SOURCES_DIR = HERE / "sources" / BATCH_ID
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
MDPI_PDF = SOURCES_DIR / "static_pdf.pdf"
MDPI_SHA256 = "b7d8fe5964a2de5d8a6c5c858d41468baff10bd8e0d40ce5245add6656266612"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def copy_source(relative: str) -> dict:
    return read_json(ROOT / relative)


def source_record(source: dict, *, anchor_id: str, start: str, end: str,
                  kind: str, text: str, notice: str | None = None) -> tuple[dict, dict]:
    excerpt_hash = sha256_text(text)
    source = dict(source)
    source["anchors"] = [{"anchor_id": anchor_id, "kind": kind, "start": start,
                          "end": end, "extracted_text_sha256": excerpt_hash}]
    if notice:
        source["adaptation_notice"] = notice
    excerpt = {
        "anchor_id": anchor_id,
        "extracted_text_sha256": excerpt_hash,
        "source_id": source["source_id"],
        "source_sha256": source["sha256"],
        "source_version": source["version"],
        "text": text,
    }
    return source, excerpt


def mdpi_source() -> dict:
    if hashlib.sha256(MDPI_PDF.read_bytes()).hexdigest() != MDPI_SHA256:
        raise ValueError("MDPI PDF snapshot hash does not match the reviewed file")
    return {
        "access_scope": "full_text",
        "adaptation_notice": "Publisher PDF from the official MDPI article page; selected passages on pp. 1, 14–15. pypdf extraction with whitespace and line-wrap normalization; figures, references, and third-party cited works excluded.",
        "anchors": [],
        "authors": ["Nobuko Shimizu", "Takako Yamada", "Nobuyuki Honda", "Miyako Mochizuki",
                    "Mayumi Kato", "Noboru Hasegawa", "Hunsa Sethabouppha", "Nattaya Suwankruhasn",
                    "Chalinee Suvanayos"],
        "license": {"license_id": "CC-BY-4.0",
                    "terms": "Creative Commons Attribution 4.0; attribution required and changes must be indicated."},
        "license_url": {"kind": "https", "value": "https://creativecommons.org/licenses/by/4.0/"},
        "locator": {"kind": "doi", "value": "10.3390/jal3010002"},
        "publication_year": 2023,
        "rights": {"allowed_routes": ["local", "colab", "export"], "classification": "licensed"},
        "schema_version": 1,
        "sha256": MDPI_SHA256,
        "source_id": "LIT-shimizu-2023-scat-application",
        "source_type": "paper",
        "title": "Qualitative Study on Important Elements of Life for Japanese and Thai Older Adults",
        "version": f"mdpi-jal-2023-publisher-pdf-2026-09-28-sha256-{MDPI_SHA256[:16]}",
    }


MDPI_EXCERPT = """The Steps for Coding and Theorization (SCAT) method [22,23] was used as the analytical framework. SCAT is a sequential and thematic technique for qualitative data analysis. The data are processed in a four-step sequential coding process: (1) selecting terms in the data segments worthy of focus; (2) assigning external terms to reword the terms from step 1; (3) drawing out concepts that explain the terms in steps 1 and 2; and (4) inferring themes and constructs from the concepts. This is followed by linking the themes and constructs to create a storyline and writing a theory.

In this study, the steps were: (1) data entry into the SCAT form; (2) grouping strips for individual data and classifying similar strips into the same piles; (3) rewording each data group; (4) conceptualizing potential themes that arise from relationships between groups; (5) writing a storyline that incorporates all data; and (6) writing a theory based on the conceptualization. The analysis examined individual participants' data, compared them with other participants to identify similarities and differences, repeated data collection and analysis, and assigned category names by tracing relationships. The analysis was supervised by a researcher experienced in SCAT. The study included 14 older adults, seven from Japan and seven from Thailand."""


TASKS = [
    {
        "suffix": "01", "expert_id": "exp-descriptive-statistics",
        "source_path": "output/knowledge-colab-batch/inputs/b20260928t025516/RES-scipy-describe/source.json",
        "source_id": "RES-scipy-describe", "anchor_id": "describe-variance-and-missing-data",
        "start": "scipy.stats.describe parameters ddof, bias, nan_policy and returned statistics",
        "end": "scipy.stats.describe variance, skewness, kurtosis and nobs behavior",
        "kind": "section",
        "text": "For scipy.stats.describe(a, axis=0, ddof=1, bias=True, nan_policy='propagate'): ddof changes only the variance calculation and defaults to 1. If bias=False, skewness and kurtosis are corrected for statistical bias. nan_policy defaults to 'propagate'; 'propagate' returns nan, 'raise' raises an error, and 'omit' ignores nan values. With nan_policy='omit', the number of observations is counted separately for each axis slice. The returned variance is unbiased, with denominator n minus one; skewness uses a denominator equal to n and no degrees-of-freedom correction; kurtosis uses no degrees of freedom.",
    },
    {
        "suffix": "02", "expert_id": "exp-embedding-topic-exploration",
        "source_path": "output/knowledge-colab-batch/inputs/b20260928t025516/RES-bertopic-official/source.json",
        "source_id": "RES-bertopic-official", "anchor_id": "bertopic-class-based-tfidf-detail",
        "start": "5. Topic representation: class-based TF and IDF",
        "end": "ClassTfidfTransformer parameters including BM25 weighting",
        "kind": "section",
        "text": "To describe what makes one cluster different from other clusters, BERTopic modifies TF-IDF to use topics (clusters) rather than documents. It treats all documents in a cluster as one document. The frequency of word x in class c gives the class-based term-frequency representation, and this representation is L1-normalized to account for differences in topic sizes. For the class-based inverse-document-frequency representation, BERTopic uses the logarithm of one plus the average number of words per class divided by the frequency of word x across all classes. The modified TF-IDF scores are used to represent each topic. ClassTfidfTransformer also has an option for additional BM25 weighting.",
    },
    {
        "suffix": "03", "expert_id": "exp-japanese-text-preprocessing",
        "source_path": "output/knowledge-colab-batch/inputs/b20260928t025516/RES-ginza-official/source.json",
        "source_id": "RES-ginza-official", "anchor_id": "ginza-v5-model-training-corpora",
        "start": "Training Datasets: UD Japanese BCCWJ r2.8, GSK2014-A, and mC4",
        "end": "GiNZA v5 parser, NER, and ja_ginza_electra training data",
        "kind": "section",
        "text": "According to the GiNZA v5 official README, its parsing model was trained on part of UD Japanese BCCWJ r2.8. Its named-entity-recognition model was trained on part of the GSK2014-A (2019) BCCWJ edition, using both Sekine's Extended Named Entity Hierarchy and an extended OntoNotes 5 label system. The ja_ginza_electra model uses a transformer pretrained on more than 200 million Japanese sentences extracted from mC4. These are descriptions of different GiNZA v5 models and their stated training sources.",
    },
    {
        "suffix": "04", "expert_id": "exp-kj-method",
        "source_path": "output/knowledge-colab-batch/inputs/b20260928t042558/LIT-kanzaki-sakai-2025-kj-medrxiv/source-v3-case-scoped.json",
        "source_id": "LIT-kanzaki-sakai-2025-kj-medrxiv", "anchor_id": "kj-case-card-grouping-detail",
        "start": "Theme extraction: repeated card grouping and title hierarchy",
        "end": "This study's six themes and spatial arrangement of theme cards",
        "kind": "paragraph",
        "text": "All members read the cards five times to determine which were related to the theme. After understanding the contents of each card, they grouped cards with similar contents and added an “A title”. The A-title group was treated as a whole together with the small cards in that group. The number of small cards in a group was not to exceed half of the initial number of cards in that round. The team then regrouped similar cards and added a “B title”; by analogy, headings B, C, and D were formed, ultimately extracting six major themes. Physical cards for the six themes were iteratively rearranged on a background sheet until their spatial arrangement reflected logical relationships, and symbols were used to annotate connections among themes.",
    },
    {
        "suffix": "05", "expert_id": "exp-scat",
        "source_inline": "mdpi-scat",
        "source_id": "LIT-shimizu-2023-scat-application", "anchor_id": "scat-application-and-procedure",
        "start": "Abstract; Methods 2.5 Methods of Analysis",
        "end": "Methods 2.6 Characteristics and Reliability of Coding and Theorization",
        "kind": "section",
        "text": MDPI_EXCERPT,
    },
    {
        "suffix": "06", "expert_id": "exp-speech-emotion-recognition",
        "source_path": "output/knowledge-colab-batch/inputs/b20260928t042558/LIT-zhang-2021-cross-corpus-ser/source-v1.json",
        "source_id": "LIT-zhang-2021-cross-corpus-ser", "anchor_id": "ser-cross-corpus-domain-shift-limit",
        "start": "Cross-corpus SER: differences between training and testing corpora",
        "end": "Corpus differences and their effect on generalization",
        "kind": "paragraph",
        "text": "Most existing speech emotion recognition systems are trained and evaluated on a single corpus and in a single-language setting. In practical applications, training and test corpora may differ in language, culture, distribution mode, data scale, and other respects. The authors state that these cross-corpus differences cause idiosyncratic variation that impedes the generalization of current speech emotion recognition techniques, making cross-corpus SER an active research topic.",
    },
]


def main() -> None:
    template_runner = (JOBS_DIR / "b20260928t051400-01" / "colab_run_job.py").read_text(encoding="utf-8")
    local_runner_template = (HERE / "run_b20260928t051400.py").read_text(encoding="utf-8")
    jobs = []
    for task in TASKS:
        job_id = f"{BATCH_ID}-{task['suffix']}"
        job_dir = JOBS_DIR / job_id
        input_dir = INPUTS_DIR / job_id
        source = mdpi_source() if task.get("source_inline") == "mdpi-scat" else copy_source(ROOT / task["source_path"])
        if source["source_id"] != task["source_id"]:
            raise ValueError(f"Source ID mismatch for {job_id}")
        source, excerpt = source_record(
            source,
            anchor_id=task["anchor_id"], start=task["start"], end=task["end"],
            kind=task["kind"], text=task["text"],
            notice=("Versioned official documentation; selected passage only."
                    if task["source_id"].startswith("RES-") else None),
        )
        source_path = input_dir / "source.json"
        excerpt_path = input_dir / "excerpt.json"
        approved_path = input_dir / "approved_sources.json"
        bundle_path = job_dir / f"Gurumoji_Job_{job_id}_g1.zip"
        write_json(source_path, source)
        write_json(excerpt_path, excerpt)
        write_json(approved_path, {"schema_version": 1, "sources": [source]})
        job_dir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable, str(ROOT / "scripts" / "prepare_colab_claim_job.py"),
            "--data-dir", str(DATA_DIR), "--expert-id", task["expert_id"],
            "--source-json", str(source_path), "--excerpt-json", str(excerpt_path),
            "--approved-sources-json", str(approved_path), "--output", str(bundle_path),
            "--ttl-minutes", "55", "--retry-limit", "1", "--job-id", job_id,
        ]
        prepared = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", check=False)
        if prepared.returncode:
            raise RuntimeError(f"prepare failed for {job_id}: {prepared.stdout}\n{prepared.stderr}")
        record = json.loads(prepared.stdout)
        if record.get("status") != "ready_for_user_started_colab":
            raise RuntimeError(f"prepare rejected {job_id}: {prepared.stdout}")

        remote_runner = template_runner.replace("b20260928t051400-01", job_id)
        remote_runner = remote_runner.replace("b20260928t025516-01", job_id)
        remote_runner = remote_runner.replace(
            "2f91acad9089b8d372b69cee879c7b02e56b5052f8f3c9c0787a915a34a330a9",
            record["bundle_sha256"],
        )
        remote_path = job_dir / "colab_run_job.py"
        remote_path.write_text(remote_runner, encoding="utf-8")
        if f'EXPECTED_JOB_ID = "{job_id}"' not in remote_runner:
            raise ValueError(f"remote runner job binding mismatch: {job_id}")
        if f'EXPECTED_BUNDLE_SHA256 = "{record["bundle_sha256"]}"' not in remote_runner:
            raise ValueError(f"remote runner bundle binding mismatch: {job_id}")

        jobs.append({
            "job_id": job_id, "generation": record["generation"],
            "expert_id": task["expert_id"], "source_id": source["source_id"],
            "anchor_id": task["anchor_id"], "status": "ready_for_user_started_colab",
            "source_record_path": source_path.relative_to(ROOT).as_posix(),
            "source_sha256": source["sha256"], "source_version": source["version"],
            "excerpt_path": excerpt_path.relative_to(ROOT).as_posix(),
            "excerpt_sha256": excerpt["extracted_text_sha256"],
            "approved_sources_path": approved_path.relative_to(ROOT).as_posix(),
            "bundle_path": bundle_path.relative_to(ROOT).as_posix(),
            "bundle_sha256": record["bundle_sha256"],
            "runner_path": remote_path.relative_to(ROOT).as_posix(),
            "result_path": (job_dir / f"Gurumoji_Result_{job_id}_g1.zip").relative_to(ROOT).as_posix(),
            "status_path": (job_dir / f"Gurumoji_Status_{job_id}_g1.json").relative_to(ROOT).as_posix(),
            "local_registry_path": str(bundle_path.with_name(bundle_path.stem + ".local-approved-sources.json")),
            "gpu": "NVIDIA A100-SXM4-80GB", "model_reference": MODEL,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    manifest = {
        "batch_id": BATCH_ID, "created_at": datetime.now(timezone.utc).isoformat(),
        "session_name": SESSION, "gpu": "NVIDIA A100-SXM4-80GB",
        "model_reference": MODEL, "total_jobs": len(jobs),
        "status": "ready_for_user_started_colab", "jobs": jobs,
    }
    manifest_path = HERE / f"{BATCH_ID}.json"
    write_json(manifest_path, manifest)
    local_runner = local_runner_template.replace("b20260928t051400", BATCH_ID)
    local_runner = local_runner.replace("gurumoji-a100-deepknowledge-20260928-051400", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(local_runner, encoding="utf-8")
    write_json(HERE / f"{BATCH_ID}-progress.json", {
        "batch_id": BATCH_ID, "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_jobs": len(jobs), "finished_jobs": 0, "candidate_ready": 0,
        "failed": 0,
        "jobs": [{k: job[k] for k in ("job_id", "expert_id", "source_id", "anchor_id", "status")}
                 for job in jobs],
    })
    print(json.dumps({"manifest": manifest_path.relative_to(ROOT).as_posix(),
                      "batch_id": BATCH_ID, "jobs": len(jobs),
                      "job_ids": [job["job_id"] for job in jobs]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
