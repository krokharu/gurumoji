import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Flask
from gurumoji.analysis_orchestration import initialize_orchestration_store, _read_events
from gurumoji.orchestration_initial import initialize_initial_checkpoints
from gurumoji.services.analysis_orchestration_publication import initialize_orchestration_publication_store
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes


class StatusIncrementalTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        initialize_orchestration_store(self.db)
        initialize_orchestration_store(self.db)
        initialize_orchestration_publication_store(self.db)
        self.addCleanup(self.db.close)

    def test_run_indexes_and_existing_store_indexes(self):
        for table in ('events', 'results', 'decisions', 'usage', 'responses', 'label_proposals', 'issues', 'tasks'):
            query = f'EXPLAIN QUERY PLAN SELECT * FROM orchestration_{table} WHERE run_id=?'
            plan = ' '.join(row[3] for row in self.db.execute(query, ('a',)))
            self.assertIn('INDEX', plan, (table, plan))
        for table, key in (('orchestration_initial_stages', 'initial_id'), ('orchestration_publications', 'run_id'), ('orchestration_publication_attempts', 'run_id')):
            plan = ' '.join(row[3] for row in self.db.execute(f'EXPLAIN QUERY PLAN SELECT * FROM {table} WHERE {key}=?', ('a',)))
            self.assertIn('INDEX', plan, (table, plan))
        plan = ' '.join(row[3] for row in self.db.execute('EXPLAIN QUERY PLAN SELECT seq,payload_json FROM orchestration_events WHERE run_id=? AND seq>? ORDER BY seq', ('a', 1)))
        self.assertIn('orchestration_events_run_seq', plan)

    def test_event_cursor_and_reset(self):
        for run in ('a', 'b', 'a'):
            self.db.execute('INSERT INTO orchestration_events(run_id,payload_json) VALUES (?,?)', (run, '{}'))
        all_events, reset = _read_events(self.db, 'a')
        self.assertEqual([v['seq'] for v in all_events], [1, 3])
        self.assertFalse(reset)
        self.assertEqual([v['seq'] for v in _read_events(self.db, 'a', 1)[0]], [3])
        self.assertEqual(_read_events(self.db, 'a', 3), ([], False))
        self.assertEqual(_read_events(self.db, 'a', 2), (all_events, True))
        self.assertEqual(_read_events(self.db, 'a', 999), (all_events, True))
        self.assertEqual(_read_events(self.db, 'b', 0)[0][0]['seq'], 2)

    def test_route_validation_and_legacy_call(self):
        service = SimpleNamespace(status=Mock(return_value={'run_id': 'r'}))
        app = Flask(__name__)
        register_orchestration_routes(app, lambda: service, lambda x: x)
        client = app.test_client()
        url = '/api/library/i/analysis/orchestration/r'
        self.assertEqual(client.get(url).status_code, 200)
        service.status.assert_called_with('i', 'r')
        self.assertEqual(client.get(url + '?events_after=0').status_code, 200)
        service.status.assert_called_with('i', 'r', events_after=0)
        for invalid in ('-1', '1.2', 'abc', '', '9999999999999999999999999'):
            self.assertEqual(client.get(url + '?events_after=' + invalid).status_code, 400)
