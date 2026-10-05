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
from gurumoji.analysis_orchestration import AnalysisOrchestrationService, validate_orchestration_payload


def intent(role, question=None, **extra):
    return {"role": role, "question": question or "Check " + role, "why_now": "Resolve uncertainty",
            "success_criteria": "Report support and limitations", "importance": "high", "importance_reason": "May alter the finding", **extra}


def core(summary="Bounded finding", **extra):
    return {"summary": summary, "claims": [], "intents": [], "critique_responses": [], "label_decisions": [], **extra}


def stop(**extra):
    return core(stop={"reason": "question_satisfied", "summary": "Evidence-limited finding", "unresolved": []}, **extra)


def critic(context, issues=None):
    return {"summary": "Review", "claims": [], "review_status": "issues" if issues else "no_issues",
            "reviewed_scope": "Provided view and evidence", "limitations": "Exploratory",
            "issues": issues or []}


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
        self.agent = lambda role, context, options, check, usage: stop() if role == "core" else critic(context)
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

    def test_configured_context_limit_keeps_omissions_and_full_source_explicit(self):
        run = self.start(context_evidence_limit=1, context_text_limit=1000, context_index_limit=1)
        final = self.drive(run)
        context = next(context for role, context, _ in self.calls if role == "core")
        self.assertEqual(len(context["raw_evidence"]), 1)
        self.assertEqual(context["coverage"]["available_count"], 2)
        self.assertEqual(context["coverage"]["omitted_count"], 1)
        self.assertFalse(context["coverage"]["complete"])
        self.assertEqual(len(context["coverage"]["evidence_index"]), 1)
        self.assertEqual(context["coverage"]["index_available_count"], 2)
        self.assertEqual(context["coverage"]["index_omitted_count"], 1)
        with self.service._db() as db:
            initial = self.service._initial(db, run["initial_id"])
        self.assertEqual(len(initial["evidence"]), 2)
        self.assertEqual(final["config"]["context_evidence_limit"], 1)

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

    def test_context_limits_reject_boolean_zero_and_values_above_the_cap(self):
        for key, bad in (("context_evidence_limit", True), ("context_evidence_limit", 0),
                         ("context_evidence_limit", 121), ("context_text_limit", 60001),
                         ("context_index_limit", True), ("context_index_limit", -1), ("context_index_limit", 121)):
            with self.subTest(key=key, bad=bad), self.assertRaises(AnalysisContractError):
                self.start(**{key: bad})

    def test_empty_core_json_is_quarantined_instead_of_counted_as_success(self):
        for summary in ("", "  "):
            with self.subTest(summary=summary):
                self.agent = lambda *_: core(summary=summary)
                run = self.start(request_id="empty-core-" + str(len(summary)))
                final = self.drive(run)
                self.assertNotEqual(final["status"], "completed")
                self.assertEqual(final["tasks"][0]["status"], "quarantined")
                self.assertEqual(final["tasks"][0]["error"], "invalid_result")

    def test_label_frequency_on_interpretation_is_quarantined_before_registration(self):
        self.agent = lambda *_: core(intents=[{"role": "interpretation", "method_id": "label_frequency",
            "question": "Check labels", "why_now": "Check evidence", "success_criteria": "Return evidence"}])
        final = self.drive(self.start())
        self.assertEqual(final["tasks"][0]["status"], "quarantined")
        self.assertEqual(final["tasks"][0]["error"], "label_field_unavailable")
        self.assertEqual(len(final["tasks"]), 1)

    def test_complete_real_loop_and_pre_stop_review(self):
        run = self.drive(self.start())
        self.assertEqual(run["status"], "completed", run)
        self.assertEqual([r for r, _, _ in self.calls], ["core", "critic", "core", "core"])
        self.assertEqual(run["iteration"], 3)
        self.assertEqual(run["config"]["min_iterations"], 3)
        self.assertEqual([ctx["budget"]["completed_core_iterations"] for role, ctx, _ in self.calls if role == "core"], [0, 1, 2])
        context = next(context for role, context, _ in self.calls if role == "core")
        self.assertEqual(context["coverage"]["index_omitted_count"], 0)
        self.assertEqual(context["coverage"]["index_provided_count"], 2)
        self.assertEqual(run["usage"]["calls"], 4)
        self.assertIsNone(run["usage"]["input_tokens"])
        self.assertTrue(all(r["validation_status"] == "valid" for r in run["results"]))
        self.assertEqual(run["review_status"], "reviewed")

    def test_default_mode_and_minimum_cannot_be_silently_lowered(self):
        config = validate_orchestration_payload({"model": "synthetic-model", "min_iterations": 0})
        self.assertEqual(config["stop_mode"], "auto")
        self.assertEqual(config["min_iterations"], 3)
        self.assertIsNone(config["max_iterations"])
        self.assertIsNone(config["time_limit_seconds"])
        for upper in (1, 2):
            with self.subTest(upper=upper), self.assertRaises(AnalysisContractError):
                self.start(max_iterations=upper)

    def test_empty_worklist_is_reexamined_three_times_without_fabricating_completion(self):
        self.agent = lambda *_: core()
        run = self.drive(self.start())
        self.assertEqual(run["iteration"], 3)
        self.assertEqual(run["status"], "stopped")
        self.assertEqual(run["stop_reason"], "no_new_tasks")
        self.assertEqual(sum(t["role"] == "core" and t["status"] == "succeeded" for t in run["tasks"]), 3)

    def test_agent_can_continue_beyond_three_then_choose_stop(self):
        def agent(role, context, *_):
            if role == "core" and context["budget"]["iteration"] <= 3:
                return core(intents=[intent("interpretation", question=f"Examine round {context['budget']['iteration']}")])
            return stop() if role == "core" else critic(context)
        self.agent = agent
        run = self.drive(self.start())
        self.assertEqual(run["status"], "completed", run)
        self.assertEqual(run["iteration"], 5)
        self.assertEqual(sum(role == "interpretation" for role, _, _ in self.calls), 3)

    def test_three_round_cap_allows_reviewed_agent_stop_on_third(self):
        final = self.drive(self.start(max_iterations=3))
        self.assertEqual(final["iteration"], 3)
        self.assertEqual(final["status"], "completed")
        self.assertEqual(final["stop_reason"], "question_satisfied")

    def test_invalid_third_result_interrupts_minimum_without_retry_or_success(self):
        self.agent = lambda role, ctx, *_: (
            core(summary="") if ctx["budget"]["iteration"] == 3 else stop()
        ) if role == "core" else critic(ctx)
        final = self.drive(self.start())
        self.assertEqual(final["stop_reason"], "execution_failure")
        self.assertNotEqual(final["status"], "completed")
        self.assertEqual(sum(t["role"] == "core" and t["status"] == "succeeded" for t in final["tasks"]), 2)
        self.assertEqual(sum(role == "core" for role, _, _ in self.calls), 3)

    def test_legacy_run_without_minimum_keeps_recorded_stop_policy(self):
        run = self.start()
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            state["config"].pop("min_iterations")
            self.service._write_run(db, state)
        final = self.drive(run)
        self.assertEqual(final["iteration"], 2)
        self.assertEqual(final["status"], "completed")

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
        newer = self.start(template_config={"different": True})
        self.assertNotEqual(newer["initial_id"], run["initial_id"])
        self.assertEqual(self.build_count, 2)
        with self.assertRaises(AnalysisContractError):
            self.start(request_id="same", question="Different")

    def test_parallel_specialists_handler_only_blind_verification_and_real_code(self):
        def agent(role, context, options, check, usage):
            if role == "core":
                if context["budget"]["iteration"] == 1:
                    return core(intents=[intent("interpretation"), intent("verification", question="SECRET_EXPECTED_CONCLUSION"),
                                         intent("statistics", method_id="participation")])
                return stop()
            if role == "critic":
                return critic(context)
            return {"summary": "Independent", "claims": []}
        self.agent = agent
        run = self.drive(self.start())
        self.assertEqual(run["status"], "completed", run)
        blind = next(ctx for role, ctx, _ in self.calls if role == "verification")
        self.assertNotIn("SECRET_EXPECTED_CONCLUSION", json.dumps(blind))
        self.assertNotIn("initial", blind)
        self.assertNotIn("current_view", blind)
        self.assertNotIn("issues", blind)
        self.assertEqual(blind["raw_evidence"][0]["utterance_id"], "u1")
        stats = next(t for t in run["tasks"] if t["role"] == "statistics")
        self.assertEqual(stats["kind"], "code")
        self.assertFalse(stats["label_dependent"])
        self.assertEqual(run["usage"]["code_executions"], 1)
        self.assertEqual(len(self.methods), 1)
        self.assertIn("analysis", self.methods[0][1])

    def test_duplicate_intents_execute_only_once(self):
        self.agent = lambda role, context, *_: core(intents=[intent("interpretation"), intent("interpretation")]) if role == "core" else {"summary": "Result"}
        run = self.drive(self.start())
        self.assertEqual(sum(role == "interpretation" for role, _, _ in self.calls), 1)
        self.assertEqual(run["stop_reason"], "no_new_tasks")
        self.assertTrue(any(e["type"] == "duplicate_suppressed" for e in run["events"]))

    def test_unsupported_confirmatory_and_cloud_without_consent(self):
        for payload in ({"research_mode": "confirmatory"}, {"research_protocol": "confirmatory"},
                        {"provider": "openai", "provider_policy": "cloud_allowed"}):
            with self.assertRaises(AnalysisContractError):
                self.start(**payload)
        self.assertEqual(self.build_count, 0)

    def test_iteration_cap_does_not_hide_extra_review_round(self):
        run = self.drive(self.start(stop_mode="iterations", max_iterations=1))
        self.assertEqual([r for r, _, _ in self.calls], ["core"])
        self.assertEqual(run["stop_reason"], "iteration_limit")
        self.assertEqual(run["status"], "stopped")
        self.assertEqual(run["review_status"], "incomplete")

    def test_time_limit_before_dispatch(self):
        run = self.start(stop_mode="time", time_limit_seconds=1)
        with contextlib.closing(self.connect()) as db, db:
            state = json.loads(db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (run["run_id"],)).fetchone()[0])
            state.update(started_at="old", deadline=time.time() - 1)
            db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (json.dumps(state), run["run_id"]))
        run = self.drive(run)
        self.assertEqual(run["stop_reason"], "time_limit")
        self.assertFalse(self.calls)

    def test_importance_threshold_stops_low_value_tasks(self):
        self.agent = lambda *_: core(intents=[intent("interpretation", importance="low")])
        run = self.drive(self.start(stop_mode="importance", importance_threshold="high"))
        self.assertEqual(run["stop_reason"], "importance_threshold")
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(any(e["type"] == "intent_deferred" for e in run["events"]))

    def test_operational_call_and_task_budgets(self):
        run = self.drive(self.start(max_calls=1))
        self.assertEqual(run["stop_reason"], "call_budget_limit")
        self.assertEqual(run["usage"]["calls"], 1)
        other = self.drive(self.start(max_tasks=1))
        self.assertEqual(other["stop_reason"], "task_budget_limit")

    def test_raw_invalid_evidence_saved_then_quarantined(self):
        self.agent = lambda *_: core(claims=[{"claim_id": "madeup", "text": "Unsupported", "kind": "observation", "evidence_ids": ["nonexistent"]}])
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "execution_failure")
        result = run["results"][0]
        self.assertEqual(result["validation_status"], "quarantined")
        received = self.service.result("conversation", run["run_id"], result["result_id"])
        self.assertEqual(received["raw"]["claims"][0]["evidence_ids"], ["nonexistent"])
        self.assertEqual(result["error"], "evidence_missing")

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

    def test_critique_response_reason_and_no_same_issue_loop(self):
        def agent(role, context, *_):
            if role == "core":
                answered = {r["issue_id"] for r in context["critique_responses"]}
                responses = [{"issue_id": issue["issue_id"], "disposition": "defer", "reason": "No additional data", "impact": "Keep conclusion exploratory"} for issue in context["issues"] if issue["issue_id"] not in answered]
                return stop(critique_responses=responses)
            target = context["review_target"]
            issue = {"issue_key": "alternative-explanation", "target_id": target["target_id"], "target_version": target["target_version"],
                     "severity": "high", "reason": "Alternative not eliminated", "evidence_ids": [], "missing_evidence": "Independent comparison data"}
            return critic(context, [issue, issue])
        self.agent = agent
        run = self.drive(self.start())
        self.assertEqual(run["status"], "completed", run)
        self.assertEqual(len(run["issues"]), 1)
        self.assertEqual(len(run["critique_responses"]), 1)
        self.assertEqual(run["unresolved_issues"][0]["status"], "defer")
        self.assertEqual(sum(role == "critic" for role, _, _ in self.calls), 1)

    def test_labels_conflict_and_immutable_manual_baseline(self):
        def agent(role, context, *_):
            if role == "core":
                if context["budget"]["iteration"] == 1:
                    return core(intents=[intent("interpretation", label_dependent=True)])
                decisions = [{"proposal_id": p["proposal_id"], "disposition": "adopt", "reason": "Evidence supports narrower code"} for p in context["label_proposals"]]
                return stop(label_decisions=decisions)
            if role == "critic":
                return critic(context)
            patch = {"utterance_id": "u1", "field": "codes", "old_value": ["manual"], "new_value": ["revised"], "reason": "Synthetic evidence", "evidence_ids": [context["raw_evidence"][0]["evidence_id"]], "base_annotation_version": 0, "codebook_version": 1}
            return {"summary": "Changes proposed", "label_patches": [patch, {**patch, "new_value": ["conflict"]}]}
        self.agent = agent
        run = self.drive(self.start())
        self.assertEqual(run["annotation_version"], 1, run)
        self.assertEqual([p["status"] for p in run["label_proposals"]], ["committed", "conflict"])
        artifact = self.service.result("conversation", run["run_id"])
        self.assertEqual(artifact["label_versions"][0]["labels"]["u1"]["codes"], ["manual"])
        self.assertEqual(artifact["label_versions"][1]["labels"]["u1"]["codes"], ["revised"])
        self.assertEqual(artifact["initial"]["snapshot"]["analysis"]["segments"][0]["annotation"]["codes"], ["manual"])
        self.assertTrue(next(t for t in run["tasks"] if t["role"] == "interpretation")["stale"])

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

    def test_major_claims_trigger_review_without_core_self_request(self):
        def agent(role, context, *_):
            evidence = context["raw_evidence"][0]["evidence_id"]
            claims = [{"claim_id": "claim1", "text": "Observed utterance", "kind": "observation", "evidence_ids": [evidence]}]
            if role == "core":
                if context["budget"]["iteration"] == 1:
                    return core(claims=claims)
                return stop(claims=claims)
            return critic(context) if role == "critic" else {"summary": "Independent observation", "claims": claims}
        self.agent = agent
        run = self.drive(self.start())
        self.assertEqual(run["status"], "completed", run)
        self.assertEqual(sum(role == "verification" for role, _, _ in self.calls), 1)
        self.assertTrue(any(t["role"] == "critic" and t["phase"] == "specialists" for t in run["tasks"]))

    def test_initial_clarification_is_bounded_read_only_and_filters_excluded(self):
        self.snapshot["analysis"]["segments"].append({"id": "excluded", "text": "DO NOT TRANSMIT", "excluded": True})
        self.snapshot["analysis"]["research"] = {"rows": [{"segment_id": "u1", "value": "allowed"},
            {"segment_id": "excluded", "value": "secret"}], "mapping": {"excluded": "hidden"}}
        run = self.start()
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            task = self.service._register(db, state, intent("interpretation", kind="clarification", result_id=run["initial_id"],
                initial_sections=["segments", "research"]), phase="specialists")
            context = self.service._context(db, state, task)
        encoded = json.dumps(context)
        self.assertNotIn("DO NOT TRANSMIT", encoded)
        self.assertNotIn('"secret"', encoded)
        self.assertNotIn('"hidden"', encoded)
        self.assertFalse(context["execution_allowed"])
        self.assertTrue(context["clarification_target"]["read_only"])
        self.assertEqual(len(context["clarification_target"]["sections"]["segments"]), 2)

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
        run = self.start(call_timeout_seconds=1)
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

    def test_label_frequency_uses_fixed_committed_annotation_and_stales_previous(self):
        def agent(role, context, *_):
            if role == "core":
                iteration = context["budget"]["iteration"]
                count = intent("statistics", method_id="label_frequency", label_field="codes")
                if iteration == 1:
                    return core(intents=[count, intent("interpretation")])
                if iteration == 2:
                    proposal = context["label_proposals"][0]
                    return core(intents=[count], label_decisions=[{"proposal_id": proposal["proposal_id"],
                        "disposition": "adopt", "reason": "Evidence-linked update"}])
                return stop()
            if role == "critic":
                return critic(context)
            return {"summary": "Label proposal", "label_patches": [{"utterance_id": "u1", "field": "codes",
                "old_value": ["manual"], "new_value": ["revised"], "reason": "Synthetic evidence",
                "evidence_ids": [context["raw_evidence"][0]["evidence_id"]], "base_annotation_version": 0, "codebook_version": 1}]}
        self.agent = agent
        run = self.drive(self.start())
        self.assertEqual(run["status"], "completed", run)
        snapshots = [value for method, value in self.methods if method == "label_frequency"]
        self.assertEqual(len(snapshots), 2)
        self.assertEqual([s["orchestration_task"]["annotation_version"] for s in snapshots], [0, 1])
        self.assertEqual(snapshots[0]["orchestration_labels"]["u1"]["codes"], ["manual"])
        self.assertEqual(snapshots[1]["orchestration_labels"]["u1"]["codes"], ["revised"])
        stats = [task for task in run["tasks"] if task["method_id"] == "label_frequency"]
        self.assertTrue(stats[0]["stale"])
        self.assertFalse(stats[1]["stale"])
        self.assertTrue(all(task["label_dependent"] for task in stats))

    def test_verification_clarification_reads_only_its_saved_result_and_evidence(self):
        self.agent = lambda role, context, *_: {"summary": "Independent observation", "claims": [
            {"claim_id": "independent-claim", "text": "First observed turn", "kind": "observation",
             "evidence_ids": [context["raw_evidence"][0]["evidence_id"]]}]}
        run = self.start()
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            original = self.service._register(db, state, intent("verification"), phase="specialists")
        self.service._execute(run["run_id"], original["task_id"])
        saved = self.service.status("conversation", run["run_id"])["results"][0]
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            state["current_view"] = {"summary": "SECRET_CORE_CONCLUSION"}
            clarification = self.service._register(db, state, intent("verification", "Explain the limits of your observation",
                kind="clarification", result_id=saved["result_id"]), phase="specialists")
            packet = self.service._context(db, state, clarification)
            with self.assertRaises(AnalysisContractError):
                self.service._register(db, state, intent("verification", "Explain initial conclusions",
                    kind="clarification", result_id=run["initial_id"], initial_sections=["segments"]), phase="specialists")
        self.assertEqual(packet["question"], "Explain the limits of your observation")
        self.assertEqual(packet["clarification_target"]["content"]["summary"], "Independent observation")
        self.assertEqual([e["utterance_id"] for e in packet["raw_evidence"]], ["u1"])
        self.assertNotIn("SECRET_CORE_CONCLUSION", json.dumps(packet))
        self.assertNotIn("initial", packet)
        self.assertNotIn("issues", packet)
        self.assertFalse(packet["execution_allowed"])
        self.assertFalse(packet["blind_first"])

    def test_configuration_secrets_not_retained_and_full_options_passed(self):
        run = self.drive(self.start(api_key="not-a-real-key", provider="openai", provider_policy="cloud_allowed", cloud_consent=True, adapter_version="core-handler-prompts-1"))
        self.assertNotIn("api_key", run["config"])
        self.assertTrue(self.calls[0][2]["cloud_consent"])
        self.assertIn("roles", self.calls[0][2])


if __name__ == "__main__":
    unittest.main()
