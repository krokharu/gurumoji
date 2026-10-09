"""Real browser interactions with synthetic responses and isolated app data."""
import copy
import json
import os
import unittest
from pathlib import Path

import browser_support
import test_ui_safety_browser as ui_support


@browser_support.ui_browser_test
class ObsidianManagementBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.browser_context = browser_support.sandboxed_playwright_browser()
        cls.browser = cls.browser_context.__enter__()
        cls.addClassCleanup(cls.browser_context.__exit__, None, None, None)

    def setUp(self):
        self.fixture = ui_support.UiSafetyBrowser("runTest")
        self.fixture.browser = self.browser
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.page = self.fixture.page
        self.requests = []
        self.run = {"run_id": "browser-R1", "item_id": "A", "status": "cancelled", "phase": "stopped",
            "source_revision": 1, "iteration": 1, "allowed_actions": [], "events": [], "tasks": [], "roles": [],
            "config": {"question": "合成の問い", "provider": "lmstudio", "model": "synthetic", "obsidian_management": True},
            "obsidian_management": {"enabled": True, "status": "edited", "note_id": "memory-browser-R1"}}
        self.page.route("**/analysis/orchestration/**", self.route)

    def route(self, route):
        request = route.request
        self.requests.append((request.method, request.url, request.post_data))
        if request.url.endswith("/memory/note"):
            route.fulfill(status=200, content_type="text/markdown", body="# Synthetic management\n",
                headers={"Content-Disposition": 'attachment; filename="obsidian-management.md"'})
            return
        if request.method == "POST":
            self.assertTrue(request.url.endswith("/memory/retry"))
            self.assertEqual(json.loads(request.post_data), {})
            self.run["obsidian_management"]["status"] = "linked"
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"run": self.run}))

    def show_run(self):
        self.page.evaluate("""run => {
            Object.assign(analysisState,{itemId:'A',data:{item:{id:'A',source_name:'合成会話',revision_count:1,analysis_revision:0}},config:{},dirty:false});
            document.body.dataset.view='analysis';analysisCard.hidden=false;
            orchestrationAdopt(run,'A');
            document.getElementById('orchestration-live').showModal();
        }""", copy.deepcopy(self.run))

    def test_management_retry_and_download_at_desktop_and_mobile_widths(self):
        self.show_run()
        self.page.locator("#orchestration-memory-retry").click()
        self.page.wait_for_function("document.getElementById('orchestration-memory-status').textContent.includes('参照を保存済み')")
        self.assertEqual(len([request for request in self.requests if request[0] == "POST"]), 1)
        self.assertIn("CODE", self.page.locator('[data-role="obsidian_manager"]').inner_text())
        self.assertFalse(self.page.locator("#orchestration-memory-retry").is_visible())
        self.assertEqual(self.page.locator("#orchestration-memory-note").get_attribute("href"),
                         "/api/library/A/analysis/orchestration/browser-R1/memory/note")
        for label, width in (("desktop", 1440), ("mobile", 390)):
            self.page.set_viewport_size({"width": width, "height": 900})
            section = self.page.locator("#orchestration-memory")
            section.scroll_into_view_if_needed()
            bounds = section.bounding_box()
            self.assertIsNotNone(bounds)
            self.assertGreaterEqual(bounds["x"], -1)
            self.assertLessEqual(bounds["x"] + bounds["width"], width + 1)
            output = os.environ.get("GURUMOJI_QA_ARTIFACT_DIR")
            if output:
                target = Path(output)
                target.mkdir(parents=True, exist_ok=True)
                self.page.screenshot(path=str(target / f"management-{label}.png"))
        with self.page.expect_download() as captured:
            self.page.locator("#orchestration-memory-note").click()
        self.assertEqual(captured.value.suggested_filename, "obsidian-management.md")
        self.fixture.assert_no_script_error()

    def test_new_run_can_disable_management_without_selecting_four_vault_output(self):
        self.show_run()
        self.page.locator("#orchestration-live-close").click()
        self.page.evaluate("openAnalysisOrchestrationSettings()")
        self.assertTrue(self.page.locator("#orchestration-memory-enabled").is_checked())
        self.assertFalse(self.page.locator("#orchestration-publication-all").is_checked())
        self.page.locator("#orchestration-question").fill("合成の問い")
        self.page.locator("#orchestration-memory-enabled").uncheck()
        value = self.page.evaluate("orchestrationPayload()")
        self.assertFalse(value["obsidian_management"])
        self.assertEqual(value["publication_targets"], [])
        self.assertEqual([request for request in self.requests if request[0] == "POST"], [])
        self.fixture.assert_no_script_error()


if __name__ == "__main__":
    unittest.main()
