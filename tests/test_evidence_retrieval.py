"""SQL既定とAI引用IDの原文復元を、一時データだけで検証する。"""
import copy
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.analysis_orchestration import validate_orchestration_payload
from gurumoji.services import evidence_retrieval as sql
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters
import test_analysis_orchestration as fixture


class SqlEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'evidence_id': f'ev-{i:04}', 'utterance_id': f'u{i}', 'speaker': '合成話者',
            'start': i, 'end': i+1, 'text': '通常の観察'} for i in range(1300)]
        self.rows[1220]['text'] = '同意はない。例外は撤回。数値は123。'
        self.index = sql.SqlEvidenceIndex('synthetic-run', self.rows)
        self.addCleanup(self.index.close)

    def test_all_rows_are_searchable_and_source_order_is_preserved(self):
        found = self.index.select(self.rows, '同意について確認', 2, 100)
        self.assertEqual(found, [self.rows[0], self.rows[1220]])
        self.assertEqual(self.index.select(self.rows, '同意', 1, 100), [self.rows[1220]])
        self.assertEqual(self.index.select(self.rows, 'ev-1220を取得', 1, 100), [self.rows[1220]])

    def test_query_is_a_bound_value_and_never_sql(self):
        self.index.select(self.rows, "'); DROP TABLE evidence; --", 1, 100)
        self.assertEqual(self.index.db.execute('SELECT count(*) FROM evidence').fetchone()[0], 1300)

    def test_changed_body_speaker_time_and_unknown_id_are_rejected(self):
        for key, value in [('text', '改変'), ('speaker', '差替え'), ('start', 100), ('evidence_id', 'unknown')]:
            with self.subTest(key=key), self.assertRaises(AnalysisContractError):
                self.index.select([{**self.rows[0], key: value}], '', 1, 100)

    def test_hash_mismatch_and_duplicate_id_are_rejected(self):
        with self.assertRaises(AnalysisContractError):
            self.index.select([self.rows[0], self.rows[0]], '', 2, 100)
        self.index.db.execute("UPDATE evidence SET body='{}' WHERE id=?", (self.rows[0]['evidence_id'],))
        with self.assertRaises(AnalysisContractError):
            self.index.select([self.rows[0]], '', 1, 100)

    def test_oversize_rows_are_not_cut_and_parallel_reads_are_isolated(self):
        rows = [self.rows[0], self.rows[1220]]
        with ThreadPoolExecutor(max_workers=4) as pool:
            found = list(pool.map(lambda _: self.index.select(rows, '同意', 2, 10), range(8)))
        self.assertTrue(all(value == [rows[0]] for value in found))
        self.assertEqual(rows[1]['text'], '同意はない。例外は撤回。数値は123。')

    def test_hybrid_uses_only_ai_ids_and_preserves_raw_response(self):
        response = {'claims': [{'text': 'AIの解釈。原文の数値は生成しない。', 'evidence_ids': ['ev-1220', 'ev-1220']}]}
        before = copy.deepcopy(response)
        result = sql.resolve_citations(self.rows, response, allowed_ids={'ev-1220'}, dataset_version='fixed-v1')
        self.assertEqual(result['sources'], [self.rows[1220]])
        self.assertEqual(result['dataset_version'], 'fixed-v1')
        self.assertEqual(response, before)

    def test_hybrid_rejects_unread_missing_and_oversize_sources(self):
        for ids, allowed, limit in [(['ev-1220'], set(), 60000), (['unknown'], {'unknown'}, 60000), (['ev-1220'], {'ev-1220'}, 1)]:
            with self.subTest(ids=ids, allowed=allowed, limit=limit), self.assertRaises(AnalysisContractError):
                sql.resolve_citations(self.rows, {'claims': [{'evidence_ids': ids}]}, allowed_ids=allowed,
                    dataset_version='fixed-v1', text_limit=limit)

    def test_future_analysis_targets_are_not_current_citations(self):
        response = {'claims': [{'evidence_ids': ['ev-1220']}],
            'intents': [{'evidence_ids': ['unread-future-target']}],
            'analysis_requests': [{'evidence_ids': ['another-future-target']}]}
        result = sql.resolve_citations(self.rows, response, allowed_ids={'ev-1220'}, dataset_version='fixed-v1')
        self.assertEqual(result['sources'], [self.rows[1220]])

    def test_api_default_and_invalid_mode_are_not_silently_switched(self):
        self.assertEqual(validate_orchestration_payload({'model': 'synthetic'})['evidence_mode'], 'sql')
        self.assertEqual(validate_orchestration_payload({'model': 'synthetic', 'evidence_mode': 'hybrid'})['evidence_mode'], 'hybrid')
        for mode in ('auto', None, [], {}, True):
            with self.subTest(mode=mode), self.assertRaises(AnalysisContractError):
                validate_orchestration_payload({'evidence_mode': mode})


class RetrievalIntegrationTests(unittest.TestCase):
    def fixture(self):
        value = fixture.RuntimeTests('test_configured_context_limit_keeps_omissions_and_full_source_explicit')
        value.setUp()
        self.addCleanup(value.doCleanups)
        return value

    def test_both_modes_keep_budget_and_raw_results_but_hybrid_adds_exact_sources(self):
        counts = []
        for mode in ('sql', 'hybrid'):
            value = self.fixture()
            def agent(role, context, *_):
                if role != 'core':
                    return fixture.critic(context)
                return fixture.stop(claims=[{'claim_id': 'synthetic-claim', 'kind': 'observation',
                    'text': '合成資料に発話がある。', 'evidence_ids': [context['raw_evidence'][0]['evidence_id']]}])
            value.agent = agent
            run = value.drive(value.start(evidence_mode=mode))
            self.assertEqual(run['status'], 'completed', run)
            self.assertEqual(run['config']['evidence_mode'], mode)
            saved = value.service.result('conversation', run['run_id'])
            core = next(r for r in saved['raw_results'] if r['raw'].get('claims'))
            self.assertNotIn('evidence_resolution', core['raw'])
            if mode == 'hybrid':
                source = core['evidence_resolution']['sources'][0]
                self.assertEqual(source['text'], value.snapshot['analysis']['segments'][0]['text'])
                self.assertEqual(source['evidence_id'], core['raw']['claims'][0]['evidence_ids'][0])
            else:
                self.assertNotIn('evidence_resolution', core)
            counts.append(len(value.calls))
        self.assertEqual(counts[0], counts[1])

    def test_adapter_uses_sql_without_maf_and_makes_one_provider_call(self):
        calls = []
        def provider(*args, **kwargs):
            calls.append(args)
            return {'summary': '合成', 'claims': []}
        resolve, runner = make_orchestration_adapters(call_ai_json=provider,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url='http://127.0.0.1:1234/v1'),
            configured_ai_credentials=lambda *_: ('', 'synthetic'))
        for mode in ('sql', 'hybrid'):
            result = runner('interpretation', {'question': '合成', 'raw_evidence': [
                {'evidence_id': 'ev-1', 'utterance_id': 'u1', 'text': '合成の原文'}]},
                resolve({'evidence_mode': mode, 'metric_codec_version': 0}), lambda: None, lambda *_: None)
            self.assertEqual(result, {'summary': '合成', 'claims': []})
            self.assertIn(sql.VERSION, calls[-1][4])
            self.assertEqual(json.loads(calls[-1][4])['coverage']['evidence_mode'], mode)
        self.assertEqual(len(calls), 2)
