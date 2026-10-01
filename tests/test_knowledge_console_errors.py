import tempfile
import unittest
from pathlib import Path
from unittest import mock

from devtools.knowledge_console.app import create_app
from devtools.knowledge_console.store import KnowledgeConsoleStore


HEADERS = {"X-Knowledge-Console-Request": "1"}


class PersistentErrorTests(unittest.TestCase):
    def test_task_error_survives_retry_success_and_store_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            store = KnowledgeConsoleStore(directory)
            task = store.create_task({"title": "Retained errors", "expert_id": "thematic-analysis",
                                      "actor": "a100", "model_id": "qwen3-80b"})
            store.execute_task(task["task_id"], expected_revision=task["revision"], simulation=False)
            store.update_real_task(task["task_id"], progress=45, phase="Worker response")
            message = "First error\n" + "詳しい原因。" * 500 + "\nLast diagnostic line"
            failed = store.fail_real_task(task["task_id"], message,
                result={"quality": {"state": "needs_input"}, "stopped_iteration": 2})
            first = store.list_events(errors_only=True)[0]
            self.assertEqual(first["payload"]["message"], message)
            self.assertEqual(first["payload"]["phase"], "Worker response")
            self.assertEqual(first["payload"]["run_count"], 1)
            self.assertEqual(first["payload"]["iteration"], 2)
            self.assertEqual(first["payload"]["quality_state"], "needs_input")
            store.execute_task(task["task_id"], expected_revision=failed["revision"], simulation=False)
            done = store.complete_real_task(task["task_id"], {"content": "Successful retry"})
            self.assertEqual(done["error_message"], "")
            reopened = KnowledgeConsoleStore(directory)
            self.assertEqual(reopened.list_events(errors_only=True), [first])
            reopened.execute_task(task["task_id"], expected_revision=done["revision"], simulation=False)
            reopened.fail_real_task(task["task_id"], "Another error")
            errors = reopened.list_events(errors_only=True)
            self.assertEqual(errors[0], first)
            self.assertEqual(errors[1]["payload"]["run_count"], 3)

    def test_old_errors_can_be_paged_without_pruning_or_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            store = KnowledgeConsoleStore(directory)
            with store._transaction() as connection:
                for i in range(125):
                    store._append_event(connection, entity_type="task", entity_id="legacy-task",
                                        event_type="task.failed", payload={"message": f"Old error {i}"})
                for i in range(600):
                    store._append_event(connection, entity_type="task", entity_id="legacy-task",
                                        event_type="task.progressed", payload={})
            self.assertFalse(any(e["event_type"] == "task.failed" for e in store.list_events(limit=500)))
            before, found = None, []
            while True:
                page = store.list_events(limit=50, before=before, errors_only=True)
                if not page:
                    break
                found.extend(page)
                before = page[0]["sequence"]
                if len(found) == 50:
                    store.record_api_error(path="/api/new", method="POST", status=400, message="New arrival")
            self.assertEqual(len(found), 125)
            self.assertEqual(len({e["sequence"] for e in found}), 125)
            self.assertIn("Old error 0", [e["payload"]["message"] for e in found])

    def test_connection_failure_remains_after_recovery_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(data_directory=directory)
            self.addCleanup(app.extensions["knowledge_console_a100_executor"].shutdown, wait=True)
            sync = Path(directory) / "sync"
            sync.mkdir()
            app.config.update(KNOWLEDGE_CONSOLE_DRIVE_SYNC_DIR=str(sync),
                              KNOWLEDGE_CONSOLE_QUEUE_SECRET="test-secret-long-enough")
            failed = {"connected": False, "state": "worker_failed", "message": "Drive error\n" + "details " * 100}
            recovered = {"connected": True, "state": "connected", "message": "Recovered"}
            with mock.patch("devtools.knowledge_console.app._check_colab_connection", side_effect=[failed, failed, recovered]):
                for _ in range(3):
                    reply = app.test_client().post("/api/knowledge-console/runtime/check", json={}, headers=HEADERS)
                    self.assertEqual(reply.status_code, 200)
            store = KnowledgeConsoleStore(directory)
            self.assertEqual(len(store.list_events(errors_only=True)), 1)
            self.assertEqual(store.list_events(errors_only=True)[0]["payload"]["message"], failed["message"].strip())
            store.record_runtime_status(failed)
            KnowledgeConsoleStore(directory).record_runtime_status(failed)
            self.assertEqual(len(store.list_events(errors_only=True)), 2)

    def test_api_errors_are_persistent_and_pagination_is_exposed(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(data_directory=directory)
            self.addCleanup(app.extensions["knowledge_console_a100_executor"].shutdown, wait=True)
            client = app.test_client()
            for _ in range(3):
                reply = client.post("/api/knowledge-console/tasks", json={}, headers=HEADERS)
                self.assertEqual(reply.status_code, 400)
            first = client.get("/api/knowledge-console/events?errors_only=1&limit=2").json
            self.assertEqual(len(first["events"]), 2)
            second = client.get(f"/api/knowledge-console/events?errors_only=1&limit=2&before={first['next_before']}").json
            self.assertEqual(len(second["events"]), 1)
            self.assertIsNone(second["next_before"])
            self.assertEqual(second["events"][0]["payload"]["status"], 400)
            self.assertEqual(len(KnowledgeConsoleStore(directory).list_events(errors_only=True)), 3)

    def test_credentials_are_masked_without_shortening_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            store = KnowledgeConsoleStore(directory)
            store.record_api_error(path="/api/test", method="POST", status=500,
                message='Trace\nAuthorization: Bearer private-token\n{"access_token":"private-value"}\n'
                        + "Details " * 500 + "\nEnd of error")
            text = store.list_events(errors_only=True)[0]["payload"]["message"]
            self.assertNotIn("private-token", text)
            self.assertNotIn("private-value", text)
            self.assertTrue(text.endswith("\nEnd of error"))
            self.assertGreater(len(text), 500)
