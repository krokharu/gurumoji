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


def assess_pending_results(context, disposition="adopt"):
    return [{"result_id": result_id, "disposition": disposition,
             "reason": "Compared the saved specialist result with the bounded finding",
             "impact": "Retain the finding within the provided evidence; no population generalization"}
            for result_id in context.get("iteration_review", {}).get("pending_result_ids", [])]


def draft_label_definition(evidence_id):
    return {"definition_id": "reason_specificity", "version": 1, "name": "理由の具体性",
            "description": "発話で理由が明示される具体性を記述する未検証の候補尺度",
            "unit_of_analysis": "utterance", "data_type": "number", "measurement_level": "ordinal",
            "measurement_justification": "程度の順序だけを扱い、間隔が等しいとは仮定しない",
            "unit": "段階", "decision_rule": "発話内の理由説明を根拠に分類する",
            "levels": [{"value": 1, "meaning": "抽象的な理由", "criteria": "理由はあるが具体例や条件がない"},
                       {"value": 2, "meaning": "具体的な理由", "criteria": "理由に具体例または条件がある"}],
            "missing_rule": "null_with_reason", "missing_criteria": "理由が語られていない、未読、判断不能はnullと区別した理由",
            "recommended_analysis": "ordinal_distribution", "evidence_ids": [evidence_id]}


class InitialLabelTests(unittest.TestCase):
    connect = lambda self: RuntimeTests.connect(self)
    build = lambda self, item: RuntimeTests.build(self, item)
    run_agent = lambda self, *args: RuntimeTests.run_agent(self, *args)
    method = lambda self, *args: RuntimeTests.method(self, *args)
    make_service = lambda self, **kwargs: RuntimeTests.make_service(self, **kwargs)
    drive = lambda self, run: RuntimeTests.drive(self, run)

    def setUp(self):
        RuntimeTests.setUp(self)
        self.agent = self.valid_agent

    def start(self, **extra):
        return RuntimeTests.start(self, core_progress_version=1, initial_label_definitions_version=1, **extra)

    def valid_agent(self, role, context, *_):
        if context.get("task", {}).get("method_id") == "label-design-v1":
            return {"summary": "Draft scale", "claims": [], "label_patches": [],
                    "label_definitions": [draft_label_definition(context["raw_evidence"][0]["evidence_id"])]}
        return stop(result_assessments=assess_pending_results(context)) if role == "core" else critic(context)

    def test_specialist_creates_scales_before_first_core_and_preserves_manual_labels(self):
        run = self.drive(self.start())
        self.assertEqual(self.calls[0][0], "interpretation")
        self.assertEqual(self.calls[0][1]["task"]["method_id"], "label-design-v1")
        self.assertEqual(self.calls[0][1]["budget"]["completed_core_iterations"], 0)
        first = next(ctx for role, ctx, _ in self.calls if role == "core")
        catalog = first["initial_label_catalog"]
        self.assertEqual(catalog["created_by"], "interpretation")
        self.assertEqual(catalog["status"], "ai_draft")
        self.assertEqual(len(catalog["definitions"]), 1)
        self.assertIn(catalog["result_id"], first["iteration_review"]["pending_result_ids"])
        self.assertEqual(first["task"]["iteration"], 1)
        export = self.service.result("conversation", run["run_id"])
        self.assertEqual(export["run"]["initial_label_catalog"], catalog)
        self.assertEqual(export["decisions"][0]["initial_label_result_id"], catalog["result_id"])
        self.assertEqual(export["label_versions"], [{"annotation_version": 0, "labels": {"u1": {"codes": ["manual"]}, "u2": {"codes": []}}}])
        self.assertEqual(run["codebook_version"], 1)
        self.assertEqual(sum(ctx.get("task", {}).get("method_id") == "label-design-v1" for _, ctx, _ in self.calls), 1)

    def test_missing_or_empty_definitions_stop_before_core_without_retry(self):
        for value in (None, [], "later"):
            with self.subTest(value=value):
                self.calls.clear()
                self.agent = lambda *_: {"summary": "Deferred", "claims": [], "label_definitions": value}
                run = self.drive(self.start(request_id="missing-" + str(value)))
                self.assertEqual(run["status"], "stopped")
                self.assertEqual(run["stop_reason"], "initial_labels_missing")
                self.assertEqual(run["completed_core_iterations"], 0)
                self.assertEqual(run["iteration"], 0)
                self.assertEqual([role for role, *_ in self.calls], ["interpretation"])
                raw = self.service.result("conversation", run["run_id"])["raw_results"]
                self.assertEqual(raw[0]["validation_status"], "quarantined")
                self.assertEqual(raw[0]["raw"]["label_definitions"], value)
                self.service.run(run["run_id"])
                self.assertEqual(len(self.calls), 1)

    def test_ai_packets_omit_redundant_metadata_and_keep_full_saved_evidence(self):
        self.snapshot["analysis"]["segments"][0]["annotation"]["private_analysis_summary"] = "Unrelated stored annotation " * 100
        run = self.drive(self.start())
        label_context = self.calls[0][1]
        self.assertNotIn("labels", label_context)
        self.assertNotIn("current_view", label_context)
        first_core = next(ctx for role, ctx, _ in self.calls if role == "core")
        self.assertEqual(first_core["labels"]["u1"], {"codes": ["manual"]})
        for context in (label_context, first_core):
            self.assertNotIn("source_hash", context["raw_evidence"][0])
            self.assertNotIn("dataset_version", context["raw_evidence"][0])
            self.assertTrue(context["data_version"])
            self.assertTrue(context["raw_evidence"][0]["evidence_id"])
        result = next(r for r in first_core["results"] if r["result_id"] == run["initial_label_result_id"])
        self.assertEqual(result["content"]["label_definitions_ref"], "initial_label_catalog")
        self.assertNotIn("label_definitions", result["content"])
        saved = self.service.result("conversation", run["run_id"])["initial"]["snapshot"]
        self.assertTrue(saved["evidence"][0]["source_hash"])
        self.assertTrue(saved["analysis"]["segments"][0]["annotation"]["private_analysis_summary"])

    def test_invalid_scales_and_unread_evidence_are_not_accepted(self):
        mutations = [lambda d: d.update(levels=[]), lambda d: d["levels"][0].update(criteria=" "),
                     lambda d: d.update(recommended_analysis="descriptive"),
                     lambda d: d.update(measurement_level="ratio", data_type="category"),
                     lambda d: d.update(missing_rule="zero"), lambda d: d.update(evidence_ids=["ev_missing"]),
                     lambda d: d.update(data_type="category", levels=[{"value": "yes", "meaning": "Present", "criteria": "Explicit"}, {"value": "欠測", "meaning": "Missing", "criteria": "No information"}]),
                     lambda d: d["levels"][1].update(value=1), lambda d: d["levels"].reverse()]
        for index, mutate in enumerate(mutations):
            def agent(role, context, *args):
                response = self.valid_agent(role, context, *args)
                mutate(response["label_definitions"][0])
                return response
            self.agent = agent
            run = self.drive(self.start(request_id=f"invalid-scale-{index}"))
            self.assertEqual(run["stop_reason"], "initial_labels_missing", index)
            self.assertEqual(run["completed_core_iterations"], 0)
        self.agent = lambda role, context, *_: {"summary": "Unread scale", "claims": [],
            "label_definitions": [draft_label_definition(context["coverage"]["evidence_index"][1]["evidence_id"])]}
        run = self.drive(self.start(request_id="unread-scale", context_evidence_limit=1))
        self.assertEqual(run["stop_reason"], "initial_labels_missing")

    def test_restart_adopts_received_scale_result_without_second_provider_call(self):
        run = self.start()
        original = self.service._drain_tasks
        def interrupted(rid):
            original(rid)
            with self.service._db() as db:
                state = self.service._read_run(db, rid)
                if state["phase"] == "initial_labels":
                    state["status"] = "recovery_required"
                    self.service._write_run(db, state)
        self.service._drain_tasks = interrupted
        paused = self.drive(run)
        self.assertEqual(paused["status"], "recovery_required")
        self.assertEqual(len(self.calls), 1)
        self.service = self.make_service()
        self.service.resume("conversation", run["run_id"], {})
        final = self.drive(run)
        self.assertTrue(final["initial_label_catalog"])
        self.assertEqual(sum(ctx.get("task", {}).get("method_id") == "label-design-v1" for _, ctx, _ in self.calls), 1)

    def test_core_cannot_create_or_overwrite_specialist_definitions(self):
        def agent(role, context, *args):
            response = self.valid_agent(role, context, *args)
            if role == "core":
                response["label_definitions"] = [draft_label_definition(context["raw_evidence"][0]["evidence_id"])]
            return response
        self.agent = agent
        run = self.drive(self.start())
        self.assertEqual(run["completed_core_iterations"], 0)
        self.assertEqual(run["tasks"][-1]["error"], "label_definition_author_invalid")

    def test_saved_definition_hash_is_checked_before_first_core(self):
        original = self.service._drain_tasks
        def tampered(rid):
            original(rid)
            with self.service._db() as db:
                state = self.service._read_run(db, rid)
                if state["phase"] == "initial_labels":
                    row = db.execute("SELECT result_id,raw_json FROM orchestration_results WHERE run_id=?", (rid,)).fetchone()
                    raw = json.loads(row[1])
                    raw["label_definitions"][0]["name"] = "Changed after validation"
                    db.execute("UPDATE orchestration_results SET raw_json=? WHERE result_id=?", (json.dumps(raw), row[0]))
        self.service._drain_tasks = tampered
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "execution_failure")
        self.assertEqual(run["error"], "result_integrity_mismatch")
        self.assertEqual(run["completed_core_iterations"], 0)
        self.assertEqual(len(self.calls), 1)


class InitialSpecialistTests(unittest.TestCase):
    connect = lambda self: RuntimeTests.connect(self)
    build = lambda self, item: RuntimeTests.build(self, item)
    run_agent = lambda self, *args: RuntimeTests.run_agent(self, *args)
    method = lambda self, *args: RuntimeTests.method(self, *args)
    make_service = lambda self, **kwargs: RuntimeTests.make_service(self, **kwargs)
    drive = lambda self, run: RuntimeTests.drive(self, run)

    def setUp(self):
        RuntimeTests.setUp(self)
        self.agent = self.valid_agent

    def start(self, **extra):
        return RuntimeTests.start(self, core_progress_version=1, initial_label_definitions_version=1,
                                  initial_specialist_analysis_version=1, max_iterations=3, **extra)

    def valid_agent(self, role, context, *_):
        task = context.get("task", {})
        if task.get("phase") == "initial_analysis":
            result = critic(context) if role == "critic" else {"summary": "Independent source inspection", "claims": []}
            if role in {"interpretation", "verification"}:
                result["claims"] = [{"claim_id": role + "_observed", "text": "The provided synthetic utterance contains a statement",
                                     "kind": "observation", "evidence_ids": [context["raw_evidence"][0]["evidence_id"]]}]
            result["label_requirements"] = [{"requirement_id": role + "_reason", "kind": "scale",
                "name": "理由の具体性", "analysis": "明示された理由の段階別分布", "reason": "段階と欠測を区別するため",
                "evidence_ids": [context["raw_evidence"][0]["evidence_id"]]}]
            return result
        if task.get("phase") == "initial_routing":
            return core("Requirements require a specialist scale", stop=None,
                intents=[intent("interpretation", "報告された理由の具体性尺度を根拠付きで設計", method_id="label-design-v1")])
        if task.get("method_id") == "label-design-v1":
            return {"summary": "Draft scale", "claims": [], "label_patches": [],
                    "label_definitions": [draft_label_definition(context["raw_evidence"][0]["evidence_id"])]}
        if role == "core":
            return stop(result_assessments=assess_pending_results(context),
                        alternatives=["Bounded examination " + str(task["iteration"])])
        return critic(context)

    def test_all_roles_report_then_core_routes_then_specialist_designs_before_round_one(self):
        run = self.drive(self.start())
        report = run["initial_analysis_report"]
        self.assertTrue(report["all_roles_reported"])
        self.assertEqual({r["role"] for r in report["reports"]}, {"interpretation", "statistics", "verification", "critic"})
        self.assertEqual({m for m, _ in self.methods}, {"participation", "conversation_dynamics", "label_frequency"})
        self.assertEqual(len(report["reports"]), 6)
        self.assertEqual(len(report["label_requirements"]), 1)
        self.assertEqual(len(report["label_requirements"][0]["sources"]), 3)
        contexts = [context for role, context, _ in self.calls if role == "core"]
        routing, first = contexts[:2]
        self.assertEqual(routing["task"]["phase"], "initial_routing")
        self.assertEqual(routing["budget"]["completed_core_iterations"], 0)
        self.assertIsNone(routing["initial_label_catalog"])
        self.assertEqual(first["task"]["iteration"], 1)
        self.assertEqual(first["budget"]["completed_core_iterations"], 0)
        self.assertTrue(first["initial_label_catalog"])
        self.assertEqual(len(first["iteration_review"]["pending_result_ids"]), 7)
        design = next(ctx for _, ctx, _ in self.calls if ctx.get("task", {}).get("method_id") == "label-design-v1")
        self.assertEqual(design["initial_analysis_report"], report)
        self.assertEqual(design["routing_instruction"]["question"], "報告された理由の具体性尺度を根拠付きで設計")
        self.assertEqual(len(design["task"]["dependencies"]), 7)
        export = self.service.result("conversation", run["run_id"])
        self.assertEqual(export["decisions"][0]["phase"], "initial_routing")
        self.assertEqual(run["completed_core_iterations"], len(export["decisions"]) - 1)
        self.assertEqual(export["label_versions"], [{"annotation_version": 0, "labels": {"u1": {"codes": ["manual"]}, "u2": {"codes": []}}}])
        for role, ctx, _ in self.calls:
            if ctx.get("task", {}).get("phase") == "initial_analysis":
                self.assertNotIn("results", ctx)
                self.assertNotIn("current_view", ctx)
                self.assertNotIn("initial_label_catalog", ctx)

    def test_unreported_requirements_stop_without_core_or_scale_task(self):
        original = self.agent
        def incomplete(role, ctx, *args):
            result = original(role, ctx, *args)
            if role == "interpretation" and ctx["task"]["phase"] == "initial_analysis":
                result.pop("label_requirements")
            return result
        self.agent = incomplete
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "initial_analysis_incomplete")
        self.assertEqual(run["completed_core_iterations"], 0)
        self.assertFalse(any(role == "core" for role, _, _ in self.calls))

    def test_invalid_routing_cannot_bypass_specialist_or_finish_analysis(self):
        original = self.agent
        def invalid(role, ctx, *args):
            if ctx["task"].get("phase") == "initial_routing":
                return stop()
            return original(role, ctx, *args)
        self.agent = invalid
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "initial_routing_invalid")
        self.assertEqual(run["completed_core_iterations"], 0)
        self.assertFalse(any(ctx.get("task", {}).get("method_id") == "label-design-v1" for _, ctx, _ in self.calls))

    def test_aggregate_survives_restart_without_reissuing_initial_tasks(self):
        original = self.service._apply_initial_routing
        def pause(db, run, task):
            run["status"] = "recovery_required"
            self.service._write_run(db, run)
        self.service._apply_initial_routing = pause
        paused = self.drive(self.start())
        self.assertEqual(paused["status"], "recovery_required")
        self.service._apply_initial_routing = original
        self.service.resume("conversation", paused["run_id"])
        final = self.drive(paused)
        self.assertEqual(final["initial_analysis_report"], paused["initial_analysis_report"])
        self.assertEqual(len(self.methods), 3)
        self.assertEqual(sum(ctx.get("task", {}).get("phase") == "initial_analysis" for _, ctx, _ in self.calls), 3)
        self.assertEqual(sum(ctx.get("task", {}).get("phase") == "initial_routing" for _, ctx, _ in self.calls), 1)

    def test_unread_scale_requirement_is_not_reported_as_an_observation(self):
        original = self.agent
        def unread(role, ctx, *args):
            result = original(role, ctx, *args)
            if role == "interpretation" and ctx["task"].get("phase") == "initial_analysis":
                result["label_requirements"][0]["evidence_ids"] = [ctx["coverage"]["evidence_index"][1]["evidence_id"]]
            return result
        self.agent = unread
        run = self.drive(self.start(context_evidence_limit=1))
        self.assertEqual(run["stop_reason"], "initial_analysis_incomplete")
        self.assertTrue(any(t.get("error") == "invalid_initial_requirement" for t in run["tasks"]))
        self.assertFalse(any(role == "core" for role, _, _ in self.calls))

    def test_budget_shortage_does_not_claim_all_initial_roles_ran(self):
        run = self.drive(self.start(max_calls=2))
        self.assertEqual(run["stop_reason"], "call_budget_limit")
        self.assertEqual(run["completed_core_iterations"], 0)
        self.assertFalse(run.get("initial_analysis_report"))
        self.assertEqual(self.calls, [])

    def test_initial_explanation_without_evidence_claims_is_not_an_analysis(self):
        original = self.agent
        def empty(role, ctx, *args):
            result = original(role, ctx, *args)
            if role == "verification" and ctx["task"].get("phase") == "initial_analysis":
                result["claims"] = []
            return result
        self.agent = empty
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "initial_analysis_incomplete")
        self.assertTrue(any(t.get("error") == "initial_analysis_empty" for t in run["tasks"]))
        self.assertFalse(any(role == "core" for role, _, _ in self.calls))


class ProgressTests(unittest.TestCase):
    connect = lambda self: RuntimeTests.connect(self)
    build = lambda self, item: RuntimeTests.build(self, item)
    run_agent = lambda self, *args: RuntimeTests.run_agent(self, *args)
    method = lambda self, *args: RuntimeTests.method(self, *args)
    make_service = lambda self, **kwargs: RuntimeTests.make_service(self, **kwargs)
    drive = lambda self, run: RuntimeTests.drive(self, run)

    def setUp(self):
        RuntimeTests.setUp(self)

    def start(self, **extra):
        return RuntimeTests.start(self, core_progress_version=1, **extra)

    def export(self, run):
        return self.service.result("conversation", run["run_id"])

    def test_identical_empty_work_is_stopped_without_counting_duplicate(self):
        self.agent = lambda *_: core(result_assessments=[])
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "no_progress")
        self.assertEqual(run["status"], "stopped")
        self.assertEqual(run["iteration"], 2)
        self.assertEqual(run["completed_core_iterations"], 1)
        exported = self.export(run)
        self.assertEqual(len(exported["decisions"]), 1)
        self.assertEqual(len(exported["raw_results"]), 2)
        self.assertEqual(exported["raw_results"][-1]["content_status"], "no_progress")
        self.assertEqual(exported["raw_results"][0]["raw_hash"], exported["raw_results"][1]["raw_hash"])
        calls_before = len(self.calls)
        self.service = self.make_service()
        self.service.run(run["run_id"])
        self.assertEqual(len(self.calls), calls_before)
        self.assertEqual(len(self.export(run)["decisions"]), 1)

    def test_same_stop_after_review_does_not_fake_three_progressing_decisions(self):
        self.agent = lambda role, ctx, *_: stop(result_assessments=assess_pending_results(ctx)) if role == "core" else critic(ctx)
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "no_progress")
        self.assertEqual(run["completed_core_iterations"], 2)
        self.assertEqual(sum(role == "core" for role, *_ in self.calls), 3)
        self.assertEqual(sum(role == "critic" for role, *_ in self.calls), 1)

    def test_cosmetic_summary_id_punctuation_and_array_order_changes_are_not_progress(self):
        def agent(role, ctx, *_):
            if role != "core":
                return critic(ctx)
            round_number = ctx["budget"]["iteration"]
            refs = [e["evidence_id"] for e in ctx["raw_evidence"]]
            return stop(summary=f"Cosmetic wording {round_number}",
                claims=[{"claim_id": str(round_number), "text": "  A bounded observation! " if round_number > 1 else "A bounded observation",
                         "kind": "observation", "evidence_ids": refs[::-1] if round_number > 1 else refs}],
                alternatives=["second", "first"] if round_number > 1 else ["first", "second"],
                result_assessments=assess_pending_results(ctx))
        self.agent = agent
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "no_progress")
        self.assertEqual(run["completed_core_iterations"], 2)
        self.assertEqual(len(self.export(run)["decisions"]), 2)

    def test_alternating_old_findings_are_detected_as_a_cycle(self):
        self.agent = lambda role, ctx, *_: core(alternatives=["First" if ctx["budget"]["iteration"] % 2 else "Second"], result_assessments=[])
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "no_progress")
        self.assertEqual(run["completed_core_iterations"], 2)
        self.assertEqual(run["iteration"], 3)

    def test_normalization_preserves_sign_decimal_and_word_boundaries(self):
        signature = self.service._core_progress_signature
        for before, after in (("The value is -1", "The value is 1"),
                              ("The value is 1.2", "The value is 12"),
                              ("not able", "notable")):
            with self.subTest(before=before, after=after):
                self.assertNotEqual(signature({"unresolved": [before]}), signature({"unresolved": [after]}))

    def test_specialist_results_cannot_be_silently_ignored_before_completion(self):
        self.agent = lambda role, ctx, *_: stop() if role == "core" else critic(ctx)
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "unreviewed_results")
        self.assertEqual(run["completed_core_iterations"], 1)
        self.assertEqual(run["tasks"][-1]["error"], "result_assessment_missing")

    def test_new_evidence_and_reviewed_specialist_results_allow_three_decisions(self):
        def agent(role, ctx, *_):
            if role != "core":
                return critic(ctx)
            claim = {"claim_id": "observed", "text": "Bounded observation", "kind": "observation",
                     "evidence_ids": [ctx["raw_evidence"][0]["evidence_id"]]}
            if ctx["budget"]["iteration"] == 1:
                return core(claims=[claim], intents=[intent("interpretation")], result_assessments=[])
            return stop(claims=[claim], result_assessments=assess_pending_results(ctx))
        self.agent = agent
        run = self.drive(self.start())
        self.assertEqual(run["status"], "completed", run)
        self.assertEqual(run["completed_core_iterations"], 3)
        decisions = self.export(run)["decisions"]
        assessed = [entry["result_id"] for decision in decisions for entry in decision["result_assessments"]]
        specialist_ids = {r["result_id"] for r in run["results"] if r["role"] != "core" and r["validation_status"] == "valid"}
        self.assertEqual(set(assessed), specialist_ids)
        self.assertEqual(len(assessed), len(set(assessed)))
        core_contexts = [ctx for role, ctx, *_ in self.calls if role == "core"]
        self.assertEqual([ctx["budget"]["completed_core_iterations"] for ctx in core_contexts], [0, 1, 2])
        self.assertTrue(any(r["role"] == "verification" for r in core_contexts[1]["results"]))

    def test_invalid_result_assessment_references_and_blank_reasons_are_quarantined(self):
        for bad in ("missing", "duplicate", "unknown", "blank", "core"):
            with self.subTest(bad=bad):
                def agent(role, ctx, *_):
                    if role != "core":
                        return critic(ctx)
                    assessments = assess_pending_results(ctx)
                    if assessments:
                        if bad == "missing": assessments = []
                        elif bad == "duplicate": assessments += assessments[:1]
                        elif bad == "unknown": assessments[0]["result_id"] = "not-in-this-run"
                        elif bad == "blank": assessments[0]["reason"] = "  "
                        else: assessments[0]["result_id"] = next(r["result_id"] for r in ctx["results"] if r["role"] == "core")
                    return stop(result_assessments=assessments)
                self.agent = agent
                run = self.drive(self.start(request_id="bad-assessment-" + bad))
                self.assertNotEqual(run["status"], "completed")
                self.assertEqual(run["completed_core_iterations"], 1)
                self.assertEqual(run["tasks"][-1]["status"], "quarantined")

    def test_pending_results_are_batched_without_dropping_earlier_unreviewed_results(self):
        def agent(role, ctx, *_):
            if role != "core":
                return critic(ctx) if role == "critic" else {"summary": ctx["task"]["title"], "claims": []}
            if ctx["budget"]["iteration"] == 1:
                return core(intents=[intent("interpretation", question=f"Check distinct scope {n}") for n in range(21)], result_assessments=[])
            return stop(result_assessments=assess_pending_results(ctx))
        self.agent = agent
        run = self.drive(self.start(max_calls=80, max_tasks=80))
        self.assertEqual(run["status"], "completed", run)
        contexts = [ctx for role, ctx, *_ in self.calls if role == "core"]
        self.assertEqual(len(contexts[1]["iteration_review"]["pending_result_ids"]), 20)
        self.assertEqual(contexts[1]["iteration_review"]["omitted_pending_result_count"], 1)
        for ctx in contexts:
            self.assertTrue(set(ctx["iteration_review"]["pending_result_ids"]) <= {r["result_id"] for r in ctx["results"]})
        assessed = [entry["result_id"] for decision in self.export(run)["decisions"] for entry in decision["result_assessments"]]
        self.assertEqual(len(assessed), 22)
        self.assertEqual(len(assessed), len(set(assessed)))

    def test_new_ids_for_identical_specialist_results_are_not_new_evidence(self):
        def agent(role, ctx, *_):
            if role != "core":
                return {"summary": "Same saved finding", "claims": []}
            question = "Initial examination" if ctx["budget"]["iteration"] == 1 else "Alternative examination"
            return core(intents=[intent("interpretation", question=question)], result_assessments=assess_pending_results(ctx))
        self.agent = agent
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "no_progress")
        self.assertEqual(run["completed_core_iterations"], 2)
        results = [r for r in run["results"] if r["role"] == "interpretation"]
        self.assertEqual(len(results), 2)
        self.assertNotEqual(results[0]["result_id"], results[1]["result_id"])
        self.assertEqual(results[0]["raw_hash"], results[1]["raw_hash"])


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
