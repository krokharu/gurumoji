import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gurumoji.knowledge_builder import source_ingestion
from gurumoji.knowledge_builder.source_ingestion import (
    SOFTWARE_VAULT_ROOT, SourceIngestionError, _frontmatter, _timestamp_string,
    _validate_rights, ingest_local_document, ingest_user_selected_local_paper,
    read_local_evidence, search_local_papers, _local_title_without_path,
)


def _source(data: bytes, *, routes=("local",)):
    return {
        "schema_version": 1, "source_id": "source-local-fixture", "version": "v1",
        "sha256": hashlib.sha256(data).hexdigest(), "title": "Synthetic local article",
        "source_type": "paper", "locator": {"kind": "doi", "value": "10.1234/local"},
        "access_scope": "full_text", "license": {"license_id": "fixture", "terms": "Synthetic"},
        "license_url": {"kind": "https", "value": "https://example.org/license"},
        "anchors": [], "rights": {"classification": "licensed", "allowed_routes": list(routes)},
    }


def _review(routes=("local",)):
    return {
        "license_id": "fixture", "license_url": "https://example.org/license",
        "llm_processing_permission": "explicitly_permitted", "llm_allowed_routes": list(routes),
        "rights_review_status": "approved", "rights_reviewed_by": "fixture-reviewer",
        "rights_reviewed_at": "2026-01-01T00:00:00Z", "rights_review_basis": "synthetic license record",
    }


def _write_authority(root: Path, document: bytes, source_id="LIT-fixture", *, routes=("local",),
                     scope="full_text", review_status="approved", expected_hash=None,
                     source_status="current", correction_status="none_found"):
    literature = root / "50-Analysis-Methods" / "20-Literature"
    literature.mkdir(parents=True, exist_ok=True)
    (literature / f"{source_id}.md").write_text(
        "---\n"
        f"note_type: literature\nliterature_id: {source_id}\ntitle: Synthetic licensed source\n"
        f"document_version: fixture-v1\ndocument_sha256: {expected_hash or hashlib.sha256(document).hexdigest()}\n"
        "authors: [A. Fixture]\nyear: 2025\ndoi: 10.1234/fixture\n"
        "url: https://example.org/article\n"
        f"access_scope: {scope}\nlicense_id: fixture\nlicense_url: https://example.org/license\n"
        "llm_processing_permission: explicitly_permitted\n"
        "llm_allowed_routes:\n" + "".join(f"  - {route}\n" for route in routes) +
        f"rights_review_status: {review_status}\nrights_reviewed_by: reviewer\n"
        "rights_reviewed_at: 2026-01-01T00:00:00Z\nrights_review_basis: approved fixture\n"
        f"status: {source_status}\ncorrection_status: {correction_status}\n---\n"
        "Catalog note body is not an article.\n", encoding="utf-8")


def _minimal_pdf(pages):
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [" + b" ".join(
                   f"{4 + index * 2} 0 R".encode() for index in range(len(pages))) +
               f"] /Count {len(pages)} >>".encode(),
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    for page in pages:
        content = ("BT /F1 12 Tf 72 720 Td (" + page.replace("\\", "\\\\").replace("(", "\\(")
                   .replace(")", "\\)") + ") Tj ET").encode("ascii")
        content_id = len(objects) + 2
        page_id = content_id - 1
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                        f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>").encode())
        objects.append(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                  f"startxref\n{xref_offset}\n%%EOF\n".encode())
    return bytes(output)


class SourceIngestionTests(unittest.TestCase):
    def test_existing_review_notes_normalize_yaml_timestamp_scalars(self):
        for source_id in ("LIT-gale-2013-framework", "LIT-gilardi-2023-llm-annotation"):
            path = SOFTWARE_VAULT_ROOT / "50-Analysis-Methods" / "20-Literature" / f"{source_id}.md"
            props, _note_hash = _frontmatter(path)
            normalized = _timestamp_string(props["rights_reviewed_at"])
            self.assertTrue(normalized.endswith("Z") or "+" in normalized)
            self.assertEqual(props["rights_review_status"], "approved")
            self.assertEqual(props["status"], "current")
            self.assertEqual(props["correction_status"], "none_found")

    def test_text_deduplicates_paragraphs_and_is_reproducible_in_private_root(self):
        data = "First paragraph.\n\nRepeated text.\n\nRepeated text.\n".encode()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "local-paper.txt"
            input_path.write_bytes(data)
            _write_authority(root / "software", data, "LIT-fixture")
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                first = ingest_local_document("LIT-fixture", input_path, data_dir=root / "user-data")
                second = ingest_local_document("LIT-fixture", input_path, data_dir=root / "user-data")
                note = root / "software" / "50-Analysis-Methods" / "20-Literature" / "LIT-fixture.md"
                note.write_text(note.read_text(encoding="utf-8") + "Catalog revision.\n", encoding="utf-8")
                revised_authority = ingest_local_document("LIT-fixture", input_path, data_dir=root / "user-data")
            output = root / "user-data" / "knowledge_builder" / "private" / "source_extractions"
            stored = output / first["storage_id"]
            self.assertTrue(stored.is_dir())
            self.assertEqual((stored / "manifest.json").read_bytes(),
                              (output / second["storage_id"] / "manifest.json").read_bytes())
            self.assertNotEqual(first["storage_id"], revised_authority["storage_id"])
        self.assertEqual(first["manifest"]["original_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(first["manifest"]["extractor"]["name"], "utf8-paragraph-normalizer")
        self.assertEqual(first["manifest"]["anchor_count"], 3)
        self.assertEqual(first["manifest"]["duplicate_paragraph_count"], 1)
        repeated = next(item for item in first["excerpts"] if item["text"] == "Repeated text.")
        self.assertEqual(len(repeated["locations"]), 2)
        self.assertNotIn("local-paper.txt", json.dumps(first))

    def test_pdf_extraction_records_page_anchor_and_hashes(self):
        data = _minimal_pdf(["Page one evidence.", "Page two evidence."])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "pages.pdf"
            input_path.write_bytes(data)
            _write_authority(root / "software", data, "LIT-pdf")
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                result = ingest_local_document("LIT-pdf", input_path, data_dir=root / "data")
        self.assertEqual(result["manifest"]["extractor"]["name"], "pypdf")
        self.assertEqual(result["manifest"]["extractor"]["page_count"], 2)
        self.assertEqual(result["manifest"]["completeness"], "requires_human_review")
        self.assertEqual([item["status"] for item in result["manifest"]["extractor"]["page_extractions"]],
                         ["extracted", "extracted"])
        self.assertEqual([anchor["start"] for anchor in result["manifest"]["source"]["anchors"]], ["1", "2"])
        for excerpt, anchor in zip(result["excerpts"], result["manifest"]["source"]["anchors"]):
            self.assertEqual(excerpt["text"], "Page one evidence." if anchor["start"] == "1" else "Page two evidence.")
            self.assertEqual(hashlib.sha256(excerpt["text"].encode()).hexdigest(),
                              anchor["extracted_text_sha256"])

    def test_pdf_empty_page_is_recorded_as_incomplete_review(self):
        data = _minimal_pdf(["Page one evidence.", ""])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "partial.pdf"
            input_path.write_bytes(data)
            _write_authority(root / "software", data, "LIT-pdf-partial")
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                result = ingest_local_document("LIT-pdf-partial", input_path, data_dir=root / "data")
        pages = result["manifest"]["extractor"]["page_extractions"]
        self.assertEqual([item["status"] for item in pages], ["extracted", "empty"])
        self.assertEqual(result["manifest"]["completeness"], "requires_human_review")

    def test_pdf_page_extraction_error_is_recorded(self):
        data = _minimal_pdf(["Page one evidence.", "Page two unavailable."])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "page-error.pdf"
            input_path.write_bytes(data)
            _write_authority(root / "software", data, "LIT-pdf-error")
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                with patch("pypdf._page.PageObject.extract_text",
                           side_effect=["Page one evidence.", RuntimeError("synthetic parser error")]):
                    result = ingest_local_document("LIT-pdf-error", input_path, data_dir=root / "data")
        pages = result["manifest"]["extractor"]["page_extractions"]
        self.assertEqual([item["status"] for item in pages], ["extracted", "error"])
        self.assertEqual(pages[1]["error_code"], "page_extraction_failed")
        self.assertEqual(result["manifest"]["completeness"], "requires_human_review")

    def test_unreviewed_or_forbidden_routes_fail_before_extraction(self):
        data = b"not read when rights are denied"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "paper.txt"
            path.write_bytes(data)
            _write_authority(Path(temporary) / "software", data, review_status="review_pending")
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", Path(temporary) / "software"):
                with self.assertRaises(SourceIngestionError):
                    ingest_local_document("LIT-fixture", path, data_dir=Path(temporary) / "data")
                with self.assertRaises(SourceIngestionError):
                    ingest_local_document("LIT-fixture", path, data_dir=Path(temporary) / "data", route="colab")
                with self.assertRaisesRegex(SourceIngestionError, "not registered"):
                    ingest_local_document("LIT-unregistered", path, data_dir=Path(temporary) / "data")
            _write_authority(Path(temporary) / "software", data, "LIT-colab-only", routes=("colab",))
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", Path(temporary) / "software"):
                with self.assertRaisesRegex(SourceIngestionError, "local route"):
                    ingest_local_document("LIT-colab-only", path, data_dir=Path(temporary) / "data")
        local_only_source = _source(data)
        with self.assertRaises(SourceIngestionError):
            _validate_rights(local_only_source, _review(), "remote_llm")
        source_without_local_reuse = _source(data, routes=("export",))
        with self.assertRaisesRegex(SourceIngestionError, "Source reuse rights"):
            _validate_rights(source_without_local_reuse, _review(), "local")

    def test_stale_corrected_or_retracted_source_is_rejected(self):
        data = b"synthetic source"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "paper.txt"
            path.write_bytes(data)
            for index, (status, correction) in enumerate((
                    ("superseded", "none_found"),
                    ("current", "correction_published"),
                    ("current", "retracted"))):
                source_id = f"LIT-stale-{index}"
                _write_authority(root / "software", data, source_id,
                                 source_status=status, correction_status=correction)
                with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                    with self.assertRaises(SourceIngestionError):
                        ingest_local_document(source_id, path, data_dir=root / "data")

    def test_hash_mismatch_malformed_and_empty_documents_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "broken.pdf"
            path.write_bytes(b"not a PDF")
            _write_authority(root / "software", b"not a PDF", "LIT-broken")
            with self.assertRaises(SourceIngestionError):
                with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                    ingest_local_document("LIT-broken", path, data_dir=root / "data")
            empty_path = root / "empty.pdf"
            empty_pdf = _minimal_pdf([""])
            empty_path.write_bytes(empty_pdf)
            _write_authority(root / "software", empty_pdf, "LIT-empty")
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                empty_result = ingest_local_document("LIT-empty", empty_path, data_dir=root / "data")
            self.assertEqual(empty_result["excerpts"], [])
            self.assertEqual(empty_result["manifest"]["extractor"]["page_extractions"][0]["status"], "empty")
            self.assertEqual(empty_result["manifest"]["completeness"], "requires_human_review")
            text_path = root / "hash.txt"
            text_path.write_text("changed", encoding="utf-8")
            _write_authority(root / "software", b"original", "LIT-hash")
            with self.assertRaisesRegex(SourceIngestionError, "hash"):
                with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                    ingest_local_document("LIT-hash", text_path, data_dir=root / "data")

    def test_private_store_is_separate_and_base_input_is_rejected(self):
        data = b"private only"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "paper.txt"
            path.write_bytes(data)
            _write_authority(root / "software", data, "LIT-private")
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                result = ingest_local_document("LIT-private", path, data_dir=root / "data")
            private = root / "data" / "knowledge_builder" / "private" / "source_extractions"
            self.assertTrue((private / result["storage_id"]).is_dir())
            base_root = root / "base"
            base_input = base_root / "40-Design" / "experiment.txt"
            base_input.parent.mkdir(parents=True)
            base_input.write_text("not processed", encoding="utf-8")
            _write_authority(base_root, data, "LIT-private")
            with self.assertRaisesRegex(SourceIngestionError, "Base"):
                with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", base_root):
                    ingest_local_document("LIT-private", base_input, data_dir=root / "data")
            with self.assertRaisesRegex(SourceIngestionError, "repository"):
                with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                    ingest_local_document("LIT-private", path, data_dir=Path(__file__).resolve().parents[1])

    def test_data_dir_symlink_ancestor_is_rejected(self):
        data = b"private only"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "paper.txt"
            path.write_bytes(data)
            _write_authority(root / "software", data, "LIT-symlink")
            link = root / "linked-data"
            original_is_symlink = Path.is_symlink
            def is_symlink(candidate):
                return candidate == link or original_is_symlink(candidate)
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                with patch.object(Path, "is_symlink", is_symlink):
                    with self.assertRaisesRegex(SourceIngestionError, "symbolic links"):
                        ingest_local_document("LIT-symlink", path, data_dir=link / "nested")

    def test_user_selected_local_paper_is_namespaced_private_and_searchable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "papers"
            source_root.mkdir()
            paper = source_root / "method.txt"
            paper.write_text(
                "Qualitative coding uses a transparent codebook.\n\n"
                "A second paragraph describes disagreements.", encoding="utf-8")
            data_dir = root / "application-data"
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                imported = ingest_user_selected_local_paper(
                    source_root, "method.txt", data_dir=data_dir,
                    installation_id="install-fixture", expert_id="exp-thematic-analysis",
                    title="User selected methods paper", authors=["A. Author"],
                    publication_year=2024, confirm_local_processing=True,
                )
                repeated = ingest_user_selected_local_paper(
                    source_root, "method.txt", data_dir=data_dir,
                    installation_id="install-fixture", expert_id="exp-thematic-analysis",
                    title="User selected methods paper", authors=["A. Author"],
                    publication_year=2024, confirm_local_processing=True,
                )
                source = imported["manifest"]["source"]
                results = search_local_papers(
                    "transparent codebook", data_dir=data_dir,
                    installation_id="install-fixture", expert_id="exp-thematic-analysis")
                evidence = read_local_evidence(
                    source["source_id"], results[0]["anchor_id"], data_dir=data_dir,
                    installation_id="install-fixture", expert_id="exp-thematic-analysis")
                other_install_results = search_local_papers(
                    "transparent codebook", data_dir=data_dir,
                    installation_id="different-install", expert_id="exp-thematic-analysis")
                other_expert_results = search_local_papers(
                    "transparent codebook", data_dir=data_dir,
                    installation_id="install-fixture", expert_id="exp-framework-method")

            self.assertEqual(imported["storage_id"], repeated["storage_id"])
            self.assertTrue(source["source_id"].startswith("local:install-fixture:source:"))
            self.assertEqual(source["rights"], {"classification": "private", "allowed_routes": ["local"]})
            self.assertEqual(source["access_scope"], "local_private")
            self.assertEqual(source["locator"], {
                "kind": "local_uri", "value": f"file://local-private/{hashlib.sha256(paper.read_bytes()).hexdigest()}"})
            self.assertFalse(imported["manifest"]["processing_attestation"]["redistribution_permission_asserted"])
            self.assertEqual(results[0]["location"], {"kind": "paragraph", "start": "1", "end": "1"})
            self.assertEqual(evidence["text"], "Qualitative coding uses a transparent codebook.")
            self.assertEqual(other_install_results, [])
            self.assertEqual(other_expert_results, [])
            self.assertNotIn(str(paper.resolve()), json.dumps(imported, ensure_ascii=False))
            self.assertNotIn(paper.name, json.dumps(imported, ensure_ascii=False))
            stored = data_dir / "knowledge_builder" / "private" / "source_extractions" / imported["storage_id"]
            self.assertEqual({path.name for path in stored.iterdir()}, {"manifest.json", "excerpts.jsonl"})

    def test_user_selected_import_requires_consent_and_contained_relative_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "papers"
            source_root.mkdir()
            (source_root / "paper.txt").write_text("local content", encoding="utf-8")
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                for relative_path, consent in (("paper.txt", False), ("../outside.txt", True),
                                                (str(source_root / "paper.txt"), True)):
                    with self.subTest(relative_path=relative_path, consent=consent):
                        with self.assertRaises(SourceIngestionError):
                            ingest_user_selected_local_paper(
                                source_root, relative_path, data_dir=root / "data",
                                installation_id="install-fixture", expert_id="exp-thematic-analysis",
                                title="Paper", confirm_local_processing=consent)

    def test_titles_and_authors_reject_embedded_absolute_paths(self):
        for value in (
            "Paper /home/alice/private.pdf",
            "Paper(C:/Users/alice/private.pdf)",
            "Reference \\\\server\\private\\paper.pdf",
            "Reference file:///Users/alice/paper.pdf",
            "Document ~/Downloads/private.pdf",
        ):
            with self.subTest(value=value):
                with self.assertRaises(SourceIngestionError):
                    _local_title_without_path(value)
                with self.assertRaises(SourceIngestionError):
                    source_ingestion._local_author_without_path(value)

    def test_private_store_read_errors_are_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary) / "data"
            private_root = data_dir / "knowledge_builder" / "private" / "source_extractions"
            private_root.mkdir(parents=True)
            original_iterdir = Path.iterdir

            def failing_iterdir(path):
                if path == private_root:
                    raise OSError("C:\\Users\\secret\\private-store")
                return original_iterdir(path)

            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", Path(temporary) / "software"), \
                    patch.object(Path, "iterdir", failing_iterdir):
                with self.assertRaises(SourceIngestionError) as raised:
                    search_local_papers("query", data_dir=data_dir,
                                        installation_id="install-fixture",
                                        expert_id="exp-thematic-analysis")
            self.assertNotIn("Users", str(raised.exception))
            self.assertNotIn("private-store", str(raised.exception))

    def test_user_selected_import_reader_rejects_changed_excerpt_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "papers"
            source_root.mkdir()
            (source_root / "paper.txt").write_text("Evidence text.", encoding="utf-8")
            data_dir = root / "data"
            with patch.object(source_ingestion, "SOFTWARE_VAULT_ROOT", root / "software"):
                imported = ingest_user_selected_local_paper(
                    source_root, "paper.txt", data_dir=data_dir,
                    installation_id="install-fixture", expert_id="exp-thematic-analysis",
                    title="Paper", confirm_local_processing=True)
                stored = data_dir / "knowledge_builder" / "private" / "source_extractions" / imported["storage_id"]
                with (stored / "excerpts.jsonl").open("ab") as stream:
                    stream.write(b"tampered")
                with self.assertRaisesRegex(SourceIngestionError, "integrity"):
                    search_local_papers(
                        "Evidence", data_dir=data_dir, installation_id="install-fixture",
                        expert_id="exp-thematic-analysis")


if __name__ == "__main__":
    unittest.main()
