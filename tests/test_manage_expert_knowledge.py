"""Focused coverage for the read-only expert knowledge preflight commands."""
import json
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import manage_expert_knowledge as manager
from gurumoji import method_experts


class InventoryTests(unittest.TestCase):
    def test_inventory_counts_experts_and_literature_without_emitting_paths_or_bodies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            literature = root / method_experts.LITERATURE_DIR
            literature.mkdir(parents=True)
            (literature / "LIT-sample.md").write_text(
                "---\nnote_type: literature\nstatus: current\ncorrection_status: checked\n"
                "access_scope: abstract\n---\nPRIVATE BODY MUST NOT APPEAR\n", encoding="utf-8")
            catalog = method_experts.ExpertCatalog(local_root=root)
            with patch.object(method_experts, "default_catalog", return_value=catalog):
                result = manager.inventory()
        self.assertEqual(result["experts"]["definitions"], 17)
        base_notes = [path for path in (catalog.root / method_experts.LITERATURE_DIR).glob("*.md")
                      if path.name != "00-Index.md"]
        self.assertEqual(result["literature"]["notes"], result["literature"]["local_only"] + len(base_notes))
        self.assertEqual(result["literature"]["local_only"], 1)
        self.assertEqual(sum(result["literature"]["status_counts"].values()), result["literature"]["notes"])
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("PRIVATE BODY", serialized)
        self.assertNotIn(str(root), serialized)
        self.assertEqual(result["references"]["unresolved"], 0)


class SourceAuditTests(unittest.TestCase):
    class Catalog:
        def __init__(self, root):
            self.root = root

        def index(self):
            return {expert_id: {} for expert_id in manager.PILOT_EXPERT_IDS}

        def definition(self, expert_id):
            refs = {manager.PILOT_EXPERT_IDS[0]: ["LIT-permitted", "LIT-self-asserted", "LIT-cc-only",
                                                "LIT-local-url", "LIT-missing", "LIT-invalid",
                                                "LIT-wrong-type", "LIT-wrong-id"],
                    manager.PILOT_EXPERT_IDS[1]: [], manager.PILOT_EXPERT_IDS[2]: []}
            return {"literature": refs[expert_id]}

    def test_metadata_only_records_and_strict_llm_rights_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            literature = root / method_experts.LITERATURE_DIR
            literature.mkdir(parents=True)
            permitted = literature / "LIT-permitted.md"
            permitted_bytes = (
                "---\nnote_type: literature\nliterature_id: LIT-permitted\ntitle: Permitted\nyear: 2024\n"
                "doi: 10.1234/example\nurl: https://doi.org/10.1234/example\n"
                "status: current\ncorrection_status: checked\naccess_scope: abstract\n"
                "license_id: example-license\nlicense_url: https://example.org/license\n"
                "llm_processing_permission: explicitly_permitted\n"
                "llm_allowed_routes: [local]\nrights_review_status: approved\n"
                "rights_reviewed_by: reviewer-1\nrights_reviewed_at: 2026-01-15T00:00:00Z\n"
                "rights_review_basis: publisher permission record 2026-01\n---\n"
                "PRIVATE BODY MUST NOT APPEAR\n"
            ).encode("utf-8")
            permitted.write_bytes(permitted_bytes)
            (literature / "LIT-cc-only.md").write_text(
                "---\nnote_type: literature\nliterature_id: LIT-cc-only\ntitle: CC only\nyear: 2020\nstatus: current\n"
                "correction_status: none_found\naccess_scope: full_text\nlicense_id: CC-BY\n"
                "license_url: https://creativecommons.org/licenses/by/4.0/\n---\nbody\n", encoding="utf-8")
            (literature / "LIT-self-asserted.md").write_text(
                "---\nnote_type: literature\nliterature_id: LIT-self-asserted\ntitle: Self asserted\n"
                "status: current\ncorrection_status: checked\nlicense_id: L\n"
                "license_url: https://example.org/license\nllm_processing_permission: explicitly_permitted\n---\nbody\n",
                encoding="utf-8")
            (literature / "LIT-local-url.md").write_text(
                "---\nnote_type: literature\nliterature_id: LIT-local-url\ntitle: Local URI\n"
                "status: current\ncorrection_status: checked\nurl: file:///private/paper.pdf\n---\nbody\n",
                encoding="utf-8")
            (literature / "LIT-invalid.md").write_text(
                "---\nnote_type: literature\nliterature_id: LIT-invalid\ntitle: Invalid\nstatus: current\n",
                encoding="utf-8")
            (literature / "LIT-wrong-type.md").write_text(
                "---\nnote_type: source\nliterature_id: LIT-wrong-type\ntitle: Wrong type\n"
                "status: current\ncorrection_status: checked\n---\nbody\n", encoding="utf-8")
            (literature / "LIT-wrong-id.md").write_text(
                "---\nnote_type: literature\nliterature_id: LIT-someone-else\ntitle: Wrong ID\n"
                "status: current\ncorrection_status: checked\n---\nbody\n", encoding="utf-8")
            result = manager.source_audit(self.Catalog(root))

        self.assertEqual(result["counts"], {
            "experts": 3, "definition_errors": 0, "references": 8, "unresolved_refs": 4,
            "missing_status": 2, "missing_correction_status": 2, "missing_rights": 7,
            "resolution_status_counts": {"invalid_frontmatter": 1, "literature_id_mismatch": 1,
                                          "missing": 1, "note_type_mismatch": 1, "resolved": 4},
        })
        self.assertEqual(len(result["experts"]), 3)
        first, self_asserted, cc_only, local_url, missing, invalid, wrong_type, wrong_id = result["records"]
        self.assertEqual(first["rights_status"], "reviewed")
        self.assertEqual(first["ai_llm_processing"]["routes"]["local"]["status"], "permitted")
        self.assertEqual(first["ai_llm_processing"]["routes"]["colab"]["status"], "not_allowlisted")
        self.assertEqual(first["doi_or_url"], "10.1234/example")
        self.assertEqual(first["note_sha256"], hashlib.sha256(permitted_bytes).hexdigest())
        self.assertEqual(cc_only["rights_status"], "unverified_no_llm_route")
        self.assertEqual(self_asserted["rights_status"], "review_pending")
        self.assertEqual(self_asserted["ai_llm_processing"]["routes"]["remote_llm"]["status"], "review_pending")
        self.assertIsNone(local_url["doi_or_url"])
        self.assertEqual(missing["note_sha256"], None)
        self.assertEqual([record["resolution_status"] for record in (invalid, wrong_type, wrong_id)],
                         ["invalid_frontmatter", "note_type_mismatch", "literature_id_mismatch"])
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("PRIVATE BODY", serialized)
        self.assertNotIn(str(root), serialized)

    def test_reviewed_no_permission_is_distinct_from_missing_rights_and_allows_no_route(self):
        properties = {
            "license_id": "Elsevier TDM license",
            "license_url": "https://www.elsevier.com/tdm/userlicense/1.0/",
            "llm_processing_permission": "not_explicitly_permitted",
            "llm_allowed_routes": [],
            "rights_review_status": "approved",
            "rights_reviewed_by": "reviewer-1",
            "rights_reviewed_at": "2026-01-15T00:00:00Z",
            "rights_review_basis": "Terms were reviewed; no project route was approved.",
        }
        reviewed = manager._ai_llm_processing(properties)
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertEqual(reviewed["reason"], "reviewed_no_explicit_permission")
        self.assertEqual(reviewed["permission_decision"], "not_explicitly_permitted")
        self.assertTrue(all(route["status"] == "not_allowlisted"
                            for route in reviewed["routes"].values()))

        properties["llm_allowed_routes"] = ["local"]
        inconsistent = manager._ai_llm_processing(properties)
        self.assertEqual(inconsistent["status"], "unverified_no_llm_route")
        self.assertTrue(all(route["status"] == "review_pending"
                            for route in inconsistent["routes"].values()))

    def test_all_17_experts_and_per_expert_counts(self):
        expert_ids = [f"exp-audit-{index:02d}" for index in range(17)]

        class AllCatalog:
            def __init__(self, root):
                self.root = root

            def index(self):
                return {expert_id: {"source": "base"} for expert_id in expert_ids}

            def definition(self, expert_id):
                note_id = f"LIT-{expert_id}"
                return {"literature": [note_id]}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            literature = root / method_experts.LITERATURE_DIR
            literature.mkdir(parents=True)
            for expert_id in expert_ids:
                note_id = f"LIT-{expert_id}"
                (literature / f"{note_id}.md").write_text(
                    f"---\nnote_type: literature\nliterature_id: {note_id}\ntitle: Fixture\n"
                    "status: current\ncorrection_status: checked\n---\nbody hidden\n", encoding="utf-8")
            result = manager.source_audit(AllCatalog(root), all_experts=True)
        self.assertEqual(result["counts"]["experts"], 17)
        self.assertEqual(result["counts"]["references"], 17)
        self.assertEqual(result["counts"]["unresolved_refs"], 0)
        self.assertEqual(result["counts"]["missing_rights"], 17)
        self.assertEqual(len(result["experts"]), 17)
        self.assertTrue(all(item["references"] == 1 and item["missing_rights"] == 1
                            for item in result["experts"]))
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("body hidden", serialized)
        self.assertNotIn(str(root), serialized)

    def test_expert_selection_rejects_unknown_malformed_and_duplicate_ids(self):
        catalog = self.Catalog(Path("."))
        with self.assertRaisesRegex(ValueError, "unknown expert"):
            manager.source_audit(catalog, expert_ids=["exp-missing"])
        with self.assertRaisesRegex(ValueError, "invalid expert"):
            manager.source_audit(catalog, expert_ids=["../bad"])
        with self.assertRaisesRegex(ValueError, "not be repeated"):
            manager.source_audit(catalog, expert_ids=[manager.PILOT_EXPERT_IDS[0]] * 2)

    def test_locator_filter_rejects_local_paths_controls_and_url_secrets(self):
        self.assertIsNone(manager._doi_or_https_url({"doi": r"10.1234/C:\Users\name\private.pdf"}))
        self.assertIsNone(manager._doi_or_https_url({"doi": "10.1234/private\x1fpaper.pdf"}))
        self.assertIsNone(manager._doi_or_https_url({"url": "https://example.org/article?token=secret#private"}))
        self.assertEqual(manager._doi_or_https_url({"doi": "10.1234/valid.doi"}), "10.1234/valid.doi")
        self.assertEqual(manager._doi_or_https_url({"url": "https://example.org/article"}),
                         "https://example.org/article")


class LocalLlmPreflightTests(unittest.TestCase):
    def test_unconfigured_does_not_attempt_network(self):
        with patch.object(manager, "_gpu_memory", return_value={"status": "unavailable"}), \
                patch.object(manager.urllib.request, "build_opener") as opener:
            result, code = manager.preflight_local_llm(None)
        self.assertEqual(code, manager.EXIT_NOT_CONFIGURED)
        self.assertEqual(result["exit_code"], code)
        self.assertEqual(result["api"]["status"], "not_configured")
        self.assertFalse(result["inference_performed"])
        opener.assert_not_called()

    def test_rejects_non_loopback_before_network(self):
        with patch.object(manager.urllib.request, "build_opener") as opener:
            result, code = manager.preflight_local_llm("https://example.com/v1")
        self.assertEqual(code, manager.EXIT_REJECTED_URL)
        self.assertEqual(result["exit_code"], code)
        self.assertEqual(result["api"]["status"], "rejected_url")
        opener.assert_not_called()

    def test_gets_models_without_sending_inference(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                self.limit = limit
                return b'{"data":[{"id":"qwen/qwen3-8b"},{"id":"mistral"}]}'

        response = Response()

        class Opener:
            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                return response

        opener = Opener()
        with patch.object(manager, "_gpu_memory", return_value={"status": "available", "devices": []}), \
                patch.object(manager.urllib.request, "build_opener", return_value=opener):
            result, code = manager.preflight_local_llm("http://127.0.0.1:1234/v1")
        self.assertEqual(code, manager.EXIT_OK)
        self.assertEqual(result["exit_code"], code)
        self.assertEqual(result["models"], ["qwen/qwen3-8b", "mistral"])
        self.assertEqual(opener.request.method, "GET")
        self.assertTrue(opener.request.full_url.endswith("/v1/models"))
        self.assertFalse(result["inference_performed"])
        self.assertFalse(result["model_load_requested"])

    def test_unreachable_api_has_defined_exit_code(self):
        class Opener:
            def open(self, request, timeout):
                raise OSError("offline")

        with patch.object(manager.urllib.request, "build_opener", return_value=Opener()):
            result, code = manager.preflight_local_llm("http://localhost:1234/v1")
        self.assertEqual(code, manager.EXIT_UNREACHABLE)
        self.assertEqual(result["exit_code"], code)
        self.assertEqual(result["api"]["status"], "unreachable")


class CandidateCommandTests(unittest.TestCase):
    def test_generate_command_routes_to_local_gale_pipeline_and_emits_summary(self):
        from gurumoji.knowledge_builder import candidate_pipeline
        expected = {"candidate_count": 1, "review_status": "pending_human_review",
                    "batch_sha256": "a" * 64}
        stdout = io.StringIO()
        with patch.object(candidate_pipeline, "generate_gale_candidates_local", return_value=expected) as run, \
                patch("sys.stdout", stdout):
            code = manager.main([
                "generate-gale-candidate", "--source-extraction-dir", "private-extraction",
                "--output-batch", "pending-batch.json", "--base-url", "http://127.0.0.1:1234/v1",
                "--timeout", "90",
            ])
        self.assertEqual(code, manager.EXIT_OK)
        run.assert_called_once_with("private-extraction", "pending-batch.json",
                                    base_url="http://127.0.0.1:1234/v1", timeout=90.0)
        self.assertEqual(json.loads(stdout.getvalue()), expected)


class LocalPaperCommandTests(unittest.TestCase):
    def test_import_command_prints_only_metadata(self):
        from gurumoji.knowledge_builder import source_ingestion

        manifest = {
            "source": {"source_id": "local:fixture:source:abc", "sha256": "a" * 64},
            "excerpt_count": 2, "anchor_count": 2, "completeness": "extracted",
            "extractor": {"review_reasons": []},
        }
        stdout = io.StringIO()
        catalog = patch.object(manager.method_experts, "ExpertCatalog")
        with catalog as expert_catalog, \
                patch.object(source_ingestion, "ingest_user_selected_local_paper",
                             return_value={"status": "stored_private", "storage_class": "private_local_only",
                                           "storage_id": "opaque-record", "manifest": manifest}) as run, \
                patch("sys.stdout", stdout):
            expert_catalog.return_value.index.return_value = {"exp-thematic-analysis": {"source": "base"}}
            code = manager.main([
                "import-local-paper", "--source-root", "papers", "--relative-path", "paper.pdf",
                "--data-dir", "private-data", "--installation-id", "fixture-install",
                "--expert-id", "exp-thematic-analysis", "--title", "Fixture paper",
                "--author", "A. Author", "--publication-year", "2025",
                "--confirm-local-processing",
            ])
        self.assertEqual(code, manager.EXIT_OK)
        run.assert_called_once_with(
            "papers", "paper.pdf", data_dir="private-data", installation_id="fixture-install",
            expert_id="exp-thematic-analysis", title="Fixture paper", authors=["A. Author"],
            publication_year=2025, confirm_local_processing=True)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["route"], "local_only")
        self.assertNotIn("text", output)
        self.assertNotIn("paper.pdf", stdout.getvalue())

    def test_import_command_requires_explicit_confirmation(self):
        stderr = io.StringIO()
        with patch.object(manager.method_experts, "ExpertCatalog") as expert_catalog, \
                patch("sys.stderr", stderr):
            expert_catalog.return_value.index.return_value = {"exp-thematic-analysis": {"source": "base"}}
            with self.assertRaises(SystemExit) as raised:
                manager.main([
                    "import-local-paper", "--source-root", "papers", "--relative-path", "paper.pdf",
                    "--data-dir", "private-data", "--installation-id", "fixture-install",
                    "--expert-id", "exp-thematic-analysis", "--title", "Fixture paper",
                ])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("confirmation", stderr.getvalue())

    def test_local_expert_override_is_not_accepted_as_a_base_expert(self):
        from gurumoji.knowledge_builder import source_ingestion

        stderr = io.StringIO()
        with patch.object(manager.method_experts, "ExpertCatalog") as expert_catalog, \
                patch.object(source_ingestion, "ingest_user_selected_local_paper") as run, \
                patch("sys.stderr", stderr):
            expert_catalog.return_value.index.return_value = {
                "exp-local-only": {"source": "local"},
            }
            with self.assertRaises(SystemExit) as raised:
                manager.main([
                    "import-local-paper", "--source-root", "papers", "--relative-path", "paper.pdf",
                    "--data-dir", "private-data", "--installation-id", "fixture-install",
                    "--expert-id", "exp-local-only", "--title", "Fixture paper",
                    "--confirm-local-processing",
                ])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("Software Vault experts", stderr.getvalue())
        run.assert_not_called()

    def test_search_command_returns_local_evidence_with_route_marker(self):
        from gurumoji.knowledge_builder import source_ingestion
        expected = [{"source_id": "local:fixture:source:abc", "anchor_id": "para-000001",
                     "text": "Synthetic local evidence."}]
        stdout = io.StringIO()
        with patch.object(manager.method_experts, "ExpertCatalog") as expert_catalog, \
                patch.object(source_ingestion, "search_local_papers", return_value=expected) as search, \
                patch("sys.stdout", stdout):
            expert_catalog.return_value.index.return_value = {"exp-thematic-analysis": {"source": "base"}}
            code = manager.main([
                "search-local-papers", "--data-dir", "private-data",
                "--installation-id", "fixture-install", "--expert-id", "exp-thematic-analysis",
                "--query", "evidence",
            ])
        self.assertEqual(code, manager.EXIT_OK)
        search.assert_called_once_with("evidence", data_dir="private-data",
                                       installation_id="fixture-install",
                                       expert_id="exp-thematic-analysis", limit=10)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["route"], "local_only")
        self.assertEqual(output["results"], expected)

    def test_filesystem_errors_do_not_print_private_paths(self):
        from gurumoji.knowledge_builder import source_ingestion
        stderr = io.StringIO()
        with patch.object(manager.method_experts, "ExpertCatalog") as expert_catalog, \
                patch.object(source_ingestion, "search_local_papers",
                             side_effect=OSError("C:\\Users\\secret\\private-store")), \
                patch("sys.stderr", stderr):
            expert_catalog.return_value.index.return_value = {"exp-thematic-analysis": {"source": "base"}}
            with self.assertRaises(SystemExit) as raised:
                manager.main([
                    "search-local-papers", "--data-dir", "private-data",
                    "--installation-id", "fixture-install", "--expert-id", "exp-thematic-analysis",
                    "--query", "evidence",
                ])
        self.assertEqual(raised.exception.code, 2)
        self.assertNotIn("Users", stderr.getvalue())
        self.assertNotIn("private-store", stderr.getvalue())

    def test_compile_command_routes_to_non_release_bundle_compiler(self):
        from gurumoji.knowledge_builder import candidate_pipeline
        expected = {"bundle_sha256": "b" * 64, "candidate_count": 1, "reused": False}
        stdout = io.StringIO()
        with patch.object(candidate_pipeline, "compile_candidate_review_bundle", return_value=expected) as run, \
                patch("sys.stdout", stdout):
            code = manager.main([
                "compile-gale-review-bundle", "--candidate-batch", "pending-batch.json",
                "--source-extraction-dir", "private-extraction", "--output", "review-bundle.json",
            ])
        self.assertEqual(code, manager.EXIT_OK)
        run.assert_called_once_with("pending-batch.json", "private-extraction", "review-bundle.json")
        self.assertEqual(json.loads(stdout.getvalue()), expected)


if __name__ == "__main__":
    unittest.main()
