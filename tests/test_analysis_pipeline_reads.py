from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import unittest

from gurumoji.analysis_pipeline import AnalysisPipelineService, initialize_pipeline_store


class AnalysisPipelineReadTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.addCleanup(self.connection.close)
        initialize_pipeline_store(self.connection)
        data = json.loads((Path(__file__).parent / "fixtures" / "analysis_three_conversations.json").read_text(encoding="utf-8"))
        snapshot = {"analysis": data["conversations"][1]["analysis"], "padding": "架空" * 20000}
        self.proposal = {"objective": "参加の偏りを確認する", "provider": "local_transformer",
                         "model": "synthetic-model", "primary_method": "participation"}
        plan = {"planning_proposal": self.proposal, "padding": "架空の計画" * 1000}
        self.connection.execute("""INSERT INTO analysis_pipeline_requests
            (pipeline_id,request_id,item_id,source_revision,analysis_revision,input_hash,plan_hash,
             plan_json,binding_json,snapshot_json,status,created_at,updated_at)
            VALUES ('pipeline','synthetic-request','synthetic-item',2,1,'input-hash','plan-hash',
                    ?,?,?,'running','synthetic-time','synthetic-time')""",
            (json.dumps(plan, ensure_ascii=False), json.dumps(data["definitions"], ensure_ascii=False),
             json.dumps(snapshot, ensure_ascii=False)))
        self.connection.execute("""INSERT INTO analysis_step_attempts
            (attempt_id,pipeline_id,step_id,milestone,generation,attempt,status,updated_at)
            VALUES ('attempt','pipeline','freeze_input','M0',1,1,'planned','synthetic-time')""")
        self.connection.commit()
        self.service = AnalysisPipelineService(
            connect=self.connect, find_item=lambda _: None, source_fingerprint=lambda _: "",
            snapshot_builder=lambda _: {}, method_runner=lambda *_: {}, save_result=lambda **_: {},
            publish_result=lambda _: {}, publication_outcomes=lambda _: {}, public_run=lambda _: {},
            runtime_key="synthetic-memory",
        )
        self.reads = []

        def record_row(cursor, values):
            self.reads.append((tuple(column[0] for column in cursor.description), sum(
                len(str(value).encode("utf-8")) for value in values if value is not None)))
            return sqlite3.Row(cursor, values)

        self.connection.row_factory = record_row

    @contextmanager
    def connect(self):
        with self.connection:
            yield self.connection

    def test_one_transition_materializes_less_data_than_select_star(self):
        # Former _set_step + _assert_current reads for one planned -> checking transition.
        self.connection.execute("SELECT * FROM analysis_step_attempts WHERE attempt_id='attempt'").fetchone()
        self.connection.execute("SELECT * FROM analysis_pipeline_requests WHERE pipeline_id='pipeline'").fetchone()
        self.connection.execute("SELECT * FROM analysis_step_attempts WHERE attempt_id='attempt' AND pipeline_id='pipeline'").fetchone()
        self.connection.execute("SELECT attempt_id FROM analysis_step_attempts WHERE pipeline_id='pipeline' AND step_id='freeze_input' ORDER BY attempt DESC LIMIT 1").fetchone()
        before = sum(size for _, size in self.reads)
        self.reads.clear()
        self.service._set_step("attempt", status="checking", generation=1)
        after = sum(size for _, size in self.reads)
        self.assertFalse(any({"snapshot_json", "plan_json", "binding_json"} & set(columns)
                             for columns, _ in self.reads))
        self.assertLess(after, before // 100)
        status = self.connection.execute("SELECT status FROM analysis_step_attempts WHERE attempt_id='attempt'").fetchone()[0]
        self.assertEqual(status, "checking")
        print(f"Synthetic transition: materialized UTF-8 values {before} -> {after} bytes (not disk I/O).")

    def test_status_and_cancellation_read_only_needed_values(self):
        state = self.service.status("synthetic-item", "pipeline", ensure_running=False)
        self.assertEqual(state["planning"], self.proposal)
        self.assertEqual((state["status"], state["progress"], state["allowed_actions"]), ("running", 0, ["cancel"]))
        self.assertFalse(any({"snapshot_json", "plan_json", "binding_json", "artifact_json", "report_json", "directive_json"}
                             & set(columns) for columns, _ in self.reads))
        self.reads.clear()
        self.assertFalse(self.service._cancelled("pipeline", 1))
        self.assertEqual(self.reads[0][0], ("cancel_requested", "generation"))
        self.assertTrue(self.service._cancelled("pipeline", 2))
        self.reads.clear()
        self.assertEqual(self.service._pipeline_row("pipeline", columns="status"), {"status": "running"})
        self.assertEqual(self.reads[0][0], ("status",))


if __name__ == "__main__":
    unittest.main()
