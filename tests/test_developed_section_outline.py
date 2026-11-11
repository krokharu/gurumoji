"""合成応答で、移植した大小見出しの境界と再試行を確認する。"""
import copy
import json
import unittest
import ai_finishing as finishing

class AiFinishingTests(unittest.TestCase):

    def setUp(self):
        self.segments = [{'id': 'a', 'speaker': 'A', 'start': 2, 'end': 6, 'text': '賛成ではない。'}, {'id': 'b', 'speaker': 'B', 'start': 7, 'end': 10, 'text': '検討します。'}]
        self.outline = {'sections': [{'title': '検討', 'bullets': ['賛成ではない。検討する。']}]}

    def clean(self, call, segments=None, cancel=lambda: None):
        return finishing.clean_transcript(segments or self.segments, call, lambda *_: None, cancel, outline=self.outline)

    def echo(self, system, prompt, name, schema):
        return {'items': [{'id': r['id'], 'text': r['text'], 'noise_candidate': False, 'reason': ''} for r in json.loads(prompt.split('\n', 1)[1])['targets']]}

    def outline_reply(self, sections=None, chapters=None):
        """A fake model: small headings per window, then large headings."""

        def call(system, prompt, name, schema):
            if name == 'meeting_outline':
                first = schema['properties']['sections']['items']['properties']['start_line']['minimum']
                return {'sections': sections or [{'start_line': first, 'title': '検討', 'summary': '賛否と検討', 'points': [{'text': '検討する', 'lines': [2, 1]}]}]}
            return {'chapters': chapters or [{'first_section': 1, 'title': '全体', 'summary': '全体の要約'}]}
        return call

    def test_outline_has_large_and_small_headings_with_summaries(self):
        result = finishing.create_section_outline(self.segments, {}, self.outline_reply(), lambda *_: None, lambda: None)
        section = result['sections'][0]
        self.assertEqual((section['start'], section['end']), (2, 10))
        self.assertEqual((section['tag'], section['chapter'], section['summary']), ('S01', 'C01', '賛否と検討'))
        self.assertEqual(section['bullets'], ['検討する'])
        self.assertEqual(section['bullet_evidence'][0]['segment_ids'], ['a', 'b'])
        self.assertEqual(result['chapters'], [{'tag': 'C01', 'title': '全体', 'summary': '全体の要約', 'sections': ['S01'], 'start': 2.0, 'end': 10.0}])
        self.assertEqual(result['evidence']['a'], self.segments[0])
        self.assertEqual(result['provenance']['prompt_version'], finishing.FINISHING_VERSION)
        self.assertEqual(result['provenance']['outline_method'], finishing.OUTLINE_METHOD)

    def test_small_headings_partition_every_utterance(self):
        from gurumoji.services.outline_tags import outline_assignment
        segments = [{'id': f'u{i}', 'speaker': 'A', 'start': i, 'end': i + 0.5, 'text': f'発話{i}'} for i in range(6)]
        sections = [{'start_line': 1, 'title': '前半', 'summary': 's', 'points': [{'text': 'p', 'lines': [2, 5]}]}, {'start_line': 4, 'title': '後半', 'summary': 's', 'points': [{'text': 'q', 'lines': [6]}]}]
        result = finishing.create_section_outline(segments, {}, self.outline_reply(sections), lambda *_: None, lambda: None)
        self.assertEqual([(s['first_segment_id'], s['last_segment_id'], s['segment_count']) for s in result['sections']], [('u0', 'u2', 3), ('u3', 'u5', 3)])
        self.assertEqual(result['sections'][0]['bullet_evidence'][0]['segment_ids'], ['u1'])
        saved = result['section_assignment']['segments']
        self.assertEqual({k: v['tag'] for k, v in saved.items()}, {'u0': 'S01', 'u1': 'S01', 'u2': 'S01', 'u3': 'S02', 'u4': 'S02', 'u5': 'S02'})
        self.assertEqual({v['basis'] for v in saved.values()}, {'range'})
        self.assertFalse(outline_assignment(result, segments)['derived'])

    def test_long_conversations_are_read_in_overlapping_windows(self):
        segments = [{'id': f'u{i}', 'speaker': 'A', 'start': i, 'end': i + 0.5, 'text': '長い発話' * 30} for i in range(400)]
        seen = []

        def call(system, prompt, name, schema):
            if name == 'meeting_outline':
                rule = schema['properties']['sections']['items']['properties']['start_line']
                seen.append((rule['minimum'], rule['maximum']))
                return {'sections': [{'start_line': n, 'title': f'節{n}', 'summary': 's', 'points': []} for n in range(rule['minimum'], rule['maximum'] + 1, 20)]}
            return {'chapters': [{'first_section': 1, 'title': '全体', 'summary': 's'}]}
        result = finishing.create_section_outline(segments, {}, call, lambda *_: None, lambda: None)
        self.assertGreater(len(seen), 2)
        self.assertTrue(all((prev[1] >= nxt[0] for prev, nxt in zip(seen, seen[1:]))), seen)
        self.assertEqual(sum((s['segment_count'] for s in result['sections'])), 400)
        starts = [s['first_segment_id'] for s in result['sections']]
        self.assertEqual(len(starts), len(set(starts)))

    def test_large_headings_are_made_in_batches_that_regroup_the_last_group(self):
        segments = [{'id': f'u{i}', 'speaker': 'A', 'start': i, 'end': i + 0.5, 'text': f'発話{i}'} for i in range(60)]
        sections = [{'start_line': n, 'title': f'節{n}', 'summary': 's', 'points': []} for n in range(1, 61, 2)]
        batches = []

        def call(system, prompt, name, schema):
            if name == 'meeting_outline':
                return {'sections': sections}
            rule = schema['properties']['chapters']['items']['properties']['first_section']
            batches.append((rule['minimum'], rule['maximum']))
            return {'chapters': [{'first_section': k, 'title': f'章{k}', 'summary': 's'} for k in range(rule['minimum'], rule['maximum'] + 1, 4)]}
        result = finishing.create_section_outline(segments, {}, call, lambda *_: None, lambda: None)
        self.assertEqual(batches, [(1, 24), (21, 30)])
        firsts = [result['sections'].index(next((s for s in result['sections'] if s['tag'] == c['sections'][0]))) + 1 for c in result['chapters']]
        self.assertEqual(firsts, [1, 5, 9, 13, 17, 21, 25, 29])
        self.assertEqual(sum((len(c['sections']) for c in result['chapters'])), 30)

    def test_an_oversized_small_heading_is_retried_once(self):
        segments = [{'id': f'u{i}', 'speaker': 'A', 'start': i, 'end': i + 0.5, 'text': 'x'} for i in range(70)]
        replies = [[{'start_line': 1, 'title': '全部', 'summary': 's', 'points': []}], [{'start_line': 1, 'title': '前', 'summary': 's', 'points': []}, {'start_line': 36, 'title': '後', 'summary': 's', 'points': []}]]
        prompts = []

        def call(system, prompt, name, schema):
            if name == 'meeting_outline':
                prompts.append(system)
                return {'sections': replies[len(prompts) - 1]}
            return {'chapters': [{'first_section': 1, 'title': '全体', 'summary': 's'}]}
        result = finishing.create_section_outline(segments, {}, call, lambda *_: None, lambda: None)
        self.assertEqual(len(prompts), 2)
        self.assertIn('60発話以内', prompts[1])
        self.assertEqual([s['segment_count'] for s in result['sections']], [35, 35])

    def test_a_heading_still_too_long_is_resplit_on_its_own_range(self):
        segments = [{'id': f'u{i}', 'speaker': 'A', 'start': i, 'end': i + 0.5, 'text': 'x'} for i in range(70)]
        calls = []

        def call(system, prompt, name, schema):
            if name != 'meeting_outline':
                return {'chapters': [{'first_section': 1, 'title': '全体', 'summary': 's'}]}
            rule = schema['properties']['sections']['items']['properties']['start_line']
            calls.append((rule['minimum'], rule['maximum']))
            if len(calls) < 3:
                return {'sections': [{'start_line': 1, 'title': '全部', 'summary': 's', 'points': []}]}
            return {'sections': [{'start_line': 1, 'title': '前', 'summary': 's', 'points': []}, {'start_line': 40, 'title': '後', 'summary': 's', 'points': []}]}
        result = finishing.create_section_outline(segments, {}, call, lambda *_: None, lambda: None)
        self.assertEqual(calls, [(1, 70), (1, 70), (1, 70)])
        self.assertEqual([s['segment_count'] for s in result['sections']], [39, 31])
        self.assertEqual(result['provenance']['model_calls'], 4)

    def test_outline_rejects_out_of_range_or_unordered_headings(self):
        for sections in ([], [{'start_line': 2, 'title': 't', 'summary': 's', 'points': []}], [{'start_line': 1, 'title': 't', 'summary': 's', 'points': [{'text': 'p', 'lines': [9]}]}], [{'start_line': 1, 'title': 't', 'summary': 's', 'points': []}, {'start_line': 1, 'title': 'u', 'summary': 's', 'points': []}]):
            with self.subTest(sections=sections), self.assertRaises(RuntimeError):
                finishing.create_section_outline(self.segments, {}, lambda *_: {'sections': sections, 'chapters': []}, lambda *_: None, lambda: None)

    def test_outline_retries_once_when_headings_are_invalid(self):
        calls = []
        good = self.outline_reply()

        def call(system, prompt, name, schema):
            calls.append(name)
            if name == 'meeting_outline' and calls.count('meeting_outline') == 1:
                return {'sections': [{'start_line': 2, 'title': 't', 'summary': 's', 'points': []}]}
            return good(system, prompt, name, schema)
        result = finishing.create_section_outline(self.segments, {}, call, lambda *_: None, lambda: None)
        self.assertEqual(calls, ['meeting_outline', 'meeting_outline', 'meeting_outline_chapters'])
        self.assertEqual(result['sections'][0]['first_segment_id'], 'a')

class FullCleanupProcedureTests(unittest.TestCase):
    """One order and stage record for the in-job and Obsidian routes (ARCH-07)."""

    def setUp(self):
        from gurumoji.services.ai.transcript_finishing import run_full_cleanup
        self.run_full_cleanup = run_full_cleanup
        self.segments = [{'id': 'a', 'text': '元の文'}]
        self.outline = {'sections': [{'title': '議題', 'bullets': ['要点']}]}
        self.calls = []

    def create(self, source):
        self.calls.append('outline')
        return self.outline

    def clean(self, source, outline):
        self.calls.append(('clean', outline is self.outline))
        return [{**segment, 'text': '校正後'} for segment in source]

    def review(self, outline):
        self.calls.append('jev')
        return ({'a': {'flagged': True}}, {'request_count': 1})

    def attach(self, segments, reviews):
        return [{**segment, 'jev': reviews[segment['id']]} for segment in segments]

    def procedure(self, **overrides):
        options = dict(check_cancelled=lambda: None, create_context_outline=self.create, clean_with_outline=self.clean, review_with_jev=self.review, attach_jev=self.attach)
        options.update(overrides)
        return self.run_full_cleanup(self.segments, **options)
if __name__ == '__main__':
    unittest.main()
