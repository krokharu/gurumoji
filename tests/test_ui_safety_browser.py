"""Opt-in actual-browser regressions with mocked network and synthetic data only.

Windows/local executor:
  set GURUMOJI_RUN_UI_BROWSER=1
  set PYTHONPATH=src;tests
  python -m unittest test_ui_safety_browser -v

No server, models, external APIs, real recordings or credentials are used.
The browser sandbox remains enabled. Not run in the restricted cloud workspace.
"""
import copy
from contextlib import ExitStack
import json
import mimetypes
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse

import app
from support import use_temporary_library
import browser_support

JOB = {
    'id': 'ui_synthetic_job', 'source_name': 'Synthetic UI', 'revision_count': 1,
    'status': 'completed', 'files': [], 'media_url': '',
    'speaker_names': {'SPEAKER_00': 'Synthetic A'}, 'speaker_profiles': {},
    'session_profile': {}, 'segments': [
        {'id': 's1', 'start': 0, 'end': 2, 'speaker': 'SPEAKER_00', 'text': 'Synthetic one', 'emotions': {}},
        {'id': 's2', 'start': 3, 'end': 5, 'speaker': 'SPEAKER_00', 'text': 'Synthetic two', 'emotions': {'synthetic': {'label': 'sample'}}},
    ],
}
CONFIG = {
    'ok': True, 'huggingface': True, 'typesafe': True, 'lmstudio': True,
    'lmstudio_model': 'synthetic-local', 'typesafe_model': 'synthetic-jev',
    'machine': {'cpu': {'available': True}, 'gpu': {'cuda_available': False},
                'recommended': {'model_name': 'tiny', 'device': 'cpu', 'diarization_device': 'cpu'}},
    'runtime': {'browser_upload': True, 'kind': 'cloud'},
    'transcription_readiness': {'whisperx': {'blockers': [], 'notes': [], 'models': {'cpu': {'tiny': {'status': 'cached', 'message': 'synthetic cache'}}}},
                                'qwen3_nemotron': {'blockers': ['Synthetic missing backend'], 'notes': []}},
}


@browser_support.ui_browser_test
class UiSafetyBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cleanup = ExitStack()
        cls.addClassCleanup(cleanup.close)
        cls.browser = cleanup.enter_context(browser_support.sandboxed_playwright_browser())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gurumoji-ui-browser-')
        self.addCleanup(self.temp.cleanup)
        use_temporary_library(self, Path(self.temp.name))
        self.html = app.app.test_client().get('/').get_data(as_text=True)
        self.config = copy.deepcopy(CONFIG)
        self.job = copy.deepcopy(JOB)
        self.puts = []
        self.delete_status = 500
        self.save_status = 200
        self.imports = 0
        self.errors = []
        self.context = self.browser.new_context(accept_downloads=True, viewport={'width': 1440, 'height': 900})
        self.addCleanup(self.context.close)
        self.context.route('**/*', self.route)
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.add_init_script("sessionStorage.setItem('gurumoji.bootSplashSeen','1')")
        self.page.goto('http://gurumoji.test/')
        self.page.wait_for_function("typeof renderResult === 'function' && configLoadState === 'loaded'")

    def route(self, route):
        request = route.request
        url = urlparse(request.url)
        if url.hostname != 'gurumoji.test':
            route.abort(); return
        path = url.path
        if path == '/':
            route.fulfill(status=200, content_type='text/html', body=self.html); return
        if path.startswith('/static/'):
            file = app.APP_DIRECTORY / path.lstrip('/')
            if file.is_file():
                route.fulfill(status=200, content_type=mimetypes.guess_type(file)[0] or 'application/octet-stream', body=file.read_bytes())
            else: route.fulfill(status=404, body='')
            return
        status = 200
        data = {}
        if path == '/api/config': data = self.config
        elif path == '/api/jobs/active': data = {'job': None}
        elif path == '/api/speakers/import':
            self.imports += 1
            self.assertIn('name="preview"', request.post_data or '')
            data = {'preview': True, 'registry_revision': 0, 'imported_count': 1,
                    'summary': {'added': 1, 'updated': 0, 'columns': [{'column': 'Synthetic question', 'field': 'attributes'}]},
                    'speakers': [{'id': 'speaker_csv_test', 'display_name': 'Synthetic CSV', 'participant_code': 'P1', 'attributes': {'Synthetic question': 'yes'}, 'tags': [], 'active': True}]}
        elif path == '/api/speakers':
            if request.method == 'PUT':
                self.puts.append(request.post_data_json)
                data = {'speakers': request.post_data_json['speakers'], 'registry_revision': 1}
            else: data = {'speakers': [], 'registry_revision': 0}
        elif path == '/api/library/ui_synthetic_job':
            if request.method == 'DELETE': status=self.delete_status; data={'error':'Synthetic delete failure'}
            elif request.method == 'PUT':
                self.puts.append(request.post_data_json)
                status=self.save_status
                if status == 409: data={'error':'Synthetic conflict','current_revision':2}
                else:
                    self.job.update(request.post_data_json); self.job['revision_count'] += 1; data=self.job
            else: data = self.job
        elif path == '/api/library': data={'items': [], 'total':0, 'groups':[]}
        elif path == '/api/custom-vocabulary': data={'terms':[]}
        route.fulfill(status=status, content_type='application/json', body=json.dumps(data))

    def show_result(self, width=1440):
        self.page.set_viewport_size({'width':width,'height':844 if width<960 else 900})
        self.page.evaluate('(job) => renderResult(job)', self.job)
        self.page.locator('#result-card').wait_for(state='visible')

    def assert_no_script_error(self):
        self.assertEqual(self.errors, [])

    def test_autonomous_defaults_minimum_three_and_optional_caps(self):
        self.page.evaluate("""Object.assign(analysisState, {
            itemId:'synthetic-analysis', data:{item:{id:'synthetic-analysis',source_name:'Synthetic',
            revision_count:1,analysis_revision:1},segments:[]}, config:{},annotations:{},dirty:false});
            analysisCard.hidden=false;document.body.dataset.view='analysis';""")
        self.page.locator('.analysis-more-actions > summary').click()
        self.page.locator('#analysis-run-settings-button').click()
        self.page.locator('#orchestration-open').click()
        self.page.locator('#orchestration-question').fill('Synthetic evidence review')
        self.assertTrue(self.page.locator('input[name=orchestration_stop][value=auto]').is_checked())
        self.assertIn('最低3回', self.page.locator('#orchestration-stop-explanation').inner_text())
        payload = self.page.evaluate('orchestrationPayload()')
        self.assertEqual(payload['stop_mode'], 'auto')
        self.assertIsNone(payload['max_iterations'])
        self.assertIsNone(payload['time_limit_seconds'])
        self.page.locator('#orchestration-iterations').fill('2')
        self.page.locator('#orchestration-start').click()
        self.assertIn('最低3回', self.page.locator('#orchestration-settings-message').inner_text())
        self.assertTrue(self.page.locator('#orchestration-settings').is_visible())
        self.page.locator('#orchestration-iterations').fill('')
        self.page.locator('input[name=orchestration_stop][value=iterations]').check()
        self.page.locator('#orchestration-iterations').fill('1')
        self.assertEqual(self.page.evaluate('orchestrationPayload().max_iterations'), 1)
        self.assert_no_script_error()

    def test_keyboard_edit_save_reload_desktop_and_mobile(self):
        for width in (1440, 390):
            self.show_result(width)
            self.page.evaluate('document.activeElement.blur()')
            for _ in range(100):
                self.page.keyboard.press('Tab')
                if self.page.evaluate("document.activeElement === document.querySelectorAll('.segment-edit')[1]"): break
            self.assertTrue(self.page.evaluate("document.activeElement === document.querySelectorAll('.segment-edit')[1]"))
            self.page.keyboard.press('Enter')
            self.assertTrue(self.page.evaluate("document.activeElement === document.querySelector('[data-segment-id=s2] textarea')"))
            self.page.keyboard.type(' changed')
            self.page.locator('#save-button').click()
            self.page.wait_for_function('!currentJobDirty')
            self.assertIn('changed', self.puts[-1]['segments'][1]['text'])
            self.page.evaluate("openLibraryItem('ui_synthetic_job')")
            self.page.locator('[data-segment-id=s2] .segment-edit').click()
            self.assertIn('changed', self.page.locator('[data-segment-id=s2] textarea').input_value())
        self.assert_no_script_error()

    def test_delete_undo_preserves_another_edit(self):
        self.show_result()
        self.page.locator('[data-segment-id=s1] .segment-edit').click()
        self.page.locator('[data-segment-id=s1] textarea').fill('Changed first')
        self.page.locator('[data-segment-id=s2] .segment-edit').click()
        self.page.locator('[data-segment-id=s2] .segment-delete').click()
        self.assertEqual(self.page.locator('.segment').count(),1)
        self.page.locator('#undo-segment-delete').click()
        segments=self.page.evaluate('currentJob.segments')
        self.assertEqual(segments[0]['text'],'Changed first')
        self.assertEqual(segments[1],JOB['segments'][1])
        self.assertTrue(self.page.evaluate("document.activeElement.dataset.segmentField === 'text'"))
        self.assert_no_script_error()

    def test_config_missing_and_destinations_mobile(self):
        self.page.set_viewport_size({'width':390,'height':844})
        self.page.locator('#input-file').set_input_files({'name':'synthetic.wav','mimeType':'audio/wav','buffer':b'RIFFsynthetic'})
        self.config['huggingface']=False
        self.page.evaluate('loadConfig()')
        self.page.wait_for_function('!tokenConfigSnapshot.huggingface')
        self.page.evaluate('setMobileStep(3)')
        self.assertTrue(self.page.locator('#start-button').is_disabled())
        self.assertIn('Hugging Face',self.page.locator('#setup-readiness-details').inner_text())
        self.page.evaluate("aiProvider.value='lmstudio'; transcriptFinishingModeInputs.forEach(i=>i.checked=i.value==='advanced'); applyTranscriptFinishingPreset(); syncAiFields(); updateCreateSummary()")
        self.assertFalse(self.page.locator('#jev-compare').is_checked())
        self.page.evaluate('jevCompare.checked=true; updateCreateSummary()')
        self.assertIn('TypeSafe',self.page.locator('[data-text-destinations]').inner_text())
        self.page.evaluate('jevCompare.checked=false; updateCreateSummary()')
        self.assertNotIn('TypeSafe',self.page.locator('[data-text-destinations]').inner_text())
        self.assert_no_script_error()

    def test_late_diagnostics_preserve_manual_model_and_explicit_reset(self):
        self.page.evaluate("openSettingsPanel('recognition')")
        self.page.locator('#model-name').select_option('base')
        recommendation = copy.deepcopy(CONFIG['machine'])
        recommendation['recommended']['model_name'] = 'small'
        self.page.evaluate('(machine) => applyMachineProfile(machine)', recommendation)
        self.page.evaluate('(machine) => applyMachineProfile(machine)', recommendation)
        self.assertEqual(self.page.locator('#model-name').input_value(), 'base')
        self.page.locator('#machine-reset-button').click()
        self.assertEqual(self.page.locator('#model-name').input_value(), 'small')
        self.assert_no_script_error()

    def test_conflict_download_is_unsaved_and_does_not_overwrite(self):
        self.show_result(); self.save_status=409
        self.page.locator('[data-segment-id=s1] .segment-edit').click()
        self.page.locator('[data-segment-id=s1] textarea').fill('Unsaved edit')
        self.page.locator('#save-button').click()
        self.page.locator('#result-draft-recovery').wait_for(state='visible')
        self.assertEqual(self.page.locator('#save-message').get_attribute('role'),'alert')
        with self.page.expect_download() as download:
            self.page.locator('#export-result-draft').click()
        data=json.loads(Path(download.value.path()).read_text())
        self.assertEqual(data['base_revision'],1)
        self.assertEqual(data['draft']['segments'][0]['text'],'Unsaved edit')
        self.assertEqual(len(self.puts),1)
        self.assertEqual(self.job['segments'][0]['text'],'Synthetic one')
        self.assert_no_script_error()

    def test_delete_failure_stays_visible(self):
        self.show_result()
        self.page.on('dialog',lambda dialog:dialog.accept())
        self.page.locator('#item-tab-files').click()
        self.page.locator('#delete-record-button').click()
        self.page.locator('#save-message').wait_for(state='visible')
        self.page.wait_for_function("document.querySelector('#save-message').textContent.includes('Synthetic delete failure')")
        self.assertTrue(self.page.locator('#result-card').is_visible())
        self.assertEqual(self.page.locator('#save-message').get_attribute('role'),'alert')
        self.assertFalse(self.page.locator('#delete-record-button').is_disabled())
        self.assert_no_script_error()

    def test_csv_preview_cancel_apply_and_explicit_save(self):
        self.page.locator('#show-speakers-button').click()
        self.page.wait_for_function('speakerRegistryLoaded')
        upload={'name':'synthetic.csv','mimeType':'text/csv','buffer':b'participant_code,name\nP1,Synthetic CSV\n'}
        self.page.locator('#speaker-csv-input').set_input_files(upload)
        self.page.locator('#speaker-import-preview').wait_for(state='visible')
        self.assertEqual(self.puts,[])
        self.page.locator('#cancel-speaker-import').click()
        self.assertEqual(self.page.evaluate('speakerRegistry.length'),0)
        self.page.locator('#speaker-csv-input').set_input_files(upload)
        self.page.locator('#apply-speaker-import').click()
        self.assertEqual(self.puts,[])
        self.assertTrue(self.page.evaluate('speakerRegistryDirty'))
        self.page.locator('#save-speakers-button').click()
        self.page.wait_for_function('!speakerRegistryDirty')
        self.assertEqual(len(self.puts),1)
        self.assertEqual(self.puts[0]['speakers'][0]['participant_code'],'P1')
        self.assert_no_script_error()
