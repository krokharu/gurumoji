"""Coreの停止と追加依頼が両立しない配送契約。"""
import copy
import unittest
from types import SimpleNamespace

from gurumoji.services.analysis_orchestration_adapters import CORE_SCHEMA, make_orchestration_adapters
from gurumoji.services.orchestration_core_control import (
    CoreControlResponseError, controlled_schema, project_response,
)


class CoreControlTests(unittest.TestCase):
    def test_schema_and_projection(self):
        schema = controlled_schema(CORE_SCHEMA)
        self.assertEqual(schema['type'], 'object')
        self.assertNotIn('stop', schema['properties'])
        branches = schema['properties']['next_step']['anyOf']
        self.assertEqual(branches[0]['properties']['intents']['minItems'], 1)
        self.assertEqual(branches[0]['properties']['stop']['type'], 'null')
        self.assertEqual(branches[1]['properties']['intents']['maxItems'], 0)
        self.assertEqual(branches[1]['properties']['stop']['type'], 'object')
        finish = {'kind': 'finish', 'intents': [], 'stop': {'reason': 'human_review_required', 'summary': '確認', 'unresolved': []}}
        analyze = {'kind': 'analyze', 'intents': [{'question': '検証'}], 'stop': None}
        for step in (finish, analyze):
            original = {'next_step': copy.deepcopy(step)}
            result = project_response(original)
            self.assertEqual(result['next_step'], step)
            self.assertEqual(result['intents'], step['intents'])
            self.assertEqual(result['stop'], step['stop'])
            self.assertEqual(original, {'next_step': step})
        for step in ({**finish, 'intents': [{'question': '併記'}]},
                     {**analyze, 'stop': finish['stop']}, {**analyze, 'intents': []},
                     {**finish, 'stop': {**finish['stop'], 'reason': []}}):
            with self.assertRaises(CoreControlResponseError):
                project_response({'next_step': step})
        with self.assertRaises(CoreControlResponseError):
            project_response({'next_step': finish, 'intents': []})

    def test_adapter_schema_references_and_invalid_response(self):
        calls = []
        response = {'next_step': {'kind': 'analyze', 'intents': [{'evidence_ids': ['e1']}], 'stop': None}}
        def transport(*args, **kwargs):
            calls.append((args, kwargs))
            return copy.deepcopy(response)
        resolve, runner = make_orchestration_adapters(
            call_ai_json=transport, load_token_config=lambda: SimpleNamespace(lmstudio_base_url=''),
            configured_ai_credentials=lambda *_: ('', 'synthetic'),
            context_meter=lambda *a, **kw: {'fits': True, 'output_reserve': 2000, 'count_method': 'synthetic'})
        for bounded in (0, 1):
            options = resolve({'model_context_version': bounded, 'context_reference_version': 0})
            context = {'task': {'role': 'core', 'phase': 'core'},
                       'raw_evidence': [{'evidence_id': 'source-id', 'utterance_id': 'u1', 'text': '合成'}],
                       'coverage': {'available_count': 1}, 'iteration_review': {'pending_result_ids': []}}
            result = runner('core', context, options, lambda: None, lambda _: None)
            self.assertEqual(result['intents'][0]['evidence_ids'], ['source-id'])
            self.assertEqual(result['next_step']['intents'], result['intents'])
            args = calls[-1][0]
            self.assertIn('next_step', args[6]['required'])
            self.assertIn('同時に選びません', args[3])
        response['next_step']['stop'] = {'reason': 'question_satisfied', 'summary': '', 'unresolved': []}
        with self.assertRaises(CoreControlResponseError) as caught:
            runner('core', context, options, lambda: None, lambda _: None)
        self.assertEqual(caught.exception.response, response)

    def test_legacy_version_and_initial_routing_keep_existing_wire_format(self):
        calls = []
        def transport(*args, **kwargs):
            calls.append(args)
            return {'intents': [], 'stop': None}
        resolve, runner = make_orchestration_adapters(
            call_ai_json=transport, load_token_config=lambda: SimpleNamespace(lmstudio_base_url=''),
            configured_ai_credentials=lambda *_: ('', 'synthetic'))
        options = resolve({})
        for phase, version in (('core', 0), ('initial_routing', 1)):
            response = runner('core', {'task': {'phase': phase}},
                              {**options, 'core_control_version': version}, lambda: None, lambda _: None)
            self.assertEqual(response, {'intents': [], 'stop': None})
            self.assertIn('intents', calls[-1][6]['properties'])
            self.assertNotIn('next_step', calls[-1][6]['properties'])


if __name__ == '__main__':
    unittest.main()
