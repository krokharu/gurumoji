"""D3–D5 acceptance with a temporary database and fictional conversations."""

import copy
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from support import use_temporary_library
from gurumoji.analysis_store import AnalysisStore, digest
from gurumoji.services import data_catalog as catalog, library_trash


class DataCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gurumoji-data-catalog-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        paths_patch = patch.multiple(app,
            DATA_DIRECTORY=self.root, MEDIA_DIRECTORY=self.root / 'media',
            THUMBNAIL_DIRECTORY=self.root / 'thumbnails', UPLOAD_DIRECTORY=self.root / 'uploads',
            TRAINING_DIRECTORY=self.root / 'training', TRAINING_AUDIO_DIRECTORY=self.root / 'training/audio',
            TRAINING_JSONL_FILE=self.root / 'training/corrections.jsonl', TRAINING_MANIFEST_FILE=self.root / 'training/manifest.csv',
            CUSTOM_VOCABULARY_FILE=self.root / 'custom_vocabulary.json')
        paths_patch.start(); self.addCleanup(paths_patch.stop)
        use_temporary_library(self, self.root, output=self.root / 'output')
        self.client = app.app.test_client()
        for identity in ('a', 'b', 'c'):
            app.upsert_library_item(item_id=identity, source_name='架空会話' + identity,
                output_dir=self.root / identity, media_path=None, language='ja',
                segments=[{'id': 'u1', 'speaker': 'P1', 'start': 0, 'end': 2, 'text': '架空の会話です。'}],
                speaker_names={'P1': '架空話者'}, outline=None, emotion_analysis=None,
                files=[], write_srt=False, write_json=True,
                session_profile={'comparison_group': '架空の調査'})
        self.store = AnalysisStore(self.root / 'library.sqlite3', app.database_connection)
        self.store_patch = patch.object(app, 'analysis_archive_store', return_value=self.store)
        self.store_patch.start(); self.addCleanup(self.store_patch.stop)
        self.publish_patch = patch.object(self.store, 'publish')
        self.publish_patch.start(); self.addCleanup(self.publish_patch.stop)

    def define(self, key='地域', scope='conversation', **extra):
        response = self.client.put('/api/library/attribute-definitions', json={
            'key': key, 'scope': scope, 'data_type': 'string', **extra})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def attributes(self, identity, values):
        return self.client.put('/api/library/' + identity + '/attributes', json={'attributes': values})

    def tag(self, label='年度'):
        response = self.client.post('/api/library/tags', json={'name': label})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def group(self, **extra):
        response = self.client.post('/api/library/data-groups', json={'name': '架空集合', **extra})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def assign(self, entity, identity, ids, remove=False):
        return self.client.put(f'/api/library/{entity}/{identity}/members', json={'item_ids': ids, 'remove': remove})

    def freeze(self, ids=('a', 'b'), **extra):
        with app.database_connection() as db:
            return catalog.freeze(db, list(ids), **extra)

    def preview(self, **extra):
        payload = {'item_ids': ['a', 'b'], **extra}
        response = self.client.post('/api/library/interview-comparison', json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        return payload, response.get_json()

    def save_comparison(self, payload, preview, request_id='catalog-comparison-0001'):
        return self.client.post('/api/library/interview-comparison/runs', json={**payload,
            'input_fingerprints': preview['input_fingerprints'],
            'target_snapshot_hash': preview['target_snapshot']['hash'], 'request_id': request_id})

    def test_conversation_rejects_undefined_wrong_type_and_allowed_value_atomically(self):
        self.assertEqual(self.attributes('a', {'unknown': 'x'}).status_code, 400)
        self.define(allowed_values=['A', 'B'])
        self.assertEqual(self.attributes('a', {'地域': 'A'}).status_code, 200)
        for values in ({'地域': 1}, {'地域': 'C'}, {'地域': 'B', 'unknown': 'x'}):
            self.assertEqual(self.attributes('a', values).status_code, 400)
            self.assertEqual(self.client.get('/api/library/a/attributes').get_json()['attributes'], {'地域': 'A'})
        with app.database_connection() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO conversation_attributes VALUES ('a','unknown','1','researcher','now')")

    def test_numeric_boolean_and_null_attributes(self):
        for key, kind in (('年度', 'integer'), ('得点', 'number'), ('同意', 'boolean')):
            self.define(key, data_type=kind)
        self.assertEqual(self.attributes('a', {'年度': 2026, '得点': 0, '同意': False}).status_code, 200)
        for key, value in (('年度', True), ('年度', 2.5), ('得点', '3'), ('得点', float('inf')), ('同意', 1)):
            self.assertEqual(self.attributes('a', {key: value}).status_code, 400)
        self.assertEqual(self.attributes('a', {'得点': None}).status_code, 200)

    def test_existing_speaker_keys_are_discovered_once_and_deletion_cleans_projection(self):
        with app.database_connection() as db:
            db.execute("DROP TRIGGER speaker_attributes_insert_v1")
            db.execute("DELETE FROM application_metadata WHERE key='data_catalog_version'")
            db.execute("INSERT INTO speaker_registry(id,display_name,attributes_json,created_at,updated_at) VALUES ('speaker01','架空話者',?, 'now','now')", ('{"専門":"研究","数値":3,"真偽":false,"欠測":null}',))
            before = db.execute("SELECT attributes_json FROM speaker_registry").fetchone()[0]
            catalog.initialize(db)
            self.assertEqual(db.execute("SELECT attributes_json FROM speaker_registry").fetchone()[0], before)
            defs = catalog.definitions(db)
            self.assertTrue(all(d['origin'] == 'discovered' and d['data_type'] == 'string' and d['type_status'] == '型未確定' for d in defs))
            self.assertEqual(db.execute('SELECT count(*) FROM speaker_attributes').fetchone()[0], 4)
            self.assertFalse(catalog.check(db)['ok'])
            catalog.initialize(db)
            db.execute("DELETE FROM speaker_registry WHERE id='speaker01'")
            self.assertEqual(db.execute('SELECT count(*) FROM speaker_attributes').fetchone()[0], 0)

    def test_csv_unknown_and_empty_columns_auto_register_without_rejecting_import(self):
        response = self.client.post('/api/speakers/import', data={
            'registry_revision': '0', 'csv_file': (io.BytesIO('氏名,専門,空欄\n架空話者,研究,\n'.encode('utf-8')), 'fiction.csv')}, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200, response.get_json())
        with app.database_connection() as db:
            self.assertEqual({d['key'] for d in catalog.definitions(db)}, {'専門', '空欄'})
            self.assertEqual({r[0]: json.loads(r[1]) for r in db.execute('SELECT key,value_json FROM speaker_attributes')}, {'専門': '研究', '空欄': ''})

    def test_researcher_definition_version_reports_existing_mismatch_without_rejecting_speaker_save(self):
        app.save_speaker_registry_records([{'id': 'speaker01', 'display_name': '架空話者', 'attributes': {'年度': '未確定'}}], expected_revision=0)
        definition = self.define('年度', 'speaker', data_type='integer', version=1)
        self.assertEqual(definition['version'], 2)
        app.save_speaker_registry_records([{'id': 'speaker01', 'display_name': '架空話者', 'attributes': {'年度': '自由入力'}}], expected_revision=1)
        with app.database_connection() as db:
            self.assertEqual(catalog.check(db)['issues'][0]['reason'], 'attribute_value_mismatch')
        self.assertEqual(self.client.put('/api/library/attribute-definitions', json={**definition, 'version': 1}).status_code, 400)

    def test_changed_conversation_definition_reports_existing_value_without_mutating_it(self):
        definition = self.define()
        self.attributes('a', {'地域': 'A'})
        self.define(version=definition['version'], allowed_values=['B'])
        with app.database_connection() as db:
            before = list(db.iterdump())
            self.assertEqual(catalog.check(db)['issues'], [{'item_id': 'a', 'key': '地域', 'reason': 'attribute_value_mismatch'}])
            self.assertEqual(list(db.iterdump()), before)
            self.assertEqual(catalog.attribute_values(db, 'a'), {'地域': 'A'})

    def test_malformed_speaker_json_does_not_block_source_update(self):
        app.save_speaker_registry_records([{'id': 'speaker01', 'display_name': '架空話者', 'attributes': {'地域': 'A'}}], expected_revision=0)
        with app.database_connection() as db:
            for source in ('{', '[]', 'null', '"text"'):
                db.execute("UPDATE speaker_registry SET attributes_json=? WHERE id='speaker01'", (source,))
                self.assertEqual(db.execute('SELECT count(*) FROM speaker_attributes').fetchone()[0], 0)
                self.assertFalse(catalog.check(db)['ok'])

    def test_tag_normalization_rejects_nfkc_space_case_and_rename_duplicates(self):
        tag = self.tag(' ＡＢＣ ')
        for label in ('abc', 'ABC', '　ａｂｃ　'):
            self.assertEqual(self.client.post('/api/library/tags', json={'name': label}).status_code, 400)
        other = self.tag('別タグ')
        self.assertEqual(self.client.put('/api/library/tags/' + other['tag_id'], json={'name': 'aBc'}).status_code, 400)
        self.assertEqual(self.assign('tags', tag['tag_id'], ['a', 'b']).status_code, 200)
        self.assertEqual(self.assign('tags', tag['tag_id'], ['a', 'b']).status_code, 200)
        self.assertEqual(self.client.get('/api/library?tag=' + tag['tag_id']).get_json()['total'], 2)

    def test_manual_multiple_membership_bulk_remove_and_atomic_missing_item(self):
        one, two = self.group(), self.group(name='別の集合')
        self.assertEqual(self.assign('data-groups', one['group_id'], ['a', 'b']).status_code, 200)
        self.assertEqual(self.assign('data-groups', two['group_id'], ['a']).status_code, 200)
        self.assertEqual(self.assign('data-groups', two['group_id'], ['b', 'absent']).status_code, 404)
        with app.database_connection() as db:
            self.assertEqual(catalog.members(db, two['group_id']), ['a'])
        self.assertEqual(self.assign('data-groups', one['group_id'], ['a'], True).status_code, 200)
        self.assertEqual(self.client.get('/api/library?data_group=' + one['group_id']).get_json()['total'], 1)
        self.assertEqual(self.client.get('/api/library/a').get_json()['revision_count'], 0)

    def test_rule_combines_attributes_tags_speakers_and_segments_without_writing_preview(self):
        self.define(); self.attributes('a', {'地域': 'A'}); self.attributes('b', {'地域': 'B'})
        tag = self.tag(); self.assign('tags', tag['tag_id'], ['a', 'c'])
        app.save_speaker_registry_records([{'id': 'speaker01', 'display_name': '架空話者', 'attributes': {'専門': '研究'}}], expected_revision=0)
        with app.database_connection() as db:
            db.execute("UPDATE library_items SET speaker_profiles_json=? WHERE id='a'", ('{"P1":{"global_speaker_id":"speaker01","session_role":"participant"}}',))
            before = list(db.iterdump())
        rule = {'mode': 'all', 'conditions': [
            {'scope': 'conversation', 'key': '地域', 'op': 'eq', 'value': 'A'},
            {'scope': 'tag', 'key': tag['tag_id'], 'op': 'exists'},
            {'scope': 'speaker', 'key': '専門', 'op': 'eq', 'value': '研究'},
            {'scope': 'segment', 'key': 'char_count', 'op': 'gte', 'value': 2}]}
        preview = self.client.post('/api/library/data-groups/preview', json={'rule': rule})
        self.assertEqual(preview.get_json()['item_ids'], ['a'])
        with app.database_connection() as db:
            self.assertEqual(list(db.iterdump()), before)
        group = self.group(kind='rule', rule=rule)
        self.assertEqual(group['item_ids'], ['a'])
        self.assertEqual(self.assign('data-groups', group['group_id'], ['b']).status_code, 400)
        self.attributes('a', {'地域': 'B'})
        with app.database_connection() as db:
            self.assertEqual(catalog.members(db, group['group_id']), [])

    def test_rule_rejects_undefined_and_sql_like_keys(self):
        for condition in ({'scope': 'conversation', 'key': 'unknown', 'value': 'A'},
                          {'scope': 'segment', 'key': 'id"; DROP TABLE tags; --', 'value': 'A'},
                          {'scope': 'speaker', 'key': 'unknown', 'value': 'A'},
                          {'scope': 'tag', 'key': 'missing', 'op': 'exists'}):
            response = self.client.post('/api/library/data-groups/preview', json={'rule': {'conditions': [condition]}})
            self.assertEqual(response.status_code, 400, response.get_json())

    def test_frozen_target_keeps_group_version_values_tags_definition_and_hash(self):
        definition = self.define(); self.attributes('a', {'地域': 'A'})
        tag = self.tag(); self.assign('tags', tag['tag_id'], ['a'])
        group = self.group(); self.assign('data-groups', group['group_id'], ['a', 'b'])
        snapshot = self.freeze(group_ids=[group['group_id']], group_by=[{'scope': 'conversation', 'key': '地域'}])
        original = copy.deepcopy(snapshot)
        self.attributes('a', {'地域': 'B'}); self.assign('tags', tag['tag_id'], ['a'], True)
        self.assign('data-groups', group['group_id'], ['a'], True)
        self.define(version=definition['version'], description='変更後')
        self.assertEqual(snapshot, original)
        self.assertEqual(snapshot['hash'], digest({k: v for k, v in snapshot.items() if k != 'hash'}))
        self.assertEqual(snapshot['members_hash'], digest(['a', 'b']))
        self.assertEqual(snapshot['items'][0]['attributes'], {'地域': 'A'})
        self.assertEqual(snapshot['items'][0]['tags'][0]['name'], '年度')
        with self.assertRaisesRegex(ValueError, '対象集合'):
            self.freeze(group_ids=[group['group_id']])

    def test_comparison_archive_uses_fixed_snapshot_and_run_members_after_group_changes(self):
        self.define(); self.attributes('a', {'地域': 'A'})
        group = self.group(); self.assign('data-groups', group['group_id'], ['a', 'b'])
        payload, preview = self.preview(data_group_id=group['group_id'])
        saved = self.save_comparison(payload, preview)
        self.assertEqual(saved.status_code, 200, saved.get_json())
        run_id = saved.get_json()['run']['id']
        snapshot, result = self.store._read_package(run_id)
        frozen = copy.deepcopy(result['parameters']['target_snapshot'])
        self.assertEqual(self.store.members(run_id), ['a', 'b'])
        self.assign('data-groups', group['group_id'], ['a'], True)
        self.attributes('a', {'地域': 'B'})
        self.assertEqual(self.store._read_package(run_id)[1]['parameters']['target_snapshot'], frozen)
        self.assertEqual(self.store.members(run_id), ['a', 'b'])
        self.assertEqual(len(snapshot['members']), 2)
        self.assertEqual(self.store.get(run_id)['stale'], 1)

    def test_attributes_tags_and_members_stale_only_member_runs_leave_single_hash_unchanged(self):
        self.define(); tag = self.tag(); group = self.group()
        before = app.archive_source_stamp(app.library_row('a'))
        payload, preview = self.preview()
        saved = self.save_comparison(payload, preview).get_json()['run']
        with app.database_connection() as db:
            db.execute("INSERT INTO analysis_runs (id,request_id,item_id,kind,fingerprint,input_fingerprint,snapshot_id,source_revision,analysis_revision,created_at,status,vault_status,stale,error,note_path,app_url,provider,model) SELECT 'single-run','single-request', 'a',kind,fingerprint,input_fingerprint,snapshot_id,source_revision,analysis_revision,created_at,status,vault_status,0,error,note_path,app_url,provider,model FROM analysis_runs WHERE id=?", (saved['id'],))
        for action in (lambda: self.attributes('a', {'地域': 'A'}), lambda: self.attributes('a', {}),
                       lambda: self.assign('tags', tag['tag_id'], ['a']), lambda: self.assign('tags', tag['tag_id'], ['a'], True),
                       lambda: self.assign('data-groups', group['group_id'], ['a']), lambda: self.assign('data-groups', group['group_id'], ['a'], True)):
            with app.database_connection() as db:
                db.execute('UPDATE analysis_runs SET stale=0')
            self.assertEqual(action().status_code, 200)
            self.assertEqual(self.store.get(saved['id'])['stale'], 1)
            self.assertEqual(self.store.get('single-run')['stale'], 0)
            self.assertEqual(app.archive_source_stamp(app.library_row('a')), before)

    def test_preview_save_conflict_on_attribute_tag_or_group_version_change(self):
        self.define(); tag = self.tag(); group = self.group()
        for action in (lambda: self.attributes('a', {'地域': 'A'}), lambda: self.assign('tags', tag['tag_id'], ['a'])):
            payload, preview = self.preview()
            action()
            self.assertEqual(self.save_comparison(payload, preview).status_code, 409)
        self.assign('data-groups', group['group_id'], ['a', 'b'])
        payload, preview = self.preview(data_group_id=group['group_id'])
        current = self.client.get('/api/library/catalog').get_json()['groups'][0]
        self.client.put('/api/library/data-groups/' + group['group_id'], json={**current, 'name': '新名称'})
        self.assertEqual(self.save_comparison(payload, preview).status_code, 409)
        self.assertEqual(self.store.list_comparisons(), [])

    def test_rule_group_freezes_evaluated_members_and_changes_do_not_mutate_it(self):
        self.define(); self.attributes('a', {'地域': 'A'}); self.attributes('b', {'地域': 'A'})
        group = self.group(kind='rule', rule={'conditions': [{'scope': 'conversation', 'key': '地域', 'value': 'A'}]})
        payload, preview = self.preview(item_ids=[], data_group_id=group['group_id'])
        saved = self.save_comparison(payload, preview).get_json()['run']
        self.attributes('c', {'地域': 'A'})
        self.attributes('a', {'地域': 'B'})
        self.assertEqual(self.store.members(saved['id']), ['a', 'b'])
        self.assertEqual(self.store._read_package(saved['id'])[1]['parameters']['target_snapshot']['item_ids'], ['a', 'b'])
        self.assertEqual(self.store.get(saved['id'])['stale'], 1)

    def test_new_member_of_rule_group_marks_old_run_stale(self):
        self.define(); self.attributes('a', {'地域': 'A'}); self.attributes('b', {'地域': 'A'})
        group = self.group(kind='rule', rule={'conditions': [{'scope': 'conversation', 'key': '地域', 'value': 'A'}]})
        payload, preview = self.preview(data_group_id=group['group_id'])
        saved = self.save_comparison(payload, preview).get_json()['run']
        self.attributes('c', {'地域': 'A'})
        self.assertEqual(self.store.get(saved['id'])['stale'], 1)

    def test_frozen_speaker_attributes_definition_versions_and_registry_fallback(self):
        app.save_speaker_registry_records([{'id': 'speaker01', 'display_name': '架空話者',
            'organization': '架空組織', 'attributes': {'地域': 'A'}, 'tags': ['架空話者タグ']}], expected_revision=0)
        with app.database_connection() as db:
            db.execute("UPDATE library_items SET speaker_profiles_json=?,analysis_config_json=? WHERE id='a'",
                ('{"P1":{"global_speaker_id":"speaker01"}}', '{"group_by":"attribute:地域"}'))
        snapshot = self.freeze()
        self.assertEqual(snapshot['definition_refs'], [{'scope': 'speaker', 'key': '地域', 'version': 1, 'status': '型未確定'}])
        frozen = snapshot['items'][0]['speakers'][0]
        app.save_speaker_registry_records([{'id': 'speaker01', 'display_name': '架空話者',
            'organization': '変更後', 'attributes': {'地域': 'B'}, 'tags': []}], expected_revision=1)
        self.assertEqual(frozen['attributes'], {'地域': 'A'})
        self.assertEqual(frozen['registry_profile']['organization'], '架空組織')
        self.assertEqual(frozen['registry_profile']['tags'], ['架空話者タグ'])

    def test_direct_member_sql_increments_version_and_update_invalidates_old_and_new_members(self):
        group = self.group()
        payload, preview = self.preview()
        saved = self.save_comparison(payload, preview).get_json()['run']
        with app.database_connection() as db:
            db.execute('INSERT INTO data_group_members VALUES (?,?,?)', (group['group_id'], 'a', 'now'))
            first = db.execute('SELECT version FROM data_groups').fetchone()[0]
            db.execute('UPDATE analysis_runs SET stale=0')
            db.execute("UPDATE data_group_members SET item_id='c'")
            self.assertGreater(db.execute('SELECT version FROM data_groups').fetchone()[0], first)
            self.assertEqual(db.execute('SELECT stale FROM analysis_runs WHERE id=?', (saved['id'],)).fetchone()[0], 1)

    def test_rule_candidate_segment_change_invalidates_in_same_transaction_and_rolls_back(self):
        with app.database_connection() as db:
            db.execute("UPDATE library_items SET segments_json=? WHERE id='c'", ('[{"id":"u1","start":20,"end":22,"speaker":"P1","text":"架空"}]',))
        group = self.group(kind='rule', rule={'conditions': [{'scope': 'segment', 'key': 'start', 'op': 'lte', 'value': 0}]})
        self.assertEqual(group['item_ids'], ['a', 'b'])
        payload, preview = self.preview(data_group_id=group['group_id'])
        saved = self.save_comparison(payload, preview).get_json()['run']
        with app.database_connection() as db:
            db.execute("UPDATE library_items SET segments_json=? WHERE id='c'", ('[{"id":"u1","start":0,"end":2,"speaker":"P1","text":"架空"}]',))
            self.assertEqual(db.execute('SELECT stale FROM analysis_runs WHERE id=?', (saved['id'],)).fetchone()[0], 1)
            db.rollback()
        self.assertEqual(self.store.get(saved['id'])['stale'], 0)
        with app.database_connection() as db:
            db.execute("UPDATE library_items SET segments_json=? WHERE id='c'", ('[{"id":"u1","start":0,"end":2,"speaker":"P1","text":"架空"}]',))
        self.assertEqual(self.store.get(saved['id'])['stale'], 1)
        self.assertEqual(self.store.members(saved['id']), ['a', 'b'])

    def test_group_and_tag_deletion_preserves_fixed_packages_and_invalidates_runs(self):
        tag = self.tag(); group = self.group()
        self.assign('tags', tag['tag_id'], ['a']); self.assign('data-groups', group['group_id'], ['a', 'b'])
        payload, preview = self.preview(data_group_id=group['group_id'])
        saved = self.save_comparison(payload, preview).get_json()['run']
        frozen = self.store._read_package(saved['id'])
        for entity, identity in (('tags', tag['tag_id']), ('data-groups', group['group_id'])):
            with app.database_connection() as db:
                db.execute('UPDATE analysis_runs SET stale=0')
            self.assertEqual(self.client.delete(f'/api/library/{entity}/{identity}').status_code, 200)
            self.assertEqual(self.store.get(saved['id'])['stale'], 1)
            self.assertEqual(self.store._read_package(saved['id']), frozen)

    def test_delete_and_restore_preserve_authoritative_catalog_rows(self):
        self.define(); self.attributes('a', {'地域': 'A'}); tag = self.tag(); group = self.group()
        self.assign('tags', tag['tag_id'], ['a']); self.assign('data-groups', group['group_id'], ['a'])
        with app.database_connection() as db:
            rows = library_trash.snapshot_rows(db, 'a')
            self.assertEqual(len(rows['conversation_attributes']), 1)
            self.assertEqual(len(rows['conversation_tags']), 1)
            self.assertEqual(len(rows['data_group_members']), 1)
            db.execute("DELETE FROM library_items WHERE id='a'")
            for table in ('conversation_attributes', 'conversation_tags', 'data_group_members'):
                self.assertEqual(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0], 0)
            for table in library_trash.ITEM_TABLES[1:]:
                db.execute(f'DELETE FROM {table} WHERE item_id=?', ('a',))
            for table in library_trash.ITEM_TABLES:
                library_trash._insert(db, table, rows.get(table, []))
            self.assertEqual(catalog.attribute_values(db, 'a'), {'地域': 'A'})
            self.assertEqual(catalog.members(db, group['group_id']), ['a'])

    def test_catalog_and_diagnostics_are_readonly_and_mutations_use_csrf(self):
        self.define()
        with app.database_connection() as db:
            before = list(db.iterdump())
        self.assertEqual(self.client.get('/api/library/catalog').status_code, 200)
        self.assertEqual(self.client.get('/api/library?data_group=missing').status_code, 404)
        with patch.object(app, 'system_activity_snapshot', return_value={}):
            self.assertTrue(self.client.get('/api/system/activity?library_check=1').get_json()['library_projection']['attributes']['ok'])
        self.assertEqual(self.client.post('/api/library/tags', json={'name': '拒否'}, headers={'Origin': 'http://localhost'}).status_code, 403)
        with app.database_connection() as db:
            self.assertEqual(list(db.iterdump()), before)


if __name__ == '__main__':
    unittest.main()
