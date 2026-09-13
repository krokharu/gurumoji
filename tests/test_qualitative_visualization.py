"""Browser regression checks for counts, evidence, and interpretation boundaries."""
import re
import subprocess
import threading
import unittest
from unittest.mock import patch

from werkzeug.serving import make_server

import app
import test_analysis as fixtures
import test_browser_e2e as browser_support


class QualitativeVisualizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.AnalysisApiTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.item_id = 'visual_fixture'
        segments = [{'id': f's{i}', 'speaker': f'P{i % 2}', 'start': i * 2, 'end': i * 2 + 1,
                     'text': f'  発言{i}\n<img src=x onerror=window.injected=1>  '} for i in range(105)]
        self.fixture.create_analysis_item(self.item_id, segments)
        annotations = {}
        for i in range(105):
            codes = (['short'] if i < 10 else []) + (['long'] if i <= 100 else [])
            annotations[f's{i}'] = {'codes': codes, 'excluded': i == 20}
        for sid, target, relation in [('s2', 's1', 'agreement'), ('s4', 's3', 'disagreement'), ('s90', 's0', 'change')]:
            annotations[sid]['interaction_links'] = [{'target_segment_id': target, 'relation': relation, 'evidence_memo': '研究者の解釈（自動推論ではない）'}]
        response = self.fixture.put_analysis(self.item_id, config={
            'exclude_moderator': False,
            'codebook': [{'id': 'short', 'label': '10件コード'}, {'id': 'long', 'label': '100件コード'}, {'id': 'zero', 'label': '0件コード'}]},
            annotations=annotations)
        self.assertEqual(response.status_code, 200, response.data)

    def exercise_browser(self, size):
        browser = browser_support.browser_executable()
        if not browser:
            self.skipTest('Chromium browser required')
        original_render = app.render_template
        original_static = app.app.send_static_file
        driver = r'''
window.addEventListener('error', event => { document.body.dataset.visualError = event.message; });
window.addEventListener('DOMContentLoaded', async () => {
  const assert = (value, message) => { if (!value) throw new Error(message); };
  const wait = async fn => {
    for (let i=0; i<200; i++) {
      if (fn()) return;
      if (i % 10 === 0) await fetch('/api/jobs/active');
      await new Promise(resolve => setTimeout(resolve, 40));
    }
    throw new Error('wait timed out: ' + fn.toString());
  };
  try {
    await wait(() => analysisState.data?.item.id === 'visual_fixture');
    setAnalysisMode('manual');
    const root = () => currentAnalysisContent();
    const graph = id => root().querySelector(`[data-qualitative-code="${id}"]`);
    assert(graph('short').querySelector('i').style.width === '10%', '10/100 scale is wrong');
    assert(graph('long').querySelector('i').style.width === '100%', '100 scale is wrong');
    assert(graph('zero').querySelector('i').style.width === '0%', 'zero has a visible bar');
    assert(getComputedStyle(graph('zero').querySelector('i')).minWidth === '0px', 'zero min-width');
    assert(!graph('short').querySelector('[role="img"]').getAttribute('aria-label').includes('%'), 'count mislabeled as percent');
    assert(root().querySelector('.analysis-matrix'), 'matrix missing on this viewport');
    root().querySelector('.qualitative-matrix-button').click();
    await wait(() => root().querySelector('.qualitative-matrix-evidence .qualitative-quote'));
    assert(root().querySelector('.qualitative-matrix-evidence').textContent.includes('連続ではない'), 'matrix evidence is not marked as excerpts');
    const timeline = () => root().querySelector('[data-interaction-timeline]');
    assert([...timeline().querySelectorAll('.qualitative-event')].map(el => el.dataset.interactionSource).join(',') === 's2,s4,s90', 'event ordering');
    const filter = timeline().querySelector('[data-interaction-filter]');
    filter.value = 'change'; filter.dispatchEvent(new Event('change', {bubbles:true}));
    assert(timeline().querySelectorAll('.qualitative-event').length === 1, 'relation filtering');
    const details = timeline().querySelector('.qualitative-evidence');
    details.open = true;
    await wait(() => details.querySelectorAll('.qualitative-quote').length === 40);
    assert(details.querySelector('[data-qualitative-evidence-id="s0"] .qualitative-exact-text').textContent === analysisState.data.segments[0].text, 'quote changed');
    assert(details.querySelector('[data-qualitative-evidence-id="s20"]').textContent.includes('集計から除外'), 'excluded context was lost');
    [...details.querySelectorAll('button')].find(button => button.textContent === '次の40発言を表示').click();
    [...details.querySelectorAll('button')].find(button => button.textContent === '次の40発言を表示').click();
    assert(details.querySelectorAll('.qualitative-quote').length === 91, 'long context missing');
    assert(details.querySelector('[data-qualitative-evidence-id="s90"]'), 'response endpoint missing');
    assert(!window.injected && !details.querySelector('img'), 'unsafe text rendering');
    assert(document.documentElement.scrollWidth <= window.innerWidth + 2, 'page horizontal overflow');
    assert(qualitativeCount(NaN) === 0 && qualitativeCount(-3) === 0, 'invalid count guard');
    const fetchBefore = apiFetch;
    try {
      const source = analysisState.data.segments[0];
      apiFetch = () => Promise.resolve(new Response(JSON.stringify({segments:[{...source, speaker:'CHANGED'}]}), {status:200}));
      await openInsightMedia(source);
      assert(document.querySelector('#analysis-message').textContent.includes('更新されています'), 'speaker-changed evidence opened');
    } finally { apiFetch = fetchBefore; analysisEvidenceReturn = null; }

    // Missing targets and stale interpretations must not acquire current evidence.
    const manual = analysisState.data.manual;
    manual.interaction_links.push({source_segment_id:'s4', target_segment_id:'deleted', relation:'agreement', relation_label:'同意', status:'missing_target'});
    renderAnalysisWorkspace();
    const missing = [...timeline().querySelectorAll('.qualitative-event')].find(el => el.textContent.includes('deleted'));
    assert(missing && !missing.querySelector('.qualitative-evidence'), 'deleted target rendered as current evidence');
    manual.preparation.analysis_needs_review = true;
    renderAnalysisWorkspace();
    assert(!timeline().querySelector('.qualitative-evidence'), 'stale links rendered with new text');
    root().querySelector('.qualitative-matrix-button').click();
    assert(root().querySelector('.qualitative-matrix-evidence').textContent.includes('要再確認'), 'stale matrix evidence');

    // Pagination is explicit; no hidden 30-link truncation.
    manual.preparation.analysis_needs_review = false;
    const sample = manual.interaction_links[0];
    manual.interaction_links = Array.from({length:31}, () => ({...sample}));
    renderAnalysisWorkspace();
    assert(timeline().querySelectorAll('.qualitative-event').length === 30, 'link page size');
    timeline().querySelector('[data-interaction-more]').click();
    assert(timeline().querySelectorAll('.qualitative-event').length === 31, 'last link unavailable');
    manual.interaction_links = [];
    renderAnalysisWorkspace();
    assert(timeline().textContent.includes('未登録'), 'empty-state instruction missing');
    document.body.dataset.visualTest = 'passed';
  } catch (error) { document.body.dataset.visualTest = 'failed: ' + error.message; }
});
'''

        def render(*args, **kwargs):
            return original_render(*args, **kwargs).replace('</body>', '<script src="/static/qualitative-driver.js" defer></script></body>')

        def static(filename):
            if filename == 'qualitative-driver.js':
                return app.app.response_class(driver, mimetype='text/javascript')
            return original_static(filename)

        server = make_server('127.0.0.1', 0, app.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(app, 'render_template', side_effect=render), patch.object(app.app, 'send_static_file', side_effect=static):
                result = subprocess.run([browser, '--headless=new', '--disable-gpu', '--disable-background-networking',
                    '--disable-extensions', '--no-first-run', '--no-default-browser-check', '--no-sandbox',
                    '--force-device-scale-factor=1', f'--window-size={size}',
                    f'--user-data-dir={self.fixture.temporary.name}/visual-browser',
                    '--virtual-time-budget=60000', '--dump-dom',
                    f'http://127.0.0.1:{server.server_port}/?view=analysis&item={self.item_id}'],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=45)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        match = re.search(r'data-visual-test="([^"]+)"', result.stdout)
        error = re.search(r'data-visual-error="([^"]+)"', result.stdout)
        self.assertIsNotNone(match, error.group(0) if error else result.stderr[-1500:])
        self.assertEqual(match.group(1), 'passed')
        self.assertIsNone(error)

    def test_desktop_counts_matrix_timeline_evidence_and_stale(self):
        self.exercise_browser('1360,900')

    def test_mobile_counts_matrix_timeline_evidence_and_stale(self):
        self.exercise_browser('390,844')


if __name__ == '__main__':
    unittest.main()
