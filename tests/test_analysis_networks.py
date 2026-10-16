"""Stage H: known structures, immutable packages and isolated browser actions."""
import copy
import json
import os
import tempfile
import threading
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from gurumoji.analysis_core import EMBEDDING_STANDARD_V1, validate_graph_edge
from gurumoji.services import analysis_networks as networks
from gurumoji.services.segment_embeddings import text_sha256
from gurumoji.transformer_analysis import transformer_embedding_fingerprint


def sample():
    sequence = ['A', 'B', 'A', 'B', 'A', 'C', 'A', 'B', 'A', 'B', 'A', 'C']
    segments = [{'id': f'u{i:02}', 'speaker': s, 'speaker_name': s, 'start': i*5, 'end': i*5+4,
                 'text': f'架空の発話{i}', 'valid_time': True, 'excluded': False, 'annotation': {}}
                for i, s in enumerate(sequence)]
    counts = Counter(zip(sequence, sequence[1:]))
    return {'item': {'id': 'synthetic', 'revision_count': 1, 'analysis_revision': 1},
            'segments': segments, 'automatic': {'transitions': [
                {'from_speaker': a, 'to_speaker': b, 'count': n} for (a, b), n in counts.items()]},
            'annotations': {}, 'manual': {'codebook': []}, 'config': {}}


def coding_sample():
    analysis = sample()
    assignments = {'topic_a': [0, 1, 2, 3, 10, 11], 'topic_b': [4, 5, 6, 7, 8, 9]}
    analysis['manual']['codebook'] = [{'id': c, 'label': c} for c in assignments]
    for code, indices in assignments.items():
        for i in indices:
            sid = f'u{i:02}'
            analysis['annotations'][sid] = {'codes': [code]}
            analysis['segments'][i]['annotation'] = {'codes': [code]}
    rows = []
    for i, segment in enumerate(analysis['segments']):
        axis = 1 if 3 <= i <= 9 else (2 if i == 10 else 0)
        vector = bytes(127 if j == axis else 0 for j in range(384))
        rows.append({**EMBEDDING_STANDARD_V1, 'item_id': 'synthetic', 'segment_id': segment['id'],
                     'text_sha256': text_sha256(segment['text']), 'input_hash': transformer_embedding_fingerprint(analysis, revision=EMBEDDING_STANDARD_V1['model_revision']),
                     'vector': vector, 'created_at': '2026-10-13T00:00:00Z', 'stale': False})
    return analysis, rows


def lexical_sample():
    analysis = sample()
    terms = [('apple', 'pear', 'peach'), ('desk', 'chair', 'table')]
    morphemes = []
    pairs = []
    for offset, group in enumerate(terms):
        for i in range(3):
            for term in group:
                morphemes.append({'segment_id': f'u{offset*3+i:02}', 'normalized': term,
                                  'is_content': True, 'excluded': False})
        for i, a in enumerate(group):
            for b in group[i+1:]:
                pairs.append({'term_a': min(a, b), 'term_b': max(a, b), 'cooccurrence_count': 3})
    return analysis, {'morphemes': morphemes, 'cooccurrence': pairs,
                      'coverage': {'document_count': 6}, 'engine': {'name': 'synthetic', 'status': 'available'}}


class NetworkCalculationTests(unittest.TestCase):
    def test_response_reproduces_counts_bias_reciprocity_and_centrality(self):
        analysis = sample()
        result = networks.response_network(analysis)
        self.assertEqual(result['status'], 'completed')
        rows = {r['speaker']: r for r in result['tables']['response_nodes']}
        self.assertEqual((rows['A']['incoming'], rows['A']['outgoing']), (5, 6))
        self.assertAlmostEqual(rows['A']['outgoing_bias'], 4/6)
        self.assertAlmostEqual(rows['A']['strength_centrality'], 1)
        self.assertAlmostEqual(result['tables']['response_summary'][0]['reciprocity'], 10/11)
        for edge in result['tables']['response_edges']:
            self.assertEqual(validate_graph_edge(edge), {k: edge[k] for k in validate_graph_edge(edge)})
            self.assertTrue(set(edge['segment_ids']) <= {s['id'] for s in analysis['segments']})

    def test_response_is_repeatable_and_conversation_scoped_or_registry_linked(self):
        analysis = sample()
        first = networks.response_network(analysis)
        self.assertEqual(first, networks.response_network(copy.deepcopy(analysis)))
        other = copy.deepcopy(analysis); other['item']['id'] = 'other'
        self.assertNotEqual(first['tables']['response_nodes'][0]['node_id'],
                            networks.response_network(other)['tables']['response_nodes'][0]['node_id'])
        linked = networks.response_network(analysis, {'A': 'participant-a'})
        self.assertEqual(linked['tables']['response_nodes'][0]['node_id'], 'spk:participant-a')

    def test_response_rejects_insufficient_unknown_and_inconsistent_evidence(self):
        for sequence in ([], ['A'], ['A', 'A', 'A'], ['A', 'B'], ['A', 'UNKNOWN']*4):
            analysis = sample(); analysis['segments'] = [dict(analysis['segments'][i], speaker=s) for i,s in enumerate(sequence)]
            counts = Counter((a,b) for a,b in zip(sequence,sequence[1:]) if a != b)
            analysis['automatic']['transitions'] = [{'from_speaker': a,'to_speaker': b,'count': n} for (a,b),n in counts.items()]
            self.assertEqual(networks.response_network(analysis)['status'], 'not_applicable')
        analysis = sample(); analysis['automatic']['transitions'][0]['count'] += 1
        self.assertEqual(networks.response_network(analysis)['status'], 'not_applicable')
        self.assertEqual(networks.response_network(sample(), projected_ids={'u00'})['status'], 'not_applicable')

    def test_response_missing_time_is_reported_without_zero_imputation(self):
        analysis = sample(); analysis['segments'][0].update(start=None, end=None, valid_time=False)
        analysis['automatic']['transitions'][0]['count'] -= 1
        result = networks.response_network(analysis)
        self.assertEqual(result['coverage']['missing_time_count'], 1)
        self.assertEqual(result['coverage']['transition_count'], 10)

    def test_cooccurrence_recovers_two_known_communities_and_equal_centers(self):
        analysis, linguistics = lexical_sample()
        result = networks.cooccurrence_network(analysis, linguistics)
        communities = [set(r['terms']) for r in result['tables']['cooccurrence_communities']]
        self.assertEqual(communities, [set(['apple','pear','peach']), set(['desk','chair','table'])])
        self.assertTrue(all(r['degree'] == 2 and r['strength'] == 6 for r in result['tables']['cooccurrence_nodes']))
        self.assertEqual(len(result['tables']['cooccurrence_edges']), 6)

    def test_cooccurrence_is_repeatable_with_reordered_input_and_ties(self):
        analysis, linguistics = lexical_sample()
        first = networks.cooccurrence_network(analysis, linguistics)
        linguistics['cooccurrence'].reverse(); linguistics['morphemes'].reverse()
        self.assertEqual(first, networks.cooccurrence_network(analysis, linguistics))

    def test_cooccurrence_rejects_empty_duplicate_mismatched_or_excluded_evidence(self):
        analysis, original = lexical_sample()
        cases = []
        empty = copy.deepcopy(original); empty['cooccurrence'] = []; cases.append(empty)
        bad = copy.deepcopy(original); bad['cooccurrence'][0]['cooccurrence_count'] = 4; cases.append(bad)
        duplicate = copy.deepcopy(original); duplicate['cooccurrence'].append(duplicate['cooccurrence'][0]); cases.append(duplicate)
        excluded = copy.deepcopy(original); excluded['morphemes'][0]['excluded'] = True; cases.append(excluded)
        for case in cases:
            self.assertEqual(networks.cooccurrence_network(analysis, case)['status'], 'not_applicable')

    def test_cooccurrence_keeps_parser_and_filter_coverage(self):
        analysis, linguistics = lexical_sample()
        linguistics['engine']['status'] = 'fallback'
        linguistics['coverage'].update(cooccurrence_truncated=True, cooccurrence_top_terms=60,
                                      cooccurrence_total_rows=900, cooccurrence_returned_rows=6)
        result = networks.cooccurrence_network(analysis, linguistics)
        self.assertEqual(result['engine']['parser']['status'], 'fallback')
        self.assertEqual(result['coverage'], linguistics['coverage'])

    def test_coding_flags_misplaced_and_distant_turns_and_keeps_annotations(self):
        analysis, rows = coding_sample(); before = copy.deepcopy(analysis)
        result = networks.coding_consistency(analysis, rows)
        flags = {r['segment_id']: r for r in result['tables']['coding_consistency']}
        self.assertEqual(flags['u03']['label'], 'closer_other_code')
        self.assertEqual(flags['u03']['nearest_other_code'], 'topic_b')
        self.assertEqual(flags['u10']['label'], 'far_from_all_codes')
        self.assertEqual(flags['u10']['origin'], 'rule')
        self.assertNotIn('u00', flags)
        self.assertLess(result['tables']['consistency_codes'][0]['mean_similarity'],
                        result['tables']['consistency_codes'][1]['mean_similarity'])
        self.assertEqual(analysis, before)
        self.assertEqual(result, networks.coding_consistency(copy.deepcopy(analysis), list(reversed(rows))))

    def test_coding_refuses_small_missing_stale_and_excluded_inputs(self):
        analysis, rows = coding_sample()
        for case in ([], [dict(r, stale=True) for r in rows], rows[1:]):
            self.assertEqual(networks.coding_consistency(analysis, case)['status'], 'not_applicable')
        small = copy.deepcopy(analysis); small['annotations'] = {'u00': {'codes': ['topic_a']}}
        self.assertEqual(networks.coding_consistency(small, rows)['status'], 'not_applicable')
        excluded = copy.deepcopy(analysis); excluded['segments'][3]['excluded'] = True
        flags = networks.coding_consistency(excluded, rows)['tables']['coding_consistency']
        self.assertNotIn('u03', {r['segment_id'] for r in flags})

    def test_multicode_is_not_flagged_as_closer_to_its_other_assigned_code(self):
        analysis, rows = coding_sample()
        analysis['annotations']['u03']['codes'].append('topic_b')
        result = networks.coding_consistency(analysis, rows)
        self.assertNotIn('u03', {r['segment_id'] for r in result['tables']['coding_consistency']})

    def test_coding_zero_centroid_is_unscorable_not_a_clean_result(self):
        analysis, rows = coding_sample()
        analysis['annotations'] = {f'u{i:02}': {'codes': ['topic_a']} for i in range(3)}
        rows[0]['vector'] = bytes([127, 0] + [0]*382)
        rows[1]['vector'] = bytes([129, 0] + [0]*382)
        rows[2]['vector'] = bytes([0, 127] + [0]*382)
        result = networks.coding_consistency(analysis, rows)
        self.assertEqual(result['coverage']['unscorable_segment_count'], 1)
        self.assertEqual(result['tables']['consistency_codes'][0]['unscorable_count'], 1)

    def test_codebook_change_changes_input_identity(self):
        analysis, rows = coding_sample(); first = networks.coding_consistency(analysis, rows)
        analysis['manual']['codebook'][0]['label'] = 'changed definition'
        self.assertNotEqual(first['input_hash'], networks.coding_consistency(analysis, rows)['input_hash'])


class ApiFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gurumoji-h-test-'); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        p = patch.dict(os.environ, {key: str(self.root / name) for key, name in (
            ('MOJIOKOSI_DATA_DIR','data'), ('MOJIOKOSI_OUTPUT_DIR','output'), ('MOJIOKOSI_BACKUP_DIR','backups'))})
        p.start(); self.addCleanup(p.stop)
        import app
        from gurumoji import research_analysis
        self.app = app
        paths = {'DATABASE_FILE': self.root/'data/library.sqlite3', 'DATA_DIRECTORY': self.root/'data',
                 'DEFAULT_OUTPUT_DIRECTORY': self.root/'output', 'BACKUP_DIRECTORY': self.root/'backups',
                 'MEDIA_DIRECTORY': self.root/'data/media', 'THUMBNAIL_DIRECTORY': self.root/'data/thumbnails',
                 'TRAINING_DIRECTORY': self.root/'data/kushinada_training',
                 'CUSTOM_VOCABULARY_FILE': self.root/'data/custom_vocabulary.json'}
        for key, value in paths.items():
            p = patch.object(app, key, value); p.start(); self.addCleanup(p.stop)
        for name in ('_load_ginza','_load_sudachi'):
            p = patch.object(research_analysis, name, return_value=(None,'synthetic fallback'))
            p.start(); self.addCleanup(p.stop)
        research_analysis._RESEARCH_CACHE.clear(); self.addCleanup(research_analysis._RESEARCH_CACHE.clear)
        for name, value in [('get_machine_profile', {}), ('load_token_config', app.TokenConfig()),
                            ('lmstudio_connection_status', {'reachable':False}), ('kushinada_training_status', {})]:
            if hasattr(app, name):
                p = patch.object(app, name, return_value=value); p.start(); self.addCleanup(p.stop)
        for name in ('call_ai_json', 'call_ai_text'):
            p = patch.object(app, name, side_effect=AssertionError('external AI call prohibited'), create=True)
            p.start(); self.addCleanup(p.stop)
        self.client = app.app.test_client(); app.initialize_library()
        self.analysis, self.vectors = coding_sample()
        segments = [dict(s, text=('apple pear peach' if i < 6 else 'desk chair table'))
                    for i,s in enumerate(self.analysis['segments'])]
        app.upsert_library_item(item_id='synthetic', source_name='架空の会話.wav',output_dir=self.root/'output/synthetic',
            media_path=None, language='ja', segments=segments, speaker_names={'A':'A','B':'B','C':'C'},
            outline=None, emotion_analysis=None, files=[], write_srt=False, write_json=True,
            speaker_profiles={s:{'display_name':s,'session_role':'participant'} for s in ('A','B','C')})
        row=app.library_row('synthetic'); current=app.group_analysis_for_row(row,include_research_rows=True)
        app.save_group_analysis('synthetic', {'source_revision':current['item']['revision_count'],
            'analysis_revision':current['item']['analysis_revision'],
            'config': {**current['config'],'codebook':self.analysis['manual']['codebook']},
            'annotations':self.analysis['annotations']})
        self.current = app.group_analysis_for_row(app.library_row('synthetic'),include_research_rows=True)
        expected=transformer_embedding_fingerprint(self.current, revision=EMBEDDING_STANDARD_V1['model_revision'])
        with app.database_connection() as connection:
            from gurumoji.services.segment_embeddings import write_rows
            by_id={s['id']:s for s in self.current['segments']}
            write_rows(connection, [('synthetic',r['segment_id'],text_sha256(by_id[r['segment_id']]['text']),expected,
                r['model_name'],r['model_revision'],r['dimensions'],r['encoding'],r['vector'],r['created_at']) for r in self.vectors])
        self.current = app.group_analysis_for_row(app.library_row('synthetic'),include_research_rows=True)


class NetworkApiTests(ApiFixture, unittest.TestCase):
    def test_staged_snapshot_pins_network_version_and_keeps_frozen_vectors(self):
        from gurumoji.services.analysis_pipeline_adapters import make_staged_initial_builder
        builder = make_staged_initial_builder(archive_snapshot=self.app.archive_snapshot,
            archive_source_stamp=self.app.archive_source_stamp, group_analysis_for_row=self.app.group_analysis_for_row)
        self.assertIn(networks.VERSION, builder.version)
        row = builder.freeze(self.app.library_row('synthetic'))
        outputs = {'base': builder.run_stage('base', row, {})}
        with self.app.database_connection() as connection:
            connection.execute("DELETE FROM segment_embeddings WHERE item_id='synthetic'")
        for stage in builder.stages[1:]:
            outputs[stage.stage_id] = builder.run_stage(stage.stage_id, row, outputs)
        self.assertEqual(outputs['snapshot']['analysis']['local_methods'],self.current['local_methods'])

    def test_registered_methods_cards_tables_and_preview_do_not_change_metrics(self):
        response = self.client.get('/api/library/synthetic/analysis/methods')
        self.assertEqual(response.status_code,200)
        methods={r['method_id']:r for r in response.get_json()['methods']}
        for method, names in networks.DATASETS.items():
            self.assertEqual(methods[method]['status'],'completed')
            self.assertTrue(methods[method]['summaries'] and methods[method]['limitations'])
            self.assertEqual(methods[method]['details']['card']['parameters'], networks.CARDS[method]['parameters'])
            self.assertEqual(set(methods[method]['datasets']),set(names))
        preview=self.app.group_analysis_for_row(self.app.library_row('synthetic'),include_research_rows=False)
        self.assertEqual(preview['local_methods'],self.current['local_methods'])

    def test_mismatched_and_stale_standard_guide_recalculation_without_loading_models(self):
        with self.app.database_connection() as connection:
            connection.execute("UPDATE segment_embeddings SET model_revision='nonstandard' WHERE item_id='synthetic'")
        result=self.app.group_analysis_for_row(self.app.library_row('synthetic'))['local_methods']['coding_consistency']
        self.assertEqual(result['status'],'not_applicable'); self.assertIn('再計算',result['reason'])

    def test_gets_are_readonly_for_primary_database_and_annotations(self):
        with self.app.database_connection() as connection:
            before=list(connection.iterdump())
        self.client.get('/api/library/synthetic/analysis/methods')
        self.client.get('/api/library/synthetic/analysis')
        with self.app.database_connection() as connection:
            self.assertEqual(list(connection.iterdump()),before)

    def test_fixed_packages_preserve_graphs_rule_labels_and_previous_runs(self):
        from gurumoji.analysis_store import AnalysisStore, StoreConflict
        from gurumoji.analysis_method_registry import method_results
        from gurumoji.services.group_analysis_exports import analysis_csv_rows
        store=AnalysisStore(self.app.DATABASE_FILE,self.app.database_connection)
        datasets={name:analysis_csv_rows(self.current,name) for name in networks.FIELDS}
        row=self.app.library_row('synthetic'); snapshot=self.app.archive_snapshot(row,self.current)
        result={'schema_version':1,'parameters':self.current['config'],
                'algorithms':{'networks':networks.VERSION}, 'methods':method_results(self.current,datasets),
                'analysis':self.current}
        def save(request,data=result):
            return store.save(item_id='synthetic',kind='text_analysis',snapshot=snapshot,result=data,datasets=datasets,
                request_id=request,input_fingerprint=self.app.archive_source_stamp(row),source_revision=row['revision_count'],
                analysis_revision=row['analysis_revision'],publish=False)
        first=save('h1'); before=store.verified_package(first['id'])
        second=save('h2'); self.assertEqual(first['id'],second['id'])
        for name, (_, rows) in datasets.items():
            self.assertEqual([r['values'] for r in store.read_table(first['id'],name)['rows']],rows)
        with self.app.database_connection() as connection:
            labels=connection.execute('SELECT origin,method_version,model,model_revision,label FROM segment_labels WHERE run_id=?',(first['id'],)).fetchall()
        self.assertTrue(labels)
        self.assertTrue(all(tuple(r)[:4] == ('rule',networks.VERSION,EMBEDDING_STANDARD_V1['model_name'],EMBEDDING_STANDARD_V1['model_revision']) for r in labels))
        changed=copy.deepcopy(result); changed['analysis']['local_methods']['coding_consistency']['reason']='changed'
        with self.assertRaises(StoreConflict): save('h1',changed)
        self.assertEqual(store.verified_package(first['id']),before)
        self.assertEqual(store.get(first['id'])['status'],'completed')

    def test_exports_include_all_new_tables_and_source_identity(self):
        import csv, io
        for name in networks.FIELDS:
            response=self.client.get('/api/library/synthetic/analysis/export.csv?dataset='+name)
            self.assertEqual(response.status_code,200)
            rows=list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig'))))
            self.assertEqual(len(rows),len(networks.csv_sources(self.current)[name]))
            if rows:
                self.assertEqual(rows[0]['item_id'],'synthetic'); self.assertTrue(rows[0]['input_version'])


import browser_support


@browser_support.ui_browser_test
class NetworkBrowserTests(ApiFixture, unittest.TestCase):
    def test_method_results_cautions_evidence_and_mobile(self):
        from playwright.sync_api import expect
        from werkzeug.serving import make_server
        server=make_server('127.0.0.1',0,self.app.app,threaded=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        self.addCleanup(thread.join,5); self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        with browser_support.sandboxed_playwright_browser() as browser:
            page=browser.new_page(viewport={'width':1360,'height':900})
            page.route('**/api/ai/**',lambda route: route.fulfill(json={}))
            errors=[]; page.on('pageerror',lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/#/analysis/synthetic')
            page.locator('.analysis-desktop-layout [data-analysis-mode="methods"]').click()
            host=page.locator('#analysis-desktop-content')
            for method in networks.DATASETS:
                host.locator(f'[data-analysis-method-select="{method}"]').click()
                detail=host.locator('.analysis-method-detail')
                expect(detail).to_contain_text('適用条件')
                expect(detail).to_contain_text('記述的な指標')
                expect(detail.locator('table').first).to_be_visible()
                detail.locator('.content-evidence summary').first.click()
                expect(detail.locator('.content-evidence blockquote').first).to_contain_text('apple')
            expect(host.locator('.analysis-method-detail')).to_contain_text('コードの正誤の判定ではありません')
            screenshot_dir = os.environ.get('GURUMOJI_NETWORK_SCREENSHOT_DIR')
            if screenshot_dir:
                Path(screenshot_dir).mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(Path(screenshot_dir)/'desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            mobile = page.locator('#analysis-mobile-content')
            for method in networks.DATASETS:
                mobile.locator(f'[data-analysis-method-select="{method}"]').click()
                detail = mobile.locator('.analysis-method-detail')
                expect(detail.locator('table').first).to_be_visible()
                detail.locator('.content-evidence summary').first.click()
                expect(detail.locator('.content-evidence blockquote').first).to_contain_text('apple')
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),391)
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir)/'mobile.png'),full_page=True)
            with self.app.database_connection() as connection:
                connection.execute("DELETE FROM segment_embeddings WHERE item_id='synthetic'")
            mobile.locator('[data-analysis-methods-refresh]').click()
            mobile.locator('[data-analysis-method-select="coding_consistency"]').click()
            expect(mobile.locator('.analysis-method-detail')).to_contain_text('適用外')
            expect(mobile.locator('.analysis-method-detail')).to_contain_text('再計算してください')
            self.assertFalse(errors,errors)
