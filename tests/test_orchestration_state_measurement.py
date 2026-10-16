"""B4: synthetic run-state write measurements, without providers or real data."""
import copy
import json
import os
from pathlib import Path
import sqlite3
import statistics
import tempfile
import time
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import canonical, fingerprint
from gurumoji.analysis_orchestration import AnalysisOrchestrationService


class OrchestrationStateMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-state-measurement-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.enterContext(patch.dict(os.environ, {
            "MOJIOKOSI_DATA_DIR": str(self.root / "data"),
            "MOJIOKOSI_OUTPUT_DIR": str(self.root / "output"),
            "MOJIOKOSI_BACKUP_DIR": str(self.root / "backup"),
        }))

    def no_external_call(self, *args):
        self.fail("Measurement must not execute agents or analysis methods")

    def fixture(self, task_count, segment_count):
        path = self.root / f"tasks-{task_count}-segments-{segment_count}.sqlite3"

        def connect():
            db = sqlite3.connect(path)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
            return db

        snapshot = {"input_hash": "synthetic-input-v1", "source_revision": 1, "analysis_revision": 1,
                    "analysis": {"segments": [
                        {"id": f"u{i}", "text": "架空の発話です。", "speaker": "A",
                         "start": i * 10, "end": i * 10 + 5, "valid_time": True}
                        for i in range(segment_count)]}}
        service = AnalysisOrchestrationService(
            connect=connect, find_item=lambda _: {"id": "synthetic", "revision": snapshot["input_hash"]},
            snapshot_builder=lambda _: copy.deepcopy(snapshot), source_fingerprint=lambda item: item["revision"],
            agent_runner=self.no_external_call, method_runner=self.no_external_call, schedule=False)
        public = service.start("synthetic", {"model": "synthetic-model", "max_tasks": 20000,
                              "analysis_interval_version": 1, "request_id": "synthetic-measurement"})
        service._prepare_intervals(public["run_id"])
        with service._db() as db:
            run = service._read_run(db, public["run_id"])
            template = service._register(db, run, {"role": "statistics", "question": "架空の集計0",
                                         "why_now": "計測用", "success_criteria": "保存量を検証"}, phase="analysis")
            # Bulk fixture creation excludes admission cost from the write timing.
            rows = []
            for i in range(1, task_count):
                task = copy.deepcopy(template)
                task.update(task_id=f"synthetic-task-{i}", intent_id=f"synthetic-intent-{i}",
                            attempt_id=f"synthetic-attempt-{i}", idempotency_key=f"synthetic-key-{i}",
                            title=f"架空の集計{i}")
                task["intent"]["question"] = task["title"]
                rows.append((task["task_id"], run["run_id"], task["idempotency_key"], canonical(task).decode("utf-8")))
            db.executemany("INSERT INTO orchestration_tasks VALUES (?,?,?,?)", rows)
            task_hash = fingerprint(service._tasks(db, run["run_id"]))
            initial_hash = db.execute("SELECT snapshot_hash FROM orchestration_initials WHERE initial_id=?",
                                      (run["initial_id"],)).fetchone()[0]
        return service, run, task_hash, initial_hash

    def measure(self, task_count, segment_count):
        service, run, task_hash, initial_hash = self.fixture(task_count, segment_count)
        write_ms, transaction_ms, payload_bytes, payload_hashes = [], [], [], []
        # One warm-up and nine measured single-write transactions on a local file DB.
        for sample in range(10):
            run["iteration"] = sample
            started = time.perf_counter_ns()
            with service._db() as db:
                before = db.total_changes
                write_started = time.perf_counter_ns()
                service._write_run(db, run)
                write_elapsed = (time.perf_counter_ns() - write_started) / 1e6
                self.assertEqual(db.total_changes - before, 1)
            elapsed = (time.perf_counter_ns() - started) / 1e6
            if sample:
                write_ms.append(write_elapsed)
                transaction_ms.append(elapsed)
                payload_bytes.append(len(canonical(run)))
                payload_hashes.append(fingerprint(run))
        with service._db() as db:
            row = db.execute("SELECT state_json,length(CAST(state_json AS BLOB)) FROM orchestration_runs WHERE run_id=?",
                             (run["run_id"],)).fetchone()
            self.assertEqual(json.loads(row[0]), run)
            self.assertEqual(row[1], payload_bytes[-1])
            self.assertEqual(db.execute("SELECT count(*) FROM orchestration_tasks WHERE run_id=?",
                                        (run["run_id"],)).fetchone()[0], task_count)
            self.assertEqual(fingerprint(service._tasks(db, run["run_id"])), task_hash)
            self.assertEqual(db.execute("SELECT snapshot_hash FROM orchestration_initials WHERE initial_id=?",
                                        (run["initial_id"],)).fetchone()[0], initial_hash)
            service._check_version(run)
            journal_mode = db.execute("PRAGMA journal_mode").fetchone()[0]
            synchronous = db.execute("PRAGMA synchronous").fetchone()[0]
        self.assertEqual(len(run["analysis_partition"]["target_evidence_ids"]), segment_count)
        return {"task_count": task_count, "segment_count": segment_count,
                "interval_count": len(run["analysis_partition"]["intervals"]),
                "samples": 9, "state_json_utf8_bytes": payload_bytes,
                "write_ms": write_ms, "write_median_ms": statistics.median(write_ms),
                "transaction_ms": transaction_ms, "transaction_median_ms": statistics.median(transaction_ms),
                "run_id": run["run_id"], "state_hashes": payload_hashes,
                "fixture_task_hash": task_hash, "initial_hash": initial_hash,
                "journal_mode": journal_mode, "synchronous": synchronous}

    def test_large_synthetic_runs_measure_full_state_writes_and_preserve_task_rows(self):
        measurements = [self.measure(tasks, segments) for tasks, segments in
                        [(10, 2), (1000, 2), (10000, 2), (10000, 1000), (10000, 10000)]]
        # Task rows are already separate; fixed partitions, rather than the task
        # count alone, enlarge state_json. No machine-specific time limit is asserted.
        sizes = [m["state_json_utf8_bytes"][-1] for m in measurements[:3]]
        self.assertLessEqual(max(sizes) - min(sizes), 32)  # Timestamp formatting only.
        self.assertLess(measurements[2]["state_json_utf8_bytes"][-1], measurements[-1]["state_json_utf8_bytes"][-1])
        print("B4_MEASUREMENT " + json.dumps({
            "scope": "_write_run serialization+UPDATE; transaction includes connection, BEGIN IMMEDIATE, commit and close",
            "excluded": "fixture creation, reads, providers, task execution, public status projection; OS cache not cleared",
            "measurements": measurements}, ensure_ascii=True))


if __name__ == "__main__":
    unittest.main()
