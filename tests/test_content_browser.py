import json
import subprocess
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from werkzeug.serving import make_server

import app
import test_browser_e2e as browser_support
import test_content_analysis as content_support


class ContentBrowserTests(unittest.TestCase):
    def setUp(self):
        self.fixture = content_support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = Path(self.fixture.temp.name)
        media = self.root / "media"
        media_patch = patch.object(app, "MEDIA_DIRECTORY", media)
        media_patch.start()
        self.addCleanup(media_patch.stop)
        audio = media / "content" / "sample.wav"
        audio.parent.mkdir(parents=True)
        with wave.open(str(audio), "wb") as handle:
            handle.setnchannels(1); handle.setsampwidth(2); handle.setframerate(8000)
            handle.writeframes(b"\0\0" * 8000 * 20)
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id='content'", (str(audio),))
        _, args = self.fixture.start()
        self.fixture.run_worker(args, response=content_support.finding(["E0001"], text="保存済みAI見解。<img src=x onerror=window.injected=1>"))

    def exercise_browser(self, mobile=False, reload_only=False, generate=False, linked='', unified_execution=False):
        browser = browser_support.browser_executable()
        if not browser:
            self.skipTest("Edge, Chrome or Chromium is required")
        original_render = app.render_template
        original_static = app.app.send_static_file
        original_worker = app.run_analysis_insight_job
        worker_done = threading.Event()

        def tracked_worker(*args, **kwargs):
            try:
                return original_worker(*args, **kwargs)
            finally:
                worker_done.set()
        driver = r"""
<script>
window.addEventListener('error', e => { document.body.dataset.scriptError = e.message; });
window.addEventListener('DOMContentLoaded', async () => {
  const waitFor = async (check, attempts = 160) => {
    for (let i = 0; i < attempts; i++) {
      if (check()) return;
      // Await real server work as well as virtual browser time, allowing the
      // background worker to finish its durable filesystem writes.
      if (i % 10 === 0) await fetch('/api/jobs/active', {cache:'no-store'});
      await new Promise(r => setTimeout(r, 40));
    }
    throw new Error('Timed out: ' + check.toString() + ' / ' + JSON.stringify(contentAnalysisState().run)
      + ' / ' + contentAnalysisState().aiError + ' / ' + contentAnalysisState().pollError);
  };
  const assert = (value, message) => { if (!value) throw new Error(message); };
  try {
    await waitFor(() => !!analysisState.data);
    if (UNIFIED_EXECUTION) {
      const runButton = document.querySelector('#analysis-run-button');
      runButton.click();
      assert(document.querySelector('#analysis-run-dialog').open, 'unified execution dialog did not open');
      const manual = document.querySelector('input[name="analysis_run_mode"][value="manual"]');
      manual.checked = true;
      manual.dispatchEvent(new Event('input', {bubbles: true}));
      document.querySelector('#analysis-definition-name').value = 'Utterance length';
      document.querySelector('#analysis-definition-id').value = 'utterance_length';
      document.querySelector('#analysis-definition-description').value = 'Characters in each included utterance';
      document.querySelector('#analysis-definition-output').value = 'utterance_length';
      document.querySelector('#analysis-definition-output').dispatchEvent(new Event('input', {bubbles: true}));
      const initialTrialText = document.querySelector('#analysis-definition-trial-result').textContent;
      document.querySelector('#analysis-run-publish').checked = false;
      document.querySelector('#analysis-run-form').requestSubmit();
      await waitFor(() => analysisExecutionState.status === 'completed');
      assert(!document.querySelector('#analysis-execution-view').hidden, 'execution screen missing');
      assert(document.querySelector('#analysis-execution-percent').textContent === '100%', 'execution progress incomplete');
      assert(document.querySelectorAll('.analysis-execution-stage.completed').length === 8, 'unexpected completed milestones');
      assert(document.querySelector('#analysis-execution-stages').textContent.includes('M7'), 'M0-M7 milestones missing');
      assert(document.querySelector('#analysis-definition-trial-result').textContent !== initialTrialText, 'manual trial result missing');
      document.querySelector('#analysis-execution-results').click();
      await waitFor(() => document.querySelector('#analysis-execution-view').hidden && !document.querySelector('#analysis-shell').hidden);
      assert(window.location.hash === '#/analysis/content', 'execution route did not return to results');
      assert(!!document.querySelector('.analysis-archive-files a[href$="/export.zip"]'), 'pipeline ZIP export link missing');
      document.body.dataset.contentTest = 'passed'; return;
    }
    if (LINKED_MODE === 'valid') {
      await waitFor(() => !resultCard.hidden && selectedSegmentId === 'a1');
      assert(mediaPlayer.src.includes('/content/media'), 'linked media unavailable');
      document.body.dataset.contentTest = 'passed'; return;
    }
    if (LINKED_MODE === 'stale') {
      await waitFor(() => document.querySelector('#analysis-message').textContent.includes('引用の保存後'));
      assert(resultCard.hidden, 'stale citation automatically opened current audio');
      document.body.dataset.contentTest = 'passed'; return;
    }
    await waitFor(() => !analysisCard.hidden);
    await waitFor(() => !!currentAnalysisContent().querySelector('.content-ai-output .content-finding'));
    const host = currentAnalysisContent();
    assert(!!host.querySelector('.content-insight-summary'), 'summary missing');
    assert(host.querySelector('.content-insight-summary').compareDocumentPosition(host.querySelector('.analysis-overview')) & Node.DOCUMENT_POSITION_FOLLOWING, 'summary order');
    assert(!window.injected && !host.querySelector('.content-ai-output img'), 'AI output was not escaped');
    assert(host.querySelector('.content-ai-output').textContent.includes('保存済みAI見解'), 'saved AI missing');
    assert(host.querySelectorAll('.analysis-distribution-row').length > 0, 'descriptive statistics chart missing');
    assert(host.querySelector('.analysis-frequency-stage .analysis-bar-track'), 'frequency chart missing');
    assert(host.querySelector('.analysis-crosstab-stage .analysis-stacked-bar'), 'crosstab chart missing');
    assert(host.querySelector('.analysis-table-details'), 'statistical detail table missing');
    await waitFor(() => analysisStorageState().runs.length > 0);
    assert(host.querySelector('.analysis-archive-run'), 'saved archive missing');
    if (GENERATE_ONLY) {
      const previous = analysisState.data.insights.ai.request_id;
      const originalFetch = apiFetch;
      let failedOnce = false;
      apiFetch = (url, options = {}) => {
        if (url.endsWith('/analysis/insights') && !options.method && !failedOnce) {
          failedOnce = true;
          return Promise.resolve(new Response(JSON.stringify({error: '一時的な通信エラー'}), {
            status: 503, headers: {'Content-Type': 'application/json'}
          }));
        }
        return originalFetch(url, options);
      };
      setAnalysisDirty(true);
      assert(host.querySelector('[data-insight-generate]').disabled, 'unsaved generation enabled');
      setAnalysisDirty(false);
      host.querySelector('[data-insight-generate]').click();
      host.querySelector('[data-insight-generate]').click();
      // File fsync uses wall time while headless timers use virtual time.
      // A test-only server barrier lets the actual background job finish;
      // UI polling must still recover and render the persisted result below.
      const finished = await fetch('/static/content-worker-wait');
      assert(finished.ok, 'background generation did not finish');
      await waitFor(() => analysisState.data.insights.ai?.request_id !== previous, 1500);
      assert(contentAnalysisState().run.status === 'completed', 'generation status');
      assert(host.querySelector('.content-ai-output').textContent.includes('新しい見解'), 'generated content');
      assert(host.querySelector('[data-insight-status]').textContent.includes('123'), 'usage missing');
      assert(failedOnce && !host.querySelector('[data-insight-status]').textContent.includes('通信エラー'), 'poll did not recover');
      document.body.dataset.contentTest = 'passed'; return;
    }
    if (RELOAD_ONLY) { document.body.dataset.contentTest = 'passed'; return; }
    setAnalysisDirty(true);
    assert(host.querySelector('[data-archive-save]').disabled, 'unsaved archive enabled');
    setAnalysisDirty(false);
    await saveAnalysisPackage();
    assert(analysisStorageState().runs.some(r => r.kind === 'text_analysis' && r.vault_status === 'completed'), 'text archive not saved');
    const savedRun = analysisStorageState().runs.find(r => r.kind === 'text_analysis');
    assert(savedRun.artifacts.some(a => a.name === 'manifest.json'), 'manifest link missing');
    await saveAnalysisPackage();
    assert(analysisStorageState().runs.filter(r => r.kind === 'text_analysis').length === 1, 'duplicate archive');
    const query = host.querySelector('[data-kwic-query]');
    query.value = '価格'; query.dispatchEvent(new Event('input', {bubbles:true}));
    host.querySelector('.content-kwic-form').requestSubmit();
    await waitFor(() => !!contentAnalysisState().result && !contentAnalysisState().loading);
    assert(contentAnalysisState().result.total === 3, 'KWIC hit count');
    await saveAnalysisPackage({q: '価格', mode:'literal', speaker:''});
    assert(analysisStorageState().runs.some(r => r.kind === 'kwic'), 'KWIC archive missing');
    const hit = host.querySelector('.content-kwic-hit');
    assert(hit.querySelector('mark').textContent === '価格', 'highlight');
    const refs = hit.querySelector('details'); refs.open = true;
    await waitFor(() => !!refs.querySelector('blockquote button'));
    hit.scrollIntoView({block:'center'});
    refs.querySelector('blockquote button').click();
    await waitFor(() => !resultCard.hidden && selectedSegmentId === 'a1');
    assert(!!mediaPlayer && mediaPlayer.src.includes('/content/media'), 'media unavailable');
    assert(document.querySelector('#media-caption').textContent.includes('参加者A'), 'media selection');
    const savedScroll = analysisEvidenceReturn.scroll;
    document.querySelector('#return-to-analysis-evidence').click();
    await waitFor(() => !analysisCard.hidden && !analysisEvidenceReturn);
    await waitFor(() => Math.abs(window.scrollY - savedScroll) < 20);
    assert(contentAnalysisState().query === '価格', 'query not restored');
    assert(currentAnalysisContent().querySelector('[data-kwic-query]').value === '価格', 'input not restored');
    assert(Math.abs(window.scrollY - savedScroll) < 20, 'scroll not restored: ' + window.scrollY + ' / ' + savedScroll);
    assert(document.documentElement.scrollWidth <= window.innerWidth + 2, 'horizontal overflow');
    const term = currentAnalysisContent().querySelector('.content-term-button'); term.click();
    await waitFor(() => !!contentAnalysisState().result && !contentAnalysisState().loading);
    assert(contentAnalysisState().result.mode === 'normalized', 'term search mode');
    assert(document.querySelector('#analysis-target-name').textContent === 'example.wav', 'target name not restored');
    document.body.dataset.contentTest = 'passed';
  } catch (error) { document.body.dataset.contentTest = 'failed: ' + error.message; }
});
</script>
""".replace("RELOAD_ONLY", "true" if reload_only else "false").replace("GENERATE_ONLY", "true" if generate else "false").replace("UNIFIED_EXECUTION", "true" if unified_execution else "false").replace('LINKED_MODE', repr(linked))

        def render(*args, **kwargs):
            return original_render(*args, **kwargs).replace("</body>", '<script src="/static/content-browser-driver.js" defer></script></body>')

        def serve_static(filename):
            if filename == 'content-worker-wait':
                return app.app.response_class('done' if worker_done.wait(15) else 'timeout',
                                              status=200 if worker_done.is_set() else 504)
            if filename == "content-browser-driver.js":
                return app.app.response_class(driver.replace("<script>", "").replace("</script>", ""), mimetype="text/javascript")
            return original_static(filename)

        machine = {"cpu": {"available": True, "name": "Test", "logical_threads": 4},
                   "gpu": {"cuda_available": False, "reason": "test", "vram_gib": 0}, "memory_gib": 8,
                   "recommended": {"model_name": "tiny", "device": "cpu", "diarization_device": "cpu"}}
        server = make_server("127.0.0.1", 0, app.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        profile = self.root / ("mobile-profile" if mobile else "desktop-profile")
        ai_calls = []
        from urllib.parse import urlencode
        import hashlib
        query = {'view': 'analysis'}
        if linked:
            query.update(item='content', segment='a1', start='0', end='2', speaker='A',
                         text_hash=hashlib.sha256('価格を価格で比べる'.encode()).hexdigest() if linked == 'valid' else '0' * 64)

        def fake_ai(*args, **kwargs):
            ai_calls.append(1)
            args[8]({"provider": "openai", "model": "test", "request_count": 1,
                     "input_tokens": 100, "output_tokens": 23, "total_tokens": 123, "reported": True})
            return content_support.finding(["E0001"], text="新しい見解")

        try:
            with patch.object(app, "render_template", side_effect=render), \
                 patch.object(app.app, "send_static_file", side_effect=serve_static), \
                 patch.object(app, "get_machine_profile", return_value=machine), \
                 patch.object(app, "load_token_config", return_value=app.TokenConfig(openai_api_key="test-key")), \
                 patch.object(app, "run_analysis_insight_job", side_effect=tracked_worker), \
                 patch.object(app, "call_ai_json", side_effect=fake_ai):
                result = subprocess.run([
                    browser, "--headless=new", "--disable-gpu", "--disable-background-networking",
                    "--disable-extensions", "--no-first-run", "--no-default-browser-check", "--no-sandbox",
                    "--autoplay-policy=no-user-gesture-required", "--force-device-scale-factor=1",
                    "--window-size=390,844" if mobile else "--window-size=1440,1000",
                    f"--user-data-dir={profile}", "--virtual-time-budget=70000", "--dump-dom",
                    f"http://127.0.0.1:{server.server_port}/?{urlencode(query)}",
                ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        import re
        status = re.search(r'data-content-test="([^"]+)"', result.stdout)
        script_error = re.search(r'data-script-error="([^"]+)"', result.stdout)
        self.assertIsNotNone(status, (script_error.group(0) if script_error else result.stderr[-1500:]))
        self.assertEqual(status.group(1), "passed", self.fixture.client.get(self.fixture.url + '/insights').get_json())
        self.assertIsNone(script_error)
        self.assertEqual(len(ai_calls), 1 if generate else 0)

    def test_desktop_evidence_kwic_audio_return_and_saved_ai_reload(self):
        self.exercise_browser()
        self.exercise_browser(reload_only=True)

    def test_mobile_evidence_kwic_audio_return(self):
        self.exercise_browser(mobile=True)

    def test_ai_generation_button_saves_and_deduplicates(self):
        self.exercise_browser(generate=True)

    def test_unified_analysis_execution_dialog_and_progress_screen(self):
        self.exercise_browser(unified_execution=True)

    def test_vault_links_open_matching_audio_and_preserve_old_evidence_after_edit(self):
        self.exercise_browser(linked='valid')
        self.exercise_browser(mobile=True, linked='stale')


if __name__ == "__main__":
    unittest.main()
