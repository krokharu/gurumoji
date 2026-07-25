import re
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

    def test_new_job_form_exposes_guided_defaults_and_advanced_settings(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertIn("<h2>新しい文字起こし</h2>", page)
        self.assertIn('id="file-drop-zone"', page)
        self.assertIn("ここへドラッグ＆ドロップ", page)
        self.assertIn("パスと保存先を指定", page)
        self.assertIn("処理装置・話者数・無音判定を手動調整", page)
        self.assertIn('id="setup-ready-state"', page)
        self.assertIn('class="primary-button launch-button"', page)
        self.assertRegex(
            page,
            r'id="start-button"[^>]*type="submit"[^>]*disabled',
        )

    def test_desktop_and_mobile_creation_interfaces_are_separate(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertEqual(page.count('id="job-form"'), 1)
        self.assertIn('class="desktop-create-sidebar desktop-only"', page)
        self.assertIn('class="mobile-create-header mobile-only"', page)
        self.assertIn('id="mobile-wizard-nav"', page)
        self.assertIn('data-mobile-step="1"', page)
        self.assertIn('data-mobile-step="2"', page)
        self.assertEqual(page.count('data-mobile-step="3"'), 2)
        self.assertIn('data-mobile-step="4"', page)
        self.assertIn('data-mobile-review-source', page)
        ids = re.findall(r'\bid="([^"]+)"', page)
        self.assertEqual(len(ids), len(set(ids)))

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
        self.assertIn("function updateCreateSummary()", script)
        self.assertIn("listen(fileDropZone, 'drop'", script)
        self.assertIn("window.matchMedia('(max-width: 959px)')", script)
        self.assertIn("browserFilePickerOnly || isMobileWizard()", script)
        self.assertIn("function setMobileStep(", script)

        styles = (app.APP_DIRECTORY / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn("width: min(calc(100% - 24px), 700px);", styles)
        self.assertIn("@media (min-width: 960px)", styles)
        self.assertIn("@media (max-width: 959px)", styles)


if __name__ == "__main__":
    unittest.main()
