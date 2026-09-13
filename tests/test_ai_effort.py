import unittest
from unittest.mock import patch

import app
from gurumoji.ai_effort import normalize_efforts, effort_payload, local_effort_payload


class AiEffortTests(unittest.TestCase):
    def test_local_binary_and_graded_model_capabilities(self):
        binary = {'allowed_options': ['off', 'on'], 'default': 'on'}
        self.assertEqual(local_effort_payload('off', binary), {'reasoning_effort': 'none'})
        self.assertEqual(local_effort_payload('low', binary), {})
        self.assertEqual(local_effort_payload('medium', binary), {})
        self.assertEqual(local_effort_payload('high', binary), {})
        self.assertEqual(local_effort_payload('ultra', {'allowed_options': ['low', 'medium', 'xhigh']}),
                         {'reasoning_effort': 'xhigh'})
        self.assertEqual(local_effort_payload('high', {'allowed_options': ['low', 'medium', 'high']}),
                         {'reasoning_effort': 'high'})
        self.assertEqual(local_effort_payload('low', {'allowed_options': ['minimal']}),
                         {'reasoning_effort': 'minimal'})
        self.assertEqual(local_effort_payload('high', {'allowed_options': ['low', 'medium', 'xhigh']}),
                         {'reasoning_effort': 'xhigh'})
        self.assertEqual(local_effort_payload('ultra', {'allowed_options': ['low', 'medium', 'high']}),
                         {'reasoning_effort': 'high'})
        # Typical Gemma/Llama listings do not advertise reasoning controls.
        self.assertEqual(local_effort_payload('off', {}), {})
        self.assertEqual(local_effort_payload('ultra', {}), {})
        self.assertEqual(local_effort_payload('high', {}), {})

    def test_local_request_uses_supported_off_value(self):
        with patch.object(app, 'lmstudio_reasoning_settings', return_value={
                'allowed_options': ['off', 'on'], 'default': 'on'}), \
                patch.object(app, 'post_json', return_value={}) as post, \
                patch.object(app, 'extract_lmstudio_text', return_value='{}'):
            app.call_ai_json('lmstudio', '', 'local-qwen', 's', 'p', 'transcript_cleanup', {},
                             ai_efforts={'cleanup': 'low'})
            self.assertNotIn('reasoning_effort', post.call_args.args[2])
            app.call_ai_json('lmstudio', '', 'local-qwen', 's', 'p', 'transcript_cleanup', {},
                             ai_efforts={'cleanup': 'off'})
            self.assertEqual(post.call_args.args[2]['reasoning_effort'], 'none')

    def test_validation_and_independent_defaults(self):
        first = normalize_efforts()
        first['cleanup'] = 'high'
        self.assertEqual(normalize_efforts()['cleanup'], 'auto')
        for value in ([], {'unknown': 'high'}, {'cleanup': 'max'}, {'cleanup': []}):
            with self.assertRaises(ValueError):
                normalize_efforts(value)

    def test_each_operation_reaches_openai_request(self):
        efforts = dict(outline='low', cleanup='high', name_extract='medium', name_verify='low')
        for schema, expected in [('meeting_outline', 'low'), ('transcript_cleanup', 'high'),
                                 ('speaker_identity_extraction', 'medium'),
                                 ('speaker_identity_link_verification', 'low')]:
            with self.subTest(schema=schema), patch.object(app, 'post_json', return_value={}) as post, \
                    patch.object(app, 'extract_openai_text', return_value='{}'):
                app.call_ai_json('openai', 'test', 'test-model', 'system', 'prompt', schema, {},
                                 ai_efforts=efforts)
                self.assertEqual(post.call_args.args[2]['reasoning'], {'effort': expected})

    def test_auto_omits_reasoning_and_unrelated_requests_stay_unchanged(self):
        self.assertEqual(effort_payload('openai', 'test', 'meeting_outline'), {})
        self.assertEqual(effort_payload('openai', 'test', 'conversation_insights', {'outline': 'high'}),
                         {'reasoning': {'effort': 'high'}})

    def test_google_and_local_payloads(self):
        self.assertEqual(effort_payload('google', 'gemini-2.5-pro', 'meeting_outline', {'outline': 'low'}),
                         {'thinkingConfig': {'thinkingBudget': 1024}})
        self.assertEqual(effort_payload('google', 'gemini-3-pro-preview', 'meeting_outline', {'outline': 'medium'}),
                         {'thinkingConfig': {'thinkingLevel': 'HIGH'}})
        self.assertEqual(effort_payload('google', 'gemini-2.5-flash', 'meeting_outline', {'outline': 'off'}),
                         {'thinkingConfig': {'thinkingBudget': 0}})
        self.assertEqual(effort_payload('google', 'gemini-2.5-pro', 'meeting_outline', {'outline': 'off'}),
                         {'thinkingConfig': {'thinkingBudget': 1024}})
        self.assertEqual(effort_payload('google', 'gemini-3.5-flash', 'meeting_outline', {'outline': 'ultra'}),
                         {'thinkingConfig': {'thinkingLevel': 'HIGH'}})
        self.assertEqual(effort_payload('openai', 'gpt-5.6-luna', 'meeting_outline', {'outline': 'off'}),
                         {'reasoning': {'effort': 'none'}})
        self.assertEqual(effort_payload('openai', 'gpt-5.6-luna', 'meeting_outline', {'outline': 'ultra'}),
                         {'reasoning': {'effort': 'xhigh'}})
        self.assertEqual(effort_payload('lmstudio', 'local', 'transcript_cleanup', {'cleanup': 'high'}),
                         {'reasoning_effort': 'high'})

    def test_cleanup_and_outline_wrappers_forward_settings(self):
        efforts = {'cleanup': 'high', 'outline': 'low'}
        def clean(segments, call, *args, **kwargs):
            return call('s', 'p', 'transcript_cleanup', {})
        def outline(segments, names, call, *args):
            call('s', 'p', 'meeting_outline', {})
            return {'provenance': {}}
        with patch.object(app, 'call_ai_json', return_value={}) as call, \
                patch.object(app, 'finish_clean_transcript', side_effect=clean), \
                patch.object(app, 'finish_create_outline', side_effect=outline):
            app.clean_segments_with_ai([], 'openai', '', '', lambda _: None, lambda: None, ai_efforts=efforts)
            self.assertEqual(call.call_args.kwargs['ai_efforts'], efforts)
            app.create_outline_with_ai([], {}, 'openai', '', '', lambda _: None, lambda: None, ai_efforts=efforts)
            self.assertEqual(call.call_args.kwargs['ai_efforts'], efforts)

    def test_both_speaker_passes_receive_individual_efforts(self):
        efforts = {'name_extract': 'low', 'name_verify': 'high'}
        response = {'speaker_names': [{'speaker': 'A', 'name': '田中',
                     'evidence': '私は田中です', 'evidence_segment_ids': [0]}]}
        with patch.object(app, 'call_ai_json', return_value=response) as call:
            app.detect_speaker_names_with_ai(
                [{'id': 's1', 'speaker': 'A', 'text': '私は田中です', 'start': 0, 'end': 2}],
                'openai', '', '', ai_efforts=efforts)
            self.assertEqual([c.args[5] for c in call.call_args_list],
                             ['speaker_identity_extraction', 'speaker_identity_link_verification'])
            self.assertTrue(all(c.kwargs.get('ai_efforts') == efforts for c in call.call_args_list))
