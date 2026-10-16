"""Synthetic end-to-end checks of the compact Handler/provider contract."""
import copy
import json
from types import SimpleNamespace
import unittest

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services import model_context
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters, ADAPTER_VERSION
import test_analysis_orchestration as fixtures


class TransportTests(unittest.TestCase):
    def context(self):
        rows = [{"evidence_id": "ev_" + str(i) * 24, "utterance_id": "utterance_" + str(i),
                 "text": "架空の発話。例外条件を含む。", "speaker": "話者A", "start": 1.234,
                 "end": None, "source_hash": "ROW_HASH", "dataset_version": "ROW_VERSION"}
                for i in range(1, 3)]
        return {"task": {"phase": "initial_analysis", "role": "interpretation"},
                "data_version": "sha256:synthetic-dataset", "raw_evidence": rows,
                "coverage": {"evidence_index": [{"evidence_id": r["evidence_id"], "utterance_id": r["utterance_id"]} for r in rows],
                             "page": {"owned_evidence_ids": [r["evidence_id"] for r in rows]}},
                "labels": {rows[0]["utterance_id"]: {"code": "example"}},
                "results": [{"result_id": "result_kept", "content": {"claims": [{"evidence_ids": [rows[1]["evidence_id"]]}]}}],
                "issues": [{"issue_id": "issue_kept", "evidence_ids": [rows[0]["evidence_id"]]}],
                "initial_analysis_report": {"label_requirements": [{"evidence_ids": [rows[1]["evidence_id"]]}]}}

    def adapter(self, reply, meter=None):
        return make_orchestration_adapters(call_ai_json=reply,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"),
            **({"context_meter": meter} if meter else {}))

    def test_all_context_references_schema_and_label_keys_share_one_map(self):
        context = self.context()
        before = copy.deepcopy(context)
        mapping = model_context.reference_map(context)
        wire = model_context.transform_references(context, mapping)
        rendered = model_context.columnar_evidence(wire)
        raw = json.dumps(rendered)
        for row in context["raw_evidence"]:
            self.assertNotIn(row["evidence_id"], raw)
            self.assertNotIn(row["utterance_id"], raw)
        self.assertNotIn("ROW_HASH", raw)
        self.assertNotIn("ROW_VERSION", raw)
        self.assertEqual(rendered["raw_evidence"]["rows"][0], ["e1", before["raw_evidence"][0]["text"], "S1", 1.2, None])
        self.assertEqual(rendered["coverage"]["page"]["owned_evidence_ids"], ["e1", "e2"])
        self.assertEqual(list(rendered["labels"]), ["e1"])
        self.assertEqual(rendered["results"][0]["result_id"], "result_kept")
        self.assertEqual(context, before)

    def test_output_nested_claim_issue_patch_definition_and_request_roundtrip(self):
        context = self.context()
        mapping = model_context.reference_map(context)
        canonical = {"claims": [{"evidence_ids": [context["raw_evidence"][0]["evidence_id"]]}],
            "issues": [{"evidence_ids": [context["raw_evidence"][1]["evidence_id"]]}],
            "label_patches": [{"utterance_id": "utterance_1", "evidence_ids": [context["raw_evidence"][0]["evidence_id"]]}],
            "label_definitions": [{"evidence_ids": [context["raw_evidence"][1]["evidence_id"]]}],
            "analysis_requests": [{"evidence_ids": [context["raw_evidence"][1]["evidence_id"]], "dependencies": ["task_kept"]}]}
        wire = model_context.transform_references(canonical, mapping)
        self.assertEqual(model_context.transform_references(wire, mapping, restore=True), canonical)

    def test_unknown_and_full_original_response_references_are_rejected(self):
        mapping = model_context.reference_map(self.context())
        for ref in ("e99", "ev_" + "1" * 24, "utterance_1", None):
            for response in ({"claims": [{"evidence_ids": [ref]}]}, {"label_patches": [{"utterance_id": ref}]}):
                with self.subTest(response=response), self.assertRaises(AnalysisContractError) as caught:
                    model_context.transform_references(response, mapping, restore=True)
                self.assertEqual(caught.exception.code, "evidence_missing")

    def test_mapping_rejects_ambiguous_identity(self):
        for rows in ([{"evidence_id": "ev1", "utterance_id": "u"}, {"evidence_id": "ev2", "utterance_id": "u"}],
                     [{"evidence_id": "ev", "utterance_id": "u1"}, {"evidence_id": "ev", "utterance_id": "u2"}]):
            with self.assertRaises(AnalysisContractError):
                model_context.reference_map({}, rows)

    def test_source_text_is_preserved_even_if_it_mentions_an_id(self):
        context = self.context()
        context["raw_evidence"][0]["text"] = "utterance_1"
        mapping = model_context.reference_map(context)
        self.assertEqual(model_context.transform_references(context, mapping)["raw_evidence"][0]["text"], "utterance_1")

    def test_restart_metadata_is_never_disclosed(self):
        context = self.context()
        context["task"]["context_manifest"] = {"secret_map": "DO_NOT_SEND"}
        self.assertNotIn("DO_NOT_SEND", json.dumps(model_context.transform_references(context, model_context.reference_map(context))))

    def test_provider_roundtrip_manifest_and_schema_never_send_original_ids(self):
        for referenced in (0, 1):
            with self.subTest(referenced=referenced):
                saved, sent = [], []
                context = self.context()
                def reply(*args, **kwargs):
                    sent.append((args, kwargs))
                    self.assertEqual(args[6]["properties"]["claims"]["items"]["properties"]["evidence_ids"]["items"]["enum"], ["e1", "e2"])
                    packet = model_context.restored_reference_context(args[4], kwargs.get("data_messages"))
                    self.assertEqual(packet["raw_evidence"][0]["utterance_id"], "e1")
                    return {"claims": [{"evidence_ids": ["e1"]}], "label_patches": [{"utterance_id": "e2", "evidence_ids": ["e2"]}]}
                resolve, runner = self.adapter(reply, lambda *a, **k: {"fits": True, "output_reserve": 1600})
                result = runner("interpretation", context, resolve({"model_context_version": referenced, "context_reference_version": referenced}), lambda: None, saved.append)
                manifest = saved[0]["context_manifest"]
                self.assertEqual(manifest["reference_map_sha256"], model_context.digest(manifest["reference_map"]))
                self.assertEqual(result["claims"][0]["evidence_ids"], [context["raw_evidence"][0]["evidence_id"]])
                self.assertEqual(result["label_patches"][0]["utterance_id"], "utterance_2")
                rendered = json.dumps([sent[0][0][3:7], sent[0][1]])
                self.assertNotIn("ev_" + "1" * 24, rendered)
                self.assertNotIn("utterance_1", rendered)

    def test_unknown_reference_from_mock_provider_is_rejected_before_adoption(self):
        resolve, runner = self.adapter(lambda *a, **k: {"claims": [{"evidence_ids": ["e404"]}]})
        with self.assertRaises(AnalysisContractError) as caught:
            runner("interpretation", self.context(), resolve({}), lambda: None, lambda _: None)
        self.assertEqual(caught.exception.code, "evidence_missing")

    def test_synthetic_context_becomes_smaller_without_dropping_rows(self):
        context = self.context()
        mapping = model_context.reference_map(context)
        columns = model_context.columnar_evidence(model_context.transform_references(context, mapping))["raw_evidence"]
        self.assertLess(len(json.dumps(columns)), len(json.dumps(context["raw_evidence"])))
        self.assertEqual(len(columns["rows"]), len(context["raw_evidence"]))

    def test_source_pool_and_raw_rows_share_columns_speakers_and_refs(self):
        context = self.context()
        context["_source_evidence"] = copy.deepcopy(context["raw_evidence"])
        mapping = model_context.reference_map(context)
        packet = model_context.columnar_evidence(model_context.transform_references(context, mapping))
        self.assertEqual(packet["_source_evidence"], packet["raw_evidence"])

    def test_duplicate_mapping_can_fill_missing_utterance_without_renumbering(self):
        rows = [{"evidence_id": "evA"}, {"evidence_id": "evB", "utterance_id": "uB"},
                {"evidence_id": "evA", "utterance_id": "uA"}]
        mapping = model_context.reference_map({}, rows)
        self.assertEqual(mapping, {"e1": {"evidence_id": "evA", "utterance_id": "uA"},
                                   "e2": {"evidence_id": "evB", "utterance_id": "uB"}})

    def test_transport_hash_records_exact_columnar_resources(self):
        context = self.context()
        mapping = model_context.reference_map(context)
        wire = model_context.transform_references(context, mapping)
        user, messages = model_context.reference_messages(wire, columnar=True)
        resources = [json.loads(message) for message in messages]
        rows = next(r for r in resources if r["reference"]["resource_id"] == "raw_evidence")
        self.assertEqual(rows["reference"]["sha256"], model_context.digest(rows["content"]))
        with self.assertRaises(ValueError):
            model_context.restored_reference_context(user, [m.replace('架空の発話', '改変') for m in messages])


class EvidenceRowTests(unittest.TestCase):
    connect = fixtures.RuntimeTests.connect
    build = fixtures.RuntimeTests.build
    run_agent = fixtures.RuntimeTests.run_agent
    method = fixtures.RuntimeTests.method
    make_service = fixtures.RuntimeTests.make_service
    start = fixtures.RuntimeTests.start
    drive = fixtures.RuntimeTests.drive
    setUp = fixtures.RuntimeTests.setUp

    def test_tampered_reference_map_hash_is_rejected_before_provider_dispatch(self):
        sent = []
        resolve, adapter = make_orchestration_adapters(
            call_ai_json=lambda *a, **k: sent.append(a),
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"))
        def agent(role, context, options, check, usage):
            def tamper(record):
                value = copy.deepcopy(record)
                if "context_manifest" in value:
                    value["context_manifest"]["reference_map_sha256"] = "incorrect"
                usage(value)
            return adapter(role, context, options, check, tamper)
        self.agent = agent
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)
        run = self.drive(self.start(**resolve({})))
        self.assertEqual(sent, [])
        self.assertTrue(any(t["error"] == "context_manifest_invalid" for t in run["tasks"]))

    def test_invalid_short_response_is_saved_and_quarantined_without_uncertain_retry(self):
        resolve, adapter = make_orchestration_adapters(
            call_ai_json=lambda *a, **k: {"summary": "架空", "claims": [{"evidence_ids": ["e404"]}]},
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"))
        self.agent = adapter
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)
        run = self.drive(self.start(**resolve({})))
        self.assertFalse(any(t["status"] == "uncertain" for t in run["tasks"]))
        with self.service._db() as db:
            rows = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE run_id=?", (run["run_id"],)).fetchall()
        invalid = [(json.loads(raw), json.loads(meta)) for raw, meta in rows if json.loads(meta).get("reference_error")]
        self.assertTrue(invalid)
        for raw, meta in invalid:
            self.assertEqual(raw["claims"][0]["evidence_ids"], ["e404"])
            self.assertEqual(meta["validation_status"], "quarantined")
            self.assertEqual(meta["error"], "evidence_missing")

    def test_old_instruction_version_is_readable_but_execution_is_rejected(self):
        old_version = "core-handler-prompts-25-referenced-context"
        self.service = self.make_service(adapter_version=old_version)
        run = self.start(adapter_version=old_version)
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)
        viewed = self.service.status("conversation", run["run_id"])
        self.assertEqual(viewed["run_id"], run["run_id"])
        self.assertEqual(viewed["config"]["adapter_version"], old_version)
        self.assertEqual(self.service.result("conversation", run["run_id"])["run"]["config"]["adapter_version"], old_version)
        with self.assertRaises(AnalysisContractError) as caught:
            self.service.resume("conversation", run["run_id"])
        self.assertEqual(caught.exception.code, "adapter_version_conflict")
        self.assertFalse(self.calls)

    def test_evidence_rows_are_six_fields_regardless_of_label_definition_setting(self):
        for flag in (0, 1):
            with self.subTest(flag=flag):
                offset = len(self.calls)
                self.drive(self.start(initial_label_definitions_version=flag))
                context = self.calls[offset][1]
                self.assertTrue(context["raw_evidence"])
                for row in context["raw_evidence"]:
                    self.assertEqual(set(row), {"evidence_id", "utterance_id", "text", "speaker", "start", "end"})


if __name__ == "__main__":
    unittest.main()
