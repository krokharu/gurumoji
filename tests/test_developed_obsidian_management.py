"""Committed handoffs, real note policy, temporary data; no model/network calls."""
import copy
import json
import unittest
from unittest.mock import patch
from flask import Flask
from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.core_pipeline_service import validate_orchestration_payload
from gurumoji.analysis_store import StoreConflict
from gurumoji.services.obsidian_management import ObsidianManagementAgent, management_packet
from gurumoji.vault_registry import VaultRegistry
from gurumoji.web.core_pipeline_routes import register_core_pipeline_routes as register_orchestration_routes
import test_developed_analysis_orchestration as runtime_support


class ObsidianManagementTests(unittest.TestCase):

    def setUp(self):
        self.fixture = runtime_support.RuntimeTests('test_complete_pipeline_and_pre_stop_review')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.registry = VaultRegistry(self.fixture.path)
        self.manager = ObsidianManagementAgent(registry_factory=lambda: self.registry)
        self.fixture.service = self.fixture.make_service(memory_manager=self.manager)
        self.service = self.fixture.service

    def note(self, run_id):
        data = self.registry.load()
        entry = data['notes'][self.manager.note_id(run_id)]
        return self.registry.root('orchestrator', data) / entry['path']

    def test_committed_core_handler_data_is_linked_without_copying_input(self):
        packets = []
        original = self.manager.receive

        def receive(packet):
            packets.append(copy.deepcopy(packet))
            return original(packet)
        with patch.object(self.manager, 'receive', side_effect=receive):
            run = self.fixture.start()
            final = self.fixture.drive(run)
        self.assertEqual(final['status'], 'completed')
        self.assertEqual(final['obsidian_management']['status'], 'linked')
        self.assertGreaterEqual(final['obsidian_management']['event_seq'], 1)
        self.assertTrue(any((packet['counts']['decisions'] >= 3 for packet in packets)))
        self.assertTrue(any((packet['counts']['tasks'] > 0 for packet in packets)))
        text = self.note(run['run_id']).read_text(encoding='utf-8')
        self.assertIn(final['current_view']['summary'], text)
        self.assertIn('/export.json', text)
        self.assertIn(run['initial_id'], text)
        self.assertNotIn('Synthetic first utterance', text)
        entity = self.registry.load()['entities'][self.manager.note_id(run['run_id'])]
        self.assertEqual(entity['references']['labels']['table'], 'orchestration_label_versions')
        self.assertGreaterEqual(entity['counts']['decisions'], 3)
        self.assertNotIn('raw_evidence', json.dumps(entity))
        role = next((role for role in final['roles'] if role['id'] == 'obsidian_manager'))
        self.assertEqual((role['kind'], role['provider'], role['status']), ('code', 'python', 'linked'))
        core_context = next((context for role, context, _ in self.fixture.calls if role == 'core'))
        self.assertNotIn('management', core_context['packet'])
        self.assertFalse((self.registry.data / 'obsidian' / 'ResearchVault').exists())

    def test_outline_tags_are_in_the_ledger_and_their_summary_in_the_note(self):
        segments = self.fixture.snapshot['analysis']['segments']
        segments[0].update(start=1.0, end=2.0)
        segments[1].update(start=12.0, end=13.0)
        self.fixture.snapshot['analysis']['session_outline'] = {'result': {'rows': [{'title': 'Opening topic', 'start': 0, 'end': 10, 'segment_ids': ['u1'], 'title_source': 'outline'}, {'title': 'Later topic', 'start': 20, 'end': 30, 'segment_ids': [], 'title_source': 'outline'}]}}
        packets = []
        original = self.manager.receive

        def receive(packet):
            packets.append(copy.deepcopy(packet))
            return original(packet)
        with patch.object(self.manager, 'receive', side_effect=receive):
            run = self.fixture.start()
            final = self.fixture.drive(run)
        self.assertEqual(final['status'], 'completed')
        tags = final['outline_tags']
        self.assertEqual(sorted(tags['tags'].values()), ['S01', 'S01'])
        self.assertEqual(tags['version'], 'outline-sections-2')
        summary = packets[-1]['outline_tags']
        self.assertEqual(summary['tagged'], 2)
        self.assertEqual(summary['sections'], [['S01', 2, 'Opening topic']])
        text = self.note(run['run_id']).read_text(encoding='utf-8')
        self.assertIn('## アウトライン節タグ', text)
        self.assertIn('| S01 | 2 | Opening topic |', text)
        self.assertIn(tags['outline_hash'], text)
        for evidence_id in tags['tags']:
            self.assertNotIn(evidence_id, text)
        self.assertNotIn('Synthetic first utterance', text)
        self.assertFalse((self.registry.data / 'obsidian' / 'ResearchVault').exists())

    def test_get_download_and_idempotent_retry_never_call_ai(self):
        run = self.fixture.start()
        final = self.fixture.drive(run)
        path = self.note(run['run_id'])
        original_note, original_db, calls = (path.read_bytes(), self.fixture.path.read_bytes(), len(self.fixture.calls))
        for _ in range(3):
            self.service.status('conversation', run['run_id'])
            self.assertEqual(self.service.memory_note('conversation', run['run_id']), original_note)
        self.assertEqual(self.fixture.path.read_bytes(), original_db)
        self.service.sync_memory('conversation', run['run_id'])
        self.assertEqual(path.read_bytes(), original_note)
        self.assertEqual(len(self.fixture.calls), calls)
        self.assertEqual(final['config']['publication_targets'], [])

    def test_cancel_retains_checkpoint_links_and_does_not_claim_fixed_package(self):
        run = self.fixture.start()
        state = self.service.cancel('conversation', run['run_id'])
        self.assertEqual(state['status'], 'cancelled')
        self.assertEqual(state['obsidian_management']['status'], 'linked')
        entity = self.registry.load()['entities'][self.manager.note_id(run['run_id'])]
        self.assertEqual(entity['status'], 'cancelled')
        self.assertIsNone(entity['package'])
        self.assertEqual(self.fixture.calls, [])

    def test_manager_failure_is_separate_and_explicit_retry_does_not_reanalyse(self):
        with patch.object(self.manager, 'receive', side_effect=OSError('secret-path-must-not-be-stored')):
            run = self.fixture.start()
            state = self.fixture.drive(run)
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state['obsidian_management'], {'status': 'failed', 'error_code': 'OSError', 'enabled': True})
        self.assertNotIn('secret-path', self.fixture.path.read_bytes().decode('latin-1'))
        calls = len(self.fixture.calls)
        state = self.service.sync_memory('conversation', run['run_id'])
        self.assertEqual(state['obsidian_management']['status'], 'linked')
        self.assertEqual(len(self.fixture.calls), calls)

    def test_generated_note_edits_are_preserved_and_deletion_is_not_recreated(self):
        run = self.fixture.start()
        path = self.note(run['run_id'])
        edited = path.read_text(encoding='utf-8') + '\nResearcher edit preserved.\n'
        path.write_text(edited, encoding='utf-8')
        self.assertEqual(self.service.status('conversation', run['run_id'])['obsidian_management']['status'], 'edited')
        self.service.sync_memory('conversation', run['run_id'])
        history = list((self.registry.root('orchestrator') / '99-Archive' / 'history').rglob('*.md'))
        self.assertTrue(any(('Researcher edit preserved.' in note.read_text(encoding='utf-8') for note in history)))
        path.unlink()
        self.assertEqual(self.service.status('conversation', run['run_id'])['obsidian_management']['status'], 'missing')
        self.fixture.drive(run)
        self.assertEqual(self.service.sync_memory('conversation', run['run_id'])['obsidian_management']['status'], 'missing')
        self.assertFalse(path.exists())
        with self.assertRaises(StoreConflict):
            self.service.memory_note('conversation', run['run_id'])

    def test_disabled_scope_and_legacy_requests_cannot_gain_management_on_resume(self):
        run = self.fixture.start(obsidian_management=False)
        self.assertFalse(self.registry.catalog_file.exists())
        for value in (0, 1, 'false', None):
            with self.subTest(value=value), self.assertRaises(AnalysisContractError):
                self.service.resume('conversation', run['run_id'], {'obsidian_management': value})
        with self.assertRaises(AnalysisContractError):
            self.service.resume('conversation', run['run_id'], {'obsidian_management': True})
        with self.service._db() as db:
            saved = self.service._read_run(db, run['run_id'])
            saved['config'].pop('obsidian_management')
            self.service._write_run(db, saved)
            request_hash = fingerprint({'item_id': 'conversation', 'config': saved['config'], 'source_revision': None, 'analysis_revision': None, 'input_hash': None})
            db.execute('UPDATE orchestration_runs SET request_hash=? WHERE run_id=?', (request_hash, run['run_id']))
        with self.assertRaises(AnalysisContractError):
            self.fixture.start(request_id=run['request_id'])
        self.assertFalse(self.registry.catalog_file.exists())

    def test_driver_is_released_even_when_final_management_snapshot_cannot_be_read(self):
        run = self.fixture.start()
        with patch.object(self.service, '_build_initial', return_value=False), patch.object(self.service, '_notify_completed'), patch.object(self.service, '_notify_management', side_effect=OSError('database unavailable')):
            with self.assertRaises(OSError):
                self.service.run(run['run_id'])
        self.assertNotIn(run['run_id'], self.service._driving)

    def test_stale_source_and_cross_item_ownership_remain_visible(self):
        run = self.fixture.start()
        self.fixture.item['revision'] = 'input-v2'
        state = self.service.sync_memory('conversation', run['run_id'])
        self.assertTrue(state['obsidian_management']['stale'])
        self.assertIn('status: stale', self.note(run['run_id']).read_text(encoding='utf-8'))
        with self.assertRaises(LookupError):
            self.service.memory_note('other-item', run['run_id'])

    def test_projection_excludes_unrecognized_secrets_and_rejects_unsafe_origin(self):
        run = self.fixture.start()
        state = self.service.status('conversation', run['run_id'])
        state.update(api_key='secret-key', raw_evidence=[{'text': 'raw-body'}], app_url='https://localhost:7860')
        state['config']['tokens'] = 'secret-key'
        packet = management_packet(state, [])
        self.assertNotIn('secret-key', json.dumps(packet))
        self.assertNotIn('raw-body', json.dumps(packet))
        for url in ('javascript:alert(1)', 'http://user:password@localhost', 'https://host>bad'):
            state['app_url'] = url
            with self.subTest(url=url), self.assertRaises(StoreConflict):
                management_packet(state, [])
        for value in ('true', 1, None, []):
            with self.subTest(value=value), self.assertRaises(AnalysisContractError):
                validate_orchestration_payload({'model': 'synthetic', 'obsidian_management': value})

    def test_download_rechecks_bytes_if_an_external_edit_arrives_during_read(self):
        run = self.fixture.start()
        path = self.note(run['run_id'])
        original = self.manager.inspect

        def edit_after_check(*args):
            state = original(*args)
            path.write_bytes(path.read_bytes() + b'\nEXTERNAL-EDIT\n')
            return state
        with patch.object(self.manager, 'inspect', side_effect=edit_after_check), self.assertRaises(StoreConflict):
            self.service.memory_note('conversation', run['run_id'])

    def test_http_read_only_download_and_empty_scoped_retry(self):
        run = self.fixture.start()
        app = Flask(__name__)
        register_orchestration_routes(app, lambda: self.service, lambda value: value)
        client = app.test_client()
        base = f"/api/library/conversation/analysis/core-pipeline/{run['run_id']}/memory"
        note = self.note(run['run_id']).read_bytes()
        db = self.fixture.path.read_bytes()
        self.assertEqual(client.get(base + '/note').data, note)
        self.assertEqual(self.fixture.path.read_bytes(), db)
        self.assertEqual(client.post(base + '/retry', json={'obsidian_management': True}).status_code, 400)
        self.assertEqual(client.post(base + '/retry', json={}).status_code, 200)
        self.assertEqual(self.fixture.calls, [])
        self.assertEqual(client.get(base.replace('conversation', 'wrong-item') + '/note').status_code, 404)
if __name__ == '__main__':
    unittest.main()
