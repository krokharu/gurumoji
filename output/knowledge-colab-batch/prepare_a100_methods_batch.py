"""Prepare hash-bound A100 Claim jobs from six rights-reviewed sources."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE_DIR = HERE / "sources-20260928"
BATCH_ID = "b" + datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%S")
LICENSES = {
    "CC-BY-4.0": ("https://creativecommons.org/licenses/by/4.0/",
                  "CC BY 4.0; attribution and change indication required"),
    "MIT": ("https://opensource.org/license/mit/",
            "MIT License; preserve copyright and permission notice"),
    "BSD-3-Clause": ("https://opensource.org/license/bsd-3-clause/",
                     "BSD 3-Clause License; preserve notices and conditions"),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<=[A-Za-z])[-\u2010]\s*\n\s*(?=[a-z])", "", text)
    return " ".join(text.split())


def pdf_pages(filename: str) -> tuple[bytes, list[str]]:
    raw = (SOURCE_DIR / filename).read_bytes()
    if not raw.startswith(b"%PDF-"):
        raise ValueError(f"not a PDF: {filename}")
    reader = PdfReader(SOURCE_DIR / filename)
    if reader.is_encrypted:
        raise ValueError(f"encrypted PDF is out of scope: {filename}")
    return raw, [normalize(page.extract_text() or "") for page in reader.pages]


def markdown_section(filename: str, start: str, end: str) -> str:
    text = (SOURCE_DIR / filename).read_text(encoding="utf-8")
    left = text.index(start)
    right = text.index(end, left + len(start))
    excerpt = normalize(text[left:right])
    if not 100 <= len(excerpt) <= 8000:
        raise ValueError(f"unexpected excerpt length for {filename}: {len(excerpt)}")
    return excerpt


def html_section(filename: str, section_id: str) -> str:
    soup = BeautifulSoup((SOURCE_DIR / filename).read_bytes(), "html.parser")
    section = soup.find("section", id=section_id)
    if section is None:
        raise ValueError(f"missing documented section: {section_id}")
    return normalize(section.get_text(" ", strip=True))


def slice_between(text: str, start: str, end: str) -> str:
    left = text.index(start)
    right = text.index(end, left + len(start))
    excerpt = normalize(text[left:right])
    if not 100 <= len(excerpt) <= 8000:
        raise ValueError(f"unexpected selected excerpt length: {len(excerpt)}")
    return excerpt


def build_source(source_id: str, title: str, authors: list[str], year: int | None,
                 source_type: str, locator: dict, scope: str, version: str,
                 raw: bytes, license_id: str, adaptation: str,
                 anchor_specs: list[tuple[str, str, str, str]]) -> tuple[dict, dict[str, dict]]:
    license_url, license_terms = LICENSES[license_id]
    excerpts: dict[str, dict] = {}
    anchors = []
    for anchor_id, kind, start, end in anchor_specs:
        text = end
        text_hash = sha(text.encode("utf-8"))
        anchor = {"anchor_id": anchor_id, "kind": kind, "start": start, "end": start,
                  "extracted_text_sha256": text_hash}
        anchors.append(anchor)
        excerpts[anchor_id] = {"source_id": source_id, "source_version": version,
                               "source_sha256": sha(raw), "anchor_id": anchor_id,
                               "extracted_text_sha256": text_hash, "text": text}
    source = {
        "schema_version": 1, "source_id": source_id, "version": version,
        "sha256": sha(raw), "title": title, "authors": authors,
        "source_type": source_type, "locator": locator, "access_scope": scope,
        "license": {"license_id": license_id, "terms": license_terms},
        "license_url": {"kind": "https", "value": license_url},
        "anchors": anchors,
        "rights": {"classification": "licensed", "allowed_routes": ["local", "colab", "export"]},
        "adaptation_notice": adaptation,
    }
    if year is not None:
        source["publication_year"] = year
    return source, excerpts


def save_inputs(source: dict, excerpts: dict[str, dict]) -> Path:
    target = HERE / "inputs" / BATCH_ID / source["source_id"]
    target.mkdir(parents=True, exist_ok=True)
    (target / "source.json").write_text(json.dumps(source, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (target / "approved_sources.json").write_text(
        json.dumps({"schema_version": 1, "sources": [source]}, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    for anchor_id, excerpt in excerpts.items():
        (target / f"excerpt-{anchor_id}.json").write_text(
            json.dumps(excerpt, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return target


def sources_and_excerpts() -> list[tuple[dict, dict[str, dict], str, str]]:
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    result = []

    raw, pages = pdf_pages("timing-2015.pdf")
    assert len(pages) == 17 and sha(raw) == "bda17c1efd9ad7914fca32e9b444141b2a7c6fc5f55ffc37678b08627205dd96"
    source, excerpts = build_source(
        "LIT-levinson-torreira-2015-timing",
        "Timing in turn-taking and its implications for processing models of language",
        ["Stephen C. Levinson", "Francisco Torreira"], 2015, "paper",
        {"kind": "doi", "value": "10.3389/fpsyg.2015.00731"}, "full_text",
        "publisher-vor-frontiers-retrieved-2026-09-28-sha256-bda17c1efd9ad791", raw, "CC-BY-4.0",
        "Official publisher PDF text extracted with pypdf; line breaks and whitespace normalized; selected pages only.",
        [("abstract", "page", "1", pages[0]), ("gap-distribution", "page", "6", pages[5])])
    result.append((source, excerpts, "exp-conversation-timing", "LIT-levinson-torreira-2015-timing"))

    raw, pages = pdf_pages("participation-2023.pdf")
    assert len(pages) == 18 and sha(raw) == "ceff84c3d635dcc5f9ed70218851055e907d97817e13d92250b5a75ffd66058c"
    source, excerpts = build_source(
        "LIT-poliandri-2023-online-focus-groups",
        "Dematerialized participation challenges: Methods and practices for online focus groups",
        ["Donatella Poliandri", "Monica Perazzolo", "Giuseppe Carmelo Pillera", "Letizia Giampietro"],
        2023, "paper", {"kind": "doi", "value": "10.3389/fsoc.2023.1145264"}, "full_text",
        "publisher-vor-frontiers-retrieved-2026-09-28-sha256-ceff84c3d635dcc5", raw, "CC-BY-4.0",
        "Official publisher PDF text extracted with pypdf; line breaks and whitespace normalized; selected pages only; table layout requires visual verification.",
        [("participation-measures", "page", "13", pages[12]),
         ("study-context", "page", "14", pages[13])])
    result.append((source, excerpts, "exp-participation-balance", "LIT-poliandri-2023-online-focus-groups"))

    ginza_raw = (SOURCE_DIR / "ginza-v5.2.0-README.md").read_bytes()
    assert sha(ginza_raw) == "71652a6e50e94ee71020d16b38dd7e67a2c679149a2622a83fe9ef8615ec2dc7"
    ginza_text = ginza_raw.decode("utf-8")
    ginza_licenses = markdown_section("ginza-v5.2.0-README.md", "## License", "## Training Datasets")
    ginza_data = markdown_section("ginza-v5.2.0-README.md", "## Training Datasets", "## Runtime Environment")
    source, excerpts = build_source(
        "RES-ginza-official", "GiNZA - Japanese NLP Library（公式README v5.2.0）", ["Megagon Labs"], None, "web",
        {"kind": "url", "value": "https://github.com/megagonlabs/ginza/blob/v5.2.0/README.md"},
        "official_page", "github-v5.2.0-readme-retrieved-2026-09-28-sha256-71652a6e50e94ee7", ginza_raw, "MIT",
        "Versioned official README only. Dependency software, model weights, corpus data, and linked third-party content are excluded.",
        [("license-and-dependencies", "section", "License", ginza_licenses),
         ("training-data-description", "section", "Training Datasets", ginza_data)])
    result.append((source, excerpts, "exp-japanese-text-preprocessing", "RES-ginza-official"))

    bert_raw = (SOURCE_DIR / "bertopic-v0.17.4-algorithm.md").read_bytes()
    assert sha(bert_raw) == "952f766df6f0030ecc5db2effdf136778372825bd1e675973d78701715df35dc"
    overview = markdown_section("bertopic-v0.17.4-algorithm.md", "# The Algorithm", "## **Detailed Overview**")
    bert_text = bert_raw.decode("utf-8")
    ctfidf_start = bert_text.index("###  **5. Topic representation")
    ctfidf_end = bert_text.index("### **6. (Optional)", ctfidf_start)
    ctfidf = normalize(bert_text[ctfidf_start:ctfidf_end])
    source, excerpts = build_source(
        "RES-bertopic-official", "BERTopic v0.17.4 algorithm documentation", ["Maarten Grootendorst"],
        2025, "web", {"kind": "url", "value": "https://github.com/MaartenGr/BERTopic/blob/v0.17.4/docs/algorithm/algorithm.md"},
        "official_page", "github-v0.17.4-algorithm-retrieved-2026-09-28-sha256-952f766df6f0030e", bert_raw, "MIT",
        "Pinned official algorithm documentation only. Model weights, datasets, and other dependencies are excluded.",
        [("pipeline-overview", "section", "The Algorithm / Visual Overview / Code Overview", overview),
         ("class-tfidf", "section", "5. Topic representation", ctfidf)])
    result.append((source, excerpts, "exp-embedding-topic-exploration", "RES-bertopic-official"))

    pearson_raw = (SOURCE_DIR / "scipy-1.18.0-pearsonr.html").read_bytes()
    assert sha(pearson_raw) == "9999856b875cf15abcad22654b16bd3d2801f89eef28b42a048114e93eac68c3"
    pearson = html_section("scipy-1.18.0-pearsonr.html", "pearsonr")
    pearson_linear = slice_between(pearson, "The Pearson correlation coefficient", "Parameters :")
    pearson_independence = slice_between(pearson, "It is important to keep in mind that no correlation", "For a more detailed example")
    pearson_test = slice_between(pearson, "This function also performs a test", "Parameters :")
    source, excerpts = build_source(
        "RES-scipy-pearsonr", "SciPy v1.18.0 stats.pearsonr API reference", ["SciPy community"],
        2026, "web", {"kind": "url", "value": "https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.pearsonr.html"},
        "official_page", "scipy-v1.18.0-manual-pearsonr-retrieved-2026-09-28", pearson_raw, "BSD-3-Clause",
        "Pinned official SciPy API documentation page only; no user or research data is included.",
        [("linear-correlation", "section", "pearsonr description", pearson_linear),
         ("zero-correlation-limit", "section", "pearsonr Notes: non-correlation", pearson_independence),
         ("test-assumptions", "section", "pearsonr null hypothesis", pearson_test)])
    result.append((source, excerpts, "exp-correlation", "RES-scipy-pearsonr"))

    describe_raw = (SOURCE_DIR / "scipy-1.18.0-describe.html").read_bytes()
    assert sha(describe_raw) == "66566c9dfdc18383000a0badfd29d550f8073edfd85c2686f8162d299e84960a"
    describe = html_section("scipy-1.18.0-describe.html", "describe")
    source, excerpts = build_source(
        "RES-scipy-describe", "SciPy v1.18.0 stats.describe API reference", ["SciPy community"],
        2026, "web", {"kind": "url", "value": "https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.describe.html"},
        "official_page", "scipy-v1.18.0-manual-describe-retrieved-2026-09-28", describe_raw, "BSD-3-Clause",
        "Pinned official SciPy API documentation page only; no user or research data is included.",
        [("describe-api", "section", "scipy.stats.describe", describe)])
    result.append((source, excerpts, "exp-descriptive-statistics", "RES-scipy-describe"))
    return result


def main() -> None:
    manifest_jobs = []
    index = 0
    for source, excerpts, expert_id, source_id in sources_and_excerpts():
        input_dir = save_inputs(source, excerpts)
        for anchor_id, excerpt in excerpts.items():
            index += 1
            job_id = f"{BATCH_ID}-{index:02d}"
            job_dir = HERE / "jobs" / job_id
            job_dir.mkdir(parents=True, exist_ok=False)
            bundle = job_dir / f"Gurumoji_Job_{job_id}_g1.zip"
            command = [
                sys.executable, str(ROOT / "scripts/prepare_colab_claim_job.py"),
                "--data-dir", str(HERE / "state"), "--expert-id", expert_id,
                "--source-json", str(input_dir / "source.json"),
                "--excerpt-json", str(input_dir / f"excerpt-{anchor_id}.json"),
                "--approved-sources-json", str(input_dir / "approved_sources.json"),
                "--output", str(bundle), "--job-id", job_id, "--ttl-minutes", "55",
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode:
                raise RuntimeError(f"{job_id}: {completed.stdout} {completed.stderr}")
            record = json.loads(completed.stdout)
            record.update({"bundle_path": bundle.relative_to(ROOT).as_posix(),
                           "source_id": source_id, "expert_id": expert_id, "anchor_id": anchor_id})
            manifest_jobs.append(record)
    manifest = {"batch_id": BATCH_ID, "created_at": datetime.now(timezone.utc).isoformat(),
                "jobs": manifest_jobs}
    path = HERE / f"{BATCH_ID}.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps({"batch_id": BATCH_ID, "jobs": len(manifest_jobs),
                      "manifest": path.relative_to(ROOT).as_posix()}, sort_keys=True))


if __name__ == "__main__":
    main()
