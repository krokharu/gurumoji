"""Finite CPU guards: fake provider responses and temporary synthetic SQLite only.

Run from the feature worktree: PYTHONPATH=src python -B -m unittest discover -s tests -v
No application composition root, credentials, real model or user data is loaded.
"""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.orchestration_initial import InitialStage
from gurumoji.services.ai import client

PROVIDERS = frozenset({"openai", "google", "lmstudio"})
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def response(provider, *, complete=True):
    if provider == "openai":
        return {"output_text": '{"ok": true}', **({"status": "completed"} if complete else {})}
    if provider == "google":
        return {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]},
                                **({"finishReason": "STOP"} if complete else {})}]}
    return {"choices": [{"message": {"content": '{"ok": true}'},
                         **({"finish_reason": "stop"} if complete else {})}]}


def call(provider, value, usage=None):
    return client.call_ai_json(provider, "synthetic-key", "synthetic-model", "system", "user", "guard", SCHEMA,
        post=lambda *args, **kwargs: value, lmstudio_base=lambda _: "http://127.0.0.1:1234/v1",
        lmstudio_model_id=str, lmstudio_reasoning=lambda *args: {}, providers=PROVIDERS,
        usage_callback=usage.append if usage is not None else None)


class TerminalGuards(unittest.TestCase):
    def test_supported_normal_terminals_parse(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                self.assertEqual(call(provider, response(provider)), {"ok": True})

    def test_missing_terminal_never_accepts_parseable_json(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                with self.assertRaises(client.ResponseCompletionError) as error:
                    call(provider, response(provider, complete=False))
                self.assertEqual(error.exception.code, "response_completion_unknown")

    def test_unknown_terminals_are_explicitly_unsupported(self):
        values = [response(provider) for provider in ("openai", "google", "lmstudio")]
        values[0]["status"] = "future-status"
        values[1]["candidates"][0]["finishReason"] = "FUTURE_REASON"
        values[2]["choices"][0]["finish_reason"] = "tool_calls"
        for provider, value in zip(("openai", "google", "lmstudio"), values):
            with self.subTest(provider=provider):
                with self.assertRaises(client.ResponseCompletionError) as error:
                    call(provider, value)
                self.assertEqual(error.exception.code, "response_completion_unsupported")

    def test_top_level_complete_does_not_override_nonfinal_output(self):
        value = {"status": "completed", "output": [{"status": "in_progress",
                 "content": [{"type": "output_text", "text": '{"ok": true}'}]}]}
        with self.assertRaises(client.ResponseCompletionError):
            call("openai", value)

    def test_usage_recorded_before_unknown_terminal_rejection(self):
        samples = []
        value = {**response("openai", complete=False), "usage": {"input_tokens": 7}}
        with self.assertRaises(client.ResponseCompletionError):
            call("openai", value, samples)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["input_tokens"], 7)
        self.assertIsNone(samples[0]["output_tokens"])


class UsageGuards(unittest.TestCase):
    def test_partial_measurement_is_not_zero_or_invented_total(self):
        cases = {"openai": {"usage": {"input_tokens": 7}},
                 "google": {"usageMetadata": {"promptTokenCount": 7}},
                 "lmstudio": {"usage": {"prompt_tokens": 7}}}
        for provider, value in cases.items():
            with self.subTest(provider=provider):
                usage = client.extract_ai_token_usage(provider, "synthetic-model", value, PROVIDERS)
                self.assertEqual(usage["input_tokens"], 7)
                for field in ("output_tokens", "total_tokens", "cached_tokens", "reasoning_tokens"):
                    self.assertIsNone(usage[field])
                self.assertTrue(usage["reported"])

    def test_explicit_zero_is_preserved_including_lmstudio_cached_zero(self):
        value = {"usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                 "prompt_tokens_details": {"cached_tokens": 0, "cached_tokens_count": 99}}}
        usage = client.extract_ai_token_usage("lmstudio", "synthetic-model", value, PROVIDERS)
        for field in ("input_tokens", "output_tokens", "total_tokens", "cached_tokens"):
            self.assertEqual(usage[field], 0)
        self.assertTrue(usage["reported"])

    def test_absent_invalid_and_null_are_unknown(self):
        usage = client.extract_ai_token_usage("openai", "synthetic-model", {}, PROVIDERS)
        self.assertFalse(usage["reported"])
        self.assertTrue(all(usage[field] is None for field in client.TOKEN_FIELDS))
        for value in (None, True, -1, float("nan"), float("inf"), "0", 0.5):
            with self.subTest(value=str(value)):
                self.assertIsNone(client.optional_token_count(value))

    def test_normalize_and_merge_never_restore_unknown_as_zero(self):
        known = {"provider": "openai", "model": "synthetic-model", "request_count": 1,
                 "input_tokens": 7, "output_tokens": 3, "total_tokens": 10, "reported": True}
        partial = {**known, "output_tokens": None, "total_tokens": None}
        self.assertEqual(client.merge_ai_usage({}, known, PROVIDERS)["total_tokens"], 10)
        self.assertEqual(client.merge_ai_usage(known, known, PROVIDERS)["total_tokens"], 20)
        merged = client.merge_ai_usage(known, partial, PROVIDERS)
        self.assertEqual(merged["input_tokens"], 14)
        self.assertEqual(merged["request_count"], 2)
        self.assertIsNone(merged["output_tokens"])
        self.assertIsNone(client.normalize_ai_usage(merged, PROVIDERS)["total_tokens"])
        self.assertIsNone(client.merge_ai_usage(merged, known, PROVIDERS)["total_tokens"])


class SyntheticBuilder:
    version = "synthetic-initial-1"
    stages = (InitialStage("snapshot", "Synthetic snapshot"),)

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.freezes = 0
        self.calls = 0

    def freeze(self, item):
        self.freezes += 1
        return copy.deepcopy(self.snapshot)

    def run_stage(self, stage_id, frozen, previous):
        self.calls += 1
        return copy.deepcopy(frozen)


class DurableGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-synthetic-guards-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.sqlite3"
        self.item = {"id": "synthetic", "revision_count": 1, "analysis_revision": 2}
        self.snapshot = {"input_hash": "synthetic-v1", "source_revision": 1, "analysis_revision": 2,
                         "analysis": {"segments": [{"id": "u1", "text": "Synthetic utterance", "speaker": "A"}]}}
        self.builder = SyntheticBuilder(self.snapshot)
        self.agent_calls = []
        self.service = self.make_service(self.builder)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def agent(self, *args):
        self.agent_calls.append(args[0])
        return call("openai", response("openai", complete=False))

    def make_service(self, builder):
        return AnalysisOrchestrationService(connect=self.connect, find_item=lambda _: self.item,
            source_fingerprint=lambda _: "synthetic-v1", snapshot_builder=lambda _: copy.deepcopy(self.snapshot),
            initial_builder=builder, agent_runner=self.agent, method_runner=lambda *args: self.fail("no method call"),
            schedule=False)

    def start(self, request="first"):
        return self.service.start("synthetic", {"model": "synthetic-model", "request_id": request})

    def ready(self):
        run = self.start()
        self.assertTrue(self.service._build_initial(run["run_id"]))
        return self.service.status("synthetic", run["run_id"])

    def task(self, run):
        with self.service._db() as db:
            stored = self.service._read_run(db, run["run_id"])
            return self.service._register(db, stored, {"role": "core", "question": "Synthetic guard check",
                "why_now": "CPU check", "success_criteria": "No unsafe adoption"}, phase="core")

    def rows(self, table):
        with self.service._db() as db:
            return [tuple(row) for row in db.execute("SELECT * FROM " + table + " ORDER BY rowid")]

    def test_same_usage_payload_is_idempotent_despite_report_timestamp(self):
        run = self.ready()
        task = self.task(run)
        usage = {"usage_id": "one", "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "reported": True}
        self.service._record_usage(run["run_id"], task["task_id"], usage)
        before = self.rows("orchestration_usage")
        self.service._record_usage(run["run_id"], task["task_id"], {**usage, "reported_at": "later"})
        self.assertEqual(self.rows("orchestration_usage"), before)
        self.assertEqual(json.loads(before[0][3])["total_tokens"], 0)

    def test_same_usage_id_changed_payload_or_task_is_explicit_immutable_conflict(self):
        run = self.ready()
        task = self.task(run)
        usage = {"usage_id": "one", "input_tokens": 7, "output_tokens": 3, "total_tokens": 10,
                 "provider": "openai", "model": "synthetic-model", "reported": True}
        self.service._record_usage(run["run_id"], task["task_id"], usage)
        before = self.rows("orchestration_usage")
        variants = [{**usage, "total_tokens": 100}, {**usage, "reported": False},
                    {**usage, "input_tokens": None}, {**usage, "model": "other-model"}, {**usage, "extra": True}]
        for value in variants:
            with self.subTest(value=value):
                with self.assertRaises(AnalysisContractError) as error:
                    self.service._record_usage(run["run_id"], task["task_id"], value)
                self.assertEqual(error.exception.code, "usage_conflict")
                self.assertEqual(self.rows("orchestration_usage"), before)
        with self.assertRaises(AnalysisContractError):
            self.service._record_usage(run["run_id"], "different-task", usage)
        self.assertEqual(self.rows("orchestration_usage"), before)

    def test_unknown_usage_remains_null_and_aggregate_explicitly_partial(self):
        run = self.ready()
        task = self.task(run)
        self.service._record_usage(run["run_id"], task["task_id"], {"input_tokens": 7,
                                  "output_tokens": None, "total_tokens": None, "reported": True})
        usage = self.service.status("synthetic", run["run_id"])["usage"]
        self.assertEqual(usage["input_tokens"], 7)
        self.assertIsNone(usage["output_tokens"])
        self.assertIsNone(usage["total_tokens"])
        self.assertEqual(usage["measurement_status"], "partial")
        self.assertFalse(usage["tokens_complete"])

    def test_legacy_usage_without_payload_proof_is_retained_for_reconciliation(self):
        run = self.ready()
        task = self.task(run)
        with self.service._db() as db:
            db.execute("INSERT INTO orchestration_usage VALUES (?,?,?,?)", (run["run_id"] + ":legacy",
                run["run_id"], task["task_id"], json.dumps({"task_id": task["task_id"], "input_tokens": 7})))
        before = self.rows("orchestration_usage")
        with self.assertRaises(AnalysisContractError) as error:
            self.service._record_usage(run["run_id"], task["task_id"], {"usage_id": "legacy", "input_tokens": 7})
        self.assertEqual(error.exception.code, "usage_conflict")
        self.assertEqual(self.rows("orchestration_usage"), before)

    def test_reported_zero_is_complete_when_the_call_is_measured(self):
        run = self.ready()
        task = self.task(run)
        with self.service._db() as db:
            stored = self.service._read_run(db, run["run_id"])
            stored["calls_started"] = 1  # A synthetic completed-call ledger, not a model call.
            self.service._write_run(db, stored)
        self.service._record_usage(run["run_id"], task["task_id"], {
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "reported": True})
        usage = self.service.status("synthetic", run["run_id"])["usage"]
        self.assertEqual(usage["total_tokens"], 0)
        self.assertEqual(usage["measurement_status"], "reported")
        self.assertTrue(usage["tokens_complete"])

    def test_same_builder_ready_cache_reused_without_execution(self):
        run = self.ready()
        before = self.rows("orchestration_initials")
        reused = self.start("second")
        self.assertEqual(reused["initial_id"], run["initial_id"])
        self.assertEqual(self.rows("orchestration_initials"), before)
        self.assertEqual((self.builder.freezes, self.builder.calls), (1, 1))
        self.assertFalse(self.agent_calls)

    def test_changed_builder_ready_cache_rejected_and_retained(self):
        run = self.ready()
        before = self.rows("orchestration_initials")
        self.builder.version = "synthetic-initial-2"
        with self.assertRaises(AnalysisContractError) as error:
            self.start("changed-builder")
        self.assertEqual(error.exception.code, "initial_revalidation_required")
        self.assertEqual(self.rows("orchestration_initials"), before)
        state = self.service.status("synthetic", run["run_id"])
        self.assertEqual(state["initial"]["status"], "revalidation_required")
        self.assertEqual(state["initial"]["stored_status"], "ready")
        self.assertFalse(state["can_resume"])
        self.assertEqual(len(self.rows("orchestration_runs")), 1)
        self.assertEqual(self.service.result("synthetic", run["run_id"])["initial"]["snapshot"]["input_hash"], "synthetic-v1")

    def test_changed_stage_or_unknown_builder_does_not_reuse_ready(self):
        self.ready()
        before = self.rows("orchestration_initials")
        self.builder.stages = (InitialStage("snapshot", "Synthetic snapshot", "2"),)
        with self.assertRaises(AnalysisContractError):
            self.start("changed-stage")
        self.builder.stages = SyntheticBuilder.stages
        self.builder.version = ""
        with self.assertRaises(AnalysisContractError):
            self.start("unknown-builder")
        self.service = self.make_service(None)
        with self.assertRaises(AnalysisContractError):
            self.start("unversioned-builder")
        self.assertEqual(self.rows("orchestration_initials"), before)
        self.assertFalse(self.agent_calls)

    def test_legacy_ready_without_metadata_requires_revalidation(self):
        run = self.ready()
        with self.service._db() as db:
            db.execute("DELETE FROM orchestration_initial_builds")
            db.execute("DELETE FROM orchestration_initial_stages")
        before = self.rows("orchestration_initials")
        with self.assertRaises(AnalysisContractError) as error:
            self.start("legacy")
        self.assertEqual(error.exception.code, "initial_revalidation_required")
        self.assertEqual(self.rows("orchestration_initials"), before)
        self.assertEqual(self.service.status("synthetic", run["run_id"])["initial"]["status"], "revalidation_required")

    def test_existing_run_cannot_resume_or_dispatch_under_changed_builder(self):
        run = self.ready()
        before = self.rows("orchestration_initials")
        self.builder.version = "synthetic-initial-2"
        with self.assertRaises(AnalysisContractError):
            self.service.resume("synthetic", run["run_id"])
        self.service.run(run["run_id"])
        state = self.service.status("synthetic", run["run_id"])
        self.assertEqual(state["status"], "recovery_required")
        self.assertEqual(state["error"], "initial_revalidation_required")
        self.assertEqual(state["calls_started"], 0)
        self.assertFalse(self.agent_calls)
        self.assertEqual(self.rows("orchestration_initials"), before)

    def test_missing_terminal_cannot_be_adopted_by_handler(self):
        run = self.ready()
        task = self.task(run)
        self.service._execute(run["run_id"], task["task_id"])
        state = self.service.status("synthetic", run["run_id"])
        self.assertEqual(len(self.agent_calls), 1)  # Fake transport only.
        self.assertEqual(state["tasks"][0]["status"], "uncertain")
        self.assertEqual(state["tasks"][0]["error"], "response_completion_unknown")
        self.assertEqual(self.rows("orchestration_results"), [])
        self.assertEqual(self.rows("orchestration_decisions"), [])


if __name__ == "__main__":
    unittest.main()
