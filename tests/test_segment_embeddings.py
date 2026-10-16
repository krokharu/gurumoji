"""C1 cache and the real worker transaction, with synthetic vectors only."""
import base64
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import numpy as np

from gurumoji.analysis_core import EMBEDDING_STANDARD_V1
from gurumoji import transformer_analysis as transformer
from gurumoji.services import segment_embeddings as store
from gurumoji.services.analysis_jobs import make_transformer_jobs
from gurumoji.services.library_trash import delete_disposable_rows, snapshot_rows


def fixture():
    data = json.loads((Path(__file__).parent/'fixtures/analysis_three_conversations.json').read_text(encoding='utf-8'))
    return data['conversations'][0]['analysis']


def result_for(analysis, *, standard=None):
    standard = EMBEDDING_STANDARD_V1 if standard is None else standard
    dimensions = standard['dimensions']
    vectors = np.zeros((len(analysis['segments']), dimensions), dtype='float32')
    vectors[:, 0] = 1
    return {'generated_at': '2026-10-13T01:00:00Z',
            'engine': {'name': standard['model_name'], 'revision': standard['model_revision'], 'dimensions': dimensions},
            'embedding_fingerprint': transformer.transformer_embedding_fingerprint(
                analysis, model=standard['model_name'], revision=standard['model_revision']),
            'parameters': {}, 'vectors': transformer._pack_vectors(vectors, [row['id'] for row in analysis['segments']])}


def initialize(connection):
    connection.execute('CREATE TABLE application_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    store.initialize(connection)


class SegmentEmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.addCleanup(self.connection.close)
        initialize(self.connection)
        self.analysis = fixture()
        self.result = result_for(self.analysis)

    def test_blob_matches_existing_pack_and_initialization_is_additive_idempotent(self):
        store.initialize(self.connection)
        store.write_rows(self.connection, store.prepare_rows(self.analysis, self.result))
        self.connection.commit()
        changes = self.connection.total_changes
        rows = store.read_current(self.connection, self.analysis)
        self.assertEqual(self.connection.total_changes, changes)
        self.assertEqual(len(rows), 2)
        raw = base64.b64decode(self.result['vectors']['data'])
        self.assertEqual(b''.join(row['vector'] for row in rows), raw)
        self.assertTrue(all(type(row['vector']) is bytes and len(row['vector']) == 384 for row in rows))
        self.assertTrue(all(not row['stale'] for row in rows))
        self.assertEqual(rows[0]['text_sha256'], store.text_sha256(self.analysis['segments'][0]['text']))
        self.assertEqual(json.loads(self.connection.execute("SELECT value FROM application_metadata WHERE key='embedding_standard_v1'").fetchone()[0]), EMBEDDING_STANDARD_V1)
        pk = [row[1] for row in sorted(self.connection.execute('PRAGMA table_info(segment_embeddings)'), key=lambda row: row[5]) if row[5]]
        self.assertEqual(pk, ['item_id', 'segment_id', 'model_name', 'model_revision', 'text_sha256'])

    def test_text_edit_and_context_only_edit_are_stale_without_rewriting_old_rows(self):
        store.write_rows(self.connection, store.prepare_rows(self.analysis, self.result))
        changed = copy.deepcopy(self.analysis)
        changed['segments'][1]['text'] += '編集'
        rows = store.read_current(self.connection, changed)
        self.assertTrue(all(row['stale'] for row in rows))
        self.assertEqual(rows[0]['text_sha256'], store.text_sha256(changed['segments'][0]['text']))
        store.write_rows(self.connection, store.prepare_rows(changed, result_for(changed)))
        rows = store.read_current(self.connection, changed)
        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(row['stale'] for row in rows), 1)
        self.assertEqual(sum(not row['stale'] for row in rows), 2)

    def test_new_and_old_models_coexist_but_comparison_rejects_other_coordinate_system(self):
        other = {**EMBEDDING_STANDARD_V1, 'model_revision': 'other-revision'}
        store.write_rows(self.connection, store.prepare_rows(self.analysis, result_for(self.analysis, standard=other)))
        with self.assertRaisesRegex(ValueError, '再計算'):
            store.read_current(self.connection, self.analysis)
        store.write_rows(self.connection, store.prepare_rows(self.analysis, self.result))
        self.assertEqual(len(store.read_current(self.connection, self.analysis)), 2)
        self.assertEqual(self.connection.execute('SELECT count(*) FROM segment_embeddings').fetchone()[0], 4)

    def test_legacy_unknown_revision_is_not_invented_or_imported(self):
        value = copy.deepcopy(self.result)
        value['engine'].pop('revision')
        self.assertEqual(store.prepare_rows(self.analysis, value), [])
        self.assertEqual(self.connection.execute('SELECT count(*) FROM segment_embeddings').fetchone()[0], 0)

    def test_corrupt_persisted_blob_is_not_treated_as_comparable(self):
        store.write_rows(self.connection, store.prepare_rows(self.analysis, self.result))
        self.connection.execute("UPDATE segment_embeddings SET vector=X'01'")
        with self.assertRaisesRegex(ValueError, '破損'):
            store.read_current(self.connection, self.analysis)

    def test_invalid_blob_hash_id_scale_and_dimensions_fail_before_write(self):
        mutations = [lambda result: result['vectors'].update(data='invalid!'),
                     lambda result: result.update(embedding_fingerprint='0'*64),
                     lambda result: result['vectors'].update(segment_ids=['u1', 'u1']),
                     lambda result: result['vectors'].update(segment_ids=['u1', 'foreign']),
                     lambda result: result['vectors'].update(scale=128),
                     lambda result: result['vectors'].update(dimensions=True),
                     lambda result: result['vectors'].update(data=base64.b64encode(bytes(768)).decode()),
                     lambda result: result['vectors'].update(data=base64.b64encode(bytes([128])*768).decode())]
        for mutate in mutations:
            result = copy.deepcopy(self.result)
            mutate(result)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                store.prepare_rows(self.analysis, result)
        self.assertEqual(self.connection.execute('SELECT count(*) FROM segment_embeddings').fetchone()[0], 0)

    def test_delete_cleans_same_transaction_and_trash_does_not_restore_vectors(self):
        store.write_rows(self.connection, store.prepare_rows(self.analysis, self.result))
        another = copy.deepcopy(self.analysis)
        another['item']['id'] = 'another'
        store.write_rows(self.connection, store.prepare_rows(another, result_for(another)))
        self.connection.commit()
        self.assertNotIn('segment_embeddings', snapshot_rows(self.connection, self.analysis['item']['id']))
        delete_disposable_rows(self.connection, self.analysis['item']['id'])
        self.connection.rollback()
        self.assertEqual(self.connection.execute('SELECT count(*) FROM segment_embeddings').fetchone()[0], 4)
        with self.connection:
            delete_disposable_rows(self.connection, self.analysis['item']['id'])
        self.assertEqual(self.connection.execute('SELECT count(*) FROM segment_embeddings').fetchone()[0], 2)


class TransformerTransactionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='gurumoji-vector-worker-')
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name)/'library.sqlite3'
        self.analysis = fixture()
        self.result = result_for(self.analysis)
        with self.database() as connection:
            initialize(connection)
            connection.execute('CREATE TABLE library_items(id TEXT PRIMARY KEY, revision_count INTEGER, analysis_revision INTEGER, transformer_analysis_json TEXT)')
            connection.execute('CREATE TABLE transformer_analysis_requests(request_id TEXT PRIMARY KEY,status TEXT,progress INTEGER,message TEXT,updated_at TEXT)')
            connection.execute('INSERT INTO library_items VALUES (?,?,?,?)', (self.analysis['item']['id'], 1, 1, '{}'))
            connection.execute("INSERT INTO transformer_analysis_requests VALUES ('synthetic-run','queued',0,'','')")
        self.archive = Mock(return_value={'id': 'synthetic-archive', 'vault_status': 'not_selected'})
        self.analyze = Mock(return_value=self.result)
        self.events = {}
        jobs = make_transformer_jobs(AnalysisConflictError=RuntimeError, analyze_transformer_topics=self.analyze,
            archive_group_analysis=self.archive, build_research_analysis=lambda value: {'linguistics': {'morphemes': []}},
            database_connection=self.database, group_analysis_for_row=lambda row, **kwargs: copy.deepcopy(self.analysis),
            library_row=self.library_row, library_write_lock=threading.RLock(), public_diagnostic_text=lambda value, **kwargs: value,
            transformer_cancel_events=self.events, transformer_jobs_lock=threading.RLock())
        self.run_job = jobs[2]

    def database(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        # sqlite connection context commits/rolls back but does not close by itself.
        from contextlib import contextmanager
        @contextmanager
        def managed():
            try:
                with connection:
                    yield connection
            finally:
                connection.close()
        return managed()

    def library_row(self, item_id):
        with self.database() as connection:
            return connection.execute('SELECT * FROM library_items WHERE id=?', (item_id,)).fetchone()

    def execute(self, event=None):
        self.run_job('synthetic-run', self.analysis, EMBEDDING_STANDARD_V1['model_name'], 8, 2, 0, event or threading.Event())

    def state(self):
        with self.database() as connection:
            return (connection.execute('SELECT transformer_analysis_json FROM library_items').fetchone()[0],
                    connection.execute('SELECT status FROM transformer_analysis_requests').fetchone()[0],
                    connection.execute('SELECT count(*) FROM segment_embeddings').fetchone()[0])

    def test_worker_commits_json_vectors_and_completed_status_together(self):
        self.execute()
        stored, status, count = self.state()
        self.assertEqual(status, 'completed')
        self.assertEqual(count, 2)
        self.assertEqual(json.loads(stored)['vectors'], self.result['vectors'])
        with self.database() as connection:
            self.assertTrue(all(not row['stale'] for row in store.read_current(connection, self.analysis)))
        self.archive.assert_called_once()

    def test_failure_after_vector_insert_rolls_back_json_vectors_and_completion(self):
        original = store.write_rows
        def fail(connection, rows):
            original(connection, rows)
            raise sqlite3.IntegrityError('synthetic failure after vector insert')
        with patch.object(store, 'write_rows', side_effect=fail):
            self.execute()
        self.assertEqual(self.state(), ('{}', 'failed', 0))

    def test_cancelled_and_source_revision_conflict_leave_no_vector_or_result(self):
        event = threading.Event()
        event.set()
        self.execute(event)
        self.assertEqual(self.state(), ('{}', 'cancelled', 0))
        self.archive.assert_not_called()
        with self.database() as connection:
            connection.execute('UPDATE library_items SET revision_count=2')
        self.execute()
        self.assertEqual(self.state(), ('{}', 'stale', 0))

    def test_invalid_result_is_rejected_before_archive_and_db_writes(self):
        self.result['embedding_fingerprint'] = '0'*64
        self.execute()
        self.assertEqual(self.state(), ('{}', 'failed', 0))
        self.archive.assert_not_called()


if __name__ == '__main__':
    unittest.main()
