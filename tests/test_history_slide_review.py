"""Independent synthetic review of history/slide boundaries. No AI or slide generation."""
import copy
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gurumoji.analysis_store import StoreConflict
from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.analysis_orchestration import AnalysisOrchestrationService, initialize_orchestration_store
from gurumoji.services.analysis_history import AnalysisHistoryService
from gurumoji.vault_registry import VaultRegistry, entity_key


class SlideDesignGateReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.registry = VaultRegistry(self.base / "data" / "library.sqlite3", self.base / "software")
        self.artifact = {
            "schema_version": 1, "template_id": "review", "template_version": "review-1",
            "design_hash": "design-hash", "snapshot_signature": "snapshot-hash",
            "item_id": "item-a", "run_id": "run-a", "provenance": {"annotation_version": 0},
            "design": {"name": "synthetic gate fixture"}, "prompt": "No generated content",
            "source_references": [],
        }

    def save(self, artifact=None):
        artifact = self.artifact if artifact is None else artifact
        return self.registry.publish_slide_design(artifact["item_id"], artifact["run_id"], artifact)

    def files(self):
        return {str(p.relative_to(self.base)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.base.rglob("*") if p.is_file()}

    def test_same_run_name_in_two_conversations_never_aliases(self):
        first = self.save()
        other = {**self.artifact, "item_id": "item-b", "snapshot_signature": "other-snapshot"}
        second = self.save(other)
        self.assertNotEqual(first["note_id"], second["note_id"])
        self.assertNotEqual(first["path"], second["path"])
        self.assertEqual(self.registry.read_slide_design("item-a", "run-a"), self.artifact)
        self.assertEqual(self.registry.read_slide_design("item-b", "run-a"), other)
        with self.assertRaises(StoreConflict):
            self.registry.read_slide_design("item-a", "run-b")

    def test_read_returns_defensive_copy_and_is_read_only(self):
        self.save()
        before = self.files()
        artifact = self.registry.read_slide_design("item-a", "run-a")
        artifact["provenance"]["annotation_version"] = 900
        self.assertEqual(self.registry.read_slide_design("item-a", "run-a"), self.artifact)
        self.assertEqual(before, self.files())

    def test_incomplete_ledger_and_cross_vault_records_fail_without_repair(self):
        receipt = self.save()
        baseline = self.registry.load()
        for field, value in (("pending", "uncommitted-hash"), ("sync", "writing"),
                             ("sync", "missing"), ("vault", "input")):
            with self.subTest(field=field, value=value):
                ledger = copy.deepcopy(baseline)
                ledger["notes"][receipt["note_id"]][field] = value
                self.registry.save(ledger)
                before = self.files()
                with self.assertRaises(StoreConflict):
                    self.registry.read_slide_design("item-a", "run-a")
                self.assertEqual(before, self.files())

    def test_deleted_design_is_still_missing_after_new_registry_instance(self):
        receipt = self.save()
        path = self.registry.root("visualization") / receipt["path"]
        path.unlink()
        new_registry = VaultRegistry(self.base / "data" / "library.sqlite3", self.base / "software")
        with self.assertRaises(StoreConflict):
            new_registry.publish_slide_design("item-a", "run-a", self.artifact)
        self.assertFalse(path.exists())
        events = [json.loads(line) for line in new_registry.note_log.read_text().splitlines()]
        self.assertTrue(any(event["path"] == receipt["path"] and event["action"] == "missing" for event in events))

    def test_cross_run_catalog_reference_fails_read(self):
        first = self.save()
        other = {**self.artifact, "run_id": "run-b", "snapshot_signature": "other-snapshot"}
        second = self.save(other)
        ledger = self.registry.load()
        ledger["slide_designs"][entity_key("item-a\nrun-a")]["note_id"] = second["note_id"]
        self.registry.save(ledger)
        with self.assertRaises(StoreConflict):
            self.registry.read_slide_design("item-a", "run-a")
        self.assertEqual(self.registry.read_slide_design("item-a", "run-b"), other)

    def test_publication_interruption_before_receipt_never_fakes_success(self):
        # Failure before the final catalog commit must leave the gate closed;
        # this only exercises a design note, never deck content.
        with patch.object(self.registry, "_finish", side_effect=OSError("synthetic interruption")):
            with self.assertRaises(OSError):
                self.save()
        with self.assertRaises(StoreConflict):
            self.registry.read_slide_design("item-a", "run-a")
        self.assertIn(self.save()["status"], ("written", "unchanged", "overwritten"))
        self.assertEqual(self.registry.read_slide_design("item-a", "run-a"), self.artifact)

    def test_json_fence_payload_is_inert_recorded_data(self):
        artifact = {**self.artifact, "prompt": "synthetic ~~~ </script> [[other-vault]] ```"}
        receipt = self.save(artifact)
        content = (self.registry.root("visualization") / receipt["path"]).read_text()
        self.assertEqual(content.count("~~~"), 2)
        self.assertEqual(self.registry.read_slide_design("item-a", "run-a"), artifact)


class HistoryProjectionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.sqlite3"
        self.snapshot = {"input_hash": "input-v1", "evidence": [{"evidence_id": "evidence-a", "utterance_id": "utterance-a",
                         "speaker": "Synthetic speaker", "text": "Synthetic frozen original", "excluded": False,
                         "start": 0, "end": 1, "source_hash": "synthetic-hash"}]}
        with self.connect() as db:
            initialize_orchestration_store(db)
            db.execute("INSERT INTO orchestration_initials VALUES (?,?,?,?,?,?,?,?)",
                       ("initial-a", "identity-a", "item-a", "ready", json.dumps(self.snapshot), fingerprint(self.snapshot), "", "2026-10-04T12:00:00+00:00"))
            run = {"item_id": "item-a", "run_id": "run-a", "initial_id": "initial-a", "annotation_version": 0,
                   "config": {"question": "Synthetic research"}, "current_view": {}, "input_hash": "input-v1", "label_audit_version": 1}
            db.execute("INSERT INTO orchestration_runs VALUES (?,?,?,?,?,?)", ("run-a", "item-a", "request-a", "request-hash", "initial-a", json.dumps(run)))
            db.execute("INSERT INTO orchestration_label_versions VALUES (?,?,?)", ("run-a", 0, json.dumps({"utterance-a": {"codes": ["frozen"]}})))
        self.history = AnalysisHistoryService(connect=self.connect, find_item=lambda item: {"id": item} if item in {"item-a", "item-b"} else None)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def result(self, raw, status="valid"):
        meta = {"result_id": "result-a", "task_id": "task-a", "role": "interpretation", "received_at": "2026-10-04T12:01:00+00:00",
                "annotation_version": 0, "validation_status": status, "raw_hash": fingerprint(raw)}
        with self.connect() as db:
            db.execute("INSERT INTO orchestration_results VALUES (?,?,?,?,?)", ("result-a", "run-a", "task-a", json.dumps(raw), json.dumps(meta)))

    def test_projection_and_source_reads_never_change_database(self):
        self.result({"summary": "Public summary", "scratchpad": "SECRET_SCRATCH", "claims": []})
        before = self.path.read_bytes()
        runs = self.history.runs("item-a")
        timeline = self.history.timeline("item-a", "run-a")
        detail = self.history.entry("item-a", "run-a", "result:result-a")
        source = self.history.source("item-a", "run-a", "utterance-a")
        self.assertEqual(before, self.path.read_bytes())
        self.assertNotIn("SECRET_SCRATCH", json.dumps([runs, timeline, detail, source]))
        self.assertNotIn("Synthetic frozen original", json.dumps([runs, timeline, detail]))
        self.assertEqual(source["source"]["text"], "Synthetic frozen original")

    def test_cross_conversation_read_is_denied(self):
        for callback in (lambda: self.history.timeline("item-b", "run-a"),
                         lambda: self.history.entry("item-b", "run-a", "initial:initial-a"),
                         lambda: self.history.source("item-b", "run-a", "utterance-a")):
            with self.assertRaises(LookupError):
                callback()

    def test_hundreds_of_events_are_reachable_exactly_once_by_pagination(self):
        with self.connect() as db:
            for i in range(127):
                event = {"created_at": "2026-10-04T12:01:00+00:00", "from": "handler", "type": "synthetic", "message": str(i)}
                db.execute("INSERT INTO orchestration_events(run_id,payload_json) VALUES (?,?)", ("run-a", json.dumps(event)))
        entries = []
        for offset in (0, 30, 60, 90, 120):
            page = self.history.timeline("item-a", "run-a", kind="event", offset=offset, limit=30)
            self.assertEqual(page["pagination"]["total"], 127)
            entries.extend(e["entry_id"] for e in page["entries"])
        self.assertEqual(len(entries), 127)
        self.assertEqual(len(set(entries)), 127)
        self.assertFalse(page["pagination"]["has_more"])

    def test_source_rejects_tampered_fixed_snapshot(self):
        with self.connect() as db:
            changed = copy.deepcopy(self.snapshot)
            changed["evidence"][0]["text"] = "Changed text"
            db.execute("UPDATE orchestration_initials SET snapshot_json=?", (json.dumps(changed),))
        with self.assertRaises(ValueError):
            self.history.source("item-a", "run-a", "utterance-a")

    def test_result_payload_hash_mismatch_cannot_be_presented_as_saved_content(self):
        self.result({"summary": "Original synthetic result", "claims": []})
        with self.connect() as db:
            db.execute("UPDATE orchestration_results SET raw_json=?", (json.dumps({"summary": "Tampered synthetic result", "claims": []}),))
        with self.assertRaises(ValueError):
            self.history.entry("item-a", "run-a", "result:result-a")

    def test_run_input_hash_cannot_relabel_another_frozen_snapshot(self):
        with self.connect() as db:
            run = json.loads(db.execute("SELECT state_json FROM orchestration_runs").fetchone()[0])
            run["input_hash"] = "different-input-hash"
            db.execute("UPDATE orchestration_runs SET state_json=?", (json.dumps(run),))
        with self.assertRaises(ValueError):
            self.history.source("item-a", "run-a", "utterance-a")

    def test_label_proposal_keeps_actual_values_and_separates_proposed_value(self):
        no_calls = unittest.mock.Mock(side_effect=AssertionError("No execution permitted"))
        service = AnalysisOrchestrationService(connect=self.connect, find_item=lambda _: {"id": "item-a"},
            snapshot_builder=no_calls, agent_runner=no_calls, method_runner=no_calls, schedule=False)
        with self.connect() as db:
            run = json.loads(db.execute("SELECT state_json FROM orchestration_runs").fetchone()[0])
            run["codebook_version"] = 1
            proposal = {"utterance_id": "utterance-a", "field": "codes", "operation": "update",
                        "old_value": ["model-asserted-incorrect-old"], "new_value": ["proposed-only"],
                        "reason": "Synthetic proposal", "evidence_ids": ["evidence-a"],
                        "base_annotation_version": 0, "codebook_version": 1}
            service._save_patch(db, run, {"task_id": "task-a", "role": "interpretation"}, proposal, {"result_id": "result-a"})
            event = json.loads(db.execute("SELECT payload_json FROM orchestration_label_audit").fetchone()[0])
            self.assertEqual(event["disposition"], "proposal")
            self.assertEqual(event["before_value"], ["frozen"])
            self.assertEqual(event["after_value"], ["frozen"])
            self.assertTrue(event["before_present"])
            self.assertTrue(event["after_present"])
            self.assertEqual(event["proposed_value"], ["proposed-only"])
            self.assertEqual(event["before_annotation_version"], event["after_annotation_version"])
            self.assertEqual(json.loads(db.execute("SELECT payload_json FROM orchestration_label_versions").fetchone()[0])["utterance-a"]["codes"], ["frozen"])
            # A delayed proposal can describe a fixed older base. Its shown
            # before/after values must not be relabelled as the latest version.
            run["annotation_version"] = 1
            db.execute("INSERT INTO orchestration_label_versions VALUES (?,?,?)", ("run-a", 1, json.dumps({"utterance-a": {"codes": ["new-current"]}})))
            service._save_patch(db, run, {"task_id": "task-b", "role": "interpretation"}, proposal, {"result_id": "result-b"})
            delayed = json.loads(db.execute("SELECT payload_json FROM orchestration_label_audit ORDER BY rowid DESC LIMIT 1").fetchone()[0])
            self.assertEqual(delayed["before_value"], ["frozen"])
            self.assertEqual(delayed["after_value"], ["frozen"])
            self.assertEqual(delayed["before_annotation_version"], 0)
            self.assertEqual(delayed["after_annotation_version"], 0)
        no_calls.assert_not_called()

    def test_quarantined_malformed_claim_is_readable_without_crashing(self):
        self.result({"summary": "Malformed synthetic result", "claims": [{"text": "Not validated", "evidence_ids": None}]}, "quarantined")
        detail = self.history.entry("item-a", "run-a", "result:result-a")
        self.assertEqual(detail["entry"]["status"], "quarantined")
        self.assertEqual(detail["evidence"], [])


class LabelAdapterContractReviewTests(unittest.TestCase):
    def test_delete_operation_is_expressible_in_both_provider_schemas(self):
        from gurumoji.services.analysis_orchestration_adapters import (
            ADAPTER_VERSION, COMMON_PROMPT, CRITIC_SCHEMA, SPECIALIST_SCHEMA)
        self.assertEqual(ADAPTER_VERSION, "core-handler-prompts-2-label-audit")
        for schema in (CRITIC_SCHEMA, SPECIALIST_SCHEMA):
            patch_schema = schema["properties"]["label_patches"]["items"]
            self.assertIn("operation", patch_schema["required"])
            self.assertEqual(set(patch_schema["properties"]["operation"]["enum"]), {"add", "update", "delete"})
            self.assertIn({"type": "null"}, patch_schema["properties"]["new_value"]["anyOf"])
            self.assertFalse(patch_schema["additionalProperties"])
        self.assertIn("deleteではnew_value=null", COMMON_PROMPT)

    def test_old_adapter_run_remains_readable_but_cannot_resume(self):
        from gurumoji.services.analysis_orchestration_adapters import ADAPTER_VERSION
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.sqlite3"
            def connect():
                db = sqlite3.connect(path)
                db.row_factory = sqlite3.Row
                return db
            item = {"id": "synthetic-item", "revision": "input-v1"}
            builder = lambda _: {"input_hash": "input-v1", "analysis": {"segments": [
                {"id": "u1", "text": "Synthetic fixed utterance", "speaker": "S1", "annotation": {"codes": ["code-a"]}}]}}
            agent = unittest.mock.Mock(side_effect=AssertionError("No provider calls permitted"))
            dependencies = dict(connect=connect, find_item=lambda key: item if key == item["id"] else None,
                                snapshot_builder=builder, source_fingerprint=lambda _: "input-v1",
                                agent_runner=agent, method_runner=agent, schedule=False)
            old = AnalysisOrchestrationService(**dependencies, adapter_version="core-handler-prompts-1")
            run = old.start(item["id"], {"model": "synthetic-model", "adapter_version": "core-handler-prompts-1"})
            current = AnalysisOrchestrationService(**dependencies, adapter_version=ADAPTER_VERSION)
            self.assertEqual(current.result(item["id"], run["run_id"])["run"]["run_id"], run["run_id"])
            history = AnalysisHistoryService(connect=connect, find_item=dependencies["find_item"])
            self.assertEqual(history.runs(item["id"])["runs"][0]["run_id"], run["run_id"])
            with self.assertRaises(AnalysisContractError) as caught:
                current.resume(item["id"], run["run_id"])
            self.assertEqual(caught.exception.code, "adapter_version_conflict")
            self.assertEqual(current.status(item["id"], run["run_id"])["status"], "queued")
            agent.assert_not_called()


class SlidesReviewHoldBoundaryTests(unittest.TestCase):
    def test_review_hold_prevents_renderer_and_download_without_generating_content(self):
        from flask import Flask
        from gurumoji.services.analysis_slides import AnalysisSlidesService
        from gurumoji.web.analysis_slides_routes import register_analysis_slides_routes
        service = AnalysisSlidesService(export_result=lambda *_: None, vault_factory=lambda: None)
        app = Flask(__name__)
        register_analysis_slides_routes(app, lambda: service)
        # No source projection is run: exercise only the download guard with a
        # held-state DTO containing no slides or analytical content.
        held = {"review_required": True, "download": {"available": False, "reason": "Synthetic review hold"}}
        with patch.object(service, "preview", return_value=held), patch("gurumoji.services.analysis_slides.render_presentation") as render:
            with self.assertRaises(AnalysisContractError) as caught:
                service.presentation("item-a", "run-a", expected_snapshot="sha256:" + "a" * 64)
            self.assertEqual(caught.exception.code, "slide_review_required")
            response = app.test_client().get("/api/library/item-a/analysis/orchestration/run-a/slides/presentation.pptx",
                                            query_string={"expected_snapshot": "sha256:" + "a" * 64})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.get_json()["reason_code"], "slide_review_required")
            render.assert_not_called()


class SlidesEvidenceIntegrityReviewTests(unittest.TestCase):
    def test_missing_excluded_or_cross_dataset_evidence_never_enables_download(self):
        from test_analysis_slides import fixture
        from gurumoji.services.analysis_slide_templates import load_slide_templates
        from gurumoji.services.analysis_slides import AnalysisSlidesService
        templates = load_slide_templates(Path(__file__).resolve().parents[1])
        self.assertTrue(templates, "The reviewed design must be saved before this test runs")
        for case in ("missing_evidence", "excluded_evidence", "wrong_result_dataset", "wrong_evidence_dataset"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as root:
                value = fixture()
                if case == "missing_evidence":
                    value["run"]["current_view"]["claims"][0]["evidence_ids"] = ["missing-id"]
                    value["raw_results"][0]["raw"]["claims"][0]["evidence_ids"] = ["missing-id"]
                    value["raw_results"][0]["raw_hash"] = fingerprint(value["raw_results"][0]["raw"])
                elif case == "excluded_evidence":
                    value["initial"]["snapshot"]["evidence"][0]["excluded"] = True
                    value["initial"]["hash"] = fingerprint(value["initial"]["snapshot"])
                elif case == "wrong_result_dataset":
                    value["raw_results"][0]["dataset_version"] = "different-input"
                else:
                    value["initial"]["snapshot"]["evidence"][0]["dataset_version"] = "different-input"
                    value["initial"]["hash"] = fingerprint(value["initial"]["snapshot"])
                vault = VaultRegistry(Path(root) / "data/library.sqlite3", Path(root) / "software")
                service = AnalysisSlidesService(export_result=lambda *_: copy.deepcopy(value), vault_factory=lambda: vault, templates=templates)
                try:
                    service.save_design("item-1", "run-1")
                    preview = service.preview("item-1", "run-1")
                except AnalysisContractError as exc:
                    self.assertEqual(exc.code, "slide_snapshot_invalid")
                    continue
                self.assertTrue(preview["review_required"])
                self.assertFalse(preview["download"]["available"])
                with patch("gurumoji.services.analysis_slides.render_presentation") as render:
                    with self.assertRaises(AnalysisContractError) as caught:
                        service.presentation("item-1", "run-1", expected_snapshot=preview["snapshot_signature"])
                    self.assertEqual(caught.exception.code, "slide_review_required")
                    render.assert_not_called()


if __name__ == "__main__":
    unittest.main()
