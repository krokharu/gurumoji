import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from devtools.knowledge_console.app import create_app, _build_a100_plan, _ask_local_llm
from devtools.knowledge_console.quality import assess_response
from devtools.knowledge_console.store import KnowledgeConsoleStore, MAX_TASK_RESULT_BYTES


CONTEXT = "資料\n" + json.dumps({"evidence": [{"note_id": "note-a", "sha256": "a" * 64,
    "excerpt": "This is the original evidence excerpt."}]})


def response(**changes):
    return {"content": json.dumps({"status": "completed", "findings": "Source-based result",
        "citations": [{"note_id": "note-a", "quote": "original evidence excerpt"}],
        "missing_inputs": [], **changes}), "provider": "test-worker"}


class EvidenceGateTests(unittest.TestCase):
    def test_long_japanese_responses_keep_full_content_and_quality(self):
        for state in ("completed", "needs_input", "invalid"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                store = KnowledgeConsoleStore(directory)
                task = store.create_task({"title": "Long response", "expert_id": "thematic-analysis",
                                          "actor": "a100", "model_id": "qwen3-80b"})
                store.execute_task(task["task_id"], expected_revision=task["revision"], simulation=False)
                raw = response(findings="根拠を確認。" * 2500, status=state,
                               missing_inputs=["話者データ"] if state == "needs_input" else [])
                # Match the worker's Unicode JSON output, not ASCII-escaped fixtures.
                raw["content"] = json.dumps(json.loads(raw["content"]), ensure_ascii=False)
                checked = assess_response(raw, CONTEXT)
                self.assertGreater(len(json.dumps(checked, ensure_ascii=False).encode()), 32 * 1024)
                if state == "completed":
                    saved = store.complete_real_task(task["task_id"], checked)
                    self.assertEqual(saved["status"], "succeeded")
                else:
                    saved = store.fail_real_task(task["task_id"], "quality gate", result=checked)
                    self.assertIn("採点停止", saved["phase"])
                self.assertEqual(saved["result"], checked)
                self.assertEqual(store.list_tasks()[0]["result"], checked)

    def test_storage_fits_latest_and_best_bounded_worker_responses(self):
        # Nearly full 512 KiB worker frames, plus JSON quotes and duplicated
        # evidence fields, must fit together without truncation.
        checked = assess_response(response(findings="資料" * 6000), CONTEXT)
        checked["usage"] = {"worker_metadata": "x" * 390000}
        saved_result = {**checked, "best_attempt": {**checked, "score": 70, "iteration": 1},
                        "attempts": [{"score": 70, "iteration": 1, "feedback": "根拠" * 120}],
                        "interrupted": True, "target_met": False}
        self.assertLess(len(json.dumps(saved_result, ensure_ascii=False).encode()), MAX_TASK_RESULT_BYTES)
        with tempfile.TemporaryDirectory() as directory:
            store = KnowledgeConsoleStore(directory)
            task = store.create_task({"title": "Bounded responses", "expert_id": "thematic-analysis",
                                      "actor": "a100", "model_id": "qwen3-80b"})
            saved = store.fail_real_task(task["task_id"], "stopped", result=saved_result)
            self.assertEqual(saved["result"], saved_result)
            with self.assertRaises(ValueError):
                store.fail_real_task(task["task_id"], "too large", result={"content": "x" * MAX_TASK_RESULT_BYTES})
            self.assertEqual(store.list_tasks()[0]["result"], saved_result)
            # A later error with no new response must not erase persisted work.
            self.assertEqual(store.fail_real_task(task["task_id"], "later failure")["result"], saved_result)

    def test_missing_inputs_are_held_even_if_llm_requests_execution(self):
        task = {"task_id": "needs-data", "title": "Input needed", "position": 1,
                "actor": "a100", "model_id": "qwen3-80b", "status": "failed",
                "quality_state": "needs_input", "input_ready": True, "decision_mode": "local_llm"}
        suggestion = {"decisions": {"needs-data": {"action": "execute", "focus": "retry", "reason": "retry"}}}
        plan = _build_a100_plan([task], suggestion)[0]
        self.assertEqual(plan["action"], "hold")
        self.assertFalse(plan["program_gate"]["approved"])
        self.assertFalse(plan["program_gate"]["checks"]["no_missing_inputs"])
        self.assertIn("不足資料", plan["reason"])
        regenerated = {**task, "task_id": "new-snapshot", "status": "draft", "quality_state": "unverified"}
        self.assertTrue(_build_a100_plan([regenerated], {"decisions": {}})[0]["program_gate"]["approved"])
        with mock.patch("devtools.knowledge_console.app._local_llm_model") as model:
            advice = _ask_local_llm(base_url="http://127.0.0.1:1234/v1", model="test", tasks=[task])
            model.assert_not_called()
            self.assertEqual(advice["state"], "not_needed")

    def test_repeat_interruptions_retain_best_output_and_unscored_response(self):
        for failure in ("needs_input", "invalid", "scoring", "timeout", "drive"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                app = create_app(data_directory=Path(directory) / "data")
                sync = Path(directory) / "sync"
                sync.mkdir()
                app.config.update(KNOWLEDGE_CONSOLE_DRIVE_SYNC_DIR=str(sync),
                                  KNOWLEDGE_CONSOLE_QUEUE_SECRET="test-secret-long-enough-for-queue")
                client = app.test_client()
                headers = {"X-Knowledge-Console-Request": "1"}
                task = client.post("/api/knowledge-console/tasks", headers=headers, json={
                    "title": "Interrupted repeat", "expert_id": "thematic-analysis", "actor": "a100",
                    "model_id": "qwen3-80b", "target_score": 90, "max_iterations": 5}).json["task"]
                first = response(findings="最良の成果物" * 1000)
                second = response(findings="Second candidate")
                last = {"needs_input": response(status="needs_input", missing_inputs=["speaker timings"]),
                        "invalid": {"content": "Unstructured reply"}, "scoring": response(findings="Unscored candidate"),
                        "timeout": TimeoutError("worker timeout"), "drive": RuntimeError("Drive failure")}[failure]
                scores = [{"score": 70, "feedback": "improve"}, {"score": 60, "feedback": "improve"},
                          ValueError("scoring failed")]
                with mock.patch("devtools.knowledge_console.goals.GoalWorkspace.task_context", return_value=CONTEXT), \
                     mock.patch("devtools.knowledge_console.app._check_colab_connection", return_value={"connected": True}), \
                     mock.patch("devtools.knowledge_console.app._wait_for_drive_result", side_effect=[first, second, last]) as worker, \
                     mock.patch("devtools.knowledge_console.app._score_with_local_llm", side_effect=scores) as scorer:
                    reply = client.post(f"/api/knowledge-console/tasks/{task['task_id']}/execute", headers=headers,
                                        json={"revision": task["revision"], "simulation": False})
                    self.assertEqual(reply.status_code, 200)
                    app.extensions["knowledge_console_a100_executor"].shutdown(wait=True)
                    self.assertEqual(worker.call_count, 3)
                    self.assertEqual(scorer.call_count, 3 if failure == "scoring" else 2)
                saved = next(t for t in client.get("/api/knowledge-console/tasks").json["tasks"] if t["task_id"] == task["task_id"])
                result = saved["result"]
                self.assertEqual(saved["status"], "failed")
                self.assertEqual(saved["score"], 60)
                self.assertTrue(result["interrupted"])
                self.assertFalse(result["target_met"])
                self.assertEqual(result["stopped_iteration"], 3)
                self.assertEqual(result["best_attempt"]["content"], first["content"])
                self.assertEqual(result["best_attempt"]["score"], 70)
                self.assertEqual(result["best_attempt"]["iteration"], 1)
                self.assertEqual(result["best_attempt"]["quality"]["citations"][0]["sha256"], "a" * 64)
                self.assertEqual([a["score"] for a in result["attempts"]], [70, 60])
                if isinstance(last, dict):
                    self.assertEqual(result["content"], last["content"])
                else:
                    self.assertNotIn("content", result)

    def test_batch_route_holds_a_linked_task_after_missing_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(data_directory=directory)
            workspace = app.extensions["knowledge_console_goals"]
            goal = workspace.create({"title": "Input recovery", "objective": "Review supplied evidence",
                                     "target_score": 90, "target_knowledge": 1})
            goal = workspace.add_note(goal["goal_id"], {"title": "Source", "content": "The available input evidence."})
            ids = [n["note_id"] for n in goal["notes"]]
            proposal = {"title": "Review inputs", "expert_id": "thematic-analysis", "dimension": "knowledge",
                        "reason": "Missing data", "focus": "Check evidence", "source_ids": ids}
            goal = workspace.generate(goal["goal_id"], {"revision": 1, "note_ids": ids}, lambda _: [proposal])["goal"]
            task = goal["tasks"][0]
            store = workspace.store
            store.execute_task(task["task_id"], expected_revision=task["revision"], simulation=False)
            store.fail_real_task(task["task_id"], "missing data", result=assess_response(
                response(status="needs_input", missing_inputs=["speaker data"]), CONTEXT))
            self.assertTrue(workspace.task_context(task["task_id"]))
            with mock.patch("devtools.knowledge_console.app._local_llm_model") as model:
                reply = app.test_client().post("/api/knowledge-console/a100/plan", json={},
                                              headers={"X-Knowledge-Console-Request": "1"})
                self.assertEqual(reply.status_code, 200)
                model.assert_not_called()
            plan = next(p for p in reply.json["plan"] if p["task_id"] == task["task_id"])
            self.assertTrue(plan["program_gate"]["checks"]["input_ready"])
            self.assertEqual(plan["action"], "hold")
            self.assertFalse(plan["program_gate"]["approved"])
            app.extensions["knowledge_console_a100_executor"].shutdown(wait=True)

    def test_citations_are_bound_to_the_supplied_excerpt_and_hash(self):
        checked = assess_response(response(), CONTEXT)
        self.assertEqual(checked["quality"]["state"], "evidence_checked")
        self.assertEqual(checked["quality"]["citations"][0]["sha256"], "a" * 64)
        for citations in ([], [{"note_id": "unknown", "quote": "original evidence excerpt"}],
                          [{"note_id": "note-a", "quote": "fabricated original evidence"}],
                          [{"note_id": "note-a", "quote": "is"}], [None]):
            with self.subTest(citations=citations):
                self.assertEqual(assess_response(response(citations=citations), CONTEXT)["quality"]["state"], "invalid")

    def test_missing_input_and_old_free_text_never_pass_the_gate(self):
        self.assertEqual(assess_response(response(), "")["quality"]["state"], "needs_input")
        self.assertEqual(assess_response(response(missing_inputs=["speaker timings"]), CONTEXT)["quality"]["state"], "needs_input")
        for text in ("更新と検証を完了しました。", "null", "[]", '{"status": "completed"}'):
            self.assertEqual(assess_response({"content": text}, CONTEXT)["quality"]["state"], "invalid")

    def test_source_free_execution_is_rejected_before_contacting_drive(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(data_directory=directory)
            client = app.test_client()
            task = next(t for t in client.get("/api/knowledge-console/tasks").json["tasks"] if t["actor"] == "a100")
            with mock.patch("devtools.knowledge_console.app._check_colab_connection") as probe:
                reply = client.post(f"/api/knowledge-console/tasks/{task['task_id']}/execute",
                    json={"revision": task["revision"], "simulation": False},
                    headers={"X-Knowledge-Console-Request": "1"})
            self.assertEqual(reply.status_code, 400)
            probe.assert_not_called()
            self.assertIn("根拠ノート", reply.json["error"])
            app.extensions["knowledge_console_a100_executor"].shutdown(wait=True)

    def test_blocked_response_is_preserved_without_scoring_or_repeating(self):
        cases = [response(status="needs_input", missing_inputs=["utterance data"], citations=[]),
                 {"content": "No actual evidence, but done."}]
        for bad, target in [(bad, target) for bad in cases for target in (None, 80)]:
            with self.subTest(response=bad, target=target), tempfile.TemporaryDirectory() as directory:
                app = create_app(data_directory=Path(directory) / "data")
                sync = Path(directory) / "sync"
                sync.mkdir()
                app.config.update(KNOWLEDGE_CONSOLE_DRIVE_SYNC_DIR=str(sync),
                                  KNOWLEDGE_CONSOLE_QUEUE_SECRET="test-secret-long-enough-for-queue")
                client = app.test_client()
                headers = {"X-Knowledge-Console-Request": "1"}
                task = client.post("/api/knowledge-console/tasks", headers=headers, json={
                    "title": "Grounded analysis", "expert_id": "thematic-analysis", "actor": "a100",
                    "model_id": "qwen3-80b", "target_score": target, "max_iterations": 5}).json["task"]
                with mock.patch("devtools.knowledge_console.goals.GoalWorkspace.task_context", return_value=CONTEXT), \
                     mock.patch("devtools.knowledge_console.app._check_colab_connection", return_value={"connected": True}), \
                     mock.patch("devtools.knowledge_console.app._wait_for_drive_result", return_value=bad) as worker, \
                     mock.patch("devtools.knowledge_console.app._score_with_local_llm") as scorer:
                    reply = client.post(f"/api/knowledge-console/tasks/{task['task_id']}/execute", headers=headers,
                                        json={"revision": task["revision"], "simulation": False})
                    self.assertEqual(reply.status_code, 200)
                    app.extensions["knowledge_console_a100_executor"].shutdown(wait=True)
                    scorer.assert_not_called()
                    worker.assert_called_once()
                saved = next(t for t in client.get("/api/knowledge-console/tasks").json["tasks"] if t["task_id"] == task["task_id"])
                self.assertEqual(saved["status"], "failed")
                self.assertEqual(saved["result"]["content"], bad["content"])
                self.assertIsNone(saved["score"])
                self.assertEqual(saved["score_history"], [])
                self.assertIn("採点停止", saved["phase"])
