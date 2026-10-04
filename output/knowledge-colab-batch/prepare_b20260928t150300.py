from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BATCH_ID = "b20260928t150300"
SESSION = "gurumoji-a100-thematic-20260928-150300"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_ID = "LIT-byrne-2022-reflexive-ta"
SOURCE_SHA = "fbe98aa82d7caea73f1bad2785eabe70c88c58a6f4b4037d8cb1d331f3abab3c"
SOURCE_URL = "https://link.springer.com/article/10.1007/s11135-021-01182-y"
SOURCE_REGISTRY = HERE / "inputs" / SOURCE_ID / "approved_sources.json"
SOURCE_RECORD = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-source.json"
EVIDENCE_SNAPSHOT = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-selected-evidence.txt"

TASKS = [
    {
        "job_id": f"{BATCH_ID}-01",
        "anchor_id": "ta-byrne-study-context-and-assumptions",
        "start": "Byrne 2022, publisher PDF pp. 1394–1397",
        "end": "One worked example: study context and theoretical positioning",
        "text": (
            "Byrne's worked example comes from the qualitative phase of a mixed-methods study of Irish post-primary "
            "educators' attitudes toward promoting student social and emotional wellbeing. It used 11 semi-structured "
            "interviews lasting about 25–30 minutes, with core-curriculum teachers, wellbeing-curriculum teachers, "
            "pastoral-care members, and senior managers. These figures describe this one study, not a recommended "
            "sample size for reflexive thematic analysis. The author situated this example in interpretivism and "
            "constructivism and attended both to participants' accounts and to the researcher's interpretive role. "
            "The article says analysts should explain where they stand and why across four continua: essentialist–"
            "constructionist epistemology, experiential–critical orientation, inductive–deductive analysis, and "
            "semantic–latent coding, in relation to their research question. (Publisher PDF pp. 1394–1397.)"
        ),
    },
    {
        "job_id": f"{BATCH_ID}-02",
        "anchor_id": "ta-byrne-six-phases-and-familiarisation",
        "start": "Byrne 2022, publisher PDF pp. 1398–1399",
        "end": "Six phases are iterative; familiarisation and initial coding",
        "text": (
            "The article describes the six phases as logically ordered but not a linear path: reflexive thematic "
            "analysis is recursive and iterative, so analysts may move back and forth as interpretations change; "
            "the phases are flexible guidelines rather than rules. Familiarisation involves reading and re-reading "
            "the whole dataset; the author also describes listening to each recording before transcription, manually "
            "transcribing, rereading transcripts several times, and noting observations and the researcher's own "
            "thoughts and feelings. Initial coding should work systematically across the dataset, give each data item "
            "equal consideration, and use concise labels with enough context to stand alone. These are methodological "
            "descriptions and a worked example, not a claim that every project must use the same transcription workflow. "
            "(Publisher PDF pp. 1398–1399.)"
        ),
    },
    {
        "job_id": f"{BATCH_ID}-03",
        "anchor_id": "ta-byrne-code-iteration-tracking",
        "start": "Byrne 2022, publisher PDF pp. 1400–1402",
        "end": "Tracking code revisions and revisiting the transcripts",
        "text": (
            "Byrne describes coding as an iterative process in which increased familiarity can change interpretations. "
            "The researcher should document coding iterations so changes to codes and prospective themes remain "
            "transparent and earlier analytic paths can be revisited. In the worked example, a spreadsheet placed "
            "data items in rows and successive coding iterations in columns; original transcripts were consulted "
            "again as familiarity grew. The author revised, merged, generalized, or discarded codes when later "
            "interpretation showed that an earlier label was too vague, too specific, or less useful. This spreadsheet "
            "is the author's example of an audit aid, not a required software or data structure. (Publisher PDF pp. 1400–1402.)"
        ),
    },
    {
        "job_id": f"{BATCH_ID}-04",
        "anchor_id": "ta-byrne-theme-generation-and-review",
        "start": "Byrne 2022, publisher PDF pp. 1403–1406",
        "end": "Building candidate themes and reviewing them at two levels",
        "text": (
            "In theme generation, the researcher interprets shared meaning across coded data and actively constructs "
            "relationships among codes; theme importance is not determined by the number of codes or data items. "
            "The article describes reviewing candidates first for coherence among the data items and codes within a "
            "theme, then against the dataset and research question. Review can lead to recoding, restructuring, "
            "adding or removing sub-themes, or discarding a candidate. In Byrne's example, an initially dense and "
            "incoherent candidate theme was broken into three themes after renewed interpretation; this illustrates "
            "the procedure rather than a universal expected outcome. (Publisher PDF pp. 1403–1406.)"
        ),
    },
    {
        "job_id": f"{BATCH_ID}-05",
        "anchor_id": "ta-byrne-theme-definition-and-reporting",
        "start": "Byrne 2022, publisher PDF pp. 1407–1410",
        "end": "Defining themes, interpreting extracts, and recursive reporting",
        "text": (
            "When defining themes, the analyst relates each theme and sub-theme to both the dataset and research "
            "question; themes should make distinct, coherent contributions while joining into an overall account. "
            "The author recommends selecting multiple extracts to show variation and cohesion, then interpreting "
            "each extract in relation to its theme and research question rather than merely reproducing participant "
            "statements. An illustrative report describes extracts, while an analytical report interprets them and may "
            "connect them with literature. Reporting is interwoven with analysis: as codes and themes change, the "
            "write-up also changes, and the order of themes should form a meaningful narrative. (Publisher PDF pp. 1407–1410.)"
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
        raise RuntimeError("approved Byrne Source registry mismatch")
    source = copy.deepcopy(matches[0])
    if source["sha256"] != SOURCE_SHA or source["locator"]["value"] != "10.1007/s11135-021-01182-y":
        raise RuntimeError("approved Byrne Source hash or DOI mismatch")
    if source["rights"]["classification"] != "licensed" or "colab" not in source["rights"]["allowed_routes"]:
        raise RuntimeError("Colab processing is not allowed by the approved Source registry")
    if source["license"]["license_id"] != "CC-BY-4.0":
        raise RuntimeError("unexpected Byrne license")

    source["version"] = "publisher-pdf-fulltext-sha256-fbe98aa82d7caea7"
    source["access_scope"] = "full_text"
    source["adaptation_notice"] = (
        "Five short, source-linked Japanese paraphrase excerpts from the full article are used for draft Claim "
        "generation. Model outputs must remain paraphrased, scoped to the study or methodological guidance, and "
        "retain the publisher PDF page locator. No standalone article text is exported."
    )
    source["anchors"] = []

    evidence_lines = [
        "Byrne, D. (2022). A worked example of Braun and Clarke's approach to reflexive thematic analysis. "
        "Quality & Quantity, 56, 1391–1412. https://doi.org/10.1007/s11135-021-01182-y",
        f"Publisher article: {SOURCE_URL}",
        f"Publisher version-of-record PDF SHA-256: {SOURCE_SHA}. License: CC BY 4.0; attribution required.",
        "Evidence A (PDF pp. 1394–1397): one Irish post-primary educator study, its 11 interviews, "
        "interpretivist/constructivist positioning, and four analytic continua.",
        "Evidence B (PDF pp. 1398–1399): the six phases are recursive and iterative; the worked example "
        "documents familiarisation and initial coding practices.",
        "Evidence C (PDF pp. 1400–1402): the author documents coding iterations, revisits transcripts, "
        "and revises codes as interpretations develop.",
        "Evidence D (PDF pp. 1403–1406): candidate themes are generated through interpreted shared meaning "
        "and reviewed against both their constituent material and the whole dataset/research question.",
        "Evidence E (PDF pp. 1407–1410): theme definition, selection and interpretation of extracts, "
        "and recursive reporting are described.",
        "All evidence excerpts are paraphrases, not copied article text. Empirical details from this single "
        "study are not presented as universal sample-size or workflow requirements.",
        "The local evidence file is a curated paraphrase snapshot; its SHA-256 is separate from the publisher PDF hash.",
    ]
    evidence_text = "\n".join(evidence_lines) + "\n"
    EVIDENCE_SNAPSHOT.write_bytes(evidence_text.encode("utf-8"))
    evidence_snapshot_sha = digest(evidence_text.encode("utf-8"))

    for task in TASKS:
        task["excerpt_sha256"] = digest(task["text"].encode("utf-8"))
        source["anchors"].append({
            "anchor_id": task["anchor_id"],
            "kind": "page",
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
        expected_inputs = {"source.json", "approved_sources.json", "excerpt.json"}
        if input_dir.exists() and {path.name for path in input_dir.iterdir()} - expected_inputs:
            raise FileExistsError(f"unexpected files in {input_dir}")
        if job_dir.exists() and any(job_dir.iterdir()):
            raise FileExistsError(f"unexpected files in {job_dir}")
        input_dir.mkdir(parents=True, exist_ok=True)
        job_dir.mkdir(parents=True, exist_ok=True)
        excerpt = {
            "source_id": SOURCE_ID,
            "source_version": source["version"],
            "source_sha256": SOURCE_SHA,
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
            "--expert-id", "exp-thematic-analysis",
            "--source-json", str(input_dir / "source.json"),
            "--excerpt-json", str(input_dir / "excerpt.json"),
            "--approved-sources-json", str(input_dir / "approved_sources.json"),
            "--output", str(bundle), "--job-id", job_id, "--ttl-minutes", "55",
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        if result.returncode:
            raise RuntimeError(f"{job_id} preparation failed: {result.stdout}\n{result.stderr}")
        prepared = json.loads(result.stdout)
        prepared.update({
            "batch_id": BATCH_ID,
            "bundle_path": bundle.relative_to(ROOT).as_posix(),
            "source_id": SOURCE_ID,
            "source_record_path": SOURCE_RECORD.relative_to(ROOT).as_posix(),
            "excerpt_path": (input_dir / "excerpt.json").relative_to(ROOT).as_posix(),
            "evidence_snapshot_path": EVIDENCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "evidence_snapshot_sha256": evidence_snapshot_sha,
            "source_sha256": SOURCE_SHA,
            "excerpt_sha256": task["excerpt_sha256"],
            "expert_id": "exp-thematic-analysis",
            "anchor_id": task["anchor_id"],
            "gpu": "NVIDIA A100",
            "model_reference": MODEL,
            "generation": 1,
            "status": "ready_for_user_started_colab",
        })
        template = (HERE / "jobs" / "b20260928t132500-03" / "colab_run_job.py").read_text(encoding="utf-8")
        template = template.replace("b20260928t132500-03", job_id)
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
        "expert_id": "exp-thematic-analysis",
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "source_license": "CC-BY-4.0",
        "source_document_sha256": SOURCE_SHA,
        "evidence_snapshot": {
            "path": EVIDENCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "sha256": evidence_snapshot_sha,
            "scope": "five source-linked methodological and study-context paraphrases; not verbatim article text",
        },
        "jobs": jobs,
    }
    write_json(manifest_path, manifest)
    run_template = (HERE / "run_b20260928t140200.py").read_text(encoding="utf-8")
    run_template = run_template.replace("b20260928t140200.json", f"{BATCH_ID}.json")
    run_template = run_template.replace("gurumoji-a100-groupstats-20260928-140200", SESSION)
    (HERE / f"run_{BATCH_ID}.py").write_text(run_template, encoding="utf-8")
    print(json.dumps({
        "batch_id": BATCH_ID,
        "session_name": SESSION,
        "source_document_sha256": SOURCE_SHA,
        "evidence_snapshot_sha256": evidence_snapshot_sha,
        "jobs": [{key: job[key] for key in (
            "job_id", "expert_id", "anchor_id", "bundle_path", "bundle_sha256", "excerpt_sha256", "deadline"
        )} for job in jobs],
    }, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
