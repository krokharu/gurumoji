"""Synthetic v1/v2 parity, immutable references, recovery and package size."""
import copy
import io
import json
import os
import sqlite3
import tempfile
import time
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from gurumoji.analysis_store import AnalysisStore, StoreConflict, initialize_store, canonical, csv_bytes
from gurumoji import research_analysis as research
from gurumoji.services.analysis_package import MissingReference, expand_document, _RECOVERIES
from gurumoji.services.derived_analysis_store import DATABASE
from gurumoji.handlers.analysis_queries import AnalysisQueries


class PackageV2Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.addCleanup(self.join_recoveries)
        environment = patch.dict(os.environ, {key: str(self.root / key) for key in
            ('MOJIOKOSI_DATA_DIR', 'MOJIOKOSI_OUTPUT_DIR', 'MOJIOKOSI_BACKUP_DIR')})
        environment.start()
        self.addCleanup(environment.stop)
        self.database = self.root / 'library.sqlite3'
        with self.connect() as connection:
            connection.execute('CREATE TABLE application_metadata (key TEXT PRIMARY KEY,value TEXT)')
            connection.execute('CREATE TABLE speaker_registry (id TEXT)')
            names = ('segments_json','speaker_names_json','speaker_profiles_json','session_profile_json',
                'analysis_config_json','analysis_annotations_json','revision_count','analysis_revision','outline_json','emotion_analysis_json')
            connection.execute('CREATE TABLE library_items (id TEXT PRIMARY KEY,' + ','.join(n + ' TEXT' for n in names) + ')')
            initialize_store(connection)
            connection.execute("INSERT INTO library_items(id) VALUES ('synthetic')")
        self.store = AnalysisStore(self.database, self.connect)
        for name in ('_load_ginza', '_load_sudachi'):
            p = patch.object(research, name, return_value=(None, 'synthetic'))
            p.start()
            self.addCleanup(p.stop)
        self.snapshot = {'conversation_id': 'synthetic', 'config': {}, 'segments': [
            {'id': 'u1','text': '架空の窓口は使いやすい。','speaker': 'A','start': 0,'end': 4}]}

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, request='synthetic-request', *, version=2, datasets=None, result=None, snapshot=None):
        return self.store.save(item_id='synthetic',kind='text_analysis',snapshot=snapshot or self.snapshot,
            result=result or {'parameters': {}, 'methods': [], 'schema_version': 1},
            datasets=datasets or {'values': (['value'], [{'value': None}, {'value': ''}, {'value': 0}, {'value': False}])},
            request_id=request,input_fingerprint='synthetic-input',source_revision=1,analysis_revision=2,
            package_version=version,publish=False)

    def queries(self):
        return AnalysisQueries(store=self.store,find_item=lambda _: {'id':'synthetic'},
            source_fingerprint=lambda _: 'synthetic-input',database_connection=self.connect,
            build_analysis=lambda _: {},public_insight_request=lambda _: None,
            public_transformer_request=lambda _: None,expose_local_paths=False)

    def lexical(self, snapshot=None):
        snapshot = snapshot or self.snapshot
        with research.derived_storage(self.root / DATABASE):
            linguistics = research.build_research_linguistics(snapshot)
        datasets = {name: (list(linguistics[name][0]) if linguistics[name] else ['segment_id'], linguistics[name])
                    for name in ('morphemes','dependencies')}
        return datasets, linguistics

    def wait_recovery(self, run):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                package = self.store.readable_package(run['id'])
                self.join_recoveries()
                return package
            except MissingReference as exc:
                if getattr(exc, 'recovery_status', '') != 'rebuilding':
                    raise
                time.sleep(.02)
        self.fail('recovery did not complete')

    def join_recoveries(self):
        for (root, _), state in list(_RECOVERIES.items()):
            if Path(root).is_relative_to(self.root) and state.get('thread'):
                state['thread'].join(timeout=10)
                self.assertFalse(state['thread'].is_alive(), 'reference recovery outlived its temporary store')

    def test_three_conversations_v1_v2_typed_csv_result_parity_and_smaller_storage(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/analysis_three_conversations.json').read_text(encoding='utf-8'))
        sizes = {1: 0, 2: 0}
        for index, conversation in enumerate(fixture['conversations']):
            snapshot = {**self.snapshot, 'segments': conversation['analysis']['segments']}
            datasets, linguistics = self.lexical(snapshot)
            datasets.update({
                'timeline': (['start','end','speaker'], [{'start':0,'end':None,'speaker':'A'}]),
                'cooccurrence': (['source_node_id','target_node_id','origin'], [{'source_node_id':'word:a','target_node_id':'word:b','origin':'rule'}]),
                'statistics': (['p_value','effect_size','n'], [{'p_value':None,'effect_size':0,'n':2}]),
                'ai_changes': (['segment_id','base_hash','after_hash','change_type'], [{'segment_id':'u1','base_hash':'before','after_hash':'after','change_type':'notation'}]),
            })
            result = {'schema_version':1,'parameters':{},'analysis': {'linguistics':linguistics},
                      'methods':[], 'document': {'claims':[{'text':'架空の所見','segment_ids':['u1']}],
                          'model':'synthetic','prompt_version':'1','usage':{'tokens':3}}}
            old = self.save(f'old-{index}',version=1,datasets=datasets,result=result,snapshot=snapshot)
            new = self.save(f'new-{index}',datasets=datasets,result=result,snapshot=snapshot)
            before = self.store.verified_package(old['id'])
            after = self.store.verified_package(new['id'])
            restored = after[1]
            restored['schema_version'] = 1
            self.assertEqual(restored, before[1])
            self.assertFalse(any(a['name'].endswith('.csv') for a in self.store.artifacts(new['id'])))
            for name in datasets:
                self.assertEqual([r['values'] for r in self.store.read_table(new['id'],name)['rows']], datasets[name][1])
                self.assertEqual(self.store.table_csv(new['id'],name), before[3][f'tables/{name}.csv'])
            for version, run in ((1,old),(2,new)):
                sizes[version] += sum(a['bytes'] for a in self.store.artifacts(run['id']))
        self.assertLess(sizes[2], sizes[1], sizes)
        print('SYNTHETIC_PACKAGE_BYTES', sizes)

    def test_same_input_different_inference_runs_remain_fixed_and_same_id_conflicts(self):
        def data(label):
            return {'segment_classifications': (['segment_id','label','score'], [{'segment_id':'u1','label':label,'score':.7}])}
        first = self.save('inference-one',datasets=data('A'))
        original = self.store.verified_package(first['id'])
        second = self.save('inference-two',datasets=data('B'))
        self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(original, self.store.verified_package(first['id']))
        self.assertEqual(self.save('inference-one',datasets=data('A'))['id'],first['id'])
        with self.assertRaises(StoreConflict):
            self.save('inference-one',datasets=data('B'))
        with self.connect() as connection:
            connection.execute('DELETE FROM segment_labels WHERE run_id=?',(first['id'],))
        with self.assertRaises(MissingReference):
            self.store.readable_package(first['id'])
        self.assertEqual(self.store.read_table(second['id'],'segment_classifications')['rows'][0]['values']['label'],'B')

    def test_legacy_and_v2_readers_preserve_missing_zero_coverage_and_expert_documents(self):
        datasets = {
            'speakers': (['speaker', 'speaking_seconds', 'timed_turn_count', 'missing_time_turn_count'], [
                {'speaker': 'unknown', 'speaking_seconds': None, 'timed_turn_count': 0, 'missing_time_turn_count': 1},
                {'speaker': 'zero', 'speaking_seconds': 0.0, 'timed_turn_count': 1, 'missing_time_turn_count': 0},
                {'speaker': 'partial', 'speaking_seconds': 10.0, 'timed_turn_count': 1, 'missing_time_turn_count': 1}]),
            'timeline': (['start', 'end'], []),
            'measurements': (['segment_id', 'duration', 'missing_reason'], [
                {'segment_id': 'u1', 'duration': None, 'missing_reason': 'unknown_time'},
                {'segment_id': 'u2', 'duration': 0.0, 'missing_reason': ''}]),
        }
        result = {'schema_version': 1, 'parameters': {}, 'methods': [{'method_id': 'participation',
            'expert_review': {'status': 'needs_attention', 'expert_id': 'synthetic-expert'},
            'summaries': [{'text': '時刻不明1発話'}], 'previews': [
                {'dataset_id': 'speakers', 'fields': datasets['speakers'][0], 'rows': datasets['speakers'][1]}]}],
            'orchestration': {'run': {'run_id': 'synthetic-orchestration'},
                'raw_results': [{'claims': [{'text': '架空の所見', 'evidence_ids': ['u1']}]}]}}
        old = self.save('reader-v1', version=1, datasets=datasets, result=result)
        new = self.save('reader-v2', datasets=datasets, result=result)
        restored = self.store.readable_package(new['id'])[1]
        self.assertEqual(restored['schema_version'], 2)
        restored['schema_version'] = 1
        self.assertEqual(self.store.readable_package(old['id'])[1], restored)
        self.assertFalse(any(a['name'].endswith('.csv') for a in self.store.artifacts(new['id'])))
        for run in (old, new):
            exports = {a['name']: a for a in self.store.export_artifacts(run['id'])}
            for name, (fields, rows) in datasets.items():
                self.assertEqual(self.store.read_table(run['id'], name)['row_count'], len(rows))
                self.assertEqual(self.store.read_artifact(exports[f'tables/{name}.csv']['id'])[1], csv_bytes(fields, rows))

    def test_milestone_snapshot_parity_uses_same_request_and_keeps_other_runs_fixed(self):
        kwargs = dict(item_id='synthetic', kind='milestone_analysis', snapshot=self.snapshot,
            result={'parameters': {}, 'methods': []}, datasets={}, input_fingerprint='synthetic-input',
            source_revision=1, analysis_revision=2, publish=False)
        first = self.store.save(request_id='snapshot-parity', **kwargs)
        saved = self.store.readable_package(first['id'])
        repeated = self.store.save(request_id='snapshot-parity', **{**kwargs, 'snapshot': copy.deepcopy(self.snapshot)})
        separate = self.store.save(request_id='separate-milestone', **kwargs)
        self.assertEqual((first['id'], first['fingerprint']), (repeated['id'], repeated['fingerprint']))
        self.assertEqual(first['snapshot_id'], separate['snapshot_id'])
        self.assertEqual(first['id'], separate['id'])
        self.assertEqual(saved, self.store.readable_package(first['id']))

    def test_lexical_loss_is_pure_on_verify_and_background_rebuild_is_hash_identical(self):
        datasets, linguistics = self.lexical()
        run = self.save(datasets=datasets,result={'parameters':{},'analysis':linguistics})
        original = self.store.verified_package(run['id'])
        (self.root / DATABASE).unlink()
        with self.assertRaises(MissingReference):
            self.store.verified_package(run['id'])
        self.assertFalse((self.root / DATABASE).exists())
        self.assertEqual(self.wait_recovery(run),original)
        (self.root / DATABASE).unlink()
        self.assertEqual(self.wait_recovery(run),original)

    def test_lexical_partial_row_loss_recovers_without_changing_package(self):
        datasets, _ = self.lexical()
        run = self.save(datasets=datasets)
        original = self.store.verified_package(run['id'])
        connection = sqlite3.connect(self.root / DATABASE)
        with connection:
            connection.execute('DELETE FROM morphemes WHERE ordinal=0')
        connection.close()
        self.assertEqual(self.wait_recovery(run),original)

    def test_unavailable_parser_and_mismatched_rebuild_never_write_or_display_values(self):
        for mode in ('version','hash'):
            with self.subTest(mode=mode):
                datasets, _ = self.lexical()
                run = self.save('lexical-'+mode,datasets=datasets)
                (self.root / DATABASE).unlink()
                target = 'RESEARCH_ALGORITHM_VERSION' if mode == 'version' else '_analyze_with_fallback'
                value = 'unavailable' if mode == 'version' else ([{'surface':'wrong'}],1)
                p = patch.object(research,target,value) if mode == 'version' else patch.object(research,target,return_value=value)
                with p, self.assertRaises(MissingReference):
                    self.wait_recovery(run)
                self.assertFalse((self.root / DATABASE).exists())
                _RECOVERIES.clear()

    def test_v2_bundle_resolves_references_and_csv_without_saved_csv(self):
        datasets, _ = self.lexical()
        datasets['segment_classifications'] = (['segment_id','label'],[{'segment_id':'u1','label':'draft'}])
        run = self.save(datasets=datasets,result={'parameters':{},'methods':[], 'morphemes':datasets['morphemes'][1]})
        bundle = self.queries().run_bundle(run['id'])
        with zipfile.ZipFile(io.BytesIO(bundle.data)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['references'],{})
            self.assertEqual(manifest['export'],'self_contained')
            tables = {name:json.loads(archive.read(entry['data'])) for name,entry in manifest['typed_tables'].items()}
            document = expand_document(json.loads(archive.read('documents/result.json')),tables,json.loads(archive.read('input.json')))
            self.assertEqual(document['morphemes'],datasets['morphemes'][1])
            for name,(fields,rows) in datasets.items():
                self.assertEqual(archive.read(f'tables/{name}.csv'),csv_bytes(fields,rows))
        self.assertFalse(list(self.store.root.rglob('*.csv')))

    def test_all_v1_readers_keep_original_bytes_and_publication_works(self):
        run = self.save('legacy',version=1)
        original = self.store.verified_package(run['id'])
        query = self.queries()
        self.assertEqual(query.run('synthetic',run['id'])['integrity'],'verified')
        for artifact in self.store.artifacts(run['id']):
            self.assertEqual(query.artifact(artifact['id']).data,original[3][artifact['name']])
            query.run_preview('synthetic',run['id'],artifact['id'])
        query.run_bundle(run['id'])
        self.store._publish_generated_vaults(run['id'])
        self.store._publish_research(run['id'])
        self.assertEqual(self.store.read_table(run['id'],'values')['row_count'],4)
        self.assertEqual(self.store.verified_package(run['id']),original)

    def test_missing_label_status_contains_no_preview_values(self):
        run = self.save(datasets={'segment_classifications': (['segment_id','label'],[{'segment_id':'u1','label':'draft'}])})
        with self.connect() as connection:
            connection.execute('DELETE FROM segment_labels')
        data = self.queries().run('synthetic',run['id'])
        self.assertEqual(data['integrity'],'missing_reference')
        self.assertEqual(data['saved_summary'],{})
        with self.assertRaises(MissingReference):
            self.queries().run_bundle(run['id'])

    def test_vectors_are_fixed_blob_references_and_missing_vectors_are_not_reinferred(self):
        from test_segment_embeddings import result_for
        snapshot = self.snapshot
        transformer = result_for({'item':{'id':'synthetic'},'segments':snapshot['segments']})
        result = {'parameters':{},'analysis':{'transformer':{'result':transformer}}}
        run = self.save('vector-run',result=result)
        saved = self.store.verified_package(run['id'])
        self.assertEqual(saved[1]['analysis']['transformer']['result']['vectors'],transformer['vectors'])
        self.assertIn('segment_embeddings',saved[2]['references'])
        self.assertNotIn(transformer['vectors']['data'].encode(),saved[3]['documents/result.json'])
        with self.connect() as connection:
            connection.execute('DELETE FROM segment_embeddings')
        with self.assertRaises(MissingReference) as missing:
            self.store.readable_package(run['id'])
        self.assertFalse(missing.exception.recoverable)

    def test_model_and_config_changes_under_same_request_are_rejected(self):
        datasets = {'segment_classifications': (['segment_id','label'],[{'segment_id':'u1','label':'draft'}])}
        self.save('fixed-config',datasets=datasets,result={'parameters':{'model':'one'},'prompt_version':'1',
            'classification': {'generated_at':'inference-time-one'}})
        for result in ({'parameters':{'model':'two'},'prompt_version':'1'},
                       {'parameters':{'model':'one'},'prompt_version':'2'},
                       {'parameters':{'model':'one'},'prompt_version':'1',
                        'classification': {'generated_at':'inference-time-two'}}):
            with self.assertRaises(StoreConflict):
                self.save('fixed-config',datasets=datasets,result=result)

    def test_v2_typed_table_tampering_and_nonfinite_values_are_rejected(self):
        empty = self.save('empty-dependencies',datasets={'dependencies': (['segment_id'],[])})
        self.assertEqual(self.store.read_table(empty['id'],'dependencies')['row_count'],0)
        self.assertFalse((self.root / DATABASE).exists())
        literal = {'$table':'values','keys':['value'],'limit':1}
        run = self.save(result={'parameters':{},'literal':literal})
        self.assertEqual(self.store.verified_package(run['id'])[1]['literal'],literal)
        artifact = next(a for a in self.store.artifacts(run['id']) if a['name']=='tables/values.json')
        path = self.store.root / artifact['path']
        value = json.loads(path.read_bytes())
        value['columns'][0]['observed_types'] = ['string']
        path.write_bytes(canonical(value))
        with self.assertRaises(StoreConflict):
            self.store.verified_package(run['id'])
        with self.assertRaises((ValueError,StoreConflict)):
            self.save('nonfinite',datasets={'values': (['value'],[{'value':float('nan')}])})

    def test_three_conversation_total_storage_includes_primary_and_derived_databases(self):
        fixture_data = json.loads((Path(__file__).parent/'fixtures/analysis_three_conversations.json').read_text(encoding='utf-8'))
        sizes = {}
        for version in (1,2):
            measurement = PackageV2Tests()
            measurement.setUp()
            try:
                for index, conversation in enumerate(fixture_data['conversations']):
                    snapshot = {**measurement.snapshot,'segments':conversation['analysis']['segments']}
                    datasets, linguistics = measurement.lexical(snapshot)
                    labels = [{'segment_id':snapshot['segments'][0]['id'],'label':'synthetic','score':.7}]
                    datasets['segment_classifications'] = (list(labels[0]),labels)
                    measurement.save(f'measure-{index}',version=version,datasets=datasets,
                        snapshot=snapshot,result={'parameters':{'model':'synthetic'},'analysis':linguistics,'labels':labels})
                sizes[version] = {'packages':sum(p.stat().st_size for p in measurement.store.root.rglob('*') if p.is_file()),
                    'primary_db':measurement.database.stat().st_size,'derived_db':(measurement.root/DATABASE).stat().st_size}
                sizes[version]['total'] = sum(sizes[version].values())
            finally:
                measurement.doCleanups()
        self.assertLess(sizes[2]['total'],sizes[1]['total'],sizes)
        print('SYNTHETIC_TOTAL_BYTES',sizes)

    def test_label_provenance_corruption_is_missing_and_never_replaced(self):
        run = self.save(datasets={'segment_classifications': (['segment_id','label'],[{'segment_id':'u1','label':'draft'}])})
        with self.connect() as connection:
            connection.execute("UPDATE segment_labels SET model_revision='tampered'")
        with self.assertRaises(MissingReference):
            self.store.readable_package(run['id'])


if __name__ == '__main__':
    unittest.main()
