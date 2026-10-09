"""Read-only monitor acceptance checks with synthetic SQLite ledgers."""
from contextlib import closing, contextmanager, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from gurumoji.analysis_orchestration import initialize_orchestration_store

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import watch_analysis_agents as monitor


class AnalysisAgentsMonitorTests(unittest.TestCase):
    @contextmanager
    def connect(self, database=None):
        with closing(sqlite3.connect(database or self.database)) as db:
            with db:
                yield db

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.database = Path(folder.name) / "library.sqlite3"
        with self.connect() as db:
            initialize_orchestration_store(db)
            db.execute("CREATE TABLE library_items(id TEXT PRIMARY KEY)")
            db.execute("INSERT INTO library_items VALUES ('conversation')")
            run = {"run_id": "run-1", "item_id": "conversation", "initial_id": "initial-1",
                   "status": "running", "phase": "specialists", "updated_at": "2026-10-06T00:00:00Z",
                   "input_hash": "synthetic-hash", "config": {"roles": {
                       "interpretation": {"provider": "synthetic", "model": "test-model", "api_key": "hidden-secret"}}},
                   "current_view": {"summary": "private source text"}}
            db.execute("INSERT INTO orchestration_runs VALUES (?,?,?,?,?,?)",
                       ("run-1", "conversation", "request-1", "hash", "initial-1", json.dumps(run)))
        self.task("task-1", "interpretation", "running")
        self.task("task-2", "verification", "uncertain")
        self.task("task-3", "statistics", "succeeded")

    def task(self, task_id, role, status):
        value = {"task_id": task_id, "run_id": "run-1", "role": role, "status": status,
                 "method_id": "synthetic-method", "title": "private task text", "raw_json": "hidden-reasoning"}
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO orchestration_tasks VALUES (?,?,?,?)",
                       (task_id, "run-1", task_id, json.dumps(value)))

    def test_saved_roles_models_and_uncertain_are_visible_without_writes(self):
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        value = monitor.snapshot(self.database)
        roles = {role["id"]: role for role in value["roles"]}
        self.assertEqual(len(roles), 7)
        self.assertEqual(roles["interpretation"]["model"], "test-model")
        self.assertEqual(roles["interpretation"]["active_tasks"][0]["task_id"], "task-1")
        self.assertEqual(roles["verification"]["status"], "uncertain")
        self.assertEqual(roles["verification"]["status_counts"], {"uncertain": 1})
        self.assertEqual(roles["statistics"]["kind"], "code")
        self.assertEqual(roles["statistics"]["status_counts"], {"succeeded": 1})
        self.assertIsNone(roles["core"]["model"])
        output = json.dumps(value)
        for secret in ("hidden-secret", "private source text", "private task text", "hidden-reasoning"):
            self.assertNotIn(secret, output)
        self.assertEqual(before, hashlib.sha256(self.database.read_bytes()).hexdigest())

    def test_watch_observes_updates_and_stops_only_the_monitor(self):
        output = io.StringIO()
        polls = []

        def update(_interval):
            polls.append(True)
            if len(polls) == 1:
                self.task("task-1", "interpretation", "succeeded")
            else:
                raise KeyboardInterrupt

        with patch.object(monitor.time, "sleep", side_effect=update), redirect_stdout(output):
            result = monitor.main(["--database", str(self.database), "--watch", "--json"])
        snapshots = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(result, 0)
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0]["roles"][2]["status_counts"], {"running": 1})
        self.assertEqual(snapshots[1]["roles"][2]["status_counts"], {"succeeded": 1})
        self.assertEqual(monitor.snapshot(self.database)["status"], "running")

    def test_missing_database_is_not_created_or_reported_as_success(self):
        missing = self.database.with_name("missing.sqlite3")
        output = io.StringIO()
        with redirect_stdout(output):
            result = monitor.main(["--database", str(missing), "--json"])
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "unavailable")
        self.assertFalse(missing.exists())

    def test_wrong_run_and_task_membership_are_rejected(self):
        with self.assertRaises(LookupError):
            monitor.snapshot(self.database, run_id="missing-run")
        with self.connect() as db:
            db.execute("UPDATE orchestration_tasks SET state_json=json_set(state_json,'$.run_id','another-run') WHERE task_id='task-1'")
        with redirect_stdout(io.StringIO()) as output:
            result = monitor.main(["--database", str(self.database), "--json"])
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "unavailable")

    def test_empty_ledger_and_terminal_controls(self):
        empty = self.database.with_name("empty.sqlite3")
        with self.connect(empty) as db:
            db.execute("CREATE TABLE library_items(id TEXT)")
        before = empty.read_bytes()
        self.assertEqual(monitor.snapshot(empty)["status"], "no_history")
        self.assertEqual(empty.read_bytes(), before)
        self.assertNotIn("\x1b", monitor.clean("model\x1b[2J\nforged row"))
        self.assertNotIn("\n", monitor.clean("model\x1b[2J\nforged row"))

    def test_explicit_run_remains_selected_when_a_new_run_appears(self):
        with self.connect() as db:
            row = db.execute("SELECT state_json FROM orchestration_runs").fetchone()
            run = json.loads(row[0])
            run.update(run_id="run-2", initial_id="initial-2")
            db.execute("INSERT INTO orchestration_runs VALUES (?,?,?,?,?,?)",
                       ("run-2", "conversation", "request-2", "hash", "initial-2", json.dumps(run)))
        self.assertEqual(monitor.snapshot(self.database)["run_id"], "run-2")
        self.assertEqual(monitor.snapshot(self.database, run_id="run-1")["run_id"], "run-1")


if __name__ == "__main__":
    unittest.main()
