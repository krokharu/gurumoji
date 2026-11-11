"""合成発話で話者×ラベルのクロス集計と欠測の契約を検証する。"""
import copy
import json
import sqlite3
import unittest
import jsonschema

from gurumoji.analysis_core import fingerprint
from gurumoji.services.analysis_orchestration_methods import run_orchestration_method
from gurumoji.services import metric_delivery
from gurumoji.services.orchestration_required_methods import required_progress
from gurumoji.services.analysis_orchestration_adapters import INTENT, _bind_required_crosstab
import test_analysis_orchestration as fixture
import test_required_methods_integration as required_fixture
from test_metric_delivery import case


def sample():
    segments = [("A", ["価格", "味", "価格"]), ("A", ["価格"]), ("A", []),
                ("B", ["味"]), ("B", ["価格", "味"]), ("B", ["味"]),
                ("UNKNOWN", ["価格"]), ("C", []), ("D", ["除外された秘密"])]
    return {"evidence": [{"evidence_id": f"e{i}", "utterance_id": f"u{i}",
                          "speaker": speaker, "excluded": i == 9}
                         for i, (speaker, _) in enumerate(segments, 1)],
            "orchestration_task": {"intent": {"label_field": "codes", "evidence_ids": []},
                                   "dataset_version": "version", "annotation_version": 0, "codebook_version": 1},
            "orchestration_labels": {f"u{i}": {"codes": labels}
                                     for i, (_, labels) in enumerate(segments, 1)}}


class CrossTabCalculationTests(unittest.TestCase):
    def test_known_matrix_and_denominators_and_missing_union(self):
        snapshot = sample()
        original = copy.deepcopy(snapshot)
        result = run_orchestration_method("cross_tabulation", snapshot)
        self.assertEqual((result["denominator"], result["observed_count"], result["missing_count"]), (8, 5, 3))
        self.assertEqual((result["missing_speaker_count"], result["missing_label_count"]), (1, 2))
        self.assertEqual(result["missing_evidence_ids"], ["e3", "e7", "e8"])
        cells = {(r["speaker"], r["label"]): r for r in result["rows"]}
        self.assertEqual({k: v["count"] for k, v in cells.items()},
                         {("A", "価格"): 2, ("A", "味"): 1, ("B", "価格"): 1,
                          ("B", "味"): 3, ("C", "価格"): 0, ("C", "味"): 0})
        self.assertEqual(cells["A", "価格"]["row_proportion"], 2 / 3)
        self.assertEqual(cells["A", "味"]["column_proportion"], 1 / 4)
        self.assertEqual(cells["B", "味"]["proportion"], 3 / 8)
        self.assertIsNone(cells["C", "価格"]["row_proportion"])
        self.assertEqual(result["total_assignments"], 7)
        self.assertEqual({r["label"]: r["count"] for r in result["column_totals"]}, {"価格": 3, "味": 4})
        self.assertEqual(result["availability"], "partial")
        self.assertNotIn("除外された秘密", str(result))
        self.assertEqual(snapshot, original)

    def test_subset_recounts_the_requested_evidence_and_versions(self):
        snapshot = sample()
        snapshot["orchestration_task"]["intent"]["evidence_ids"] = ["e2", "e5"]
        result = run_orchestration_method("cross_tabulation", snapshot)
        self.assertEqual((result["denominator"], result["missing_count"]), (2, 0))
        self.assertEqual(result["availability"], "computed")
        self.assertEqual(result["manifest"]["scope"], "selected")
        snapshot["orchestration_task"]["annotation_version"] = 1
        snapshot["orchestration_labels"]["u2"]["codes"] = ["味"]
        revised = run_orchestration_method("cross_tabulation", snapshot)
        self.assertEqual(next(r["count"] for r in revised["rows"] if r["speaker"] == "A" and r["label"] == "価格"), 0)
        self.assertEqual((result["annotation_version"], revised["annotation_version"]), (0, 1))

    def test_missing_dimensions_never_become_zero_or_a_category(self):
        for field in ("speaker", "codes"):
            snapshot = sample()
            if field == "speaker":
                for row in snapshot["evidence"]:
                    row["speaker"] = None
            else:
                snapshot["orchestration_labels"] = {}
            result = run_orchestration_method("cross_tabulation", snapshot)
            self.assertEqual(result["availability"], "unavailable")
            self.assertEqual((result["observed_count"], result["missing_count"]), (0, 8))
            self.assertEqual(result["rows"], [])

    def test_missing_dimensions_are_counted_once_per_utterance(self):
        snapshot = sample()
        snapshot["orchestration_labels"]["u7"]["codes"] = []
        result = run_orchestration_method("cross_tabulation", snapshot)
        self.assertEqual((result["missing_count"], result["missing_speaker_count"], result["missing_label_count"]), (3, 1, 3))

    def test_invalid_scope_and_fields_are_rejected(self):
        for ids in (["e9"], ["absent"]):
            snapshot = sample()
            snapshot["orchestration_task"]["intent"]["evidence_ids"] = ids
            with self.assertRaises(ValueError):
                run_orchestration_method("cross_tabulation", snapshot)
        snapshot = sample()
        snapshot["orchestration_task"]["intent"]["label_field"] = "memo"
        with self.assertRaises(ValueError):
            run_orchestration_method("cross_tabulation", snapshot)

    def test_real_metric_encoder_and_decoder_keep_cell_counts_and_missing(self):
        raw = run_orchestration_method("cross_tabulation", sample())
        context = case()
        source = {"result_id": "cross-result", "role": "statistics", "validation_status": "valid",
                  "raw_hash": fingerprint(raw), "content": raw}
        context["results"] = [source]
        context["iteration_review"]["pending_result_ids"] = [source["result_id"]]
        public, contract, schema = metric_delivery.prepare(context)
        bindings = contract["state"]["bindings"]
        cell = next(b for b in bindings if b["record"]["source_ref"].endswith("/rows/0/count"))
        self.assertEqual(cell["record"]["value"], "2")
        self.assertEqual((cell["record"]["population_count"], cell["record"]["missing_count"]), (3, 1))
        unknown = next(b for b in bindings if b["record"]["source_ref"].endswith("/rows/4/count"))
        self.assertIsNone(unknown["record"]["value"])
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.execute("CREATE TABLE orchestration_results(result_id TEXT,run_id TEXT,raw_json TEXT,state_json TEXT)")
        db.execute("INSERT INTO orchestration_results VALUES(?,?,?,?)", (source["result_id"], "run-synthetic",
                   json.dumps(raw), json.dumps({k: v for k, v in source.items() if k != "content"})))
        task = context["task"]
        task["context_manifest"] = {"metric_contract": contract, "requested_result_ids": [source["result_id"]]}
        run = {"run_id": "run-synthetic", "initial_id": "initial", "input_hash": "version",
               "config": {"metric_codec_version": 1}}
        decoded = metric_delivery.validate(db, run, task, {"claims": [], "metric_selections": {
            "source_1": {"operation": "value", "operands": [cell["ref"]], "value": "2"}}})
        self.assertEqual(decoded["status"], "answered")
        self.assertTrue(public["metric_context"]["sources"][0]["refs"])
        self.assertIn("source_1", schema["required"])

    def test_required_cross_table_is_stale_after_label_or_codebook_change(self):
        task = {"role": "statistics", "method_id": "cross_tabulation", "task_id": "task", "result_id": "result",
                "status": "succeeded", "validation_status": "valid", "dataset_version": "version",
                "annotation_version": 0, "codebook_version": 1}
        results = [{"result_id": "result", "validation_status": "valid", "calculation": {"availability": "computed"}}]
        decisions = [{"role": "orchestrator", "result_id": "report", "result_assessments": [
            {"result_id": "result", "disposition": "adopt", "reason": "件数を確認"}]},
            {"role": "core", "domain_report_ids": ["report"]}]
        def progress(annotation, codebook):
            return required_progress(["cross_tabulation"], [task], results, decisions,
                dataset_version="version", annotation_version=annotation, codebook_version=codebook)[0]
        self.assertTrue(progress(0, 1)["complete"])
        self.assertFalse(progress(1, 1)["complete"])
        self.assertFalse(progress(0, 2)["complete"])
        task["intent"] = {"label_field": "codes", "evidence_ids": ["e1"]}
        self.assertFalse(progress(0, 1)["complete"])
        task["intent"] = {"label_field": "sentiment", "evidence_ids": []}
        self.assertFalse(progress(0, 1)["complete"])

    def test_generation_schema_keeps_the_required_column_without_restricting_frequency(self):
        schema = _bind_required_crosstab(INTENT)
        intent = {"role": "statistics", "kind": "analysis", "result_id": "", "initial_sections": [],
                  "question": "クロス表", "why_now": "確認", "success_criteria": "件数と欠測を照合",
                  "method_id": "cross_tabulation", "label_field": "codes", "evidence_ids": [],
                  "importance": "high", "importance_reason": "必須", "dependencies": [],
                  "label_dependent": True, "replicate_id": ""}
        jsonschema.validate(intent, schema)
        intent["label_field"] = "code"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(intent, schema)
        intent["method_id"] = "label_frequency"
        jsonschema.validate(intent, schema)
        self.assertEqual(INTENT["anyOf"][1]["properties"]["label_field"]["enum"][0], "code")


class CrossTabIntegrationTests(unittest.TestCase):
    connect = fixture.RuntimeTests.connect
    build = fixture.RuntimeTests.build
    run_agent = fixture.RuntimeTests.run_agent
    make_service = fixture.RuntimeTests.make_service
    start = fixture.RuntimeTests.start
    drive = fixture.RuntimeTests.drive

    def method(self, name, snapshot):
        return run_orchestration_method(name, snapshot)

    def setUp(self):
        fixture.RuntimeTests.setUp(self)
        self.agent = lambda *args: required_fixture.RequiredMethodsIntegrationTests.agent_response(self, *args)

    def test_gui_required_method_reaches_real_calculation_review_and_core(self):
        original = copy.deepcopy(self.snapshot)
        run = self.drive(self.start(required_methods=["cross_tabulation"],
                                    specialist_orchestration_version=1, core_progress_version=1,
                                    max_calls=60, max_tasks=80))
        self.assertTrue(run["analysis_processing_complete"], run)
        progress = run["required_methods_progress"][0]
        self.assertEqual(progress["calculation"], {"availability": "partial", "denominator": 2,
                                                 "observed_count": 1, "missing_count": 1})
        self.assertTrue(progress["complete"])
        self.assertTrue(progress["core_integrated"])
        self.assertEqual(progress["review"]["disposition"], "adopt")
        raw = self.service.result("conversation", run["run_id"], progress["result_id"])["raw"]
        self.assertEqual({(r["speaker"], r["label"]): r["count"] for r in raw["rows"]},
                         {("A", "manual"): 1, ("B", "manual"): 0})
        self.assertEqual(self.snapshot, original)
        self.item["revision"] = "changed-input"
        stale = self.service.status("conversation", run["run_id"])
        self.assertFalse(stale["required_methods_progress"][0]["complete"])

    def test_all_missing_is_not_a_completed_required_cross_tabulation(self):
        for row in self.snapshot["analysis"]["segments"]:
            row["annotation"]["codes"] = []
        run = self.drive(self.start(required_methods=["cross_tabulation"],
                                    specialist_orchestration_version=1, core_progress_version=1,
                                    max_calls=60, max_tasks=80))
        self.assertFalse(run.get("analysis_processing_complete", False))
        self.assertEqual(run["stop_reason"], "required_methods_incomplete")
        progress = run["required_methods_progress"][0]
        self.assertEqual(progress["calculation"]["availability"], "unavailable")
        self.assertFalse(progress["complete"])

    def test_reworded_full_cross_tabulation_reuses_the_fixed_result(self):
        original = self.agent
        def agent(role, context, *args):
            response = original(role, context, *args)
            if role == "orchestrator" and context.get("review_domain") == "statistics":
                response["intents"] = [fixture.intent("statistics", "表現を変えた同じ集計",
                    method_id="cross_tabulation", label_field="codes", label_dependent=True,
                    evidence_ids=[row["evidence_id"] for row in context["raw_evidence"]])]
            return response
        self.agent = agent
        run = self.drive(self.start(required_methods=["cross_tabulation"],
                                    specialist_orchestration_version=1, core_progress_version=1,
                                    max_calls=60, max_tasks=80))
        self.assertTrue(run["analysis_processing_complete"], run)
        self.assertEqual(len([t for t in run["tasks"] if t["method_id"] == "cross_tabulation"]), 1)
        self.assertTrue(any(event["type"] == "duplicate_suppressed" for event in run["events"]))

    def test_handler_rejects_a_changed_required_column_even_without_provider_schema(self):
        original = self.agent
        def agent(role, context, *args):
            response = original(role, context, *args)
            if role == "orchestrator" and context.get("review_domain") == "statistics":
                response["intents"] = [fixture.intent("statistics", "別列への変更",
                    method_id="cross_tabulation", label_field="code", label_dependent=True)]
            return response
        self.agent = agent
        run = self.drive(self.start(required_methods=["cross_tabulation"],
                                    specialist_orchestration_version=1, core_progress_version=1,
                                    max_calls=60, max_tasks=80))
        self.assertFalse(run.get("analysis_processing_complete", False))
        self.assertTrue(any(t.get("error") == "required_method_spec_mismatch" for t in run["tasks"]))

    def test_initial_three_methods_and_label_workflow_coexist_with_required_cross_table(self):
        self.method = lambda name, snapshot: (run_orchestration_method(name, snapshot)
            if name == "cross_tabulation" else fixture.RuntimeTests.method(self, name, snapshot))
        self.service = self.make_service()
        run = self.drive(self.start(required_methods=["cross_tabulation"],
                                    specialist_orchestration_version=1, core_progress_version=1,
                                    initial_label_definitions_version=1, initial_specialist_analysis_version=1,
                                    max_calls=100, max_tasks=120))
        self.assertTrue(run["analysis_processing_complete"], run)
        self.assertTrue(run["required_methods_progress"][0]["complete"])
        initial = [task for task in run["tasks"] if task["phase"] == "initial_analysis" and task["role"] == "statistics"]
        self.assertEqual({task["method_id"] for task in initial}, {"participation", "conversation_dynamics", "label_frequency"})
        self.assertEqual(len([task for task in run["tasks"] if task["method_id"] == "cross_tabulation"]), 1)


if __name__ == "__main__":
    unittest.main()
