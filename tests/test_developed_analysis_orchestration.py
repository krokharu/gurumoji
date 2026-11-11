"""Synthetic-only durable Core/Handler acceptance tests; no external providers."""
import copy
import contextlib
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from gurumoji.analysis_core import AnalysisContractError
from pipeline_fixtures import reply, core_task, pin
from gurumoji.core_pipeline_service import AnalysisOrchestrationService, validate_orchestration_payload

def intent(role, question=None, **extra):
    return {"role": role, "question": question or "Check " + role, "why_now": "Resolve uncertainty",
            "success_criteria": "Report support and limitations", "importance": "high", "importance_reason": "May alter the finding", **extra}

def core(summary="合成の判断", **extra):
    return {"summary": summary, "state_ops": [], "action": {"op": "none"}, "reason": "合成の根拠", **extra}

def stop(**extra):
    return core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}, **extra)

def critic(context, issues=None):
    return {"summary": "Review", "claims": [], "review_status": "issues" if issues else "no_issues",
            "reviewed_scope": "Provided view and evidence", "limitations": "Exploratory",
            "issues": issues or [], "analysis_requests": [], "label_patches": []}

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "runtime.sqlite"
        self.item = {"id": "conversation", "revision": "input-v1"}
        self.build_count = 0
        self.calls = []
        self.methods = []
        self.snapshot = {"input_hash": "input-v1", "source_revision": 1, "analysis_revision": 2,
            "analysis": {"segments": [
                {"id": "u1", "text": "Synthetic first utterance", "speaker": "A", "annotation": {"codes": ["manual"]}},
                {"id": "u2", "text": "Synthetic alternative explanation", "speaker": "B", "annotation": {"codes": []}}],
                "all_results": {"hidden_table": [{"value": 0, "missing": None}]}}}
        self.agent = lambda role, context, options, check, usage: reply(context)
        self.service = self.make_service()

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def build(self, item):
        self.build_count += 1
        return copy.deepcopy(self.snapshot)

    def run_agent(self, role, context, options, check, usage):
        self.calls.append((role, copy.deepcopy(context), copy.deepcopy(options)))
        return self.agent(role, context, options, check, usage)

    def method(self, name, snapshot):
        self.methods.append((name, copy.deepcopy(snapshot)))
        return {"method": {"method_id": name}, "datasets": {"summary": {"fields": ["n"], "rows": [{"n": 2}]}}}

    def make_service(self, **kwargs):
        return AnalysisOrchestrationService(connect=self.connect, find_item=lambda item: self.item if self.item and item == self.item["id"] else None,
            snapshot_builder=self.build, source_fingerprint=lambda item: item["revision"], agent_runner=self.run_agent,
            method_runner=self.method, schedule=False, **kwargs)

    def start(self, **extra):
        payload = {"model": "synthetic-model", "stop_mode": "auto", "max_iterations": None,
                   "time_limit_seconds": None, "max_calls": 20, "max_tasks": 30, **extra}
        return self.service.start("conversation", payload)

    def drive(self, run):
        self.service.run(run["run_id"])
        return self.service.status("conversation", run["run_id"])

    def test_evidence_preserves_explicit_time_validity_and_legacy_zero(self):
        cases = [
            ("valid_zero", {"start": 0, "end": 0, "duration": 0, "valid_time": True}, 0, 0, True),
            ("known_positive", {"start": 2, "end": 5, "duration": 3, "valid_time": True}, 2, 5, True),
            ("null_time", {"start": None, "end": None, "duration": None, "valid_time": False}, None, None, False),
            ("false_placeholder", {"start": 0, "end": 0, "duration": 0, "valid_time": False}, None, None, False),
            ("start_missing", {"start": None, "end": 5, "duration": 0, "valid_time": False}, None, None, False),
            ("end_missing", {"start": 2, "end": None, "duration": 0, "valid_time": False}, None, None, False),
            ("duration_uncomputed", {"start": 2, "end": 5, "duration": None, "valid_time": True}, 2, 5, True),
            ("duration_absent", {"start": 2, "end": 5, "valid_time": True}, 2, 5, True),
            ("legacy_no_flag", {"start": 0, "end": 0}, 0, 0, None),
            ("legacy_duration", {"start": 2, "end": 5, "duration": 3}, 2, 5, None),
        ]
        for name, timing, start, end, validity in cases:
            with self.subTest(case=name):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot["analysis"]["segments"] = [{"id": "u1", "text": "Synthetic timing", "speaker": "UNKNOWN", **timing}]
                before = copy.deepcopy(snapshot)
                evidence = self.service._evidence(snapshot)[0]
                self.assertEqual((evidence["start"], evidence["end"]), (start, end))
                if validity is None:
                    self.assertNotIn("valid_time", evidence)
                else:
                    self.assertIs(evidence["valid_time"], validity)
                if validity is not None and "duration" in timing:
                    self.assertEqual(evidence["duration"], None if validity is False else timing["duration"])
                else:
                    self.assertNotIn("duration", evidence)
                self.assertEqual(evidence["speaker"], "UNKNOWN")
                self.assertEqual(evidence["utterance_id"], "u1")
                self.assertEqual(snapshot, before)

    def test_raw_sqlite_factory_connections_are_closed_after_commit_and_error(self):
        connections = []
        original = self.service.connect
        def tracked():
            connection = original()
            connections.append(connection)
            return connection
        self.service.connect = tracked
        self.start()
        with self.assertRaisesRegex(RuntimeError, "synthetic rollback"):
            with self.service._db():
                raise RuntimeError("synthetic rollback")
        for connection in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")

    def test_initial_all_results_reused_request_dedup_and_changed_config(self):
        run = self.start(request_id="same")
        again = self.start(request_id="same")
        other = self.start(request_id="other")
        self.assertEqual(run["run_id"], again["run_id"])
        self.assertEqual(run["initial_id"], other["initial_id"])
        self.assertEqual(self.build_count, 1)
        before = self.service.result("conversation", run["run_id"])["initial"]
        self.drive(run)
        self.assertEqual(before, self.service.result("conversation", run["run_id"])["initial"])
        self.assertEqual(before["snapshot"]["analysis"]["all_results"]["hidden_table"][0]["value"], 0)
        self.item["revision"] = self.snapshot["input_hash"] = "input-v2"
        newer = self.start()
        self.assertNotEqual(newer["initial_id"], run["initial_id"])
        self.assertEqual(self.build_count, 2)
        with self.assertRaises(AnalysisContractError):
            self.start(request_id="same", question="Different")

    def test_unsupported_confirmatory_and_cloud_without_consent(self):
        for payload in ({"research_mode": "confirmatory"}, {"research_protocol": "confirmatory"},
                        {"provider": "openai", "provider_policy": "cloud_allowed"}):
            with self.assertRaises(AnalysisContractError):
                self.start(**payload)
        self.assertEqual(self.build_count, 0)

    def test_time_limit_before_dispatch(self):
        run = self.start(stop_mode="time", time_limit_seconds=1)
        with contextlib.closing(self.connect()) as db, db:
            state = json.loads(db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (run["run_id"],)).fetchone()[0])
            state.update(started_at="old", deadline=time.time() - 1)
            db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (json.dumps(state), run["run_id"]))
        run = self.drive(run)
        self.assertEqual(run["stop_reason"], "time_limit")
        self.assertFalse(self.calls)

    def test_operational_call_and_task_budgets(self):
        run = self.drive(self.start(max_calls=1))
        self.assertEqual(run["stop_reason"], "call_budget_limit")
        self.assertEqual(run["usage"]["calls"], 1)
        other = self.drive(self.start(max_tasks=1))
        self.assertEqual(other["stop_reason"], "task_budget_limit")

    def test_cancel_wins_late_response_fenced_and_usage_preserved(self):
        entered, release = threading.Event(), threading.Event()
        def delayed(role, context, options, check, usage):
            entered.set()
            release.wait(3)
            usage({"input_tokens": 7, "output_tokens": 2, "reported": True})
            return stop()
        self.agent = delayed
        run = self.start()
        worker = threading.Thread(target=self.service.run, args=(run["run_id"],))
        worker.start(); self.assertTrue(entered.wait(2))
        cancelled = self.service.cancel("conversation", run["run_id"])
        self.assertEqual(cancelled["stop_reason"], "user_stop")
        release.set(); worker.join(3)
        for _ in range(100):
            current = self.service.status("conversation", run["run_id"])
            if current["results"]:
                break
            time.sleep(.01)
        self.assertEqual(current["status"], "cancelled")
        self.assertEqual(current["results"][0]["validation_status"], "quarantined")
        self.assertEqual(current["results"][0]["error"], "late_response_after_stop")
        self.assertEqual(current["usage"]["input_tokens"], 7)
        self.assertEqual(len(self.calls), 1)

    def test_unknown_execution_requires_explicit_recovery_never_replays(self):
        def broken(*_):
            raise TimeoutError("Response lost")
        self.agent = broken
        run = self.drive(self.start())
        self.assertEqual(run["status"], "recovery_required")
        self.assertEqual(run["tasks"][0]["status"], "uncertain")
        second = self.make_service()
        recovery = second.resume("conversation", run["run_id"])
        self.assertEqual(recovery["status"], "recovery_required")
        self.assertEqual(len(self.calls), 1)
        task_id = run["tasks"][0]["task_id"]
        second.resume("conversation", run["run_id"], {"recovery": {task_id: "abandon"}})
        second.run(run["run_id"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(second.status("conversation", run["run_id"])["stop_reason"], "execution_failure")

    def test_usage_unknown_zero_not_claimed_and_dedup(self):
        def agent(role, context, options, check, usage):
            usage({"input_tokens": 0, "output_tokens": 0, "reported": False})
            return stop() if role == "core" else critic(context)
        self.agent = agent
        run = self.drive(self.start())
        self.assertIsNone(run["usage"]["input_tokens"])
        self.assertEqual(run["usage"]["measurement_status"], "unavailable")
        self.service._record_usage(run["run_id"], run["tasks"][0]["task_id"], {"input_tokens": 9})
        self.service._record_usage(run["run_id"], run["tasks"][0]["task_id"], {"input_tokens": 9})
        self.assertEqual(self.service.status("conversation", run["run_id"])["usage"]["input_tokens"], 9)

    def test_changed_source_stale_fixed_snapshot_and_deleted_read_hidden(self):
        run = self.start()
        self.item["revision"] = "input-v2"
        self.assertTrue(self.service.status("conversation", run["run_id"])["stale"])
        self.assertEqual(self.service.result("conversation", run["run_id"])["initial"]["snapshot"]["input_hash"], "input-v1")
        self.item = None
        for read in (lambda: self.service.status("conversation", run["run_id"]), lambda: self.service.result("conversation", run["run_id"]), lambda: self.service.history("conversation")):
            with self.assertRaises(LookupError):
                read()
        self.service.run(run["run_id"])
        self.assertEqual(len(self.calls), 0)

    def test_all_excluded_and_unmeasurable_cost_cap_are_rejected(self):
        with self.assertRaises(AnalysisContractError):
            self.start(max_cost=10)
        for segment in self.snapshot["analysis"]["segments"]:
            segment["excluded"] = True
        with self.assertRaises(AnalysisContractError):
            self.start()
        self.assertFalse(self.calls)

    def test_statistics_rejects_scoped_or_label_dependent_exports(self):
        run = self.start()
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            evidence = self.service._initial(db, run["initial_id"])["evidence"][0]["evidence_id"]
            for extra in ({"evidence_ids": [evidence]}, {"scope": "first-half"}, {"label_dependent": True}):
                with self.assertRaises(AnalysisContractError):
                    self.service._register(db, state, intent("statistics", method_id="participation", **extra), phase="specialists")

    def test_noncooperative_timeout_stops_new_work(self):
        entered, release = threading.Event(), threading.Event()
        def blocked(*_):
            entered.set(); release.wait(3)
            return stop()
        self.agent = blocked
        run = self.start()
        with self.service._db() as db:
            fixed = self.service._read_run(db, run["run_id"])
            fixed["config"]["call_timeout_seconds"] = 1
            self.service._write_run(db, fixed)
        worker = threading.Thread(target=self.service.run, args=(run["run_id"],))
        worker.start(); self.assertTrue(entered.wait(1))
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.service.status("conversation", run["run_id"])["stop_reason"], "call_timeout")
        release.set()
        for _ in range(100):
            if self.service.status("conversation", run["run_id"])["results"]:
                break
            time.sleep(.01)

    def test_complete_pipeline_and_pre_stop_review(self):
        final = self.drive(self.start())
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(set(role for role, _, _ in self.calls), {"core", "interpretation", "verification", "critic"})
        self.assertGreaterEqual(final["iteration"], 3)
        self.assertTrue(all(result["validation_status"] == "valid" for result in final["results"]))
        self.assertEqual(final["config"]["adapter_version"], "core-pipeline-1")
        self.assertEqual(self.make_service().result("conversation", final["run_id"]), self.service.result("conversation", final["run_id"]))

    def test_payload_accepts_only_ui_fields_and_explicit_experts_question(self):
        from gurumoji.core_pipeline_service import PAYLOAD_FIELDS
        expected = {"source_revision", "analysis_revision", "request_id", "question", "provider", "model", "provider_policy",
                    "cloud_consent", "stop_mode", "time_limit_seconds", "max_iterations", "importance_threshold",
                    "max_calls", "max_tasks", "concurrency", "research_mode", "roles", "publication_targets",
                    "obsidian_management", "expert_ids", "research_question"}
        self.assertEqual(PAYLOAD_FIELDS, expected)
        for field in ("full_text", "partial_expert_reports", "output_contract", "harness_context", "full_text_review_policy",
                      "context_index_limit", "context_evidence_limits_by_role", "dependency_candidate_version", "expert_hooks",
                      "expert_hook_version", "analysis_pipeline", "map_body_chars", "map_expert_id", "expert_inputs", "min_iterations"):
            with self.subTest(field=field), self.assertRaises(AnalysisContractError) as caught:
                validate_orchestration_payload({"model": "fixture", field: None})
            self.assertEqual(caught.exception.field, field)

    def test_unbounded_defaults_and_invalid_caps(self):
        config = validate_orchestration_payload({"model": "fixture"})
        self.assertIsNone(config["max_calls"])
        self.assertIsNone(config["max_tasks"])
        self.assertEqual(config["min_iterations"], 3)
        for field in ("max_calls", "max_tasks"):
            for bad in (True, 0, -1, 2.5, "10"):
                with self.subTest(field=field, bad=bad), self.assertRaises(AnalysisContractError):
                    validate_orchestration_payload({"model": "fixture", field: bad})

    def test_research_question_is_trimmed_and_validated(self):
        self.assertEqual(validate_orchestration_payload({"model": "fixture", "research_question": "  研究質問  "})["research_question"], "研究質問")
        for bad in (None, "", " ", 1):
            with self.assertRaises(AnalysisContractError):
                validate_orchestration_payload({"model": "fixture", "research_question": bad})

if __name__ == "__main__":
    unittest.main()
