"""Issue 35: dependency-scoped delivery from synthetic, isolated saved results."""
import copy
import itertools
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from gurumoji.analysis_core import AnalysisContractError, canonical, fingerprint
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
import test_analysis_orchestration as support
import test_expert_agents as expert_support
import test_statistical_expert_agents as statistical_support


class ResultDeliveryScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-result-delivery-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.sqlite3"
        self.snapshot = {"input_hash": "synthetic-input-v1", "source_revision": 1,
            "analysis_revision": 1, "analysis": {"segments": [
                {"id": f"u{i}", "text": f"Synthetic range {i}",
                 "speaker": "UNKNOWN" if i == 2 else f"S{i % 2}",
                 "start": None, "end": None, "duration": None, "valid_time": False,
                 "annotation": {"codes": [f"synthetic-{i}"]}, "excluded": i == 7}
                for i in range(8)], "all_results": {"missing": None, "computed_zero": 0}}}
        self.calls = []
        self.task_numbers = itertools.count(1)
        self.response = {"summary": "Synthetic saved result", "claims": []}
        self.service = self.make_service()
        self.run = self.start()
        self.evidence = self.saved()["initial"]["snapshot"]["evidence"]

    def make_service(self):
        return AnalysisOrchestrationService(
            connect=lambda: sqlite3.connect(self.path), find_item=lambda _: {"id": "synthetic"},
            snapshot_builder=lambda _: copy.deepcopy(self.snapshot),
            source_fingerprint=lambda _: self.snapshot["input_hash"],
            agent_runner=self.agent, method_runner=lambda *_: self.fail("No method dispatch"),
            schedule=False)

    def start(self):
        return self.service.start("synthetic", {"model": "synthetic-model",
            "obsidian_management": False, "time_limit_seconds": None,
            "max_calls": 80, "max_tasks": 100, "context_evidence_limit": 2,
            "context_index_limit": 3})

    def agent(self, role, context, *_):
        self.calls.append(copy.deepcopy(context))
        return copy.deepcopy(self.response)

    def register(self, role="interpretation", run=None, **extra):
        run = run or self.run
        with self.service._db() as db:
            current = self.service._read_run(db, run["run_id"])
            if role == "critic":
                extra = {"target_id": "view", "target_version": current["view_version"], **extra}
            return self.service._register(db, current,
                support.intent(role, question=extra.pop("question", f"Synthetic task {next(self.task_numbers)}"),
                               kind=extra.pop("kind", "analysis"), **extra),
                phase="core" if role == "core" else "specialists", automatic=True)

    def context(self, task, run=None):
        with self.service._db() as db:
            current = self.service._read_run(db, (run or self.run)["run_id"])
            return self.service._context(db, current, task)

    def produce(self, summary="Synthetic saved result", role="interpretation", run=None, **extra):
        self.response = {"summary": summary, "claims": []}
        task = self.register(role, run=run, **extra)
        self.service._execute((run or self.run)["run_id"], task["task_id"])
        state = self.service.status("synthetic", (run or self.run)["run_id"])
        result = next(row for row in state["tasks"] if row["task_id"] == task["task_id"])
        self.assertEqual(result["status"], "succeeded", result)
        return result

    def saved(self, result_id=None, service=None):
        return (service or self.service).result("synthetic", self.run["run_id"], result_id)

    def mutate_result(self, task, **changes):
        with self.service._db() as db:
            row = db.execute("SELECT state_json FROM orchestration_results WHERE result_id=?",
                             (task["result_id"],)).fetchone()
            metadata = {**json.loads(row[0]), **changes}
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?",
                       (canonical(metadata).decode(), task["result_id"]))
        return metadata

    def mutate_task(self, task, **changes):
        with self.service._db() as db:
            row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?",
                             (task["task_id"],)).fetchone()
            self.service._write_task(db, {**json.loads(row[0]), **changes})

    def assert_not_delivered(self, result, metadata):
        self.assertEqual(result, {**metadata, "body_not_delivered": True})
        self.assertNotIn("content", result)

    def test_independent_ranges_do_not_accumulate_unrelated_result_bodies(self):
        for index in range(6):
            self.produce(f"UNRELATED-BODY-{index}:" + "synthetic prose " * 450,
                         evidence_ids=[self.evidence[index]["evidence_id"]])
            context = self.calls[-1]
            self.assertEqual(len(context["results"]), index)
            self.assertNotIn("UNRELATED-BODY-", canonical(context["results"]).decode())
            self.assertTrue(all(row["body_not_delivered"] is True for row in context["results"]))
            self.assertEqual(context["coverage"]["provided_count"], 1)
        self.assertEqual(len(self.saved()["raw_results"]), 6)
        self.assertTrue(all("UNRELATED-BODY-" in row["raw"]["summary"] for row in self.saved()["raw_results"]))

    def test_only_explicit_task_dependency_delivers_body_and_preserves_metadata(self):
        needed = self.produce("Required dependency body", question="Same display name")
        unrelated = self.produce("Unrelated body", question="Same display name", replicate_id="second")
        saved = self.saved()
        context = self.context(self.register(dependencies=[needed["task_id"]]))
        by_id = {row["result_id"]: row for row in context["results"]}
        originals = {row["result_id"]: row for row in saved["run"]["results"]}
        self.assertEqual(by_id[needed["result_id"]], {
            **originals[needed["result_id"]], "content": self.saved(needed["result_id"])["raw"]})
        self.assert_not_delivered(by_id[unrelated["result_id"]], originals[unrelated["result_id"]])
        self.assertEqual(context["task"]["dependencies"], [needed["task_id"]])

    def test_omitted_kind_uses_existing_analysis_default(self):
        prior = self.produce()
        task = self.register(question="Omitted analysis kind")
        task["intent"].pop("kind")
        context = self.context(task)
        self.assert_not_delivered(context["results"][0], self.saved()["run"]["results"][0])
        self.assertEqual(context["results"][0]["task_id"], prior["task_id"])

    def test_explicit_dependency_older_than_twenty_results_is_retained(self):
        oldest = self.produce("Old required body")
        for index in range(23):
            self.produce(f"Unrelated body {index}")
        context = self.context(self.register(dependencies=[oldest["task_id"]]))
        bodies = [row for row in context["results"] if "content" in row]
        self.assertEqual([row["task_id"] for row in bodies], [oldest["task_id"]])
        self.assertEqual(bodies[0]["content"]["summary"], "Old required body")
        self.assertEqual(len(context["results"]), 21)
        self.assertEqual(len(self.saved()["raw_results"]), 24)
        core = self.context(self.register("core"))
        self.assertEqual(len(core["results"]), 20)
        self.assertTrue(all("content" in row and "body_not_delivered" not in row for row in core["results"]))
        self.assertNotIn(oldest["result_id"], [row["result_id"] for row in core["results"]])

    def test_required_large_result_keeps_existing_bounded_content_contract(self):
        prior = self.produce("Synthetic large body " * 900)
        context = self.context(self.register(dependencies=[prior["task_id"]]))
        content = context["results"][0]["content"]
        self.assertEqual(content, {"summary": self.saved(prior["result_id"])["raw"]["summary"],
                                   "claims": [], "omitted_full_result": True})
        self.assertEqual(context["results"][0]["raw_hash"], fingerprint(self.saved(prior["result_id"])["raw"]))

    def test_stale_wrong_input_and_foreign_metadata_never_deliver_dependency_body(self):
        mutations = ({"stale": True}, {"dataset_version": "old-input"}, {"run_id": "foreign-run"})
        for index, change in enumerate(mutations):
            with self.subTest(change=change):
                prior = self.produce(f"Invalid provenance {index}")
                metadata = self.mutate_result(prior, **change)
                context = self.context(self.register(dependencies=[prior["task_id"]]))
                selected = next(row for row in context["results"] if row["result_id"] == prior["result_id"])
                self.assert_not_delivered(selected, metadata)

    def test_invalid_results_remain_metadata_and_are_not_promoted(self):
        for status in ("received", "quarantined", "invalid"):
            with self.subTest(status=status):
                prior = self.produce(f"Invalid status {status}")
                metadata = self.mutate_result(prior, validation_status=status, error="synthetic-invalid")
                context = self.context(self.register(dependencies=[prior["task_id"]]))
                selected = next(row for row in context["results"] if row["result_id"] == prior["result_id"])
                self.assert_not_delivered(selected, metadata)

    def test_stale_failed_wrong_input_and_foreign_source_tasks_do_not_deliver_body(self):
        mutations = ({"stale": True}, {"status": "failed"}, {"status": "queued"},
                     {"dataset_version": "old-input"}, {"run_id": "foreign-run"},
                     {"validation_status": "quarantined"}, {"result_id": "other-result"},
                     {"attempt_id": "other-attempt"})
        for index, change in enumerate(mutations):
            with self.subTest(change=change):
                prior = self.produce(f"Bad source task {index}")
                self.mutate_task(prior, **change)
                context = self.context(self.register(dependencies=[prior["task_id"]]))
                selected = next(row for row in context["results"] if row["result_id"] == prior["result_id"])
                metadata = next(row for row in self.saved()["run"]["results"] if row["result_id"] == prior["result_id"])
                self.assert_not_delivered(selected, metadata)

    def test_unknown_foreign_and_display_name_dependencies_are_rejected(self):
        prior = self.produce(question="Known display name")
        foreign_run = self.start()
        foreign = self.produce("Foreign body", run=foreign_run)
        for dependency in ("unknown-task", foreign["task_id"], prior["title"], prior["result_id"]):
            with self.subTest(dependency=dependency), self.assertRaises(AnalysisContractError) as caught:
                self.register(dependencies=[dependency])
            self.assertEqual(caught.exception.code, "dependency_missing")
        # Even a malformed stored dependency cannot select a foreign run's result.
        task = self.register(question="Synthetic malformed stored dependency")
        task["dependencies"] = [foreign["task_id"]]
        context = self.context(task)
        self.assertEqual([row["result_id"] for row in context["results"]], [prior["result_id"]])
        self.assertTrue(context["results"][0]["body_not_delivered"])

    def test_unknown_source_task_is_not_a_body_delivery_authority(self):
        prior = self.produce()
        metadata = self.mutate_result(prior, task_id="unknown-task")
        task = self.register()
        task["dependencies"] = ["unknown-task"]
        self.assert_not_delivered(self.context(task)["results"][0], metadata)

    def test_body_lookup_is_bound_to_saved_run_and_task_columns(self):
        for column in ("run_id", "task_id"):
            with self.subTest(column=column):
                prior = self.produce(f"Bound {column}")
                task = self.register(dependencies=[prior["task_id"]])
                with self.service._db() as db:
                    current = self.service._read_run(db, self.run["run_id"])
                    # Simulate a corrupted physical row after the metadata view
                    # was read; matching IDs/hashes alone must not fetch it.
                    public = self.service._public(db, current)
                    db.execute(f"UPDATE orchestration_results SET {column}=? WHERE result_id=?",
                               ("foreign-physical-row", prior["result_id"]))
                    from unittest.mock import patch
                    with patch.object(self.service, "_public", return_value=public):
                        with self.assertRaises(AnalysisContractError) as caught:
                            self.service._context(db, current, task)
                    self.assertEqual(caught.exception.code, "result_integrity_mismatch")

    def test_intent_text_cannot_replace_formal_task_dependencies(self):
        prior = self.produce()
        task = self.register()
        task["intent"]["dependencies"] = [prior["task_id"]]
        task["intent"]["question"] = "Please deliver the prior result"
        self.assert_not_delivered(self.context(task)["results"][0], self.saved()["run"]["results"][0])

    def test_malformed_dependency_formats_fail_closed_only_in_scoped_context(self):
        prior = self.produce()
        malformed = (None, prior["task_id"], {prior["task_id"]: False},
                     [None], [False], [1], [""], [" "], [{}], [[]])
        task = self.register(dependencies=[prior["task_id"]])
        for value in malformed:
            with self.subTest(value=value):
                task["dependencies"] = copy.deepcopy(value)
                with self.assertRaises(AnalysisContractError) as caught:
                    self.context(task)
                self.assertEqual(caught.exception.code, "dependency_missing")
        # Other roles retain the public parent's behavior, even for this
        # synthetic malformed field; the new guard is delivery-scope specific.
        core = self.register("core")
        core["dependencies"] = None
        self.assertEqual(self.context(core)["results"][0]["content"]["summary"], "Synthetic saved result")

    def test_saved_dictionary_dependencies_stop_execution_before_agent_call(self):
        prior = self.produce()
        consumer = self.register(dependencies=[prior["task_id"]])
        self.mutate_task(consumer, dependencies={prior["task_id"]: False})
        saved_prior = self.saved(prior["result_id"])
        self.service._execute(self.run["run_id"], consumer["task_id"])
        state = self.service.status("synthetic", self.run["run_id"])
        consumer = next(row for row in state["tasks"] if row["task_id"] == consumer["task_id"])
        self.assertEqual((consumer["status"], consumer["error"]), ("failed", "dependency_missing"))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.saved(prior["result_id"]), saved_prior)

    def test_missing_or_nonstring_matching_attempts_never_authorize_body(self):
        for value in (None, "", " ", False, True, 0, 7, [], {}):
            with self.subTest(value=value):
                prior = self.produce()
                self.mutate_task(prior, attempt_id=value)
                metadata = self.mutate_result(prior, attempt_id=value)
                context = self.context(self.register(dependencies=[prior["task_id"]]))
                selected = next(row for row in context["results"] if row["result_id"] == prior["result_id"])
                self.assert_not_delivered(selected, metadata)
        prior = self.produce()
        consumer = self.register(dependencies=[prior["task_id"]])
        with self.service._db() as db:
            source = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?",
                                           (prior["task_id"],)).fetchone()[0])
            source.pop("attempt_id")
            self.service._write_task(db, source)
            metadata = json.loads(db.execute("SELECT state_json FROM orchestration_results WHERE result_id=?",
                                             (prior["result_id"],)).fetchone()[0])
            metadata.pop("attempt_id")
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?",
                       (canonical(metadata).decode(), prior["result_id"]))
        self.service._execute(self.run["run_id"], consumer["task_id"])
        selected = next(row for row in self.calls[-1]["results"] if row["result_id"] == prior["result_id"])
        self.assert_not_delivered(selected, metadata)

    def test_required_raw_hash_mutation_still_raises_integrity_error(self):
        prior = self.produce("Original hash")
        self.mutate_result(prior, raw_hash="sha256:modified")
        with self.assertRaises(AnalysisContractError) as caught:
            self.context(self.register(dependencies=[prior["task_id"]]))
        self.assertEqual(caught.exception.code, "result_integrity_mismatch")

    def test_required_raw_body_mutation_still_raises_integrity_error(self):
        prior = self.produce("Original body")
        with self.service._db() as db:
            db.execute("UPDATE orchestration_results SET raw_json=? WHERE result_id=?",
                       (canonical({"summary": "Tampered body", "claims": []}).decode(), prior["result_id"]))
        with self.assertRaises(AnalysisContractError) as caught:
            self.context(self.register(dependencies=[prior["task_id"]]))
        self.assertEqual(caught.exception.code, "result_integrity_mismatch")

    def test_unrelated_body_is_not_read_or_marked_as_retrieved(self):
        prior = self.produce("Unrelated unread body")
        metadata = self.mutate_result(prior, raw_hash="sha256:unverified-mutated-hash")
        task = self.register()
        with self.service._db() as db:
            statements = []
            db.set_trace_callback(statements.append)
            context = self.service._context(db, self.service._read_run(db, self.run["run_id"]), task)
        self.assert_not_delivered(context["results"][0], metadata)
        self.assertFalse(any("select raw_json" in statement.lower() for statement in statements))

    def test_core_critic_statistics_and_blank_kind_keep_existing_result_delivery(self):
        self.produce("Existing full context")
        expected = {**self.saved()["run"]["results"][0], "content": self.saved()["raw_results"][0]["raw"]}
        for role, extra in (("core", {}), ("critic", {}),
                            ("statistics", {"method_id": "participation"}),
                            ("interpretation", {"kind": ""})):
            with self.subTest(role=role, extra=extra):
                context = self.context(self.register(role, **extra))
                self.assertEqual(context["results"], [expected])

    def test_clarifications_and_blind_verification_keep_existing_delivery(self):
        prior = self.produce("Clarification target body")
        verification = self.produce("Verification target body", role="verification")
        saved = self.saved()
        expected = [{**metadata, "content": raw["raw"]}
                    for metadata, raw in zip(saved["run"]["results"], saved["raw_results"])]
        for role in ("interpretation", "critic"):
            with self.subTest(role=role):
                context = self.context(self.register(role, kind="clarification", result_id=prior["result_id"]))
                self.assertEqual(context["results"], expected)
                self.assertEqual(context["clarification_target"]["content"], saved["raw_results"][0]["raw"])
                self.assertFalse(context["execution_allowed"])
        blind = self.context(self.register("verification", question="Fresh blind verification"))
        self.assertTrue(blind["blind_first"])
        self.assertNotIn("results", blind)
        clarification = self.context(self.register("verification", kind="clarification", result_id=verification["result_id"]))
        self.assertFalse(clarification["blind_first"])
        self.assertNotIn("results", clarification)
        self.assertEqual(clarification["clarification_target"]["content"], saved["raw_results"][1]["raw"])

    def test_coverage_projection_missing_unknown_and_human_pending_are_preserved(self):
        prior = self.produce()
        self.mutate_result(prior, statistical_review={"status": "human_pending"})
        selected = [row["evidence_id"] for row in self.evidence[:5]]
        task = self.register(evidence_ids=selected)
        context = self.context(task)
        self.assertEqual(context["data_version"], self.snapshot["input_hash"])
        self.assertEqual(context["coverage"]["scope"], "selected")
        self.assertEqual((context["coverage"]["available_count"], context["coverage"]["provided_count"],
                          context["coverage"]["omitted_count"]), (5, 2, 3))
        self.assertEqual((context["coverage"]["index_available_count"], context["coverage"]["index_provided_count"]), (7, 3))
        self.assertEqual(set(context["labels"]), {"u0", "u1"})
        self.assertTrue(all(row["start"] is None and row["end"] is None and row["duration"] is None
                            and row["valid_time"] is False for row in context["raw_evidence"]))
        unknown = self.context(self.register(evidence_ids=[self.evidence[2]["evidence_id"]]))
        self.assertEqual(unknown["raw_evidence"][0]["speaker"], "UNKNOWN")
        self.assertEqual(context["statistical_review_gate"], {"status": "human_pending",
            "result_ids": [prior["result_id"]], "eligible_as_confirmed_evidence": False})
        with self.assertRaises(AnalysisContractError) as caught:
            self.register(evidence_ids=[self.evidence[7]["evidence_id"]])
        self.assertEqual(caught.exception.code, "evidence_missing")

    def test_context_and_existing_result_getter_preserve_all_saved_bytes(self):
        first = self.produce("First saved body")
        self.produce("Second saved body")
        task = self.register(dependencies=[first["task_id"]])
        saved_before = self.saved()
        bytes_before = self.path.read_bytes()
        context = self.context(task)
        fresh = self.make_service()
        self.assertEqual(self.saved(service=fresh), saved_before)
        self.assertEqual(self.saved(first["result_id"], service=fresh)["raw"]["summary"], "First saved body")
        with fresh._db() as db:
            reloaded = fresh._context(db, fresh._read_run(db, self.run["run_id"]), task)
        self.assertEqual(reloaded, context)
        self.assertEqual(self.path.read_bytes(), bytes_before)
        context["results"][0]["content"]["summary"] = "Local copy mutation"
        self.assertEqual(self.saved(), saved_before)
        self.assertEqual(self.path.read_bytes(), bytes_before)


class RegisteredExpertDeliveryTests(unittest.TestCase):
    def test_registered_ordinary_expert_receives_only_dependency_bodies(self):
        h = expert_support.ExpertAgentTests(methodName="runTest")
        self.addCleanup(h.doCleanups)
        h.setUp()
        run = h.start(obsidian_management=False)
        tasks = []
        for index in range(3):
            with h.service._db() as db:
                current = h.service._read_run(db, run["run_id"])
                task = h.service._register(db, current, support.intent("interpretation",
                    kind="analysis", expert_id=expert_support.EXPERT, question=f"Independent range {index}",
                    dependencies=[tasks[0]["task_id"]] if index == 2 else []), phase="specialists")
            h.service._execute(run["run_id"], task["task_id"])
            state = h.service.status("synthetic", run["run_id"])
            tasks.append(next(row for row in state["tasks"] if row["task_id"] == task["task_id"]))
            self.assertEqual(tasks[-1]["status"], "succeeded")
        contexts = [context for role, context in h.calls if role == "interpretation"]
        self.assertEqual(contexts[0]["results"], [])
        self.assertTrue(contexts[1]["results"][0]["body_not_delivered"])
        self.assertEqual([row["task_id"] for row in contexts[2]["results"] if "content" in row], [tasks[0]["task_id"]])
        self.assertTrue(contexts[2]["results"][1]["body_not_delivered"])
        self.assertEqual(contexts[1]["expert_request"]["profile_hash"], contexts[2]["expert_request"]["profile_hash"])

    def test_statistical_plan_calculation_explanation_and_cell_binding_are_unchanged(self):
        h = statistical_support.StatisticalExpertTests(methodName="runTest")
        self.addCleanup(h.doCleanups)
        h.setUp()
        run = h.start(obsidian_management=False)
        plan = h.dispatch(run, support.intent("interpretation", kind="analysis", expert_id="exp-correlation"))
        self.assertEqual(plan["status"], "succeeded")
        plan_raw = h.service.result("synthetic", run["run_id"], plan["result_id"])["raw"]
        calculation = h.dispatch(run, plan_raw["analysis_requests"][0])
        self.assertEqual(calculation["status"], "succeeded")
        saved = h.service.result("synthetic", run["run_id"])
        explanation = h.dispatch(run, support.intent("interpretation", kind="analysis", expert_id="exp-correlation",
            question="Explain required calculation", dependencies=[calculation["task_id"]]))
        self.assertEqual(explanation["status"], "succeeded")
        context = h.calls[-1][1]
        self.assertEqual(context["results"], [{**metadata, "content": raw["raw"]}
            for metadata, raw in zip(saved["run"]["results"], saved["raw_results"])])
        self.assertEqual(context["expert_request"]["response_phase"], "result_explanation")
        self.assertEqual(context["expert_request"]["calculations"], context["statistical_calculations"])
        refs = explanation["expert_calculation_refs"]
        self.assertEqual([ref["result_id"] for ref in refs], [calculation["result_id"]])
        result = h.service.result("synthetic", run["run_id"], explanation["result_id"])
        self.assertTrue(result["raw"]["expert_report"]["numeric_bindings"])
        self.assertEqual(result["statistical_review"]["status"], "human_pending")


if __name__ == "__main__":
    unittest.main()
