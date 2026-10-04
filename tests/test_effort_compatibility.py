"""Synthetic capability and finishing-route regressions; no provider IO."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app
from gurumoji.ai_effort import (
    LEVELS, SCHEMA_STAGES, UnsupportedLocalEffort, local_cleanup_effort_payload,
    local_effort_payload, normalize_efforts,
)
from gurumoji.ai_finishing import repair_recommended_segments
from gurumoji.obsidian_finishing import ObsidianWorkbench
from gurumoji.services.ai.client import call_ai_json
from gurumoji.services.obsidian_workflows import ObsidianWorkflowService
import test_pipeline_regressions as pipeline_fixtures


CAPABILITIES = {
    'binary_on': {'allowed_options': ['off', 'on'], 'default': 'on'},
    'binary_off': {'allowed_options': ['off', 'on'], 'default': 'off'},
    'binary_missing': {'allowed_options': ['off', 'on']},
    'finite': {'allowed_options': ['low', 'medium', 'high']},
    'minimal': {'allowed_options': ['minimal']},
    'xhigh': {'allowed_options': ['low', 'medium', 'xhigh']},
    'high_only': {'allowed_options': ['high']},
    'unknown': {},
}


class EffortCompatibilityTests(unittest.TestCase):
    def test_all_schemas_capability_matrix_preserves_settings(self):
        for schema, stage in SCHEMA_STAGES.items():
            for label, capability in CAPABILITIES.items():
                for level in LEVELS:
                    with self.subTest(schema=schema, capability=label, level=level):
                        efforts = normalize_efforts({stage: level})
                        before = copy.deepcopy(efforts)
                        post = Mock(return_value={'choices': [{'message': {'content': '{}'}}]})
                        kwargs = dict(post=post, lmstudio_base=lambda _: 'http://synthetic.invalid/v1',
                                      lmstudio_model_id=lambda model: model,
                                      lmstudio_reasoning=lambda *_: capability, providers={'lmstudio'},
                                      ai_efforts=efforts)
                        resolver = local_cleanup_effort_payload if stage == 'cleanup' else local_effort_payload
                        try:
                            expected = resolver(level, capability)
                        except UnsupportedLocalEffort:
                            with self.assertRaises(UnsupportedLocalEffort):
                                call_ai_json('lmstudio', '', 'synthetic', 's', 'p', schema, {}, **kwargs)
                            post.assert_not_called()
                        else:
                            call_ai_json('lmstudio', '', 'synthetic', 's', 'p', schema, {}, **kwargs)
                            payload = post.call_args.args[2]
                            self.assertEqual({k: payload[k] for k in ['reasoning_effort'] if k in payload}, expected)
                        self.assertEqual(efforts, before)

    def test_binary_default_off_and_missing_never_pretend_to_enable_thinking(self):
        for label in ('binary_off', 'binary_missing'):
            for level in ('low', 'medium', 'high', 'ultra'):
                with self.subTest(label=label, level=level):
                    with self.assertRaises(UnsupportedLocalEffort):
                        local_effort_payload(level, CAPABILITIES[label])
                    self.assertEqual(local_cleanup_effort_payload(level, CAPABILITIES[label]), {})
        with self.assertRaises(UnsupportedLocalEffort):
            local_cleanup_effort_payload('off', CAPABILITIES['finite'])

    def test_finite_cleanup_overrides_keep_existing_aliases(self):
        expected = {
            'finite': ['low', 'medium', 'high', 'high'],
            'minimal': ['minimal', 'minimal', 'minimal', 'minimal'],
            'xhigh': ['low', 'medium', 'xhigh', 'xhigh'],
            'high_only': [None, None, 'high', 'high'],
            'unknown': [None, None, None, None],
        }
        for label, values in expected.items():
            for level, wire in zip(('low', 'medium', 'high', 'ultra'), values):
                with self.subTest(label=label, level=level):
                    self.assertEqual(local_cleanup_effort_payload(level, CAPABILITIES[label]),
                                     {} if wire is None else {'reasoning_effort': wire})
        self.assertEqual(local_effort_payload('off', CAPABILITIES['unknown']), {})
        with self.assertRaises(UnsupportedLocalEffort):
            local_effort_payload('off', CAPABILITIES['finite'])

    def test_cleanup_does_not_swallow_generic_value_errors(self):
        with patch('gurumoji.ai_effort.local_effort_payload', side_effect=ValueError('invalid metadata')):
            with self.assertRaisesRegex(ValueError, 'invalid metadata'):
                local_cleanup_effort_payload('medium', {})

    def test_off_wrappers_never_polish_and_return_independent_originals(self):
        source = [{'id': 's1', 'text': '合成原文', 'words': [{'word': '原文'}]}]
        before = copy.deepcopy(source)
        for provider in ('lmstudio', 'openai', 'google'):
            with self.subTest(provider=provider), patch.object(app, 'call_ai_json') as call:
                args = (source, provider, '', '', lambda _: None, lambda: None)
                full = app.clean_segments_with_ai(*args, ai_efforts={'cleanup': 'off'})
                recommended = app.clean_recommended_segments_with_ai(
                    source, {'s1': {'flagged': True}}, provider, '', '', lambda _: None, lambda: None,
                    ai_efforts={'cleanup': 'off'}, effort='high')
                call.assert_not_called()
                self.assertEqual(full, source)
                self.assertEqual(recommended, source)
                full[0]['words'][0]['word'] = 'changed'
                self.assertEqual(source, before)

    def test_recommended_content_windows_are_unchanged(self):
        source = [{'id': f's{i}', 'speaker': 'A', 'text': f'合成発話{i}'} for i in range(23)]
        before = copy.deepcopy(source)
        for level, expected in [('off', []), ('low', [1]), ('medium', [1]), ('high', [2]), ('ultra', [21])]:
            windows = []
            def answer(_system, prompt, _name, _schema):
                windows.append(len(json.loads(prompt.split('\n', 1)[1])['conversation_window']))
                return {'confirmed_problem': False, 'needs_more_context': False, 'issue_type': 'none',
                        'text': '合成発話11', 'reason': 'synthetic'}
            result = repair_recommended_segments(source, {'s11': {'flagged': True}}, answer,
                                                lambda *_: None, lambda: None, effort=level,
                                                outline={'sections': [{'title': '合成話題'}]})
            self.assertEqual(windows, expected)
            self.assertEqual([s["text"] for s in result], [s["text"] for s in before])
            self.assertEqual(source, before)

    def test_workbench_all_strengths_round_trip_without_coercion(self):
        with tempfile.TemporaryDirectory() as temp:
            workbench = ObsidianWorkbench(Path(temp) / 'library.sqlite3')
            for level in LEVELS:
                efforts = normalize_efforts({'cleanup': level, 'outline': 'off', 'name_verify': 'ultra'})
                workbench.prepare('synthetic', 'synthetic.wav', [{'id': 's1', 'text': '合成原文'}],
                                  revision=0, ai_efforts=efforts)
                self.assertEqual(workbench.load('synthetic')['ai_efforts'], efforts)
                workbench.prepare('synthetic', 'synthetic.wav', [], revision=0)
                self.assertEqual(workbench.load('synthetic')['ai_efforts'], efforts)

    def test_obsidian_off_skips_cleanup_context_but_keeps_independent_actions(self):
        source = [{'id': 's1', 'speaker': 'A', 'text': '合成原文'}]
        for separate_actions in (False, True):
            with self.subTest(separate_actions=separate_actions):
                d = SimpleNamespace(
                    library_row=Mock(return_value={'revision_count': 0, 'speaker_names_json': '{}'}),
                    load_token_config=Mock(return_value=SimpleNamespace(lmstudio_base_url='http://synthetic.invalid')),
                    configured_ai_credentials=Mock(return_value=('', 'synthetic')),
                    json_load=json.loads,
                    create_outline_with_ai=Mock(return_value={'sections': [{'title': 'synthetic'}]}),
                    clean_segments_with_ai=Mock(side_effect=AssertionError('cleanup must not run')),
                    review_segments_with_jev=Mock(side_effect=AssertionError('comparison must not run')),
                    attach_jev_comparison=Mock(), detect_speaker_names_with_ai=Mock(return_value={}),
                    apply_speaker_identity_repairs=Mock(return_value=(source, {}, {})),
                )
                d.json_load = lambda value, _default: json.loads(value)
                state = {'item_id': 'synthetic', 'revision': 0, 'ai_efforts': {'cleanup': 'off', 'outline': 'low'},
                         'jev_compare': True, 'detect_names': separate_actions, 'create_outline': separate_actions}
                before = copy.deepcopy(state)
                result = ObsidianWorkflowService(d).run_finishing('finish', state, source, {}, 'lmstudio', lambda: None)
                self.assertEqual(result['segments'], source)
                self.assertEqual(result['stages']['cleanup'], 'not_requested')
                self.assertEqual(result['stages']['jev_comparison'], 'skipped')
                self.assertEqual(d.create_outline_with_ai.call_count, int(separate_actions))
                self.assertEqual(d.detect_speaker_names_with_ai.call_count, int(separate_actions))
                self.assertEqual(state, before)
                d.clean_segments_with_ai.assert_not_called()
                d.review_segments_with_jev.assert_not_called()
                if separate_actions:
                    self.assertEqual(d.create_outline_with_ai.call_args.kwargs['ai_efforts'], state['ai_efforts'])
                # Explicit outline command remains enabled even when polishing is OFF.
                ObsidianWorkflowService(d).run_finishing('outline', state, source, {}, 'lmstudio', lambda: None)
                self.assertEqual(d.create_outline_with_ai.call_count, int(separate_actions) + 1)


class CleanupOffJobTests(unittest.TestCase):
    def test_recommended_advanced_and_custom_off_preserve_input_and_stage_independence(self):
        fixture = pipeline_fixtures.TranscriptionJobRegressionTests()
        for mode in ('recommended', 'advanced', 'custom'):
            for independent in (False, True):
                with self.subTest(mode=mode, independent=independent), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    job = fixture.job(root)
                    efforts = normalize_efforts({'cleanup': 'off', 'outline': 'low', 'name_extract': 'medium'})
                    with fixture.fake_pipeline() as calls, \
                            patch.object(app, 'clean_segments_with_ai') as clean, \
                            patch.object(app, 'clean_recommended_segments_with_ai') as repair, \
                            patch.object(app, 'review_segments_with_jev') as review, \
                            patch.object(app, 'detect_speaker_names_with_ai', return_value={}) as names:
                        app.run_transcription_job(job, fixture.options(
                            root, transcript_finishing_mode=mode, recommended_cleanup=mode == 'recommended',
                            clean_transcript=mode != 'recommended', jev_compare=mode != 'recommended',
                            create_outline=independent, detect_speaker_names=independent, ai_efforts=efforts))
                    self.assertEqual(job.status, 'completed')
                    clean.assert_not_called()
                    repair.assert_not_called()
                    review.assert_not_called()
                    self.assertEqual(names.call_count, int(independent))
                    self.assertEqual(calls['outline'].call_count, int(independent))
                    self.assertEqual(calls['write_outputs'].call_args.args[2][0]['text'], '元の文字起こし')
                    self.assertEqual(efforts['cleanup'], 'off')
