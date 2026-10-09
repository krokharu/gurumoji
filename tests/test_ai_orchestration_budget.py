"""Lifecycle CPU fixtures and isolated loopback worker, never real model proof."""
import ast
import copy
import http.server
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
import types
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.analysis_orchestration import ExecutionStopped, OrchestrationBudget
from gurumoji.services.ai import client
from gurumoji.services.ai.request_budget import BatchQuota, BudgetHold, payload_hash
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters, ADAPTER_VERSION
from gurumoji.services.subprocesses import run_cancellable_subprocess
from test_ai_request_budget import Clock, make_budget, make_m_budget, count_proof, CONDITIONS
import test_analysis_orchestration as runtime_fixture
import test_expert_data_hooks as hook_fixture
from test_analysis_orchestration import core, stop, intent

ROOT = Path(__file__).resolve().parents[1]
CPU_PROOF = []  # Safe hashes, counts and timing only; no request/response bodies.
INITIAL_PROMOTION_PROOF = []


def app_call_function(run_subprocess):
    # Execute the exact app seam without app import/startup or user DB/settings.
    tree = ast.parse((ROOT / "src/gurumoji/app.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "call_orchestration_ai_json")
    namespace = {"ai_client": client, "copy": copy,
        "AI_HTTP_WORKER_FILE": ROOT / "src/gurumoji/ai_http_worker.py",
        "run_cancellable_subprocess": run_subprocess,
        "lmstudio_base_url": lambda value="": value.rstrip("/") if value.rstrip("/").endswith("/v1") else value.rstrip("/") + "/v1",
        "lmstudio_model_id": lambda value: value, "lmstudio_reasoning_settings": lambda *_: {},
        "extract_lmstudio_text": lambda value: value["choices"][0]["message"]["content"],
        "extract_openai_text": lambda *_: "", "extract_google_text": lambda *_: "",
        "AI_MODEL_PROVIDERS": {"lmstudio": {"label": "TEST"}}}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / "src/gurumoji/app.py"), "exec"), namespace)
    return namespace[node.name]


class BudgetFixture:
    def setUp(self):
        self.fixture = runtime_fixture.RuntimeTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.clock = Clock()
        self.budgets = []
        self.batch = BatchQuota(max_calls=216, max_tokens=6193152)
        self.factory = self.make_factory(self.batch)
        self.service = self.fixture.make_service(budget_clock=self.clock)
        self.service.agent_runner = lambda role, context, options, check, usage: stop() if role == "core" else self.fixture.agent(role, context, options, check, usage)

    def make_factory(self, batch):
        def factory(*, run_id, run_started_at, clock):
            budget = make_budget(clock, batch=batch, run_id=run_id, run_started_at=run_started_at)
            self.budgets.append(budget)
            return budget
        return factory

    def start(self, **extra):
        return self.service.start("conversation", {"model": "synthetic-model", "stop_mode": "auto",
            "max_iterations": None, "time_limit_seconds": None, "max_calls": 20, "max_tasks": 30, **extra}, budget_factory=self.factory)

    def task(self, run, role="core", **extra):
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            return self.service._register(db, state, intent(role, **extra), phase="core", automatic=role == "core")

    def status(self, run):
        return self.service.status("conversation", run["run_id"])


class LifecycleTests(BudgetFixture, unittest.TestCase):
    def test_initial_cpu_origin_precedes_builder_and_no_late_initial_adoption(self):
        def slow(item):
            self.clock.advance(601)
            return self.fixture.build(item)
        self.service.snapshot_builder = slow
        with self.assertRaises(AnalysisContractError) as caught:
            self.start()
        self.assertEqual(caught.exception.code, "time_limit")
        self.assertEqual(self.budgets[0].ledger()["run_started_at"], 1_000_000_000)
        self.assertEqual(self.budgets[0].ledger()["entry_count"], 0)
        with self.service._db() as db:
            self.assertEqual(db.execute("SELECT status FROM orchestration_initials").fetchone()[0], "failed")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_runs").fetchone()[0], 0)

    def staged_service(self, delay=0):
        from gurumoji.orchestration_initial import InitialStage
        outer = self
        class Builder:
            version = "TEST-stage-1"
            stages = [InitialStage("snapshot", "TEST-snapshot")]
            def freeze(self, item): return copy.deepcopy(outer.fixture.snapshot)
            def run_stage(self, stage_id, frozen, outputs):
                outer.clock.advance(delay)
                return copy.deepcopy(frozen)
        self.fixture.item.update(revision_count=1, analysis_revision=2)
        self.service = self.fixture.make_service(initial_builder=Builder(), budget_clock=self.clock)
        self.service.agent_runner = lambda *_: self.fail("initial hold must not call model")

    def test_staged_initial_cpu_keeps_raw_checkpoint_but_fences_adoption(self):
        self.staged_service(delay=601)
        run = self.start()
        self.assertFalse(self.service._build_initial(run["run_id"]))
        state = self.status(run)
        self.assertEqual(state["stop_reason"], "time_limit")
        self.assertEqual(state["calls_started"], 0)
        with self.service._db() as db:
            self.assertNotEqual(db.execute("SELECT status FROM orchestration_initials").fetchone()[0], "ready")
            checkpoint = db.execute("SELECT state_json,output_json FROM orchestration_initial_stages").fetchone()
            self.assertEqual(json.loads(checkpoint[0])["status"], "completed")
            self.assertEqual(json.loads(checkpoint[1]), self.fixture.snapshot)

    def test_staged_promotion_cpu_cannot_make_late_snapshot_ready(self):
        self.staged_service()
        run = self.start()
        original = self.service._source_labels
        def slow(snapshot):
            value = original(snapshot); self.clock.advance(601); return value
        self.service._source_labels = slow
        self.assertFalse(self.service._build_initial(run["run_id"]))
        self.assertEqual(self.status(run)["stop_reason"], "time_limit")
        with self.service._db() as db:
            self.assertNotEqual(db.execute("SELECT status FROM orchestration_initials").fetchone()[0], "ready")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_label_versions").fetchone()[0], 0)

    def test_context_cpu_before_old_started_epoch_counts(self):
        run = self.start(); task = self.task(run)
        original = self.service._context
        def slow(*args):
            result = original(*args); self.clock.advance(241); return result
        self.service._context = slow
        self.service._execute(run["run_id"], task["task_id"])
        state = self.status(run)
        self.assertIsNone(state["tasks"][0]["started_at"])
        self.assertEqual(state["calls_started"], 0)
        self.assertEqual(state["tasks"][0]["error"], "call_timeout")

    def test_queue_aging_is_not_reset_at_dispatch(self):
        run = self.start(); task = self.task(run)
        self.clock.advance(240)
        self.service._execute(run["run_id"], task["task_id"])
        state = self.status(run)
        self.assertEqual(state["stop_reason"], "call_timeout")
        self.assertEqual(state["calls_started"], 0)

    def test_late_code_result_saved_quarantined_and_no_new_origin(self):
        run = self.start(); task = self.task(run, "statistics", method_id="participation")
        def slow(*args):
            result = self.fixture.method(*args); self.clock.advance(241); return result
        self.service.method_runner = slow
        self.service._execute(run["run_id"], task["task_id"])
        state = self.status(run)
        self.assertEqual(state["code_executions"], 1)
        self.assertEqual(state["tasks"][0]["status"], "quarantined")
        self.assertEqual(state["results"][0]["validation_status"], "quarantined")
        self.assertEqual(state["request_budget"]["run_started_at"], run["request_budget"]["run_started_at"])
        self.assertEqual(state["request_budget"]["ledger"]["entry_count"], 0)

    def test_validation_cpu_rollback_preserves_raw_only(self):
        run = self.start(); task = self.task(run)
        original = self.service._validate_result
        def slow(*args):
            value = original(*args); self.clock.advance(241); return value
        self.service._validate_result = slow
        self.service._execute(run["run_id"], task["task_id"])
        state = self.status(run)
        self.assertEqual(state["results"][0]["validation_status"], "quarantined")
        self.assertEqual(state["tasks"][0]["error"], "call_timeout")
        with self.service._db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_label_proposals").fetchone()[0], 0)

    def test_core_adoption_cpu_rollback(self):
        run = self.start()
        original = self.service._apply_core
        def slow(*args):
            original(*args); self.clock.advance(241)
        self.service._apply_core = slow
        self.service.run(run["run_id"])
        self.assertEqual(self.status(run)["stop_reason"], "call_timeout")
        with self.service._db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_decisions").fetchone()[0], 0)

    def test_cancel_before_dispatch_and_read_paths_never_create_budget(self):
        run = self.start(); task = self.task(run)
        self.service.cancel("conversation", run["run_id"])
        self.service._execute(run["run_id"], task["task_id"])
        for _ in range(3):
            self.status(run)
            self.service.history("conversation")
            self.service.result("conversation", run["run_id"])
        self.assertEqual(len(self.budgets), 1)
        self.assertEqual(self.budgets[0].ledger()["entry_count"], 0)

    def test_restart_guarded_origin_refused_old_unprotected_readable(self):
        run = self.start()
        restarted = self.fixture.make_service()
        self.assertEqual(restarted.status("conversation", run["run_id"])["run_id"], run["run_id"])
        with self.assertRaises(AnalysisContractError) as caught:
            restarted.resume("conversation", run["run_id"])
        self.assertEqual(caught.exception.code, "budget_origin_unavailable")
        restarted.run(run["run_id"])
        self.assertEqual(restarted.status("conversation", run["run_id"])["stop_reason"], "budget_origin_unavailable")
        old = restarted.start("conversation", {"model": "synthetic-model", "request_id": "ordinary"})
        self.assertNotIn("request_budget", old)

    def test_same_cached_service_has_per_run_and_per_task_origins(self):
        first = self.start(request_id="first")
        self.clock.advance(10)
        second = self.start(request_id="second")
        self.assertIsNot(self.service._run_budgets[first["run_id"]], self.service._run_budgets[second["run_id"]])
        self.assertEqual(second["request_budget"]["run_started_at"] - first["request_budget"]["run_started_at"], 10)
        tasks = []
        def enqueue(run): tasks.append(self.task(run))
        threads = [threading.Thread(target=enqueue, args=(run,)) for run in (first, second)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(2); self.assertFalse(thread.is_alive())
        self.assertEqual(len(tasks), 2)
        self.assertNotEqual(tasks[0]["run_id"], tasks[1]["run_id"])
        json.dumps(self.status(first)); json.dumps(self.status(second))

    def test_reusing_one_budget_for_another_run_is_rejected(self):
        first = self.start()
        old = self.budgets[0]
        with self.assertRaises(AnalysisContractError) as caught:
            self.service.start("conversation", {"model": "synthetic-model", "request_id": "TEST-reused"},
                budget_factory=lambda **_: old)
        self.assertEqual(caught.exception.code, "budget_origin_mismatch")
        self.assertEqual(len(self.service.history("conversation")), 1)

    def test_clock_identity_and_origin_change_refused(self):
        budget = make_budget(self.clock)
        with self.assertRaises(AnalysisContractError):
            OrchestrationBudget(budget, run_id="test-run", run_started_at=self.clock(), clock=lambda: self.clock())
        run = self.start()
        self.clock.advance(-1)
        self.assertEqual(self.service._budget_reason(run), "budget_clock_mismatch")
        self.clock.advance(1)
        self.assertEqual(self.service._budget_reason(run), "budget_clock_mismatch")

    def test_hook_cpu_aging_blocks_continuation_without_new_deadline(self):
        fixture = hook_fixture.ExpertDataHookTests()
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        fixture.service._budget_clock = self.clock
        def factory(**kw):
            budget = make_budget(self.clock, run_id=kw["run_id"], run_started_at=kw["run_started_at"],
                model="fixture", token_counter=lambda payload: count_proof(payload, model="fixture"))
            self.budgets.append(budget); return budget
        fixture.service._budget_factory = factory
        def cpu_call(*args, **kwargs):
            fixture.calls.append((json.loads(args[4]), args[6]))
            self.assertIs(kwargs["request_budget"], self.budgets[-1])
            args[7]()
            return hook_fixture.wire_response(fixture.respond(len(fixture.calls)))
        _, fixture.service.agent_runner = make_orchestration_adapters(call_ai_json=cpu_call,
            load_token_config=lambda: type("Config", (), {"lmstudio_base_url": "http://127.0.0.1:9/v1"})(),
            configured_ai_credentials=lambda *_: ("", "fixture"))
        fixture.respond = lambda _: fixture.hook_response([hook_fixture.request(ids=[fixture.ids[-1]])])
        original = fixture.service._expert_data_hook
        def slow(*args):
            result = original(*args)
            if args[2] == "read": self.clock.advance(241)
            return result
        fixture.service._expert_data_hook = slow
        state, task = fixture.dispatch()
        self.assertEqual(len(fixture.calls), 1)
        self.assertEqual(state["stop_reason"], "call_timeout")
        self.assertEqual(task["status"], "cancelled")
        self.assertEqual(self.budgets[0].ledger()["entry_count"], 0)
        self.assertEqual(state["request_budget"]["run_started_at"], self.clock() - 241)

    def test_verification_cpu_late_result_not_adopted(self):
        run = self.start(); task = self.task(run, "verification")
        def slow(*args):
            self.clock.advance(241)
            return {"summary": "TEST", "claims": [], "analysis_requests": [], "label_patches": []}
        self.service.agent_runner = slow
        self.service._execute(run["run_id"], task["task_id"])
        state = self.status(run)
        self.assertEqual(state["tasks"][0]["status"], "quarantined")
        self.assertEqual(state["stop_reason"], "call_timeout")

    def test_cleanup_clock_is_observed_without_reset(self):
        run = self.start()
        self.service._notify_completed = lambda *_: self.clock.advance(601)
        self.service.run(run["run_id"])
        state = self.status(run)
        self.assertEqual(state["request_budget"]["cleanup_hold"], "time_limit")
        self.assertEqual(state["request_budget"]["run_started_at"], run["request_budget"]["run_started_at"])
        self.assertFalse(state["request_budget"]["ledger"]["measurement_ready"])

    def test_completion_callback_cpu_overrun_is_not_recorded_successful(self):
        self.service.on_complete = lambda *_: self.clock.advance(601)
        run = self.start()
        self.service.run(run["run_id"])
        state = self.status(run)
        self.assertEqual(state["completion_callback_status"], "failed")
        self.assertEqual(state["publication_error"], "time_limit")
        self.assertEqual(state["request_budget"]["cleanup_hold"], "time_limit")
        self.assertNotIn(run["run_id"], self.service._driving)

    def test_token_proof_delay_uses_existing_origin_and_zero_post(self):
        run = self.start(); task = self.task(run)
        def slow(payload):
            self.clock.advance(236); return count_proof(payload)
        budget = self.budgets[0]; budget._counter = slow
        posts = []
        call = app_call_function(lambda *args, **kwargs: posts.append(args))
        with self.assertRaises(BudgetHold):
            call("lmstudio", "", "synthetic-model", "TEST", "TEST", "test", {"type": "object"},
                 base_url="http://127.0.0.1:9", request_budget=budget,
                 task_id=task["task_id"], attempt_id="test")
        self.assertEqual(posts, [])
        self.assertEqual(budget.ledger()["entry_count"], 0)
        self.assertIsNotNone(budget.ledger()["batch"]["hold_reason"])

    def test_subprocess_startup_delay_cannot_reset_task_clock(self):
        run = self.start(); task = self.task(run)
        stages = []
        def startup(*args, **kwargs):
            stages.append("startup")
            self.clock.advance(241)
            kwargs["check_cancelled"]()
            self.fail("late subprocess must not start")
        call = app_call_function(startup)
        with self.assertRaises(BudgetHold) as caught:
            call("lmstudio", "", "synthetic-model", "TEST", "TEST", "test", {"type": "object"},
                 check_cancelled=lambda: self.service._check(run["run_id"], run["generation"], task["task_id"]),
                 base_url="http://127.0.0.1:9", request_budget=self.budgets[0],
                 task_id=task["task_id"], attempt_id="TEST-startup")
        self.assertEqual(caught.exception.reason, "transport_unknown")
        ledger = self.budgets[0].ledger()
        self.assertEqual(stages, ["startup"])
        self.assertEqual(ledger["entry_count"], 1)
        self.assertEqual(ledger["observed_wire_calls"], 0)
        self.assertEqual(ledger["reserved_unknown_calls"], 1)
        self.assertEqual(self.status(run)["stop_reason"], "call_timeout")


class InitialPromotionTests(BudgetFixture, unittest.TestCase):
    """IR-L01 old defect and fixed normal/negative probes, no transport calls."""
    OLD = "113f2f94214e411644256af8342da0099736530e"
    # Preregistered finite CPU delays. The normal case has 0.25 seconds left.
    CASES = (("normal", 599.75, 0, 0, 0, 0, 0),
             ("labels", 599.75, .5, 0, 0, 0, 0),
             ("snapshot_json_hash", 599.75, 0, .3, .3, 0, 0),
             ("high_cost_hash", 599.75, 0, 0, .5, 0, 0),
             ("labels_json", 599.75, 0, 0, 0, .5, 0),
             ("run_json", 599.75, 0, 0, 0, 0, .5),
             ("builder", 600.125, 0, 0, 0, 0, 0))

    def module(self, old=False):
        if not old:
            import gurumoji.analysis_orchestration as module
            return module
        import hashlib
        # Independent pins keep coordinated fixture/manifest edits from redefining history.
        expected = {
            "source_commit": "113f2f94214e411644256af8342da0099736530e",
            "source_path": "src/gurumoji/analysis_orchestration.py",
            "git_blob": "f625fb702d9998079bfafda0b18fe759814ab576",
            "sha256": "9ac84563489a93953f1d25ed7776521d58ce09663af5d8e29783c48bc799fca7",
            "bytes": 165604,
            "purpose": "Public code-only fixed previous initial-promotion fixture; original Git history excluded.",
        }
        fixture_root = ROOT / "tests/fixtures/orchestration_history"
        fixture_path = fixture_root / expected["source_commit"] / "analysis_orchestration.py"
        try:
            manifest_bytes = (fixture_root / "manifest.json").read_bytes()
            source = fixture_path.read_bytes()
        except OSError as exc:
            self.fail(f"IR-L01 historical fixture unavailable: {exc}")
        self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(),
            "37b62804cc8695ff30134a49340ec9c40220b85a9e5856882bd9a6a0a56474ce",
            "IR-L01 manifest integrity mismatch")
        self.assertEqual(json.loads(manifest_bytes), expected, "IR-L01 manifest metadata mismatch")
        self.assertEqual(len(source), expected["bytes"], "IR-L01 fixture size mismatch")
        self.assertEqual(hashlib.sha256(source).hexdigest(), expected["sha256"],
            "IR-L01 fixture SHA256 mismatch")
        git_blob = hashlib.sha1(b"blob " + str(len(source)).encode("ascii") + b"\0" + source).hexdigest()
        self.assertEqual(git_blob, expected["git_blob"], "IR-L01 fixture Git blob mismatch")
        module = types.ModuleType("gurumoji._old_lifecycle_fixture")
        module.__package__ = "gurumoji"
        exec(compile(source, str(fixture_path), "exec"), module.__dict__)
        return module  # Never check out or replace the installed module/global paths.

    def probe(self, case, old=False, staged=False, event_delay=0):
        name, builder_delay, labels_delay, snapshot_delay, hash_delay, labels_json_delay, run_delay = case
        module = self.module(old)
        fixture = runtime_fixture.RuntimeTests(); fixture.setUp()
        clock = Clock(); budgets = []; operations = []
        try:
            original_build = fixture.build
            def build(item):
                value = original_build(item); clock.advance(builder_delay); operations.append("builder"); return value
            kwargs = {}
            if staged:
                from gurumoji.orchestration_initial import InitialStage
                fixture.item.update(revision_count=1, analysis_revision=2)
                class Builder:
                    version = "TEST-promotion-1"
                    stages = [InitialStage("snapshot", "TEST")]
                    def freeze(self, item): return copy.deepcopy(fixture.snapshot)
                    def run_stage(self, stage_id, frozen, outputs):
                        clock.advance(builder_delay); operations.append("builder"); return copy.deepcopy(frozen)
                kwargs["initial_builder"] = Builder()
            def factory(**kw):
                budget = make_budget(clock, run_id=kw["run_id"], run_started_at=kw["run_started_at"])
                budgets.append(budget); return budget
            service = module.AnalysisOrchestrationService(connect=fixture.connect,
                find_item=lambda *_: fixture.item, snapshot_builder=build,
                source_fingerprint=lambda item: item["revision"], agent_runner=lambda *_: self.fail("unexpected model"),
                method_runner=lambda *_: self.fail("unexpected code"), schedule=False,
                budget_factory=factory, budget_clock=clock, **kwargs)
            original_labels, original_json, original_hash = service._source_labels, module._json, module.fingerprint
            label_payloads = []
            def labels(snapshot):
                result = original_labels(snapshot); label_payloads.append(result)
                clock.advance(labels_delay); operations.append("labels"); return result
            def encode(value):
                result = original_json(value)
                if isinstance(value, dict) and "analysis" in value and "input_hash" in value and "evidence" in value:
                    clock.advance(snapshot_delay); operations.append("snapshot_json")
                elif isinstance(value, dict) and "run_id" in value and "schema_version" in value and value.get("phase") == "core":
                    clock.advance(run_delay); operations.append("run_json")
                elif any(value is payload for payload in label_payloads):
                    clock.advance(labels_json_delay); operations.append("labels_json")
                elif isinstance(value, dict) and value.get("type") == "initial_saved":
                    clock.advance(event_delay); operations.append("event_json")
                return result
            def digest(value):
                result = original_hash(value)
                if isinstance(value, dict) and "analysis" in value and "input_hash" in value and "evidence" in value:
                    clock.advance(hash_delay); operations.append("snapshot_hash")
                return result
            service._source_labels = labels
            error = None
            with patch.object(module, "_json", side_effect=encode), patch.object(module, "fingerprint", side_effect=digest):
                try:
                    run = service.start("conversation", {"model": "synthetic-model", "request_id": "TEST-promotion"})
                    if staged: service._build_initial(run["run_id"])
                except AnalysisContractError as exc: error = exc.code
            with service._db() as db:
                initial = dict(db.execute("SELECT status,snapshot_hash FROM orchestration_initials").fetchone())
                runs = db.execute("SELECT COUNT(*) FROM orchestration_runs").fetchone()[0]
                labels_count = db.execute("SELECT COUNT(*) FROM orchestration_label_versions").fetchone()[0]
                saved_events = sum(json.loads(row[0])["type"] == "initial_saved"
                    for row in db.execute("SELECT payload_json FROM orchestration_events"))
                checkpoint = db.execute("SELECT state_json,output_json FROM orchestration_initial_stages").fetchone()
                if staged:
                    state = service._read_run(db, run["run_id"])
                    error = state["stop_reason"] or None
            result = {"case": ("OLD" if old else "FIX") + ("-staged-" if staged else "-") + name + ("-event_json" if event_delay else ""),
                "delay_seconds": list(case[1:]), "event_delay_seconds": event_delay,
                "origin": budgets[0].ledger()["run_started_at"],
                "elapsed": clock() - budgets[0].ledger()["run_started_at"], "initial_status": initial["status"],
                "snapshot_hash": initial["snapshot_hash"], "runs": runs, "label_versions": labels_count,
                "error": error, "initial_saved_events": saved_events,
                "reservation_count": budgets[0].ledger()["entry_count"],
                "wire_calls": budgets[0].ledger()["actual_wire_calls"], "operations": operations,
                "raw_checkpoint_completed": bool(checkpoint and json.loads(checkpoint[0])["status"] == "completed" and checkpoint[1])}
            INITIAL_PROMOTION_PROOF.append(result)
            return result
        finally: fixture.doCleanups()

    def test_old_blob_reproduces_IR_L01_without_mutating_repository(self):
        for case in (self.CASES[0], self.CASES[1], self.CASES[2], self.CASES[-1]):
            with self.subTest(case=case[0]):
                result = self.probe(case, old=True)
                self.assertEqual(result["wire_calls"], 0)
                self.assertEqual(result["reservation_count"], 0)
                expected = "failed" if case[0] == "builder" else "ready"
                self.assertEqual(result["initial_status"], expected)
                self.assertEqual(result["runs"], 1 if case[0] == "normal" else 0)
                if case[0] in {"labels", "snapshot_json_hash"}:
                    self.assertEqual(result["error"], "time_limit")

    def test_fixed_nonstaged_all_preparation_cpu_precedes_atomic_promotion(self):
        for case in self.CASES:
            with self.subTest(case=case[0]):
                result = self.probe(case)
                self.assertEqual((result["reservation_count"], result["wire_calls"]), (0, 0))
                self.assertEqual(result["origin"], 1_000_000_000)
                normal = case[0] == "normal"
                self.assertEqual(result["initial_status"], "ready" if normal else "failed")
                if not normal: self.assertIsNone(result["snapshot_hash"])
                self.assertEqual(result["runs"], int(normal))
                self.assertEqual(result["label_versions"], int(normal))
                self.assertEqual(result["error"], None if normal else "time_limit")

    def test_fixed_staged_all_preparation_cpu_precedes_atomic_promotion(self):
        for case in self.CASES[:-1]:
            with self.subTest(case=case[0]):
                result = self.probe(case, staged=True)
                self.assertTrue(result["raw_checkpoint_completed"])
                normal = case[0] == "normal"
                self.assertEqual(result["initial_status"], "ready" if normal else "failed")
                if not normal: self.assertIsNone(result["snapshot_hash"])
                self.assertEqual(result["runs"], 1)  # Existing staged run, never a second run.
                self.assertEqual(result["label_versions"], int(normal))
                self.assertEqual(result["error"], None if normal else "time_limit")
                self.assertEqual((result["reservation_count"], result["wire_calls"]), (0, 0))

    def test_cached_initial_is_preserved_when_new_run_labels_cpu_times_out(self):
        first = self.start(request_id="TEST-original")
        with self.service._db() as db:
            before = dict(db.execute("SELECT * FROM orchestration_initials").fetchone())
        original = self.service._source_labels
        def slow(snapshot):
            result = original(snapshot); self.clock.advance(600.25); return result
        self.service._source_labels = slow
        with self.assertRaises(AnalysisContractError) as caught:
            self.start(request_id="TEST-cache-timeout")
        self.assertEqual(caught.exception.code, "time_limit")
        with self.service._db() as db:
            self.assertEqual(dict(db.execute("SELECT * FROM orchestration_initials").fetchone()), before)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_runs").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_label_versions").fetchone()[0], 1)
        self.assertEqual(len(self.budgets), 2)
        self.assertEqual(self.budgets[1].ledger()["entry_count"], 0)
        self.assertEqual(self.budgets[1].ledger()["actual_wire_calls"], 0)
        INITIAL_PROMOTION_PROOF.append({"case": "FIX-cached-timeout", "old_initial_byte_fields_unchanged": True,
            "existing_runs": 1, "new_runs": 0, "wire_calls": 0, "reservation_count": 0})

    def test_final_transaction_fence_rolls_back_ready_run_labels_and_event(self):
        for staged in (False, True):
            with self.subTest(staged=staged):
                result = self.probe(self.CASES[0], staged=staged, event_delay=.5)
                self.assertEqual(result["initial_status"], "failed")
                self.assertIsNone(result["snapshot_hash"])
                self.assertEqual(result["runs"], int(staged))
                self.assertEqual(result["label_versions"], 0)
                self.assertEqual(result["initial_saved_events"], 0)
                self.assertEqual(result["error"], "time_limit")
                self.assertEqual((result["reservation_count"], result["wire_calls"]), (0, 0))
                self.assertEqual(result["raw_checkpoint_completed"], staged)


class LoopbackLifecycleTests(BudgetFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.clock = time.monotonic
        self.service._budget_clock = self.clock
        self.service.adapter_version = ADAPTER_VERSION
        self.received, self.children, self.raw_usage = [], [], []
        self.received_output_caps = []
        self.post_received, self.release_response = threading.Event(), threading.Event()
        self.wait_for_cancel = False
        outer = self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.received.append(payload_hash(payload))
                outer.received_output_caps.append(payload.get("max_tokens"))
                outer.post_received.set()
                if outer.wait_for_cancel: outer.release_response.wait(3)
                body = outer.response_body(len(outer.received)) if callable(outer.response_body) else outer.response_body
                value = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(body)}}]}
                if outer.include_usage:
                    value["usage"] = {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}
                encoded = json.dumps(value).encode()
                try:
                    self.send_response(200); self.send_header("Content-Length", str(len(encoded))); self.end_headers(); self.wfile.write(encoded)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass  # Cancellation closes the synthetic socket.
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close_server)
        self.include_usage, self.response_body = True, {**core(), "stop": None}
        def runner(command, **kwargs):
            # Production cancellation/polling subprocess implementation, exact worker.
            self.children.append(time.monotonic())
            return run_cancellable_subprocess(command, **kwargs)
        call = app_call_function(runner)
        config = type("Config", (), {"lmstudio_base_url": f"http://127.0.0.1:{self.server.server_port}"})()
        _, adapter = make_orchestration_adapters(call_ai_json=call,
            load_token_config=lambda: config, configured_ai_credentials=lambda *_: ("", "synthetic-model"))
        def observe(role, context, options, check, usage):
            options["_raw_usage_callback"] = self.raw_usage.append
            return adapter(role, context, options, check, usage)
        self.service.agent_runner = observe

    def close_server(self):
        self.release_response.set()
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)
        self.assertFalse(self.thread.is_alive())

    def start(self, **extra):
        return super().start(adapter_version=ADAPTER_VERSION, **extra)

    def proof(self, name, run):
        state = self.status(run)
        ledger = self.service._run_budgets[run["run_id"]].request_budget.ledger()
        CPU_PROOF.append({"case": name, "wire_count": len(self.received), "child_count": len(self.children),
            "payload_hashes": self.received, "ledger": ledger, "task_statuses": [t["status"] for t in state["tasks"]],
            "real_model_calls": 0, "external_http_calls": 0, "synthetic_only": True})
        return ledger

    def test_worker_valid_usage_through_service_context_adapter_app_guard(self):
        run = self.start(); task = self.task(run)
        self.service._execute(run["run_id"], task["task_id"])
        state = self.status(run); ledger = self.proof("valid_usage", run)
        self.assertEqual(state["tasks"][0]["status"], "succeeded")
        self.assertEqual((len(self.received), len(self.children), ledger["entry_count"], ledger["actual_wire_calls"]), (1, 1, 1, 1))
        self.assertEqual(ledger["entries"][0]["usage"]["total_tokens"], 12)
        self.assertEqual(ledger["entries"][0]["ticket"]["payload_hash"], self.received[0])
        self.assertFalse(ledger["measurement_ready"])
        self.assertEqual(state["request_budget"]["ledger"]["actual_wire_calls"], 1)
        self.assertEqual(self.raw_usage, [{"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}])
        self.assertEqual(self.received_output_caps, [4096])

    def test_worker_usage_absent_holds_next_post_reservation_null(self):
        self.include_usage = False
        run = self.start(); task = self.task(run)
        self.service._execute(run["run_id"], task["task_id"])
        ledger = self.proof("absent_usage", run)
        self.assertEqual(len(self.received), 1)
        self.assertEqual(ledger["unknown_usage_entries"], 1)
        self.assertIsNone(ledger["entries"][0]["usage"])
        self.assertEqual(ledger["charged_or_reserved_tokens"], 4106)
        with self.assertRaises(BudgetHold):
            ledger_budget = self.budgets[0]
            client.post_json(f"http://127.0.0.1:{self.server.server_port}/v1/chat/completions", {},
                {"model": "synthetic-model"}, worker_file=ROOT / "src/gurumoji/ai_http_worker.py",
                run_subprocess=lambda *_a, **_k: self.fail("second child prohibited"), request_budget=ledger_budget,
                task_id=task["task_id"], attempt_id="second", timeout=240, retry_delays=())
        self.assertEqual(len(self.received), 1)

    def test_missing_full_payload_proof_zero_child_zero_post(self):
        run = self.start(); task = self.task(run)
        self.budgets[0]._counter = lambda _: None
        self.service._execute(run["run_id"], task["task_id"])
        ledger = self.proof("missing_proof", run)
        self.assertEqual((len(self.received), len(self.children), ledger["entry_count"]), (0, 0, 0))
        self.assertEqual(self.status(run)["calls_started"], 1)  # Entrance != reservation != actual wire.

    def test_cancel_after_actual_wire_stops_worker_and_holds_unknown_usage(self):
        self.wait_for_cancel = True
        run = self.start(); task = self.task(run)
        thread = threading.Thread(target=self.service._execute, args=(run["run_id"], task["task_id"]))
        thread.start()
        try:
            self.assertTrue(self.post_received.wait(2), "own loopback POST not received")
            self.service.cancel("conversation", run["run_id"])
            thread.join(2)
            self.assertFalse(thread.is_alive())
        finally:
            self.release_response.set(); thread.join(2)
        ledger = self.proof("cancel_after_wire", run)
        self.assertEqual(len(self.received), 1)
        self.assertEqual(ledger["entry_count"], 1)
        self.assertEqual(ledger["unknown_usage_entries"], 1)
        self.assertIsNone(ledger["actual_wire_calls"])
        state = self.status(run)
        self.assertEqual(state["status"], "cancelled")
        self.assertEqual(state["request_budget"]["ledger"]["unknown_usage_entries"], 1)
        self.assertEqual(state["results"], [])

    def test_concurrent_cached_service_runs_have_distinct_private_ledgers(self):
        first, second = self.start(request_id="TEST-1"), self.start(request_id="TEST-2")
        tasks = [self.task(run) for run in (first, second)]
        threads = [threading.Thread(target=self.service._execute, args=(run["run_id"], task["task_id"]))
                   for run, task in zip((first, second), tasks)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(3); self.assertFalse(thread.is_alive())
        self.assertEqual(len(self.received), 2)
        ledgers = []
        for run in (first, second):
            state = self.status(run)
            self.assertEqual(state["tasks"][0]["status"], "succeeded", state["tasks"][0]["error"])
            ledger = state["request_budget"]["ledger"]; ledgers.append(ledger)
            self.assertEqual((ledger["entry_count"], ledger["actual_wire_calls"]), (1, 1))
        self.assertEqual(self.batch.snapshot()["reserved_entries"], 2)
        self.assertNotEqual(ledgers[0]["run_id"], ledgers[1]["run_id"])
        CPU_PROOF.append({"case": "concurrent_two_runs", "wire_count": 2, "child_count": len(self.children),
            "ledgers": ledgers, "real_model_calls": 0, "external_http_calls": 0, "synthetic_only": True})

    def test_hook_rounds_share_guard_task_origin_and_finite_wire_counts(self):
        fixture = hook_fixture.ExpertDataHookTests()
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        runner = self.service.agent_runner
        self.service = fixture.service
        self.service.agent_runner = runner
        self.service._budget_clock = self.clock
        def factory(**kw):
            budget = make_budget(self.clock, run_id=kw["run_id"], run_started_at=kw["run_started_at"],
                model="fixture", token_counter=lambda payload: count_proof(payload, model="fixture"))
            self.budgets.append(budget); return budget
        self.service._budget_factory = factory
        self.response_body = lambda n: (hook_fixture.wire_response(fixture.hook_response(
            [hook_fixture.request(ids=[fixture.ids[-1]])])) if n == 1 else hook_fixture.wire_response(fixture.report))
        state, task = fixture.dispatch()
        self.assertEqual(task["status"], "succeeded", task["error"])
        ledger = self.budgets[0].ledger()
        self.assertEqual((len(self.received), len(self.children), ledger["actual_wire_calls"]), (2, 2, 2))
        first, second = (entry["ticket"] for entry in ledger["entries"])
        self.assertEqual(first["task_started_at"], second["task_started_at"])
        self.assertEqual(first["run_started_at"], second["run_started_at"])
        self.assertNotEqual(first["payload_hash"], second["payload_hash"])
        self.assertEqual(task["model_calls"], 2)
        self.assertEqual(len(task["expert_hook_reads"]), 1)
        CPU_PROOF.append({"case": "hook_two_rounds", "wire_count": 2, "child_count": 2,
            "ledger": ledger, "task_statuses": [task["status"]], "real_model_calls": 0,
            "external_http_calls": 0, "synthetic_only": True})


class MProfileLifecycleTests(BudgetFixture, unittest.TestCase):
    def make_factory(self, batch):
        def factory(*, run_id, run_started_at, clock):
            budget = make_m_budget(clock, batch=batch, run_id=run_id, run_started_at=run_started_at)
            self.budgets.append(budget)
            return budget
        return factory

    def test_initial_preparation_uses_original_M_deadline_and_ledger(self):
        origin = self.clock()
        original = self.service.snapshot_builder
        def slow(item):
            self.clock.advance(700)
            return original(item)
        self.service.snapshot_builder = slow
        run = self.start()
        guard = self.service._run_budgets[run["run_id"]]
        self.assertEqual(guard.origin, origin)
        self.assertEqual(guard.deadline, origin + 1800)
        self.assertEqual(guard.deadline, guard.snapshot()["ledger"]["run_deadline"])
        self.assertIsNone(guard.reason())
        self.clock.advance(1099.75)
        self.assertIsNone(guard.reason())
        self.clock.advance(.25)
        self.assertEqual(guard.reason(), "time_limit")
        self.assertEqual(guard.snapshot()["ledger"]["entry_count"], 0)

    def test_initial_preparation_at_M_deadline_is_never_promoted(self):
        def slow(item):
            self.clock.advance(1800)
            return self.fixture.build(item)
        self.service.snapshot_builder = slow
        with self.assertRaises(AnalysisContractError) as caught:
            self.start()
        self.assertEqual(caught.exception.code, "time_limit")
        with self.service._db() as db:
            self.assertEqual(db.execute("SELECT status FROM orchestration_initials").fetchone()[0], "failed")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_runs").fetchone()[0], 0)
        self.assertEqual(self.budgets[0].ledger()["entry_count"], 0)

    def test_M_guard_keeps_task_240_and_rejects_inconsistent_initial_ledger(self):
        budget = make_m_budget(self.clock)
        guard = OrchestrationBudget(budget, run_id="test-run", run_started_at=self.clock(), clock=self.clock)
        self.clock.advance(700); guard.register("later", self.clock())
        self.clock.advance(239.999); self.assertIsNone(guard.reason("later"))
        self.clock.advance(.001); self.assertEqual(guard.reason("later"), "call_timeout")
        ledger = budget.ledger(); ledger["run_deadline"] += 1
        with patch.object(budget, "ledger", return_value=ledger), self.assertRaises(AnalysisContractError) as caught:
            OrchestrationBudget(budget, run_id="test-run", run_started_at=ledger["run_started_at"], clock=self.clock)
        self.assertEqual(caught.exception.code, "budget_origin_mismatch")


class MProfileIPCAndCancellationTests(unittest.TestCase):
    def fixture(self):
        fixture = LoopbackLifecycleTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        def factory(*, run_id, run_started_at, clock):
            budget = make_m_budget(clock, batch=fixture.batch, run_id=run_id, run_started_at=run_started_at)
            fixture.budgets.append(budget)
            return budget
        fixture.factory = factory
        return fixture

    def test_M_exact_existing_worker_roundtrip_known_usage(self):
        fixture = self.fixture()
        fixture.test_worker_valid_usage_through_service_context_adapter_app_guard()
        ledger = fixture.budgets[0].ledger()
        self.assertEqual(ledger["profile"], "M")
        self.assertEqual(ledger["run_deadline"] - ledger["run_started_at"], 1800)
        self.assertEqual(ledger["entries"][0]["ticket"]["trial_call_limit"], 32)

    def test_M_existing_worker_missing_usage_retains_cost_and_blocks_next(self):
        fixture = self.fixture()
        fixture.test_worker_usage_absent_holds_next_post_reservation_null()
        self.assertEqual(fixture.budgets[0].ledger()["profile"], "M")

    def test_M_cancel_after_actual_fixture_wire_retains_unknown_no_retry(self):
        fixture = self.fixture()
        fixture.test_cancel_after_actual_wire_stops_worker_and_holds_unknown_usage()
        ledger = fixture.budgets[0].ledger()
        self.assertEqual(ledger["profile"], "M")
        self.assertEqual(ledger["charged_or_reserved_tokens"], 4106)

    def test_M_worker_rejects_rehashed_invalid_profile_limits_before_HTTP(self):
        fixture = self.fixture()
        from test_ai_request_budget import PAYLOAD
        budget = make_m_budget(time.monotonic)
        received = []
        def corrupt_and_run(command, **kwargs):
            wire = json.loads(kwargs["input_text"])
            ticket = wire["request_budget"]
            ticket["profile_limits"]["run_seconds"] = 1801
            ticket["ticket_hash"] = payload_hash({k: v for k, v in ticket.items() if k != "ticket_hash"})
            kwargs["input_text"] = json.dumps(wire)
            result = run_cancellable_subprocess(command, **kwargs)
            received.append(json.loads(result.stdout))
            return result
        with self.assertRaises(BudgetHold):
            client.post_json(f"http://127.0.0.1:{fixture.server.server_port}/v1/chat/completions", {}, PAYLOAD,
                worker_file=ROOT / "src/gurumoji/ai_http_worker.py", run_subprocess=corrupt_and_run,
                request_budget=budget, task_id="task", attempt_id="invalid-profile", timeout=240, retry_delays=())
        self.assertEqual(fixture.received, [])
        self.assertEqual(received[0]["kind"], "guard")
        self.assertIs(received[0]["budget_receipt"]["sent"], False)
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)
        self.assertEqual(budget.ledger()["unknown_usage_entries"], 1)


if __name__ == "__main__":
    unittest.main()
