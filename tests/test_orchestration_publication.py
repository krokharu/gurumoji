"""Synthetic fixed-output and temporary-Vault regressions; no external models."""
import copy
import json
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support
from test_analysis_orchestration import stop, critic
from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.analysis_orchestration import AnalysisOrchestrationService, validate_orchestration_payload
from gurumoji.analysis_store import AnalysisStore, StoreConflict
from gurumoji.services.analysis_orchestration_publication import (
    AnalysisOrchestrationPublicationService, recover_orchestration_publications,
)
from gurumoji.vault_registry import VaultRegistry

TARGETS = ["input", "orchestrator", "visualization"]


class OrchestrationPublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store = app.analysis_archive_store()
        segments = [{"id": "u1", "text": "Synthetic ANALYSIS VERSION", "speaker": "A", "start": 0, "end": 1},
                    {"id": "u2", "text": "Synthetic second view", "speaker": "B", "start": 2, "end": 3}]
        self.snapshot = {"input_hash": "input-v0", "source_revision": 0, "analysis_revision": 1,
            "analysis": {"segments": segments, "all_results": {"hidden": [0, None, 42]}},
            "archive_snapshot": {"title": "Synthetic publication", "segments": segments,
                "original_source": {"segments": [{**row, "text": "Synthetic ORIGINAL VERSION"} for row in segments]}}}
        self.runtime = AnalysisOrchestrationService(connect=app.database_connection, find_item=app.library_row,
            source_fingerprint=lambda row: "input-v" + str(row["revision_count"]),
            snapshot_builder=lambda row: copy.deepcopy(self.snapshot), agent_runner=self.agent,
            method_runner=lambda *_: self.fail("No code execution expected"), schedule=False)
        self.publisher = self.make_publisher()
        self.calls = 0
        self.exports = 0

    def agent(self, role, context, *args):
        self.calls += 1
        if role == "critic":
            return critic(context)
        eid = context["raw_evidence"][0]["evidence_id"]
        return stop(summary="Synthetic readable summary", claims=[{"claim_id": "claim1", "text": "Synthetic bounded observation",
                    "kind": "observation", "evidence_ids": [eid]}])

    def source_guard(self, db, item_id, expected):
        self.assertTrue(db.in_transaction)
        row = db.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise LookupError("Source deleted")
        if "input-v" + str(row["revision_count"]) != expected:
            raise AnalysisContractError("Source changed", code="revision_conflict")
        return dict(row)

    def export(self, db, item_id, run_id):
        self.exports += 1
        return self.runtime.result_locked(db, item_id, run_id)

    def make_publisher(self):
        return AnalysisOrchestrationPublicationService(connect=app.database_connection,
            store_factory=lambda: self.store, source_guard=self.source_guard, export_locked=self.export)

    def start(self, targets=None, **extra):
        payload = {"model": "synthetic-model", "stop_mode": "auto", "max_iterations": None,
                   "time_limit_seconds": None, "publication_targets": targets if targets is not None else [], **extra}
        run = self.runtime.start("content", payload)
        self.runtime.run(run["run_id"])
        self.assertEqual(self.runtime.status("content", run["run_id"])["status"], "completed")
        return run["run_id"]

    def finalize(self, rid):
        value = self.publisher.finalize("content", rid)
        self.assertEqual(value["save_status"], "saved", value)
        return value

    def test_default_off_scope_direct_publish_retry_refresh_never_write(self):
        self.assertEqual(validate_orchestration_payload({"model": "synthetic"})["publication_targets"], [])
        rid = self.start()
        with patch.object(VaultRegistry, "publish_analysis") as generated, patch.object(AnalysisStore, "source_notes") as research:
            value = self.finalize(rid)
            self.assertEqual(value["publication_status"], "not_selected")
            self.assertFalse(value["can_retry"])
            self.store.publish(value["result_run_id"])
            self.store.retry(value["result_run_id"])
            self.store.refresh_vaults("content")
            generated.assert_not_called(); research.assert_not_called()
        with self.assertRaises(StoreConflict):
            self.store.publish(value["result_run_id"], targets=TARGETS)

    def test_invalid_scope_fails_before_runtime_or_publication(self):
        for targets in (["input"], ["research"], TARGETS + ["research"], ["input"] * 3, None, "all", {}):
            with self.subTest(targets=targets), self.assertRaises(AnalysisContractError):
                validate_orchestration_payload({"model": "synthetic", "publication_targets": targets})

    def test_full_ledger_roundtrip_artifacts_and_four_writers(self):
        rid = self.start(TARGETS)
        original = self.runtime.result("content", rid)
        value = self.finalize(rid)
        self.assertEqual(value["publication_status"], "published", value)
        self.assertTrue(value["result_run"]["vault_outputs_complete"])
        self.assertEqual({v["status"] for v in value["outcomes"].values()}, {"published"})
        _, result, _, content = self.store.verified_package(value["result_run_id"])
        self.assertEqual(result["orchestration"], original)
        self.assertEqual(result["parameters"]["sealed_hash"], fingerprint(original))
        self.assertEqual(result["parameters"]["publication_targets"], TARGETS)
        self.assertIn("tables/autonomous_summary.csv", content)
        self.assertIn("tables/autonomous_summary.json", content)
        table = self.store.read_table(value["result_run_id"], "autonomous_summary")
        self.assertEqual(table["row_count"], 1)
        self.assertEqual(table["run_id"], value["result_run_id"])
        self.assertTrue(all(a["url"].startswith("/api/analysis/artifacts/") for a in value["result_run"]["artifacts"]))
        methods = result["methods"][0]
        self.assertEqual(methods["findings"][0]["segment_ids"], ["u1"])
        self.assertEqual(methods["details"]["evidence"]["u1"]["text"], "Synthetic ANALYSIS VERSION")
        self.assertTrue(any(p.name == "autonomous_analysis.md" for p in self.store.vaults.roots()["orchestrator"].rglob("*.md")))
        note = next(p for p in self.store.vault.rglob("method-autonomous_analysis.md"))
        text = note.read_text(encoding="utf-8")
        self.assertIn("Synthetic readable summary", text)
        self.assertIn("result.json", text)
        self.assertIn("型付き全件データ", text)
        self.assertIn("tables/autonomous_summary.json", text)
        # The evidence-specific source note contains the actual analysis text.
        quoted = [p.read_text(encoding="utf-8") for p in self.store.vault.rglob("part-*.md")]
        self.assertTrue(any("Synthetic ANALYSIS VERSION" in text for text in quoted))

    def test_runs_do_not_deduplicate_different_autonomous_ledgers(self):
        first = self.finalize(self.start())
        second = self.finalize(self.start())
        self.assertNotEqual(first["result_run_id"], second["result_run_id"])
        self.assertNotEqual(first["sealed_hash"], second["sealed_hash"])

    def test_partial_publication_retry_sealed_package_without_calls(self):
        rid = self.start(TARGETS)
        with patch.object(AnalysisStore, "source_notes", side_effect=StoreConflict("Synthetic conflict")):
            first = self.finalize(rid)
        self.assertEqual(first["publication_status"], "incomplete")
        self.assertEqual(first["outcomes"]["research"]["status"], "conflict")
        before = self.calls, self.exports
        with patch.object(self.runtime, "snapshot_builder", side_effect=AssertionError("Snapshot repeated")), \
             patch.object(self.runtime, "method_runner", side_effect=AssertionError("Statistics repeated")):
            final = self.publisher.retry("content", rid)
        self.assertEqual(final["publication_status"], "published", final)
        self.assertEqual((self.calls, self.exports), before)
        self.assertEqual(first["result_run_id"], final["result_run_id"])
        attempts = self.store.publication_attempts(final["result_run_id"])
        self.assertEqual([a["status"] for a in attempts], ["incomplete", "completed"])
        self.assertEqual(attempts[0]["package_hash"], attempts[1]["package_hash"])
        self.assertEqual(set(attempts[1]["executed"]), {"research", *TARGETS})

    def test_success_reuse_checks_hash_and_guard_before_writer_reuse(self):
        rid = self.start(TARGETS)
        first = self.finalize(rid)
        with patch.object(VaultRegistry, "publish_analysis") as writer:
            again = self.publisher.retry("content", rid)
            writer.assert_not_called()
        self.assertEqual(again["publication_status"], "published")
        self.assertEqual(len(self.store.publication_attempts(first["result_run_id"])), 1)
        artifact = next(a for a in self.store.artifacts(first["result_run_id"]) if a["name"] == "result.json")
        (self.store.root / artifact["path"]).write_bytes(b"tampered")
        with patch.object(VaultRegistry, "publish_analysis") as writer:
            broken = self.publisher.retry("content", rid)
            writer.assert_not_called()
        self.assertEqual(broken["publication_status"], "conflict")

    def test_source_changed_after_completion_saves_stale_but_no_vaults(self):
        rid = self.start(TARGETS)
        with app.database_connection() as db:
            db.execute("UPDATE library_items SET revision_count=revision_count+1 WHERE id='content'")
        with patch.object(VaultRegistry, "publish_analysis") as generated, patch.object(AnalysisStore, "source_notes") as research:
            value = self.finalize(rid)
            self.assertTrue(value["stale"])
            self.assertTrue(value["result_run"]["stale"])
            self.assertEqual(value["publication_status"], "conflict")
            self.assertFalse(value["can_retry"])
            generated.assert_not_called(); research.assert_not_called()
        with self.assertRaises(StoreConflict):
            self.store.publish(value["result_run_id"])

    def test_source_deleted_blocks_seal(self):
        rid = self.start()
        with app.database_connection() as db:
            db.execute("DELETE FROM library_items WHERE id='content'")
        with self.assertRaises(LookupError):
            self.publisher.finalize("content", rid)
        self.assertFalse(self.store.list("content"))

    def test_noncompleted_runs_never_save_or_publish(self):
        run = self.runtime.start("content", {"model": "synthetic", "publication_targets": TARGETS})
        self.runtime.cancel("content", run["run_id"])
        with self.assertRaises(StoreConflict):
            self.publisher.finalize("content", run["run_id"])
        self.assertFalse(self.store.list("content"))
        state = self.publisher.status("content", run["run_id"])
        self.assertEqual(state["publication_status"], "skipped")
        self.assertEqual({value["status"] for value in state["outcomes"].values()}, {"skipped"})

    def test_tampered_initial_raw_and_attempt_ownership_block_seal(self):
        for kind in ("initial", "raw", "attempt"):
            with self.subTest(kind=kind):
                rid = self.start()
                with app.database_connection() as db:
                    if kind == "initial":
                        initial = self.runtime.status("content", rid)["initial_id"]
                        db.execute("UPDATE orchestration_initials SET snapshot_hash='changed' WHERE initial_id=?", (initial,))
                    elif kind == "raw":
                        db.execute("UPDATE orchestration_results SET raw_json='{}' WHERE run_id=?", (rid,))
                    else:
                        row = db.execute("SELECT task_id,state_json FROM orchestration_tasks WHERE run_id=? LIMIT 1", (rid,)).fetchone()
                        task = json.loads(row[1]); task["attempt_id"] = "wrong"
                        db.execute("UPDATE orchestration_tasks SET state_json=? WHERE task_id=?", (json.dumps(task), row[0]))
                with self.assertRaises(StoreConflict):
                    self.publisher.finalize("content", rid)
                # Each test run needs an independent initial when corrupting the shared cache.
                if kind == "initial":
                    with app.database_connection() as db:
                        initial = db.execute("SELECT snapshot_json FROM orchestration_initials WHERE initial_id=?", (initial,)).fetchone()[0]
                        db.execute("UPDATE orchestration_initials SET snapshot_hash=?", (fingerprint(json.loads(initial)),))

    def test_late_ledger_append_after_sealing_does_not_change_package(self):
        rid = self.start()
        first = self.finalize(rid)
        expected = self.store.verified_package(first["result_run_id"])[3]
        with app.database_connection() as db:
            db.execute("INSERT INTO orchestration_events(run_id,payload_json) VALUES (?,?)", (rid, json.dumps({"type": "late_record", "detail": "retained in live ledger"})))
        value = self.publisher.retry("content", rid)
        self.assertEqual(value["result_run_id"], first["result_run_id"])
        self.assertEqual(self.store.verified_package(value["result_run_id"])[3], expected)
        self.assertEqual(self.exports, 1)
        self.assertTrue(any(e["type"] == "late_record" for e in self.runtime.status("content", rid)["events"]))

    def test_old_run_missing_scope_fixed_saves_without_permission_expansion(self):
        rid = self.start()
        with app.database_connection() as db:
            run = json.loads(db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (rid,)).fetchone()[0])
            run["config"].pop("publication_targets", None); run["config"].pop("effective_publication_writers", None)
            db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (json.dumps(run), rid))
        value = self.finalize(rid)
        self.assertEqual(value["publication_targets"], [])
        self.assertEqual(value["publication_status"], "not_selected")

    def test_partial_retry_preserves_edited_history_and_deleted_notes(self):
        rid = self.start(TARGETS)
        with patch.object(AnalysisStore, "source_notes", side_effect=StoreConflict("Synthetic conflict")):
            first = self.finalize(rid)
        roots = self.store.vaults.roots()
        edited = roots["orchestrator"] / "10-Methods/autonomous_analysis.md"
        edited.write_text(edited.read_text(encoding="utf-8") + "\nSynthetic researcher edit to preserve\n", encoding="utf-8")
        removed = roots["visualization"] / ("10-Visuals/run-" + first["result_run_id"]) / "autonomous_analysis.md"
        self.assertTrue(removed.exists())
        removed.unlink()
        final = self.publisher.retry("content", rid)
        self.assertFalse(removed.exists())
        # The inherited writer contract treats a researcher deletion as an
        # intentional exclusion, while preserving its explicit missing record.
        self.assertEqual(final["publication_status"], "published")
        note = self.store.vaults.load()["notes"]["visual-" + first["result_run_id"] + "-autonomous_analysis"]
        self.assertEqual(note["sync"], "missing")
        histories = list((roots["orchestrator"] / "99-Archive").rglob("*.md"))
        self.assertTrue(any("Synthetic researcher edit to preserve" in path.read_text(encoding="utf-8") for path in histories))
        self.assertNotIn("Synthetic researcher edit to preserve", edited.read_text(encoding="utf-8"))

    def test_lost_save_or_publish_acknowledgement_reuses_fixed_success(self):
        for boundary in ("save", "publish"):
            with self.subTest(boundary=boundary):
                rid = self.start(TARGETS)
                original = getattr(self.store, boundary)
                def lose_ack(*args, **kwargs):
                    original(*args, **kwargs)
                    raise KeyboardInterrupt("Synthetic acknowledgement loss")
                with patch.object(self.store, boundary, side_effect=lose_ack):
                    with self.assertRaises(KeyboardInterrupt):
                        self.publisher.finalize("content", rid)
                sealed = self.publisher.status("content", rid)["sealed_hash"]
                self.publisher.recover()
                before = self.calls, self.exports
                if boundary == "publish":
                    with patch.object(VaultRegistry, "publish_analysis") as writers:
                        final = self.publisher.retry("content", rid)
                        writers.assert_not_called()
                else:
                    final = self.publisher.retry("content", rid)
                self.assertEqual(final["publication_status"], "published", final)
                self.assertEqual(final["sealed_hash"], sealed)
                self.assertEqual((self.calls, self.exports), before)
                self.assertEqual(len(self.store.publication_attempts(final["result_run_id"])), 1)

    def test_sealed_hash_mutation_and_generation_change_are_fenced(self):
        for mutation in ("hash", "generation"):
            with self.subTest(mutation=mutation):
                rid = self.start(TARGETS)
                first = self.finalize(rid)
                with app.database_connection() as db:
                    if mutation == "hash":
                        db.execute("UPDATE orchestration_publications SET sealed_hash='wrong' WHERE run_id=?", (rid,))
                    else:
                        run = json.loads(db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (rid,)).fetchone()[0])
                        run["generation"] += 1
                        db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (json.dumps(run), rid))
                with patch.object(VaultRegistry, "publish_analysis") as writers, self.assertRaises(StoreConflict):
                    self.publisher.retry("content", rid)
                writers.assert_not_called()
                self.assertEqual(len(self.store.publication_attempts(first["result_run_id"])), 1)

    def test_recoverable_save_exception_releases_attempt_without_reexport(self):
        rid = self.start()
        with patch.object(self.store, "save", side_effect=RuntimeError("Synthetic save failure")):
            failed = self.publisher.finalize("content", rid)
        self.assertEqual(failed["save_status"], "failed")
        self.assertTrue(failed["can_retry"])
        final = self.publisher.retry("content", rid)
        self.assertEqual(final["save_status"], "saved")
        self.assertEqual(final["sealed_hash"], failed["sealed_hash"])
        self.assertEqual(self.exports, 1)

    def test_recovery_marks_uncertain_attempt_and_retains_seal_for_retry(self):
        rid = self.start()
        with patch.object(self.store, "save", side_effect=KeyboardInterrupt("Synthetic process interruption")):
            with self.assertRaises(KeyboardInterrupt):
                self.publisher.finalize("content", rid)
        pending = self.publisher.status("content", rid)
        self.assertEqual(pending["save_status"], "saving")
        self.assertFalse(pending["can_retry"])
        with app.database_connection() as db:
            recover_orchestration_publications(db)
        restarted = self.make_publisher()
        self.assertEqual(restarted.status("content", rid)["save_status"], "interrupted")
        final = restarted.retry("content", rid)
        self.assertEqual(final["save_status"], "saved", final)
        self.assertEqual(final["sealed_hash"], pending["sealed_hash"])
        self.assertEqual(self.exports, 1)
        self.assertEqual(final["attempts"][0]["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
