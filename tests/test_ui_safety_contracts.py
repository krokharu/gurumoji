"""Synthetic UI/API regression contracts; never calls an external AI or model."""
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
from support import use_temporary_library
from gurumoji.services.transcription_readiness import transcription_readiness


class UiSafetyContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gurumoji-ui-safety-')
        self.addCleanup(self.temp.cleanup)
        use_temporary_library(self, Path(self.temp.name))
        self.client = app.app.test_client()

    def preview(self, content, revision=0):
        return self.client.post('/api/speakers/import', data={
            'csv_file': (io.BytesIO(content.encode()), 'synthetic.csv'),
            'registry_revision': str(revision), 'preview': '1',
        })

    def test_preview_is_read_only_then_normal_save_is_atomic(self):
        original = self.client.put('/api/speakers', json={'registry_revision': 0, 'speakers': [
            {'id': 'speaker_original', 'participant_code': 'P1', 'display_name': 'Before', 'attributes': {'old': 'kept'}}
        ]}).get_json()
        preview = self.preview('参加者コード,氏名,知らない質問\nP1,After,yes\nP2,New,no\n', 1)
        self.assertEqual(preview.status_code, 200)
        data = preview.get_json()
        self.assertTrue(data['preview'])
        self.assertEqual(data['summary']['added'], 1)
        self.assertEqual(data['summary']['updated'], 1)
        self.assertEqual(data['registry_revision'], 1)
        self.assertEqual(self.client.get('/api/speakers').get_json(), {**original, 'total': 1})
        self.assertIn({'column': '知らない質問', 'field': 'attributes'}, data['summary']['columns'])
        # Invalid row rejects the entire save before any persistence.
        invalid = self.client.put('/api/speakers', json={
            'registry_revision': 1, 'speakers': [data['speakers'][0], {}],
        })
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.client.get('/api/speakers').get_json()['speakers'], original['speakers'])
        saved = self.client.put('/api/speakers', json={
            'registry_revision': data['registry_revision'], 'speakers': data['speakers'],
        })
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()['registry_revision'], 2)
        speakers = saved.get_json()['speakers']
        self.assertEqual(len(speakers), 2)
        updated = next(item for item in speakers if item['participant_code'] == 'P1')
        self.assertEqual(updated['display_name'], 'After')
        self.assertEqual(updated['attributes'], {'old': 'kept', '知らない質問': 'yes'})

    def test_preview_and_later_save_keep_revision_conflicts(self):
        draft = self.preview('参加者コード,氏名\nP1,Draft\n').get_json()
        latest = self.client.put('/api/speakers', json={
            'registry_revision': 0, 'speakers': [{'id': 'speaker_latest', 'display_name': 'Latest'}],
        }).get_json()
        self.assertEqual(self.preview('参加者コード,氏名\nP1,Draft\n').status_code, 409)
        result = self.client.put('/api/speakers', json={'registry_revision': 0, 'speakers': draft['speakers']})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(self.client.get('/api/speakers').get_json()['speakers'], latest['speakers'])

    def test_page_has_named_live_regions_and_recovery_controls(self):
        page = self.client.get('/').get_data(as_text=True)
        for tab in ('transcript', 'conversation', 'summary', 'files'):
            self.assertIn(f'aria-labelledby="item-tab-{tab}"', page)
        for control in ('undo-segment-delete', 'speaker-import-preview', 'export-result-draft',
                        'export-speaker-draft', 'setup-readiness-details', 'setup-open-connections'):
            self.assertIn(f'id="{control}"', page)
        self.assertIn('id="save-message" class="alert" role="status" aria-live="polite"', page)

    def test_runtime_labels_are_configurable_and_os_specific(self):
        for system, runtime, label, path in [
            ('Linux', 'cloud', '検証クラウド', '/path/to/recording.wav'),
            ('Windows', 'local', '検証PC', r'C:\audio\recording.wav'),
            ('Linux', 'colab', '検証Colab', '/content/drive/MyDrive/...'),
        ]:
            with self.subTest(system=system, runtime=runtime), patch.object(app.platform, 'system', return_value=system), patch.dict(os.environ, {'MOJIOKOSI_RUNTIME': runtime, 'MOJIOKOSI_RUNTIME_LABEL': label}):
                info = app.runtime_info()
                self.assertEqual(info['label'], label)
                self.assertEqual(info['source_path_example'], path)
                page = self.client.get('/').get_data(as_text=True)
                self.assertIn(label, page)
                self.assertIn(path, page)
                if system == 'Linux':
                    self.assertNotIn('scripts\\setup_qwen_stack.bat', page)

    def test_readiness_never_downloads_and_distinguishes_missing(self):
        with patch.dict(os.environ, {'XDG_CACHE_HOME': self.temp.name, 'HF_HOME': self.temp.name}), patch('gurumoji.services.transcription_readiness.importlib.util.find_spec', return_value=None), patch('gurumoji.services.transcription_readiness.shutil.which', return_value=None), patch('gurumoji.services.transcription_readiness.qwen_stack_available', return_value=False):
            result = transcription_readiness()
        self.assertTrue(result['whisperx']['blockers'])
        self.assertEqual(result['whisperx']['models']['cpu']['tiny']['status'], 'missing')
        self.assertIn('ダウンロード', result['whisperx']['models']['cpu']['tiny']['message'])
        self.assertTrue(result['qwen3_nemotron']['blockers'])


if __name__ == '__main__':
    unittest.main()
