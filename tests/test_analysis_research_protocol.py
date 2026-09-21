import csv
import io
import json
import time
import unittest

import app
import test_content_analysis as support


class AnalysisResearchProtocolTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests(
            "test_generated_result_persists_and_becomes_stale_on_edit"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.url = self.fixture.url

    def revisions(self):
        item = self.client.get(self.url).get_json()["item"]
        return item["revision_count"], item["analysis_revision"]

    def wait(self, pipeline_id):
        body = None
        for _ in range(250):
            body = self.client.get(f"{self.url}/pipelines/{pipeline_id}").get_json()
            if body["status"] in {"completed", "waiting", "failed", "cancelled"}:
                return body
            time.sleep(0.02)
        self.fail(f"pipeline timeout: {body}")

    def artifact(self, run, name):
        artifact = next(value for value in run["artifacts"] if value["name"] == name)
        response = self.client.get(artifact["url"])
        self.assertEqual(response.status_code, 200)
        return response.data

    def pipeline_payload(self, request_id, definition_ids=None):
        source_revision, analysis_revision = self.revisions()
        return {
            "request_id": request_id, "source_revision": source_revision,
            "analysis_revision": analysis_revision, "mode": "manual",
            "definition_ids": definition_ids or [], "provider_policy": "local_only",
            "publication_targets": [],
            "research_protocol": {"classification": "exploratory", "data_viewed": True},
        }

    def test_existing_method_adapter_matches_legacy_csv_values(self):
        response = self.client.post(
            self.url + "/pipelines",
            json=self.pipeline_payload("research-equivalence-request-0001"),
        )
        result = self.wait(response.get_json()["pipeline_id"])
        self.assertEqual(result["status"], "completed", result)
        pipeline_rows = list(csv.DictReader(io.StringIO(
            self.artifact(result["result_run"], "tables/speakers.csv").decode("utf-8-sig")
        )))
        legacy_rows = list(csv.DictReader(io.StringIO(
            self.client.get(self.url + "/export.csv?dataset=speakers").data.decode("utf-8-sig")
        )))
        numeric = ("turn_count", "speaking_seconds", "speaking_percent", "participant_percent",
                   "average_turn_seconds", "characters", "characters_per_minute")
        self.assertEqual(
            [{key: row[key] for key in numeric} for row in pipeline_rows],
            [{key: row[key] for key in numeric} for row in legacy_rows],
        )
        method_ids = [
            value["method_id"]
            for value in json.loads(self.artifact(result["result_run"], "result.json"))["methods"]
        ]
        self.assertEqual(method_ids, ["participation", "conversation_dynamics"])

    def test_manual_definition_trial_adoption_measurement_and_history(self):
        definition = {
            "definition_id": "utterance_length", "name": "発話文字数",
            "description": "除外していない発話ごとの文字数", "unit_of_analysis": "segment",
            "source_columns": ["text"], "output_column": "utterance_length",
            "data_type": "number", "measurement_level": "ratio",
            "measurement_rule": "text_length", "method": "descriptive", "status": "draft",
        }
        saved = self.client.put(
            self.url + "/definitions/utterance_length", json=definition
        )
        self.assertEqual(saved.status_code, 200, saved.get_json())
        self.assertEqual(saved.get_json()["definition"]["revision"], 1)
        trial = self.client.post(
            self.url + "/definitions/utterance_length/trials", json={"limit": 3}
        )
        self.assertEqual(trial.status_code, 200, trial.get_json())
        self.assertEqual(trial.get_json()["trial"]["external_calls"], 0)
        self.assertEqual(trial.get_json()["trial"]["sample_size"], 3)

        adopted = self.client.put(
            self.url + "/definitions/utterance_length",
            json={**definition, "status": "adopted", "expected_revision": 1},
        )
        self.assertEqual(adopted.status_code, 200, adopted.get_json())
        response = self.client.post(
            self.url + "/pipelines",
            json=self.pipeline_payload("manual-measurement-request-0001", ["utterance_length"]),
        )
        self.assertEqual(response.status_code, 202, response.get_json())
        result = self.wait(response.get_json()["pipeline_id"])
        self.assertEqual(result["status"], "completed", result)
        rows = list(csv.DictReader(io.StringIO(
            self.artifact(result["result_run"], "tables/measurements.csv").decode("utf-8-sig")
        )))
        self.assertEqual(len(rows), 4)  # the explicitly excluded x1 row is not measured
        self.assertEqual(rows[0]["utterance_length"], str(len("価格を価格で比べる")))
        self.assertTrue(all(row["utterance_length__missing_reason"] == "" for row in rows))

        package = json.loads(self.artifact(result["result_run"], "result.json"))
        manual = next(value for value in package["methods"] if value["method_id"] == "descriptive_statistics")
        self.assertIn("有効N=4", manual["summaries"][0]["text"])
        self.assertEqual(package["parameters"]["research_protocol"]["classification"], "exploratory")
        committed = [event["payload"]["milestone"] for event in result["events"]
                     if event["type"] == "milestone_committed"]
        self.assertEqual(committed, [f"M{index}" for index in range(8)])

    def test_draft_definition_and_unsupported_inference_stop_before_execution(self):
        definition = {
            "definition_id": "draft_label", "name": "ラベル", "description": "試行中",
            "unit_of_analysis": "segment", "source_columns": ["speaker"],
            "output_column": "draft_label", "data_type": "category",
            "measurement_level": "nominal", "measurement_rule": "identity",
            "method": "frequency", "status": "draft",
        }
        self.client.put(self.url + "/definitions/draft_label", json=definition)
        preview = self.client.post(
            self.url + "/plans/preview",
            json=self.pipeline_payload("unused-preview-request-0001", ["draft_label"]),
        )
        self.assertEqual(preview.status_code, 409)
        self.assertEqual(preview.get_json()["reason_code"], "definition_not_adopted")
        unsupported = self.client.put(
            self.url + "/definitions/inference_test",
            json={**definition, "definition_id": "inference_test", "output_column": "inference_test",
                  "method": "pearson", "status": "adopted"},
        )
        self.assertEqual(unsupported.status_code, 409)
        self.assertEqual(unsupported.get_json()["reason_code"], "method_unavailable")


if __name__ == "__main__":
    unittest.main()
