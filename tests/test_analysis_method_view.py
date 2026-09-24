"""The method view: one page per analysis method, with its result state and the expert's judgement."""
import re
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.serving import make_server

import app
from gurumoji.web import system_routes
import research_analysis
from gurumoji.analysis_method_registry import METHODS, SEPARATE_RUN_METHODS
from test_browser_e2e import browser_executable
from test_method_expert_samples import LINES, NAMES, PROFILE, QUESTION

PANEL_METHODS = ("participation", "conversation_dynamics", "morphology", "syntax", "lexical_frequency",
                 "cooccurrence", "descriptive_statistics", "group_statistics", "correlation", "audio_emotion",
                 "qualitative_coding", "kwic", "speaker_characteristics", "transformer_topics",
                 "local_insights ai_insights")


class MethodViewFixture(unittest.TestCase):
    item_id = "method_view"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-method-view-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for patcher in (patch.object(app, "DATABASE_FILE", self.root / "library.sqlite3"),
                        patch.object(research_analysis, "_load_ginza", return_value=(None, "test fallback")),
                        patch.object(research_analysis, "_load_sudachi", return_value=(None, "test fallback"))):
            patcher.start()
            self.addCleanup(patcher.stop)
        research_analysis._RESEARCH_CACHE.clear()
        self.addCleanup(research_analysis._RESEARCH_CACHE.clear)
        app.initialize_library()
        self.client = app.app.test_client()
        segments = [{"id": f"{self.item_id}_{index:03d}", "speaker": speaker, "text": text,
                     "start": index * 6.0, "end": index * 6.0 + 5.0,
                     "emotions": {"sample": {"label": "neutral", "label_ja": "中立", "model_name": "架空の保存済み推定"}}}
                    for index, (speaker, text) in enumerate(LINES)]
        app.upsert_library_item(
            item_id=self.item_id, source_name="架空の座談会.wav", output_dir=self.root / "out", media_path=None,
            language="ja", segments=segments, speaker_names=dict(NAMES), outline=None, emotion_analysis=None,
            files=[], write_srt=False, write_json=True, session_profile=PROFILE,
            speaker_profiles={key: {"display_name": name, "session_role": "moderator" if key == "MOD" else "participant"}
                              for key, name in NAMES.items()})
        data = self.client.get(f"/api/library/{self.item_id}/analysis").get_json()
        self.client.put(f"/api/library/{self.item_id}/analysis", json={
            "source_revision": data["item"]["revision_count"], "analysis_revision": data["item"]["analysis_revision"],
            "config": {**data["config"], "analysis_method": "thematic", "research_question": QUESTION}})

    def overview(self):
        response = self.client.get(f"/api/library/{self.item_id}/analysis/methods")
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()


class MethodOverviewApiTests(MethodViewFixture):
    def test_every_analysis_method_is_listed_once_with_its_result_state(self):
        data = self.overview()
        listed = [method["method_id"] for method in data["methods"]]
        self.assertEqual(set(listed), {key for key, *_ in METHODS} - SEPARATE_RUN_METHODS)
        self.assertEqual(len(listed), len(set(listed)))
        self.assertEqual({method_id for group in data["groups"] for method_id in group["method_ids"]}, set(listed))
        self.assertEqual(sum(data["summary"].values()), len(listed))
        for method in data["methods"]:
            self.assertTrue(method["title"] and method["status_label"] and method["verdict_label"], method)

    def test_a_method_without_a_result_shows_its_conditions_instead_of_a_judgement(self):
        methods = {method["method_id"]: method for method in self.overview()["methods"]}
        transformer = methods["transformer_topics"]
        self.assertEqual((transformer["produced"], transformer["verdict"]), (False, "none"))
        self.assertEqual((transformer["expert_id"], transformer["expert_scope"]),
                         ("exp-embedding-topic-exploration", "preconditions"))
        self.assertTrue(transformer["verdict_reason"])

    def test_produced_methods_carry_the_responsible_expert_shared_between_methods(self):
        data = self.overview()
        methods = {method["method_id"]: method for method in data["methods"]}
        participation = methods["participation"]
        self.assertTrue(participation["produced"])
        self.assertIn(participation["verdict"], {"ok", "check"})
        self.assertEqual(participation["expert_scope"], "result")
        expert = data["experts"][participation["expert_id"]]
        self.assertEqual(expert["expert_id"], "exp-participation-balance")
        self.assertEqual(expert["selection_label"], "現在のデータに対する確認")
        self.assertTrue(expert["procedure"] and expert["references"] and expert["prohibited_conclusions"])
        # One entry serves every method the expert covers.
        self.assertEqual({methods[method_id]["expert_id"] for method_id in
                          ("lexical_frequency", "cooccurrence", "speaker_characteristics", "kwic")},
                         {"exp-quantitative-text-analysis"})

    def test_functions_without_an_expert_say_why(self):
        methods = {method["method_id"]: method for method in self.overview()["methods"]}
        for method_id in ("local_insights", "qualitative_coding", "ai_insights", "outline", "ai_finishing"):
            with self.subTest(method_id):
                self.assertEqual(methods[method_id]["expert_id"], "")
                self.assertTrue(methods[method_id]["expert_note"])
        self.assertEqual(methods["local_insights"]["verdict"], "no_expert")

    def test_missing_item_is_reported(self):
        self.assertEqual(self.client.get("/api/library/unknown/analysis/methods").status_code, 404)

    def test_the_interface_offers_the_method_tab_and_tags_every_result_panel(self):
        html = (app.APP_DIRECTORY / "templates" / "index.html").read_text(encoding="utf-8")
        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        script += (app.APP_DIRECTORY / "static" / "analysis-method-view.js").read_text(encoding="utf-8")
        content = (app.APP_DIRECTORY / "static" / "analysis-content.js").read_text(encoding="utf-8")
        self.assertEqual(html.count('data-analysis-mode="methods"'), 2)
        for needle in ("function renderMethodAnalysis", "data-analysis-method-select", "buildExpertDetails"):
            self.assertIn(needle, script)
        for method_id in PANEL_METHODS:
            with self.subTest(method_id):
                self.assertTrue(f", '{method_id}')" in script or f", '{method_id}')" in content, method_id)


class MethodViewBrowserTests(MethodViewFixture):
    def test_real_browser_shows_each_method_with_its_expert_and_panels(self):
        browser = browser_executable()
        if browser is None:
            self.skipTest("Chrome, Edge, or Chromium is required for the browser smoke test")
        driver = r"""
window.addEventListener('DOMContentLoaded', async () => {
  const waitFor = async (check, label) => {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const value = check();
      if (value) return value;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error('timeout: ' + label);
  };
  try {
    const content = await waitFor(() => {
      const host = document.querySelector('#analysis-desktop-content');
      return host && host.querySelector('.analysis-result-intro') ? host : null;
    }, 'analysis view');
    document.querySelector('.analysis-desktop-layout [data-analysis-mode="methods"]').click();
    const buttons = await waitFor(() => {
      const found = content.querySelectorAll('[data-analysis-method-select]');
      return found.length ? found : null;
    }, 'method list');
    document.body.dataset.methodCount = String(buttons.length);
    document.body.dataset.methodSummary = String(content.querySelectorAll('.analysis-method-chip').length);
    [...buttons].find(button => button.dataset.analysisMethodSelect === 'participation').click();
    const detail = await waitFor(() => content.querySelector('.analysis-method-detail'), 'method detail');
    document.body.dataset.methodPanels = String(detail.querySelectorAll('.analysis-panel').length);
    document.body.dataset.methodExpert = (detail.querySelector('.analysis-expert summary') || {}).textContent || '';
    document.body.dataset.methodVerdict = (detail.querySelector('.analysis-method-verdict') || {}).textContent || '';
    // Selecting a method rebuilds the list, so the buttons must be looked up again.
    const rebuilt = content.querySelectorAll('[data-analysis-method-select]');
    [...rebuilt].find(button => button.dataset.analysisMethodSelect === 'transformer_topics').click();
    const pending = await waitFor(() => content.querySelector('.analysis-method-detail'), 'second method');
    document.body.dataset.methodPending = pending.textContent.includes('実行前に満たす条件') ? 'conditions' : 'missing';
    document.body.dataset.methodView = 'passed';
  } catch (error) {
    document.body.dataset.methodView = 'failed: ' + error.message;
  }
});
"""
        original_render = system_routes.render_template
        original_static = app.app.send_static_file

        def render(*args, **kwargs):
            return original_render(*args, **kwargs).replace(
                "</body>", '<script src="/static/method-view-test.js" defer></script></body>')

        def static(filename):
            if filename == "method-view-test.js":
                return app.app.response_class(driver, mimetype="text/javascript")
            return original_static(filename)

        server = make_server("127.0.0.1", 0, app.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(system_routes, "render_template", side_effect=render), \
                    patch.object(app.app, "send_static_file", side_effect=static), \
                    patch.object(app, "get_machine_profile", return_value={}), \
                    patch.object(app, "load_token_config", return_value=app.TokenConfig()):
                result = subprocess.run([
                    browser, "--headless=new", "--disable-gpu", "--disable-background-networking",
                    "--disable-extensions", "--no-first-run", "--no-default-browser-check", "--no-sandbox",
                    "--window-size=1440,1000", f"--user-data-dir={self.root / 'method-view-profile'}",
                    "--virtual-time-budget=20000", "--dump-dom",
                    f"http://127.0.0.1:{server.server_port}/#/analysis/{self.item_id}",
                ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

        def marker(name):
            found = re.search(rf'data-{name}="([^"]*)"', result.stdout)
            return found.group(1) if found else ""

        self.assertEqual(marker("method-view"), "passed", result.stdout[-3000:])
        self.assertEqual(marker("method-count"), "18")
        self.assertEqual(marker("method-summary"), "5")
        self.assertGreaterEqual(int(marker("method-panels")), 4)
        self.assertIn("参加バランスの専門家", marker("method-expert"))
        self.assertIn("結果あり", marker("method-verdict"))
        self.assertEqual(marker("method-pending"), "conditions")


if __name__ == "__main__":
    unittest.main()
