"""Deterministic staged initial recovery; temporary SQLite and synthetic inputs only."""
import copy
import json
import threading
import unittest
from collections import Counter
from contextlib import contextmanager
from unittest import mock

from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.analysis_orchestration import recover_orchestration_runs
from gurumoji.orchestration_initial import InitialStage
import test_analysis_orchestration as runtime_tests


class SimulatedCrash(BaseException):
    pass


class SyntheticBuilder:
    version = "synthetic-initial-1"
    stages = (InitialStage("base", "Base"), InitialStage("statistics", "Statistics"),
              InitialStage("snapshot", "Snapshot"))

    def __init__(self, fixture):
        self.fixture = fixture
        self.counts = Counter()
        self.freeze_count = 0
        self.hook = lambda stage: None

    def freeze(self, row):
        self.freeze_count += 1
        return {"row": dict(row), "snapshot": copy.deepcopy(self.fixture.snapshot)}

    def run_stage(self, stage, frozen, outputs):
        self.counts[stage] += 1
        self.hook(stage)
        if stage == "base":
            return {"frozen_saved_view": frozen["row"].get("saved_view", "original")}
        if stage == "statistics":
            return {"n": 2, "missing": None, "value": 0}
        result = copy.deepcopy(frozen["snapshot"])
        result["analysis"]["staged_statistics"] = copy.deepcopy(outputs["statistics"])
        result["analysis"]["saved_view"] = outputs["base"]["frozen_saved_view"]
        return result


class InitialRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f = runtime_tests.RuntimeTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.item.update(revision_count=1, analysis_revision=2)
        self.builder = SyntheticBuilder(self.f)
        self.f.service = self.f.make_service(initial_builder=self.builder)

    def failed_snapshot(self, crash=False):
        def fail(stage):
            if stage == "snapshot":
                raise SimulatedCrash() if crash else RuntimeError("Synthetic stage failure")
        self.builder.hook = fail
        run = self.f.start(request_id="staged-request")
        if crash:
            with self.assertRaises(SimulatedCrash):
                self.f.service.run(run["run_id"])
        else:
            self.f.service.run(run["run_id"])
        return self.f.service.status("conversation", run["run_id"])

    def test_early_run_progress_and_incomplete_result_are_honest(self):
        run = self.f.start(request_id="early")
        self.assertEqual(run["phase"], "initial")
        self.assertEqual(run["initial"]["completed_stages"], 0)
        self.assertEqual(self.builder.counts, {})
        self.assertFalse(self.f.calls)
        self.assertEqual(run["allowed_actions"], ["resume", "cancel"])
        result = self.f.service.result("conversation", run["run_id"])
        self.assertIsNone(result["initial"]["snapshot"])
        self.assertIsNone(result["initial"]["hash"])
        self.assertEqual(result["label_versions"], [])

    def test_failure_resume_never_recalculates_completed_statistics(self):
        run = self.failed_snapshot()
        self.assertEqual(run["status"], "recovery_required")
        self.assertEqual([s["status"] for s in run["initial_stages"]], ["completed", "completed", "failed"])
        self.assertFalse(self.f.calls)
        before = copy.deepcopy(run["initial_stages"][:2])
        with self.f.connect() as db:
            encoded = db.execute("SELECT output_json FROM orchestration_initial_stages WHERE stage_id='statistics'").fetchone()[0]
        self.builder.hook = lambda _: None
        self.f.service = self.f.make_service(initial_builder=self.builder)
        self.f.service.resume("conversation", run["run_id"])
        complete = self.f.drive(run)
        self.assertEqual(complete["status"], "completed", complete)
        self.assertEqual(complete["initial_stages"][:2], before)
        self.assertEqual(self.builder.counts, {"base": 1, "statistics": 1, "snapshot": 2})
        with self.f.connect() as db:
            self.assertEqual(db.execute("SELECT output_json FROM orchestration_initial_stages WHERE stage_id='statistics'").fetchone()[0], encoded)

    def test_startup_marks_only_and_resumes_after_committed_statistics(self):
        run = self.failed_snapshot(crash=True)
        counts = self.builder.counts.copy()
        with self.f.connect() as db:
            recover_orchestration_runs(db)
        self.assertEqual(self.builder.counts, counts)
        state = self.f.service.status("conversation", run["run_id"])
        self.assertEqual(state["status"], "recovery_required")
        self.assertEqual(state["initial_stages"][-1]["error"], "initial_stage_interrupted")
        self.builder.hook = lambda _: None
        self.f.service = self.f.make_service(initial_builder=self.builder)
        self.f.service.resume("conversation", run["run_id"])
        state = self.f.drive(run)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(self.builder.counts["statistics"], 1)

    def test_crash_after_last_stage_commit_adopts_without_replaying_any_stage(self):
        run = self.f.start()
        original_db = self.f.service._db
        crashed = False

        @contextmanager
        def crash_after_commit():
            nonlocal crashed
            trigger = False
            with original_db() as db:
                yield db
                row = db.execute("SELECT state_json FROM orchestration_initial_stages WHERE stage_id='snapshot'").fetchone()
                initial = db.execute("SELECT status FROM orchestration_initials WHERE initial_id=?", (run["initial_id"],)).fetchone()
                trigger = bool(row and json.loads(row[0])["status"] == "completed" and initial[0] != "ready")
            if trigger and not crashed:
                crashed = True
                raise SimulatedCrash()

        with mock.patch.object(self.f.service, "_db", crash_after_commit):
            with self.assertRaises(SimulatedCrash):
                self.f.service.run(run["run_id"])
        before = self.f.service.status("conversation", run["run_id"])["initial_stages"]
        self.assertTrue(all(stage["status"] == "completed" for stage in before))
        self.assertIsNone(self.f.service.result("conversation", run["run_id"])["initial"]["snapshot"])
        with self.f.connect() as db:
            recover_orchestration_runs(db)
        self.f.service = self.f.make_service(initial_builder=self.builder)
        self.f.service.resume("conversation", run["run_id"])
        complete = self.f.drive(run)
        self.assertEqual(complete["status"], "completed")
        self.assertEqual(complete["initial_stages"], before)
        self.assertEqual(self.builder.counts, {"base": 1, "statistics": 1, "snapshot": 1})

    def test_initial_deadline_stops_later_stages_and_core_after_inflight_commit(self):
        now = [100.0]
        def advance_clock(stage):
            if stage == "statistics":
                now[0] = 102.0
        self.builder.hook = advance_clock
        run = self.f.start(stop_mode="time", time_limit_seconds=1)
        with mock.patch("gurumoji.analysis_orchestration.time.time", side_effect=lambda: now[0]):
            current = self.f.drive(run)
        self.assertEqual(current["status"], "stopped")
        self.assertEqual(current["stop_reason"], "time_limit")
        self.assertEqual(current["deadline"], 101.0)
        self.assertEqual(current["initial_stages"][1]["status"], "completed")
        self.assertEqual(self.builder.counts, {"base": 1, "statistics": 1})
        self.assertFalse(self.f.calls)
        self.assertIsNone(self.f.service.result("conversation", run["run_id"])["initial"]["snapshot"])

    def test_initial_deadline_before_final_adoption_keeps_snapshot_unadopted(self):
        now = [100.0]
        def advance_clock(stage):
            if stage == "snapshot":
                now[0] = 102.0
        self.builder.hook = advance_clock
        run = self.f.start(stop_mode="time", time_limit_seconds=1)
        with mock.patch("gurumoji.analysis_orchestration.time.time", side_effect=lambda: now[0]):
            current = self.f.drive(run)
        self.assertEqual(current["stop_reason"], "time_limit")
        self.assertTrue(all(stage["status"] == "completed" for stage in current["initial_stages"]))
        self.assertIsNone(self.f.service.result("conversation", run["run_id"])["initial"]["snapshot"])
        self.assertFalse(self.f.calls)

    def test_initial_resume_keeps_original_deadline(self):
        now = [100.0]
        def fail(stage):
            if stage == "snapshot":
                raise RuntimeError("Synthetic failure")
        self.builder.hook = fail
        run = self.f.start(stop_mode="time", time_limit_seconds=1)
        with mock.patch("gurumoji.analysis_orchestration.time.time", side_effect=lambda: now[0]):
            failed = self.f.drive(run)
            self.assertEqual(failed["status"], "recovery_required")
            self.assertEqual(failed["deadline"], 101.0)
            self.builder.hook = lambda _: None
            now[0] = 102.0
            self.f.service.resume("conversation", run["run_id"])
            current = self.f.drive(run)
        self.assertEqual(current["stop_reason"], "time_limit")
        self.assertEqual(current["deadline"], 101.0)
        self.assertEqual(current["started_at"], failed["started_at"])
        self.assertEqual(self.builder.counts["snapshot"], 1)
        self.assertFalse(self.f.calls)

    def test_cancel_checkpoints_inflight_but_never_adopts_or_calls_core(self):
        entered, release = threading.Event(), threading.Event()
        def hold(stage):
            if stage == "statistics":
                entered.set()
                self.assertTrue(release.wait(3))
        self.builder.hook = hold
        run = self.f.start()
        worker = threading.Thread(target=self.f.service.run, args=(run["run_id"],))
        worker.start()
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(2))
        cancelled = self.f.service.cancel("conversation", run["run_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        release.set(); worker.join(3)
        current = self.f.service.status("conversation", run["run_id"])
        self.assertEqual(current["initial_stages"][1]["status"], "completed")
        self.assertIsNone(self.f.service.result("conversation", run["run_id"])["initial"]["snapshot"])
        self.assertEqual(self.builder.counts["snapshot"], 0)
        self.assertFalse(self.f.calls)
        with self.assertRaises(AnalysisContractError):
            self.f.service.resume("conversation", run["run_id"])
        new = self.f.start(request_id="explicit-new-after-cancel")
        self.assertNotEqual(new["run_id"], run["run_id"])
        self.assertEqual(self.f.drive(new)["status"], "completed")
        self.assertEqual(self.builder.counts["statistics"], 1)
        self.assertEqual(self.f.service.status("conversation", run["run_id"])["status"], "cancelled")

    def test_changed_source_refuses_resume_without_recalculation(self):
        run = self.failed_snapshot()
        self.f.item["revision"] = "input-v2"
        before = self.builder.counts.copy()
        self.assertFalse(self.f.service.status("conversation", run["run_id"])["can_resume"])
        with self.assertRaises(AnalysisContractError) as exc:
            self.f.service.resume("conversation", run["run_id"])
        self.assertEqual(exc.exception.code, "revision_conflict")
        self.assertEqual(self.builder.counts, before)
        self.assertFalse(self.f.calls)

    def test_frozen_nonfingerprinted_saved_fields_survive_resume(self):
        self.f.item["saved_view"] = "before"
        run = self.failed_snapshot()
        self.f.item["saved_view"] = "after"
        self.builder.hook = lambda _: None
        self.f.service.resume("conversation", run["run_id"])
        self.f.drive(run)
        snapshot = self.f.service.result("conversation", run["run_id"])["initial"]["snapshot"]
        self.assertEqual(snapshot["analysis"]["saved_view"], "before")

    def test_stage_hash_and_builder_version_refuse_resume(self):
        run = self.failed_snapshot()
        original = self.builder.version
        self.builder.version = "incompatible"
        state = self.f.service.status("conversation", run["run_id"])
        self.assertFalse(state["can_resume"])
        self.assertEqual(state["initial"]["recovery_error"], "initial_version_conflict")
        with self.assertRaises(AnalysisContractError):
            self.f.service.resume("conversation", run["run_id"])
        self.builder.version = original
        with self.f.connect() as db:
            db.execute("UPDATE orchestration_initial_stages SET output_json='{}' WHERE stage_id='statistics'")
        self.assertFalse(self.f.service.status("conversation", run["run_id"])["can_resume"])
        with self.assertRaises(AnalysisContractError) as exc:
            self.f.service.resume("conversation", run["run_id"])
        self.assertEqual(exc.exception.code, "initial_hash_mismatch")
        self.assertEqual(self.builder.counts["statistics"], 1)

    def test_duplicate_start_returns_same_run_other_request_cannot_steal_build(self):
        run = self.f.start(request_id="same-initial")
        same = self.f.start(request_id="same-initial")
        self.assertEqual(run["run_id"], same["run_id"])
        self.assertEqual(self.builder.freeze_count, 1)
        with self.assertRaises(AnalysisContractError):
            self.f.start(request_id="other-initial")
        self.assertFalse(self.builder.counts)

    def test_legacy_completed_initial_is_reused_without_stages_or_freeze(self):
        self.f.service = self.f.make_service()
        legacy = self.f.start(request_id="legacy")
        expected = self.f.service.result("conversation", legacy["run_id"])["initial"]
        self.f.service = self.f.make_service(initial_builder=self.builder)
        new = self.f.start(request_id="reuse-legacy")
        self.assertEqual(new["phase"], "core")
        self.assertEqual(new["initial_id"], legacy["initial_id"])
        self.assertEqual(new["initial_stages"], [])
        self.assertEqual(self.builder.freeze_count, 0)
        self.assertEqual(self.f.service.result("conversation", new["run_id"])["initial"], expected)

    def test_completed_callback_runs_outside_transaction_once_and_failure_is_separate(self):
        callback_calls = []
        def callback(item_id, run_id):
            with self.f.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                state = json.loads(db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (run_id,)).fetchone()[0])
                self.assertEqual(state["status"], "completed")
                callback_calls.append((item_id, run_id))
            raise RuntimeError("Synthetic publication failure")
        self.f.service = self.f.make_service(initial_builder=self.builder, on_complete=callback)
        run = self.f.drive(self.f.start())
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["completion_callback_status"], "failed")
        self.assertEqual(run["publication_error"], "RuntimeError")
        self.f.service.run(run["run_id"])
        self.assertEqual(callback_calls, [("conversation", run["run_id"])])
        self.assertEqual(self.builder.counts["statistics"], 1)

    def test_publication_default_and_legacy_resume_cannot_expand_scope(self):
        run = self.f.start()
        self.assertEqual(run["config"]["publication_targets"], [])
        self.assertEqual(run["config"]["effective_publication_writers"], [])
        with self.f.connect() as db:
            state = json.loads(db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (run["run_id"],)).fetchone()[0])
            del state["config"]["publication_targets"]
            del state["config"]["effective_publication_writers"]
            db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (json.dumps(state), run["run_id"]))
        with self.assertRaises(AnalysisContractError) as exc:
            self.f.service.resume("conversation", run["run_id"], {"publication_targets": ["input", "orchestrator", "visualization"]})
        self.assertEqual(exc.exception.code, "publication_scope_conflict")

    def test_old_request_hash_deduplicates_without_new_publication_authority(self):
        run = self.f.start(request_id="old-request")
        with self.f.connect() as db:
            state = json.loads(db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (run["run_id"],)).fetchone()[0])
            del state["config"]["publication_targets"]
            del state["config"]["effective_publication_writers"]
            old_hash = fingerprint({"item_id": "conversation", "config": state["config"],
                                    "source_revision": None, "analysis_revision": None, "input_hash": None})
            db.execute("UPDATE orchestration_runs SET request_hash=?,state_json=? WHERE run_id=?", (old_hash, json.dumps(state), run["run_id"]))
        same = self.f.start(request_id="old-request")
        self.assertEqual(same["run_id"], run["run_id"])
        self.assertEqual(same["config"]["publication_targets"], [])
        with self.assertRaises(AnalysisContractError):
            self.f.start(request_id="old-request", publication_targets=["input", "orchestrator", "visualization"])

    def test_result_locked_shares_caller_transaction(self):
        run = self.f.start()
        with self.f.service._db() as db:
            payload = self.f.service.result_locked(db, "conversation", run["run_id"])
        self.assertEqual(payload["run"]["run_id"], run["run_id"])


class ProductionStageParityTests(unittest.TestCase):
    def test_warm_cache_staged_snapshot_matches_existing_normal_snapshot(self):
        import app
        import test_content_analysis as support
        import gurumoji.research_analysis as research
        from gurumoji.analysis_core import canonical
        from gurumoji.services.analysis_pipeline_adapters import make_staged_initial_builder

        fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        row = app.library_row("content")
        builder = make_staged_initial_builder(
            archive_snapshot=app.archive_snapshot, archive_source_stamp=app.archive_source_stamp,
            group_analysis_for_row=app.group_analysis_for_row)
        with mock.patch("gurumoji.services.group_analysis.utc_now_iso", return_value="2026-10-04T00:00:00+00:00"):
            expected = app.build_analysis_pipeline_snapshot(row)
            # Expected calculation populated the process cache. The staged base
            # must still be pure and the true statistics stage must run once.
            with mock.patch.object(research, "_statistics_analysis", wraps=research._statistics_analysis) as statistics:
                frozen = json.loads(canonical(builder.freeze(row)))
                outputs = {}
                for stage in builder.stages:
                    outputs[stage.stage_id] = json.loads(canonical(builder.run_stage(stage.stage_id, frozen, outputs)))
                    if stage.stage_id == "base":
                        self.assertNotIn("research", outputs["base"]["analysis"])
                self.assertEqual(statistics.call_count, 1)
        self.assertEqual(outputs["snapshot"], json.loads(canonical(expected)))
        self.assertEqual(fingerprint(outputs["snapshot"]), fingerprint(expected))


if __name__ == "__main__":
    unittest.main()
