import json
from contextlib import contextmanager
import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask
from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.analysis_orchestration import initialize_orchestration_store
from gurumoji.services.analysis_history import AnalysisHistoryService
from gurumoji.services.analysis_reanalysis import freeze_reanalysis, lookup_reanalysis_source
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
from gurumoji.services.model_context import transform_references


class ReanalysisSourceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dbpath = Path(self.temp.name) / 'test.sqlite'
        @contextmanager
        def connect():
            db = sqlite3.connect(self.dbpath)
            try:
                with db:
                    yield db
            finally:
                db.close()
        self.connect = connect
        snapshot = {'input_hash': 'input', 'evidence': []}
        run = {'run_id': 'run_a', 'item_id': 'item', 'initial_id': 'initial_a',
               'input_hash': 'input', 'source_revision': 2, 'analysis_revision': 3,
               'config': {'question': '元の問い'}, 'last_decision_id': 'decision_a'}
        task = {'run_id': 'run_a', 'task_id': 'task_a', 'status': 'completed'}
        raw = {'summary': '保存済み結果', 'claims': []}
        meta = {'run_id': 'run_a', 'result_id': 'result_a', 'task_id': 'task_a',
                'validation_status': 'valid', 'dataset_version': 'input', 'raw_hash': fingerprint(raw)}
        self.dump = lambda obj: json.dumps(obj, ensure_ascii=False)
        with self.connect() as db:
            initialize_orchestration_store(db)
            db.execute('INSERT INTO orchestration_initials VALUES (?,?,?,?,?,?,?,?)',
                       ('initial_a', 'identity', 'item', 'ready', self.dump(snapshot), fingerprint(snapshot), '', 'now'))
            db.execute('INSERT INTO orchestration_runs VALUES (?,?,?,?,?,?)',
                       ('run_a', 'item', 'request', 'hash', 'initial_a', self.dump(run)))
            db.execute('INSERT INTO orchestration_tasks VALUES (?,?,?,?)', ('task_a', 'run_a', 'key', self.dump(task)))
            db.execute('INSERT INTO orchestration_results VALUES (?,?,?,?,?)', ('result_a', 'run_a', 'task_a', self.dump(raw), self.dump(meta)))
            db.execute('INSERT INTO orchestration_decisions VALUES (?,?,?,?)', ('decision_a', 'run_a', 'result_a', '{}'))
        self.viewer = AnalysisHistoryService(connect=self.connect, find_item=lambda item: {'id': item} if item in ('item', 'other') else None)

    def tearDown(self):
        self.temp.cleanup()

    def test_lookup_freeze_and_http_read_only(self):
        for identifier in ('run_a', 'result_a'):
            source = lookup_reanalysis_source(self.viewer, 'item', identifier)
            self.assertEqual(source['source_result_id'], 'result_a')
            frozen = freeze_reanalysis(self.viewer, 'item', identifier, '追加の問い')
            self.assertEqual(frozen['original_question'], '元の問い')
            self.assertEqual(frozen['human_prompt'], '追加の問い')
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            frozen = freeze_reanalysis(self.viewer, 'item', 'result_a', '追加の問い', connection=db)
            self.assertEqual(frozen['source_run_id'], 'run_a')
            with self.assertRaises(LookupError):
                freeze_reanalysis(self.viewer, 'other', 'result_a', '追加の問い', connection=db)
        app = Flask(__name__)
        register_orchestration_routes(app, lambda: self.fail('execution service used'), lambda x: x,
                                      history_viewer=lambda: self.viewer)
        response = app.test_client().get('/api/library/item/analysis/orchestration/reanalysis/source/result_a')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.json['source']['raw_hash'], source['raw_hash'])

    def test_saved_result_with_null_utterance_id_can_be_delivered(self):
        frozen = freeze_reanalysis(self.viewer, 'item', 'result_a', 'additional prompt')
        transformed = transform_references({'reanalysis': frozen}, {})
        self.assertIsNone(transformed['reanalysis']['content']['utterance_id'])

    def test_rejections(self):
        with self.assertRaises(LookupError): lookup_reanalysis_source(self.viewer, 'other', 'result_a')
        with self.assertRaises(LookupError): lookup_reanalysis_source(self.viewer, 'item', 'result_missing')
        for prompt in (' ', 'a' * 8001):
            with self.assertRaises(AnalysisContractError): freeze_reanalysis(self.viewer, 'item', 'result_a', prompt)
        with self.connect() as db:
            db.execute("UPDATE orchestration_results SET raw_json='{}'")
        with self.assertRaises(AnalysisContractError): lookup_reanalysis_source(self.viewer, 'item', 'result_a')
        with self.connect() as db:
            row = db.execute('SELECT state_json FROM orchestration_results').fetchone()
            meta = json.loads(row[0]); meta['raw_hash'] = fingerprint({}); meta['validation_status'] = 'quarantined'
            db.execute('UPDATE orchestration_results SET state_json=?', (self.dump(meta),))
        with self.assertRaises(AnalysisContractError): lookup_reanalysis_source(self.viewer, 'item', 'result_a')


if __name__ == '__main__':
    unittest.main()
