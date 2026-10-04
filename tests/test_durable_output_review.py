"""Independent adversarial review using synthetic SQLite and temporary Vaults only."""
import copy
import json
import threading
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support
import gurumoji.research_analysis as research
from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.analysis_store import AnalysisStore, StoreConflict
from gurumoji.services.analysis_orchestration_publication import AnalysisOrchestrationPublicationService
from gurumoji.services.analysis_pipeline_adapters import make_staged_initial_builder
from gurumoji.vault_registry import VaultRegistry


class DurableOutputReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests('test_generated_result_persists_and_becomes_stale_on_edit')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.calls = []
        self.snapshot_calls = []
        item = app.library_row('content')
        self.snapshot = {
            'input_hash': app.archive_source_stamp(item),
            'source_revision': item['revision_count'], 'analysis_revision': item['analysis_revision'],
            'analysis': {'segments': [{'id': 'a1', 'text': 'observed synthetic source',
                'speaker': 'A', 'start': 0, 'end': 2, 'excluded': False,
                'annotation': {'memo': 'synthetic human annotation'}}]},
            'archive_snapshot': {'title': 'synthetic review', 'conversation_id': 'content',
                'segments': [{'id': 'a1', 'text': 'observed synthetic source', 'speaker': 'A',
                              'start': 0, 'end': 2, 'excluded': False}],
                'original_source': {'segments': [{'id': 'a1', 'text': 'earlier synthetic source'}]}},
        }
        def snapshot_builder(item):
            self.snapshot_calls.append(item['id'])
            return copy.deepcopy(self.snapshot)
        def agent(role, context, options, check, usage):
            self.calls.append(role)
            evidence = context['raw_evidence'][0]['evidence_id']
            claim = {'claim_id': 'observed', 'text': 'An observed synthetic finding',
                     'kind': 'observation', 'evidence_ids': [evidence]}
            if role == 'core':
                return {'summary': 'Synthetic conclusion', 'claims': [claim], 'intents': [],
                    'stop': {'reason': 'question_satisfied', 'summary': 'done', 'unresolved': []},
                    'critique_responses': [], 'label_decisions': []}
            return {'summary': 'Synthetic review', 'claims': [claim], 'label_patches': [],
                    'issues': [], 'review_status': 'no_issues', 'reviewed_scope': 'synthetic', 'limitations': ''}
        self.runtime = AnalysisOrchestrationService(connect=app.database_connection,
            find_item=app.library_row, source_fingerprint=app.archive_source_stamp,
            snapshot_builder=snapshot_builder, agent_runner=agent,
            method_runner=lambda *args: self.fail('Unexpected statistics recalculation'),
            write_lock=app.library_write_lock, schedule=False)
        def source_guard(db, item_id, input_hash):
            row = db.execute('SELECT * FROM library_items WHERE id=?', (item_id,)).fetchone()
            if row is None:
                raise LookupError('Deleted source')
            if app.archive_source_stamp(row, connection=db) != input_hash:
                raise AnalysisContractError('Source changed', code='revision_conflict')
        self.output = AnalysisOrchestrationPublicationService(connect=app.database_connection,
            store_factory=app.analysis_archive_store, source_guard=source_guard,
            export_locked=self.runtime.result_locked, write_lock=app.library_write_lock)
        self.store = app.analysis_archive_store()

    def completed(self, targets=None):
        run = self.runtime.start('content', {'request_id': 'independent-review',
            'provider': 'lmstudio', 'model': 'synthetic', 'question': 'Observe synthetic text',
            'publication_targets': [] if targets is None else targets})
        self.runtime.run(run['run_id'])
        self.assertEqual(self.runtime.status('content', run['run_id'])['status'], 'completed')
        return run['run_id']

    def test_default_off_stays_off_via_generic_publish_retry_and_refresh(self):
        rid = self.completed()
        with patch.object(VaultRegistry, 'publish_analysis') as generated, patch.object(AnalysisStore, 'source_notes') as research:
            result = self.output.finalize('content', rid)
            saved_id = result['result_run_id']
            self.assertEqual(result['save_status'], 'saved', result)
            self.store.publish(saved_id)
            self.store.retry(saved_id)
            self.store.refresh_vaults('content')
            with self.assertRaises(StoreConflict):
                self.store.publish(saved_id, targets=['input', 'orchestrator', 'visualization'])
            generated.assert_not_called(); research.assert_not_called()

    def test_legacy_completed_run_can_save_with_default_off_scope(self):
        rid = self.completed()
        with self.runtime._db() as db:
            run = self.runtime._read_run(db, rid)
            run['config'].pop('publication_targets', None)
            run['config'].pop('effective_publication_writers', None)
            self.runtime._write_run(db, run)
        with patch.object(VaultRegistry, 'publish_analysis') as generated, patch.object(AnalysisStore, 'source_notes') as research:
            result = self.output.finalize('content', rid)
            self.assertEqual((result['save_status'], result['publication_status']), ('saved', 'not_selected'), result)
            self.assertEqual(result['effective_writers'], [])
            generated.assert_not_called(); research.assert_not_called()

    def test_sealed_export_is_not_replaced_by_late_live_ledger_updates(self):
        rid = self.completed()
        result = self.output.finalize('content', rid)
        saved_id = result['result_run_id']
        original = self.store.verified_package(saved_id)[1]['orchestration']
        with self.runtime._db() as db:
            self.runtime._event(db, rid, 'late_review_marker', 'Synthetic late event')
        before = (list(self.calls), list(self.snapshot_calls))
        with patch.object(self.output, 'export_locked', side_effect=AssertionError('Must reuse sealed output')):
            repeated = self.output.retry('content', rid)
        self.assertEqual(repeated['sealed_hash'], result['sealed_hash'])
        self.assertEqual(self.store.verified_package(saved_id)[1]['orchestration'], original)
        self.assertEqual((self.calls, self.snapshot_calls), before)
        self.assertTrue(any(e['type'] == 'late_review_marker' for e in self.runtime.status('content', rid)['events']))

    def test_corrupted_raw_result_is_rejected_before_any_output_or_writer(self):
        rid = self.completed(['input', 'orchestrator', 'visualization'])
        with app.database_connection() as db:
            row = db.execute('SELECT result_id,raw_json FROM orchestration_results WHERE run_id=? LIMIT 1', (rid,)).fetchone()
            raw = json.loads(row['raw_json']); raw['summary'] = 'corrupted synthetic payload'
            db.execute('UPDATE orchestration_results SET raw_json=? WHERE result_id=?', (json.dumps(raw), row['result_id']))
        with patch.object(AnalysisStore, 'save') as save, patch.object(VaultRegistry, 'publish_analysis') as generated:
            with self.assertRaises(StoreConflict):
                self.output.finalize('content', rid)
            save.assert_not_called(); generated.assert_not_called()

    def test_partial_failure_retry_keeps_same_package_and_all_observed_quotations(self):
        rid = self.completed(['input', 'orchestrator', 'visualization'])
        with patch.object(AnalysisStore, 'source_notes', side_effect=StoreConflict('synthetic conflict')):
            first = self.output.finalize('content', rid)
        self.assertEqual((first['save_status'], first['publication_status']), ('saved', 'incomplete'), first)
        calls = (list(self.calls), list(self.snapshot_calls))
        retried = self.output.retry('content', rid)
        self.assertEqual((retried['save_status'], retried['publication_status']), ('saved', 'published'), retried)
        self.assertEqual(first['result_run_id'], retried['result_run_id'])
        self.assertEqual(first['sealed_hash'], retried['sealed_hash'])
        self.assertEqual((self.calls, self.snapshot_calls), calls)
        result = self.store.verified_package(retried['result_run_id'])[1]
        evidence = result['methods'][0]['details']['evidence']
        self.assertEqual(evidence['a1']['text'], 'observed synthetic source')
        self.assertEqual(len(self.store.publication_attempts(retried['result_run_id'])), 2)

    def test_generic_publication_cannot_write_after_source_deletion(self):
        rid = self.completed(['input', 'orchestrator', 'visualization'])
        saved = self.output.finalize('content', rid)['result_run_id']
        with app.database_connection() as db:
            db.execute("DELETE FROM library_items WHERE id='content'")
        with patch.object(VaultRegistry, 'publish_analysis') as generated, patch.object(AnalysisStore, 'source_notes') as research:
            with self.assertRaises((StoreConflict, LookupError, AnalysisContractError)):
                self.store.publish(saved)
            generated.assert_not_called(); research.assert_not_called()

    def test_generic_publication_cannot_write_after_run_generation_changes(self):
        rid = self.completed(['input', 'orchestrator', 'visualization'])
        saved = self.output.finalize('content', rid)['result_run_id']
        with self.runtime._db() as db:
            run = self.runtime._read_run(db, rid)
            run['generation'] += 1
            self.runtime._write_run(db, run)
        with patch.object(VaultRegistry, 'publish_analysis') as generated, patch.object(AnalysisStore, 'source_notes') as research:
            with self.assertRaises((StoreConflict, AnalysisContractError)):
                self.store.publish(saved)
            generated.assert_not_called(); research.assert_not_called()

    def test_simultaneous_retries_publish_one_package_once_without_reanalysis(self):
        rid = self.completed(['input', 'orchestrator', 'visualization'])
        with patch.object(AnalysisStore, 'source_notes', side_effect=StoreConflict('synthetic conflict')):
            first = self.output.finalize('content', rid)
        results, errors = [], []
        barrier = threading.Barrier(2)
        before = (list(self.calls), list(self.snapshot_calls))
        def retry():
            try:
                barrier.wait(5)
                results.append(self.output.retry('content', rid))
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=retry) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result['publication_status'] == 'published' for result in results))
        self.assertTrue(all(result['result_run_id'] == first['result_run_id'] for result in results))
        self.assertEqual(len(self.store.publication_attempts(first['result_run_id'])), 2)
        self.assertEqual((self.calls, self.snapshot_calls), before)


class StagedInitialReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests('test_generated_result_persists_and_becomes_stale_on_edit')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.stage_calls, self.ai_calls = [], []
        self.builder = make_staged_initial_builder(archive_snapshot=app.archive_snapshot,
            archive_source_stamp=app.archive_source_stamp, group_analysis_for_row=app.group_analysis_for_row)
        self.real_stage = self.builder.run_stage
        def stage(stage_id, frozen, outputs):
            self.stage_calls.append(stage_id)
            return self.real_stage(stage_id, frozen, outputs)
        self.builder.run_stage = stage
        def agent(role, context, options, check, usage):
            self.ai_calls.append(role)
            if role == 'core':
                return {'summary': 'Synthetic result', 'claims': [], 'intents': [],
                    'stop': {'reason': 'question_satisfied', 'summary': 'done', 'unresolved': []},
                    'critique_responses': [], 'label_decisions': []}
            return {'summary': 'Synthetic review', 'claims': [], 'label_patches': [], 'issues': [],
                    'review_status': 'no_issues', 'reviewed_scope': 'synthetic', 'limitations': ''}
        self.service = AnalysisOrchestrationService(connect=app.database_connection,
            find_item=app.library_row, source_fingerprint=app.archive_source_stamp,
            snapshot_builder=lambda item: self.fail('Monolithic snapshot must not run'),
            initial_builder=self.builder, agent_runner=agent, method_runner=lambda *args: {},
            write_lock=app.library_write_lock, schedule=False)

    def start(self, request='staged-independent-review'):
        return self.service.start('content', {'request_id': request, 'provider': 'lmstudio',
            'model': 'synthetic', 'question': 'Observe synthetic text'})

    def fail_snapshot(self):
        normal = self.builder.run_stage
        def injected(stage_id, frozen, outputs):
            if stage_id == 'snapshot':
                raise RuntimeError('Synthetic final-stage failure')
            return normal(stage_id, frozen, outputs)
        self.builder.run_stage = injected
        run = self.start()
        self.service.run(run['run_id'])
        self.builder.run_stage = normal
        state = self.service.status('content', run['run_id'])
        self.assertEqual((state['status'], state['phase']), ('recovery_required', 'initial'), state)
        self.assertEqual(self.ai_calls, [])
        return state

    def test_real_statistics_execute_once_across_snapshot_failure_and_resume(self):
        with patch.object(research, '_statistics_analysis', wraps=research._statistics_analysis) as statistics:
            initial = self.fail_snapshot()
            self.assertEqual(statistics.call_count, 1)
            preserved = {s['stage_id']: s['output_hash'] for s in initial['initial_stages'] if s['status'] == 'completed'}
            self.service.resume('content', initial['run_id'])
            self.service.run(initial['run_id'])
            final = self.service.status('content', initial['run_id'])
            self.assertEqual(final['status'], 'completed', final)
            self.assertEqual(statistics.call_count, 1)
        self.assertEqual(self.stage_calls, ['base', 'linguistics', 'statistics', 'content', 'snapshot'])
        self.assertEqual({s['stage_id']: s['output_hash'] for s in final['initial_stages'] if s['stage_id'] in preserved}, preserved)
        self.assertTrue(all(s['attempt_count'] == 1 for s in final['initial_stages'] if s['stage_id'] != 'snapshot'))

    def test_corrupt_completed_stage_never_reexecutes_and_disables_resume(self):
        run = self.fail_snapshot()
        with app.database_connection() as db:
            db.execute("UPDATE orchestration_initial_stages SET output_json='{}' WHERE initial_id=? AND stage_id='statistics'", (run['initial_id'],))
        calls = list(self.stage_calls)
        self.assertFalse(self.service.status('content', run['run_id'])['can_resume'])
        with self.assertRaises(AnalysisContractError):
            self.service.resume('content', run['run_id'])
        self.assertEqual(self.stage_calls, calls)

    def test_algorithm_version_change_blocks_completed_checkpoint_reuse(self):
        run = self.fail_snapshot()
        self.builder.version += ':different'
        with self.assertRaises(AnalysisContractError) as error:
            self.service.resume('content', run['run_id'])
        self.assertEqual(error.exception.code, 'initial_version_conflict')
        self.assertFalse(self.service.status('content', run['run_id'])['can_resume'])

    def test_cache_hit_performs_no_freeze_or_initial_stage_side_effects(self):
        run = self.start()
        self.service.run(run['run_id'])
        original = self.service.result('content', run['run_id'])['initial']
        with patch.object(self.builder, 'freeze', side_effect=AssertionError('Cache hit must not freeze')), \
                patch.object(self.builder, 'run_stage', side_effect=AssertionError('Cache hit must not calculate')):
            reused = self.start('same-input-new-question-run')
            self.assertEqual(self.service.result('content', reused['run_id'])['initial'], original)

    def test_cancel_running_initial_stage_retains_completed_output_but_starts_no_ai(self):
        entered, release = threading.Event(), threading.Event()
        normal = self.builder.run_stage
        def blocked(stage_id, frozen, outputs):
            if stage_id == 'statistics':
                entered.set()
                if not release.wait(5):
                    raise AssertionError('Test release timed out')
            return normal(stage_id, frozen, outputs)
        self.builder.run_stage = blocked
        run = self.start()
        thread = threading.Thread(target=self.service.run, args=(run['run_id'],))
        thread.start()
        try:
            self.assertTrue(entered.wait(5))
            self.assertEqual(self.service.cancel('content', run['run_id'])['status'], 'cancelled')
        finally:
            release.set(); thread.join(5)
        self.assertFalse(thread.is_alive())
        final = self.service.status('content', run['run_id'])
        self.assertEqual(final['status'], 'cancelled')
        self.assertEqual(self.ai_calls, [])
        self.assertNotIn('content', self.stage_calls)
        stages = {s['stage_id']: s for s in final['initial_stages']}
        self.assertEqual(stages['statistics']['status'], 'completed')

    def test_run_exists_before_first_stage_and_same_request_starts_once(self):
        runs, errors = [], []
        barrier = threading.Barrier(2)
        def start():
            try:
                barrier.wait(5)
                runs.append(self.start())
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=start) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(5)
        self.assertEqual(errors, [])
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0]['run_id'], runs[1]['run_id'])
        self.assertEqual(self.stage_calls, [])
        self.assertEqual(runs[0]['initial']['completed_stages'], 0)
        normal = self.builder.run_stage
        def check_saved(stage_id, frozen, outputs):
            with app.database_connection() as db:
                self.assertIsNotNone(db.execute('SELECT 1 FROM orchestration_runs WHERE run_id=?', (runs[0]['run_id'],)).fetchone())
            return normal(stage_id, frozen, outputs)
        self.builder.run_stage = check_saved
        self.service.run(runs[0]['run_id'])
        self.assertEqual(self.stage_calls, ['base', 'linguistics', 'statistics', 'content', 'snapshot'])


if __name__ == '__main__':
    unittest.main()
