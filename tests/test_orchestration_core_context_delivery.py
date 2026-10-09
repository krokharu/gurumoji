"""Synthetic delivery projections; saved ledgers and model authority stay intact."""
import copy
import itertools
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError, canonical, fingerprint
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.services.analysis_orchestration_adapters import ADAPTER_VERSION, make_orchestration_adapters
import test_analysis_orchestration as support
import test_orchestration_result_delivery_scope as delivery_support


def decode_index(index):
    if isinstance(index, list):
        return index
    return [dict(zip(index["columns"], row)) for row in index["rows"]]


class CoreHistoryDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.h = delivery_support.ResultDeliveryScopeTests(methodName="runTest")
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)

    def produce_core(self, *, adopt=True, summary="Synthetic Core judgment"):
        h = self.h
        h.response = support.core(summary=summary, alternatives=["Alternative remains open"], unresolved=["Human review"])
        task = h.register("core")
        h.service._execute(h.run["run_id"], task["task_id"])
        with h.service._db() as db:
            current = h.service._read_run(db, h.run["run_id"])
            source = next(row for row in h.service._tasks(db, h.run["run_id"]) if row["task_id"] == task["task_id"])
            self.assertEqual(source["status"], "succeeded", source)
            if adopt:
                row = db.execute("SELECT * FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
                h.service._apply_core(db, current, source, row)
                h.service._write_run(db, current)
        return source

    def mutate_decision(self, task, **changes):
        with self.h.service._db() as db:
            row = db.execute("SELECT payload_json FROM orchestration_decisions WHERE result_id=?", (task["result_id"],)).fetchone()
            decision = {**json.loads(row[0]), **changes}
            db.execute("UPDATE orchestration_decisions SET payload_json=? WHERE result_id=?",
                       (canonical(decision).decode(), task["result_id"]))

    def assert_reference(self, row, task):
        original = self.h.saved(task["result_id"])
        self.assertEqual(row, {"result_id": task["result_id"], "raw_hash": original["raw_hash"], "body_not_delivered": True})

    def test_real_adopted_history_is_reference_only_for_normal_core_and_critic(self):
        prior = self.produce_core()
        expert = self.h.produce("Expert report body remains visible")
        for role in ("core", "critic"):
            with self.subTest(role=role):
                context = self.h.context(self.h.register(role))
                self.assert_reference(context["results"][0], prior)
                self.assertEqual(context["results"][1]["task_id"], expert["task_id"])
                self.assertEqual(context["results"][1]["content"]["summary"], "Expert report body remains visible")
                self.assertEqual(context["result_delivery"]["core_history"], "verified_committed_decision_references")
                self.assertFalse(context["result_delivery"]["reference_is_body_read"])
                self.assertEqual(context["current_view"]["summary"], "Synthetic Core judgment")
                for field in ("view_version", "stop_proposal", "issues", "critique_responses", "labels"):
                    self.assertIn(field, context)
                if role == "critic":
                    self.assertEqual(context["review_target"]["view"], context["current_view"])

    def test_missing_decision_or_caller_adoption_flags_cannot_create_reference(self):
        prior = self.produce_core(adopt=False)
        self.h.mutate_result(prior, adopted=True, decision_id="caller-flag")
        context = self.h.context(self.h.register("core"))
        self.assertEqual(context["results"][0]["content"], self.h.saved(prior["result_id"])["raw"])
        self.assertNotIn("body_not_delivered", context["results"][0])

    def test_explicit_dependencies_and_clarification_keep_existing_body_metadata(self):
        prior = self.produce_core()
        original = self.h.saved(prior["result_id"])
        expected = {**{key: value for key, value in original.items() if key != "raw"}, "content": original["raw"]}
        for role, extra in (("core", {"dependencies": [prior["task_id"]]}),
                            ("critic", {"dependencies": [prior["task_id"]]}),
                            ("critic", {"kind": "clarification", "result_id": prior["result_id"]}),
                            ("interpretation", {"kind": "clarification", "result_id": prior["result_id"]}),
                            ("interpretation", {"dependencies": [prior["task_id"]]})):
            with self.subTest(role=role, extra=extra):
                context = self.h.context(self.h.register(role, **extra))
                self.assertEqual(context["results"], [expected])
                if extra.get("kind") == "clarification":
                    self.assertEqual(context["clarification_target"]["content"], original["raw"])
                    self.assertNotIn("result_delivery", context)

    def test_explicit_core_dependency_survives_existing_twenty_result_window(self):
        prior = self.produce_core()
        for index in range(22):
            self.h.produce(f"Independent report {index}")
        context = self.h.context(self.h.register("core", dependencies=[prior["task_id"]]))
        self.assertEqual(len(context["results"]), 21)
        self.assertEqual(context["results"][0]["task_id"], prior["task_id"])
        self.assertIn("content", context["results"][0])

    def test_large_raw_is_validated_before_reference_and_legacy_bound_is_unchanged(self):
        prior = self.produce_core(summary="Synthetic long Core history " * 800)
        context = self.h.context(self.h.register("core"))
        self.assert_reference(context["results"][0], prior)
        dependency = self.h.context(self.h.register("core", dependencies=[prior["task_id"]]))
        self.assertTrue(dependency["results"][0]["content"]["omitted_full_result"])
        self.assertEqual(dependency["results"][0]["content"]["summary"], self.h.saved(prior["result_id"])["raw"]["summary"])
        raw = self.h.saved(prior["result_id"])["raw"]
        raw["unresolved"].append("Tampered tail beyond bounded delivery")
        with self.h.service._db() as db:
            db.execute("UPDATE orchestration_results SET raw_json=? WHERE result_id=?", (canonical(raw).decode(), prior["result_id"]))
        with self.assertRaises(AnalysisContractError) as caught:
            self.h.context(self.h.register("core"))
        self.assertEqual(caught.exception.code, "result_integrity_mismatch")

    def test_core_result_provenance_mutations_fail_closed_without_writes(self):
        prior = self.produce_core()
        task = self.h.register("core")
        original = self.h.saved(prior["result_id"])
        mutations = ({"raw_hash": "sha256:changed"}, {"run_id": "foreign"}, {"dataset_version": "old"},
                     {"attempt_id": "different"}, {"attempt_id": None}, {"stale": True},
                     {"validation_status": "quarantined"}, {"task_id": "unknown"},
                     {"annotation_version": 5}, {"annotation_version": False})
        for change in mutations:
            with self.subTest(change=change):
                metadata = {key: value for key, value in original.items() if key != "raw"}
                self.h.mutate_result(prior, **metadata)
                self.h.mutate_result(prior, **change)
                before = self.h.path.read_bytes()
                with self.assertRaises(AnalysisContractError) as caught:
                    self.h.context(task)
                self.assertEqual(caught.exception.code, "result_integrity_mismatch")
                self.assertEqual(self.h.path.read_bytes(), before)

    def test_source_task_and_committed_decision_mismatches_fail_closed(self):
        prior = self.produce_core()
        consumer = self.h.register("critic")
        for field, value in (("run_id", "foreign"), ("dataset_version", "old"), ("attempt_id", "wrong"),
                             ("attempt_id", None), ("stale", True), ("status", "queued")):
            with self.subTest(source_field=field):
                self.h.mutate_task(prior, **{field: value})
                with self.assertRaises(AnalysisContractError):
                    self.h.context(consumer)
                self.h.mutate_task(prior, **{field: prior[field]})
        with self.h.service._db() as db:
            original = json.loads(db.execute("SELECT payload_json FROM orchestration_decisions WHERE result_id=?", (prior["result_id"],)).fetchone()[0])
        for change in ({"task_id": "other"}, {"result_id": "other"}, {"summary": "Modified adopted text"},
                       {"intents": [support.intent("verification")]}, {"iteration": 999}, {"view_version": -1}):
            with self.subTest(decision=change):
                self.mutate_decision(prior, **change)
                with self.assertRaises(AnalysisContractError):
                    self.h.context(consumer)
                self.mutate_decision(prior, **original)
        with self.h.service._db() as db:
            db.execute("UPDATE orchestration_decisions SET run_id=? WHERE result_id=?", ("foreign", prior["result_id"]))
        with self.assertRaises(AnalysisContractError):
            self.h.context(consumer)

    def test_rehashed_raw_does_not_match_original_committed_decision(self):
        prior = self.produce_core()
        raw = self.h.saved(prior["result_id"])["raw"]
        raw["summary"] = "Changed raw with a matching new raw hash"
        self.h.mutate_result(prior, raw_hash=fingerprint(raw))
        with self.h.service._db() as db:
            db.execute("UPDATE orchestration_results SET raw_json=? WHERE result_id=?", (canonical(raw).decode(), prior["result_id"]))
        with self.assertRaises(AnalysisContractError):
            self.h.context(self.h.register("core"))

    def test_ordinary_expert_omits_unrelated_metadata_but_preserves_dependency_guards(self):
        needed = self.h.produce("Required body")
        self.h.produce("Unrelated body")
        task = self.h.register(dependencies=[needed["task_id"]])
        context = self.h.context(task)
        self.assertEqual([row["task_id"] for row in context["results"]], [needed["task_id"]])
        self.assertEqual(context["result_delivery"]["unrelated_results_not_delivered"], 1)
        self.assertEqual(context["result_delivery"]["unrelated_result_metadata"], "not_delivered")
        self.assertFalse(context["result_delivery"]["omission_is_body_read"])
        self.assertEqual(self.h.context(self.h.register())["results"], [])
        self.assertEqual(self.h.context(self.h.register(kind=""))["results"], [])
        self.h.mutate_result(needed, raw_hash="sha256:bad")
        with self.assertRaises(AnalysisContractError):
            self.h.context(task)
        malformed = copy.deepcopy(task); malformed["dependencies"] = {needed["task_id"]: False}
        with self.assertRaises(AnalysisContractError) as caught:
            self.h.context(malformed)
        self.assertEqual(caught.exception.code, "dependency_missing")

    def test_core_dependency_shape_and_unknown_attempts_cannot_hide_history(self):
        prior = self.produce_core()
        task = self.h.register("core")
        for value in (None, {prior["task_id"]: False}, [None], [""]):
            with self.subTest(dependencies=value):
                task["dependencies"] = value
                with self.assertRaises(AnalysisContractError) as caught:
                    self.h.context(task)
                self.assertEqual(caught.exception.code, "dependency_missing")
        task["dependencies"] = []
        self.h.mutate_task(prior, attempt_id=None)
        self.h.mutate_result(prior, attempt_id=None)
        with self.assertRaises(AnalysisContractError) as caught:
            self.h.context(task)
        self.assertEqual(caught.exception.code, "result_integrity_mismatch")

    def test_unrelated_invalid_raw_is_not_read_or_promoted(self):
        prior = self.h.produce()
        task = self.h.register()
        with self.h.service._db() as db:
            db.execute("UPDATE orchestration_results SET raw_json=? WHERE result_id=?", ("invalid-json", prior["result_id"]))
        before = self.h.path.read_bytes()
        with self.h.service._db() as db:
            statements = []
            db.set_trace_callback(statements.append)
            context = self.h.service._context(db, self.h.service._read_run(db, self.h.run["run_id"]), task)
        self.assertEqual(context["results"], [])
        self.assertEqual(context["result_delivery"]["unrelated_results_not_delivered"], 1)
        self.assertFalse(any("select raw_json" in sql.lower() for sql in statements))
        self.assertEqual(self.h.path.read_bytes(), before)

    def test_projections_are_read_only_and_fresh_saved_ledger_stays_exact(self):
        self.produce_core()
        consumers = [self.h.register(role) for role in ("core", "critic", "interpretation")]
        before = self.h.saved()
        database = self.h.path.read_bytes()
        for task in consumers:
            with self.h.service._db() as db:
                self.assertTrue(db.in_transaction)
                statements = []
                db.set_trace_callback(statements.append)
                context = self.h.service._context(db, self.h.service._read_run(db, self.h.run["run_id"]), task)
                self.assertFalse(any(sql.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"} for sql in statements))
                context["results"].clear()
        self.assertEqual(self.h.saved(service=self.h.make_service()), before)
        self.assertEqual(self.h.path.read_bytes(), database)


class CoreWireProjectionTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.resolve, self.runner = make_orchestration_adapters(call_ai_json=lambda *args: self.calls.append(args) or support.core(),
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"))
        self.context = {"question": "Same instruction", "task": {"task_id": "task", "role": "core", "attempt_id": "attempt",
            "run_id": "run", "dataset_version": "input", "annotation_version": 0, "codebook_version": 1,
            "iteration": 3, "phase": "core", "dependencies": ["required-task"], "title": "Same instruction",
            "intent": {"question": "Same instruction", "why_now": "Meaningful reason", "kind": "analysis"},
            "created_at": "created", "started_at": None, "ended_at": None, "idempotency_key": "identity-hash",
            "status": "queued", "error": "", "provider": "lmstudio", "model": "synthetic"},
            "raw_evidence": [{"evidence_id": "e0", "utterance_id": "u0", "text": "Synthetic"}],
            "coverage": {"available_count": 323, "provided_count": 1, "omitted_count": 322, "complete": False,
                "index_available_count": 323, "index_provided_count": 323, "index_omitted_count": 0,
                "evidence_index": [{"evidence_id": f"e{i}", "utterance_id": f"u{i}"} for i in range(323)]}}

    def wire(self, role, context=None):
        self.runner(role, context or self.context, self.resolve({}), lambda: None, lambda _: None)
        return json.loads(self.calls[-1][4])

    def test_all_index_ids_order_counts_and_raw_bindings_round_trip_once(self):
        original = copy.deepcopy(self.context)
        expected = [{"evidence_id": f"e{i}"} for i in range(323)]
        for role in ("core", "critic"):
            with self.subTest(role=role):
                wire = self.wire(role)
                self.assertEqual(decode_index(wire["coverage"]["evidence_index"]), expected)
                self.assertEqual(wire["coverage"]["evidence_index"]["columns"], ["evidence_id"])
                for key, value in original["coverage"].items():
                    if key != "evidence_index": self.assertEqual(wire["coverage"][key], value)
                self.assertEqual(wire["raw_evidence"], original["raw_evidence"])
                twice = self.wire(role, wire)
                self.assertEqual(twice["coverage"], wire["coverage"])
                self.assertIn("columns_rows_v1", wire["coverage"]["evidence_index_format"])
        self.assertEqual(self.context, original)

    def test_task_identity_intent_and_exact_question_references_only(self):
        original = copy.deepcopy(self.context)
        wire = self.wire("core")
        for key in ("task_id", "role", "attempt_id", "run_id", "dataset_version", "annotation_version",
                    "codebook_version", "iteration", "phase", "dependencies"):
            self.assertEqual(wire["task"][key], original["task"][key])
        self.assertEqual(wire["task"]["intent"]["why_now"], "Meaningful reason")
        self.assertEqual(wire["task"]["title"], {"ref": "question"})
        self.assertEqual(wire["task"]["intent"]["question"], {"ref": "question"})
        self.assertEqual(wire["task_delivery"]["question_references"], ["task.title", "task.intent.question"])
        removed = set(original["task"]) - set(wire["task"])
        self.assertEqual(set(wire["task_delivery"]["diagnostic_fields_not_delivered"]), removed)
        self.assertTrue(wire["task_delivery"]["full_task_preserved"])
        for title, question in (("Different title", "Different intent"), ("Same instruction ", "same instruction"),
                                ("Same instruction", "Different intent"), ("Different title", "Same instruction")):
            with self.subTest(title=title, question=question):
                self.context["task"]["title"] = title
                self.context["task"]["intent"]["question"] = question
                wire = self.wire("critic")
                self.assertEqual(wire["task"]["title"], {"ref": "question"} if title == original["question"] else title)
                self.assertEqual(wire["task"]["intent"]["question"], {"ref": "question"} if question == original["question"] else question)

    def test_clarification_verification_and_nonstat_expert_wire_types_are_unchanged(self):
        for role, kind in (("critic", "clarification"), ("interpretation", "analysis"), ("verification", "analysis")):
            with self.subTest(role=role, kind=kind):
                self.context["task"]["intent"]["kind"] = kind
                wire = self.wire(role)
                self.assertEqual(wire["coverage"]["evidence_index"], [{"evidence_id": f"e{i}"} for i in range(323)])
                self.assertEqual(wire["task"], self.context["task"])
                self.assertNotIn("task_delivery", wire)

    def test_statistical_plan_calculation_explanation_and_bindings_keep_existing_delivery(self):
        # Reuse the already accepted real Handler/statistical fixture, without
        # inheriting or rediscovering its unrelated test methods.
        test = delivery_support.RegisteredExpertDeliveryTests(
            "test_statistical_plan_calculation_explanation_and_cell_binding_are_unchanged")
        self.addCleanup(test.doCleanups)
        test.test_statistical_plan_calculation_explanation_and_cell_binding_are_unchanged()

    def test_core_routes_formal_statistical_dependencies_with_history_references(self):
        import test_statistical_expert_agents as statistical_support
        h = statistical_support.StatisticalExpertTests(methodName="runTest")
        h.setUp(); self.addCleanup(h.doCleanups)
        core_contexts = []
        def agent(role, context, *args):
            if role != "core":
                return h.agent(role, context, *args)
            core_contexts.append(copy.deepcopy(context))
            reports = [row for row in context["results"] if row.get("role") == "interpretation"]
            calculations = [row for row in context["results"] if row.get("role") == "statistics"]
            if not reports:
                return support.core(intents=[support.intent("interpretation", expert_id="exp-correlation")])
            if not calculations:
                return support.core(intents=reports[-1]["content"]["analysis_requests"])
            if len(reports) == 1:
                return support.core(intents=[support.intent("interpretation", expert_id="exp-correlation",
                    question="Explain the formal calculation", dependencies=[calculations[0]["task_id"]])])
            return support.stop()
        h.service.agent_runner = agent
        run = h.start(obsidian_management=False)
        h.service.run(run["run_id"])
        saved = h.service.result("synthetic", run["run_id"])
        self.assertEqual((saved["run"]["status"], saved["run"]["stop_reason"]), ("stopped", "human_review_required"))
        self.assertEqual(len([task for task in saved["run"]["tasks"] if task["role"] == "statistics"]), 1)
        self.assertTrue(any(row.get("body_not_delivered") for context in core_contexts for row in context["results"]))
        explanation = next(task for task in saved["run"]["tasks"] if task.get("expert_response_phase") == "result_explanation")
        self.assertEqual(len(explanation["expert_calculation_refs"]), 1)
        self.assertEqual(explanation["statistical_review_status"], "human_pending")


class SyntheticNineScopeCycleTests(unittest.TestCase):
    """Actual service -> expert hooks -> stop review -> fixed Store -> fresh read."""

    def run_cycle(self, adapter_factory=make_orchestration_adapters, context_method=None):
        import app
        import test_content_analysis as content_support
        from gurumoji.analysis_store import AnalysisStore
        from gurumoji.method_experts import ExpertCatalog
        from gurumoji.services.expert_agents import ExpertAgentRegistry
        from gurumoji.services.analysis_orchestration_publication import AnalysisOrchestrationPublicationService
        from test_expert_data_hooks import request
        fixture = content_support.ContentApiTests(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        guards = [patch("socket.socket.connect", side_effect=AssertionError("No network")),
                  patch.object(AnalysisStore, "_publish_generated_vaults", side_effect=AssertionError("No Vault publication")),
                  patch.object(AnalysisStore, "_publish_research", side_effect=AssertionError("No Vault publication"))]
        for guard in guards:
            guard.start(); self.addCleanup(guard.stop)
        registry = ExpertAgentRegistry(ExpertCatalog(root=Path(__file__).resolve().parents[1] / "docs/program-vault",
            local_root=Path(fixture.temp.name) / "synthetic-local-knowledge"))
        segments = [{"id": f"u{i}", "text": f"Synthetic scope utterance {i}", "speaker": f"S{i % 3}",
                     "annotation": {"codes": ["synthetic"]}, "excluded": False} for i in range(323)]
        snapshot = {"input_hash": "synthetic-323-v1", "source_revision": 0, "analysis_revision": 1,
            "analysis": {"segments": segments, "automatic": {"overview": {"included_segment_count": 323, "speaker_count": 3}},
                         "all_results": {"preserved_missing": None, "preserved_zero": 0}}}
        wires, replies, rounds = [], [], {}
        def transport(*args, **kwargs):
            context = json.loads(args[4]); role = args[5].removeprefix("analysis_orchestration_")
            wires.append((role, copy.deepcopy(context)))
            args[7](); args[8]({"reported": False})
            if role == "core":
                iteration = context["task"]["iteration"]
                ids = [row["evidence_id"] for row in decode_index(context["coverage"]["evidence_index"])]
                if iteration <= 3:
                    raw = support.core(summary="Synthetic integrated view", intents=[support.intent("interpretation",
                        kind="analysis", expert_id="exp-thematic-analysis", question=f"Synthetic independent scope {scope}",
                        evidence_ids=ids[scope * 36:(scope + 1) * 36]) for scope in range((iteration - 1) * 3, iteration * 3)])
                else:
                    responses = [{"issue_id": row["issue_id"], "disposition": "defer", "reason": "Human interpretation remains pending",
                                  "impact": "Keep the observation bounded"} for row in context["issues"]]
                    raw = support.stop(summary="Synthetic integrated view", claims=[{"claim_id": "synthetic-observation",
                        "text": "Synthetic evidence only", "kind": "observation", "evidence_ids": [ids[0]]}],
                        critique_responses=responses)
            elif role == "interpretation":
                task_id = context["task"]["task_id"]
                rounds[task_id] = rounds.get(task_id, 0) + 1
                if rounds[task_id] == 1:
                    provided = {row["evidence_id"] for row in context["raw_evidence"]}
                    remaining = [row["evidence_id"] for row in context["expert_hooks"]["evidence_index"] if row["evidence_id"] not in provided]
                    return {"expert_response": {"mode": "read", "hook_requests": [request(ids=remaining[i:i + 8]) for i in range(0, len(remaining), 8)]}}
                packet = context["expert_request"]; profile = packet["knowledge"]
                raw = {"summary": "Synthetic independent expert draft", "claims": [], "analysis_requests": [], "label_patches": [],
                    "expert_report": {"expert_id": packet["expert_id"], "profile_hash": packet["profile_hash"],
                        "knowledge_hash": packet["knowledge_hash"], "status": "draft",
                        "outputs": {field["id"]: "Synthetic bounded draft; human interpretation remains pending" for field in profile["output_fields"]},
                        "evidence_ids": [row["evidence_id"] for row in context["raw_evidence"]],
                        "knowledge_note_ids": [profile["knowledge"][0]["note_id"]],
                        "performed_step_ids": [profile["allowed_steps"][0]["id"]], "missing_inputs": [],
                        "limitations": "Synthetic input only; human decisions unverified"}}
            elif role == "critic":
                target = context["review_target"]
                raw = support.critic(context, [{"issue_key": "synthetic-human-review", "target_id": target["target_id"],
                    "target_version": target["target_version"], "severity": "low", "reason": "Human interpretation pending",
                    "evidence_ids": [context["raw_evidence"][0]["evidence_id"]], "missing_evidence": "Human review",
                    "alternative": "Bounded alternative", "proposed_test": "Researcher review"}])
            else:
                raw = {"summary": "Synthetic blind verification", "claims": []}
            replies.append((role, copy.deepcopy(raw)))
            return {"expert_response": {"mode": "report", "result": raw}} if "expert_response" in args[6]["properties"] else raw
        _, runner = adapter_factory(call_ai_json=transport,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"))
        service = AnalysisOrchestrationService(connect=app.database_connection, find_item=app.library_row,
            snapshot_builder=lambda _: copy.deepcopy(snapshot), source_fingerprint=lambda _: snapshot["input_hash"],
            agent_runner=runner, method_runner=lambda *_: self.fail("No statistical dispatch in this cycle"),
            expert_provider=registry.freeze, adapter_version=ADAPTER_VERSION, schedule=False)
        if context_method is not None:
            service._context = context_method.__get__(service)
        serial = itertools.count(1)
        with patch("gurumoji.analysis_orchestration._id", side_effect=lambda prefix: f"{prefix}_{next(serial):06d}"), \
             patch("gurumoji.analysis_orchestration._now", return_value="2026-01-01T00:00:00+00:00"), \
             patch("gurumoji.analysis_orchestration.time.time", return_value=1767225600.0):
            run = service.start("content", {"request_id": "synthetic-nine-scope", "model": "synthetic", "question": "Synthetic full index inquiry",
                "adapter_version": ADAPTER_VERSION, "expert_ids": ["exp-thematic-analysis"], "expert_hooks": True,
                "expert_inputs": {"exp-thematic-analysis": {"analysis_premises": None}},
                "concurrency": 1, "context_evidence_limit": 120, "context_index_limit": 0,
                "context_evidence_limits_by_role": {"core": 12, "critic": 12, "verification": 12, "interpretation": 120},
                "max_calls": 80, "max_tasks": 100, "time_limit_seconds": None, "obsidian_management": False,
                "publication_targets": []})
            service.run(run["run_id"])
        saved = service.result("content", run["run_id"])
        self.assertEqual(saved["run"]["status"], "completed", saved["run"])
        self.assertTrue(all(task["status"] == "succeeded" for task in saved["run"]["tasks"]))
        self.assertEqual(len(rounds), 9)
        self.assertEqual(set(rounds.values()), {2})
        self.assertEqual(len([task for task in saved["run"]["tasks"] if task["role"] == "verification"]), 1)
        self.assertEqual(len(saved["decisions"]), 5)
        self.assertTrue(saved["decisions"][-1]["critique_responses"])
        self.assertEqual([(row["role"], row["raw"]) for row in saved["raw_results"]], replies)
        with service._db() as db:
            rows_before = {table: [tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                           for table in ("orchestration_results", "orchestration_tasks", "orchestration_decisions", "orchestration_label_versions")}
            # Delivery and fresh getters do not alter a single saved byte.
            final_task = next(task for task in reversed(saved["run"]["tasks"]) if task["role"] == "core")
            service._context(db, service._read_run(db, run["run_id"]), final_task)
        fresh_service = AnalysisOrchestrationService(connect=app.database_connection, find_item=app.library_row,
            snapshot_builder=lambda *_: self.fail("No rebuild"), source_fingerprint=lambda _: snapshot["input_hash"],
            agent_runner=lambda *_: self.fail("No fresh model"), method_runner=lambda *_: self.fail("No fresh method"), schedule=False)
        self.assertEqual(fresh_service.result("content", run["run_id"]), saved)
        store = app.analysis_archive_store()
        publisher = AnalysisOrchestrationPublicationService(connect=app.database_connection, store_factory=lambda: store,
            source_guard=lambda db, item, expected: {"id": item}, export_locked=service.result_locked)
        publication = publisher.finalize("content", run["run_id"])
        self.assertEqual(publication["save_status"], "saved", publication)
        artifact = next(row for row in publication["result_run"]["artifacts"] if row["name"] == "result.json")
        fresh_store = AnalysisStore(store.database_file, store.connect)
        _, package_bytes = fresh_store.read_artifact(artifact["id"])
        self.assertEqual(package_bytes, store.read_artifact(artifact["id"])[1])
        self.assertEqual(json.loads(package_bytes)["orchestration"]["raw_results"], saved["raw_results"])
        self.assertEqual(json.loads(package_bytes)["orchestration"]["run"]["tasks"], saved["run"]["tasks"])
        with service._db() as db:
            rows_after = {table: [tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")] for table in rows_before}
        self.assertEqual(rows_after, rows_before)
        return {"wires": wires, "saved": saved, "ledger_rows": rows_after, "package_bytes": package_bytes}

    def test_323_ids_nine_scopes_hooks_stop_review_store_and_fresh_bytes(self):
        outcome = self.run_cycle()
        saved = outcome["saved"]
        expected = [{"evidence_id": row["evidence_id"]} for row in saved["initial"]["snapshot"]["evidence"]]
        delivered = []
        for role, context in outcome["wires"]:
            if role in {"core", "critic"}:
                self.assertEqual(decode_index(context["coverage"]["evidence_index"]), expected)
                self.assertEqual(context["coverage"]["index_provided_count"], 323)
                self.assertEqual(context["coverage"]["index_omitted_count"], 0)
                self.assertIn("task_delivery", context)
                self.assertNotIn("idempotency_key", context["task"])
                for row in context["results"]:
                    if row.get("body_not_delivered"):
                        self.assertEqual(set(row), {"result_id", "raw_hash", "body_not_delivered"})
            elif role == "interpretation":
                self.assertEqual(context["results"], [])
                self.assertEqual(context["result_delivery"]["scope"], "explicit_dependencies_only")
                self.assertIsInstance(context["expert_hooks"]["evidence_index"], list)
                if context.get("expert_hook_results"):
                    delivered.extend(row["evidence_id"] for row in context["raw_evidence"])
            else:
                self.assertTrue(context["blind_first"])
                self.assertNotIn("results", context)
                self.assertNotIn("task_delivery", context)
        self.assertEqual(set(delivered), {row["evidence_id"] for row in expected})
        self.assertEqual(len(delivered), 323)
        self.assertEqual(len(saved["label_versions"][0]["labels"]), 323)


if __name__ == "__main__":
    unittest.main()
