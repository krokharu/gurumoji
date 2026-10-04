"""Prepare one bounded, abstract-only Colab pilot from a reviewed source note."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
NOTE = ROOT / "docs/program-vault/50-Analysis-Methods/20-Literature/LIT-hermann-2024-fg-interaction-coding.md"
PDF = HERE / "hermann-2024.pdf"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


raw_note = NOTE.read_text(encoding="utf-8-sig")
frontmatter = raw_note.split("---", 2)[1]
meta = yaml.safe_load(frontmatter)
assert meta["literature_id"] == "LIT-hermann-2024-fg-interaction-coding"
assert meta["access_scope"] == "abstract"
assert meta["status"] == "current" and meta["correction_status"] == "none_found"
assert meta["rights_review_status"] == "approved"
assert meta["llm_processing_permission"] == "explicitly_permitted"
assert "colab" in meta["llm_allowed_routes"]
assert meta["doi"] == "10.1177/16094069241286848"
assert meta["license_id"] == "CC-BY-4.0"
assert "exp-focus-group-interaction" in meta["related_experts"]

pdf_bytes = PDF.read_bytes()
assert pdf_bytes.startswith(b"%PDF-")
pdf_hash = sha256(pdf_bytes)
page = PdfReader(PDF).pages[0].extract_text() or ""
parts = page.split("\nAbstract\n", 1)
assert len(parts) == 2
abstract_parts = parts[1].split("\nKeywords\n", 1)
assert len(abstract_parts) == 2
abstract = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", abstract_parts[0])
abstract = " ".join(abstract.split())
assert 1000 <= len(abstract) <= 3000
assert "focus group interactions" in abstract.lower()
abstract_hash = sha256(abstract.encode("utf-8"))

source = {
    "schema_version": 1,
    "source_id": meta["literature_id"],
    "version": "repository-pdf-abstract-sha256-" + pdf_hash[:16],
    "sha256": pdf_hash,
    "title": meta["title"],
    "authors": meta["authors"],
    "publication_year": meta["year"],
    "source_type": "paper",
    "locator": {"kind": "doi", "value": meta["doi"]},
    "access_scope": "abstract",
    "license": {
        "license_id": meta["license_id"],
        "terms": f"{meta['license_id']} ({meta['license_url']}); attribution required",
    },
    "license_url": {"kind": "https", "value": meta["license_url"]},
    "anchors": [{
        "anchor_id": "abstract",
        "kind": "section",
        "start": "Abstract",
        "end": "Abstract",
        "extracted_text_sha256": abstract_hash,
    }],
    "rights": {"classification": "licensed", "allowed_routes": ["local", "colab", "export"]},
    "adaptation_notice": "Pilot uses only the abstract extracted from the university-hosted author paper PDF.",
}
excerpt = {
    "source_id": source["source_id"],
    "source_version": source["version"],
    "source_sha256": source["sha256"],
    "anchor_id": "abstract",
    "extracted_text_sha256": abstract_hash,
    "text": abstract,
}

for name, value in (
    ("source.json", source),
    ("excerpt.json", excerpt),
    ("approved_sources.json", {"schema_version": 1, "sources": [source]}),
):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")
print(json.dumps({"source_id": source["source_id"], "pdf_sha256": pdf_hash,
                  "abstract_sha256": abstract_hash, "abstract_chars": len(abstract)}, sort_keys=True))
