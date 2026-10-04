"""Prepare source-bound A100 Claim jobs from the reviewed IRSP correction."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE_ID = "LIT-delacre-2022-correction"
PDF = HERE / "delacre-2022-correction.pdf"
EXPECTED_PDF_SHA256 = "747dc11c7ca447a22ab85b33bbc83dbf871a8ea4cdb1a22e2569d67ced667260"
SOURCE_VERSION = "official-publisher-pdf-2022-11-25"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(value: str) -> str:
    value = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", value)
    return " ".join(value.split())


def main() -> None:
    raw = PDF.read_bytes()
    if sha(raw) != EXPECTED_PDF_SHA256:
        raise ValueError("publisher PDF hash differs from the reviewed document")
    pages = [page.extract_text() or "" for page in PdfReader(PDF).pages]
    if len(pages) != 3:
        raise ValueError("publisher PDF page count changed")
    page = pages[1]
    boundaries = [
        ("main-message", "Since the publication", "In p.93,"),
        ("ratio-definitions", "In p.93,", "In Table 1"),
        ("equality-condition", "In Table 1", "Finally, although not visible"),
        ("simulation-limitations", "Finally, although not visible", "COMPETING INTERESTS"),
    ]
    excerpts = []
    anchors = []
    for anchor_id, start, end in boundaries:
        text = normalize(page[page.index(start):page.index(end)])
        if len(text) < 150 or len(text) > 8_000:
            raise ValueError(f"unexpected excerpt length for {anchor_id}: {len(text)}")
        text_sha256 = sha(text.encode("utf-8"))
        anchors.append({"anchor_id": anchor_id, "kind": "page", "start": "2", "end": "2",
                        "extracted_text_sha256": text_sha256})
        excerpts.append({"source_id": SOURCE_ID, "source_version": SOURCE_VERSION,
                         "source_sha256": EXPECTED_PDF_SHA256, "anchor_id": anchor_id,
                         "extracted_text_sha256": text_sha256, "text": text})

    source = {
        "schema_version": 1,
        "source_id": SOURCE_ID,
        "version": SOURCE_VERSION,
        "sha256": EXPECTED_PDF_SHA256,
        "title": "Correction: Why Psychologists Should by Default Use Welch’s t-test Instead of Student’s t-test",
        "authors": ["Marie Delacre", "Daniël Lakens", "Christophe Leys"],
        "publication_year": 2022,
        "source_type": "paper",
        "locator": {"kind": "doi", "value": "10.5334/irsp.661"},
        "access_scope": "full_text",
        "license": {"license_id": "CC-BY-4.0",
                    "terms": "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); attribution required"},
        "license_url": {"kind": "https", "value": "https://creativecommons.org/licenses/by/4.0/"},
        "anchors": anchors,
        "rights": {"classification": "licensed", "allowed_routes": ["local", "colab", "export"]},
        "adaptation_notice": "Official publisher PDF text extracted with pypdf; line breaks and whitespace normalized; selected passages from page 2 only; formula layout may be flattened.",
    }

    source_dir = HERE / "inputs" / SOURCE_ID
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "source.json").write_text(
        json.dumps(source, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (source_dir / "approved_sources.json").write_text(
        json.dumps({"schema_version": 1, "sources": [source]}, ensure_ascii=False, sort_keys=True),
        encoding="utf-8")
    for excerpt in excerpts:
        (source_dir / f"excerpt-{excerpt['anchor_id']}.json").write_text(
            json.dumps(excerpt, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    batch_id = "b" + datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%S")
    jobs = []
    for index, excerpt in enumerate(excerpts, 1):
        job_id = f"{batch_id}-{index:02d}"
        job_dir = HERE / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        bundle = job_dir / f"Gurumoji_Job_{job_id}_g1.zip"
        completed = subprocess.run([
            sys.executable, str(ROOT / "scripts/prepare_colab_claim_job.py"),
            "--data-dir", str(HERE / "state"),
            "--expert-id", "exp-group-comparison-statistics",
            "--source-json", str(source_dir / "source.json"),
            "--excerpt-json", str(source_dir / f"excerpt-{excerpt['anchor_id']}.json"),
            "--approved-sources-json", str(source_dir / "approved_sources.json"),
            "--output", str(bundle), "--job-id", job_id, "--ttl-minutes", "55",
        ], capture_output=True, text=True, check=False)
        if completed.returncode:
            raise RuntimeError(f"{job_id}: {completed.stdout} {completed.stderr}")
        record = json.loads(completed.stdout)
        record.update({"bundle_path": str(bundle.relative_to(ROOT)).replace("\\", "/"),
                       "source_id": SOURCE_ID, "expert_id": "exp-group-comparison-statistics",
                       "anchor_id": excerpt["anchor_id"]})
        jobs.append(record)

    manifest = {"batch_id": batch_id, "created_at": datetime.now(timezone.utc).isoformat(),
                "jobs": jobs}
    manifest_path = HERE / f"{batch_id}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
                             encoding="utf-8")
    print(json.dumps({"batch_id": batch_id, "jobs": len(jobs),
                      "manifest": str(manifest_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
