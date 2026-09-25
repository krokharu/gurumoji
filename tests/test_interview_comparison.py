import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class InterviewComparisonApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-interview-comparison-")
        self.addCleanup(self.temp.cleanup)
        self.database_patch = patch.object(app, "DATABASE_FILE", Path(self.temp.name) / "library.sqlite3")
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        app.initialize_library()
        self.client = app.app.test_client()
        self.add_item("same_a", "同内容 A", "製品評価", ["使いやすい製品", "価格を改善してほしい"])
        self.add_item("same_b", "同内容 B", "製品評価", ["製品は使いやすい", "価格より機能を重視する"])
        self.add_item("different", "別内容", "採用面接", ["採用の面接方法", "候補者の評価方法"])

    def add_item(self, item_id, name, comparison_group, texts):
        segments = [
            {"id": f"{item_id}_{index}", "speaker": "P1", "start": index * 2,
             "end": index * 2 + 1, "text": text}
            for index, text in enumerate(texts)
        ]
        app.upsert_library_item(
            item_id=item_id, source_name=name, output_dir=Path(self.temp.name) / item_id,
            media_path=None, language="ja", segments=segments, speaker_names={"P1": "参加者"},
            outline=None, emotion_analysis=None, files=[], write_srt=False, write_json=True,
            session_profile={
                "session_type": "focus_group", "comparison_group": comparison_group,
                "objective": "比較テスト", "moderator_guide": "質問ガイド",
            },
        )

    def test_same_content_comparison_is_allowed_by_default(self):
        response = self.client.post("/api/library/interview-comparison", json={
            "item_ids": ["same_a", "same_b"], "allow_different_content": False,
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        self.assertTrue(data["same_content"])
        self.assertEqual(data["mode"], "same_content")
        self.assertEqual([item["item_id"] for item in data["interviews"]], ["same_a", "same_b"])
        self.assertIn("term_count", data["interviews"][0])

    def test_different_content_requires_explicit_override(self):
        payload = {"item_ids": ["same_a", "different"], "allow_different_content": False}
        blocked = self.client.post("/api/library/interview-comparison", json=payload)
        self.assertEqual(blocked.status_code, 409)
        self.assertIn("異なる内容", blocked.get_json()["error"])

        payload["allow_different_content"] = True
        allowed = self.client.post("/api/library/interview-comparison", json=payload)
        self.assertEqual(allowed.status_code, 200, allowed.get_json())
        data = allowed.get_json()
        self.assertEqual(data["mode"], "different_content")
        self.assertTrue(any("内容が異なる" in caution for caution in data["cautions"]))

    def test_catalog_exposes_safe_comparison_metadata(self):
        items = self.client.get("/api/library").get_json()["items"]
        same = next(item for item in items if item["id"] == "same_a")
        self.assertEqual(same["comparison_label"], "製品評価")
        self.assertTrue(same["comparison_key"].startswith("group:"))
        self.assertEqual(same["comparison_source"], "comparison_group")

    def test_comparison_group_is_editable_and_comparison_ui_is_loaded(self):
        template = self.client.get("/").get_data(as_text=True)
        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        comparison_script = (app.APP_DIRECTORY / "static" / "interview-comparison.js").read_text(encoding="utf-8")
        self.assertIn('id="session-comparison-group"', template)
        self.assertIn("'comparison_group'", script)
        self.assertIn("#session-comparison-group", script)
        self.assertIn("/api/library/interview-comparison", comparison_script)
        self.assertIn('id="interview-comparison-history-list"', template)
        self.assertIn("/api/analysis/runs/${encodeURIComponent(runId)}/vault", comparison_script)
        self.assertIn("loadComparisonHistory()", comparison_script)

    def test_browser_requests_require_csrf_and_save_the_displayed_input_version(self):
        headers = {'Origin': 'http://localhost', 'Sec-Fetch-Site': 'same-origin'}
        selection = {'item_ids': ['same_a', 'same_b'], 'allow_different_content': False}
        url = '/api/library/interview-comparison'
        self.assertEqual(self.client.post(url, json=selection, headers=headers).status_code, 403)
        self.assertEqual(self.client.post(url + '/runs', json=selection, headers=headers).status_code, 403)
        headers['X-Gurumoji-Request'] = '1'
        compared = self.client.post(url, json=selection, headers=headers)
        self.assertEqual(compared.status_code, 200)
        payload = {**selection, 'request_id': 'versioned-comparison-0001',
                   'input_fingerprints': compared.get_json()['input_fingerprints']}
        missing = {key: value for key, value in payload.items() if key != 'input_fingerprints'}
        self.assertEqual(self.client.post(url + '/runs', json=missing, headers=headers).status_code, 400)
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET source_name='changed',revision_count=revision_count+1 WHERE id='same_a'")
        stale = self.client.post(url + '/runs', json=payload, headers=headers)
        self.assertEqual(stale.status_code, 409, stale.get_json())
        self.assertTrue(stale.get_json()['conflict'])
        self.assertEqual(app.analysis_archive_store().list_comparisons(), [])
        payload['input_fingerprints'] = self.client.post(url, json=selection, headers=headers).get_json()['input_fingerprints']
        saved = self.client.post(url + '/runs', json=payload, headers=headers)
        self.assertEqual(saved.status_code, 200, saved.get_json())
        repeated = self.client.post(url + '/runs', json=payload, headers=headers)
        self.assertEqual(repeated.get_json()['run']['id'], saved.get_json()['run']['id'])


if __name__ == "__main__":
    unittest.main()
