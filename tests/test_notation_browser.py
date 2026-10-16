import threading
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from werkzeug.serving import make_server

import app
import browser_support
import test_notation_workflows as fixtures


@browser_support.ui_browser_test
class NotationBrowserTests(unittest.TestCase):
    def test_real_browser_preview_apply_cancel_change_and_register(self):
        from playwright.sync_api import expect
        fixture = fixtures.NotationWorkflowTests("test_preview_is_read_only_no_llm_and_stale_preview_rejected")
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        app.save_custom_vocabulary(["AI", "サーバー"])
        server = make_server("127.0.0.1", 0, app.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(thread.join, 5); self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        with patch.object(app, "call_ai_json") as call, browser_support.sandboxed_playwright_browser() as browser:
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{server.server_port}/#/data/c")
            page.locator("#notation-preview").wait_for(state="visible")
            page.locator("#notation-preview").click()
            page.locator("#notation-apply").wait_for(state="visible")
            self.assertIn("送信なし", page.locator("#notation-status").inner_text())
            page.locator("#notation-apply").click()
            expect(page.locator('#notation-status')).to_contain_text('結果と差分を保存')
            page.locator("#notation-groups button", has_text="取り消し").first.click()
            expect(page.locator('#notation-status')).to_contain_text('研究者の変更を保存')
            first = page.locator("#notation-groups section").first
            first.locator("input").fill("研究者表記")
            first.get_by_role("button", name="この表記へ変更", exact=True).click()
            expect(page.locator('#notation-groups')).to_contain_text('表記: 研究者表記')
            expect(page.locator('#notation-groups button').first).to_be_enabled()
            page.locator("#notation-groups section").first.get_by_role("button", name="辞書へ登録", exact=True).click()
            expect(page.locator('#notation-status')).to_contain_text('表記辞書と変更履歴を保存')
            call.assert_not_called()
            self.assertFalse(page.locator("#notation-apply").is_visible())
            # Researcher controls also remain usable in a narrow viewport.
            screenshot_root = Path(os.environ.get('GURUMOJI_NOTATION_SCREENSHOT_DIR', fixture.root))
            screenshot_root.mkdir(parents=True, exist_ok=True)
            page.locator('[aria-labelledby="notation-title"]').screenshot(path=str(screenshot_root / 'notation-desktop.png'))
            page.set_viewport_size({"width": 390, "height": 844})
            self.assertTrue(page.locator("#notation-groups input").first.is_visible())
            page.locator("#notation-groups section").first.get_by_role("button", name="この群の辞書項目を削除", exact=True).click()
            expect(page.locator('#notation-status')).to_contain_text('表記辞書と変更履歴を保存')
            page.locator("#notation-groups section").first.scroll_into_view_if_needed()
            page.screenshot(path=str(screenshot_root / 'notation-mobile.png'))


if __name__ == "__main__":
    unittest.main()
