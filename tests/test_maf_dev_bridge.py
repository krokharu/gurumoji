"""実MAF・実ObusSQLと合成応答を、一時DBと一時Vaultで検証する。"""
import copy
import json
import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services import maf_dev_bridge as bridge, model_context
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters
from gurumoji.services.ai import client as ai_client
import test_analysis_orchestration as runtime_fixture


class MafBridgeTests(unittest.TestCase):
    def setUp(self):
        self.environ = patch.dict(os.environ, {
            "MOJIOKOSI_OBUSSQL_ENABLED": "1", "MOJIOKOSI_MAF_DEV_ENABLED": "1"})
        self.environ.start()
        self.addCleanup(self.environ.stop)
        try:
            bridge.require_available()
        except AnalysisContractError as exc:
            self.skipTest(str(exc))
        self.rows = [{"evidence_id": "ev-1", "utterance_id": "u1", "text": "合成発話\n```\n---\n引用と別解釈\u2028行区切り\u2029段落区切り"},
                     {"evidence_id": "ev-2", "utterance_id": "u2", "text": "異なる観察"}]

    def test_real_workflow_orders_stages_and_releases_index(self):
        stages = []
        def analyze():
            stages.append("analysis")
            self.assertEqual(bridge.select_evidence("run-order", self.rows, "引用", 2, 1000), self.rows)
        bridge.drive("run-order", lambda: stages.append("initial") or True,
                     lambda: stages.append("index") or self.rows, analyze)
        self.assertEqual(stages, ["initial", "index", "analysis"])
        self.assertNotIn("run-order", bridge._indexes)

    def test_incomplete_initial_never_indexes_or_runs_analysis(self):
        bridge.drive("run-initial", lambda: False,
                     lambda: self.fail("初期未完了で根拠を読まない"), lambda: self.fail("分析を開始しない"))

    def test_workflow_failure_releases_index_without_retry(self):
        calls = []
        def analyze():
            calls.append(1)
            raise RuntimeError("synthetic")
        with self.assertRaises(Exception):
            bridge.drive("run-fail", lambda: True, lambda: self.rows, analyze)
        self.assertEqual(calls, [1])
        self.assertNotIn("run-fail", bridge._indexes)

    def test_obussql_restores_japanese_fences_and_source_order(self):
        index = bridge.FixedEvidenceIndex("run-unicode", self.rows)
        self.assertEqual(index.select(self.rows, "引用", 2, 1000), self.rows)
        self.assertEqual(index.select(self.rows, "異なる", 1, 1000), [self.rows[1]])

    def test_obussql_rejects_unknown_or_changed_evidence(self):
        index = bridge.FixedEvidenceIndex("run-tamper", self.rows)
        for change in ({"evidence_id": "unknown"}, {"text": "差し替えた本文"}):
            with self.subTest(change=change), self.assertRaises(AnalysisContractError):
                index.select([{**self.rows[0], **change}], "引用", 2, 1000)

    def test_selector_cannot_introduce_unrequested_evidence(self):
        context = {"results": [{"result_id": "r", "content": {"claims": [{"evidence_ids": ["ev-1"]}]}}],
                   "coverage": {}}
        with self.assertRaises(AnalysisContractError):
            model_context.hydrate_core_evidence(context, self.rows, 1, 1000,
                                               select=lambda *_: [self.rows[1]])

    def test_compact_delivery_keeps_content_and_detects_tampering(self):
        context = {"question": "合成", "data_version": "fixed-v1", "raw_evidence": self.rows,
                   "expert_knowledge": {"sources": [{"note_id": "rules", "path": "obsidian://software/rules", "revision": 1}]}}
        original = copy.deepcopy(context)
        user, messages = model_context.reference_messages(context, compact_references=True)
        self.assertEqual(model_context.restored_reference_context(user, messages), context)
        self.assertEqual(context, original)
        altered = json.loads(messages[0])
        altered["reference"]["resource_id"] = "other"
        with self.assertRaises(ValueError):
            model_context.restored_reference_context(user, [json.dumps(altered), *messages[1:]])
        altered_control = json.loads(user)
        altered_control["resource_references"][0]["path"] = "db://wrong/source"
        with self.assertRaises(ValueError):
            model_context.restored_reference_context(json.dumps(altered_control), messages)

    def test_single_catalog_does_not_deliver_unrequested_definitions(self):
        definition = runtime_fixture.draft_label_definition("ev-1")
        context = {"task": {"role": "orchestrator", "phase": "specialist_review"},
                   "iteration_review": {"pending_result_ids": ["interpretation-result"]},
                   "results": [], "initial_label_catalog": {"result_id": "labels-result", "definitions": [definition]}}
        compact = model_context.compact_context(context)
        catalog = compact["initial_label_catalog"]
        self.assertEqual(catalog["definitions"], [])
        self.assertEqual(catalog["omitted_definition_count"], 1)
        self.assertEqual(catalog["full_catalog_sha256"], model_context.digest(context["initial_label_catalog"]))
        self.assertEqual(context["initial_label_catalog"]["definitions"], [definition])

    def test_disabled_status_does_not_load_framework_or_obussql(self):
        with patch.dict(os.environ, {bridge.ENV_ENABLED: "0"}), \
                patch.object(bridge, "require_available", side_effect=AssertionError("import")):
            self.assertEqual(bridge.status()["status"], "disabled")

    def test_single_concept_fits_eight_k_without_cutting_input_or_margin(self):
        handle = SimpleNamespace(identifier="synthetic", get_context_length=lambda: 8192,
            get_info=lambda: SimpleNamespace(to_dict=lambda: {}),
            get_load_config=lambda: SimpleNamespace(to_dict=lambda: {}),
            apply_prompt_template=lambda _: "rendered",
            tokenize=lambda value: range(5000 if value == "rendered" else 900))
        client = MagicMock()
        client.__enter__.return_value.llm.list_loaded.return_value = [handle]
        with patch("lmstudio.Client", return_value=client):
            budgets = [model_context.measure_local_context("synthetic", "http://127.0.0.1:1234/v1", "system", "user",
                {"properties": {"label_definitions": {"maxItems": count}, "analysis_requests": {"maxItems": 0}}})
                for count in (1, 2)]
        self.assertTrue(budgets[0]["fits"])
        self.assertFalse(budgets[1]["fits"])
        self.assertEqual(budgets[0]["template_input_tokens"], budgets[1]["template_input_tokens"])
        self.assertEqual(budgets[0]["safety_margin"], 512)
        self.assertGreater(budgets[0]["output_limit"], budgets[0]["output_reserve"])
        self.assertEqual(sum(budgets[0][key] for key in
                             ("template_input_tokens", "output_limit", "safety_margin")), 8192)
        client.__enter__.return_value.llm.model.assert_not_called()

    def test_reasoning_off_is_per_request_and_auto_keeps_model_default(self):
        payloads = []
        def post(url, headers, payload, **kwargs):
            payloads.append(payload)
            return {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]}
        for level in ("off", "auto"):
            ai_client.call_ai_json("lmstudio", "", "synthetic", "system", "user", "analysis_orchestration_core", {},
                post=post, lmstudio_base=lambda _: "http://127.0.0.1:1234/v1", lmstudio_model_id=lambda value: value,
                lmstudio_reasoning=lambda *_: {"allowed_options": ["off", "on"], "default": "on"},
                providers={"lmstudio"}, local_reasoning_level=level)
        self.assertEqual(payloads[0]["reasoning_effort"], "none")
        self.assertNotIn("reasoning_effort", payloads[1])

    def test_actual_adapter_receives_obussql_evidence_before_provider(self):
        calls = []
        def provider(*args, **kwargs):
            calls.append(json.loads(args[4]))
            return {"summary": "合成", "claims": []}
        resolve, runner = make_orchestration_adapters(call_ai_json=provider,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"), evidence_selector=bridge.select_evidence)
        options = {**resolve({}), "_run_id": "run-adapter", "model_context_version": 0,
                   "context_reference_version": 0, "analysis_interval_version": 0}
        def analyze():
            runner("critic", {"raw_evidence": copy.deepcopy(self.rows), "question": "引用"},
                   options, lambda: None, lambda *_: None)
        bridge.drive("run-adapter", lambda: True, lambda: self.rows, analyze)
        self.assertEqual(calls[0]["coverage"]["retrieval"], "fixed-evidence-sql-v1")
        self.assertEqual(calls[0]["raw_evidence"]["rows"][0][1], self.rows[0]["text"])

    def fixture(self):
        value = runtime_fixture.RuntimeTests("test_configured_context_limit_keeps_omissions_and_full_source_explicit")
        value.setUp()
        self.addCleanup(value.doCleanups)
        value.service.execution_driver = bridge.drive
        return value

    def test_durable_analysis_completes_and_notifies_once(self):
        fixture = self.fixture()
        callbacks = []
        fixture.service.on_complete = lambda *args: callbacks.append(args)
        run = fixture.start()
        final = fixture.drive(run)
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(final["completion_callback_status"], "completed")
        fixture.service.run(run["run_id"])
        self.assertEqual(len(callbacks), 1)
        with fixture.service._db() as db:
            events = db.execute("SELECT payload_json FROM orchestration_events WHERE run_id=?", (run["run_id"],)).fetchall()
        self.assertEqual(sum("driver_attached" in row[0] for row in events), 1)

    def test_deadline_keeps_late_response_without_false_completion(self):
        fixture = self.fixture()
        run = fixture.start(time_limit_seconds=10)
        def provider(*_):
            with fixture.service._db() as db:
                state = fixture.service._read_run(db, run["run_id"])
                state["deadline"] = time.time() - 1
                fixture.service._write_run(db, state)
            return runtime_fixture.stop()
        fixture.agent = provider
        final = fixture.drive(run)
        self.assertEqual(final["stop_reason"], "time_limit")
        self.assertNotEqual(final["status"], "completed")
        saved = fixture.service.result("conversation", run["run_id"])
        self.assertEqual(len(saved["raw_results"]), 1)
        self.assertEqual(saved["raw_results"][0]["validation_status"], "quarantined")

    def test_missing_dependencies_stop_before_any_provider_call(self):
        fixture = self.fixture()
        run = fixture.start()
        with patch.object(bridge, "require_available", side_effect=AnalysisContractError("未導入")):
            final = fixture.drive(run)
        self.assertEqual(final["status"], "stopped")
        self.assertEqual(final["stop_reason"], "execution_failure")
        self.assertFalse(fixture.calls)

    def label_repair_fixture(self, always_invalid=False):
        fixture = self.fixture()
        labels = []
        def provider(role, context, *_):
            if context.get("task", {}).get("method_id") == "label-design-v1":
                labels.append(copy.deepcopy(context))
                definition = runtime_fixture.draft_label_definition(context["raw_evidence"][0]["evidence_id"])
                if len(labels) == 1 or always_invalid:
                    definition["levels"][0]["value"] = "none"
                return {"summary": "合成尺度案", "claims": [], "label_patches": [], "label_definitions": [definition]}
            return runtime_fixture.stop(result_assessments=runtime_fixture.assess_pending_results(context)) if role == "core" else runtime_fixture.critic(context)
        fixture.agent = provider
        return fixture, labels

    def test_rejected_label_gets_one_ledgered_correction_then_completes(self):
        fixture, labels = self.label_repair_fixture()
        run = fixture.start(label_repair_limit=1, initial_label_definitions_version=1,
                            core_progress_version=1, stop_mode="iterations", max_iterations=5)
        final = fixture.drive(run)
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(labels), 2)
        self.assertEqual(labels[1]["definition_feedback"]["forbidden_values"], ["none"])
        saved = fixture.service.result("conversation", run["run_id"])
        quarantined = [r for r in saved["raw_results"] if r["validation_status"] == "quarantined"]
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0]["raw"]["label_definitions"][0]["levels"][0]["value"], "none")
        self.assertTrue(any(t["phase"] == "initial_labels_rejected" for t in final["tasks"]))

    def test_second_invalid_label_stops_without_another_correction(self):
        fixture, labels = self.label_repair_fixture(always_invalid=True)
        final = fixture.drive(fixture.start(label_repair_limit=1, initial_label_definitions_version=1))
        self.assertEqual(final["stop_reason"], "initial_labels_missing")
        self.assertEqual(len(labels), 2)
        self.assertFalse(any(role == "core" for role, *_ in fixture.calls))

    def test_correction_respects_original_call_budget(self):
        fixture, labels = self.label_repair_fixture()
        final = fixture.drive(fixture.start(label_repair_limit=1, initial_label_definitions_version=1, max_calls=1))
        self.assertEqual(final["stop_reason"], "call_budget_limit")
        self.assertEqual(len(labels), 1)

    def test_cancel_during_provider_call_quarantines_late_response(self):
        fixture = self.fixture()
        entered, release = threading.Event(), threading.Event()
        def provider(*_):
            entered.set()
            self.assertTrue(release.wait(10))
            return runtime_fixture.stop()
        fixture.agent = provider
        run = fixture.start()
        worker = threading.Thread(target=fixture.service.run, args=(run["run_id"],))
        worker.start()
        try:
            self.assertTrue(entered.wait(10))
            fixture.service.cancel("conversation", run["run_id"])
        finally:
            release.set()
            worker.join(10)
        self.assertFalse(worker.is_alive())
        saved = fixture.service.result("conversation", run["run_id"])
        self.assertEqual(len(fixture.calls), 1)
        self.assertTrue(all(row["validation_status"] == "quarantined" for row in saved["raw_results"]))
        self.assertNotEqual(saved["run"]["status"], "completed")

    def test_complete_real_publication_to_temporary_vault(self):
        from test_orchestration_publication import OrchestrationPublicationTests, TARGETS
        fixture = OrchestrationPublicationTests("test_full_ledger_roundtrip_artifacts_and_four_writers")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.runtime.execution_driver = bridge.drive
        fixture.runtime.on_complete = lambda item, rid: fixture.publisher.finalize(item, rid)
        rid = fixture.start(TARGETS)
        final = fixture.runtime.status("content", rid)
        self.assertEqual(final["completion_callback_status"], "completed", final)
        published = fixture.publisher.status("content", rid)
        self.assertEqual(published["save_status"], "saved", published)
        self.assertEqual(published["publication_status"], "published", published)
