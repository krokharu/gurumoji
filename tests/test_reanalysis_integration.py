"""一時DB上で再分析の保存・配送契約を検証する。"""
import json
import unittest
from contextlib import contextmanager

import test_analysis_orchestration as fixtures
from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services.model_context import reference_messages


class ReanalysisIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RuntimeTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.service = self.fixture.service
        raw_connect = self.fixture.connect

        @contextmanager
        def connect():
            db = raw_connect()
            try:
                with db:
                    yield db
            finally:
                db.close()
        self.service.connect = connect
        self.service.find_item = lambda item: self.fixture.item if item == 'conversation' else ({'id': 'other', 'revision': 'input-v1'} if item == 'other' else None)
        original = self.fixture.drive(self.fixture.start(question='元の問い', request_id='source-request'))
        self.assertEqual(original['status'], 'completed')
        self.run_id = original['run_id']
        self.result_id = next(r['result_id'] for r in original['results']
                              if r['validation_status'] == 'valid' and r['role'] == 'core')
        with self.service._db() as db:
            self.original_run = db.execute('SELECT state_json FROM orchestration_runs WHERE run_id=?', (self.run_id,)).fetchone()[0]
            self.original_results = [tuple(r) for r in db.execute('SELECT * FROM orchestration_results WHERE run_id=? ORDER BY result_id', (self.run_id,))]
        self.fixture.calls.clear()

    def test_run_and_result_reanalysis_are_frozen_and_delivered(self):
        for index, identifier in enumerate((self.run_id, self.result_id)):
            with self.subTest(identifier=identifier):
                self.fixture.calls.clear()
                run = self.fixture.start(question='新しい問い', source_analysis_id=identifier,
                                         human_prompt='追加の視点を検討', request_id='new-' + str(index))
                frozen = run['config']['reanalysis']
                self.assertEqual(frozen['source_analysis_id'], identifier)
                self.assertEqual(frozen['source_run_id'], self.run_id)
                self.assertEqual(frozen['original_question'], '元の問い')
                self.assertEqual(frozen['human_prompt'], '追加の視点を検討')
                self.assertEqual(run['config']['question'], '新しい問い')
                self.assertTrue(frozen['raw_hash'])
                self.fixture.drive(run)
                context = next(ctx for role, ctx, _ in self.fixture.calls if role == 'core')
                self.assertEqual(context['reanalysis'], frozen)
                instruction, resources = reference_messages(context)
                instruction = json.loads(instruction)
                self.assertNotIn('reanalysis', instruction)
                self.assertEqual(instruction['human_prompt'], frozen['human_prompt'])
                resource = next(json.loads(value) for value in resources if json.loads(value)['reference']['resource_id'] == 'reanalysis')
                self.assertEqual(resource['content'], frozen)
                context['reanalysis']['human_prompt'] = 'changed copy'
                self.assertEqual(self.service.status('conversation', run['run_id'])['config']['reanalysis'], frozen)
                self.fixture.calls.clear()
        with self.service._db() as db:
            self.assertEqual(db.execute('SELECT state_json FROM orchestration_runs WHERE run_id=?', (self.run_id,)).fetchone()[0], self.original_run)
            self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM orchestration_results WHERE run_id=? ORDER BY result_id', (self.run_id,))], self.original_results)

    def test_invalid_and_cross_item_inputs_are_rejected(self):
        cases = [dict(source_analysis_id=self.run_id), dict(human_prompt='追加'),
                 dict(source_analysis_id='result_missing', human_prompt='追加'),
                 dict(source_analysis_id=self.result_id, human_prompt=' '),
                 dict(source_analysis_id=self.result_id, human_prompt='a' * 8001)]
        for index, fields in enumerate(cases):
            with self.subTest(fields=fields.keys()), self.assertRaises((AnalysisContractError, LookupError)):
                self.fixture.start(request_id='bad-' + str(index), **fields)
        with self.assertRaises((AnalysisContractError, LookupError)):
            self.service.start('other', {'model': 'synthetic-model', 'source_analysis_id': self.result_id,
                                         'human_prompt': '追加', 'request_id': 'cross-item'})

    def test_changed_input_rejects_old_source(self):
        self.fixture.item['revision'] = 'input-v2'
        with self.assertRaises(AnalysisContractError) as caught:
            self.fixture.start(source_analysis_id=self.result_id, human_prompt='追加', request_id='stale-source')
        self.assertEqual(caught.exception.code, 'revision_conflict')

    def test_preview_identity_is_rechecked_before_start(self):
        with self.assertRaises(AnalysisContractError) as caught:
            self.fixture.start(source_analysis_id=self.run_id, human_prompt='追加の視点',
                expected_source_result_id='result_changed_after_preview', request_id='changed-preview')
        self.assertEqual(caught.exception.code, 'revision_conflict')
        source = self.fixture.start(source_analysis_id=self.result_id, human_prompt='追加の視点',
            expected_source_result_id=self.result_id, request_id='matching-preview')
        self.assertEqual(source['config']['reanalysis']['source_result_id'], self.result_id)

    def test_request_id_is_idempotent_and_prompt_changes_conflict(self):
        fields = dict(source_analysis_id=self.result_id, human_prompt='追加', request_id='same-request')
        first = self.fixture.start(**fields)
        self.assertEqual(self.fixture.start(**fields)['run_id'], first['run_id'])
        with self.assertRaises(AnalysisContractError) as caught:
            self.fixture.start(**{**fields, 'human_prompt': '別の追加'})
        self.assertEqual(caught.exception.code, 'request_conflict')


if __name__ == '__main__':
    unittest.main()
