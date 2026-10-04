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
BATCH_ID = "b20260928t143300"
SESSION = "gurumoji-a100-crosssession-20260928-143300"
MODEL = "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8"
SOURCE_ID = "LIT-poliandri-2023-online-focus-groups"
SOURCE_SHA = "ceff84c3d635dcc5f9ed70218851055e907d97817e13d92250b5a75ffd66058c"
SOURCE_URL = "https://www.frontiersin.org/journals/sociology/articles/10.3389/fsoc.2023.1145264/full"
SOURCE_REGISTRY = (
    HERE / "jobs" / "b20260928t025516-03" /
    "Gurumoji_Job_b20260928t025516-03_g1.local-approved-sources.json"
)
SOURCE_RECORD = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-source.json"
EVIDENCE_SNAPSHOT = HERE / "sources-20260928" / f"{BATCH_ID}-{SOURCE_ID}-selected-evidence.txt"
TASKS = [
    {
        "job_id": f"{BATCH_ID}-01",
        "anchor_id": "cross-session-study-group-composition",
        "start": "Composition of the study's 13 online focus groups",
        "end": "Four principal groups and nine teacher groups",
        "text": (
            "In this Italian online synchronous focus-group study, the researchers held 13 groups from late March "
            "through May 2020: four groups with school principals and nine with teachers. This is the design of "
            "the reported study, not a general recommendation for the number of groups."
        ),
    },
    {
        "job_id": f"{BATCH_ID}-02",
        "anchor_id": "cross-session-uniform-protocol",
        "start": "A common protocol for focus groups on different days",
        "end": "Same script and outline across the study's groups",
        "text": (
            "In this study, a management protocol was used to keep focus groups held on different days with "
            "different participants more uniform. The same script and outline guided discussion in each group. "
            "This reports one study's procedure and does not establish a universal comparison standard."
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
        raise RuntimeError("approved Poliandri Source registry mismatch")
    source = copy.deepcopy(matches[0])
    if source["sha256"] != SOURCE_SHA or source["locator"]["value"] != "10.3389/fsoc.2023.1145264":
        raise RuntimeError("approved Poliandri Source hash or DOI mismatch")
    if source["rights"]["classification"] != "licensed" or "colab" not in source["rights"]["allowed_routes"]:
        raise RuntimeError("Colab processing is not allowed by the approved Source registry")
    if source["license"]["license_id"] != "CC-BY-4.0":
        raise RuntimeError("unexpected Poliandri license")
    source["adaptation_notice"] = (
        "Two study-scoped design facts paraphrased from the selected publisher article section 4.2.2. "
        "No participant transcripts, personal data, or verbatim passages are included."
    )
    evidence_text = "\n".join([
        "Poliandri, D., Perazzolo, M., Pillera, G. C., & Giampietro, L. (2023). Dematerialized participation challenges: Methods and practices for online focus groups. Frontiers in Sociology, 8, 1145264.",
        f"Publisher article: {SOURCE_URL}",
        f"Document SHA-256: {SOURCE_SHA}. License: CC BY 4.0; attributed paraphrases only.",
        "Evidence paraphrase A: the Italian study conducted 13 synchronous online focus groups from late March through May 2020, comprising four groups with principals and nine with teachers.",
        "Evidence paraphrase B: the study used a common management protocol for sessions held on different days with different participants, and used the same script and outline for every group.",
        "These statements describe one published study's design and procedure. They do not establish a universal number-of-groups threshold or a validated general comparison method.",
        "This local evidence file contains curated paraphrases, not verbatim article text; its hash is separate from the publisher PDF hash.",
    ]) + "\n"
    EVIDENCE_SNAPSHOT.write_bytes(evidence_text.encode("utf-8"))
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
            "--expert-id", "exp-cross-session-comparison",
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
            "expert_id": "exp-cross-session-comparison",
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
        "expert_id": "exp-cross-session-comparison",
        "source_id": SOURCE_ID,
        "source_url": SOURCE_URL,
        "source_license": "CC-BY-4.0",
        "source_document_sha256": SOURCE_SHA,
        "evidence_snapshot": {
            "path": EVIDENCE_SNAPSHOT.relative_to(ROOT).as_posix(),
            "sha256": evidence_snapshot_sha,
            "scope": "selected study-design paraphrases; not verbatim article text",
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
