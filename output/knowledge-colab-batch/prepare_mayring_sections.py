"""Prepare position-bound Mayring excerpts from the reviewed FQS PDF."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE_ID = "LIT-mayring-2000-qca"
PDF = HERE / "mayring-2000.pdf"
NOTE = ROOT / "docs/program-vault/50-Analysis-Methods/20-Literature" / f"{SOURCE_ID}.md"
TARGET = HERE / "inputs" / SOURCE_ID


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(value: str) -> str:
    return " ".join(re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", value).split())


def main() -> None:
    meta = yaml.safe_load(NOTE.read_text(encoding="utf-8-sig").split("---", 2)[1])
    assert meta["literature_id"] == SOURCE_ID and meta["status"] == "current"
    assert meta["correction_status"] == "none_found" and meta["rights_review_status"] == "approved"
    assert meta["access_scope"] == "full_text" and "colab" in meta["llm_allowed_routes"]
    raw = PDF.read_bytes()
    assert raw.startswith(b"%PDF-") and sha(raw) == meta["document_sha256"]
    pages = [page.extract_text() or "" for page in PdfReader(PDF).pages]
    assert len(pages) == 10
    p3, p4, p5, p8 = pages[2], pages[3], pages[4], pages[7]
    sections = [
        ("principles", "3", p3[p3.index("3. Basic Ideas of Content Analysis"):p3.index("4. Procedures of Qualitative Content Analysis")]),
        ("inductive", "4", p4[p4.index("The specific steps cannot be explained"):p4.index("4.2 Deductive category application")]),
        ("deductive", "5", p5[p5.index("Then main idea here"):p5.index("Category Definition Examples Coding Rules")]),
        ("integration", "8", p8[p8.index("7. Discussion"):p8.index("The procedures of qualitative content analysis seem less appropriate")]),
        ("limits", "8", p8[p8.index("The procedures of qualitative content analysis seem less appropriate"):p8.index("References")]),
    ]
    anchors = []
    excerpts = []
    for anchor_id, page, fragment in sections:
        text = normalize(fragment)
        assert 150 < len(text) < 4000, (anchor_id, len(text))
        digest = sha(text.encode("utf-8"))
        anchors.append({"anchor_id": anchor_id, "kind": "page", "start": page,
                        "end": page, "extracted_text_sha256": digest})
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
        "adaptation_notice": "FQS PDF text extracted with pypdf; bounded paragraphs have line-wrap hyphens and whitespace normalized; figures and tables excluded.",
    }
    TARGET.mkdir(parents=True, exist_ok=True)
    (TARGET / "source.json").write_text(json.dumps(source, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (TARGET / "approved_sources.json").write_text(json.dumps(
        {"schema_version": 1, "sources": [source]}, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    for excerpt in excerpts:
        (TARGET / f"excerpt-{excerpt['anchor_id']}.json").write_text(
            json.dumps(excerpt, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(json.dumps({"source_id": SOURCE_ID, "pdf_sha256": sha(raw),
                      "anchors": [(a["anchor_id"], a["start"]) for a in anchors]}, sort_keys=True))


if __name__ == "__main__":
    main()
