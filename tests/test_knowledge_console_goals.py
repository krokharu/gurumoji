import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest import mock

from devtools.knowledge_console.app import create_app, _enqueue_drive_task, _propose_goal_tasks, _evaluate_goal_artifact
from devtools.knowledge_console.goals import GoalWorkspace, settings, excerpt
from devtools.knowledge_console.store import KnowledgeConsoleStore

HEADERS = {"X-Knowledge-Console-Request": "1"}
SPEC = dict(title="会話知識を改善", objective="根拠のある会話分析レポートを生成する",
            target_score=85, target_knowledge=100, target_compression=50,
            max_iterations=3, max_tasks=3)


class GoalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-goal-tests-")
        self.root = Path(self.temp.name)
        self.store = KnowledgeConsoleStore(self.root)
        self.workspace = GoalWorkspace(self.store)
        self.goal = self.workspace.create(SPEC)

    def tearDown(self):
        self.temp.cleanup()

    def note(self, text="発言量の偏りと会話参加の関係を検討する。"):
        self.goal = self.workspace.add_note(self.goal["goal_id"], {"title": "参加分析の根拠", "content": text})
        return self.goal["notes"][-1]

    def payload(self, notes=None):
        return {"revision": self.goal["revision"], "note_ids": notes or [self.goal["notes"][0]["note_id"]]}

    def proposal(self, packet):
        return [{"title": "参加指標の不足根拠を整理", "expert_id": "participation-balance",
                 "dimension": "knowledge", "reason": "ノートでは適用条件が未整理のため",
                 "focus": "提供された根拠から適用条件を分類し、不足情報を明示する",
                 "source_ids": [packet["sources"][0]["note_id"]]}]

    def test_isolated_vault_and_persistent_settings(self):
        vault = Path(self.goal["vault_path"])
        self.assertTrue(vault.is_relative_to(self.root))
        self.assertTrue((vault / ".obsidian/app.json").exists())
        self.assertTrue((vault / "00-Home.md").exists())
        self.assertEqual(self.goal["knowledge_count"], 0)
        self.assertIsNone(self.goal["compression_rate"])
        self.assertIsNone(self.goal["artifact_score"])
        other = GoalWorkspace(KnowledgeConsoleStore(self.root)).get(self.goal["goal_id"])
        self.assertEqual(other["target_score"], 85)
        self.assertEqual(other["target_compression"], 50)
        self.assertEqual(len(list((vault / "99-Archive").rglob("*.md"))), 1)

    def test_no_user_note_overwrite_and_manual_notes_supported(self):
        home = Path(self.goal["vault_path"]) / "00-Home.md"
        home.write_text("利用者の編集", encoding="utf-8")
        self.workspace.ensure_vault(self.goal["goal_id"])
        self.assertEqual(home.read_text(encoding="utf-8"), "利用者の編集")
        self.workspace.update(self.goal["goal_id"], {**SPEC, "revision": 1, "target_score": 90})
        self.assertEqual(home.read_text(encoding="utf-8"), "利用者の編集")
        manual = home.parent / "10-Knowledge/manual.md"
        manual.write_text("# 研究ノート\n手動追加した根拠", encoding="utf-8")
        self.assertEqual(self.workspace.get(self.goal["goal_id"])["knowledge_count"], 1)

    def test_target_validation_and_revision(self):
        for key, value in [("target_score", 101), ("target_score", True), ("target_knowledge", 1.5),
                           ("target_compression", float("nan")), ("target_compression", 100),
                           ("max_tasks", 6), ("max_iterations", 11)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                settings({**SPEC, key: value})
        self.workspace.update(self.goal["goal_id"], {**SPEC, "revision": 1})
        with self.assertRaises(RuntimeError):
            self.workspace.update(self.goal["goal_id"], {**SPEC, "revision": 1})

    def test_real_proposals_link_evidence_and_deduplicate(self):
        self.note()
        result = self.workspace.generate(self.goal["goal_id"], self.payload(), self.proposal)
        self.assertEqual(result["created_count"], 1)
        task = result["goal"]["tasks"][0]
        self.assertEqual(task["target_score"], 85)
        self.assertEqual(task["status"], "draft")
        self.assertEqual(task["max_iterations"], 3)
        context = self.workspace.task_context(task["task_id"])
        self.assertIn("発言量の偏り", context)
        self.assertNotIn(str(self.root), context)
        again = self.workspace.generate(self.goal["goal_id"], self.payload(), lambda p: self.fail("must reuse"))
        self.assertEqual(again["created_count"], 0)
        self.assertTrue(again["reused"])

    def test_changed_or_deleted_notes_block_stale_execution(self):
        note = self.note()
        result = self.workspace.generate(self.goal["goal_id"], self.payload(), self.proposal)
        task = result["goal"]["tasks"][0]
        path = Path(self.goal["vault_path"]) / note["path"]
        path.write_text("内容が変わった", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.workspace.task_context(task["task_id"])
        path.unlink()
        with self.assertRaises(RuntimeError):
            self.workspace.task_context(task["task_id"])

    def test_changed_goal_blocks_old_tasks(self):
        self.note()
        result = self.workspace.generate(self.goal["goal_id"], self.payload(), self.proposal)
        task = result["goal"]["tasks"][0]
        self.workspace.update(self.goal["goal_id"], {**SPEC, "target_score": 90, "revision": 1})
        with self.assertRaises(RuntimeError):
            self.workspace.task_context(task["task_id"])

    def test_invalid_plan_leaves_no_partial_tasks(self):
        self.note()
        def invalid(packet):
            valid = self.proposal(packet)
            return valid + [{**valid[0], "title": "別の案", "source_ids": ["invented-note"]}]
        with self.assertRaises(ValueError):
            self.workspace.generate(self.goal["goal_id"], self.payload(), invalid)
        self.assertEqual(self.store.list_tasks(), [])
        # A database error on the second insert must also roll back the first task.
        def two(packet):
            first = self.proposal(packet)[0]
            return [first, {**first, "title": "別の案"}]
        original = self.store.create_task
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise sqlite3.OperationalError("injected failure")
            return original(*args, **kwargs)
        with patch.object(self.store, "create_task", side_effect=fail_second), self.assertRaises(sqlite3.OperationalError):
            self.workspace.generate(self.goal["goal_id"], self.payload(), two)
        self.assertEqual(self.store.list_tasks(), [])

    def test_changes_during_llm_call_do_not_create_tasks(self):
        note = self.note()
        def changing(packet):
            (Path(self.goal["vault_path"]) / note["path"]).write_text("変更", encoding="utf-8")
            return self.proposal(packet)
        with self.assertRaises(RuntimeError):
            self.workspace.generate(self.goal["goal_id"], self.payload(), changing)
        self.assertEqual(self.store.list_tasks(), [])

    def test_excerpts_bounded_and_secrets_removed(self):
        self.note("password=do-not-send\n" + "あ" * 6500)
        packet = self.workspace.context(self.goal["goal_id"], self.payload()["note_ids"])
        self.assertLessEqual(len(packet["sources"][0]["excerpt"]), 6000)
        self.assertTrue(packet["sources"][0]["truncated"])
        self.assertNotIn("do-not-send", packet["sources"][0]["excerpt"])
        self.assertNotIn("example.org", excerpt("[link](https://example.org)"))

    def test_duplicate_note_ids_and_links_rejected(self):
        note = self.note()
        vault = Path(self.goal["vault_path"])
        raw = (vault / note["path"]).read_bytes()
        (vault / "10-Knowledge/duplicate.md").write_bytes(raw)
        with self.assertRaises(ValueError):
            self.workspace.notes(self.goal["goal_id"])
        with self.assertRaises(ValueError):
            self.workspace.root("../escape")

    def test_old_task_without_goal_is_unaffected(self):
        self.assertEqual(self.workspace.task_context("unlinked"), "")


class GoalRouteTests(unittest.TestCase):
    def test_llm_request_contains_notes_and_goals(self):
        packet = {"goals": SPEC, "sources": [{"note_id": "note-1", "excerpt": "根拠となる知識"}]}
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"choices": [{"message": {
            "content": '{"tasks":[{"title":"根拠の整理"}]}'}}]}, ensure_ascii=False).encode()
        with patch("devtools.knowledge_console.app.urllib.request.urlopen", return_value=response) as send:
            tasks = _propose_goal_tasks(packet, base_url="http://127.0.0.1:1234/v1", model="local-model", timeout_seconds=3)
        request = json.loads(send.call_args.args[0].data)
        self.assertEqual(json.loads(request["messages"][1]["content"]), packet)
        self.assertEqual(tasks[0]["title"], "根拠の整理")

    def test_create_note_generate_and_worker_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(data_directory=tmp)
            client = app.test_client()
            self.assertEqual(client.post("/api/knowledge-console/goals", json=SPEC).status_code, 403)
            response = client.post("/api/knowledge-console/goals", json=SPEC, headers=HEADERS)
            self.assertEqual(response.status_code, 200, response.json)
            goal = response.json["goal"]
            prefix = "/api/knowledge-console/goals/" + goal["goal_id"]
            response = client.post(prefix + "/notes", json={"title": "根拠", "content": "評価対象の根拠資料"}, headers=HEADERS)
            self.assertEqual(response.status_code, 200, response.json)
            goal = response.json["goal"]
            payload = {"revision": 1, "note_ids": [goal["notes"][0]["note_id"]]}
            proposal = [{"title": "根拠資料を整理", "expert_id": "thematic-analysis", "dimension": "score",
                         "reason": "目標品質に向けて根拠を明示", "focus": "資料を整理", "source_ids": payload["note_ids"]}]
            with patch("devtools.knowledge_console.app._propose_goal_tasks", return_value=proposal) as ask:
                response = client.post(prefix + "/generate", json=payload, headers=HEADERS)
            self.assertEqual(response.status_code, 200, response.json)
            self.assertIn("評価対象の根拠資料", json.dumps(ask.call_args.args[0], ensure_ascii=False))
            task = response.json["goal"]["tasks"][0]
            workspace = app.extensions["knowledge_console_goals"]
            task["goal_context"] = workspace.task_context(task["task_id"])
            class Queue:
                def write(self, name, raw):
                    self.payload = json.loads(raw)
            queue = Queue()
            _enqueue_drive_task(queue=queue, secret="test", task=task, focus="採点の改善点")
            self.assertIn("評価対象の根拠資料", queue.payload["analysis_focus"])
            self.assertIn("採点の改善点", queue.payload["analysis_focus"])
            response = client.post(f"/api/knowledge-console/tasks/{task['task_id']}/execute",
                                   json={"revision": task["revision"], "simulation": True}, headers=HEADERS)
            self.assertEqual(response.status_code, 400)
            html = client.get("/").get_data(as_text=True)
            self.assertIn('data-view="goals"', html)
            self.assertIn('id="kc-goal-generate"', html)
            with client.get("/static/goals.js") as static_response:
                self.assertEqual(static_response.status_code, 200)

    def test_llm_unavailable_is_not_fake_generation(self):
        with self.assertRaises(RuntimeError):
            _propose_goal_tasks({}, base_url="", model="", timeout_seconds=1)


class GoalMetricsTests(unittest.TestCase):
    setUp = GoalWorkspaceTests.setUp
    tearDown = GoalWorkspaceTests.tearDown
    note = GoalWorkspaceTests.note
    proposal = GoalWorkspaceTests.proposal

    def assessment(self):
        note = self.note("発言量の偏り。根拠と具体例。適用条件と限界。")
        return {"goal_revision": self.goal["revision"], "revision": self.goal["assessment_revision"],
                "scope_ids": [note["note_id"]], "reviews": [{"note_id": note["note_id"], "sha256": note["sha256"],
                    "duplicates_checked": True, "conflicts_checked": True, "sources_checked": True,
                    "depth": 3, "evidence": "根拠の節と適用条件を確認"}],
                "cases": [{"question": "発言量の限界は？", "terms": ["発言量", "限界"], "expected_ids": [note["note_id"]]}]}

    def save(self, payload):
        self.goal = self.workspace.save_assessment(self.goal["goal_id"], payload)
        return self.goal

    def evaluate(self, score=80, scorer="test-model", artifact="成果物"):
        payload = {"goal_revision": self.goal["revision"], "revision": self.goal["assessment_revision"],
                   "note_ids": self.goal["assessment"]["scope_ids"][:3], "prompt": "根拠から説明を生成", "artifact": artifact}
        self.goal = self.workspace.evaluate_artifact(self.goal["goal_id"], payload,
            lambda _: {"score": score, "feedback": "適用条件を明示する", "scorer": scorer})
        return self.goal

    def test_only_scoped_knowledge_and_confirmed_reviews_count(self):
        payload = self.assessment()
        self.note("無関係な日記")
        result = self.save(payload)
        self.assertEqual(result["knowledge_count"], 2)
        self.assertEqual(result["metrics"]["knowledge_count"], 1)
        self.assertEqual(result["metrics"]["organized_count"], 1)
        self.assertEqual(result["metrics"]["organization_rate"], 100)
        self.assertEqual(result["metrics"]["depth"], 3)
        self.assertEqual(result["metrics"]["index_rate"], 100)
        self.assertIsNone(result["artifact_score"])
        self.assertFalse(result["goal_reached"])
        self.assertEqual([gap["dimension"] for gap in result["gaps"]],
                         ["knowledge", "organization", "depth", "index", "score"])
        self.assertEqual(result["gaps"][0]["current"], 1)
        self.assertIn("score", result["unmet_dimensions"])
        restored = GoalWorkspace(KnowledgeConsoleStore(self.root)).get(result["goal_id"])
        self.assertEqual(restored["history"], result["history"])

    def test_unreviewed_is_explicit_and_not_fake_depth(self):
        payload = self.assessment()
        payload["reviews"] = []
        payload["cases"] = []
        result = self.save(payload)
        self.assertIsNone(result["metrics"]["depth"])
        self.assertIsNone(result["metrics"]["index_rate"])
        self.assertEqual(result["metrics"]["review_coverage"], 0)
        self.assertFalse(result["goal_reached"])

    def test_search_uses_query_not_expected_answers_and_requires_all_terms(self):
        payload = self.assessment()
        payload["cases"][0]["terms"] = ["発言量", "存在しない語"]
        result = self.save(payload)
        self.assertEqual(result["metrics"]["index_rate"], 0)
        self.assertEqual(result["metrics"]["retrieval_results"][0]["found_ids"], [])

    def test_search_requires_expected_notes_in_top_five(self):
        for i in range(6):
            path = Path(self.goal["vault_path"]) / f"10-Knowledge/n{i}.md"
            path.write_text(f"---\nnote_id: n{i}\n---\n共通の検索語", encoding="utf-8")
        payload = {"goal_revision": 1, "revision": 0, "scope_ids": [f"n{i}" for i in range(6)], "reviews": [],
                   "cases": [{"question": "共通の資料", "terms": ["共通"], "expected_ids": ["n5"]}]}
        result = self.save(payload)
        self.assertEqual(result["metrics"]["index_rate"], 0)
        self.assertEqual(result["metrics"]["retrieval_results"][0]["found_ids"], ["n0", "n1", "n2", "n3", "n4"])

    def test_changed_notes_invalidate_confirmation_and_artifact(self):
        self.save(self.assessment())
        self.evaluate()
        note = self.goal["notes"][0]
        path = Path(self.goal["vault_path"]) / note["path"]
        original = path.read_text(encoding="utf-8")
        path.write_text(original + "\n新しい条件", encoding="utf-8")
        result = self.workspace.get(self.goal["goal_id"])
        self.assertEqual(result["metrics"]["organized_count"], 0)
        self.assertEqual(result["metrics"]["stale_ids"], [note["note_id"]])
        self.assertIsNone(result["artifact_score"])
        self.assertTrue(result["artifact_evaluation"]["stale"])
        path.unlink()
        result = self.workspace.get(self.goal["goal_id"])
        self.assertEqual(result["metrics"]["knowledge_count"], 0)
        self.assertEqual(result["metrics"]["index_rate"], 0)

    def test_legacy_targets_load_without_rewriting_notes(self):
        home = Path(self.goal["vault_path"]) / "00-Home.md"
        original = home.read_bytes()
        with self.store._transaction() as connection:
            connection.execute("UPDATE knowledge_console_goals SET settings_json=? WHERE goal_id=?", (json.dumps(SPEC), self.goal["goal_id"]))
        result = self.workspace.get(self.goal["goal_id"])
        self.assertEqual(result["target_depth"], 2)
        self.assertEqual(result["target_organization"], 80)
        self.assertEqual(home.read_bytes(), original)
        for key, value in [("target_depth", 4), ("target_index", -1), ("target_organization", True)]:
            with self.assertRaises(ValueError):
                settings({**SPEC, key: value})

    def test_invalid_or_stale_assessment_leaves_history_unchanged(self):
        payload = self.assessment()
        for bad in [{**payload, "scope_ids": ["missing"]}, {**payload, "cases": [{"question": "Q", "terms": [], "expected_ids": payload["scope_ids"]}]},
                    {**payload, "reviews": [{**payload["reviews"][0], "depth": 9}]}]:
            with self.assertRaises(ValueError):
                self.save(bad)
        self.save(payload)
        with self.assertRaises(RuntimeError):
            self.save(payload)
        self.assertEqual(len(self.workspace.get(self.goal["goal_id"])["history"]), 1)

    def test_changed_questions_reset_comparison_and_goal_requires_artifact(self):
        self.goal = self.workspace.update(self.goal["goal_id"], {**SPEC, "revision": 1, "target_knowledge": 1})
        self.save(self.assessment())
        self.evaluate(score=90)
        self.assertTrue(self.goal["goal_reached"])
        payload = {**self.goal["assessment"], "goal_revision": self.goal["revision"]}
        payload["cases"][0]["question"] = "別の問い"
        self.save(payload)
        self.assertFalse(self.goal["goal_reached"])
        self.assertIsNone(self.goal["artifact_score"])
        self.assertFalse(self.goal["history"][0]["comparable"])

    def test_forecast_requires_three_improving_scores_same_model(self):
        self.save(self.assessment())
        self.evaluate(score=60, artifact="初稿")
        self.evaluate(score=65, artifact="二稿")
        self.assertIsNone(self.goal["forecast_iterations"])
        self.evaluate(score=70, artifact="三稿")
        self.assertEqual(self.goal["forecast_iterations"], 3)
        self.evaluate(score=75, scorer="other-model", artifact="四稿")
        self.assertIsNone(self.goal["forecast_iterations"])

    def test_regrading_identical_output_does_not_create_forecast(self):
        self.save(self.assessment())
        for score in (60, 65, 70):
            self.evaluate(score=score, artifact="同じ成果物")
        self.assertIsNone(self.goal["forecast_iterations"])

    def test_scoring_inputs_are_sanitized_and_persisted_with_provenance(self):
        self.save(self.assessment())
        payload = {"goal_revision": self.goal["revision"], "revision": self.goal["assessment_revision"],
                   "note_ids": self.goal["assessment"]["scope_ids"], "prompt": "生成指示 password=private-value",
                   "artifact": "根拠を明示した成果物"}
        seen = []
        def evaluate(packet):
            seen.append(packet)
            return {"score": 80, "feedback": "根拠を確認", "scorer": "test"}
        self.workspace.evaluate_artifact(self.goal["goal_id"], payload, evaluate)
        self.assertNotIn("private-value", json.dumps(seen))
        with self.store._transaction() as connection:
            raw = connection.execute("SELECT payload_json FROM knowledge_console_goal_measurements WHERE kind='artifact'").fetchone()[0]
        saved = json.loads(raw)
        self.assertEqual(saved["input"], seen[0])
        self.assertEqual(saved["input"]["sources"][0]["sha256"], self.goal["notes"][0]["sha256"])

    def test_artifact_evaluation_race_and_failure_do_not_record_scores(self):
        self.save(self.assessment())
        payload = {"goal_revision": self.goal["revision"], "revision": self.goal["assessment_revision"],
                   "note_ids": self.goal["assessment"]["scope_ids"], "prompt": "生成指示", "artifact": "実際の出力"}
        with self.assertRaises(ValueError):
            self.workspace.evaluate_artifact(self.goal["goal_id"], payload, lambda _: {"score": 101})
        note = self.goal["notes"][0]
        def change(_):
            path = Path(self.goal["vault_path"]) / note["path"]
            path.write_text(path.read_text(encoding="utf-8") + "\n変更", encoding="utf-8")
            return {"score": 80, "feedback": "ok", "scorer": "test"}
        with self.assertRaises(RuntimeError):
            self.workspace.evaluate_artifact(self.goal["goal_id"], payload, change)
        self.assertIsNone(self.workspace.get(self.goal["goal_id"])["artifact_score"])

    def test_new_dimensions_and_feedback_reach_planner_without_secrets(self):
        payload = self.assessment()
        payload["reviews"][0]["evidence"] = "根拠不足 password=do-not-send"
        self.save(payload)
        self.evaluate()
        seen = []
        def propose(packet):
            seen.append(packet)
            return [{**self.proposal(packet)[0], "title": f"改善 {dim}", "dimension": dim} for dim in ("organization", "depth", "index")]
        result = self.workspace.generate(self.goal["goal_id"], {"revision": self.goal["revision"], "note_ids": payload["scope_ids"]}, propose)
        self.assertEqual(result["created_count"], 3)
        self.assertEqual(seen[0]["progress"]["artifact_feedback"], "適用条件を明示する")
        self.assertNotIn("do-not-send", json.dumps(seen, ensure_ascii=False))
        self.assertEqual(seen[0]["progress"]["unmet_dimensions"], ["knowledge", "score"])
        self.assertEqual(seen[0]["progress"]["gaps"][0]["target"], self.goal["target_knowledge"])
        self.assertIn("target_index", self.workspace.task_context(result["goal"]["tasks"][0]["task_id"]))


class GoalEvaluationRouteTests(unittest.TestCase):
    def test_goal_page_has_slider_measurement_and_automatic_task_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = create_app(data_directory=tmp).test_client().get("/").get_data(as_text=True)
        for control in ("knowledge", "organization", "depth", "index", "score"):
            self.assertIn(f'id="kc-goal-{control}" type="range"', html)
        self.assertIn('id="kc-goal-measure-now"', html)
        self.assertIn('id="kc-goal-auto-start"', html)
        self.assertIn('id="kc-goal-auto-status"', html)

    def test_fixed_rubric_scoring_validates_components(self):
        response = mock.MagicMock()
        def reply(value):
            response.__enter__.return_value.read.return_value = json.dumps({"choices": [{"message": {"content": json.dumps(value)}}]}).encode()
        with patch("devtools.knowledge_console.app.urllib.request.urlopen", return_value=response) as send:
            reply(dict(goal_fit=20, evidence=21, coherence=22, usefulness=23, feedback="根拠を確認"))
            result = _evaluate_goal_artifact({"artifact": "実際の出力"}, base_url="http://127.0.0.1:1234/v1", model="local", timeout_seconds=1)
            self.assertEqual(result["score"], 86)
            self.assertIn("goal-artifact-v1", json.loads(send.call_args.args[0].data)["messages"][0]["content"])
            reply(dict(goal_fit=True, evidence=21, coherence=22, usefulness=23, feedback="bad"))
            with self.assertRaises(ValueError):
                _evaluate_goal_artifact({}, base_url="http://127.0.0.1:1234/v1", model="local", timeout_seconds=1)

    def test_assessment_measure_and_evaluate_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(data_directory=tmp)
            client = app.test_client()
            goal = client.post("/api/knowledge-console/goals", json=SPEC, headers=HEADERS).json["goal"]
            prefix = "/api/knowledge-console/goals/" + goal["goal_id"]
            goal = client.post(prefix + "/notes", json={"title": "根拠", "content": "会話分析の根拠"}, headers=HEADERS).json["goal"]
            note_id = goal["notes"][0]["note_id"]
            payload = dict(goal_revision=1, revision=0, scope_ids=[note_id], reviews=[], cases=[])
            self.assertEqual(client.post(prefix + "/assessment", json=payload).status_code, 403)
            self.assertEqual(client.post(prefix + "/assessment", json=payload, headers=HEADERS).status_code, 200)
            self.assertEqual(client.post(prefix + "/measure", json=dict(goal_revision=1, revision=1), headers=HEADERS).status_code, 200)
            with patch("devtools.knowledge_console.app._evaluate_goal_artifact", return_value=dict(score=80, feedback="根拠がある", scorer="test")):
                result = client.post(prefix + "/evaluate", json=dict(goal_revision=1, revision=1, note_ids=[note_id], prompt="生成指示", artifact="成果物"), headers=HEADERS)
            self.assertEqual(result.status_code, 200, result.json)
            self.assertEqual(result.json["goal"]["artifact_score"], 80)


if __name__ == "__main__":
    unittest.main()
