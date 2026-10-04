"""Read-only fixed-package contracts; temporary synthetic SQLite/files only."""
import contextlib
import sqlite3
import tempfile
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

import app
import test_content_analysis as support
from gurumoji.analysis_store import AnalysisStore, canonical
from gurumoji.analysis_pipeline import AnalysisPipelineService


class FixedRunTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests('test_generated_result_persists_and_becomes_stale_on_edit')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.store = app.analysis_archive_store()
        self.counter = 0

    def save(self, *, result=None, datasets=None, kind='text_analysis'):
        self.counter += 1
        return self.store.save(
            item_id='content', kind=kind,
            snapshot={'sequence': self.counter, 'segments': [
                {'id': 'saved-zero', 'text': '<img src=x onerror=alert(1)>', 'role': None,
                 'speaker': 'saved-speaker', 'start': 0, 'end': None}]},
            result=result if result is not None else {'parameters': {'definition_version': 7},
                'zero': 0, 'missing': None, 'empty': '', 'rows': [{'id': 'saved-zero', 'value': None}]},
            datasets=datasets if datasets is not None else {'values': (['id','value','reason'], [
                {'id':'zero','value':0,'reason':''}, {'id':'missing','value':None,'reason':'not_recorded'}])},
            request_id=f'fixed-request-{self.counter:05}', input_fingerprint=f'saved-input-{self.counter}',
            source_revision=3, analysis_revision=4, publish=False)

    def url(self, run):
        return f'/api/library/content/analysis/runs/{run["id"]}'

    def artifact(self, run, name):
        return next(a for a in self.store.artifacts(run['id']) if a['name'] == name)

    def dump(self):
        with self.store.connect() as conn:
            db = '\n'.join(conn.iterdump())
        files = {str(p.relative_to(self.store.root)): p.read_bytes() for p in self.store.root.rglob('*') if p.is_file()}
        return db, files

    def replace_artifact(self, run, name, data):
        """Create deliberately invalid yet hash-consistent synthetic packages."""
        artifact = self.artifact(run, name)
        (self.store.root / artifact['path']).write_bytes(data)
        artifact.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
        with self.store.connect() as conn:
            conn.execute('UPDATE analysis_artifacts SET sha256=?,bytes=? WHERE id=?',
                         (artifact['sha256'],artifact['bytes'],artifact['id']))
        if name != 'manifest.json':
            manifest = self.artifact(run, 'manifest.json')
            value = json.loads((self.store.root / manifest['path']).read_bytes())
            value['artifacts'] = [artifact if a['name'] == name else a for a in value['artifacts']]
            self.replace_artifact(run, 'manifest.json', canonical(value))

    def test_exact_run_outside_newest_100_and_ownership(self):
        run = self.save()
        for _ in range(100):
            self.save()
        self.assertNotIn(run['id'], [r['id'] for r in self.store.list('content')])
        response = self.client.get(self.url(run))
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['run']['id'], run['id'])
        for url in ['/api/library/content/analysis/runs/absent',
                    f'/api/library/wrong/analysis/runs/{run["id"]}']:
            self.assertEqual(self.client.get(url).status_code, 404)
        with self.store.connect() as conn:
            conn.execute("DELETE FROM library_items WHERE id='content'")
        self.assertEqual(self.client.get(self.url(run)).status_code, 404)

    def test_get_preview_export_are_read_only_and_preserve_saved_bytes(self):
        run = self.save()
        before = self.dump()
        with patch.object(app, 'run_analysis_pipeline_method') as method, \
             patch.object(app, 'group_analysis_for_row') as live, \
             patch.object(app, 'call_ai_json') as ai, \
             patch.object(AnalysisStore, 'publish') as publish, \
             patch.object(AnalysisStore, 'retry') as retry, \
             patch.object(AnalysisPipelineService, 'status') as status:
            payload = self.client.get(self.url(run)).get_json()
            self.assertEqual(payload['integrity'], 'verified')
            self.assertEqual(payload['run']['source_revision'], 3)
            self.assertEqual(payload['provenance']['input_fingerprint'], 'saved-input-1')
            self.assertTrue(payload['current_input']['stale'])
            self.assertNotIn(str(self.store.root), json.dumps(payload))
            for artifact in payload['run']['artifacts']:
                self.assertNotIn('path', artifact)
                self.assertEqual(len(artifact['sha256']), 64)
                response = self.client.get(self.url(run)+'/previews/'+artifact['id'])
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertNotIn(str(self.store.root), json.dumps(response.get_json()))
                self.assertNotIn('"path":', response.get_json()['preview'].get('text',''))
                raw = self.client.get(artifact['url'])
                self.assertEqual(hashlib.sha256(raw.data).hexdigest(),artifact['sha256'])
            bundle = self.client.get(f'/api/analysis/runs/{run["id"]}/export.zip')
            self.assertEqual(bundle.status_code, 200)
            with zipfile.ZipFile(io.BytesIO(bundle.data)) as archive:
                for artifact in self.store.artifacts(run['id']):
                    self.assertEqual(archive.read(artifact['name']),self.store.read_artifact(artifact['id'])[1])
            for spy in [method, live, ai, publish, retry, status]:
                spy.assert_not_called()
        self.assertEqual(before, self.dump())

    def test_source_edits_never_join_into_saved_preview_or_download(self):
        run = self.save()
        artifact = self.artifact(run,'input.json')
        url = self.url(run)+'/previews/'+artifact['id']
        before = self.client.get(url).get_json()
        raw = self.client.get('/api/analysis/artifacts/'+artifact['id']).data
        with self.store.connect() as conn:
            conn.execute("UPDATE library_items SET segments_json=?,speaker_names_json=?,revision_count=99,analysis_revision=99 WHERE id='content'",
                         (json.dumps([{'id':'saved-zero','text':'CURRENT-CHANGED','role':'participant','start':999,'end':1000}]),
                          json.dumps({'saved-speaker':'CURRENT-NAME'})))
        self.assertEqual(before,self.client.get(url).get_json())
        self.assertEqual(raw,self.client.get('/api/analysis/artifacts/'+artifact['id']).data)
        self.assertNotIn('CURRENT',json.dumps(before))
        self.assertIn('null',before['preview']['text'])
        self.assertIn('"start": 0',before['preview']['text'])

    def test_bounded_json_and_table_previews_keep_full_downloads(self):
        run=self.save(result={'parameters':{},'zero':0,'missing':None,'empty':'','large':'あ'*20000},
                      datasets={'large':(['c'+str(i) for i in range(30)],
                                        [{f'c{i}': ('x'*10000 if i == 0 else str(n)) for i in range(30)} for n in range(100)])})
        for name in ['result.json','tables/large.csv']:
            artifact=self.artifact(run,name)
            response=self.client.get(self.url(run)+'/previews/'+artifact['id'])
            self.assertEqual(response.status_code,200,response.get_json())
            value=response.get_json()['preview']
            self.assertTrue(value['truncated'])
            if value['format']=='table':
                self.assertEqual((value['total_rows'],value['shown_rows'],value['total_columns']),(100,20,30))
                self.assertEqual(len(value['columns']),24)
                self.assertTrue(all(len(cell)<=256 for row in value['rows'] for cell in row))
                self.assertLessEqual(sum(len(c.encode()) for r in value['rows'] for c in r)+sum(len(c.encode()) for c in value['columns']),16384)
            else:
                self.assertLessEqual(len(value['text'].encode()),16384)
            self.assertEqual(len(self.client.get('/api/analysis/artifacts/'+artifact['id']).data),artifact['bytes'])

    def test_valid_very_long_csv_cells_remain_readable_and_complete(self):
        run = self.save(datasets={'large': (['value'], [{'value':'あ' * 200000}])})
        artifact = self.artifact(run,'tables/large.csv')
        response = self.client.get(self.url(run))
        self.assertEqual(response.status_code,200,response.get_json())
        preview = self.client.get(self.url(run)+'/previews/'+artifact['id']).get_json()['preview']
        self.assertTrue(preview['truncated'])
        self.assertEqual(len(preview['rows'][0][0]),256)
        bundle = self.client.get(f'/api/analysis/runs/{run["id"]}/export.zip')
        self.assertEqual(bundle.status_code,200)
        with zipfile.ZipFile(io.BytesIO(bundle.data)) as archive:
            self.assertEqual(archive.read(artifact['name']),self.store.read_artifact(artifact['id'])[1])

    def test_human_summary_uses_only_saved_fields_and_is_bounded(self):
        methods = [{'title':'保存した手法','method_id':'saved-method','method_version':'old-version',
                    'status':'not_run','analysis_unit':None,'summaries':[{'title':'集計','text':'保存時の有効N=0'}],
                    'findings':[{'title':'<script>','text':'保存された見解'}], 'limitations':['保存時の制約']}]
        run = self.save(result={'parameters':{'definitions':[{'definition_id':'adopted','version':7,'name':'固定定義'}]},'methods':methods})
        summary = self.client.get(self.url(run)).get_json()['saved_summary']
        self.assertEqual(summary['methods'][0]['status'],'not_run')
        self.assertIsNone(summary['methods'][0]['analysis_unit'])
        self.assertEqual(summary['methods'][0]['summaries'][0]['text'],'保存時の有効N=0')
        self.assertEqual(summary['definitions'][0]['version'],'7')
        methods = [{'title':'long','summaries':[{'text':'あ'*10000}]*30,'limitations':['制約'*1000]*30}]*30
        run = self.save(result={'parameters':{},'methods':methods})
        summary = self.client.get(self.url(run)).get_json()['saved_summary']
        self.assertTrue(summary['truncated'])
        self.assertLessEqual(len(summary['methods']),12)
        self.assertEqual(summary['total_methods'],30)

    def test_saved_computation_versions_remain_independent_and_typed(self):
        from gurumoji.handlers.analysis_queries import saved_result_summary
        versions = ["focus-group-local-4", "focus-group-local-5", "focus-group-local-6", 0, 7.5,
                    None, "", "   ", True, False, [], {}, float("inf")]
        expected = ["recorded"] * 5 + ["missing"] * 3 + ["unsupported"] * 5
        for value, status in zip(versions, expected):
            with self.subTest(value=value):
                summary = saved_result_summary({"methods": [{"method_version": value, "engine": {"version": value}}],
                                                "algorithms": {"automatic": value}})
                method = summary["methods"][0]
                self.assertEqual(method["engine_version_status"], status)
                self.assertEqual(method["method_version_status"], status)
                self.assertEqual(summary["algorithms"][0]["status"], status)
                if status == "recorded":
                    self.assertEqual(method["engine_version"], str(value))
                    self.assertEqual(summary["algorithms"][0]["version"], str(value))
                else:
                    self.assertIsNone(method["engine_version"])
        run = self.save(result={"parameters": {}, "algorithms": {"automatic": "saved-global-v4"},
            "methods": [{"title": "Old", "method_version": "saved-registry-v9", "engine": {"version": "saved-engine-v5"}},
                        {"title": "Missing", "method_version": "saved-registry-v3"}]})
        before = self.dump()
        response = self.client.get(self.url(run))
        self.assertEqual(response.status_code, 200, response.get_json())
        summary = response.get_json()["saved_summary"]
        self.assertEqual(summary["methods"][0]["engine_version"], "saved-engine-v5")
        self.assertEqual(summary["methods"][0]["method_version"], "saved-registry-v9")
        self.assertEqual(summary["methods"][1]["engine_version_status"], "missing")
        self.assertEqual(summary["algorithms"], [{"name": "automatic", "version": "saved-global-v4", "status": "recorded"}])
        self.assertEqual(before, self.dump())

    def test_saved_version_projection_is_bounded_without_converting_clipping_to_missing(self):
        from gurumoji.handlers.analysis_queries import saved_result_summary
        methods = [{"method_id": "id" * 300, "title": "title" * 300,
                    "method_version": "registry" * 300, "engine": {"version": "engine" * 300},
                    "summaries": [{"title": "summary" * 300, "text": "text" * 300}] * 5,
                    "findings": [{"title": "finding" * 300, "text": "text" * 300}] * 5,
                    "limitations": ["limit" * 300] * 5}] * 12
        summary = saved_result_summary({"methods": methods, "algorithms": {f"algorithm-{i}": "v" * 10000 for i in range(40)}})
        self.assertTrue(summary["truncated"])
        self.assertEqual(summary["total_algorithms"], 40)
        self.assertLessEqual(len(summary["algorithms"]), 20)
        self.assertTrue(any(row["version"] == "" and row["status"] == "recorded" for row in summary["algorithms"]))
        source_text = []
        for method in summary["methods"]:
            source_text.extend(method.get(key) for key in ("method_id", "method_version", "engine_version", "title", "status", "analysis_unit"))
            source_text.extend(value for key in ("summaries", "findings") for row in method[key] for value in row.values())
            source_text.extend(method["limitations"])
        source_text.extend(value for row in summary["algorithms"] for key, value in row.items() if key != "status")
        self.assertLessEqual(sum(len(value.encode()) for value in source_text if isinstance(value, str)), 16384)

    def test_missing_corrupt_malformed_and_future_packages_stop_without_changes(self):
        for broken in ['missing','corrupt','bad-json','bad-csv','bad-manifest','future','incomplete']:
            with self.subTest(broken=broken):
                run=self.save()
                artifact=self.artifact(run,'result.json')
                if broken=='missing': (self.store.root/artifact['path']).unlink()
                elif broken=='corrupt': (self.store.root/artifact['path']).write_bytes(b'changed')
                elif broken=='bad-json': self.replace_artifact(run,'result.json',b'{broken')
                elif broken=='bad-csv': self.replace_artifact(run,'tables/values.csv',b'a,b\n"unterminated')
                elif broken in ['future','bad-manifest']:
                    manifest=self.artifact(run,'manifest.json')
                    value=json.loads((self.store.root/manifest['path']).read_bytes())
                    value['schema_version']=999 if broken=='future' else 1
                    if broken=='bad-manifest': value['artifacts']=[]
                    self.replace_artifact(run,'manifest.json',canonical(value))
                else:
                    with self.store.connect() as conn: conn.execute("UPDATE analysis_runs SET status='writing' WHERE id=?",(run['id'],))
                before=self.dump()
                self.assertEqual(self.client.get(self.url(run)).status_code,409)
                self.assertEqual(self.client.get(self.url(run)+'/previews/'+artifact['id']).status_code,409)
                self.assertIn(self.client.get(f'/api/analysis/runs/{run["id"]}/export.zip').status_code,[404,409])
                self.assertEqual(before,self.dump())

    def test_unknown_legacy_provenance_stays_unknown(self):
        run=self.save()
        artifact=self.artifact(run,'manifest.json')
        value=json.loads((self.store.root/artifact['path']).read_bytes())
        for key in ['schema_version','method_version','input_fingerprint','source_revision','analysis_revision']:
            value.pop(key,None)
        self.replace_artifact(run,'manifest.json',canonical(value))
        response=self.client.get(self.url(run))
        self.assertEqual(response.status_code,200,response.get_json())
        for key in ['schema_version','method_version','input_fingerprint','source_revision','analysis_revision']:
            self.assertIsNone(response.get_json()['provenance'][key])
        self.assertFalse(response.get_json()['run']['vault_outputs_complete'])

    def test_nonfinite_json_and_future_result_schema_are_unavailable(self):
        for data in [b'{"parameters":{},"value":NaN}', b'{"parameters":{},"value":Infinity}',
                     b'{"parameters":{},"schema_version":999}']:
            run = self.save()
            self.replace_artifact(run,'result.json',data)
            self.assertEqual(self.client.get(self.url(run)).status_code,409)

    def test_structurally_invalid_json_is_integrity_error(self):
        cases = [(name, value) for name in ['manifest.json','input.json','result.json','parameters.json']
                 for value in [None, [], 1, "not-an-object"]]
        cases += [('manifest.json', {'schema_version': 1, 'artifacts': entries})
                  for entries in [None, [None], ['entry'], [{}], [{'name': []}]]]
        for name, value in cases:
            with self.subTest(name=name, value=value):
                run = self.save()
                self.replace_artifact(run, name, canonical(value))
                before = self.dump()
                response = self.client.get(self.url(run))
                self.assertEqual(response.status_code, 409, response.get_json())
                self.assertEqual(before, self.dump())

    def test_pipeline_history_retry_success_is_distinct_from_older_workflow_ledger(self):
        payload = self.fixture.payload('fixed-pipeline-request-0001')
        payload.update(mode='automatic',definition_ids=[],publication_targets=['input','orchestrator','visualization'])
        from gurumoji.analysis_store import StoreConflict
        with patch.object(AnalysisPipelineService,'_schedule',return_value=None), patch.object(app,'call_ai_json',side_effect=AssertionError('no AI')):
            response = self.client.post(self.fixture.url+'/pipelines',json=payload)
            self.assertEqual(response.status_code,202,response.get_json())
            pipeline_id = response.get_json()['pipeline_id']
            with patch.object(AnalysisStore,'source_notes',side_effect=StoreConflict('synthetic conflict')):
                app.analysis_pipeline_service()._run(pipeline_id,'http://synthetic.invalid')
            state = app.analysis_pipeline_service().status('content',pipeline_id,ensure_running=False)
            run_id = state['result_run']['id']
            response = self.client.post('/api/analysis/runs/'+run_id+'/vault')
            self.assertEqual(response.status_code,200,response.get_json())
            current = self.client.get('/api/library/content/analysis/runs/'+run_id).get_json()['run']
            self.assertTrue(current['vault_outputs_complete'])
            self.assertEqual(current['publication_attempts'][-1]['status'],'completed')
            self.assertEqual(next(r for r in current['publication_records'] if r['target_role']=='research')['status'],'conflict')

    def test_empty_pipeline_scope_is_read_from_verified_saved_package(self):
        payload = self.fixture.payload('fixed-pipeline-empty-0001')
        payload.update(mode='automatic',definition_ids=[],publication_targets=[])
        with patch.object(AnalysisPipelineService,'_schedule',return_value=None):
            response = self.client.post(self.fixture.url+'/pipelines',json=payload)
            self.assertEqual(response.status_code,202,response.get_json())
            pipeline_id = response.get_json()['pipeline_id']
            app.analysis_pipeline_service()._run(pipeline_id,'http://synthetic.invalid')
            state = app.analysis_pipeline_service().status('content',pipeline_id,ensure_running=False)
            run_id = state['result_run']['id']
            value = self.client.get('/api/library/content/analysis/runs/'+run_id).get_json()['run']
            self.assertEqual(value['saved_publication_targets'],[])
            self.assertEqual(value['publication_attempts'],[])
            self.assertTrue(all(r['status']=='not_selected' for r in value['publication_records']))

    def rename_catalog_artifact(self, run, old_name, new_name):
        artifact = self.artifact(run, old_name)
        with self.store.connect() as connection:
            connection.execute("UPDATE analysis_artifacts SET name=? WHERE id=?", (new_name, artifact["id"]))
        artifact["name"] = new_name
        manifest_artifact = self.artifact(run, "manifest.json")
        manifest = json.loads((self.store.root / manifest_artifact["path"]).read_bytes())
        manifest["artifacts"] = [artifact if row["name"] == old_name else row for row in manifest["artifacts"]]
        self.replace_artifact(run, "manifest.json", canonical(manifest))
        return artifact

    def test_unsafe_zip_member_names_stop_without_writing_or_extracting(self):
        for name in ("../outside.csv", "/absolute.csv", "C:/outside.csv", "C:outside.csv", "folder\\outside.csv",
                     "folder/../outside.csv", "./data.csv", "folder//data.csv", "folder/", "folder/./data.csv",
                     "folder/data.csv ", "folder/data.csv.", "folder/NUL.csv", "folder/COM¹.csv", "folder/data:stream",
                     "folder/data?.csv", "bad\x00name.csv", "bad\x7fname.csv"):
            with self.subTest(name=name):
                run = self.save()
                artifact = self.rename_catalog_artifact(run, "tables/values.csv", name)
                before = self.dump()
                self.assertEqual(self.client.get(self.url(run)).status_code, 409)
                self.assertEqual(self.client.get(self.url(run) + "/previews/" + artifact["id"]).status_code, 409)
                self.assertEqual(self.client.get(f'/api/analysis/runs/{run["id"]}/export.zip').status_code, 409)
                self.assertEqual(self.client.get('/api/analysis/artifacts/' + artifact["id"]).status_code, 409)
                self.assertEqual(before, self.dump())

    def test_safe_nested_unicode_members_keep_exact_names_and_bytes(self):
        for name in ("tables/nested/data.csv", "tables/日本語の表.csv", "tables/.hidden/値 1.csv", "tables/cafe\u0301.csv"):
            with self.subTest(name=name):
                run = self.save()
                artifact = self.rename_catalog_artifact(run, "tables/values.csv", name)
                before = self.dump()
                self.assertEqual(self.client.get(self.url(run)).status_code, 200)
                response = self.client.get(f'/api/analysis/runs/{run["id"]}/export.zip')
                self.assertEqual(response.status_code, 200)
                with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
                    self.assertEqual(archive.read(name), self.store.read_artifact(artifact["id"])[1])
                self.assertEqual(before, self.dump())

    def test_archive_aliases_and_file_directory_collisions_are_rejected(self):
        pairs = [("tables/Case.csv", "tables/case.csv"),
                 ("tables/café.csv", "tables/cafe\u0301.csv"),
                 ("tables/note", "tables/note/data.csv")]
        for first_name, second_name in pairs:
            with self.subTest(names=(first_name, second_name)):
                run = self.save(datasets={"one": (["value"], [{"value": 1}]), "two": (["value"], [{"value": 2}])})
                self.rename_catalog_artifact(run, "tables/one.csv", first_name)
                self.rename_catalog_artifact(run, "tables/two.csv", second_name)
                before = self.dump()
                self.assertEqual(self.client.get(self.url(run)).status_code, 409)
                self.assertEqual(self.client.get(f'/api/analysis/runs/{run["id"]}/export.zip').status_code, 409)
                self.assertEqual(before, self.dump())

    def test_snapshot_binding_rejects_hash_consistent_changed_input(self):
        run = self.save()
        artifact = self.artifact(run, "input.json")
        snapshot = json.loads((self.store.root / artifact["path"]).read_bytes())
        snapshot["segments"][0]["text"] = "synthetic changed input"
        self.replace_artifact(run, "input.json", canonical(snapshot))
        before = self.dump()
        self.assertEqual(self.client.get(self.url(run)).status_code, 409)
        self.assertEqual(self.client.get(self.url(run) + "/previews/" + artifact["id"]).status_code, 409)
        self.assertEqual(self.client.get(f'/api/analysis/runs/{run["id"]}/export.zip').status_code, 409)
        self.assertEqual(before, self.dump())

    def test_snapshot_binding_uses_original_canonicalization_and_library_id(self):
        from gurumoji.analysis_store import digest
        run = self.save()
        artifact = self.artifact(run, "input.json")
        snapshot = json.loads((self.store.root / artifact["path"]).read_bytes())
        self.assertEqual(snapshot["library_id"], self.store.library_id())
        self.assertEqual(digest(snapshot), run["snapshot_id"])
        # Semantically identical saved JSON need not be serialized identically.
        self.replace_artifact(run, "input.json", json.dumps(snapshot, ensure_ascii=True, indent=2).encode())
        before = self.dump()
        self.assertEqual(self.client.get(self.url(run)).status_code, 200)
        self.assertEqual(before, self.dump())

    def test_other_run_artifact_is_not_accepted(self):
        run=self.save(); other=self.save()
        artifact=self.artifact(other,'result.json')
        self.assertEqual(self.client.get(self.url(run)+'/previews/'+artifact['id']).status_code,404)


class PublicSnapshotTests(unittest.TestCase):
    def test_attempt_outputs_records_and_complete_share_one_read_snapshot(self):
        # A WAL writer commits immediately after the attempt SELECT. Reader must
        # keep the original snapshot for its later publication-record SELECT.
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'fixture.sqlite'
            roles = ['research','input','orchestrator','visualization']
            row = dict(id='run', item_id='item', kind='milestone_analysis', source_revision=1,
                       analysis_revision=1, created_at='saved', status='completed', vault_status='completed',
                       stale=0, error='', provider='', model='', note_path='', fingerprint='fp',
                       input_fingerprint='input', snapshot_id='snapshot')
            def connect_raw():
                connection = sqlite3.connect(database)
                connection.row_factory = sqlite3.Row
                return connection
            def insert(connection, number):
                outcomes = {role:{'status':'failed' if number == 1 and role == 'research' else 'published'} for role in roles}
                connection.execute('INSERT INTO analysis_publication_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    ('attempt'+str(number),'run',number,'fp',json.dumps(roles[1:]),json.dumps(roles),json.dumps(roles),
                     json.dumps(outcomes),'incomplete' if number == 1 else 'completed','','saved','saved'))
            with connect_raw() as connection:
                connection.execute('PRAGMA journal_mode=WAL')
                connection.execute('CREATE TABLE analysis_artifacts(run_id TEXT,name TEXT)')
                connection.execute('CREATE TABLE analysis_publication_attempts(attempt_id TEXT,run_id TEXT,sequence INTEGER,package_hash TEXT,requested_json TEXT,effective_json TEXT,executed_json TEXT,outcomes_json TEXT,status TEXT,error TEXT,created_at TEXT,ended_at TEXT)')
                connection.execute('CREATE TABLE analysis_pipeline_requests(pipeline_id TEXT,result_run_id TEXT,created_at TEXT)')
                connection.execute("INSERT INTO analysis_pipeline_requests VALUES ('p','run','saved')")
                connection.execute('CREATE TABLE analysis_pipeline_publications(pipeline_id TEXT,target_role TEXT,status TEXT,error TEXT,result_run_id TEXT,package_hash TEXT)')
                connection.executemany('INSERT INTO analysis_pipeline_publications VALUES (?,?,?,?,?,?)',
                    [('p',role,'failed' if role == 'research' else 'published','','run','fp') for role in roles])
                insert(connection,1)
            statements = []
            class Cursor:
                def __init__(self,cursor,sql): self.cursor,self.sql = cursor,sql
                def fetchall(self):
                    rows = self.cursor.fetchall()
                    if 'FROM analysis_publication_attempts' in self.sql:
                        with connect_raw() as writer:
                            insert(writer,2)
                            writer.execute("UPDATE analysis_pipeline_publications SET status='published'")
                    return rows
                def __getattr__(self,name): return getattr(self.cursor,name)
            class Connection:
                def __init__(self,connection): self.connection = connection
                def execute(self,sql,args=()):
                    statements.append(sql.split()[0].upper())
                    return Cursor(self.connection.execute(sql,args),sql)
            @contextlib.contextmanager
            def connect():
                connection = connect_raw()
                try:
                    with connection: yield Connection(connection)
                finally: connection.close()
            store = AnalysisStore.__new__(AnalysisStore)
            store.connect = connect
            store.vault_notes = lambda _run: {}
            value = store.public(row)
            self.assertEqual(value['publication_attempts'][-1]['attempt_id'],'attempt1')
            self.assertEqual(value['publication_outcomes']['research']['status'],'failed')
            self.assertEqual(next(r for r in value['publication_records'] if r['target_role']=='research')['status'],'failed')
            self.assertFalse(value['vault_outputs_complete'])
            self.assertEqual(set(statements), {'BEGIN','SELECT'})


if __name__ == '__main__':
    unittest.main()
