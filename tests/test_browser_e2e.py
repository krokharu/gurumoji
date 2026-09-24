import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.serving import make_server

import app
from gurumoji.web import system_routes


def browser_executable() -> str | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    return next((str(path) for path in candidates if path and Path(path).is_file()), None)


class BrowserJobRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-browser-")
        self.root = Path(self.temporary.name)
        self.original_database = app.DATABASE_FILE
        app.DATABASE_FILE = self.root / "library.sqlite3"
        app.initialize_library()
        with app.jobs_lock:
            app.jobs.clear()
            app._job_admission_id = None

    def tearDown(self):
        with app.jobs_lock:
            app.jobs.clear()
            app._job_admission_id = None
        app.DATABASE_FILE = self.original_database
        self.temporary.cleanup()

    def test_real_browser_restores_the_active_job(self):
        browser = browser_executable()
        if browser is None:
            self.skipTest("Chrome, Edge, or Chromium is required for the browser smoke test")

        marker = "E2E_ACTIVE_JOB_RESTORED"
        job = app.JobRecord(
            id="browser-active-job",
            source_name="browser-test.wav",
            output_dir=self.root / "output",
            write_srt=False,
            write_json=True,
            status="running",
            progress=37,
            message=marker,
            logs=[marker],
            ai_usage={
                "provider": "openai", "model": "gpt-browser-test", "request_count": 2,
                "input_tokens": 1234, "output_tokens": 321, "total_tokens": 1555,
                "cached_tokens": 100, "reasoning_tokens": 25, "reported": True,
            },
        )
        with app.jobs_lock:
            app.jobs[job.id] = job

        machine = {
            "cpu": {"available": True, "name": "Test CPU", "logical_threads": 4},
            "gpu": {"cuda_available": False, "reason": "test", "vram_gib": 0},
            "memory_gib": 8,
            "recommended": {
                "model_name": "tiny",
                "device": "cpu",
                "diarization_device": "cpu",
            },
        }
        server = make_server("127.0.0.1", 0, app.app, threaded=True)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        profile = self.root / "browser-profile"
        url = f"http://127.0.0.1:{server.server_port}/"
        try:
            with (
                patch.object(app, "get_machine_profile", return_value=machine),
                patch.object(app, "load_token_config", return_value=app.TokenConfig()),
                patch.object(
                    app,
                    "system_activity_snapshot",
                    return_value={
                        "sampled_at": "2026-07-31T00:00:00+00:00",
                        "cpu": {"available": True, "utilization_percent": 42},
                        "memory": {
                            "available": True,
                            "utilization_percent": 55,
                            "used_gib": 8.8,
                            "total_gib": 16.0,
                        },
                        "gpu": {
                            "available": True,
                            "utilization_percent": 64,
                            "memory_used_gib": 4.0,
                            "memory_total_gib": 12.0,
                            "memory_percent": 33,
                        },
                        "disk": {
                            "available": True,
                            "read_active": True,
                            "write_active": True,
                            "read_mib_per_second": 1.5,
                            "write_mib_per_second": 0.5,
                        },
                    },
                ),
            ):
                completed = subprocess.run(
                    [
                        browser,
                        "--headless=new",
                        "--disable-gpu",
                        "--disable-background-networking",
                        "--disable-extensions",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--no-sandbox",
                        f"--user-data-dir={profile}",
                        "--virtual-time-budget=5000",
                        "--dump-dom",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    check=False,
                )
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)

        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        self.assertIn(marker, completed.stdout)
        self.assertIn("37%", completed.stdout)
        self.assertIn('id="progress-stage-label">文字起こし</strong>', completed.stdout)
        self.assertIn('id="progress-activity-label">RUNNING</small>', completed.stdout)
        self.assertIn('id="monitor-cpu-value">42.0%</strong>', completed.stdout)
        self.assertIn('id="monitor-gpu-value">64%</strong>', completed.stdout)
        self.assertIn('id="monitor-memory-value">55%</strong>', completed.stdout)
        self.assertRegex(completed.stdout, r'id="monitor-read-light" class="[^"]*is-active')
        self.assertRegex(completed.stdout, r'id="monitor-write-light" class="[^"]*is-active')
        self.assertIn('id="progress-ai-usage"', completed.stdout)
        self.assertIn('data-ai-total="">1,555</strong>', completed.stdout)
        self.assertIn('data-ai-provider="">OpenAI</strong>', completed.stdout)
        progress_tag = re.search(
            r'<section\b[^>]*\bid="progress-card"[^>]*>', completed.stdout
        )
        self.assertIsNotNone(progress_tag)
        self.assertNotRegex(progress_tag.group(0), r'\shidden(?:\s|=|>)')

    def test_ai_review_displays_reason_safely_and_restores_original_text(self):
        browser = browser_executable()
        if browser is None:
            self.skipTest("Chrome, Edge, or Chromium is required")
        driver = r"""
window.addEventListener('DOMContentLoaded', () => {
  try {
    setRunning(false);
    const provider = document.querySelector('#ai-provider');
    provider.value = 'openai';
    provider.dispatchEvent(new Event('change'));
    const effort = document.querySelector('input[name="ai_effort_choice_cleanup"][value="high"]');
    effort.click();
    if (readAiEfforts().cleanup !== 'high' || readAiEfforts().outline !== 'medium') throw new Error('efforts are not independent: ' + JSON.stringify(readAiEfforts()) + ' disabled=' + effort.matches(':disabled'));
    if (effort.closest('fieldset').dataset.effort !== 'high') throw new Error('effort visual did not update');
    const off = document.querySelector('input[name="ai_thinking_mode_cleanup"][value="off"]');
    off.click();
    if (readAiEfforts().cleanup !== 'off' || !effort.matches(':disabled')) throw new Error('thinking mode OFF did not disable effort');
    renderAiFinishingActivity({status: 'running', stage: 'finishing', message: 'test activity'});
    if (document.querySelector('#ai-finishing-activity').hidden) throw new Error('missing animation');
    renderAiFinishingActivity({status: 'failed', stage: 'finishing'});
    if (!document.querySelector('#ai-finishing-activity').hidden) throw new Error('animation did not stop');
    const mode = document.querySelector('#finish-in-obsidian');
    const direct = document.querySelector('[data-app-finishing-only]');
    if (!mode.checked || !direct.hidden) throw new Error('Obsidian mode is not the default');
    const advanced = document.querySelector('input[name="transcript_finishing_mode"][value="advanced"]');
    advanced.checked = true;
    advanced.dispatchEvent(new Event('change'));
    if (direct.hidden || mode.checked) throw new Error('advanced finishing mode did not become available');
    currentJob = {speaker_names: {}, speaker_profiles: {}, segments: [{
      id: 'review-test', speaker: 'A', start: 0, end: 1, text: '校正後の本文',
      ai_review: {original_text: '元の本文', noise_candidate: true, fragments: [
        {reason: '候補理由 <img src=x onerror=window.reviewInjected=1>'}
      ]},
      jev_review: {original_text: '元の本文', decision: 'correction_needed',
        correction_needed_probability: 0.88, confidence: 0.76, model: 'jev-test',
        comparison: {current_ai_flagged: true, jev_flagged: true, agreement: 'both_flagged'}}
    }]};
    setCurrentJobDirty(false);
    renderSegments();
    const panel = segmentEditor.querySelector('.segment-ai-review');
    if (!panel || !panel.textContent.includes('ノイズ候補') || !panel.textContent.includes('候補理由'))
      throw new Error('review or reason missing');
    if (panel.querySelector('img') || window.reviewInjected) throw new Error('unsafe reason rendering');
    const jevSummary = document.querySelector('#jev-comparison-summary');
    const jevPanel = segmentEditor.querySelector('.segment-jev-review');
    if (!jevSummary || jevSummary.hidden || !jevSummary.textContent.includes('判定一致 1 / 1') ||
        !jevSummary.textContent.includes('両方：修正が必要'))
      throw new Error('Jev comparison summary missing');
    if (!jevPanel || !jevPanel.textContent.includes('Jev：修正が必要') ||
        !jevPanel.textContent.includes('現行AI：修正あり'))
      throw new Error('Jev segment comparison missing');
    panel.querySelector('button').click();
    if (currentJob.segments[0].text !== '元の本文' || segmentEditor.querySelector('textarea').value !== '元の本文')
      throw new Error('restore failed');
    if (!currentJobDirty || currentJob.segments.length !== 1) throw new Error('state not preserved');
    document.body.dataset.aiReviewTest = 'passed';
  } catch (error) { document.body.dataset.aiReviewTest = 'failed: ' + error.message; }
});
"""
        original_render = system_routes.render_template
        original_static = app.app.send_static_file
        def render(*args, **kwargs):
            return original_render(*args, **kwargs).replace('</body>',
                '<script src="/static/ai-review-test.js" defer></script></body>')
        def static(filename):
            if filename == 'ai-review-test.js':
                return app.app.response_class(driver, mimetype='text/javascript')
            return original_static(filename)
        server = make_server('127.0.0.1', 0, app.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(system_routes, 'render_template', side_effect=render), \
                    patch.object(app.app, 'send_static_file', side_effect=static), \
                    patch.object(app, 'get_machine_profile', return_value={}), \
                    patch.object(app, 'load_token_config', return_value=app.TokenConfig()):
                result = subprocess.run([
                    browser, '--headless=new', '--disable-gpu', '--disable-background-networking',
                    '--disable-extensions', '--no-first-run', '--no-default-browser-check', '--no-sandbox',
                    f'--user-data-dir={self.root / "review-profile"}', '--virtual-time-budget=2000',
                    '--dump-dom', f'http://127.0.0.1:{server.server_port}/',
                ], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        status = re.search(r'data-ai-review-test="([^"]+)"', result.stdout)
        self.assertIsNotNone(status, result.stderr[-2000:])
        self.assertEqual(status.group(1), 'passed')

    def test_comparison_and_unsaved_navigation_regressions(self):
        browser = browser_executable()
        if browser is None:
            self.skipTest('Chrome, Edge, or Chromium is required')
        for item_id in ('compare_a', 'compare_b'):
            app.upsert_library_item(item_id=item_id, source_name=item_id,
                output_dir=self.root / item_id, media_path=None, language='ja',
                segments=[{'id': item_id + '_1', 'speaker': 'A', 'start': 0, 'end': 1, 'text': '同じ話題を比較する'}],
                speaker_names={'A': '参加者'}, files=[], outline=None, emotion_analysis=None,
                write_srt=False, write_json=True,
                session_profile={'session_type': 'focus_group', 'comparison_group': 'example'})
        client = app.app.test_client()
        selection = {'item_ids': ['compare_a', 'compare_b'], 'allow_different_content': False}
        compared = client.post('/api/library/interview-comparison', json=selection).get_json()
        with patch.object(app.AnalysisStore, '_publish_comparison', side_effect=app.StoreConflict('test conflict')):
            saved = client.post('/api/library/interview-comparison/runs', json={
                **selection, 'request_id': 'browser-conflict-comparison',
                'input_fingerprints': compared['input_fingerprints'],
            })
        self.assertEqual(saved.status_code, 200, saved.get_json())
        self.assertEqual(saved.get_json()['run']['vault_status'], 'conflict')
        driver = r"""
window.addEventListener('DOMContentLoaded', async () => {
  const check = (condition, message) => { if (!condition) throw Error(message); };
  const until = async condition => {
    for (let n = 0; n < 200; n++) {
      if (condition()) return;
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    throw Error('Timed out waiting for UI');
  };
  try {
    const base = document.querySelector('#interview-comparison-base');
    const run = document.querySelector('#interview-comparison-run');
    const result = document.querySelector('#interview-comparison-result');
    const history = document.querySelector('#interview-comparison-history-list');
    await until(() => !base.disabled && base.options.length === 2);
    await until(() => history.querySelector('[data-comparison-vault-retry]'));
    history.querySelector('[data-comparison-vault-retry]').click();
    await until(() => !history.querySelector('[data-comparison-vault-retry]'));
    check(history.querySelector('[data-comparison-run] summary').textContent.includes('保存済み'), 'vault retry did not refresh history');
    const target = document.querySelector('#interview-comparison-targets input:not(:disabled)');
    target.click();
    run.click();
    check(base.disabled && target.disabled && run.disabled, 'comparison selection not locked');
    check(document.querySelector('#interview-comparison-allow-different').disabled, 'comparison mode not locked');
    await until(() => !result.hidden);
    result.querySelector('button').click();
    await until(() => result.querySelector('.interview-comparison-save-status').textContent.includes('保存しました'));
    await until(() => history.querySelector('[data-comparison-run]'));
    const saved = history.querySelector('[data-comparison-run]');
    saved.open = true;
    check(saved.querySelector('a[href^="/api/analysis/artifacts/"]'), 'saved comparison artifact link missing');
    document.querySelector('#interview-comparison-history-refresh').click();
    await until(() => document.querySelector('#interview-comparison-history-status').textContent.includes('1件'));

    const originalConfirm = window.confirm;
    const originalLoad = loadAnalysisItem;
    let confirms = 0, loads = 0;
    window.confirm = () => { confirms++; return false; };
    loadAnalysisItem = () => { loads++; };
    analysisState.itemId = 'compare_a';
    analysisState.dirty = false;
    preparationDirty = true;
    analysisCard.hidden = false;
    currentJobDirty = false;
    document.querySelector('#analysis-refresh-button').click();
    check(confirms === 1 && loads === 0 && preparationDirty, 'preparation refresh discarded edits');
    analysisState.dirty = true;
    check(showView('analysis', {analysisItemId: 'compare_b'}) === false, 'analysis navigation bypassed confirmation');
    check(loads === 0 && analysisState.itemId === 'compare_a', 'cancelled navigation changed target');
    window.confirm = originalConfirm;
    loadAnalysisItem = originalLoad;
    analysisState.dirty = false;
    preparationDirty = false;

    const originalFetch = apiFetch, originalRender = renderResult;
    const pending = {}, rendered = [];
    apiFetch = url => new Promise(resolve => { pending[url] = resolve; });
    renderResult = data => rendered.push(data.id);
    const a = openLibraryItem('A'), b = openLibraryItem('B');
    const reply = id => new Response(JSON.stringify({id}), {headers: {'Content-Type':'application/json'}});
    pending['/api/library/B'](reply('B')); await b;
    pending['/api/library/A'](reply('A')); await a;
    check(rendered.join(',') === 'B', 'late response replaced selected result');
    const c = openLibraryItem('C');
    showView('new');
    pending['/api/library/C'](reply('C')); await c;
    check(rendered.join(',') === 'B', 'late response replaced a different view');
    apiFetch = originalFetch; renderResult = originalRender;
    document.body.dataset.priorityFixes = 'passed';
  } catch (error) {
    document.body.dataset.priorityFixes = error.message;
  }
});
"""
        original_render = system_routes.render_template
        original_static = app.app.send_static_file
        def render(*args, **kwargs):
            return original_render(*args, **kwargs).replace('</body>',
                '<script src="/static/priority-fixes-test.js" defer></script></body>')
        def static(filename):
            if filename == 'priority-fixes-test.js':
                return app.app.response_class(driver, mimetype='text/javascript')
            return original_static(filename)
        server = make_server('127.0.0.1', 0, app.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(system_routes, 'render_template', side_effect=render), \
                    patch.object(app.app, 'send_static_file', side_effect=static), \
                    patch.object(app, 'get_machine_profile', return_value={}), \
                    patch.object(app, 'system_activity_snapshot', return_value={}), \
                    patch.object(app, 'load_token_config', return_value=app.TokenConfig()):
                result = subprocess.run([
                    browser, '--headless=new', '--disable-gpu', '--disable-background-networking',
                    '--disable-extensions', '--no-first-run', '--no-default-browser-check', '--no-sandbox',
                    f'--user-data-dir={self.root / "priority-profile"}', '--virtual-time-budget=10000',
                    '--dump-dom', f'http://127.0.0.1:{server.server_port}/',
                ], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=40)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        status = re.search(r'data-priority-fixes="([^"]+)"', result.stdout)
        self.assertIsNotNone(status, result.stderr[-2000:])
        self.assertEqual(status.group(1), 'passed')
        self.assertEqual(len(app.analysis_archive_store().list_comparisons()), 1)

    def test_real_browser_renders_pre_survey_dashboard(self):
        browser = browser_executable()
        if browser is None:
            self.skipTest("Chrome, Edge, or Chromium is required for the browser smoke test")

        app.save_speaker_registry_records(
            [
                {
                    "id": "survey_a",
                    "participant_code": "P-01",
                    "pseudonym": "参加者A",
                    "attributes": {"満足度": "5", "年齢層": "30代", "利用歴": "3年以上"},
                    "active": True,
                },
                {
                    "id": "survey_b",
                    "participant_code": "P-02",
                    "pseudonym": "参加者B",
                    "attributes": {"満足度": "3", "年齢層": "40代", "利用歴": "1年未満"},
                    "active": True,
                },
                {
                    "id": "survey_c",
                    "participant_code": "P-03",
                    "pseudonym": "参加者C",
                    "attributes": {"満足度": "4", "年齢層": "30代", "利用歴": "1年未満"},
                    "active": True,
                },
            ],
            expected_revision=0,
        )
        machine = {
            "cpu": {"available": True, "name": "Test CPU", "logical_threads": 4},
            "gpu": {"cuda_available": False, "reason": "test", "vram_gib": 0},
            "memory_gib": 8,
            "recommended": {
                "model_name": "tiny",
                "device": "cpu",
                "diarization_device": "cpu",
            },
        }
        server = make_server("127.0.0.1", 0, app.app, threaded=True)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        profile = self.root / "survey-browser-profile"
        url = f"http://127.0.0.1:{server.server_port}/?view=speakers"
        try:
            with (
                patch.object(app, "get_machine_profile", return_value=machine),
                patch.object(app, "load_token_config", return_value=app.TokenConfig()),
            ):
                completed = subprocess.run(
                    [
                        browser,
                        "--headless=new",
                        "--disable-gpu",
                        "--disable-background-networking",
                        "--disable-extensions",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--no-sandbox",
                        f"--user-data-dir={profile}",
                        "--virtual-time-budget=7000",
                        "--dump-dom",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    check=False,
                )
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)

        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        self.assertIn('id="registry-survey-metric">3</strong>', completed.stdout)
        self.assertIn('class="speaker-survey-overview"', completed.stdout)
        self.assertIn('class="speaker-survey-bars"', completed.stdout)
        self.assertIn(
            'class="speaker-survey-panel speaker-survey-crosstab"',
            completed.stdout,
        )
        self.assertIn('class="speaker-survey-table participant"', completed.stdout)
        self.assertIn("満足度", completed.stdout)
        self.assertIn("年齢層", completed.stdout)

    def test_registered_ui_ux_fixes_work_in_a_real_browser(self):
        browser = browser_executable()
        if browser is None:
            self.skipTest('Chrome, Edge, or Chromium is required')
        driver = r"""
window.addEventListener('DOMContentLoaded', async () => {
  const checks = [];
  const pause = ms => new Promise(resolve => window.setTimeout(resolve, ms));
  const expect = (name, value, detail = '') => {
    if (!value) throw new Error(name + (detail ? ': ' + detail : ''));
    checks.push(name);
  };
  const waitFor = async (predicate, name) => {
    for (let i = 0; i < 60; i += 1) { if (predicate()) return; await pause(50); }
    throw new Error('timeout: ' + name);
  };
  try {
    const mobile = window.innerWidth <= 540;
    const byId = id => document.getElementById(id);

    // UX-14: a hand-edited value survives a mode switch; reset restores the preset.
    const maxSpeakers = document.querySelector('[name="max_speakers"]');
    const minSpeakers = document.querySelector('[name="min_speakers"]');
    setRunning(false);
    expect('UX-14 meeting preset applied', maxSpeakers.value === '10', maxSpeakers.value);
    maxSpeakers.value = '5';
    maxSpeakers.dispatchEvent(new Event('input', {bubbles: true}));
    const groupMode = document.querySelector('input[name="conversation_mode"][value="group_interview"]');
    groupMode.click();
    expect('UX-14 unedited field follows new mode', minSpeakers.value === '3',
      `min=${minSpeakers.value} checked=${groupMode.checked} disabled=${groupMode.matches(':disabled')}`);
    expect('UX-14 edited field kept', maxSpeakers.value === '5', maxSpeakers.value);
    expect('UX-14 hint names kept field', byId('conversation-mode-hint').textContent.includes('最多話者数'));
    const reset = byId('conversation-mode-reset');
    expect('UX-14 reset offered', !reset.hidden);
    reset.click();
    expect('UX-14 reset restores preset', maxSpeakers.value === '12' && reset.hidden, maxSpeakers.value);

    // UX-12: cancelling asks first; declining sends nothing.
    const cancelCalls = [];
    const realFetch = window.fetch;
    window.fetch = (input, options) => {
      if (String(input).includes('/cancel')) {
        cancelCalls.push(String(input));
        return Promise.resolve(new Response('{"ok": true}', {status: 200, headers: {'Content-Type': 'application/json'}}));
      }
      return realFetch(input, options);
    };
    const realConfirm = window.confirm;
    let confirmAnswer = false;
    let confirmCount = 0;
    window.confirm = () => { confirmCount += 1; return confirmAnswer; };
    activeJobId = 'ux-cancel-job';
    cancelButton.disabled = false;
    cancelButton.click();
    await pause(50);
    expect('UX-12 declined cancel sends no request', confirmCount === 1 && cancelCalls.length === 0);
    confirmAnswer = true;
    activeJobId = 'ux-cancel-job';
    cancelButton.disabled = false;
    cancelButton.click();
    await pause(50);
    expect('UX-12 confirmed cancel sends request', confirmCount === 2 && cancelCalls.length === 1,
      `confirms=${confirmCount} calls=${cancelCalls.join()} job=${activeJobId}`);
    window.fetch = realFetch;
    window.confirm = realConfirm;
    activeJobId = null;

    // UX-23: one Tab stop per tablist; arrows, Home and End move focus.
    const tabs = ['show-new-button', 'show-library-button', 'show-speakers-button'].map(byId);
    const key = name => document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: name, bubbles: true}));
    expect('UX-23 roving tabindex', tabs.map(tab => tab.getAttribute('tabindex')).join() === '0,-1,-1',
      tabs.map(tab => tab.getAttribute('tabindex')).join());
    tabs[0].focus();
    key('ArrowRight');
    expect('UX-23 ArrowRight', document.activeElement === tabs[1], document.activeElement.id);
    key('End');
    expect('UX-23 End', document.activeElement === tabs[2], document.activeElement.id);
    key('Home');
    expect('UX-23 Home', document.activeElement === tabs[0], document.activeElement.id);
    key('ArrowLeft');
    expect('UX-23 ArrowLeft wraps', document.activeElement === tabs[2], document.activeElement.id);
    expect('UX-23 arrows do not switch view', !byId('create-view').hidden);
    showView('speakers');
    await pause(0);
    expect('UX-23 Tab stop follows selection', tabs[2].getAttribute('tabindex') === '0' && tabs[0].getAttribute('tabindex') === '-1');
    expect('UX-01 route follows the screen', window.location.hash === '#/speakers', window.location.hash);
    showView('new');
    await pause(0);
    expect('UX-01 route returns to create', window.location.hash === '#/new', window.location.hash);
    showView('library');
    await pause(0);
    expect('processed data hub opens on list', !byId('processed-data-hub').hidden
      && byId('show-library-list-button').getAttribute('aria-selected') === 'true');
    byId('show-library-analysis-button').click();
    await pause(0);
    expect('analysis has a separate top-level destination', window.location.hash === '#/analysis'
      && byId('show-analysis-button').getAttribute('aria-selected') === 'true'
      && byId('show-library-button').getAttribute('aria-selected') === 'false'
      && byId('show-library-analysis-button').getAttribute('aria-selected') === 'true');
    showView('new');
    await pause(0);

    // UX-24 / UX-17: inspect the loaded stylesheet itself.
    const sheet = [...document.styleSheets].find(item => item.href && item.href.includes('style.css'));
    const rules = [];
    const walk = list => [...list].forEach(rule => { rules.push(rule); if (rule.cssRules) walk(rule.cssRules); });
    walk(sheet.cssRules);
    expect('UX-24 focus ring is a top-level rule', rules.some(rule => rule.parentRule === null
      && String(rule.selectorText || '').includes(':focus-visible') && String(rule.selectorText || '').includes(':is(')));
    const probe = document.createElement('label');
    probe.className = 'field';
    probe.innerHTML = '<input type="text">';
    document.body.append(probe);
    probe.querySelector('input').focus();
    if (probe.querySelector('input').matches(':focus-visible')) {
      expect('UX-24 outline on .field input', getComputedStyle(probe.querySelector('input')).outlineStyle === 'solid');
    }
    probe.remove();
    const tiny = rules.filter(rule => rule.style && /rem$/.test(rule.style.fontSize) && parseFloat(rule.style.fontSize) < 0.7)
      .map(rule => rule.selectorText + ' ' + rule.style.fontSize);
    expect('UX-17 no font size below .7rem', tiny.length === 0, tiny.slice(0, 3).join(' | '));
    expect('UX-17 token resolves', getComputedStyle(document.documentElement).getPropertyValue('--text-min').trim() === '.7rem');
    const smallest = [...document.querySelectorAll('body *')].filter(el => el.getClientRects().length && el.textContent.trim())
      .reduce((min, el) => Math.min(min, parseFloat(getComputedStyle(el).fontSize)), 99);
    expect('UX-17 smallest visible text >= 11px', smallest >= 11, String(smallest));

    // UX-11: delete sits outside the sticky bar; the phone bar keeps two buttons.
    const deleteButton = byId('delete-record-button');
    expect('UX-11 delete outside sticky bar', !deleteButton.closest('.sticky-actions') && !!deleteButton.closest('.result-danger-zone'));
    if (mobile) {
      const sticky = document.querySelector('.sticky-actions');
      const shown = [...sticky.children].filter(button => getComputedStyle(button).display !== 'none');
      expect('UX-11 phone sticky bar has two buttons', getComputedStyle(sticky).display === 'grid' && shown.length === 2,
        shown.map(button => button.id).join());
    }

    // UX-10: the connection dialog shows token status at every width and opens the model flow.
    await waitFor(() => !document.querySelector('[data-status-provider="openai"]').classList.contains('loading'), 'config');
    const dialogPill = document.querySelector('[data-status-provider="openai"]');
    expect('UX-10 dialog pill mirrors header pill', dialogPill.className === byId('status-openai').className, dialogPill.className);
    expect('UX-10 dialog closed until asked', dialogPill.getBoundingClientRect().width === 0);
    byId('connection-button').click();
    await pause(50);
    expect('UX-10 dialog opens', byId('connection-dialog').open && dialogPill.getBoundingClientRect().width > 0);
    let alerted = '';
    const realAlert = window.alert;
    window.alert = message => { alerted = String(message); };
    byId('connection-dialog').querySelector('[data-model-provider="openai"]').click();
    await pause(50);
    window.alert = realAlert;
    expect('UX-10 model flow opens from the dialog', alerted.includes('OpenAI') || aiModelDialog.open, alerted);
    if (aiModelDialog.open) aiModelDialog.close();
    byId('connection-dialog').close();
    if (mobile) {
      expect('UX-10 header pills hidden on phones', byId('status-openai').getBoundingClientRect().width === 0);
    } else {
      expect('UX-10 header pills visible on desktop', byId('status-openai').getBoundingClientRect().width > 0);
    }
    expect('UX-09 no horizontal overflow', document.documentElement.scrollWidth <= window.innerWidth + 2,
      String(document.documentElement.scrollWidth));

    // All detailed settings start closed; the summary opens only the requested panel.
    const panels = [...document.querySelectorAll('[data-settings-panel]')];
    expect('all settings closed by default', panels.length === 5 && panels.every(panel => !panel.open));
    document.querySelector('[data-open-panel="finishing"]').click();
    await pause(400);
    expect('summary row opens requested panel', byId('panel-finishing').open && !byId('panel-recognition').open);
    byId('panel-finishing').open = false;

    // UX-06 / UX-07: the main task is placed first.
    const follows = (first, second) => Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING);
    expect('UX-06 comparison after analysis', follows(byId('analysis-shell'), byId('interview-comparison-card'))
      && !byId('interview-comparison-details').open);
    expect('UX-07 survey after table', follows(document.querySelector('.spreadsheet-shell'), byId('speaker-survey-analysis')));

    // UX-08: the splash shows once per session and is skipped afterwards.
    expect('UX-08 session flag stored', window.sessionStorage.getItem('gurumoji.bootSplashSeen') === '1');
    await waitFor(() => bootSplash.hidden, 'first splash');
    bootSplash.hidden = false;
    document.body.classList.add('booting');
    startBootSequence();
    expect('UX-08 repeat visit skips splash', bootSplash.hidden && !document.body.classList.contains('booting')
      && document.body.classList.contains('boot-skipped'));

    document.body.dataset.uxFixesTest = 'passed';
  } catch (error) {
    document.body.dataset.uxFixesTest = 'failed: ' + error.message;
  }
  document.body.dataset.uxFixesChecks = String(checks.length);
});
"""
        original_render = system_routes.render_template
        original_static = app.app.send_static_file

        def render(*args, **kwargs):
            return original_render(*args, **kwargs).replace(
                '</body>', '<script src="/static/ux-fixes-test.js" defer></script></body>')

        def static(filename):
            if filename == 'ux-fixes-test.js':
                return app.app.response_class(driver, mimetype='text/javascript')
            return original_static(filename)

        for width, expected_checks in (("1440,1000", 33), ("390,844", 33)):
            with self.subTest(window=width):
                server = make_server('127.0.0.1', 0, app.app, threaded=True)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    with patch.object(system_routes, 'render_template', side_effect=render), \
                            patch.object(app.app, 'send_static_file', side_effect=static), \
                            patch.object(app, 'get_machine_profile', return_value={}), \
                            patch.object(app, 'load_token_config', return_value=app.TokenConfig()):
                        result = subprocess.run([
                            browser, '--headless=new', '--disable-gpu', '--disable-background-networking',
                            '--disable-extensions', '--no-first-run', '--no-default-browser-check', '--no-sandbox',
                            f'--window-size={width}', f'--user-data-dir={self.root / ("ux-profile-" + width.split(",")[0])}',
                            '--virtual-time-budget=10000', '--dump-dom', f'http://127.0.0.1:{server.server_port}/',
                        ], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr[-2000:])
                status = re.search(r'data-ux-fixes-test="([^"]+)"', result.stdout)
                self.assertIsNotNone(status, result.stderr[-2000:])
                self.assertEqual(status.group(1), 'passed')
                checks = re.search(r'data-ux-fixes-checks="(\d+)"', result.stdout)
                self.assertGreaterEqual(int(checks.group(1)), expected_checks - 1)


if __name__ == "__main__":
    unittest.main()
