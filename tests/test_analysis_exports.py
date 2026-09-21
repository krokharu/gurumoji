import csv
import io
import json
import time
import unittest
import zipfile

import test_content_analysis as support


class AnalysisPipelineExportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests(
            "test_generated_result_persists_and_becomes_stale_on_edit"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.url = self.fixture.url

    def test_json_csv_and_zip_round_trip_from_one_fixed_package(self):
        item = self.client.get(self.url).get_json()["item"]
        response = self.client.post(self.url + "/pipelines", json={
            "request_id": "pipeline-export-request-0001",
            "source_revision": item["revision_count"],
            "analysis_revision": item["analysis_revision"],
            "mode": "automatic", "definition_ids": [],
            "provider_policy": "local_only", "publication_targets": [],
        })
        pipeline_id = response.get_json()["pipeline_id"]
        result = None
        for _ in range(250):
            result = self.client.get(f"{self.url}/pipelines/{pipeline_id}").get_json()
            if result["status"] in {"completed", "waiting", "failed"}:
                break
            time.sleep(0.02)
        self.assertEqual(result["status"], "completed", result)
        run = result["result_run"]
        bundle = self.client.get(f"/api/analysis/runs/{run['id']}/export.zip")
        self.assertEqual(bundle.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(bundle.data)) as archive:
            self.assertIn("manifest.json", archive.namelist())
            self.assertIn("result.json", archive.namelist())
            self.assertIn("tables/speakers.csv", archive.namelist())
            manifest = json.loads(archive.read("manifest.json"))
            package = json.loads(archive.read("result.json"))
            speakers = list(csv.DictReader(io.StringIO(
                archive.read("tables/speakers.csv").decode("utf-8-sig")
            )))
        self.assertEqual(manifest["analysis_id"], run["id"])
        self.assertEqual({value["method_id"] for value in package["methods"]}, {
            "participation", "conversation_dynamics",
        })
        self.assertEqual(len(speakers), 2)
        self.assertEqual(manifest["input_fingerprint"], result["input_hash"])


if __name__ == "__main__":
    unittest.main()
