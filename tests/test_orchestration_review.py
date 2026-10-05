"""Independent adversarial review: synthetic SQLite/input only, no external AI."""
import copy
import contextlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.analysis_orchestration import AnalysisOrchestrationService, recover_orchestration_runs
from gurumoji.services.ai.client import extract_ai_token_usage


class OrchestrationReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'synthetic.sqlite'
        self.item = {'id': 'synthetic', 'revision_count': 2, 'analysis_revision': 3}
        self.snapshot = {
            'input_hash': 'sha256:synthetic-input', 'source_revision': 2, 'analysis_revision': 3,
            'analysis': {'segments': [{'id': 'u1', 'text': 'synthetic text', 'speaker': 'A',
                'start': 0, 'end': 1, 'annotation': {'codes': ['existing'], 'memo': 'human'},
                'excluded': False}], 'annotations': {'u1': {'codes': ['existing'], 'memo': 'human'}},
                'insights': {'ai': {'secret_conclusion': 'EXPECTED ANSWER'}}},
            'archive_snapshot': {'original_source': {'segments': [{'id': 'u1', 'text': 'synthetic text'}]}},
        }
        self.calls = []
        def agent(role, context, options, check, usage):
            self.calls.append((role, context, options))
            if role == 'core':
                return {'summary': 'synthetic observation', 'claims': [], 'intents': [],
                        'stop': {'reason': 'no_more_evidence', 'summary': 'done', 'unresolved': []},
                        'critique_responses': [], 'label_decisions': []}
            if role == 'critic':
                return {'summary': 'review', 'claims': [], 'label_patches': [], 'issues': [],
                        'review_status': 'no_issues', 'reviewed_scope': 'given view', 'limitations': ''}
            return {'summary': 'independent', 'claims': [], 'label_patches': []}
        self.service = AnalysisOrchestrationService(connect=self.connect, find_item=lambda _: self.item,
            source_fingerprint=lambda _: self.snapshot['input_hash'],
            snapshot_builder=lambda _: copy.deepcopy(self.snapshot), agent_runner=agent,
            method_runner=lambda method, snapshot: {'method': method}, schedule=False)

    def connect(self):
        connection = sqlite3.connect(self.db, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def start(self, **extra):
        return self.service.start('synthetic', {'question': 'Synthetic question', 'provider': 'lmstudio',
            'model': 'mock', 'max_iterations': 4, 'request_id': 'review-start',
            'source_revision': 2, 'analysis_revision': 3, **extra})

    def register(self, run, role, **extra):
        with self.service._db() as db:
            fixed = self.service._read_run(db, run['run_id'])
            return self.service._register(db, fixed, {'role': role, 'question': 'synthetic task',
                'why_now': 'test boundary', 'success_criteria': 'inspect evidence', **extra}, phase='specialists')

    def test_start_rejects_changed_source_revision_before_capture(self):
        with self.assertRaises(AnalysisContractError):
            self.start(source_revision=1)
        self.assertEqual(self.calls, [])

    def test_start_rejects_changed_analysis_revision_before_capture(self):
        with self.assertRaises(AnalysisContractError):
            self.start(analysis_revision=2)

    def test_request_id_cannot_silently_change_requested_source_version(self):
        self.start()
        with self.assertRaises(AnalysisContractError):
            self.start(source_revision=1)

    def test_source_codebook_version_is_preserved(self):
        self.snapshot['analysis']['config'] = {'codebook_version': 7}
        self.snapshot['analysis']['manual'] = {'codebook_version': 7}
        run = self.start()
        self.assertEqual(run['codebook_version'], 7)

    def test_unknown_provider_usage_does_not_become_measured_zero(self):
        run = self.start()
        usage = extract_ai_token_usage('lmstudio', 'mock', {}, {'lmstudio'})
        self.assertIs(usage['reported'], False)
        self.service._record_usage(run['run_id'], 'synthetic-task', usage)
        public = self.service.status('synthetic', run['run_id'])
        self.assertIsNone(public['usage']['total_tokens'], public['usage'])
        self.assertEqual(public['usage']['measured_calls'], 0)

    def test_source_human_annotations_survive_initial_label_version(self):
        run = self.start()
        exported = self.service.result('synthetic', run['run_id'])
        self.assertEqual(exported['label_versions'][0]['labels']['u1']['codes'], ['existing'])
        self.assertEqual(exported['label_versions'][0]['labels']['u1']['memo'], 'human')

    def test_core_stop_has_bounded_review_and_read_only_polling(self):
        run = self.start()
        self.service.run(run['run_id'])
        before = len(self.calls)
        for _ in range(5):
            state = self.service.status('synthetic', run['run_id'])
            self.service.history('synthetic')
        self.assertEqual(len(self.calls), before)
        self.assertEqual(state['status'], 'completed', state)
        self.assertEqual([role for role, *_ in self.calls], ['core', 'critic', 'core', 'core'])

    def test_blind_packet_excludes_initial_and_core_conclusions(self):
        run = self.start()
        task = self.register(run, 'verification', question='EXPECTED ANSWER?')
        with self.service._db() as db:
            packet = self.service._context(db, self.service._read_run(db, run['run_id']), task)
        self.assertNotIn('EXPECTED ANSWER', json.dumps(packet))
        self.assertTrue(packet['blind_first'])
        self.assertTrue(packet['raw_evidence'])

    def test_result_task_exposes_committed_result_reference(self):
        run = self.start()
        self.service.run(run['run_id'])
        state = self.service.status('synthetic', run['run_id'])
        for task in state['tasks']:
            if task['status'] == 'succeeded':
                self.assertIn('result_id', task, task)
                result = self.service.result('synthetic', run['run_id'], task['result_id'])
                self.assertEqual(result['task_id'], task['task_id'])

    def test_wrong_item_cannot_read_or_cancel_run(self):
        run = self.start()
        for call in (lambda: self.service.status('other', run['run_id']),
                     lambda: self.service.cancel('other', run['run_id']),
                     lambda: self.service.result('other', run['run_id'])):
            with self.assertRaises(LookupError):
                call()

    def test_critic_issue_state_requires_at_least_one_issue(self):
        run = self.start()
        task = self.register(run, 'critic', target_id='view:' + run['run_id'], target_version=1)
        with self.service._db() as db:
            fixed = self.service._read_run(db, run['run_id'])
            with self.assertRaises(AnalysisContractError):
                self.service._validate_result(db, fixed, task, {'review_status': 'issues',
                    'reviewed_scope': 'current view', 'issues': []})

    def test_response_returning_after_call_timeout_is_not_adopted(self):
        run = self.start(call_timeout_seconds=1)
        task = self.register(run, 'interpretation')
        clock = [100.0]
        def delayed(role, context, options, check, usage):
            clock[0] = 102.0
            return {'summary': 'synthetic late result', 'claims': []}
        self.service.agent_runner = delayed
        with patch('gurumoji.analysis_orchestration.time.time', side_effect=lambda: clock[0]):
            self.service._execute(run['run_id'], task['task_id'])
        state = self.service.status('synthetic', run['run_id'])
        self.assertEqual(state['stop_reason'], 'call_timeout')
        self.assertEqual(state['results'][0]['validation_status'], 'quarantined')

    def test_response_returning_after_deadline_is_not_adopted(self):
        run = self.start()
        task = self.register(run, 'interpretation')
        with self.service._db() as db:
            fixed = self.service._read_run(db, run['run_id'])
            fixed['deadline'] = 101.0
            self.service._write_run(db, fixed)
        clock = [100.0]
        def delayed(role, context, options, check, usage):
            clock[0] = 102.0
            return {'summary': 'synthetic late result', 'claims': []}
        self.service.agent_runner = delayed
        with patch('gurumoji.analysis_orchestration.time.time', side_effect=lambda: clock[0]):
            self.service._execute(run['run_id'], task['task_id'])
        state = self.service.status('synthetic', run['run_id'])
        self.assertEqual(state['stop_reason'], 'time_limit')
        self.assertEqual(state['results'][0]['validation_status'], 'quarantined')

    def test_complete_export_contains_every_saved_raw_result(self):
        run = self.start()
        self.service.run(run['run_id'])
        exported = self.service.result('synthetic', run['run_id'])
        exported_raw = {}
        def collect(value):
            if isinstance(value, dict):
                if 'result_id' in value and 'raw' in value:
                    exported_raw[value['result_id']] = value['raw']
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
        collect(exported)
        state = self.service.status('synthetic', run['run_id'])
        self.assertEqual(len(exported_raw), len(state['results']), 'Complete export dropped raw task responses')
        for meta in state['results']:
            saved = self.service.result('synthetic', run['run_id'], meta['result_id'])
            self.assertEqual(exported_raw[meta['result_id']], saved['raw'])

    def test_received_result_hash_corruption_is_quarantined(self):
        run = self.start()
        task = self.register(run, 'interpretation')
        with patch.object(self.service, '_validate_received', return_value=None):
            self.service._execute(run['run_id'], task['task_id'])
        with contextlib.closing(self.connect()) as db, db:
            raw = json.loads(db.execute('SELECT raw_json FROM orchestration_results WHERE task_id=?',
                                        (task['task_id'],)).fetchone()[0])
            raw['summary'] = 'modified after raw commit'
            db.execute('UPDATE orchestration_results SET raw_json=? WHERE task_id=?',
                       (json.dumps(raw), task['task_id']))
        self.service._validate_received(run['run_id'], task['task_id'])
        final = self.service.status('synthetic', run['run_id'])
        self.assertEqual(final['results'][0]['validation_status'], 'quarantined')

    def test_validated_result_is_rechecked_before_post_restart_adoption(self):
        run = self.start()
        with self.service._db() as db:
            fixed = self.service._read_run(db, run['run_id'])
            fixed.update(iteration=1, phase='core', status='running')
            task = self.service._register(db, fixed, {'role': 'core', 'question': 'Synthetic question'},
                                          phase='core', automatic=True)
            self.service._write_run(db, fixed)
        self.service._execute(run['run_id'], task['task_id'])
        self.assertEqual(len(self.calls), 1)
        with contextlib.closing(self.connect()) as db, db:
            raw = json.loads(db.execute('SELECT raw_json FROM orchestration_results WHERE task_id=?',
                                        (task['task_id'],)).fetchone()[0])
            raw['summary'] = 'corrupted after validation, before Core adoption'
            db.execute('UPDATE orchestration_results SET raw_json=? WHERE task_id=?',
                       (json.dumps(raw), task['task_id']))
            recover_orchestration_runs(db)
        self.service.resume('synthetic', run['run_id'])
        self.service.run(run['run_id'])
        self.assertEqual(len(self.calls), 1, 'Corrupted validated result must not authorize further AI calls')
        final = self.service.status('synthetic', run['run_id'])
        self.assertEqual(final['results'][0]['validation_status'], 'quarantined')
        self.assertNotIn('corrupted after validation', json.dumps(final['current_view']))

    def test_incompatible_schema_version_cannot_resume(self):
        run = self.start()
        with self.service._db() as db:
            fixed = self.service._read_run(db, run['run_id'])
            fixed.update(status='recovery_required', schema_version=999)
            self.service._write_run(db, fixed)
        with self.assertRaises(AnalysisContractError):
            self.service.resume('synthetic', run['run_id'])
        self.assertEqual(len(self.calls), 0)

    def test_incompatible_adapter_version_cannot_resume(self):
        run = self.start()
        with self.service._db() as db:
            fixed = self.service._read_run(db, run['run_id'])
            fixed.update(status='recovery_required')
            fixed['config']['adapter_version'] = 'older-incompatible-prompt'
            self.service._write_run(db, fixed)
        with self.assertRaises(AnalysisContractError):
            self.service.resume('synthetic', run['run_id'])
        self.assertEqual(len(self.calls), 0)

    def test_received_core_result_resumes_without_reexecuting_call(self):
        run = self.start()
        with self.service._db() as db:
            fixed = self.service._read_run(db, run['run_id'])
            fixed.update(iteration=1, phase='core', status='running')
            task = self.service._register(db, fixed, {'role': 'core', 'question': 'Synthetic question'},
                                          phase='core', automatic=True)
            self.service._write_run(db, fixed)
        with patch.object(self.service, '_validate_received', return_value=None):
            self.service._execute(run['run_id'], task['task_id'])
        self.assertEqual(len(self.calls), 1)
        with self.service._db() as db:
            recover_orchestration_runs(db)
        self.service.resume('synthetic', run['run_id'])
        self.service.run(run['run_id'])
        final = self.service.status('synthetic', run['run_id'])
        self.assertEqual(final['status'], 'completed', final)
        self.assertEqual([role for role, *_ in self.calls], ['core', 'critic', 'core', 'core'])
        self.assertEqual(final['tasks'][0]['task_id'], task['task_id'])

    def test_deleted_source_fences_late_result_and_all_reads(self):
        run = self.start()
        task = self.register(run, 'interpretation')
        existing_item = self.item
        def delete_during_call(role, context, options, check, usage):
            self.item = None
            return {'summary': 'late result after source deletion', 'claims': []}
        self.service.agent_runner = delete_during_call
        self.service._execute(run['run_id'], task['task_id'])
        for reader in (lambda: self.service.status('synthetic', run['run_id']),
                       lambda: self.service.history('synthetic'),
                       lambda: self.service.result('synthetic', run['run_id'])):
            with self.assertRaises(LookupError):
                reader()
        self.item = existing_item
        final = self.service.status('synthetic', run['run_id'])
        self.assertEqual(final['stop_reason'], 'source_deleted')
        self.assertEqual(final['results'][0]['validation_status'], 'quarantined')

    def test_snapshot_hash_corruption_blocks_ai_dispatch(self):
        run = self.start()
        with contextlib.closing(self.connect()) as db, db:
            value = json.loads(db.execute('SELECT snapshot_json FROM orchestration_initials WHERE initial_id=?',
                                         (run['initial_id'],)).fetchone()[0])
            value['analysis']['segments'][0]['text'] = 'corrupted synthetic bytes'
            db.execute('UPDATE orchestration_initials SET snapshot_json=? WHERE initial_id=?',
                       (json.dumps(value), run['initial_id']))
        self.service.run(run['run_id'])
        self.assertEqual(len(self.calls), 0, 'Corrupted initial snapshot must not reach an agent')

    def test_late_response_after_cancel_is_preserved_but_quarantined(self):
        run = self.start()
        task = self.register(run, 'interpretation')
        def late(role, context, options, check, usage):
            self.service.cancel('synthetic', run['run_id'])
            return {'summary': 'late synthetic result', 'claims': []}
        self.service.agent_runner = late
        self.service._execute(run['run_id'], task['task_id'])
        state = self.service.status('synthetic', run['run_id'])
        self.assertEqual(state['status'], 'cancelled')
        self.assertEqual(state['results'][0]['validation_status'], 'quarantined')
        self.assertEqual(state['tasks'][0]['status'], 'quarantined')


if __name__ == '__main__':
    unittest.main()
