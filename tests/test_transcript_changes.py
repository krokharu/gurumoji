"""I1: lossless replay, legacy cutover, immutable Raw and all history readers."""
import copy
import json
import sqlite3
import unittest
from unittest.mock import patch

from gurumoji import transcript_preparation as p


class TranscriptChangeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('CREATE TABLE library_items(id TEXT PRIMARY KEY, segments_json TEXT, '
                        'speaker_profiles_json TEXT, speaker_names_json TEXT, session_profile_json TEXT, '
                        'original_segments_json TEXT, original_segments_status TEXT)')
        self.db.execute('CREATE TABLE analysis_runs(id TEXT, item_id TEXT, stale INTEGER)')
        self.db.execute('CREATE TABLE analysis_run_members(run_id TEXT, item_id TEXT)')
        p.initialize(self.db)
        self.raw = [{'id': 'a', 'text': '原文', 'speaker': 'S1', 'start': None},
                    {'id': 'b', 'text': '第二発話', 'end': 3}]
        self.value = dict(segments=copy.deepcopy(self.raw), speaker_profiles={'S1': {'role': 'unknown'}},
                          speaker_names={'S1': '架空話者'}, session_profile={'date': None})
        self.insert('c')

    def insert(self, item_id):
        self.db.execute('INSERT INTO library_items VALUES (?, ?, ?, ?, ?, ?, ?)',
            (item_id, *(p.encode(self.value[key]) for key in p.source_keys()), p.encode(self.raw), 'initial_import'))

    def row(self, item_id='c'):
        return self.db.execute('SELECT * FROM library_items WHERE id=?', (item_id,)).fetchone()

    def write(self, value):
        self.db.execute('UPDATE library_items SET segments_json=?, speaker_profiles_json=?, '
                        'speaker_names_json=?, session_profile_json=? WHERE id="c"',
                        tuple(p.encode(value[key]) for key in p.source_keys()))

    def legacy(self, version=1, value=None):
        value = value or self.value
        self.db.execute('INSERT INTO transcript_versions VALUES (?, ?, ?, ?, ?, ?)',
                        ('c', version, p.digest(value), p.encode(value), 'saved', 'old-time'))

    def test_pure_diff_all_operations_null_missing_and_order(self):
        before = copy.deepcopy(self.value)
        after = copy.deepcopy(before)
        after['segments'] = [after['segments'][1], {'id': 'new', 'text': ''}, after['segments'][0]]
        after['segments'][2].update(text='編集', speaker='S2', start=0, end=None)
        after['segments'][0].pop('end')
        after['speaker_names'].pop('S1')
        after['session_profile']['empty'] = None
        ops = p.diff_source(before, after)
        self.assertEqual(p.apply_ops(before, ops), after)
        self.assertEqual(before, self.value)
        self.assertEqual(p.apply_ops(after, p.diff_source(after, before)), before)
        self.assertTrue(any(o['op'] == 'segment_order' for o in ops))
        self.assertEqual(p.apply_ops(before, p.diff_source(before, {**before, 'segments': []}))['segments'], [])

    def test_invalid_legacy_ids_are_preserved_without_invention(self):
        before = {**self.value, 'segments': [{'text': 'IDなし'}, {'id': 'x'}, {'id': 'x', 'text': None}]}
        self.assertEqual(p.apply_ops(before, p.diff_source(before, self.value)), self.value)

    def test_json_numeric_types_are_not_silently_equal(self):
        before = copy.deepcopy(self.value)
        before['segments'][0]['start'] = 0
        before['session_profile']['flag'] = 1
        after = copy.deepcopy(before)
        after['segments'][0]['start'] = 0.0
        after['session_profile']['flag'] = True
        replayed = p.apply_ops(before, p.diff_source(before, after))
        self.assertEqual(p.digest(replayed), p.digest(after))
        self.assertNotEqual(p.digest(before), p.digest(after))
        before = copy.deepcopy(after)
        after['segments'][0]['start'] = -0.0
        self.assertEqual(p.digest(p.apply_ops(before, p.diff_source(before, after))), p.digest(after))
        self.assertNotEqual(p.digest(before), p.digest(after))

    def test_import_metadata_and_current_share_version_one(self):
        changed = copy.deepcopy(self.value)
        changed['segments'][0]['text'] = '処理済み'
        self.write(changed)
        self.assertEqual(p.capture(self.db, self.row(), 'initial_import'), 1)
        changes = p._changes(self.db, 'c')
        self.assertEqual([c['version'] for c in changes], [1, 1])
        self.assertEqual([c['process'] for c in changes], ['import_metadata', 'import_current_snapshot'])
        self.assertEqual(p.read_version(self.db, 'c', 1)['source'], changed)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM transcript_versions').fetchone()[0], 0)
        self.assertEqual(json.loads(self.row()['original_segments_json']), self.raw)

    def test_save_once_increments_once_even_for_unchanged_values(self):
        p.capture(self.db, self.row(), 'initial_import')
        for version in (2, 3):
            p.capture(self.db, self.row(), 'legacy_current_baseline')
            self.assertEqual(p.capture(self.db, self.row()), version)
            self.assertEqual(p.current_version(self.db, self.row()), version)
        p.capture(self.db, self.row(), 'preparation_baseline')
        self.assertEqual(len(p.read_versions(self.db, 'c')), 3)

    def test_dry_run_read_only_cutover_deduplicated_and_idempotent(self):
        self.legacy()
        before = self.db.total_changes
        report = p.migration_dry_run(self.db, self.row())
        self.assertEqual(report['status'], 'ready')
        self.assertEqual(self.db.total_changes, before)
        old = list(self.db.execute('SELECT * FROM transcript_versions'))
        self.assertEqual(p.activate_changes(self.db, self.row()), 1)
        before = self.db.total_changes
        self.assertEqual(p.activate_changes(self.db, self.row()), 1)
        self.assertEqual(self.db.total_changes, before)
        self.assertEqual(list(self.db.execute('SELECT * FROM transcript_versions')), old)
        self.assertEqual(len(p.read_versions(self.db, 'c')), 1)
        self.assertEqual(p.read_version(self.db, 'c', 1)['created_at'], 'old-time')
        self.assertEqual(p._changes(self.db, 'c')[0]['origin'], 'rule')

    def test_cutover_mismatch_or_no_history_uses_next_version(self):
        self.legacy(4, {**self.value, 'speaker_names': {}})
        self.assertEqual(p.activate_changes(self.db, self.row()), 5)
        changed = copy.deepcopy(self.value)
        changed['segments'].pop(0)
        self.write(changed)
        self.assertEqual(p.current_version(self.db, self.row()), None)
        self.assertEqual(p.capture(self.db, self.row()), 6)
        self.assertIn('a', p.known_segment_ids(self.db, self.row()))
        self.assertEqual(p.read_version(self.db, 'c', 6)['source'], changed)

    def test_no_history_and_missing_or_substitute_raw_remain_disclosed(self):
        for status, raw in [('unavailable', ''), ('migrated_current_snapshot', p.encode(self.raw))]:
            with self.subTest(status=status):
                self.db.execute('DELETE FROM transcript_changes')
                self.db.execute('DELETE FROM transcript_change_bases')
                self.db.execute('UPDATE library_items SET original_segments_json=?, original_segments_status=?', (raw, status))
                self.assertEqual(p.activate_changes(self.db, self.row()), 1)
                self.assertEqual(p._base(self.db, 'c')['raw_status'], status)
                self.assertEqual(p.read_version(self.db, 'c', 1)['source'], self.value)

    def test_corrupt_legacy_snapshot_blocks_cutover_without_writes(self):
        self.legacy()
        self.db.execute('UPDATE transcript_versions SET source_hash="wrong"')
        before = self.db.total_changes
        self.assertEqual(p.migration_dry_run(self.db, self.row())['status'], 'conflict')
        with self.assertRaises(ValueError):
            p.activate_changes(self.db, self.row())
        self.assertEqual(self.db.total_changes, before)
        self.assertIsNone(p._base(self.db, 'c'))

    def test_cutover_failure_rolls_back_even_when_caller_catches(self):
        self.legacy()
        real = p.current_version
        with patch.object(p, 'current_version', side_effect=ValueError('injected')):
            with self.assertRaises(ValueError):
                p.activate_changes(self.db, self.row())
        self.assertIsNone(p._base(self.db, 'c'))
        self.assertEqual(p._changes(self.db, 'c'), [])
        self.assertEqual(real(self.db, self.row()), 1)

    def test_tampered_raw_delta_or_sequence_detected(self):
        p.capture(self.db, self.row(), 'initial_import')
        self.db.commit()
        for sql in ['UPDATE transcript_changes SET base_hash="wrong"',
                    'UPDATE transcript_changes SET after_hash="wrong"',
                    'UPDATE transcript_changes SET seq=2',
                    'UPDATE transcript_change_bases SET base_hash="wrong"']:
            with self.subTest(sql=sql):
                self.db.execute(sql)
                with self.assertRaises(ValueError):
                    p.read_versions(self.db, 'c')
                self.db.rollback()
        self.db.execute('UPDATE library_items SET original_segments_json="[]"')
        self.assertEqual(p.migration_dry_run(self.db, self.row())['status'], 'conflict')

    def test_code_rollback_conflicts_never_auto_append(self):
        self.legacy()
        p.activate_changes(self.db, self.row())
        p.capture(self.db, self.row())
        changed = {**self.value, 'speaker_names': {}}
        self.legacy(2, changed)
        self.write(changed)
        before = len(p._changes(self.db, 'c'))
        self.assertEqual(p.migration_dry_run(self.db, self.row())['status'], 'conflict')
        with self.assertRaises(ValueError):
            p.capture(self.db, self.row(), 'legacy_current_baseline')
        self.assertEqual(len(p._changes(self.db, 'c')), before)

    def test_deletion_snapshot_restores_bases_history_only_for_one_item(self):
        from gurumoji.services import library_trash as trash
        p.capture(self.db, self.row(), 'initial_import')
        self.insert('other')
        p.capture(self.db, self.row('other'), 'initial_import')
        snapshot = trash.snapshot_rows(self.db, 'c')
        old = p.read_versions(self.db, 'c', include_source=True)
        other = p.read_versions(self.db, 'other', include_source=True)
        self.db.execute('DELETE FROM library_items WHERE id="c"')
        self.assertIsNone(p._base(self.db, 'c'))
        for table in trash.ITEM_TABLES:
            trash._insert(self.db, table, snapshot.get(table, []))
        self.assertEqual(p.read_versions(self.db, 'c', include_source=True), old)
        self.assertEqual(p.read_versions(self.db, 'other', include_source=True), other)


class TranscriptChangeApiTests(unittest.TestCase):
    def setUp(self):
        from test_transcript_preparation import TranscriptPreparationTests
        self.helper = TranscriptPreparationTests()
        self.addCleanup(self.helper.doCleanups)
        self.helper.setUp()
        self.client = self.helper.client
        self.item_id = self.helper.item_id

    def test_current_export_analysis_and_vault_projection_use_delta_version(self):
        import app
        self.helper.rewrite(lambda segments: segments[0].update(text='  編集本文\n第二行  '))
        data = self.helper.analysis()
        prepared = data['manual']['preparation']
        exported = self.client.get(f'/api/library/{self.item_id}/preparation/export.json').get_json()
        self.assertEqual(prepared['input_version'], 2)
        self.assertEqual(exported['versions'][-1]['source']['segments'][0]['text'], '  編集本文\n第二行  ')
        self.assertEqual(exported['source_hash'], prepared['source_hash'])
        self.helper.test_preparation_vault_only_receives_counts_and_hashes()
        with app.database_connection() as db:
            before = db.total_changes
            self.assertEqual(p.read_version(db, self.item_id, 2)['source_hash'], prepared['source_hash'])
            self.assertEqual(db.total_changes, before)

    def test_get_does_not_activate_legacy_item(self):
        import app
        with app.database_connection() as db:
            value = p.source(app.library_row(self.item_id))
            db.execute('DELETE FROM transcript_changes WHERE item_id=?', (self.item_id,))
            db.execute('DELETE FROM transcript_change_bases WHERE item_id=?', (self.item_id,))
            db.execute('INSERT INTO transcript_versions VALUES (?, ?, ?, ?, ?, ?)',
                       (self.item_id, 7, p.digest(value), p.encode(value), 'old', 'old-time'))
        for _ in range(2):
            self.assertEqual(self.helper.analysis()['manual']['preparation']['input_version'], 7)
            self.assertEqual(self.client.get(f'/api/library/{self.item_id}/preparation/export.json').status_code, 200)
        with app.database_connection() as db:
            self.assertIsNone(p._base(db, self.item_id))
            self.assertEqual(p._changes(db, self.item_id), [])

    def test_diagnostics_replays_current_and_never_repairs_mismatch(self):
        import app
        with app.database_connection() as db:
            db.execute('UPDATE transcript_changes SET after_hash="tampered" WHERE item_id=?', (self.item_id,))
            before = list(db.iterdump())
        result = self.client.get('/api/system/activity?library_check=1').get_json()['library_projection']
        self.assertFalse(result['ok'])
        self.assertIn({'item_id': self.item_id, 'table': 'transcript_changes', 'reason': 'history_mismatch'}, result['issues'])
        with app.database_connection() as db:
            self.assertEqual(list(db.iterdump()), before)

    def test_api_delete_restore_preserves_raw_and_both_histories(self):
        import app
        self.helper.rewrite(lambda segments: segments[0].update(text='架空編集'))
        self.helper.fixture.create_analysis_item('other_i1', [{'id': 'o', 'text': '別の架空会話'}])
        with app.database_connection() as db:
            versions = p.read_versions(db, self.item_id, include_source=True)
            other = p.read_versions(db, 'other_i1', include_source=True)
        raw = app.library_row(self.item_id)['original_segments_json']
        with patch.object(app, 'retire_input_vault'):
            result = self.client.delete(f'/api/library/{self.item_id}')
        self.assertEqual(result.status_code, 200, result.get_json())
        with app.database_connection() as db:
            self.assertIsNone(p._base(db, self.item_id))
            self.assertEqual(p._changes(db, self.item_id), [])
        entry = next(app.trash_directory().glob('*/manifest.json')).parent
        self.assertEqual(app.restore_library_trash(entry.name), self.item_id)
        self.assertEqual(app.library_row(self.item_id)['original_segments_json'], raw)
        with app.database_connection() as db:
            self.assertEqual(p.read_versions(db, self.item_id, include_source=True), versions)
            self.assertEqual(p.read_versions(db, 'other_i1', include_source=True), other)


if __name__ == '__main__':
    unittest.main()
