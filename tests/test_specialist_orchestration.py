"""Responsibility boundaries and restart of delegated specialist review."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_analysis_orchestration as f
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters, ADAPTER_VERSION


class SpecialistOrchestrationTests(unittest.TestCase):
    connect = f.RuntimeTests.connect
    build = f.RuntimeTests.build
    run_agent = f.RuntimeTests.run_agent
    method = f.RuntimeTests.method
    make_service = f.RuntimeTests.make_service
    start = f.RuntimeTests.start
    drive = f.RuntimeTests.drive

    def setUp(self):
        f.RuntimeTests.setUp(self)
        self.sent = []
        self.snapshot["analysis"]["segments"] = [
            {"id": f"u{i}", "text": f"Synthetic reason {i}", "speaker": "A", "annotation": {"codes": []}}
            for i in range(48)]
        self.resolve, self.adapter = make_orchestration_adapters(call_ai_json=self.transport,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"),
            context_meter=lambda *a: {"fits": len(json.loads(a[3]).get("iteration_review", {}).get("pending_result_ids", [])) <= 2, "output_reserve": 2000})
        self.agent = lambda role, context, options, check, usage: self.adapter(role, context, options, check, usage)
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)

    def transport(self, provider, key, model, system, prompt, name, schema, check, usage, *a, **kw):
        context = json.loads(prompt)
        role = name.removeprefix("analysis_orchestration_")
        self.sent.append((role, copy.deepcopy(context)))
        if role == "orchestrator":
            raw = f.core("Concrete scoped specialist finding", stop=None,
                result_assessments=f.assess_pending_results(context),
                critique_responses=[{"issue_id": i["issue_id"], "disposition": "defer", "reason": "Needs review", "impact": "Keep unresolved"} for i in context.get("issues", [])])
            if context["raw_evidence"]:
                raw["claims"] = [{"claim_id": "local", "text": "A scoped source contains a reason", "kind": "observation", "evidence_ids": [context["raw_evidence"][0]["evidence_id"]]}]
            return raw
        if role == "core" and context["task"]["phase"] == "core":
            return f.stop(alternatives=["Bounded alternative"])
        return f.InitialSpecialistTests.valid_agent(self, role, context)

    def begin(self, **options):
        return self.start(**self.resolve({"question": "test", "model_context_version": 1,
            "context_reference_version": 0, "max_calls": 150, "max_tasks": 200, "context_evidence_limit": 4, **options}))

    def test_core_only_sees_completed_reports_and_batches_are_not_core_rounds(self):
        run = self.drive(self.begin())
        self.assertEqual(run["status"], "completed", run.get("error"))
        integrations = [c for role, c in self.sent if role == "core" and c["task"]["phase"] == "core"]
        reviews = [c for role, c in self.sent if role == "orchestrator"]
        self.assertGreater(len(reviews), 3)
        self.assertEqual(len(integrations), 2)  # integration and post-critic decision
        self.assertEqual(run["completed_core_iterations"], 2)

        self.assertEqual(run["config"]["min_iterations"], 0)
        for c in integrations:
            self.assertEqual(c["iteration_review"]["pending_result_ids"], [])
            self.assertEqual(c["results"], [])
            self.assertTrue(c["domain_reports"])
        for c in reviews:
            self.assertNotIn("current_view", c)
            self.assertTrue(all(r["domain"] == c["review_domain"] for r in c["prior_domain_reports"]))
            roles = {r["role"] for r in c["results"]}
            if c["review_domain"] == "labels":
                self.assertTrue(roles <= {"interpretation", "critic"})
            else:
                self.assertEqual(len(roles), 1)
        labels = [c for role, c in self.sent if c.get("task", {}).get("phase") == "label_review"]
        self.assertEqual(len(labels), 1)
        self.assertTrue(labels[0]["initial_label_catalog"]["definitions"])
        self.assertNotIn("current_view", labels[0])
        with self.service._db() as db:
            decisions = [json.loads(row[0]) for row in db.execute("SELECT payload_json FROM orchestration_decisions WHERE run_id=?", (run["run_id"],))]
            refs = [a["result_id"] for d in decisions if d.get("role") == "orchestrator" for a in d["result_assessments"]]
            self.assertEqual(len(refs), len(set(refs)))
        count = len(self.sent)
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)
        self.service.run(run["run_id"])
        self.assertEqual(len(self.sent), count)

    def test_reference_delivery_is_used_by_all_roles_and_saved_with_manifest(self):
        from gurumoji import method_experts
        from gurumoji.services.model_context import restored_reference_context
        from test_referenced_context import make_catalog
        catalog = make_catalog(self.path.parent / "fixture-vault")
        actual_transport = self.transport
        deliveries = []
        def transport(*args, **kwargs):
            context = restored_reference_context(args[4], kwargs["data_messages"])
            deliveries.append((args[5], json.loads(args[4]), kwargs["data_messages"]))
            amended = list(args)
            amended[4] = json.dumps(context)
            return actual_transport(*amended, **kwargs)
        self.resolve, self.adapter = make_orchestration_adapters(call_ai_json=transport,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""), configured_ai_credentials=lambda *_: ("", "synthetic"),
            context_meter=lambda *a, **k: {"fits": len(json.loads(a[3]).get("iteration_review", {}).get("pending_result_ids", [])) <= 2, "output_reserve": 3200})
        original_reader = method_experts.orchestration_context
        with patch.object(method_experts, "orchestration_context", side_effect=lambda **kwargs: original_reader(**kwargs, catalog=catalog)):
            run = self.drive(self.begin(context_reference_version=1))
        self.assertEqual(run["status"], "completed", run.get("error"))
        self.assertEqual({role for role, _, _ in deliveries}, {"analysis_orchestration_" + role for role in ("core", "orchestrator", "interpretation", "verification", "critic")})
        for role, instruction, messages in deliveries:
            self.assertEqual(instruction["message_kind"], "task_instruction")
            self.assertNotIn("expert_knowledge", instruction)
            self.assertFalse(instruction.get("raw_evidence"))
            self.assertTrue(any(row["resource_id"] == "expert_knowledge" for row in instruction["resource_references"]))
            for reference in instruction["resource_references"]:
                if reference["resource_id"] == "raw_evidence":
                    self.assertIn(run["initial_id"], reference["path"])
        ai_tasks = [task for task in run["tasks"] if task["kind"] == "ai"]
        self.assertTrue(ai_tasks)
        for task in ai_tasks:
            self.assertEqual(task["context_manifest"]["reference_version"], 1)
            self.assertTrue(task["context_manifest_hash"])

    def test_prior_scoped_findings_are_read_as_memory_without_rereading_the_source(self):
        actual = self.transport
        remembered = []
        def memory(*args, **kwargs):
            raw = actual(*args, **kwargs); c = json.loads(args[4])
            if args[5].endswith("_orchestrator"):
                prior = [claim for r in c["prior_domain_reports"] for claim in r["claims"]]
                if prior:
                    claim = prior[0]
                    ref = claim["evidence_ids"][0]
                    current = {e["evidence_id"] for e in c["raw_evidence"]}
                    if ref not in current:
                        self.assertIn(ref, args[6]["properties"]["claims"]["items"]["properties"]["evidence_ids"]["items"]["enum"])
                        raw["claims"] = [copy.deepcopy(claim)]
                        remembered.append(ref)
            return raw
        self.resolve, self.adapter = make_orchestration_adapters(call_ai_json=memory,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"),
            context_meter=lambda *a: {"fits": len(json.loads(a[3]).get("iteration_review", {}).get("pending_result_ids", [])) <= 2, "output_reserve": 3200})
        run = self.drive(self.begin())
        self.assertEqual(run["status"], "completed", run.get("error"))
        self.assertTrue(remembered)

    def test_specialist_cannot_stop_or_replace_core_view(self):
        actual = self.transport
        def invalid(*args, **kwargs):
            raw = actual(*args, **kwargs)
            if args[5].endswith("_orchestrator"):
                raw["stop"] = {"reason": "question_satisfied", "summary": "Forbidden"}
            return raw
        self.resolve, self.adapter = make_orchestration_adapters(call_ai_json=invalid,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"),
            context_meter=lambda *a: {"fits": True, "output_reserve": 2000})
        run = self.drive(self.begin(context_evidence_limit=48))
        self.assertEqual(run["completed_core_iterations"], 0)
        self.assertEqual(run["current_view"], {})
        self.assertTrue(any(t.get("error") == "orchestrator_authority_invalid" for t in run["tasks"]))

    def test_restart_adopts_received_review_without_second_call(self):
        original = self.service._drain_tasks
        def pause(rid):
            original(rid)
            with self.service._db() as db:
                run = self.service._read_run(db, rid)
                if run["phase"] == "specialist_review":
                    run["status"] = "recovery_required"
                    self.service._write_run(db, run)
        self.service._drain_tasks = pause
        paused = self.drive(self.begin())
        self.assertEqual(paused["status"], "recovery_required")
        review = next(t for t in paused["tasks"] if t["role"] == "orchestrator")
        count = sum(role == "orchestrator" and c["task"]["task_id"] == review["task_id"] for role, c in self.sent)
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)
        self.service.resume("conversation", paused["run_id"], {})
        final = self.drive(paused)
        self.assertEqual(final["status"], "completed", final.get("error"))
        self.assertEqual(count, 1)
        self.assertEqual(sum(role == "orchestrator" and c["task"]["task_id"] == review["task_id"] for role, c in self.sent), count)

    def test_domain_followup_dispatches_before_first_core_and_exact_repeat_is_deferred(self):
        actual = self.transport
        def followup(*args, **kwargs):
            raw = actual(*args, **kwargs)
            c = json.loads(args[4])
            if args[5].endswith("_orchestrator") and c["review_domain"] == "interpretation":
                question = "Inspect the specific counterexample" if not any(x.get("task", {}).get("phase") == "specialist_followup" for _, x in self.sent) else "test"
                raw["intents"] = [{"role": "interpretation", "kind": "analysis", "question": question,
                    "why_now": "Test a specific limitation", "success_criteria": "Retain cited counterexample",
                    "evidence_ids": [c["raw_evidence"][0]["evidence_id"]], "importance": "high", "importance_reason": "Relevant limitation"}]
            return raw
        self.resolve, self.adapter = make_orchestration_adapters(call_ai_json=followup,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"), context_meter=lambda *a: {"fits": True, "output_reserve": 2000})
        run = self.drive(self.begin(context_evidence_limit=48))
        self.assertEqual(run["status"], "completed", run.get("error"))
        tasks = [t for t in run["tasks"] if t["phase"] == "specialist_followup"]
        self.assertEqual(len(tasks), 1)
        first_core = next(t for t in run["tasks"] if t["phase"] == "core")
        self.assertLessEqual(tasks[0]["ended_at"], first_core["started_at"])
        followup_context = next(c for role, c in self.sent if c.get("task", {}).get("phase") == "specialist_followup")
        self.assertEqual(followup_context["results"], [])
        self.assertNotIn("initial_analysis_report", followup_context)
        self.assertNotIn("current_view", followup_context)
        self.assertTrue(any(e["type"] == "intent_deferred" for e in run["events"]))

    def test_core_cannot_take_back_individual_result_assessment(self):
        actual = self.transport
        def invalid(*args, **kwargs):
            raw = actual(*args, **kwargs)
            context = json.loads(args[4])
            if args[5].endswith("_core") and context["task"]["phase"] == "core":
                rid = context["domain_reports"][0]["source_result_ids"][0]
                raw["result_assessments"] = [{"result_id": rid, "disposition": "adopt", "reason": "Forbidden", "impact": "Forbidden"}]
            return raw
        self.resolve, self.adapter = make_orchestration_adapters(call_ai_json=invalid,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"), context_meter=lambda *a: {"fits": True, "output_reserve": 2000})
        run = self.drive(self.begin(context_evidence_limit=48))
        self.assertEqual(run["completed_core_iterations"], 0)
        self.assertTrue(any(t.get("error") == "core_authority_invalid" for t in run["tasks"]))

    def test_new_review_identity_for_same_sources_is_not_progress(self):
        final = self.drive(self.begin())
        with self.service._db() as db:
            run = self.service._read_run(db, final["run_id"])
            reports = self.service._domain_reports(db, run)
            same_sources = {**reports[0], "result_id": "new-review-same-sources"}
            # Re-adopt a saved valid Core answer with a new review identity.
            # The answer and underlying source/version/hash remain unchanged.
            core_task = next(t for t in reversed(self.service._tasks(db, run["run_id"])) if t["phase"] == "core")
            result = dict(db.execute("SELECT * FROM orchestration_results WHERE task_id=?", (core_task["task_id"],)).fetchone())
            meta = json.loads(result["state_json"])
            result["result_id"] = meta["result_id"] = "new-core-same-answer"
            result["state_json"] = json.dumps(meta)
            run["status"] = "running"
            with patch.object(self.service, "_domain_reports", return_value=[*reports, same_sources]):
                self.service._apply_core(db, run, core_task, result)
            self.assertEqual(run["stop_reason"], "no_progress")

    def test_measurement_critique_keeps_its_own_target_version_after_core_changes(self):
        actual = self.transport
        def critique(*args, **kwargs):
            raw = actual(*args, **kwargs); c = json.loads(args[4])
            if c.get("task", {}).get("phase") == "label_review":
                target = c["review_target"]
                raw.update(review_status="issues", issues=[{"issue_key": "measurement-validity",
                    "target_id": target["target_id"], "target_version": target["target_version"], "severity": "high",
                    "reason": "Scale lacks independent validation", "evidence_ids": [], "missing_evidence": "Independent coder agreement"}])
            return raw
        self.resolve, self.adapter = make_orchestration_adapters(call_ai_json=critique,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"), context_meter=lambda *a: {"fits": True, "output_reserve": 2000})
        run = self.drive(self.begin(context_evidence_limit=48))
        issue = next(i for i in run["issues"] if i["issue_key"] == "measurement-validity")
        self.assertGreater(run["view_version"], issue["target_version"])
        self.assertFalse(issue["stale"])
        self.assertEqual(issue["status"], "defer")
        self.assertIn(issue["issue_id"], {i["issue_id"] for i in run["unresolved_issues"]})

    def test_failed_domain_followup_prevents_silent_success(self):
        actual = self.transport
        def failure(*args, **kwargs):
            c = json.loads(args[4])
            if c.get("task", {}).get("phase") == "specialist_followup":
                raise f.AnalysisContractError("Synthetic scoped analysis failure", code="context_budget_exceeded")
            raw = actual(*args, **kwargs)
            if args[5].endswith("_orchestrator") and c["review_domain"] == "interpretation":
                raw["intents"] = [{"role": "interpretation", "question": "Inspect one counterexample", "why_now": "New limitation",
                    "success_criteria": "Cite the scoped source", "evidence_ids": [c["raw_evidence"][0]["evidence_id"]],
                    "importance": "high", "importance_reason": "Relevant limitation"}]
            return raw
        self.resolve, self.adapter = make_orchestration_adapters(call_ai_json=failure,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"), context_meter=lambda *a: {"fits": True, "output_reserve": 2000})
        run = self.drive(self.begin(context_evidence_limit=48))
        self.assertEqual(run["status"], "stopped")
        self.assertEqual(run["stop_reason"], "execution_failure")
        self.assertEqual(run["completed_core_iterations"], 0)

    def test_broad_near_repeat_is_deferred_and_fixed_statistics_are_reused(self):
        actual = self.transport
        original = "Analyze the reasons, evaluations and concerns in this synthetic conversation using source IDs and retain alternative explanations."
        def repeated(*args, **kwargs):
            c = json.loads(args[4]); raw = actual(*args, **kwargs)
            if args[5].endswith("_orchestrator"):
                if c["review_domain"] == "interpretation":
                    raw["intents"] = [{"role": "interpretation", "question": original.replace("this synthetic", "the synthetic"),
                        "why_now": "Analyze again", "success_criteria": "Report reasons", "importance": "high", "importance_reason": "Related"}]
                elif c["review_domain"] == "statistics":
                    raw["intents"] = [{"role": "statistics", "method_id": "participation", "question": "Recount participation with a different title",
                        "why_now": "Recheck", "success_criteria": "Retain denominator", "importance": "high", "importance_reason": "Related"}]
            return raw
        self.resolve, self.adapter = make_orchestration_adapters(call_ai_json=repeated,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"), context_meter=lambda *a: {"fits": True, "output_reserve": 2000})
        run = self.drive(self.begin(question=original, context_evidence_limit=48))
        self.assertEqual(run["status"], "completed", run.get("error"))
        self.assertFalse(any(t["phase"] == "specialist_followup" for t in run["tasks"]))
        self.assertEqual(sum(t["role"] == "statistics" and t["method_id"] == "participation" for t in run["tasks"]), 1)
        self.assertTrue(any(e["type"] == "duplicate_suppressed" for e in run["events"]))
        self.assertTrue(any(r["deferred_followup_count"] for role, c in self.sent if role == "core" for r in c.get("domain_reports", [])))


if __name__ == "__main__":
    unittest.main()
