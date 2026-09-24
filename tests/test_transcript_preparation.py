import csv
import io
import json
import unittest
import re
import subprocess
import threading
from unittest.mock import patch

import app
from gurumoji.web import system_routes
import test_analysis as fixtures
import test_browser_e2e as browser_support
from gurumoji import transcript_preparation as preparation


class TranscriptPreparationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.AnalysisApiTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.client = self.fixture.client
        self.item_id = self.fixture.item_id
        for target in ('publish_input_vault', 'refresh_archive_index'):
            mock = patch.object(app, target)
            mock.start()
            self.addCleanup(mock.stop)

    def analysis(self, item_id=None):
        response = self.client.get(f'/api/library/{item_id or self.item_id}/analysis')
        self.assertEqual(response.status_code, 200, response.data[:300])
        return response.get_json()

    def payload(self):
        p = self.analysis()['manual']['preparation']
        return {'revision': p['revision'], 'source_hash': p['source_hash'], 'records': {
            row['segment_id']: {'text_status': 'transcript_checked', 'boundary_verified': True,
                'speaker_verified': True, 'role': 'moderator' if row['speaker_id'] == 'MODERATOR' else 'participant',
                'source_segment_ids': [row['segment_id']], 'source_locator': ''}
            for row in p['rows']}, 'order_verified': True}

    def save(self, payload):
        return self.client.put(f'/api/library/{self.item_id}/preparation', json=payload)

    def rewrite(self, change):
        row = app.library_row(self.item_id)
        segments = app.row_segments(row)
        change(segments)
        app.upsert_library_item(item_id=self.item_id, source_name=row['source_name'],
            output_dir=app.Path(row['output_dir']), media_path=None, language='ja', segments=segments,
            speaker_names=json.loads(row['speaker_names_json']), outline=None, emotion_analysis=None,
            files=[], write_srt=False, write_json=True, increment_revision=True,
            speaker_profiles=json.loads(row['speaker_profiles_json']), session_profile=json.loads(row['session_profile_json']))

    def test_unknown_metadata_stays_unknown(self):
        self.fixture.create_analysis_item('unknown_prep', [{'id': 'u', 'text': 'data only'}])
        result = self.analysis('unknown_prep')
        p = result['manual']['preparation']
        self.assertIsNone(p['participant_count'])
        self.assertEqual(p['known_speaker_count'], 0)
        self.assertEqual(p['unknown_speaker_turns'], 1)
        self.assertIsNone(p['rows'][0]['start'])
        self.assertIsNone(p['rows'][0]['speaker_id'])
        self.assertEqual(p['rows'][0]['role'], 'unknown')
        self.assertEqual(p['interaction_ready_count'], 0)
        inventory = {r['item']: r['status'] for r in result['manual']['focus_group_plan']['data_inventory']}
        self.assertEqual(inventory['時刻または元ファイル内の位置'], '不明')
        self.assertEqual(inventory['このレコードの参加者数'], '不明')

    def test_confirm_and_stale_on_edit_preserve_all_versions(self):
        payload = self.payload()
        result = self.save({**payload, 'confirm': True})
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.get_json()['status'], 'confirmed')
        self.assertEqual(result.get_json()['interaction_ready_count'], len(payload['records']))
        original = app.library_row(self.item_id)['original_segments_json']
        self.rewrite(lambda rows: rows[1].update(text='corrected text'))
        p = self.analysis()['manual']['preparation']
        self.assertEqual(p['status'], 'needs_review')
        self.assertEqual(p['content_ready_count'], 0)
        self.assertEqual(len(p['versions']), 2)
        self.assertEqual(app.library_row(self.item_id)['original_segments_json'], original)
        self.assertEqual(self.save(payload).status_code, 409)
        history = self.client.get(f'/api/library/{self.item_id}/preparation/export.json').get_json()
        self.assertEqual(len(history['versions']), 2)
        self.assertNotEqual(history['versions'][0]['source']['segments'][1]['text'], 'corrected text')
        self.assertTrue(history['review_history'])
        self.assertEqual(history['manifest']['rows_sha256'], preparation.digest(history['rows']))

    def test_confirmation_checks_not_guessed_or_empty(self):
        payload = self.payload()
        payload['records']['p1_first']['text_status'] = 'unreviewed'
        self.assertEqual(self.save({**payload, 'confirm': True}).status_code, 400)
        payload['records']['p1_first']['text_status'] = 'audio_verified'
        self.assertEqual(self.save(payload).status_code, 400)  # no media
        payload = self.payload()
        self.assertEqual(self.save({**payload, 'participant_count': 3}).status_code, 400)
        self.assertEqual(self.save({**payload, 'participant_count': 3, 'metadata_sources': 'roster page 1'}).status_code, 200)

    def test_get_has_no_side_effects_and_conflict_on_two_reviewers(self):
        first = self.payload()
        before = self.analysis()['manual']['preparation']
        self.analysis()
        self.assertEqual(before, self.analysis()['manual']['preparation'])
        self.assertEqual(self.save(first).status_code, 200)
        self.assertEqual(self.save(first).status_code, 409)

    def test_analysis_binding_and_current_version_quote(self):
        self.rewrite(lambda rows: rows[1].update(text='I agree.'))
        response = self.fixture.put_analysis(self.item_id,
            config={'codebook': [{'id': 'support', 'label': 'Support'}]},
            annotations={'p1_first': {'codes': ['support']}})
        self.assertEqual(response.status_code, 200, response.data)
        report = self.client.get(f'/api/library/{self.item_id}/analysis/export.md').data.decode('utf-8')
        self.assertIn('I agree.', report)
        self.rewrite(lambda rows: rows[1].update(text='I disagree.'))
        self.assertTrue(self.analysis()['manual']['preparation']['analysis_needs_review'])
        # Unrelated saves must not silently rebind the old codes.
        self.assertEqual(self.fixture.put_analysis(self.item_id).status_code, 200)
        self.assertTrue(self.analysis()['manual']['preparation']['analysis_needs_review'])
        report = self.client.get(f'/api/library/{self.item_id}/analysis/export.md').data.decode('utf-8')
        self.assertIn('要再確認', report)
        self.assertNotIn('I disagree.', report)
        result = self.save({**self.payload(), 'review_analysis': True})
        self.assertEqual(result.status_code, 200, result.data)
        self.assertFalse(result.get_json()['analysis_needs_review'])

    def test_deleted_link_remains_as_missing_target(self):
        data = self.analysis()
        response = self.client.put(f'/api/library/{self.item_id}/analysis', json={
            'source_revision': data['item']['revision_count'], 'analysis_revision': data['item']['analysis_revision'],
            'annotations': {'p2_overlap': {'interaction_links': [{'target_segment_id': 'p1_first', 'relation': 'agreement'}]}}})
        self.assertEqual(response.status_code, 200)
        self.rewrite(lambda rows: rows.pop(1))
        data = self.analysis()
        self.assertEqual(data['annotations']['p2_overlap']['interaction_links'][0]['target_segment_id'], 'p1_first')
        self.assertEqual(data['manual']['interaction_links'][0]['status'], 'missing_target')

    def test_blank_initial_record_does_not_gain_fabricated_original(self):
        self.fixture.create_analysis_item('empty_prep', [])
        self.fixture.create_analysis_item('empty_prep', [{'id': 'added', 'text': 'new'}])
        p = self.analysis('empty_prep')['manual']['preparation']
        self.assertIsNone(p['rows'][0]['original_text'])
        self.assertEqual(len(p['versions']), 2)

    def test_split_merge_lineage_validated_without_guessing(self):
        self.rewrite(lambda rows: rows.append({'id': 'split', 'speaker': 'PARTICIPANT_A', 'text': 'split part'}))
        payload = self.payload()
        payload['records']['split']['source_segment_ids'] = ['p1_first']
        self.assertEqual(self.save(payload).status_code, 200)
        self.assertEqual(self.analysis()['manual']['preparation']['rows'][-1]['source_segment_ids'], ['p1_first'])
        payload = self.payload()
        payload['records']['split']['source_segment_ids'] = ['imaginary-id']
        self.assertEqual(self.save(payload).status_code, 400)

    def test_exports_are_linked_and_exact_text_has_version(self):
        self.rewrite(lambda rows: rows[1].update(text='  first\nsecond, "quote"  '))
        data = self.analysis()
        response = self.client.get(data['exports']['prepared_turns'])
        rows = list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig'))))
        row = next(r for r in rows if r['segment_id'] == 'p1_first')
        self.assertEqual(row['text'], '  first\nsecond, "quote"  ')
        self.assertEqual(row['input_version'], '2')
        self.assertEqual(row['start'], '2.5')
        self.assertTrue(row['source_hash'])
        for dataset in ('analysis_units', 'analysis_plan', 'interaction_links', 'codebook_history'):
            self.assertEqual(self.client.get(data['exports'][dataset]).status_code, 200)

    def test_capture_rolls_back_with_transcript_transaction(self):
        row = app.library_row(self.item_id)
        before = self.analysis()['manual']['preparation']['versions']
        with self.assertRaises(RuntimeError):
            with app.database_connection() as connection:
                connection.execute('UPDATE library_items SET segments_json=? WHERE id=?', ('[]', self.item_id))
                changed = connection.execute('SELECT * FROM library_items WHERE id=?', (self.item_id,)).fetchone()
                preparation.capture(connection, changed)
                raise RuntimeError('rollback')
        self.assertEqual(app.library_row(self.item_id)['segments_json'], row['segments_json'])
        self.assertEqual(self.analysis()['manual']['preparation']['versions'], before)

    def test_order_preserved_when_times_missing(self):
        self.fixture.create_analysis_item('order_prep', [
            {'id': 'a', 'start': 20, 'end': 22, 'text': 'first'},
            {'id': 'b', 'text': 'second'}, {'id': 'c', 'start': 2, 'end': 3, 'text': 'third'}])
        data = self.analysis('order_prep')
        self.assertEqual([r['id'] for r in data['segments']], ['a', 'b', 'c'])
        self.assertFalse(data['segments'][1]['valid_time'])
        normalized = app.normalize_edited_segments('x', [{'id': 'b', 'text': '  exact  '}])
        self.assertTrue(normalized[0]['time_unknown'])
        self.assertEqual(normalized[0]['text'], '  exact  ')
        mixed = app.normalize_edited_segments('x', [
            {'id': 'first', 'start': 20, 'end': 21, 'text': 'first'},
            {'id': 'second', 'text': 'second'}])
        self.assertEqual([r['id'] for r in mixed], ['first', 'second'])

    def test_pre_ai_original_is_separate_from_first_saved_analysis_text(self):
        app.upsert_library_item(item_id='before_ai', source_name='synthetic.wav',
            output_dir=app.Path(self.fixture.temporary.name) / 'before_ai', media_path=None, language='ja',
            segments=[{'id': 's', 'text': 'cleaned'}], original_segments=[{'id': 's', 'text': '  RAW ASR  '}],
            speaker_names={}, outline=None, emotion_analysis=None, files=[], write_srt=False, write_json=True)
        p = self.analysis('before_ai')['manual']['preparation']
        self.assertEqual(p['rows'][0]['original_text'], '  RAW ASR  ')
        self.assertEqual(p['rows'][0]['text'], 'cleaned')
        self.assertEqual(p['rows'][0]['text_status'], 'unreviewed')

    def test_legacy_baseline_is_lazy_and_schema_upgrade_idempotent(self):
        original = app.library_row(self.item_id)['original_segments_json']
        with app.database_connection() as connection:
            connection.execute('DELETE FROM transcript_versions WHERE item_id=?', (self.item_id,))
        app.initialize_library()
        app.initialize_library()
        p = self.analysis()['manual']['preparation']
        self.assertIsNone(p['input_version'])
        self.assertFalse(p['versions'])
        result = self.save(self.payload())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()['versions'][0]['origin'], 'preparation_baseline')
        self.assertEqual(app.library_row(self.item_id)['original_segments_json'], original)

    def test_preparation_vault_only_receives_counts_and_hashes(self):
        from gurumoji.vault_registry import VaultRegistry
        p = self.analysis()['manual']['preparation']
        row = app.library_row(self.item_id)
        registry = VaultRegistry(app.DATABASE_FILE, app.PROJECT_DIRECTORY / 'docs' / 'program-vault')
        registry.publish_input(item_id=self.item_id, title='synthetic', segments=app.row_segments(row), revision=0,
            preparation_state={**p, 'metadata_sources': 'PRIVATE_REVIEW_MEMO'})
        folder = app.Path(self.fixture.temporary.name) / 'obsidian' / 'InputVault'
        notes = '\n'.join(path.read_text(encoding='utf-8') for path in folder.rglob('*.md'))
        self.assertIn(p['source_hash'], notes)
        self.assertIn('content_ready_count', notes)
        self.assertNotIn('PRIVATE_REVIEW_MEMO', notes)
        self.assertNotIn(p['rows'][1]['text'], notes)

    def test_browser_preparation_save_desktop_and_mobile(self):
        from werkzeug.serving import make_server
        browser = browser_support.browser_executable()
        if not browser:
            self.skipTest('Chromium browser required')
        original_render = app.render_template
        original_static = app.app.send_static_file
        driver = r'''
window.addEventListener('error', event => { document.body.dataset.preparationError = event.message; });
window.addEventListener('DOMContentLoaded', async () => {
  const wait = async (fn) => {
    for (let i=0; i<180; i++) {
      if (fn()) return;
      if (i % 10 === 0) await fetch('/api/jobs/active');
      await new Promise(resolve => setTimeout(resolve, 40));
    }
    throw new Error('wait timed out: ' + fn.toString());
  };
  try {
    await wait(() => analysisState.data?.item.id === 'analysis_fixture');
    setAnalysisMode('manual');
    const root = () => document.querySelector(window.innerWidth < 960 ? '#analysis-mobile-content' : '#analysis-desktop-content');
    if (!root().querySelector('a[href$="dataset=prepared_turns"]')) throw new Error('missing CSV link');
    const revision = analysisState.data.manual.preparation.revision;
    root().querySelectorAll('[data-preparation-key]').forEach(input => {
      const key = input.dataset.preparationKey;
      if (key.endsWith(':text_status')) input.value = 'transcript_checked';
      else if (key.endsWith(':role')) input.value = key.startsWith('m_intro:') ? 'moderator' : 'participant';
      else if (input.type === 'checkbox' && !key.endsWith(':review_analysis')) input.checked = true;
      else return;
      input.dispatchEvent(new Event('input', {bubbles:true}));
    });
    root().querySelector('[data-preparation-save="true"]').click();
    await wait(() => analysisState.data?.manual.preparation.revision > revision);
    if (analysisState.data.manual.preparation.status !== 'confirmed') throw new Error('not confirmed');
    if (preparationDirty) throw new Error('draft still dirty');
    const target = [...root().querySelectorAll('[data-analysis-interaction-target]')]
      .find(input => input.getAttribute('data-analysis-interaction-target') === 'p2_overlap');
    if (!target) throw new Error('no interaction control');
    target.value = 'p1_first';
    const card = target.closest('.analysis-segment-card');
    card.querySelector('[data-analysis-interaction-relation]').value = 'agreement';
    card.querySelector('[data-analysis-add-interaction-link]').click();
    if (!analysisState.annotations.p2_overlap?.interaction_links?.length) throw new Error('interaction control reads wrong layout');
    document.body.dataset.preparationTest = 'passed';
  } catch (error) { document.body.dataset.preparationTest = 'failed: ' + error.message; }
});
'''

        def render(*args, **kwargs):
            return original_render(*args, **kwargs).replace('</body>', '<script src="/static/preparation-driver.js" defer></script></body>')

        def static(filename):
            if filename == 'preparation-driver.js':
                return app.app.response_class(driver, mimetype='text/javascript')
            return original_static(filename)

        server = make_server('127.0.0.1', 0, app.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(system_routes, 'render_template', side_effect=render), patch.object(app.app, 'send_static_file', side_effect=static):
                for size in ('1360,900', '390,844'):
                    with self.subTest(size=size):
                        result = subprocess.run([browser, '--headless=new', '--disable-gpu', '--disable-background-networking',
                            '--disable-extensions', '--no-first-run', '--no-default-browser-check', '--no-sandbox',
                            '--force-device-scale-factor=1', f'--window-size={size}',
                            f'--user-data-dir={self.fixture.temporary.name}/browser-{size.split(",")[0]}',
                            '--virtual-time-budget=40000', '--dump-dom',
                            f'http://127.0.0.1:{server.server_port}/?view=analysis&item=analysis_fixture'],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=40)
                        match = re.search(r'data-preparation-test="([^"]+)"', result.stdout)
                        error = re.search(r'data-preparation-error="([^"]+)"', result.stdout)
                        self.assertIsNotNone(match, error.group(0) if error else result.stderr[-2000:])
                        self.assertEqual(match.group(1), 'passed')
                        self.assertIsNone(error)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
