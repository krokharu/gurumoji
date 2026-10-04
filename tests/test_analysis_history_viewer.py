"""Synthetic saved-history coverage. No AI, user files or external services."""
import copy
import json
import sqlite3
import unittest
from unittest.mock import Mock

from flask import Flask
from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.services.analysis_history import AnalysisHistoryService
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
import test_analysis_orchestration as fixtures
from test_analysis_orchestration import core, critic, intent, stop


class HistoryViewerTests(unittest.TestCase):
    def setUp(self):
        self.runtime = fixtures.RuntimeTests()
        self.runtime.setUp()
        self.addCleanup(self.runtime.doCleanups)
        self.service = self.runtime.service
        self.viewer = AnalysisHistoryService(connect=self.runtime.connect, find_item=self.service.find_item)
        self.run = self.runtime.start()
        self.run_id = self.run['run_id']
        app = Flask(__name__)
        self.execution_factory = Mock(side_effect=AssertionError('GET called execution factory'))
        register_orchestration_routes(app, self.execution_factory, Mock(side_effect=AssertionError('GET prepared a model')),
                                      history_viewer=lambda: self.viewer)
        self.client = app.test_client()
        self.base = '/api/library/conversation/analysis/orchestration/'

    def audit(self):
        with self.runtime.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT payload_json FROM orchestration_label_audit ORDER BY rowid')]

    def patch(self, field='codes', old=None, new=None, operation=None, disposition='adopt', base=None):
        with self.service._db() as db:
            run = self.service._read_run(db, self.run_id, 'conversation')
            patch = {'utterance_id': 'u1', 'field': field, 'old_value': old, 'new_value': new,
                     'reason': 'Recorded synthetic evidence', 'evidence_ids': [self.service._initial(db, run['initial_id'])['evidence'][0]['evidence_id']],
                     'base_annotation_version': run['annotation_version'] if base is None else base, 'codebook_version': 1}
            if operation:
                patch['operation'] = operation
            proposer = {'task_id': 'synthetic-task', 'role': 'interpretation', 'model': 'synthetic-model', 'provider': 'synthetic'}
            self.service._save_patch(db, run, proposer, patch, {'result_id': 'synthetic-result'})
            proposal = json.loads(db.execute('SELECT payload_json FROM orchestration_label_proposals ORDER BY rowid DESC LIMIT 1').fetchone()[0])
            self.service._commit_labels(db, run, [{'proposal_id': proposal['proposal_id'], 'disposition': disposition, 'reason': 'Recorded decision'}],
                                        task={**proposer, 'task_id': 'core-task', 'role': 'core'}, result_id='core-result', decision_id='core-decision')
            self.service._write_run(db, run)
            return proposal

    def test_add_update_delete_retains_original_and_tombstone(self):
        self.patch(field='theme', new='first', operation='add')
        self.patch(field='theme', old='first', new='second', operation='update')
        self.patch(field='theme', old='second', operation='delete')
        events = self.audit()
        self.assertEqual([e['disposition'] for e in events], ['proposal', 'adopt'] * 3)
        self.assertEqual([e['operation'] for e in events], ['add', 'add', 'update', 'update', 'delete', 'delete'])
        deletion = events[-1]
        self.assertTrue(deletion['tombstone'])
        self.assertEqual((deletion['before_value'], deletion['after_value']), ('second', None))
        self.assertEqual((deletion['before_present'], deletion['after_present']), (True, False))
        self.assertEqual((deletion['before_annotation_version'], deletion['after_annotation_version']), (2, 3))
        self.assertEqual(deletion['item_id'], 'conversation')
        self.assertEqual(deletion['decision_id'], 'core-decision')
        source = self.viewer.source('conversation', self.run_id, 'u1', annotation_version=1)
        self.assertNotIn('theme', source['labels']['initial'])
        self.assertEqual(source['labels']['selected']['theme'], 'first')
        self.assertNotIn('theme', source['labels']['latest'])
        self.assertEqual(self.runtime.snapshot['analysis']['segments'][0]['annotation'], {'codes': ['manual']})

    def test_proposal_does_not_claim_application_or_trust_stated_old_value(self):
        self.patch(old=['invented-old'], new=['proposal-only'])
        proposed, conflict = self.audit()
        self.assertEqual(proposed['before_value'], ['manual'])
        self.assertEqual(proposed['after_value'], ['manual'])
        self.assertEqual(proposed['stated_old_value'], ['invented-old'])
        self.assertEqual(proposed['proposed_value'], ['proposal-only'])
        self.assertEqual(proposed['before_annotation_version'], proposed['after_annotation_version'])
        self.assertEqual(conflict['disposition'], 'conflict')
        self.assertEqual(conflict['after_value'], ['manual'])

    def test_reject_defer_conflict_are_distinct_immutable_events(self):
        for disposition in ('reject', 'defer'):
            self.patch(old=['manual'], new=['ignored'], disposition=disposition)
        self.patch(old=['manual'], new=['adopted'])
        self.patch(old=['manual'], new=['stale'], base=0)
        events = self.audit()
        self.assertEqual([e['disposition'] for e in events[1::2]], ['reject', 'defer', 'adopt', 'conflict'])
        self.assertEqual([e['after_annotation_version'] for e in events[1::2]], [0, 0, 1, 1])
        self.assertEqual(events[-1]['before_value'], ['adopted'])
        self.assertEqual(events[-1]['after_value'], ['adopted'])
        self.assertEqual(events[-1]['proposed_value'], ['stale'])
        for sql in ('UPDATE orchestration_label_audit SET payload_json=?', 'DELETE FROM orchestration_label_audit'):
            with self.assertRaises(sqlite3.IntegrityError), self.runtime.connect() as db:
                db.execute(sql, ('{}',) if '?' in sql else ())
        self.assertEqual(events, self.audit())
        self.assertEqual(self.service.result('conversation', self.run_id)['label_audit'], events)

    def test_explicit_operation_presence_conflicts(self):
        self.patch(field='theme', new='missing', operation='update')
        self.patch(field='codes', old=['manual'], new=['present'], operation='add')
        self.patch(field='theme', operation='delete')
        self.assertEqual([e['disposition'] for e in self.audit()[1::2]], ['conflict'] * 3)
        self.assertEqual(self.viewer.source('conversation', self.run_id, 'u1')['labels']['latest'], {'codes': ['manual']})

    def test_persistence_preserves_full_audit_values_but_projection_marks_bounds(self):
        values = ['v' + str(i) for i in range(60)]
        self.patch(old=['manual'], new=values)
        self.assertEqual(self.audit()[-1]['after_value'], values)
        entry = self.viewer.entry('conversation', self.run_id, 'label:' + self.audit()[-1]['event_id'])['entry']
        self.assertEqual(len(entry['after_value']), 50)
        self.assertIn('after_value', entry['truncated_fields'])

    def test_old_schema_missing_audit_is_read_only_and_explicit(self):
        self.patch(old=['manual'], new=['legacy'])
        with self.runtime.connect() as db:
            db.execute('DROP TABLE orchestration_label_audit')
            row = db.execute('SELECT proposal_id,payload_json FROM orchestration_label_proposals').fetchone()
            patch = json.loads(row[1]); patch.pop('created_at')
            db.execute('UPDATE orchestration_label_proposals SET payload_json=?', (json.dumps(patch),))
            run = self.service._read_run(db, self.run_id); run.pop('label_audit_version', None)
            db.execute('UPDATE orchestration_runs SET state_json=? WHERE run_id=?', (json.dumps(run), self.run_id))
        before = self.runtime.path.read_bytes()
        data = self.viewer.timeline('conversation', self.run_id, kind='label')
        self.assertEqual(data['audit']['status'], 'partial')
        self.assertEqual(data['entries'][0]['created_at'], None)
        detail = self.viewer.entry('conversation', self.run_id, data['entries'][0]['entry_id'])['entry']
        self.assertEqual(detail['audit_status'], 'legacy_projection')
        self.assertIsNone(detail['after_value'])
        self.assertIn('disposition_time', detail['missing_fields'])
        self.assertEqual(before, self.runtime.path.read_bytes())

    def test_timeline_filters_and_sql_pagination(self):
        self.patch(old=['manual'], new=['accepted'])
        with self.runtime.connect() as db:
            for i in range(213):
                self.service._event(db, self.run_id, 'fixture', 'event', source='critic')
        first = self.viewer.timeline('conversation', self.run_id, kind='event', role='critic', operation='fixture', limit=100)
        second = self.viewer.timeline('conversation', self.run_id, kind='event', role='critic', operation='fixture', limit=100, offset=100)
        last = self.viewer.timeline('conversation', self.run_id, kind='event', role='critic', operation='fixture', limit=100, offset=200)
        self.assertEqual([len(p['entries']) for p in (first, second, last)], [100, 100, 13])
        ids = [e['entry_id'] for p in (first, second, last) for e in p['entries']]
        self.assertEqual(len(set(ids)), 213)
        self.assertFalse(last['pagination']['has_more'])
        adopted = self.viewer.timeline('conversation', self.run_id, kind='label', operation='adopt', status='committed')
        self.assertEqual(adopted['pagination']['total'], 1)
        timestamp = adopted['entries'][0]['created_at']
        self.assertEqual(self.viewer.timeline('conversation', self.run_id, kind='label', after=timestamp, before=timestamp)['pagination']['total'], 1)

    def test_invalid_filters_and_versions_rejected(self):
        for query in ({'limit': 0}, {'limit': 101}, {'offset': -1}, {'limit': '1.0'}, {'offset': '99999999999999999999'}, {'after': '2026-10-04'},
                      {'after': '2026-10-05T00:00:00Z', 'before': '2026-10-04T00:00:00Z'}, {'annotation_version': 'oops'}):
            with self.assertRaises(AnalysisContractError):
                self.viewer.timeline('conversation', self.run_id, **query)
        with self.assertRaises(LookupError):
            self.viewer.source('conversation', self.run_id, 'u1', annotation_version=99)

    def test_get_is_read_only_no_execution_source_refresh_or_schema_mutation(self):
        self.runtime.item['revision'] = 'changed-after-run'
        before = self.runtime.path.read_bytes()
        initial = 'initial:' + self.run['initial_id']
        urls = ['viewer', self.run_id + '/viewer', self.run_id + '/viewer/entries/' + initial,
                self.run_id + '/viewer/sources/u1?annotation_version=0']
        for url in urls:
            response = self.client.get(self.base + url)
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(before, self.runtime.path.read_bytes())
        self.assertFalse(self.runtime.calls)
        self.assertFalse(self.runtime.methods)
        self.execution_factory.assert_not_called()

    def test_cross_run_item_entry_and_fixed_sources_rejected(self):
        first = self.run
        self.runtime.item['revision'] = 'input-v2'
        self.runtime.snapshot['input_hash'] = 'input-v2'
        self.runtime.snapshot['analysis']['segments'] = [{'id': 'other', 'text': 'Other snapshot only'}]
        other = self.runtime.start()
        for action in (
                lambda: self.viewer.timeline('wrong-item', first['run_id']),
                lambda: self.viewer.source('conversation', first['run_id'], 'other'),
                lambda: self.viewer.source('conversation', other['run_id'], 'u1'),
                lambda: self.viewer.entry('conversation', first['run_id'], 'initial:' + other['initial_id'])):
            with self.assertRaises(LookupError):
                action()
        self.assertEqual(self.viewer.source('conversation', first['run_id'], 'u1')['source']['text'], 'Synthetic first utterance')

    def test_result_projection_scratch_exclusion_and_malformed_quarantined_claims(self):
        self.runtime.agent = lambda *_: core(summary='Visible', claims=[{'evidence_ids': None}], chain_of_thought='DO-NOT-DISPLAY')
        run = self.runtime.drive(self.run)
        entry_id = 'result:' + run['results'][0]['result_id']
        detail = self.viewer.entry('conversation', self.run_id, entry_id)
        self.assertEqual(detail['entry']['summary'], 'Visible')
        self.assertNotIn('DO-NOT-DISPLAY', json.dumps(detail))
        self.assertEqual(detail['entry']['claims'][0]['evidence_ids'], [])
        with self.runtime.connect() as db:
            db.execute('UPDATE orchestration_results SET raw_json=?', ('{"summary":"tampered"}',))
        with self.assertRaises(AnalysisContractError):
            self.viewer.entry('conversation', self.run_id, entry_id)

    def test_run_identity_corruption_rejected_in_list_and_detail(self):
        with self.runtime.connect() as db:
            run = self.service._read_run(db, self.run_id); run['item_id'] = 'forged'
            db.execute('UPDATE orchestration_runs SET state_json=?', (json.dumps(run),))
        for action in (lambda: self.viewer.runs('conversation'), lambda: self.viewer.timeline('conversation', self.run_id)):
            with self.assertRaises(AnalysisContractError) as error:
                action()
            self.assertEqual(error.exception.code, 'history_integrity_mismatch')

    def test_empty_uninitialized_ledger_never_creates_schema(self):
        self.runtime.path.unlink()
        with self.runtime.connect() as db:
            db.execute('CREATE TABLE unrelated(id)')
        before = self.runtime.path.read_bytes()
        self.assertEqual(self.viewer.runs('conversation')['runs'], [])
        self.assertEqual(before, self.runtime.path.read_bytes())

    def test_initial_evidence_pagination_and_large_version_selection(self):
        self.runtime.item['revision'] = 'many'
        self.runtime.snapshot['input_hash'] = 'many'
        self.runtime.snapshot['analysis']['segments'] = [{'id': f'u{i}', 'text': f'Synthetic {i}', 'annotation': {}} for i in range(135)]
        run = self.runtime.start()
        page = self.viewer.entry('conversation', run['run_id'], 'initial:' + run['initial_id'], evidence_offset=100, evidence_limit=100)
        self.assertEqual(len(page['evidence']), 35)
        self.assertEqual(page['evidence'][0]['utterance_id'], 'u100')
        self.assertFalse(page['evidence_pagination']['has_more'])
        with self.runtime.connect() as db:
            for i in range(1, 205):
                db.execute('INSERT INTO orchestration_label_versions VALUES (?,?,?)', (run['run_id'], i, '{"u0":{}}'))
            state = self.service._read_run(db, run['run_id']); state['annotation_version'] = 204
            db.execute('UPDATE orchestration_runs SET state_json=? WHERE run_id=?', (json.dumps(state), run['run_id']))
        page = self.viewer.timeline('conversation', run['run_id'], annotation_version=203)
        self.assertEqual(page['versions']['selected'], 203)
        self.assertTrue(page['versions']['has_more'])
        self.assertEqual(len(page['versions']['available']), 200)

    def test_saved_export_is_read_only_and_fails_on_size_limit(self):
        before = self.runtime.path.read_bytes()
        exported = self.viewer.saved_export('conversation', self.run_id)
        self.assertEqual(exported['initial']['snapshot']['analysis']['segments'][0]['id'], 'u1')
        self.assertEqual(before, self.runtime.path.read_bytes())
        with self.runtime.connect() as db:
            for i in range(2001):
                self.service._event(db, self.run_id, 'many', '')
        with self.assertRaises(AnalysisContractError) as error:
            self.viewer.saved_export('conversation', self.run_id)
        self.assertEqual(error.exception.code, 'history_export_limit')

    def test_missing_readonly_factory_fails_closed_without_execution_factory(self):
        app = Flask(__name__ + '-missing')
        register_orchestration_routes(app, self.execution_factory, Mock())
        self.assertEqual(app.test_client().get(self.base + 'viewer').status_code, 503)
        self.execution_factory.assert_not_called()

    def test_real_decision_summary_version_and_backlinks(self):
        def agent(role, context, *_):
            if role == 'core':
                if context['budget']['iteration'] == 1:
                    return core(intents=[intent('interpretation', label_dependent=True)])
                return stop(label_decisions=[{'proposal_id': p['proposal_id'], 'disposition': 'adopt', 'reason': 'Observed'}
                                             for p in context['label_proposals']])
            if role == 'critic':
                return critic(context)
            return {'summary': 'Proposal', 'label_patches': [{'utterance_id': 'u1', 'field': 'codes',
                'old_value': ['manual'], 'new_value': ['accepted'], 'reason': 'Observed evidence',
                'evidence_ids': [context['raw_evidence'][0]['evidence_id']], 'base_annotation_version': 0, 'codebook_version': 1}]}
        self.runtime.agent = agent
        run = self.runtime.drive(self.run)
        event = self.audit()[-1]
        detail = self.viewer.entry('conversation', self.run_id, 'label:' + event['event_id'])
        self.assertIn('decision:' + event['decision_id'], detail['entry']['related_entry_ids'])
        self.assertIn('result:' + event['proposal_result_id'], detail['entry']['related_entry_ids'])
        self.assertEqual(detail['evidence'][0]['utterance_id'], 'u1')
        dto = self.viewer.timeline('conversation', self.run_id, kind='decision', status='saved')
        self.assertGreater(dto['pagination']['total'], 0)
        self.assertEqual(dto['run']['summary_entry_id'], 'decision:' + run['last_decision_id'])
        self.assertIsInstance(dto['run']['summary_annotation_version'], int)
        self.assertEqual(self.client.get(self.base + self.run_id + '/viewer?limit=1001').status_code, 400)
        self.assertEqual(self.client.get(self.base + self.run_id + '/viewer/sources/unknown').status_code, 404)

    def test_export_rejects_result_task_identity_mixup(self):
        first = self.runtime.drive(self.run)
        second = self.runtime.drive(self.runtime.start())
        with self.runtime.connect() as db:
            row = db.execute('SELECT state_json FROM orchestration_results WHERE run_id=? LIMIT 1', (self.run_id,)).fetchone()
            value = json.loads(row[0]); value['task_id'] = second['tasks'][0]['task_id']
            db.execute('UPDATE orchestration_results SET state_json=? WHERE result_id=?', (json.dumps(value), value['result_id']))
        with self.assertRaises(AnalysisContractError) as error:
            self.viewer.saved_export('conversation', self.run_id)
        self.assertEqual(error.exception.code, 'history_integrity_mismatch')

    def test_export_checks_cap_before_snapshot_allocation(self):
        with self.runtime.connect() as db:
            db.execute('UPDATE orchestration_initials SET snapshot_json=? WHERE initial_id=?',
                       (' ' * (32 * 1024 * 1024 + 1), self.run['initial_id']))
        self.viewer._snapshot = Mock(side_effect=AssertionError('Snapshot parsed before SQL limit guard'))
        with self.assertRaises(AnalysisContractError) as error:
            self.viewer.saved_export('conversation', self.run_id)
        self.assertEqual(error.exception.code, 'history_export_limit')
        self.viewer._snapshot.assert_not_called()

    def test_provider_patch_operation_validation(self):
        def agent(role, context, *_):
            if role == 'core':
                return core(intents=[intent('interpretation')])
            return {'summary': 'bad operation', 'label_patches': [{'utterance_id': 'u1', 'field': 'codes',
                'old_value': ['manual'], 'new_value': ['ignored'], 'operation': 'purge', 'reason': 'Reason',
                'evidence_ids': [context['raw_evidence'][0]['evidence_id']], 'base_annotation_version': 0, 'codebook_version': 1}]}
        self.runtime.agent = agent
        run = self.runtime.drive(self.run)
        self.assertTrue(any(r.get('error') == 'invalid_label_patch' for r in run['results']))
        self.assertEqual(self.audit(), [])


if __name__ == '__main__':
    unittest.main()
