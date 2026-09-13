import copy
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from gurumoji import ai_finishing
from gurumoji.obsidian_finishing import (
    ObsidianWorkbench, outline_note, parse_transcript, read_text, transcript_note,
    split_properties, with_properties, parse_outline,
)


class ObsidianWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workbench = ObsidianWorkbench(Path(self.temporary.name) / 'library.sqlite3')
        self.segments = [
            {'id': 'first', 'speaker': 'A', 'start': 0, 'end': 2, 'text': '原文です。'},
            {'id': 'second', 'speaker': 'B', 'start': 3, 'end': 4, 'text': '賛成ではない。'},
        ]
        self.state = self.workbench.prepare('recording', '会議.wav', self.segments,
                                             revision=0, provider='lmstudio')
        self.calls = []

    def test_efforts_persist_and_can_be_updated_without_replacing_notes(self):
        original = read_text(self.workbench.note_path(self.state['work']))
        self.workbench.prepare('recording', '会議.wav', self.segments, revision=0,
                               ai_efforts={'cleanup': 'high', 'name_verify': 'low'})
        self.assertEqual(self.workbench.load('recording')['ai_efforts']['cleanup'], 'high')
        self.workbench.prepare('recording', '会議.wav', self.segments, revision=0)
        self.assertEqual(self.workbench.load('recording')['ai_efforts']['name_verify'], 'low')
        self.assertEqual(read_text(self.workbench.note_path(self.state['work'])), original)

    def engine(self, action, state, segments, context, provider, check):
        check()
        self.calls.append((action, copy.deepcopy(segments), copy.deepcopy(context)))
        if action == 'outline':
            return {'outline': {'sections': [{'title': '検討', 'bullets': ['合意は未確定']} ]}}
        if action == 'finish':
            return {'segments': [{**s, 'text': s['text'] + '校正'} for s in segments],
                    'names': {}, 'outline': context}
        return {'revision': state['revision'] + 1}

    def choose(self, action, engine=None):
        state = self.workbench.load('recording')
        text = read_text(self.workbench.note_path(state['control']))
        text = re.sub(r'^- \[[xX]\](.*gurumoji-command:[^\n]+)$', r'- [ ]\1', text, flags=re.M)
        self.workbench.note(state['control'], text)
        self.workbench.poll_once(engine or self.engine)
        if action:
            text = re.sub(r'^- \[ \](.*gurumoji-command:' + action + r' -->)$',
                          r'- [x]\1', text, flags=re.M)
            self.workbench.note(state['control'], text)
            self.workbench.poll_once(engine or self.engine)
        return self.workbench.load('recording')

    def test_recording_is_one_note_and_arbitrary_text_round_trips(self):
        source = copy.deepcopy(self.segments)
        source[0]['text'] = '~~~\n<!-- gurumoji:segment e4 -->\n# 見出し\n<img src=x>\n~~~'
        note = transcript_note('会議', source)
        self.assertEqual(parse_transcript(note, source), source)
        self.assertEqual(len(list(self.workbench.note_path(self.state['folder']).glob('*-全文.md'))), 1)
        self.assertEqual(len(list(self.workbench.root.glob('*/source-*.json'))), 1)
        with self.assertRaises(ValueError):
            parse_transcript(note.replace('6669727374', '0000'), source)

    def test_native_properties_blocks_and_legacy_notes_round_trip(self):
        note = read_text(self.workbench.note_path(self.state['work']))
        properties, body = split_properties(note)
        self.assertTrue({'gurumoji/finishing', 'gurumoji/transcript', 'graph/detail'} <= set(properties['tags']))
        self.assertTrue(properties['source'].startswith('[[10-インタビュー/'))
        self.assertTrue(properties['note_id'])
        self.assertNotIn('~~~text', body)
        self.assertIn('\n\n^s-6669727374\n', body)
        text = '\n> literal\n\n[[note]] #^block &amp; \\ * _\n'
        segments = [{**self.segments[0], 'text': text}]
        self.assertEqual(parse_transcript(transcript_note('会議', segments), segments), segments)
        legacy = '<!-- gurumoji:segment 6669727374 -->\n### 0–2秒 A\n~~~~text\n' + text + '\n~~~~\n'
        self.assertEqual(parse_transcript(legacy, segments), segments)
        outline = {'title': '全体アウトライン', 'sections': [{'title': 'A & B', 'bullets': ['[[会議]] *未確定*']} ]}
        self.assertEqual(parse_outline(with_properties(outline_note(outline), {'tags': ['test']})), outline)

    def test_metadata_edits_and_moved_notes_preserve_finishing_and_apply(self):
        state = self.choose('finish')
        for key in ('work', 'outline', 'control', 'result_note'):
            path = self.workbench.note_path(state[key])
            properties, body = split_properties(read_text(path))
            properties.update(tags=['研究/確認済み'], aliases=['手動の別名'])
            path.write_text(with_properties(body, properties), encoding='utf-8')
            destination = self.workbench.vault / '移動先' / path.name
            destination.parent.mkdir(exist_ok=True)
            path.rename(destination)
        self.workbench.poll_once(self.engine)
        moved = self.workbench.load('recording')
        self.assertTrue(moved['control'].startswith('移動先/'))
        self.assertEqual(len(self.calls), 1)
        state = self.choose('apply')
        self.assertEqual(state['status'], 'completed', state['message'])
        self.assertEqual([call[0] for call in self.calls], ['finish', 'apply'])

    def test_ambiguous_moved_note_is_rejected(self):
        relative = self.state['work']
        path = self.workbench.note_path(relative)
        body = read_text(path)
        path.rename(path.with_name('移動した会話.md'))
        path.with_name('複製した会話.md').write_text(body, encoding='utf-8')
        with self.assertRaises(ValueError):
            self.workbench.refresh_paths(self.state)

    def test_default_pipeline_uses_obsidian(self):
        self.assertTrue(app.JobOptions.__dataclass_fields__['finish_in_obsidian'].default)

    def test_outline_manual_edits_finishing_result_edits_and_apply(self):
        state = self.choose('outline')
        self.assertEqual(state['status'], 'completed')
        self.workbench.note(state['outline'], '# 全体アウトライン\n## 人が調整した議題\n- 保留する\n')
        self.workbench.note(state['work'], transcript_note('会議', [
            {**self.segments[0], 'text': 'Obsidianで直した本文'}, self.segments[1]]))
        state = self.choose('finish')
        self.assertEqual(self.calls[-1][1][0]['text'], 'Obsidianで直した本文')
        self.assertEqual(self.calls[-1][2]['sections'][0]['title'], '人が調整した議題')
        body = read_text(self.workbench.note_path(state['result_note']))
        self.workbench.note(state['result_note'], body.replace('Obsidianで直した本文校正', '確認して修正した結果'))
        state = self.choose('apply')
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state['revision'], 1)
        self.assertEqual(self.calls[-1][1][0]['text'], '確認して修正した結果')
        self.assertEqual([call[0] for call in self.calls], ['outline', 'finish', 'apply'])
        for _ in range(4):
            self.workbench.poll_once(self.engine)
        self.assertEqual(len(self.calls), 3)
        self.assertNotIn('candidate', state)

    def test_edit_during_finishing_is_preserved_and_cannot_be_applied(self):
        def engine(*args):
            result = self.engine(*args)
            self.workbench.note(self.state['work'], transcript_note('会議', [
                {**self.segments[0], 'text': '処理中の手動編集'}, self.segments[1]]))
            return result
        state = self.choose('finish', engine)
        self.assertEqual(state['status'], 'error')
        self.assertNotIn('candidate', state)
        self.assertIn('処理中の手動編集', read_text(self.workbench.note_path(state['work'])))
        self.assertTrue(self.workbench.note_path(state['result_note']).exists())
        self.workbench.poll_once(engine)
        self.assertEqual(len(self.calls), 1)
        state = self.choose('apply')
        self.assertEqual(state['status'], 'error')
        self.assertEqual(len(self.calls), 1)

    def test_source_edit_after_generation_blocks_apply(self):
        state = self.choose('finish')
        self.workbench.note(state['outline'], '# 全体アウトライン\n## 別の議題\n- 手動変更\n')
        state = self.choose('apply')
        self.assertEqual(state['status'], 'error')
        self.assertEqual(len(self.calls), 1)

    def test_restart_does_not_repeat_latched_command_and_recheck_can_retry(self):
        def interrupted(*args):
            raise RuntimeError('API failed')
        state = self.choose('finish', interrupted)
        state['status'] = 'running'
        self.workbench.save(state)
        restarted = ObsidianWorkbench(self.workbench.root.parent / 'library.sqlite3')
        restarted.recover()
        restarted.poll_once(self.engine)
        self.assertEqual(self.calls, [])
        self.assertEqual(restarted.load('recording')['status'], 'interrupted')
        state = self.choose('finish')
        self.assertEqual(state['status'], 'completed')

    def test_multiple_commands_never_trigger_ai(self):
        control = read_text(self.workbench.note_path(self.state['control']))
        self.workbench.note(self.state['control'], control.replace('[ ]', '[x]'))
        self.workbench.poll_once(self.engine)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.workbench.load('recording')['status'], 'error')

    def test_application_watcher_executes_saved_checkbox_and_stops(self):
        control = read_text(self.workbench.note_path(self.state['control']))
        control = control.replace('- [ ] アウトラインを作成', '- [x] アウトラインを作成')
        self.workbench.note(self.state['control'], control)
        polled = threading.Event()
        original_poll = self.workbench.poll_once
        def poll(*args):
            original_poll(*args)
            polled.set()
        with patch.object(app, 'obsidian_workbench', return_value=self.workbench), \
                patch.object(app, 'run_obsidian_finishing', side_effect=self.engine), \
                patch.object(self.workbench, 'poll_once', side_effect=poll):
            stop, worker = app.start_obsidian_watcher()
            try:
                self.assertTrue(polled.wait(5))
            finally:
                stop.set()
                worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
        self.assertEqual([call[0] for call in self.calls], ['outline'])
        self.assertEqual(self.workbench.load('recording')['status'], 'completed')

    def test_ready_gate_and_new_revision_preserve_old_notes(self):
        self.state['ready'] = False
        self.workbench.save(self.state)
        self.choose('outline')
        self.assertEqual(self.calls, [])
        self.workbench.activate('recording', 0)
        self.workbench.poll_once(self.engine)
        self.assertEqual(len(self.calls), 1)
        old = self.workbench.load('recording')
        note = read_text(self.workbench.note_path(old['work']))
        updated = self.workbench.prepare('recording', '会議.wav', self.segments, revision=1)
        self.assertNotEqual(old['work'], updated['work'])
        self.assertEqual(split_properties(read_text(self.workbench.note_path(old['work'])))[1], split_properties(note)[1])
        self.assertIn('graph/history', split_properties(read_text(self.workbench.note_path(old['work'])))[0]['tags'])
        self.assertEqual(updated['original_note'], old['original_note'])

    def test_notes_do_not_add_per_utterance_ai_calls_or_markdown_overhead(self):
        segments = [{**self.segments[0], 'id': f's{i}', 'text': f'発話{i}'} for i in range(100)]
        parsed = parse_transcript(with_properties(transcript_note('タイトル', segments),
                                  {'tags': ['送信しないタグ'], 'aliases': ['送信しない別名']}), segments)
        payloads = []
        def call(system, prompt, name, schema):
            payload = json.loads(prompt.split('\n', 1)[1])
            payloads.append(payload)
            self.assertNotIn('gurumoji:segment', prompt)
            self.assertNotIn('~~~text', prompt)
            self.assertNotIn('segment_id', prompt)
            self.assertNotIn('送信しない', prompt)
            self.assertNotIn('^s-', prompt)
            return {'items': [{**r, 'noise_candidate': False, 'reason': ''} for r in payload['targets']]}
        result = ai_finishing.clean_transcript(parsed, call, lambda *_: None, lambda: None,
            outline={'sections': [{'title': '全体', 'bullets': ['検討中']} ]})
        self.assertEqual(result, segments)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(sum(len(p['targets']) for p in payloads), 100)


class ObsidianAppIntegrationTests(unittest.TestCase):
    def setUp(self):
        import test_content_analysis
        self.fixture = test_content_analysis.ContentApiTests('test_generated_result_persists_and_becomes_stale_on_edit')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_route_prepares_saved_recording_without_ai_and_preserves_edits(self):
        with patch.object(app, 'call_ai_json') as ai:
            response = self.fixture.client.post('/api/library/content/obsidian-finishing', json={'provider': 'lmstudio'})
            self.assertEqual(response.status_code, 200, response.get_json())
            state = app.obsidian_workbench().load('content')
            path = app.obsidian_workbench().note_path(state['work'])
            edited = read_text(path).replace('価格を価格で比べる', '手動編集')
            path.write_text(edited, encoding='utf-8')
            response = self.fixture.client.post('/api/library/content/obsidian-finishing', json={'provider': 'lmstudio'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(read_text(path), edited)
            ai.assert_not_called()

    def test_engine_uses_edited_outline_and_applies_transactionally_without_ai_training(self):
        workbench = app.obsidian_workbench()
        row = app.library_row('content')
        segments = app.row_segments(row)
        state = workbench.prepare('content', '会議.wav', segments, revision=int(row['revision_count']),
                                 provider='lmstudio', detect_names=False, create_outline=True)
        context = {'sections': [{'title': '編集した全体像', 'bullets': ['合意は未確定']} ]}
        revised = [{**s, 'text': s['text'] + '修正'} for s in segments]
        final_outline = ai_finishing.create_outline(revised, {}, lambda *_: {'sections': [
            {'title': '仕上げ後の議題', 'bullets': [{'text': '修正後の要点', 'segment_ids': [revised[0]['id']]}]}]},
            lambda *_: None, lambda: None)
        with patch.object(app, 'load_token_config', return_value=app.TokenConfig(lmstudio_model='test-model')), \
                patch.object(app, 'clean_segments_with_ai', return_value=revised) as clean, \
                patch.object(app, 'create_outline_with_ai', return_value=final_outline) as outline:
            result = app.run_obsidian_finishing('finish', state, segments, context, 'lmstudio', lambda: None)
            self.assertIs(clean.call_args.kwargs['outline'], context)
            self.assertEqual(outline.call_count, 1)
            self.assertEqual(outline.call_args.args[0], revised)
        result.update(before=segments, revision=state['revision'], run_id='test-obsidian-apply')
        with patch.object(app, 'prepare_training_corrections') as training:
            applied = app.run_obsidian_finishing('apply', state, revised, result, 'lmstudio', lambda: None)
            training.assert_not_called()
        self.assertEqual(applied['revision'], state['revision'] + 1)
        saved = app.library_row('content')
        self.assertEqual(app.row_segments(saved)[0]['text'], revised[0]['text'])
        self.assertEqual(json.loads(saved['outline_json']), final_outline)
        output = next(Path(p) for p in json.loads(saved['files_json']) if p.endswith('_話者分離.json'))
        self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['outline'], final_outline)
        self.assertTrue(any('obsidian-finishing' in r['request_id'] for r in app.analysis_archive_store().list('content')))
        with self.assertRaises(ValueError):
            app.run_obsidian_finishing('apply', state, revised, result, 'lmstudio', lambda: None)


if __name__ == '__main__':
    unittest.main()
