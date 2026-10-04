"""Synthetic saved-run slide service tests; no providers or real Vaults."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask
from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.services.analysis_slides import AnalysisSlidesService, _facts, _safe_url, _text, _wrap
from gurumoji.web.analysis_slides_routes import register_analysis_slides_routes


def fixture():
    raw = {"summary": "Synthetic saved finding", "claims": [{"claim_id": "claim1", "kind": "observation",
           "text": "Synthetic observation", "evidence_ids": ["ev_1"]}]}
    initial = {"input_hash": "input-fixed", "analysis": {}, "evidence": [{"evidence_id": "ev_1",
               "utterance_id": "u1", "dataset_version": "input-fixed", "source_hash": fingerprint("Synthetic quote"),
               "text": "Synthetic quote", "excluded": False}]}
    return {"run": {"run_id": "run-1", "item_id": "item-1", "initial_id": "initial-1", "input_hash": "input-fixed",
        "status": "completed", "source_revision": 0, "analysis_revision": 1, "annotation_version": 2,
        "codebook_version": 1, "view_version": 3, "generation": 4, "tasks": [],
        "config": {"question": "Synthetic question", "research_mode": "exploratory", "stop_mode": "iterations"},
        "current_view": copy.deepcopy(raw), "review_status": "incomplete", "stop_reason": "question_satisfied"},
        "initial": {"initial_id": "initial-1", "hash": fingerprint(initial), "snapshot": initial},
        "raw_results": [{"run_id": "run-1", "result_id": "result-1", "role": "core", "raw_hash": fingerprint(raw),
            "raw": raw, "annotation_version": 2, "dataset_version": "input-fixed", "validation_status": "valid",
            "content_status": "unreviewed"}], "decisions": [], "label_versions": [], "usage_records": []}


def template():
    # Test-only recipe, not an application slide design or user deliverable.
    return {"research": {"id": "research", "name": "Synthetic test template", "version": "test-1",
        "description": "Synthetic fixture", "design": {"sections": [{"key": "purpose", "title": "Fixture purpose"}]},
        "prompt": "Fixture rule: only saved values.", "source_references": []}}


class SlidesGateTests(unittest.TestCase):
    def setUp(self):
        self.saved = fixture()
        self.artifact = None
        self.reader = Mock(side_effect=lambda item, run: copy.deepcopy(self.saved))
        self.vault = SimpleNamespace(publish_slide_design=Mock(side_effect=self.publish),
                                     read_slide_design=Mock(side_effect=lambda **_: copy.deepcopy(self.artifact)))
        self.service = AnalysisSlidesService(export_result=self.reader, vault_factory=lambda: self.vault, templates=template())
        self.app = Flask(__name__)
        register_analysis_slides_routes(self.app, lambda: self.service)
        self.client = self.app.test_client()
        self.url = "/api/library/item-1/analysis/orchestration/run-1/slides"

    def publish(self, **args):
        self.artifact = copy.deepcopy(args["artifact"])
        return {"status": "saved", "note_id": "synthetic-note"}

    def test_empty_template_configuration_fails_closed(self):
        service = AnalysisSlidesService(export_result=self.reader, vault_factory=lambda: self.vault)
        self.assertEqual(service.catalog("item-1", "run-1")["templates"], [])
        with self.assertRaises(AnalysisContractError):
            service.save_design("item-1", "run-1")
        self.vault.publish_slide_design.assert_not_called()

    def test_catalog_only_reads_and_exposes_reviewable_design(self):
        response = self.client.get(self.url + "/templates")
        self.assertEqual(response.status_code, 200)
        value = response.get_json()
        self.assertIn("prompt", value["templates"][0])
        self.assertIn("design", value["templates"][0])
        self.assertIsNone(value["design"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.vault.publish_slide_design.assert_not_called()
        self.reader.assert_called_once_with("item-1", "run-1")

    def test_gate_rejects_preview_before_saved_design(self):
        with patch.object(self.service, "_project") as projection:
            response = self.client.get(self.url + "/preview")
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.get_json()["reason_code"], "slide_design_required")
            projection.assert_not_called()
        self.vault.publish_slide_design.assert_not_called()

    def test_save_is_explicit_and_contains_no_source_text(self):
        response = self.client.post(self.url + "/design", json={"template": "research"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["design"]["snapshot_signature"], fingerprint(self.saved))
        encoded = json.dumps(self.artifact)
        for text in ("Synthetic saved finding", "Synthetic observation", "Synthetic quote", "Synthetic question"):
            self.assertNotIn(text, encoded)
        self.vault.publish_slide_design.assert_called_once()
        self.assertEqual(self.artifact["provenance"]["annotation_version"], "2")
        self.assertEqual(self.artifact["provenance"]["result_versions"][0]["raw_hash"], self.saved["raw_results"][0]["raw_hash"])

    def test_save_stale_snapshot_or_unexpected_body_never_writes(self):
        for body in ({"template": "research", "expected_snapshot": "wrong"}, {"prompt": "execute"},
                     [], {"template": {"url": "https://example.com"}}):
            response = self.client.post(self.url + "/design", json=body)
            self.assertIn(response.status_code, (400, 409))
        self.vault.publish_slide_design.assert_not_called()

    def test_save_failure_and_unverified_save_gate_closed(self):
        self.vault.publish_slide_design.side_effect = OSError("private path")
        response = self.client.post(self.url + "/design", json={})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private path", response.get_data(as_text=True))
        self.vault.publish_slide_design.side_effect = lambda **_: {}
        self.assertEqual(self.client.post(self.url + "/design", json={}).status_code, 409)

    def test_wrong_item_run_and_tampered_hash_rejected(self):
        self.saved["run"]["item_id"] = "other"
        self.assertEqual(self.client.get(self.url + "/templates").status_code, 404)
        self.saved = fixture()
        self.saved["raw_results"][0]["run_id"] = "other-run"
        self.assertEqual(self.client.get(self.url + "/templates").status_code, 409)
        self.saved = fixture()
        self.saved["initial"]["snapshot"]["evidence"][0]["text"] = "tampered"
        self.assertEqual(self.client.get(self.url + "/templates").status_code, 409)
        self.saved = fixture()
        self.saved["raw_results"][0]["raw"]["summary"] = "tampered"
        self.assertEqual(self.client.get(self.url + "/templates").status_code, 409)

    def test_deleted_changed_design_and_changed_run_cannot_project(self):
        self.service.save_design("item-1", "run-1")
        original = copy.deepcopy(self.artifact)
        with patch.object(self.service, "_project") as projection:
            for change in ("deleted", "changed_prompt", "changed_version", "changed_run"):
                self.artifact = copy.deepcopy(original)
                self.saved = fixture()
                if change == "deleted":
                    self.artifact = None
                elif change == "changed_prompt":
                    self.artifact["prompt"] = "new prompt"
                elif change == "changed_version":
                    self.artifact["template_version"] = "new"
                else:
                    self.saved["run"]["annotation_version"] = 3
                self.assertEqual(self.client.get(self.url + "/preview").status_code, 409)
            projection.assert_not_called()

    def test_download_requires_exact_preview_fingerprint_before_rendering(self):
        with patch("gurumoji.services.analysis_slides.render_presentation") as render:
            self.assertEqual(self.client.get(self.url + "/presentation.pptx").status_code, 400)
            self.service.save_design("item-1", "run-1")
            self.assertEqual(self.client.get(self.url + "/presentation.pptx?expected_snapshot=sha256:" + "0" * 64).status_code, 409)
            render.assert_not_called()

    def test_plain_text_projection_helpers_are_bounded_inert_and_preserve_zero(self):
        text = '<script>alert(1)</script>\x00\ud800'
        self.assertEqual(_text(text), '<script>alert(1)</script>')
        self.assertIn('件数: 0', _facts({"count": 0, "missing_count": 1, "denominator": 2}))
        self.assertEqual(len(_facts({"rows": [{"value": i} for i in range(10000)]}, maximum=7)), 7)
        self.assertLessEqual(max(map(len, _wrap("あ" * 1000))), 41)
        for url in ("javascript:alert(1)", "file:///etc/passwd", "https://user:secret@site.test", "//example.com"):
            self.assertEqual(_safe_url(url), "")
        self.assertEqual(_safe_url("https://example.com/source"), "https://example.com/source")
        self.assertEqual(_facts({"reasoning": "PRIVATE", "provider_trace": {"summary": "PRIVATE"}}), [])


if __name__ == "__main__":
    unittest.main()
