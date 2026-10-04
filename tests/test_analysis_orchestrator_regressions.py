"""Evaluation regressions: synthetic input, temporary SQLite and writer doubles only."""
import copy
import json
import unittest
from unittest.mock import patch

import test_analysis_definition_safety as support
from gurumoji.analysis_core import AnalysisContractError, PUBLICATION_TARGETS, EFFECTIVE_PUBLICATION_WRITERS
from gurumoji.analysis_pipeline import ACTIVE_STEP_STATES, measure_segments
from gurumoji.analysis_method_registry import method_results
from gurumoji.analysis_store import AnalysisStore, initialize_store


class OrchestratorRegressionTests(unittest.TestCase):
    setUp = support.DefinitionSafetyTests.setUp
    connect = support.DefinitionSafetyTests.connect
    save_result = support.DefinitionSafetyTests.save_result
    payload = support.DefinitionSafetyTests.payload
    start = support.DefinitionSafetyTests.start

    def run_pipeline(self, pipeline_id):
        self.service._run_guarded(pipeline_id, 'http://synthetic.invalid', 'synthetic-runtime',
                                  self.service._pipeline_row(pipeline_id)['generation'])
        return self.service.status('synthetic', pipeline_id, ensure_running=False)

    def steps(self, pipeline_id):
        return [s for m in self.service.status('synthetic', pipeline_id, ensure_running=False)['milestones'] for s in m['steps']]

    def test_no_effective_input_is_rejected_without_saving(self):
        for segments in ([], [{**self.snapshot['analysis']['segments'][0], 'excluded': True}]):
            with self.subTest(segments=segments):
                self.snapshot['analysis']['segments'] = segments
                preview = self.service.preview('synthetic', self.payload(definition_ids=[], mode='automatic'))
                self.assertEqual(preview['plan']['eligibility']['execution'], 'blocked')
                self.assertEqual(preview['plan']['eligibility']['checks'][0]['reason_code'], 'no_valid_input')
                with self.assertRaises(AnalysisContractError) as caught:
                    self.start(definition_ids=[], mode='automatic')
                self.assertEqual(caught.exception.code, 'ineligible')
        self.assertEqual(self.saved, [])
        with self.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM analysis_pipeline_requests').fetchone()[0], 0)

    def test_partial_exclusion_uses_same_rows_for_eligibility_and_measurement(self):
        segment = self.snapshot['analysis']['segments'][0]
        self.snapshot['analysis']['segments'] = [dict(segment, excluded=True), dict(segment, id='included')]
        definition = support.definition(version=1)
        rows = measure_segments(self.snapshot['analysis'], [definition])
        self.assertEqual([r['segment_id'] for r in rows], ['included'])
        from gurumoji.analysis_pipeline import build_plan_envelope
        with patch('gurumoji.analysis_pipeline.build_plan_envelope', wraps=build_plan_envelope) as build:
            self.service.preview('synthetic', self.payload(definition_ids=[], mode='automatic'))
        self.assertEqual(build.call_args.kwargs['segment_count'], len(rows))
        self.assertEqual(self.run_pipeline(self.start(definition_ids=[], mode='automatic'))['status'], 'completed')

    def test_summary_schema_rows_do_not_make_empty_participation_completed(self):
        analysis = {'segments': [{'id': 'excluded', 'excluded': True}]}
        methods = method_results(analysis, {'summary': (['metric', 'value'], [{'metric': 'included', 'value': 0}])})
        self.assertEqual(next(m['status'] for m in methods if m['method_id'] == 'participation'), 'empty')

    def test_previously_accepted_empty_snapshot_cannot_execute(self):
        pid = self.start(definition_ids=[], mode='automatic')
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['analysis']['segments'][0]['excluded'] = True
        with self.connect() as connection:
            connection.execute('UPDATE analysis_pipeline_requests SET snapshot_json=? WHERE pipeline_id=?', (json.dumps(snapshot), pid))
        with patch.object(self.service, 'method_runner') as runner:
            state = self.run_pipeline(pid)
        self.assertEqual(state['status'], 'failed')
        self.assertEqual(self.saved, [])
        runner.assert_not_called()

    def test_cancellation_at_each_step_transition_is_terminal_and_retryable(self):
        for target in ('checking', 'ready', 'running', 'validating', 'persisting', 'committed'):
            with self.subTest(target=target):
                fixture = OrchestratorRegressionTests()
                fixture.setUp()
                try:
                    pid = fixture.start(definition_ids=[], mode='automatic')
                    original = fixture.service._set_step
                    seen = []
                    def cancel_before(attempt_id, status, **kwargs):
                        if status == target and not seen:
                            seen.append(attempt_id)
                            fixture.service.cancel('synthetic', pid)
                        return original(attempt_id, status, **kwargs)
                    with patch.object(fixture.service, '_set_step', side_effect=cancel_before):
                        state = fixture.run_pipeline(pid)
                    self.assertEqual(state['status'], 'cancelled', state)
                    self.assertTrue(seen)
                    self.assertFalse(any(s['status'] in ACTIVE_STEP_STATES for s in fixture.steps(pid)))
                    self.assertTrue(all(s['ended_at'] for s in fixture.steps(pid) if s['status'] == 'cancelled'))
                    fixture.service.retry('synthetic', pid, {}, app_url='http://synthetic.invalid')
                    self.assertEqual(fixture.run_pipeline(pid)['status'], 'completed')
                finally:
                    fixture.doCleanups()

    def test_cancel_after_commit_preserves_success_and_artifact_on_retry(self):
        pid = self.start(definition_ids=[], mode='automatic')
        original = self.service._set_step
        committed = []
        def cancel_after(attempt_id, status, **kwargs):
            result = original(attempt_id, status, **kwargs)
            if status == 'committed' and not committed:
                committed.append(attempt_id)
                self.service.cancel('synthetic', pid)
            return result
        with patch.object(self.service, '_set_step', side_effect=cancel_after):
            self.assertEqual(self.run_pipeline(pid)['status'], 'cancelled')
        with self.connect() as connection:
            before = tuple(connection.execute('SELECT status,artifact_json,attempt FROM analysis_step_attempts WHERE attempt_id=?', (committed[0],)).fetchone())
        self.service.retry('synthetic', pid, {}, app_url='http://synthetic.invalid')
        self.assertEqual(self.run_pipeline(pid)['status'], 'completed')
        with self.connect() as connection:
            after = tuple(connection.execute('SELECT status,artifact_json,attempt FROM analysis_step_attempts WHERE attempt_id=?', (committed[0],)).fetchone())
        self.assertEqual(before, after)
        self.assertEqual(before[0], 'committed')

    def configure_store(self):
        with self.connect() as connection:
            connection.execute('CREATE TABLE application_metadata(key TEXT PRIMARY KEY,value TEXT)')
            connection.execute('CREATE TABLE library_items(id TEXT PRIMARY KEY)')
            connection.execute('CREATE TABLE speaker_registry(id TEXT PRIMARY KEY)')
            initialize_store(connection)
        store = AnalysisStore(self.db, self.connect)
        self.service.save_result = store.save
        self.service.publish_result = lambda run_id, **kwargs: store.publish(run_id, reuse_completed=True, **kwargs)
        self.service.publication_outcomes = store.publication_outcomes
        self.service.public_run = lambda row: store.get(row['id'])
        def generated(run_id):
            store._last_publication_outcomes[run_id] = {k: {'status': 'published', 'error': ''} for k in PUBLICATION_TARGETS}
            return {k: 'published' for k in PUBLICATION_TARGETS}
        store._publish_generated_vaults = generated
        store._publish_research = lambda _: {'vault_status': 'completed', 'error': ''}
        return store

    def test_cancel_after_publication_commit_records_outcomes_without_duplicate_writes(self):
        store = self.configure_store()
        pid = self.start(definition_ids=[], mode='automatic', publication_targets=list(PUBLICATION_TARGETS))
        def cancel_after(run_id):
            self.service.cancel('synthetic', pid)
            return store.publication_outcomes(run_id)
        self.service.publication_outcomes = cancel_after
        state = self.run_pipeline(pid)
        self.assertEqual(state['status'], 'cancelled')
        run_id = state['result_run']['id']
        attempt = store.publication_attempts(run_id)[-1]
        self.assertEqual(attempt['status'], 'completed')
        self.assertTrue(store.verified_package(run_id))
        self.assertEqual({p['target_role']: p['status'] for p in state['publications']},
                         {k: v['status'] for k, v in attempt['outcomes'].items()})
        self.assertFalse(any(s['status'] in ACTIVE_STEP_STATES for s in self.steps(pid)))
        self.service.publication_outcomes = store.publication_outcomes
        self.service.retry('synthetic', pid, {}, app_url='http://synthetic.invalid')
        with patch.object(store, '_publish_generated_vaults') as publish, patch.object(self.service, 'save_result') as save:
            final = self.run_pipeline(pid)
        self.assertEqual(final['status'], 'completed', final)
        publish.assert_not_called(); save.assert_not_called()
        self.assertEqual(store.publication_attempts(run_id), [attempt])
        self.assertEqual(final['result_run']['id'], run_id)

    def test_published_retry_still_requires_fixed_package_integrity(self):
        for fault in ('missing_manifest', 'corrupt_result'):
            with self.subTest(fault=fault):
                fixture = OrchestratorRegressionTests()
                fixture.setUp()
                try:
                    store = fixture.configure_store()
                    pid = fixture.start(definition_ids=[], mode='automatic', publication_targets=list(PUBLICATION_TARGETS))
                    def cancel_after(run_id):
                        fixture.service.cancel('synthetic', pid)
                        return store.publication_outcomes(run_id)
                    fixture.service.publication_outcomes = cancel_after
                    state = fixture.run_pipeline(pid)
                    run_id = state['result_run']['id']
                    attempts = store.publication_attempts(run_id)
                    if fault in ('missing_manifest', 'corrupt_result'):
                        name = 'manifest.json' if fault == 'missing_manifest' else 'result.json'
                        artifact = next(a for a in store.artifacts(run_id) if a['name'] == name)
                        path = store.root / artifact['path']
                        if fault == 'missing_manifest':
                            path.unlink()
                        else:
                            path.write_bytes(b'{}')
                    fixture.service.publication_outcomes = store.publication_outcomes
                    fixture.service.retry('synthetic', pid, {}, app_url='http://synthetic.invalid')
                    with patch.object(store, '_publish_generated_vaults') as publish, patch.object(fixture.service, 'save_result') as save:
                        final = fixture.run_pipeline(pid)
                    self.assertEqual((final['status'], final['wait_reason']), ('waiting', 'publication'), final)
                    publish.assert_not_called(); save.assert_not_called()
                    self.assertEqual(store.publication_attempts(run_id)[:-1], attempts)
                    self.assertEqual(store.publication_attempts(run_id)[-1]['status'], 'blocked')
                    self.assertEqual({p['status'] for p in final['publications']}, {'failed'})
                finally:
                    fixture.doCleanups()

    def test_later_failed_publication_invalidates_prior_success_before_retry(self):
        store = self.configure_store()
        pid = self.start(definition_ids=[], mode='automatic', publication_targets=list(PUBLICATION_TARGETS))
        def cancel_after(run_id):
            self.service.cancel('synthetic', pid)
            return store.publication_outcomes(run_id)
        self.service.publication_outcomes = cancel_after
        state = self.run_pipeline(pid)
        run_id = state['result_run']['id']
        store._publish_research = lambda _: {'vault_status': 'conflict', 'error': 'synthetic newer conflict'}
        store.publish(run_id, targets=list(PUBLICATION_TARGETS))
        self.assertEqual(store.publication_outcomes(run_id)['research']['status'], 'conflict')
        self.service.publication_outcomes = store.publication_outcomes
        self.service.retry('synthetic', pid, {}, app_url='http://synthetic.invalid')
        final = self.run_pipeline(pid)
        self.assertEqual((final['status'], final['wait_reason']), ('waiting', 'publication'))
        self.assertEqual({p['target_role']: p['status'] for p in final['publications']}['research'], 'conflict')
        self.assertEqual(len(store.publication_attempts(run_id)), 3)

    def test_cancel_during_publication_preserves_mixed_durable_outcomes(self):
        store = self.configure_store()
        pid = self.start(definition_ids=[], mode='automatic', publication_targets=list(PUBLICATION_TARGETS))
        def generated(run_id):
            self.service.cancel('synthetic', pid)
            store._last_publication_outcomes[run_id] = {
                k: {'status': 'conflict' if k == 'visualization' else 'published', 'error': ''}
                for k in PUBLICATION_TARGETS}
        store._publish_generated_vaults = generated
        state = self.run_pipeline(pid)
        self.assertEqual(state['status'], 'cancelled')
        outcomes = store.publication_outcomes(state['result_run']['id'])
        self.assertEqual({p['target_role']: p['status'] for p in state['publications']},
                         {k: v['status'] for k, v in outcomes.items()})

    def test_cancel_before_store_dispatch_never_writes_or_claims_success(self):
        store = self.configure_store()
        pid = self.start(definition_ids=[], mode='automatic', publication_targets=list(PUBLICATION_TARGETS))
        def cancel_before(run_id, **kwargs):
            self.service.cancel('synthetic', pid)
            return store.publish(run_id, **kwargs)
        self.service.publish_result = cancel_before
        with patch.object(store, '_publish_generated_vaults') as writer:
            state = self.run_pipeline(pid)
        self.assertEqual(state['status'], 'cancelled')
        writer.assert_not_called()
        self.assertEqual(store.publication_attempts(state['result_run']['id']), [])
        self.assertEqual({p['status'] for p in state['publications']}, {'unknown'})

    def test_exception_after_publication_commit_does_not_erase_published(self):
        store = self.configure_store()
        pid = self.start(definition_ids=[], mode='automatic', publication_targets=list(PUBLICATION_TARGETS))
        def publish_then_raise(run_id, **kwargs):
            store.publish(run_id, **kwargs)
            self.service.cancel('synthetic', pid)
            raise OSError('synthetic response lost')
        self.service.publish_result = publish_then_raise
        state = self.run_pipeline(pid)
        self.assertEqual(state['status'], 'cancelled')
        self.assertEqual({p['status'] for p in state['publications']}, {'published'})

    def test_unreadable_outcomes_are_unknown_after_cancellation(self):
        self.configure_store()
        pid = self.start(definition_ids=[], mode='automatic', publication_targets=list(PUBLICATION_TARGETS))
        def unknown(_):
            self.service.cancel('synthetic', pid)
            raise OSError('synthetic journal unavailable')
        self.service.publication_outcomes = unknown
        state = self.run_pipeline(pid)
        self.assertEqual(state['status'], 'cancelled')
        self.assertEqual({p['status'] for p in state['publications']}, {'unknown'})

    def test_old_publication_outcome_cannot_write_new_generation(self):
        store = self.configure_store()
        pid = self.start(definition_ids=[], mode='automatic', publication_targets=list(PUBLICATION_TARGETS))
        def superseded(run_id):
            with self.connect() as connection:
                connection.execute("UPDATE analysis_pipeline_requests SET generation=2,status='accepted' WHERE pipeline_id=?", (pid,))
                connection.execute("UPDATE analysis_pipeline_publications SET status='pending' WHERE pipeline_id=?", (pid,))
            return store.publication_outcomes(run_id)
        self.service.publication_outcomes = superseded
        state = self.run_pipeline(pid)
        self.assertEqual((state['generation'], state['status']), (2, 'accepted'))
        self.assertEqual({p['status'] for p in state['publications']}, {'pending'})


if __name__ == '__main__':
    unittest.main()
