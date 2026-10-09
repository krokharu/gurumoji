"""Synthetic capacity, evidence coverage and durable packet tests; no real Vault."""
import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services import model_context
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters, ADAPTER_VERSION
import test_analysis_orchestration as fixtures


class ContextTests(unittest.TestCase):
    def adapter(self, meter, reply=lambda *_: {"summary": "synthetic"}):
        resolve, runner = make_orchestration_adapters(call_ai_json=reply,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"), context_meter=meter)
        return lambda payload: resolve({"specialist_orchestration_version": 0, "context_reference_version": 0, **payload}), runner

    def test_mandatory_oversized_initial_page_is_never_dispatched_or_truncated(self):
        calls, recorded = [], []
        resolve, runner = self.adapter(lambda *_: {"fits": False}, lambda *a, **k: calls.append(a))
        context = {"task": {"phase": "initial_analysis"}, "data_version": "version",
                   "raw_evidence": [{"evidence_id": "e1", "text": "日本語"}, {"evidence_id": "e2", "text": "例外"}]}
        with self.assertRaises(AnalysisContractError) as caught:
            runner("interpretation", context, resolve({"model_context_version": 1}), lambda: None, recorded.append)
        self.assertEqual(caught.exception.code, "context_budget_exceeded")
        self.assertEqual(calls, [])
        self.assertEqual(recorded[0]["context_manifest"]["provided_evidence_ids"], ["e1", "e2"])
        self.assertEqual(context["raw_evidence"][1]["text"], "例外")

    def test_result_batches_keep_order_and_pending_remainder(self):
        calls, recorded = [], []
        def meter(model, base, system, user, schema):
            count = len(json.loads(user)["results"])
            return {"fits": count <= 1, "output_reserve": 1600}
        resolve, runner = self.adapter(meter, lambda *a, **k: calls.append((a, k)))
        context = {"task": {"phase": "core", "role": "core"}, "data_version": "v",
            "results": [{"result_id": str(i), "content": {"claims": []}} for i in range(4)],
            "issues": [{"issue_id": "i0", "result_id": "0"}, {"issue_id": "i3", "result_id": "3"}],
            "iteration_review": {"pending_result_ids": [str(i) for i in range(4)], "omitted_pending_result_count": 0}}
        runner("core", context, resolve({"model_context_version": 1}), lambda: None, recorded.append)
        sent = json.loads(calls[0][0][4])
        self.assertEqual(sent["iteration_review"]["pending_result_ids"], ["0"])
        self.assertEqual(sent["iteration_review"]["omitted_pending_result_count"], 3)
        self.assertEqual([issue["issue_id"] for issue in sent["issues"]], ["i0"])
        self.assertEqual(sent["issue_scope"]["unread_result_issue_count"], 1)
        self.assertEqual(recorded[0]["context_manifest"]["provided_issue_ids"], ["i0"])
        self.assertEqual(calls[0][1]["max_output_tokens"], 1600)
        self.assertEqual(calls[0][0][6]["properties"]["result_assessments"]["maxItems"], 1)
        self.assertEqual(len(context["results"]), 4)

    def test_routing_preserves_requirements_and_provenance_without_integration_payload(self):
        report = {"reports": [{"role": "critic", "summary": "verbose" * 100,
                               "result_id": "r", "raw_hash": "hash", "requirement_count": 1}],
                  "label_requirements": [{"reason": "条件", "exceptions": ["例外"], "sources": ["r"]}]}
        context = {"task": {"phase": "initial_routing", "role": "core"}, "raw_evidence": ["private"],
                   "current_view": {"claims": []}, "initial_analysis_report": report}
        short = model_context.compact_context(context)
        self.assertEqual(short["initial_analysis_report"]["label_requirements"], report["label_requirements"])
        self.assertNotIn("raw_evidence", short)
        self.assertNotIn("summary", short["initial_analysis_report"]["reports"][0])
        self.assertEqual(report["reports"][0]["summary"], "verbose" * 100)

    def test_core_reads_issue_and_requirement_sources_without_claims(self):
        pool = [{"evidence_id": f"e{i}", "utterance_id": f"u{i}", "text": f"source {i}"} for i in range(5)]
        context = {"raw_evidence": [pool[0]], "coverage": {},
            "results": [{"result_id": "r1", "content": {"claims": [], "issues": [{"evidence_ids": ["e3"]}],
                                     "label_requirements": [{"evidence_ids": ["e2"]}]}}],
            "issues": [{"result_id": "r1", "evidence_ids": ["e4"]},
                       {"result_id": "past", "evidence_ids": ["e1"]}], "current_view": {"claims": []}}
        prepared = model_context.hydrate_core_evidence(context, pool, 10, 1000)
        self.assertEqual([r["evidence_id"] for r in prepared["raw_evidence"]], ["e2", "e3", "e4"])
        self.assertEqual(prepared["coverage"]["scope"], "result_evidence")
        self.assertEqual(context["raw_evidence"], [pool[0]])

    def test_core_hydrates_current_result_sources_and_reduction_terminates(self):
        pool = [{"evidence_id": f"e{i}", "utterance_id": f"u{i}", "text": "日本語の条件", "speaker": "A", "start": 0, "end": 1}
                for i in range(3)]
        context = {"task": {"phase": "core", "role": "core"}, "data_version": "v", "raw_evidence": pool[:1],
            "coverage": {"available_count": 3, "provided_count": 1, "omitted_count": 2},
            "results": [{"result_id": "r", "content": {"claims": [{"evidence_ids": ["e1", "e2"]}]}}],
            "iteration_review": {"pending_result_ids": ["r"], "omitted_pending_result_count": 0}}
        prepared = model_context.hydrate_core_evidence(context, pool, 10, 1000)
        self.assertEqual([row["evidence_id"] for row in prepared["raw_evidence"]], ["e1", "e2"])
        self.assertEqual(prepared["coverage"]["scope"], "result_evidence")
        self.assertEqual(context["raw_evidence"][0]["evidence_id"], "e0")
        measured = []
        def meter(*args):
            measured.append(json.loads(args[3]))
            return {"fits": False}
        resolve, runner = self.adapter(meter)
        options = {**resolve({"model_context_version": 1}), "_source_evidence": pool}
        with self.assertRaises(AnalysisContractError):
            runner("core", context, options, lambda: None, lambda _: None)
        self.assertEqual([len(row["raw_evidence"]) for row in measured], [2, 1])
        self.assertEqual([row["evidence_id"] for row in measured[-1]["raw_evidence"]], ["e1"])

    def test_model_discovery_never_autoloads_and_rechecks_instance(self):
        import lmstudio
        for length in (8192, 16384, 32768):
            handle = SimpleNamespace(identifier="synthetic", get_context_length=lambda: length,
                get_info=lambda: SimpleNamespace(to_dict=lambda: {"instance": "one"}),
                get_load_config=lambda: SimpleNamespace(to_dict=lambda: {"context": length}),
                apply_prompt_template=lambda chat: "rendered",
                tokenize=lambda text: range(6000 if text == "rendered" else 300))
            class Client:
                def __init__(self, api_host):
                    self.llm = SimpleNamespace(list_loaded=lambda: [handle], model=lambda *_: self.fail())
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def fail(self): raise AssertionError("autoload is forbidden")
            with patch.object(lmstudio, "Client", Client):
                measured = model_context.measure_local_context("synthetic", "", "日本語", "例外", {})
                integration = model_context.measure_local_context("synthetic", "", "", "", {
                    "properties": {"result_assessments": {"minItems": 3},
                                   "critique_responses": {"maxItems": 2}}})
            self.assertEqual(measured["loaded_context_length"], length)
            self.assertEqual(measured["fits"], length > 8192)
            self.assertEqual(integration["output_reserve"], 4096)
            self.assertEqual(integration["fits"], length > 8192)
        with patch.object(lmstudio, "Client", side_effect=RuntimeError("SECRET")):
            with self.assertRaises(AnalysisContractError) as caught:
                model_context.measure_local_context("synthetic", "", "", "", {})
        self.assertNotIn("SECRET", str(caught.exception))


class DurableContextTests(unittest.TestCase):
    connect = fixtures.RuntimeTests.connect
    build = fixtures.RuntimeTests.build
    run_agent = fixtures.RuntimeTests.run_agent
    method = fixtures.RuntimeTests.method
    make_service = fixtures.RuntimeTests.make_service
    start = fixtures.RuntimeTests.start
    drive = fixtures.RuntimeTests.drive

    def setUp(self):
        fixtures.RuntimeTests.setUp(self)
        self.snapshot["analysis"]["segments"] = [
            {"id": f"u{i}", "text": f"日本語の発話{i}と例外条件", "speaker": "A", "annotation": {"codes": []}}
            for i in range(323)]
        def reply(*args, **kwargs):
            role = args[5].removeprefix("analysis_orchestration_")
            context = json.loads(args[4])
            self.sent.append((role, context))
            return fixtures.InitialSpecialistTests.valid_agent(self, role, context)
        self.sent = []
        def meter(model, base, system, user, schema):
            value = json.loads(user)
            return {"fits": len(value.get("iteration_review", {}).get("pending_result_ids", [])) <= 2,
                    "output_reserve": 1600}
        self.resolve, self.agent = make_orchestration_adapters(call_ai_json=reply,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"), context_meter=meter)
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)

    def begin(self, **extra):
        return self.start(**self.resolve({"question": "test", "model_context_version": 1,
            "specialist_orchestration_version": 0,
            "context_reference_version": 0,
            "max_calls": 200, "max_tasks": 250, "context_evidence_limit": 24, **extra}))

    def test_full_323_rows_per_role_boundaries_once_and_restart_reuses_results(self):
        run = self.drive(self.begin(max_iterations=50))
        initial = [task for task in run["tasks"] if task["phase"] == "initial_analysis"]
        self.assertTrue(run["initial_analysis_report"]["full_evidence_coverage"])
        for role in ("interpretation", "verification", "critic"):
            tasks = [task for task in initial if task["role"] == role]
            owned = [ref for task in tasks for ref in task["intent"]["scope"]["owned_evidence_ids"]]
            self.assertEqual(len(owned), 323)
            self.assertEqual(len(set(owned)), 323)
            self.assertTrue(all(set(t["intent"]["scope"]["owned_evidence_ids"]).issubset(t["context_manifest"]["provided_evidence_ids"]) for t in tasks))
        blind = [c for role, c in self.sent if role == "verification"]
        self.assertTrue(all("results" not in c and "initial_analysis_report" not in c and "current_view" not in c for c in blind))
        self.assertFalse(any(t["status"] in {"quarantined", "uncertain", "failed"} for t in run["tasks"]), run.get("error"))
        calls = len(self.sent)
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)
        self.service.run(run["run_id"])
        self.assertEqual(len(self.sent), calls)
        self.assertEqual(run["usage"]["measured_calls"], 0)
        with self.service._db() as db:
            self.assertEqual(self.service._pending_result_assessments(db, self.service._read_run(db, run["run_id"])), [])

    def test_preflight_failure_is_known_unsent_and_does_not_retry(self):
        def fail(*args):
            raise AnalysisContractError("No capacity", code="context_budget_unavailable")
        self.agent = fail
        run = self.drive(self.begin())
        self.assertEqual(run["status"], "stopped")
        self.assertNotEqual(run["status"], "recovery_required")
        self.assertEqual(run["usage"]["measured_calls"], 0)
        calls = len(self.calls)
        self.service.run(run["run_id"])
        self.assertEqual(len(self.calls), calls)

    def test_capacity_splits_source_and_requirements_preserving_all_owners(self):
        self.snapshot["analysis"]["segments"] = self.snapshot["analysis"]["segments"][:11]
        def reply(*args, **kwargs):
            role = args[5].removeprefix("analysis_orchestration_")
            context = json.loads(args[4])
            self.sent.append((role, context))
            return fixtures.InitialSpecialistTests.valid_agent(self, role, context)
        def meter(model, base, system, user, schema):
            context = json.loads(user)
            phase = context.get("task", {}).get("phase")
            fits = True
            if phase == "initial_analysis":
                fits = len(context["coverage"]["page"]["owned_evidence_ids"]) <= 4
            elif phase in {"initial_routing", "initial_labels"}:
                fits = len(context["initial_analysis_report"]["label_requirements"]) <= 1
            return {"fits": fits, "output_reserve": 1600}
        self.resolve, self.agent = make_orchestration_adapters(call_ai_json=reply,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"), context_meter=meter)
        run = self.drive(self.begin(max_iterations=50))
        self.assertTrue(run["initial_analysis_report"]["full_evidence_coverage"])
        split = [t for t in run["tasks"] if t["phase"].endswith("_split")]
        self.assertTrue(split)
        self.assertTrue(all(t["status"] == "blocked" and not t.get("result_id") for t in split))
        self.assertEqual(run["calls_started"], len(self.sent))
        self.assertTrue(all(c["initial_analysis_report"]["label_requirements"] for role, c in self.sent if c["task"]["phase"] == "initial_labels"))
        self.assertEqual(len(run["initial_label_catalog"]["result_ids"]), len(run["initial_analysis_report"]["label_requirements"]))
        self.assertTrue(all(t["status"] == "succeeded" for t in run["tasks"] if not t["phase"].endswith("_split")))


if __name__ == "__main__":
    unittest.main()
