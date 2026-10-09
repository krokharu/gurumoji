"""Domain advisers, real Python calculations, and fixed result provenance."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.method_experts import ExpertCatalog
from gurumoji.research_analysis import build_research_statistics
from gurumoji.services.analysis_orchestration_methods import (
    STATISTICAL_TOOLS, EXPERT_STATISTICAL_TOOLS, run_orchestration_method,
)
from gurumoji.services.expert_agents import ExpertAgentRegistry, cell_binding
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters
import test_analysis_orchestration as fixtures

ROOT = Path(__file__).resolve().parents[1]


def tool_intent(method):
    return {"role": "statistics", "kind": "analysis", "result_id": "", "initial_sections": [],
            "question": "Retrieve the fixed statistical table", "why_now": "Check the proposed analysis",
            "success_criteria": "Report values, missingness and limits", "expert_id": "", "method_id": method,
            "label_field": "", "evidence_ids": [], "importance": "high", "importance_reason": "Needed for explanation",
            "dependencies": [], "label_dependent": False, "replicate_id": ""}


class StatisticalExpertTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = ExpertCatalog(root=ROOT / "docs/program-vault", local_root=self.root / "local")
        self.registry = ExpertAgentRegistry(self.catalog)
        self.analysis = {"segments": [
            {"id": f"u{i}", "speaker": "A" if i < 3 else "B", "text": "x" * count,
             "characters": count, "duration": i + 2, "valid_time": i != 1, "excluded": False,
             "question_candidate": i % 2 == 0, "annotation": {}}
            for i, count in enumerate((5, 9, 13, 20, 30, 40))],
            "config": {"statistics_group_by": "speaker"}, "manual": {"codebook": []},
            "automatic": {"overview": {"included_segment_count": 6, "speaker_count": 2}},
            "research": {"linguistics": {"morphemes": [], "engine": {"status": "fallback"}}}}
        self.analysis["segments"].append({"id": "excluded", "speaker": "C", "text": "excluded",
                                         "characters": 10000, "excluded": True})
        stage = build_research_statistics(self.analysis, self.analysis["research"]["linguistics"])
        self.analysis["research"].update(stage)
        self.snap = {"input_hash": "v1", "source_revision": 1, "analysis_revision": 1, "analysis": self.analysis}
        self.calls = []
        self.service = AnalysisOrchestrationService(
            connect=lambda: sqlite3.connect(self.root / "test.sqlite3"), find_item=lambda _: {"id": "synthetic"},
            snapshot_builder=lambda _: copy.deepcopy(self.snap), source_fingerprint=lambda _: "v1",
            method_runner=run_orchestration_method, agent_runner=self.agent, schedule=False,
            expert_provider=self.registry.freeze)

    def start(self, expert="exp-correlation", **kwargs):
        return self.service.start("synthetic", {"model": "fixture", "expert_ids": [expert],
            "question": "Explore this synthetic dataset", "time_limit_seconds": None, "max_calls": 25, **kwargs})

    def dispatch(self, run, intent):
        with self.service._db() as db:
            saved = self.service._read_run(db, run["run_id"])
            task = self.service._register(db, saved, intent, phase="specialists")
        self.service._execute(run["run_id"], task["task_id"])
        state = self.service.status("synthetic", run["run_id"])
        return next(t for t in state["tasks"] if t["task_id"] == task["task_id"])

    def expert_report(self, context):
        packet = context["expert_request"]
        profile = packet["knowledge"]
        calculations = packet["calculations"]
        ready = bool(calculations)
        bindings = []
        for calculation in calculations:
            name, table = next(iter(calculation["datasets"].items()))
            row = table["rows"][0]
            column = {"descriptives": "mean", "frequencies": "count", "crosstabs": "count",
                      "tests": "statistic", "correlations": "coefficient"}[name]
            bindings.append(cell_binding(calculation, name, row, column))
        return {"summary": "Synthetic statistical explanation" if ready else "Calculation requested",
            "claims": [], "label_patches": [],
            "analysis_requests": [] if ready else [tool_intent(profile["statistical_tools"][0])],
            "expert_report": {"expert_id": profile["expert_id"], "profile_hash": profile["profile_hash"],
                "knowledge_hash": profile["knowledge_hash"], "status": "draft" if ready else "needs_calculation",
                "outputs": {name: "Synthetic bounded explanation" for name in profile["output_schema"]["properties"]},
                "evidence_ids": [context["raw_evidence"][0]["evidence_id"]],
                "knowledge_note_ids": [profile["knowledge"][0]["note_id"]],
                "performed_step_ids": [profile["allowed_steps"][1 if ready else 0]["id"]],
                "missing_inputs": [], "limitations": "Exploratory; independent observations are unverified.",
                "calculation_result_ids": [row["result_id"] for row in calculations], "numeric_bindings": bindings}}

    def agent(self, role, context, *args):
        self.calls.append((role, copy.deepcopy(context)))
        if role == "interpretation":
            return self.expert_report(context)
        if role == "critic":
            return fixtures.critic(context)
        return fixtures.stop()

    def test_default_nine_experts_keep_code_and_human_steps_separate(self):
        bundle = self.registry.freeze({})
        self.assertEqual(len(bundle["profiles"]), 9)
        for eid in EXPERT_STATISTICAL_TOOLS:
            profile = bundle["profiles"][eid]
            self.assertTrue(profile["knowledge"])
            self.assertEqual(len(profile["allowed_steps"]), 2)
            self.assertTrue(all(step["actor"] == "ai_draft" for step in profile["allowed_steps"]))
            self.assertTrue(profile["human_steps"])
            self.assertTrue(any(step["actor"] == "code" for step in self.catalog.definition(eid)["procedure"]))
        # The public configuration accepts nine choices and still rejects ten.
        run = self.service.start("synthetic", {
            "model": "fixture", "question": "Synthetic", "expert_ids": list(bundle["profiles"])})
        self.assertEqual(len(run["expert_agents"]["experts"]), 9)
        with self.assertRaises(AnalysisContractError):
            self.service.start("synthetic", {"model": "fixture", "expert_ids": list(bundle["profiles"]) + ["exp-extra"]})

    def test_all_eight_tools_use_real_engine_and_preserve_missing_and_excluded(self):
        run = self.start()
        for method in STATISTICAL_TOOLS:
            task = self.dispatch(run, tool_intent(method))
            self.assertEqual(task["status"], "succeeded", task)
            raw = self.service.result("synthetic", run["run_id"], task["result_id"])["raw"]
            self.assertEqual(raw["manifest"]["included_count"], 6)
            self.assertEqual(raw["manifest"]["excluded_count"], 1)
            self.assertEqual(len(raw["manifest"]["evidence_ids"]), 6)
            rows = next(iter(raw["datasets"].values()))["rows"]
            self.assertTrue(rows, method)
            if method == "descriptive_statistics":
                duration = next(row for row in rows if row["scope"] == "overall" and row["variable"] == "duration_seconds")
                self.assertEqual(duration["missing"], 1)
                self.assertEqual(duration["n"], 5)
                characters = next(row for row in rows if row["scope"] == "overall" and row["variable"] == "characters")
                self.assertEqual(characters["maximum"], 40)
                self.assertEqual(characters["mean"], 19.5)
            if method in {"pearson", "spearman"}:
                self.assertTrue(all(row["method"] == ("Pearson" if method == "pearson" else "Spearman") for row in rows))
        self.assertEqual(self.calls, [])

    def test_each_domain_plan_calculation_then_explanation_has_fixed_result_reference(self):
        for eid, tools in EXPERT_STATISTICAL_TOOLS.items():
            run = self.start(eid)
            before = copy.deepcopy(self.analysis)
            plan = self.dispatch(run, fixtures.intent("interpretation", expert_id=eid))
            self.assertEqual(plan["status"], "succeeded", plan)
            raw = self.service.result("synthetic", run["run_id"], plan["result_id"])["raw"]
            self.assertEqual(raw["expert_report"]["status"], "needs_calculation")
            self.assertEqual(len(self.service.status("synthetic", run["run_id"])["tasks"]), 1)
            calculation = self.dispatch(run, raw["analysis_requests"][0])
            explanation = self.dispatch(run, fixtures.intent("interpretation", expert_id=eid,
                question="Explain the verified calculation", dependencies=[calculation["task_id"]]))
            self.assertEqual(explanation["status"], "succeeded", explanation)
            raw = self.service.result("synthetic", run["run_id"], explanation["result_id"])["raw"]
            self.assertEqual(raw["expert_report"]["calculation_result_ids"], [calculation["result_id"]])
            self.assertEqual(before, self.analysis)

    def test_core_routing_uses_specialist_proposal_and_formal_calculation_tasks(self):
        eid = "exp-correlation"
        def agent(role, context, *args):
            if role != "core":
                return self.agent(role, context, *args)
            self.calls.append((role, copy.deepcopy(context)))
            reports = [r for r in context["results"] if r["role"] == "interpretation"]
            calculations = [r for r in context["results"] if r["role"] == "statistics"]
            if not reports:
                return fixtures.core(intents=[fixtures.intent("interpretation", expert_id=eid)])
            if not calculations:
                return fixtures.core(intents=reports[-1]["content"]["analysis_requests"])
            if len(reports) == 1:
                return fixtures.core(intents=[fixtures.intent("interpretation", expert_id=eid,
                    question="Explain the verified calculation", dependencies=[calculations[0]["task_id"]])])
            return fixtures.stop()
        self.service.agent_runner = agent
        run = self.start()
        self.service.run(run["run_id"])
        state = self.service.status("synthetic", run["run_id"])
        self.assertEqual(state["status"], "stopped", state.get("error"))
        self.assertEqual(state["stop_reason"], "human_review_required")
        self.assertEqual(len([t for t in state["tasks"] if t["role"] == "statistics"]), 1)
        self.assertEqual(len([r for r, _ in self.calls if r == "interpretation"]), 2)

    def test_draft_without_calculation_and_wrong_domain_tool_are_quarantined(self):
        original = self.expert_report
        for mutation in (lambda raw: raw["expert_report"].update(status="draft"),
                         lambda raw: raw["analysis_requests"][0].update(method_id="chi_square"),
                         lambda raw: raw["analysis_requests"][0].update(dependencies=["invented"]),
                         lambda raw: raw["expert_report"].update(calculation_result_ids=["invented"]),
                         lambda raw: raw["expert_report"].update(performed_step_ids=["cor-p2"])):
            def bad(context, mutate=mutation):
                raw = original(context)
                mutate(raw)
                return raw
            self.expert_report = bad
            task = self.dispatch(self.start(), fixtures.intent("interpretation", expert_id="exp-correlation"))
            self.assertEqual(task["status"], "quarantined", task)
        self.expert_report = original

    def test_foreign_run_results_and_wrong_method_are_not_supplied(self):
        first = self.start()
        calculation = self.dispatch(first, tool_intent("pearson"))
        second = self.start()
        plan = self.dispatch(second, fixtures.intent("interpretation", expert_id="exp-correlation"))
        self.assertEqual(plan["status"], "succeeded")
        self.assertEqual(self.calls[-1][1]["expert_request"]["calculations"], [])
        other = self.dispatch(second, tool_intent("chi_square"))
        plan = self.dispatch(second, fixtures.intent("interpretation", expert_id="exp-correlation",
            question="Check results", dependencies=[other["task_id"]]))
        self.assertEqual(self.calls[-1][1]["expert_request"]["calculations"], [])
        with self.service._db() as db:
            saved = self.service._read_run(db, second["run_id"])
            with self.assertRaises(AnalysisContractError):
                self.service._register(db, saved, fixtures.intent("interpretation", expert_id="exp-correlation",
                    dependencies=[calculation["task_id"]]), phase="specialists")

    def test_not_applicable_cannot_claim_to_have_performed_result_explanation(self):
        run = self.start()
        calc = self.dispatch(run, tool_intent("pearson"))
        original = self.expert_report
        def bad(context):
            raw = original(context)
            raw["expert_report"]["status"] = "not_applicable"
            return raw
        self.expert_report = bad
        task = self.dispatch(run, fixtures.intent("interpretation", expert_id="exp-correlation", dependencies=[calc["task_id"]]))
        self.assertEqual(task["status"], "quarantined")
        self.assertEqual(task["error"], "expert_report_state_mismatch")

    def test_result_tamper_and_partial_scope_are_rejected(self):
        run = self.start()
        with self.service._db() as db:
            saved = self.service._read_run(db, run["run_id"])
            evidence = self.service._initial(db, saved["initial_id"])["evidence"]
            with self.assertRaises(AnalysisContractError):
                self.service._register(db, saved, tool_intent("pearson") | {"evidence_ids": [evidence[0]["evidence_id"]]}, phase="specialists")
        calc = self.dispatch(run, tool_intent("pearson"))
        with self.service._db() as db:
            db.execute("UPDATE orchestration_results SET raw_json=? WHERE result_id=?", ('{"tampered":true}', calc["result_id"]))
        task = self.dispatch(run, fixtures.intent("interpretation", expert_id="exp-correlation", dependencies=[calc["task_id"]]))
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error"], "result_integrity_mismatch")
        self.assertEqual(self.calls, [])

    def test_missing_engine_or_fixed_morphemes_never_become_success(self):
        self.analysis["research"]["statistics"]["engine"]["status"] = "unavailable"
        run = self.start()
        task = self.dispatch(run, fixtures.intent("interpretation", expert_id="exp-correlation"))
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error"], "expert_not_applicable")
        self.assertEqual(self.calls, [])
        del self.analysis["research"]["linguistics"]["morphemes"]
        # Changed inputs get a new identity; the old fixed snapshot is reusable.
        self.snap["input_hash"] = "v2"
        self.service.source_fingerprint = lambda _: "v2"
        run = self.start("exp-descriptive-statistics")
        task = self.dispatch(run, tool_intent("descriptive_statistics"))
        self.assertEqual(task["status"], "failed")
        self.assertIsNone(task.get("result_id"))

    def test_local_and_cloud_get_same_calculation_schema_and_bounded_tables(self):
        from types import SimpleNamespace
        run = self.start()
        calc = self.dispatch(run, tool_intent("pearson"))
        self.dispatch(run, fixtures.intent("interpretation", expert_id="exp-correlation", dependencies=[calc["task_id"]]))
        context = self.calls[-1][1]
        calls = []
        resolve, runner = make_orchestration_adapters(call_ai_json=lambda *args: calls.append(args) or {},
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1"),
            configured_ai_credentials=lambda *_: ("synthetic", "synthetic"))
        for provider in ("lmstudio", "openai", "google"):
            runner("interpretation", context, resolve({"provider": provider, "provider_policy": "cloud_allowed", "cloud_consent": True}), lambda: None, lambda _: None)
        self.assertEqual(calls[0][3:7], calls[1][3:7])
        self.assertEqual(calls[1][3:7], calls[2][3:7])
        schema = calls[0][6]
        self.assertEqual(schema["properties"]["expert_report"]["properties"]["calculation_result_ids"]["items"]["enum"], [calc["result_id"]])
        self.assertEqual(schema["properties"]["claims"]["maxItems"], 0)
        report_properties = schema["properties"]["expert_report"]["properties"]
        self.assertEqual(set(report_properties["numeric_bindings"]["items"]["properties"]), {
            "result_id", "dataset", "row_id", "column", "variables", "target", "dataset_version", "computation_input_hash", "rows_hash"})
        self.assertEqual(report_properties["performed_step_ids"]["items"]["enum"], ["cor-ai-report"])
        for handler_field in ("statistical_review", "human_pending", "rendered_cells", "researcher_records"):
            self.assertNotIn(handler_field, report_properties)
        packet = json.loads(calls[0][4])
        self.assertNotIn("results", packet)
        self.assertLessEqual(len(packet["expert_request"]["calculations"][0]["datasets"]["correlations"]["rows"]), 40)
        self.assertEqual(packet["expert_request"]["phase_requirements"]["ai_draft"], ["cor-ai-report"])
        self.assertEqual(packet["expert_request"]["numeric_binding"]["render_policy"], "statistical-cells-v1")


if __name__ == "__main__":
    unittest.main()
