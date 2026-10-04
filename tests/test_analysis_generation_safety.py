"""Deterministic contention tests with synthetic temporary SQLite only."""
import json
import threading
import unittest
from unittest.mock import patch

import test_analysis_definition_safety as definition_support
from gurumoji.analysis_core import AnalysisContractError
from gurumoji.analysis_pipeline import RUNTIMES, RUNTIME_LOCK, initialize_pipeline_store


class GenerationSafetyTests(unittest.TestCase):
    setUp = definition_support.DefinitionSafetyTests.setUp
    connect = definition_support.DefinitionSafetyTests.connect
    save_result = definition_support.DefinitionSafetyTests.save_result
    payload = definition_support.DefinitionSafetyTests.payload
    start = definition_support.DefinitionSafetyTests.start

    def start_auto(self):
        return self.start(definition_ids=[], mode="automatic")

    def set_waiting(self, pipeline_id):
        with self.connect() as connection:
            connection.execute("UPDATE analysis_pipeline_requests SET status='waiting',wait_reason='retry' WHERE pipeline_id=?", (pipeline_id,))
            connection.execute("UPDATE analysis_step_attempts SET status='failed' WHERE pipeline_id=? AND step_id='participation'", (pipeline_id,))

    def step(self, pipeline_id, step_id="participation"):
        with self.connect() as connection:
            return dict(connection.execute("SELECT * FROM analysis_step_attempts WHERE pipeline_id=? AND step_id=? ORDER BY attempt DESC LIMIT 1", (pipeline_id, step_id)).fetchone())

    def test_restart_before_first_step_resumes_without_consuming_planned_attempts(self):
        pipeline_id = self.start_auto()
        for expected_generation in (2, 3, 4, 5):
            with self.connect() as connection:
                initialize_pipeline_store(connection)
            state = self.service.status("synthetic", pipeline_id)
            self.assertEqual((state["status"], state["generation"]), ("accepted", expected_generation))
            self.assertEqual(self.step(pipeline_id)["attempt"], 1)
        self.service._run(pipeline_id, "http://synthetic.invalid")
        self.assertEqual(self.service._pipeline_row(pipeline_id)["status"], "completed")
        self.assertEqual(len(self.saved), 1)

    def test_restart_between_milestones_keeps_committed_sibling_and_resumes_planned(self):
        pipeline_id = self.start_auto()
        with self.connect() as connection:
            connection.execute("UPDATE analysis_pipeline_requests SET status='running',current_milestone='M1' WHERE pipeline_id=?", (pipeline_id,))
            connection.execute("UPDATE analysis_step_attempts SET status='committed',artifact_json=? WHERE pipeline_id=? AND step_id='freeze_input'",
                               (json.dumps({"fixed": "kept"}), pipeline_id))
            initialize_pipeline_store(connection)
        state = self.service.status("synthetic", pipeline_id)
        self.assertEqual((state["status"], state["generation"]), ("accepted", 2))
        frozen = self.step(pipeline_id, "freeze_input")
        self.assertEqual((frozen["status"], frozen["attempt"], frozen["artifact_json"]), ("committed", 1, json.dumps({"fixed": "kept"})))
        self.service._run(pipeline_id, "http://synthetic.invalid")
        self.assertEqual(self.service._pipeline_row(pipeline_id)["status"], "completed")

    def test_restart_after_all_steps_committed_only_finalizes_the_existing_package(self):
        pipeline_id = self.start_auto()
        self.service._run(pipeline_id, "http://synthetic.invalid")
        before = self.service._pipeline_row(pipeline_id)
        with self.connect() as connection:
            steps_before = [tuple(row) for row in connection.execute("SELECT attempt_id,status,artifact_json FROM analysis_step_attempts ORDER BY attempt_id")]
            connection.execute("UPDATE analysis_pipeline_requests SET status='running' WHERE pipeline_id=?", (pipeline_id,))
            initialize_pipeline_store(connection)
        resumed = self.service.status("synthetic", pipeline_id)
        self.assertEqual((resumed["status"], resumed["generation"]), ("accepted", 2))
        with patch.object(self.service, "method_runner") as methods, patch.object(self.service, "save_result") as save:
            self.service._run(pipeline_id, "http://synthetic.invalid")
            methods.assert_not_called(); save.assert_not_called()
        after = self.service._pipeline_row(pipeline_id)
        self.assertEqual((after["status"], after["result_run_id"]), ("completed", before["result_run_id"]))
        with self.connect() as connection:
            self.assertEqual([tuple(row) for row in connection.execute("SELECT attempt_id,status,artifact_json FROM analysis_step_attempts ORDER BY attempt_id")], steps_before)
        self.assertEqual(len(self.saved), 1)

    def test_recovery_limit_is_visible_without_get_status_raising_or_retry_action(self):
        pipeline_id = self.start_auto()
        with self.connect() as connection:
            connection.execute("UPDATE analysis_pipeline_requests SET status='running' WHERE pipeline_id=?", (pipeline_id,))
            connection.execute("UPDATE analysis_step_attempts SET status='running',attempt=3 WHERE pipeline_id=? AND step_id='participation'", (pipeline_id,))
            initialize_pipeline_store(connection)
        state = self.service.status("synthetic", pipeline_id)
        self.assertEqual(state["status"], "waiting")
        self.assertEqual(state["recovery"], {"pending": True, "mode": "blocked", "reason_code": "retry_limit_reached"})
        self.assertEqual(state["allowed_actions"], ["cancel"])
        self.assertEqual(self.service._pipeline_row(pipeline_id)["generation"], 1)

    def test_restart_preserves_cancellation_intent_without_automatic_retry(self):
        pipeline_id = self.start_auto()
        with self.connect() as connection:
            connection.execute("UPDATE analysis_pipeline_requests SET status='cancelling',cancel_requested=1 WHERE pipeline_id=?", (pipeline_id,))
            connection.execute("UPDATE analysis_step_attempts SET status='running' WHERE pipeline_id=? AND step_id='participation'", (pipeline_id,))
            initialize_pipeline_store(connection)
        state = self.service.status("synthetic", pipeline_id)
        self.assertEqual((state["status"], state["generation"]), ("cancelled", 1))
        self.service._run(pipeline_id, "http://synthetic.invalid")
        self.assertEqual(self.saved, [])

    def test_retry_rejects_accepted_running_and_cancelling_without_new_attempt(self):
        pipeline_id = self.start_auto()
        self.set_waiting(pipeline_id)
        for status in ("accepted", "running", "cancelling"):
            with self.subTest(status=status):
                with self.connect() as connection:
                    connection.execute("UPDATE analysis_pipeline_requests SET status=? WHERE pipeline_id=?", (status, pipeline_id))
                with self.assertRaises(AnalysisContractError) as caught:
                    self.service.retry("synthetic", pipeline_id, {}, app_url="http://synthetic.invalid")
                self.assertEqual(caught.exception.code, "retry_in_progress")
                self.assertEqual(self.service._pipeline_row(pipeline_id)["generation"], 1)
                self.assertEqual(self.step(pipeline_id)["attempt"], 1)

    def test_simultaneous_retries_accept_only_one_generation(self):
        pipeline_id = self.start_auto()
        self.set_waiting(pipeline_id)
        barrier = threading.Barrier(2)
        results = []
        def retry():
            barrier.wait()
            try:
                result = self.service.retry("synthetic", pipeline_id, {}, app_url="http://synthetic.invalid")
                results.append(result["status"])
            except AnalysisContractError as exc:
                results.append(exc.code)
        threads = [threading.Thread(target=retry) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(3); self.assertFalse(thread.is_alive())
        self.assertCountEqual(results, ["accepted", "retry_in_progress"])
        self.assertEqual(self.service._pipeline_row(pipeline_id)["generation"], 2)
        self.assertEqual(self.step(pipeline_id)["attempt"], 2)

    def test_old_generation_cannot_update_reused_planned_attempt(self):
        pipeline_id = self.start_auto()
        step = self.step(pipeline_id, "save_result")
        self.set_waiting(pipeline_id)
        self.service.retry("synthetic", pipeline_id, {}, app_url="http://synthetic.invalid")
        with self.assertRaises(AnalysisContractError) as caught:
            self.service._set_step(step["attempt_id"], "checking", generation=1)
        self.assertEqual(caught.exception.code, "stale_generation")
        current = self.step(pipeline_id, "save_result")
        self.assertEqual((current["attempt_id"], current["generation"], current["status"]), (step["attempt_id"], 2, "planned"))

    def test_latest_attempt_and_terminal_state_are_checked_atomically(self):
        pipeline_id = self.start_auto()
        old = self.step(pipeline_id)
        self.set_waiting(pipeline_id)
        self.service.retry("synthetic", pipeline_id, {}, app_url="http://synthetic.invalid")
        # A same-generation stale attempt must still fail the latest-attempt check.
        with self.connect() as connection:
            connection.execute("UPDATE analysis_step_attempts SET generation=2 WHERE attempt_id=?", (old["attempt_id"],))
        with self.assertRaises(AnalysisContractError) as caught:
            self.service._set_step(old["attempt_id"], "running", generation=2)
        self.assertEqual(caught.exception.code, "stale_attempt")
        current = self.step(pipeline_id)
        with self.connect() as connection:
            connection.execute("UPDATE analysis_step_attempts SET status='committed' WHERE attempt_id=?", (current["attempt_id"],))
        with self.assertRaises(AnalysisContractError):
            self.service._set_step(current["attempt_id"], "running", generation=2)
        self.assertEqual(self.step(pipeline_id)["status"], "committed")

    def test_nonterminal_attempt_cannot_move_backwards(self):
        pipeline_id = self.start_auto()
        step = self.step(pipeline_id)
        with self.connect() as connection:
            connection.execute("UPDATE analysis_step_attempts SET status='persisting' WHERE attempt_id=?", (step["attempt_id"],))
        with self.assertRaises(AnalysisContractError) as caught:
            self.service._set_step(step["attempt_id"], "running", generation=1)
        self.assertEqual(caught.exception.code, "invalid_transition")
        self.assertEqual(self.step(pipeline_id)["status"], "persisting")

    def test_old_worker_failure_cannot_overwrite_or_unregister_new_worker(self):
        pipeline_id = self.start_auto()
        key = self.service.runtime_key + ":" + pipeline_id
        newer = object()
        def fail(*args, **kwargs):
            with self.connect() as connection:
                connection.execute("UPDATE analysis_pipeline_requests SET generation=2,status='accepted' WHERE pipeline_id=?", (pipeline_id,))
            with RUNTIME_LOCK: RUNTIMES[key] = newer
            raise OSError("late old-worker error")
        try:
            with patch.object(self.service, "_run", side_effect=fail):
                self.service._run_guarded(pipeline_id, "http://synthetic.invalid", key, 1)
            self.assertEqual((self.service._pipeline_row(pipeline_id)["status"], self.service._pipeline_row(pipeline_id)["generation"]), ("accepted", 2))
            self.assertIs(RUNTIMES[key], newer)
        finally:
            with RUNTIME_LOCK: RUNTIMES.pop(key, None)

    def test_interrupted_old_worker_cannot_cancel_retried_generation(self):
        pipeline_id = self.start_auto()
        entered = {method: threading.Event() for method in ("participation", "conversation_dynamics")}
        release = threading.Event()
        original = self.service.method_runner
        def delayed(method, snapshot):
            entered[method].set()
            release.wait()
            return original(method, snapshot)
        self.service.method_runner = delayed
        thread = threading.Thread(target=self.service._run_guarded, args=(pipeline_id, "http://synthetic.invalid", "synthetic-old", 1))
        thread.start()
        try:
            # M2 runs both adapters concurrently. Interrupt only once neither
            # sibling can still be left in checking/ready by the fixture update.
            for method, event in entered.items():
                self.assertTrue(event.wait(3), f"{method} did not start")
            with self.connect() as connection:
                connection.execute("UPDATE analysis_pipeline_requests SET status='waiting',wait_reason='retry' WHERE pipeline_id=?", (pipeline_id,))
                connection.execute("UPDATE analysis_step_attempts SET status='interrupted' WHERE pipeline_id=? AND status='running'", (pipeline_id,))
            self.service.retry("synthetic", pipeline_id, {}, app_url="http://synthetic.invalid")
        finally:
            release.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual((self.service._pipeline_row(pipeline_id)["status"], self.service._pipeline_row(pipeline_id)["generation"]), ("accepted", 2))
        self.assertEqual(self.saved, [])
        self.service._run(pipeline_id, "http://synthetic.invalid")
        self.assertEqual(self.service.status("synthetic", pipeline_id, ensure_running=False)["status"], "completed")
        self.assertEqual(len(self.saved), 1)

    def test_two_workers_cannot_claim_the_same_accepted_generation(self):
        pipeline_id = self.start_auto()
        barrier = threading.Barrier(2)
        original = self.service._bound_definitions
        def bound(*args):
            result = original(*args); barrier.wait(); return result
        with patch.object(self.service, "_bound_definitions", side_effect=bound):
            threads = [threading.Thread(target=self.service._run_guarded, args=(pipeline_id, "http://synthetic.invalid", "duplicate", 1)) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(5); self.assertFalse(thread.is_alive())
        self.assertEqual(self.service._pipeline_row(pipeline_id)["status"], "completed")
        self.assertEqual(len(self.saved), 1)

    def test_cancelled_accepted_pipeline_can_retry_without_restarting_old_worker(self):
        pipeline_id = self.start_auto()
        result = self.service.cancel("synthetic", pipeline_id)
        self.assertEqual(result["status"], "cancelled")
        self.service._run(pipeline_id, "http://synthetic.invalid", generation=1)
        self.assertEqual(self.saved, [])
        self.service.retry("synthetic", pipeline_id, {}, app_url="http://synthetic.invalid")
        self.service._run(pipeline_id, "http://synthetic.invalid", generation=2)
        self.assertEqual(self.service._pipeline_row(pipeline_id)["status"], "completed")

    def test_publication_retry_cannot_change_fixed_scope_or_package(self):
        pipeline_id = self.start_auto()
        self.set_waiting(pipeline_id)
        for extra in ({"publication_targets": ["input", "orchestrator", "visualization"]}, {"result_run_id": "another-package"}):
            with self.subTest(extra=extra), self.assertRaises(AnalysisContractError) as caught:
                self.service.retry("synthetic", pipeline_id, extra, app_url="http://synthetic.invalid")
            self.assertEqual(caught.exception.code, "publication_scope_conflict")
        self.assertEqual(self.service._pipeline_row(pipeline_id)["generation"], 1)


if __name__ == "__main__":
    unittest.main()
