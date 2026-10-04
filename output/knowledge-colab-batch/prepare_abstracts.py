"""Prepare reviewed abstract excerpts for the bounded Colab Claim worker."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
NOTES = ROOT / "docs/program-vault/50-Analysis-Methods/20-Literature"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def note(source_id: str) -> dict:
    content = (NOTES / f"{source_id}.md").read_text(encoding="utf-8-sig")
    meta = yaml.safe_load(content.split("---", 2)[1])
    assert meta["literature_id"] == source_id
    assert meta["status"] == "current"
    assert meta["correction_status"] == "none_found"
    assert meta["access_scope"] == "abstract"
    assert meta["rights_review_status"] == "approved"
    assert meta["llm_processing_permission"] == "explicitly_permitted"
    assert {"local", "colab", "export"} <= set(meta["llm_allowed_routes"])
    assert meta["license_id"] == "CC-BY-4.0"
    return meta


def save(source_id: str, raw: bytes, abstract: str, *, origin: str) -> None:
    meta = note(source_id)
    abstract = " ".join(abstract.split())
    assert 300 <= len(abstract) <= 4000
    assert abstract.count("�") == 0
    original_hash = sha(raw)
    abstract_hash = sha(abstract.encode("utf-8"))
    source = {
        "schema_version": 1, "source_id": source_id,
        "version": f"{origin}-abstract-sha256-{original_hash[:16]}",
        "sha256": original_hash, "title": meta["title"], "authors": meta["authors"],
        "publication_year": meta["year"], "source_type": "paper",
        "locator": {"kind": "doi", "value": meta["doi"]},
        "access_scope": "abstract",
        "license": {"license_id": meta["license_id"],
                    "terms": f"{meta['license_id']} ({meta['license_url']}); attribution required"},
        "license_url": {"kind": "https", "value": meta["license_url"]},
        "anchors": [{"anchor_id": "abstract", "kind": "section", "start": "Abstract",
                     "end": "Abstract", "extracted_text_sha256": abstract_hash}],
        "rights": {"classification": "licensed", "allowed_routes": ["local", "colab", "export"]},
        "adaptation_notice": "Only the abstract extracted from the verified original is used for draft Claim generation.",
    }
    excerpt = {
        "source_id": source_id, "source_version": source["version"],
        "source_sha256": source["sha256"], "anchor_id": "abstract",
        "extracted_text_sha256": abstract_hash, "text": abstract,
    }
    target = HERE / "inputs" / source_id
    target.mkdir(parents=True, exist_ok=True)
    for filename, value in (("source.json", source), ("excerpt.json", excerpt),
                            ("approved_sources.json", {"schema_version": 1, "sources": [source]})):
        (target / filename).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(json.dumps({"source_id": source_id, "original_sha256": original_hash,
                      "abstract_sha256": abstract_hash, "abstract_chars": len(abstract)}, sort_keys=True))


def main() -> None:
    byrne = (HERE / "byrne-2022.pdf").read_bytes()
    assert byrne.startswith(b"%PDF-")
    page = PdfReader(HERE / "byrne-2022.pdf").pages[0].extract_text()
    abstract = page.split("Abstract\n", 1)[1].split("\nKeywords ", 1)[0]
    abstract = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", abstract)
    save("LIT-byrne-2022-reflexive-ta", byrne, abstract, origin="publisher-pdf")

    gilardi = (HERE / "gilardi-2023.xml").read_bytes()
    root = ET.fromstring(gilardi)
    article_id = root.find(".//article-id[@pub-id-type='pmcid']")
    assert article_id is not None and article_id.text == "PMC10372638"
    abstract_node = root.find(".//abstract")
    assert abstract_node is not None
    abstract = "".join(abstract_node.itertext())
    save("LIT-gilardi-2023-llm-annotation", gilardi, abstract, origin="europepmc-xml")


if __name__ == "__main__":
    main()
