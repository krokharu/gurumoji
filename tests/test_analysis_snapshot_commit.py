import json
import threading
import time
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support


class AnalysisSnapshotCommitTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests(
            "test_generated_result_persists_and_becomes_stale_on_edit"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.url = self.fixture.url

    def payload(self, request_id, **values):
        data = self.client.get(self.url).get_json()
        result = {
            "request_id": request_id,
            "source_revision": data["item"]["revision_count"],
            "analysis_revision": data["item"]["analysis_revision"],
            "mode": "automatic", "definition_ids": [],
            "provider_policy": "local_only", "publication_targets": [],
        }
        result.update(values)
        return result

    def wait(self, pipeline_id, terminal=("completed", "cancelled", "waiting", "failed")):
        body = None
        for _ in range(200):
            response = self.client.get(f"{self.url}/pipelines/{pipeline_id}")
            self.assertEqual(response.status_code, 200, response.get_json())
            body = response.get_json()
            if body["status"] in terminal:
                return body
            time.sleep(0.02)
        self.fail(f"pipeline did not finish: {body}")

    def test_fixed_snapshot_survives_concurrent_edit_and_result_is_stale_not_overwritten(self):
        entered = threading.Event()
        release = threading.Event()
        original = app.run_analysis_pipeline_method

        def delayed(step_id, snapshot):
            entered.set()
            release.wait(2)
            return original(step_id, snapshot)

        with patch.object(app, "run_analysis_pipeline_method", side_effect=delayed):
            response = self.client.post(
                self.url + "/pipelines", json=self.payload("snapshot-fixed-request-0001")
            )
            self.assertEqual(response.status_code, 202, response.get_json())
            pipeline_id = response.get_json()["pipeline_id"]
            self.assertTrue(entered.wait(2))
            with app.database_connection() as connection:
                row = connection.execute("SELECT segments_json FROM library_items WHERE id='content'").fetchone()
                segments = json.loads(row[0])
                segments[0]["text"] = "実行開始後の編集"
                connection.execute(
                    "UPDATE library_items SET segments_json=?,revision_count=revision_count+1 WHERE id='content'",
                    (json.dumps(segments, ensure_ascii=False),),
                )
            release.set()
            result = self.wait(pipeline_id)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["result_run"]["source_revision"], 0)
        self.assertTrue(app.analysis_archive_store().get(result["result_run"]["id"])["stale"])

    def test_duplicate_post_commits_one_run_and_deferred_publication_stays_pending(self):
        payload = self.payload("duplicate-pipeline-request-0001")
        first = self.client.post(self.url + "/pipelines", json=payload)
        second = self.client.post(self.url + "/pipelines", json=payload)
        self.assertIn(first.status_code, (200, 202))
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.get_json()["pipeline_id"], second.get_json()["pipeline_id"])
        result = self.wait(first.get_json()["pipeline_id"])
        self.assertEqual(result["status"], "completed", result)
        with app.database_connection() as connection:
            runs = connection.execute(
                "SELECT * FROM analysis_runs WHERE kind='milestone_analysis'"
            ).fetchall()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["vault_status"], "pending")
        self.assertTrue(all(value["status"] == "not_selected" for value in result["publications"]))

    def test_cancel_generation_wins_before_result_commit(self):
        entered = threading.Event()
        release = threading.Event()
        original = app.run_analysis_pipeline_method

        def delayed(step_id, snapshot):
            entered.set()
            release.wait(2)
            return original(step_id, snapshot)

        with patch.object(app, "run_analysis_pipeline_method", side_effect=delayed):
            response = self.client.post(
                self.url + "/pipelines", json=self.payload("cancel-pipeline-request-0001")
            )
            pipeline_id = response.get_json()["pipeline_id"]
            self.assertTrue(entered.wait(2))
            cancelled = self.client.post(f"{self.url}/pipelines/{pipeline_id}/cancel")
            self.assertEqual(cancelled.status_code, 200)
            release.set()
            result = self.wait(pipeline_id)
        self.assertEqual(result["status"], "cancelled", result)
        self.assertIsNone(result["result_run"])

    def test_restart_marks_inflight_attempt_interrupted_without_touching_legacy_runs(self):
        now = app.utc_now_iso()
        with app.database_connection() as connection:
            connection.execute("""INSERT INTO analysis_pipeline_requests
                (pipeline_id,request_id,item_id,source_revision,analysis_revision,input_hash,plan_hash,
                 plan_json,binding_json,snapshot_json,status,current_milestone,created_at,updated_at)
                VALUES ('restart-pipe','restart-request-0001','content',0,1,'hash','plan','{}','{}','{}','running','M2',?,?)""",
                (now, now),
            )
            connection.execute("""INSERT INTO analysis_step_attempts
                (attempt_id,pipeline_id,step_id,milestone,generation,attempt,status,updated_at)
                VALUES ('restart-attempt','restart-pipe','participation','M2',1,1,'running',?)""",
                (now,),
            )
            connection.execute("""INSERT INTO analysis_runs
                (id,request_id,item_id,kind,fingerprint,input_fingerprint,snapshot_id,
                 source_revision,analysis_revision,created_at,status)
                VALUES ('legacy-run','legacy-request','content','text_analysis','f','i','s',0,1,?,'completed')""",
                (now,),
            )
        app.initialize_library()
        with app.database_connection() as connection:
            pipeline = connection.execute(
                "SELECT status,wait_reason FROM analysis_pipeline_requests WHERE pipeline_id='restart-pipe'"
            ).fetchone()
            attempt = connection.execute(
                "SELECT status,error_code FROM analysis_step_attempts WHERE attempt_id='restart-attempt'"
            ).fetchone()
            legacy = connection.execute("SELECT status FROM analysis_runs WHERE id='legacy-run'").fetchone()
        self.assertEqual(tuple(pipeline), ("waiting", "retry"))
        self.assertEqual(tuple(attempt), ("interrupted", "process_restart"))
        self.assertEqual(legacy[0], "completed")


if __name__ == "__main__":
    unittest.main()
