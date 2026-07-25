import unittest

import app


class UiDefaultsTests(unittest.TestCase):
    def test_processing_labels_and_json_visibility(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertIn("おすすめ — ノイズ除去・音量調整・明瞭化", page)
        self.assertIn("<strong>詳細処理</strong>", page)
        self.assertIn(
            "複数回処理やエフェクトを加えて精度を上げます。注意：処理時間が増えます",
            page,
        )
        self.assertIn("<h2>AI仕上げ <em>任意</em></h2>", page)
        self.assertIn("<p>TXT は常に作成</p>", page)
        self.assertNotIn("JSON（常時）", page)

    def test_ai_provider_selection_enables_all_options_and_json_downloads_are_hidden(self):
        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("listen(aiProvider, 'change', selectDefaultAiOptions);", script)
        self.assertIn(
            "if (aiProvider.value !== 'none')",
            script,
        )
        self.assertIn("aiOptionInputs.forEach(input => { input.checked = true; });", script)
        self.assertIn("if (aiProvider.value === 'none') input.checked = false;", script)
        self.assertIn(
            ".filter(file => !String(file.name || '').toLowerCase().endsWith('.json'))",
            script,
        )


if __name__ == "__main__":
    unittest.main()
