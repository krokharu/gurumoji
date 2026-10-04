"""Build page-bound Gale stage excerpts from the newly pinned publisher PDF."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE_ID = "LIT-gale-2013-framework"
PDF = HERE / "gale-2013-publisher.pdf"
NOTE = ROOT / "docs/program-vault/50-Analysis-Methods/20-Literature" / f"{SOURCE_ID}.md"
TARGET = HERE / "inputs" / SOURCE_ID


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(value: str) -> str:
    value = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", value)
    return " ".join(value.split())


def main() -> None:
    meta = yaml.safe_load(NOTE.read_text(encoding="utf-8-sig").split("---", 2)[1])
    assert meta["literature_id"] == SOURCE_ID
    assert meta["rights_review_status"] == "approved" and meta["correction_status"] == "none_found"
    assert meta["access_scope"] == "full_text" and "colab" in meta["llm_allowed_routes"]
    raw = PDF.read_bytes()
    assert raw.startswith(b"%PDF-") and sha(raw) == meta["document_sha256"]
    pages = [page.extract_text() or "" for page in PdfReader(PDF).pages]
    assert len(pages) == 8
    p4, p5, p7 = pages[3], pages[4], pages[6]
    marks4 = [p4.index(f"Stage {number}:") for number in range(1, 5)]
    marks5 = [p5.index(f"Stage {number}:") for number in range(5, 8)]
    footer = "Gale et al. BMC Medical Research Methodology 2013, 13:117 Page 4 of 8"
    fragments = [
        ("stage-1", "4", "4", p4[marks4[0]:marks4[1]]),
        ("stage-2", "4", "4", p4[marks4[1]:marks4[2]]),
        ("stage-3", "4", "4", p4[marks4[2]:marks4[3]]),
        ("stage-4", "4", "5", p4[marks4[3]:p4.index(footer)] + " " + p5[:marks5[0]]),
        ("stage-5", "5", "5", p5[marks5[0]:marks5[1]]),
        ("stage-6", "5", "5", p5[marks5[1]:marks5[2]]),
        ("stage-7", "5", "5", p5[marks5[2]:p5.index("\nDiscussion", marks5[2])]),
        ("summary", "7", "7", p7[p7.index("Summary\n"):p7.index("Additional files")]),
    ]
    excerpts = []
    anchors = []
    for anchor_id, start, end, raw_text in fragments:
        text = normalized(raw_text.replace("/C15", ""))
        assert 100 < len(text) < 4000, (anchor_id, len(text))
        digest = sha(text.encode("utf-8"))
        anchors.append({"anchor_id": anchor_id, "kind": "page", "start": start,
                        "end": end, "extracted_text_sha256": digest})
        excerpts.append({"source_id": SOURCE_ID, "source_version": meta["document_version"],
                         "source_sha256": meta["document_sha256"], "anchor_id": anchor_id,
                         "extracted_text_sha256": digest, "text": text})
    source = {
        "schema_version": 1, "source_id": SOURCE_ID, "version": meta["document_version"],
        "sha256": meta["document_sha256"], "title": meta["title"], "authors": meta["authors"],
        "publication_year": meta["year"], "source_type": "paper",
        "locator": {"kind": "doi", "value": meta["doi"]}, "access_scope": "full_text",
        "license": {"license_id": meta["license_id"],
                    "terms": f"{meta['license_id']} ({meta['license_url']}); attribution required"},
        "license_url": {"kind": "https", "value": meta["license_url"]},
        "anchors": anchors,
        "rights": {"classification": "licensed", "allowed_routes": ["local", "colab", "export"]},
        "adaptation_notice": "Publisher PDF text extracted with pypdf; line-wrap hyphens and page 4 footer removed from bounded excerpts; figure/table content not included.",
    }
    TARGET.mkdir(parents=True, exist_ok=True)
    (TARGET / "source.json").write_text(json.dumps(source, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (TARGET / "approved_sources.json").write_text(json.dumps(
        {"schema_version": 1, "sources": [source]}, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    for excerpt in excerpts:
        (TARGET / f"excerpt-{excerpt['anchor_id']}.json").write_text(
            json.dumps(excerpt, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(json.dumps({"source_id": SOURCE_ID, "pdf_sha256": sha(raw),
                      "anchors": [(item["anchor_id"], item["start"], item["end"])
                                  for item in anchors]}, sort_keys=True))


if __name__ == "__main__":
    main()
