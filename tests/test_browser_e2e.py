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
    mode.checked = false;
    mode.dispatchEvent(new Event('change'));
    if (direct.hidden) throw new Error('direct finishing mode did not become available');
    mode.checked = true;
    mode.dispatchEvent(new Event('change'));
    currentJob = {speaker_names: {}, speaker_profiles: {}, segments: [{
      id: 'review-test', speaker: 'A', start: 0, end: 1, text: '校正後の本文',
      ai_review: {original_text: '元の本文', noise_candidate: true, fragments: [
        {reason: '候補理由 <img src=x onerror=window.reviewInjected=1>'}
      ]}
    }]};
    setCurrentJobDirty(false);
    renderSegments();
    const panel = segmentEditor.querySelector('.segment-ai-review');
    if (!panel || !panel.textContent.includes('ノイズ候補') || !panel.textContent.includes('候補理由'))
      throw new Error('review or reason missing');
    if (panel.querySelector('img') || window.reviewInjected) throw new Error('unsafe reason rendering');
    panel.querySelector('button').click();
    if (currentJob.segments[0].text !== '元の本文' || segmentEditor.querySelector('textarea').value !== '元の本文')
      throw new Error('restore failed');
    if (!currentJobDirty || currentJob.segments.length !== 1) throw new Error('state not preserved');
    document.body.dataset.aiReviewTest = 'passed';
  } catch (error) { document.body.dataset.aiReviewTest = 'failed: ' + error.message; }
});
"""
        original_render = app.render_template
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
            with patch.object(app, 'render_template', side_effect=render), \
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
    await until(() => !base.disabled && base.options.length === 2);
    const target = document.querySelector('#interview-comparison-targets input:not(:disabled)');
    target.click();
    run.click();
    check(base.disabled && target.disabled && run.disabled, 'comparison selection not locked');
    check(document.querySelector('#interview-comparison-allow-different').disabled, 'comparison mode not locked');
    await until(() => !result.hidden);
    result.querySelector('button').click();
    await until(() => result.querySelector('.interview-comparison-save-status').textContent.includes('保存しました'));

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
        original_render = app.render_template
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
            with patch.object(app, 'render_template', side_effect=render), \
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


if __name__ == "__main__":
    unittest.main()
