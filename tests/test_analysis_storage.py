import copy
import csv
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import analysis_store
import test_content_analysis as support


class AnalysisStorageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests('test_generated_result_persists_and_becomes_stale_on_edit')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.store = app.analysis_archive_store()
        self.url = self.fixture.url + '/runs'

    def save(self, request_id='archive-request-000001', **extra):
        payload = self.fixture.payload(request_id)
        return self.client.post(self.url, json={**payload, **extra})

    def artifact(self, run, name):
        meta = next(a for a in run['artifacts'] if a['name'] == name)
        response = self.client.get(meta['url'])
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_full_package_catalog_notes_links_and_idempotency_without_ai(self):
        with patch.object(app, 'call_ai_json') as ai:
            response = self.save()
            self.assertEqual(response.status_code, 200, response.get_json())
            run = response.get_json()['run']
            self.assertEqual(run['vault_status'], 'completed', run)
            self.assertEqual(self.save().get_json()['run']['id'], run['id'])
            self.assertEqual(self.save('archive-request-000002').get_json()['run']['id'], run['id'])
            ai.assert_not_called()
        self.assertEqual(len(self.store.list('content')), 1)
        manifest = json.loads(self.artifact(run, 'manifest.json'))
        self.assertEqual(manifest['conversation_id'], 'content')
        for record in manifest['artifacts']:
            self.assertEqual(analysis_store.hashlib.sha256((self.store.root / record['path']).read_bytes()).hexdigest(), record['sha256'])
        result = json.loads(self.artifact(run, 'result.json'))
        self.assertGreaterEqual(len(result['methods']), 15)
        self.assertTrue(next(m for m in result['methods'] if m['method_id'] == 'morphology')['previews'])
        notes = '\n'.join(p.read_text(encoding='utf-8') for p in self.store.vault.rglob('*.md'))
        self.assertIn('text_hash=', notes)
        self.assertIn('価格を価格で比べる', notes)
        # Graph result nodes deliberately retain compact finding previews.
        self.assertIn('graph_kind: analysis_result', notes)
        self.assertIn('先頭10行まで', notes)
        # Reproduction files link through the app only; no machine-specific file:/// path (OBS-12).
        self.assertIn('/api/analysis/artifacts/', notes)
        self.assertNotIn('file://', notes)
        self.assertNotIn(str(self.store.root.absolute()), notes)

    def test_moved_interview_folder_keeps_catalog_ownership(self):
        run = self.save().get_json()['run']
        self.assertEqual(run['vault_status'], 'completed', run)
        record = self.store.layout.register('content', '')
        old = self.store.vault / record['folder']
        old.rename(old.with_name(old.name + '-移動後'))
        self.store.publish_index('content')
        moved = self.store.layout.load()['interviews']['content']
        self.assertEqual(moved['folder'], record['folder'] + '-移動後')
        self.assertFalse(old.exists())
        with self.store.connect() as conn:
            note_path = conn.execute('SELECT note_path FROM analysis_runs WHERE id=?', (run['id'],)).fetchone()[0]
        self.assertTrue(note_path.startswith(moved['folder'] + '/'), note_path)

    def test_transformer_note_keeps_searchable_results_stats_and_domain_columns(self):
        evidence = {
            'a1': {'id': 'a1', 'speaker': 'A', 'speaker_name': '参加者A',
                   'start': 0, 'end': 2, 'text': '考えが変わりました。'},
            'a2': {'id': 'a2', 'speaker': 'B', 'speaker_name': '参加者B',
                   'start': 3, 'end': 4, 'text': 'なるほど。'},
        }
        fields = ['schema_version', 'item_id', 'source_name', 'revision_count',
                  'analysis_revision', 'analysis_updated_at', 'generated_at',
                  'algorithm_version', 'speaker_name', 'result_label', 'topic_label',
                  'confidence', 'basis', 'evidence_segment_ids']
        rows = [{
            'schema_version': 5, 'item_id': 'content', 'source_name': 'example.wav',
            'revision_count': 0, 'analysis_revision': 0, 'analysis_updated_at': '',
            'generated_at': '2026-09-14T00:00:00+00:00',
            'algorithm_version': 'transformer-topics-test', 'speaker_name': '参加者A',
            'result_label': '意見・認識が変わった', 'topic_label': '価格',
            'confidence': 0.9, 'basis': '明示的な変化表現',
            'evidence_segment_ids': ['a1'],
        }]
        method = {
            'method_id': 'transformer_topics', 'method_version': 'test',
            'title': 'Transformerテーマ分析', 'status': 'completed',
            'datasets': ['transformer_speaker_results'],
            'findings': [{
                'title': '話者別リザルト：参加者A／意見・認識が変わった',
                'text': '対象話題：価格。明示的な変化表現', 'segment_ids': ['a1'],
            }],
            'summaries': [
                {'title': '相づち応答率：参加者B',
                 'text': '反応機会4件、応答した対象発話1件、応答率25.0%。'},
                {'title': '相づち統計：話者と応答有無',
                 'text': 'p値：0.04。Cramér\'s V：0.31。'},
            ],
            'details': {'evidence': evidence},
            'previews': [{
                'dataset': 'transformer_speaker_results',
                'fields': ['speaker_name', 'result_label', 'topic_label', 'confidence',
                           'basis', 'evidence_segment_ids'],
                'rows': rows, 'total': 1,
            }],
            'analysis_unit': '文脈付き発話',
            'engine': {'name': 'fixture-transformer', 'revision': 'r1'},
            'limitations': ['明示表現に基づく補助判定です。'],
        }
        run = self.store.save(
            item_id='content', kind='transformer_topics',
            snapshot={'title': 'example.wav', 'segments': list(evidence.values()),
                      'original_source': {'segments': list(evidence.values())}},
            result={'schema_version': 1, 'parameters': {},
                    'algorithms': {'transformer': 'transformer-topics-test'},
                    'methods': [method]},
            datasets={'transformer_speaker_results': (fields, rows)},
            request_id='transformer-note-request', input_fingerprint='fixture-input',
            source_revision=0, analysis_revision=0,
            app_url='http://127.0.0.1:7860',
        )
        note_dir = self.store.vault / Path(run['note_path']).parent
        note = next(note_dir.glob('method-transformer_topics.md'))
        text = note.read_text(encoding='utf-8')
        self.assertIn('相づち応答率：参加者B', text)
        self.assertIn('相づち統計：話者と応答有無', text)
        self.assertIn('話者別リザルト：参加者A／意見・認識が変わった', text)
        self.assertIn('| speaker\\_name | result\\_label | topic\\_label | confidence |', text)
        self.assertIn('http://127.0.0.1:7860/api/analysis/artifacts/', text)
        self.assertIn('fixture-transformer', text)

    def test_saved_analysis_builds_visible_type_result_and_outline_graph_nodes(self):
        outline = {
            'title': '議題・アウトライン',
            'sections': [{
                'title': '価格と操作性', 'bullets': ['価格と操作性を比較した。'],
                'bullet_evidence': [{'text': '価格と操作性を比較した。', 'segment_ids': ['a1']}],
                'segment_ids': ['a1'], 'start': 0, 'end': 2,
            }],
            'evidence': {'a1': {'id': 'a1', 'speaker': 'A', 'start': 0, 'end': 2,
                                'text': '価格を価格で比べる'}},
        }
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET outline_json=? WHERE id='content'",
                               (json.dumps(outline, ensure_ascii=False),))
        run = self.save().get_json()['run']
        graph_dir = self.store.vault / self.store.layout.analysis_dir('content', 'example.wav', run['id']) / 'graph'
        nodes = list(graph_dir.glob('*.md'))
        self.assertTrue(any(path.name.startswith('分類-text-') for path in nodes))
        self.assertTrue(any(path.name.startswith('手法-morphology-') for path in nodes))
        self.assertTrue(any(path.name.startswith('結果-morphology-表-') for path in nodes))
        outline_node = next(path for path in nodes if path.name.startswith('アウトライン-'))
        text = outline_node.read_text(encoding='utf-8')
        self.assertIn('価格と操作性を比較した', text)
        self.assertIn('graph/detail', text)

    def test_kwic_saves_all_occurrences_beyond_preview_and_filters_exclusions(self):
        with app.database_connection() as connection:
            data = app.row_segments(app.library_row('content'))
            data[0]['text'] = '価格 ' * 220
            connection.execute("UPDATE library_items SET segments_json=?,revision_count=revision_count+1 WHERE id='content'", (json.dumps(data),))
        run = self.save(kwic={'q': '価格', 'mode': 'literal'}).get_json()['run']
        rows = list(csv.DictReader(io.StringIO(self.artifact(run, 'tables/kwic.csv').decode('utf-8-sig'))))
        self.assertEqual(len(rows), 221)
        self.assertNotIn('x1', {r['segment_id'] for r in rows})
        result = json.loads(self.artifact(run, 'result.json'))
        self.assertEqual([m['method_id'] for m in result['methods']], ['kwic'])
        self.assertEqual(result['parameters']['mode'], 'literal')

    def test_changed_input_creates_new_version_and_marks_vault_index(self):
        first = self.save().get_json()['run']
        data = self.client.get(self.fixture.url).get_json()
        config = data['config']; config['research_question'] = '変更した問い'
        response = self.client.put(self.fixture.url, json={**self.fixture.payload(), 'config': config})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.get(self.url).get_json()['runs'][0]['stale'])
        self.assertIn('needs_update: true', next(self.store.vault.rglob('*-分析まとめ.md')).read_text(encoding='utf-8'))
        second = self.save('archive-request-000002').get_json()['run']
        self.assertNotEqual(first['id'], second['id'])
        self.assertFalse(second['stale'])
        self.assertEqual(self.save().status_code, 409)
        self.assertEqual(json.loads(self.artifact(first, 'parameters.json'))['research_question'], '')

    def test_method_navigation_keeps_other_results_after_kwic_only_save(self):
        from gurumoji.obsidian_layout import ANALYSIS_INDEX, method_group_path
        from gurumoji.analysis_method_registry import METHODS, METHOD_GROUPS
        first = self.save().get_json()['run']
        second = self.save('archive-request-000002', kwic={'q': '価格', 'mode': 'literal'}).get_json()['run']
        text_path = self.store.vault / method_group_path('text')
        text = text_path.read_text(encoding='utf-8')
        self.assertIn(first['id'] + '/method-lexical_frequency', text)
        self.assertIn(second['id'] + '/method-kwic', text)
        self.assertIn('KH Coder本体の出力ではありません', text)
        transformer = (self.store.vault / method_group_path('transformer')).read_text(encoding='utf-8')
        self.assertIn('method-audio_emotion', transformer)
        self.assertIn('データなし', transformer)
        index = (self.store.vault / ANALYSIS_INDEX).read_text(encoding='utf-8')
        for key, _, _, _ in METHOD_GROUPS:
            self.assertIn(method_group_path(key)[:-3], index)
        self.assertEqual({key for key, _, _ in METHODS}, {key for _, _, _, keys in METHOD_GROUPS for key in keys})
        before = text_path.read_bytes() + '\n手書きの考察\n'.encode()
        text_path.write_bytes(before)
        with patch.object(app, 'call_ai_json') as ai:
            self.store.publish_index('content')
            ai.assert_not_called()
        self.assertEqual(text_path.read_bytes(), before)

    def test_human_notes_are_never_overwritten_and_retry_never_calls_ai(self):
        run = self.save().get_json()['run']
        path = self.store.vault / self.store.get(run['id'])['note_path']
        original = path.read_bytes()
        edited = original + '\n手書きの解釈\n'.encode()
        path.write_bytes(edited)
        with patch.object(app, 'call_ai_json') as ai:
            result = self.client.post(f"/api/analysis/runs/{run['id']}/vault").get_json()['run']
            self.assertEqual(result['vault_status'], 'conflict')
            self.assertEqual(path.read_bytes(), edited)
            self.assertEqual(result['status'], 'completed')
            path.write_bytes(original)
            result = self.client.post(f"/api/analysis/runs/{run['id']}/vault").get_json()['run']
            self.assertEqual(result['vault_status'], 'completed')
            ai.assert_not_called()

    def test_vault_failure_keeps_artifacts_and_recovers_from_saved_package(self):
        with patch.object(analysis_store.AnalysisStore, 'write_note', side_effect=OSError('disk')):
            run = self.save().get_json()['run']
        self.assertEqual((run['status'], run['vault_status']), ('completed', 'conflict'))
        before = self.artifact(run, 'result.json')
        with patch.object(app, 'group_analysis_for_row', side_effect=AssertionError('must not recompute')):
            result = self.client.post(f"/api/analysis/runs/{run['id']}/vault").get_json()['run']
        self.assertEqual(result['vault_status'], 'completed')
        self.assertEqual(self.artifact(result, 'result.json'), before)

    def test_mid_write_failure_retries_deterministically_and_detects_tamper(self):
        write = analysis_store.write_atomic
        def fail_on_table(path, data):
            if path.suffix == '.csv': raise OSError('disk full')
            return write(path, data)
        with patch.object(analysis_store, 'write_atomic', side_effect=fail_on_table):
            self.assertEqual(self.save().status_code, 500)
        self.assertEqual(self.store.list('content')[0]['status'], 'failed')
        run = self.save().get_json()['run']
        self.assertEqual(run['status'], 'completed')
        target = next(a for a in self.store.artifacts(run['id']) if a['name'] == 'result.json')
        (self.store.root / target['path']).write_bytes(b'{}')
        self.assertEqual(self.client.get('/api/analysis/artifacts/' + target['id']).status_code, 409)

    def test_raw_quotes_are_preserved_and_unsafe_markdown_is_escaped(self):
        with app.database_connection() as conn:
            rows = app.row_segments(app.library_row('content'))
            rows[0]['text'] = '  <script>alert(1)</script> [[偽リンク]]  \n価格  '
            conn.execute("UPDATE library_items SET segments_json=? WHERE id='content'", (json.dumps(rows),))
        run = self.save().get_json()['run']
        saved = json.loads(self.artifact(run, 'input.json'))
        self.assertEqual(saved['original_source']['segments'][0]['text'], rows[0]['text'])
        notes = '\n'.join(p.read_text(encoding='utf-8') for p in self.store.vault.rglob('part-*.md'))
        self.assertNotIn('<script>', notes)
        self.assertIn('&lt;script&gt;', notes)
        self.assertIn('>   &lt;', notes)
        self.assertNotIn('[[偽リンク]]', notes)

    def test_interrupted_save_recovers_original_package_after_edit_without_reanalysis(self):
        with patch.object(analysis_store, 'write_atomic', side_effect=OSError('disk full')):
            self.assertEqual(self.save().status_code, 500)
        run = self.store.list('content')[0]
        with app.database_connection() as conn:
            self.assertIsNotNone(conn.execute('SELECT run_id FROM analysis_pending_packages').fetchone())
            conn.execute("UPDATE analysis_runs SET status='writing' WHERE id=?", (run['id'],))
            conn.execute("UPDATE library_items SET revision_count=revision_count+1 WHERE id='content'")
        app.initialize_library()
        self.assertEqual(self.store.get(run['id'])['status'], 'interrupted')
        with patch.object(app, 'group_analysis_for_row', side_effect=AssertionError('must not recompute')), patch.object(app, 'call_ai_json') as ai:
            response = self.client.post(f"/api/analysis/runs/{run['id']}/vault")
            self.assertEqual(response.status_code, 200, response.get_json())
            ai.assert_not_called()
        result = response.get_json()['run']
        self.assertEqual(result['vault_status'], 'completed')
        self.assertTrue(result['stale'])
        self.assertEqual(result['source_revision'], 0)
        with app.database_connection() as conn:
            self.assertIsNone(conn.execute('SELECT run_id FROM analysis_pending_packages').fetchone())

    def test_ai_success_is_archived_and_old_evidence_survives_source_changes(self):
        _, args = self.fixture.start()
        self.fixture.run_worker(args)
        ai = self.client.get(self.fixture.url).get_json()['insights']['ai']
        self.assertEqual(self.store.get(ai['archive_id'])['status'], 'completed')
        with app.database_connection() as conn:
            rows = app.row_segments(app.library_row('content')); rows[0]['text'] = '更新後の本文'
            conn.execute("UPDATE library_items SET segments_json=?,revision_count=revision_count+1 WHERE id='content'", (json.dumps(rows),))
        run = self.save().get_json()['run']
        self.assertEqual(run['vault_status'], 'completed', run)
        notes = '\n'.join(p.read_text(encoding='utf-8') for p in self.store.vault.rglob('part-*.md'))
        self.assertIn('価格を価格で比べる', notes)
        self.assertIn('更新後の本文', notes)

    def test_failed_ai_archiving_keeps_last_successful_ai(self):
        _, args = self.fixture.start(); self.fixture.run_worker(args)
        before = self.client.get(self.fixture.url).get_json()['insights']['ai']
        _, args = self.fixture.start(self.fixture.payload('request-content-0002'))
        with patch.object(app, 'archive_group_analysis', side_effect=OSError('disk full')):
            self.fixture.run_worker(args)
        current = self.client.get(self.fixture.url + '/insights').get_json()
        self.assertEqual(current['run']['status'], 'failed')
        self.assertEqual(current['insights']['ai'], before)

    def test_finishing_archive_records_partial_stage_and_before_after(self):
        row = app.library_row('content')
        original = copy.deepcopy(app.row_segments(row))
        original[0]['text'] = '価格の誤変換'
        run = app.archive_ai_finishing(row, original, {'cleanup': 'completed', 'outline': 'failed'}, 'openai', 'mock', {})
        self.assertEqual(run['vault_status'], 'completed', run)
        result = json.loads(self.artifact(self.store.public(run), 'result.json'))
        finishing = next(m for m in result['methods'] if m['method_id'] == 'ai_finishing')
        self.assertEqual(finishing['status'], 'partial')
        self.assertEqual(finishing['details']['changes'][0]['before_text'], '価格の誤変換')

    def test_finishing_noise_review_and_reference_outline_survive_storage_and_edit_normalization(self):
        row = app.library_row('content')
        original = copy.deepcopy(app.row_segments(row))
        revised = copy.deepcopy(original)
        revised[0]['ai_review'] = {
            'original_text': original[0]['text'], 'noise_candidate': True,
            'prompt_version': app.FINISHING_VERSION,
            'fragments': [{'offset': 0, 'original_text': original[0]['text'],
                           'noise_candidate': True, 'reason': '雑音の誤認識が疑われる'}],
        }
        revised[0]['jev_review'] = {
            'review_version': app.JEV_REVIEW_VERSION, 'model': 'jev-test',
            'original_text': original[0]['text'], 'decision': 'correction_needed',
            'correction_needed_probability': 0.88, 'confidence': 0.76, 'flagged': True,
            'fragments': [],
            'comparison': {'current_ai_flagged': True, 'jev_flagged': True,
                           'agreement': 'both_flagged'},
        }
        normalized = app.normalize_edited_segments('content', revised)
        self.assertEqual(normalized[0]['ai_review'], revised[0]['ai_review'])
        self.assertEqual(normalized[0]['jev_review'], revised[0]['jev_review'])
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET segments_json=? WHERE id='content'",
                               (json.dumps(normalized),))
        context = {'sections': [{'title': '参照用議題', 'bullets': ['会話全体の要点']}]}
        run = app.archive_ai_finishing(app.library_row('content'), original,
            {'outline_context': 'completed', 'cleanup': 'completed'}, 'openai', 'mock', {},
            context_outline=context,
            jev_usage={'provider': 'typesafe', 'model': 'jev-test', 'input_tokens': 12})
        self.assertEqual(run['vault_status'], 'completed', run)
        public = self.store.public(run)
        details = json.loads(self.artifact(public, 'result.json'))['finishing']
        self.assertEqual(details['context_outline'], context)
        self.assertEqual(details['changes'][0]['ai_review'], revised[0]['ai_review'])
        self.assertEqual(details['jev_comparison']['reviewed_segment_count'], 1)
        self.assertEqual(details['jev_comparison']['agreement_counts']['both_flagged'], 1)
        rows = list(csv.DictReader(io.StringIO(
            self.artifact(public, 'tables/ai_changes.csv').decode('utf-8-sig'))))
        self.assertEqual(rows[0]['noise_candidate'], 'True')
        self.assertIn('雑音', rows[0]['review_reason'])
        jev_rows = list(csv.DictReader(io.StringIO(
            self.artifact(public, 'tables/ai_jev_comparison.csv').decode('utf-8-sig'))))
        self.assertEqual(jev_rows[0]['agreement'], 'both_flagged')
        self.assertEqual(jev_rows[0]['jev_decision'], 'correction_needed')

    def test_path_traversal_request_validation_and_formula_safety(self):
        for value in ('../outside', 'C:/outside', 'nested\\file', '/outside'):
            with self.assertRaises(ValueError): analysis_store.safe_path(self.store.root, value)
        for extra in ({'source_revision': True}, {'request_id': '../outside'}, {'analysis_revision': 99}, {'kwic': {'mode': 'invalid', 'q': '価格'}}):
            self.assertIn(self.save(**extra).status_code, (400, 409))
        text = analysis_store.csv_bytes(['value'], [{'value': '=SUM(1,2)'}, {'value': -2}]).decode('utf-8-sig')
        self.assertIn("'=SUM", text)
        self.assertIn('-2', text)


if __name__ == '__main__':
    unittest.main()
