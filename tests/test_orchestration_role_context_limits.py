"""Issue 35: synthetic-only role row caps; no model, credentials or Vault writes."""
import copy
import hashlib
import itertools
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError, canonical, fingerprint
from gurumoji.analysis_orchestration import (
    AnalysisOrchestrationService, ROLES, validate_orchestration_payload,
)
import test_analysis_orchestration as support


KEY = "context_evidence_limits_by_role"
CAPS = {"core": 12, "interpretation": 120, "verification": 12, "critic": 12}


def segments():
    return [{"id": f"u{i}", "text": f"Synthetic utterance {i:03d}",
             "speaker": f"S{i % 5}", "start": i * 3, "end": i * 3 + 2,
             "annotation": {"codes": [f"synthetic-label-{i:03d}"],
                            "memo": f"Synthetic label memo {i:03d}"}, "excluded": False}
            for i in range(1, 324)]


def wire_bytes(context):
    return json.dumps(context, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class RoleCapValidationTests(unittest.TestCase):
    def validate(self, **extra):
        return validate_orchestration_payload({"model": "synthetic-model", **extra})

    def test_omission_preserves_exact_public_base_config_bytes(self):
        value = self.validate()
        self.assertNotIn(KEY, value)
        # Captured on public cbce30ba before the Issue 35 implementation.
        self.assertEqual(fingerprint(value), "sha256:4b15bd51132b76c733b24a95c8be0a820b124b797d39f2242cd0f71b0bbc3a0f")
        self.assertEqual(value["context_evidence_limit"], 120)
        self.assertEqual(value["context_text_limit"], 60000)
        self.assertEqual(value["context_index_limit"], 0)

    def test_known_roles_empty_mapping_and_boundary_values(self):
        for limits in ({}, CAPS, {role: 1 for role in ROLES}, {role: 120 for role in ROLES}):
            with self.subTest(limits=limits):
                self.assertEqual(self.validate(**{KEY: limits})[KEY], limits)

    def test_unknown_roles_and_expert_ids_are_rejected(self):
        for role in ("unknown", "Core", "expert", "exp-thematic-analysis", "", 1, None):
            with self.subTest(role=role), self.assertRaises(AnalysisContractError) as error:
                self.validate(**{KEY: {role: 12}})
            self.assertEqual(error.exception.field, KEY)

    def test_mapping_required_when_present(self):
        for value in (None, True, False, 12, 12.0, "12", [], [["core", 12]]):
            with self.subTest(value=value), self.assertRaises(AnalysisContractError) as error:
                self.validate(**{KEY: value})
            self.assertEqual(error.exception.field, KEY)

    def test_bool_noninteger_nonpositive_and_over_shared_cap_rejected(self):
        for value in (True, False, "12", 12.0, None, [], {}, 0, -1, 121):
            with self.subTest(value=value), self.assertRaises(AnalysisContractError) as error:
                self.validate(**{KEY: {"core": value}})
            self.assertEqual(error.exception.field, KEY)
        with self.assertRaises(AnalysisContractError):
            self.validate(context_evidence_limit=12, **{KEY: {"interpretation": 13}})
        self.assertEqual(self.validate(context_evidence_limit=12, **{KEY: {"core": 12}})[KEY], {"core": 12})

    def test_validated_mapping_does_not_alias_input(self):
        payload = {"model": "synthetic-model", KEY: dict(CAPS)}
        before = copy.deepcopy(payload)
        value = validate_orchestration_payload(payload)
        self.assertEqual(payload, before)
        payload[KEY]["core"] = 1
        self.assertEqual(value[KEY], CAPS)
        value[KEY]["interpretation"] = 1
        self.assertEqual(payload[KEY]["interpretation"], 120)


class RoleContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-role-context-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.sqlite3"
        serial = itertools.count(1)
        for name, kwargs in (("_id", {"side_effect": lambda prefix: f"{prefix}_{next(serial):04d}"}),
                             ("_now", {"return_value": "2026-01-01T00:00:00+00:00"})):
            patched = patch("gurumoji.analysis_orchestration." + name, **kwargs)
            patched.start(); self.addCleanup(patched.stop)
        self.snapshot = {"input_hash": "synthetic-input-v1", "source_revision": 1, "analysis_revision": 1,
                         "analysis": {"segments": segments(), "manual": {"codebook_version": 1}}}
        self.service = self.make_service()
        # Readable fixture IDs e1..e323; real API tests below retain production IDs.
        original = self.service._evidence
        def evidence(snapshot):
            rows = original(snapshot)
            for i, row in enumerate(rows, 1):
                row["id"] = row["evidence_id"] = f"e{i}"
            return rows
        self.service._evidence = evidence

    def connect(self):
        return sqlite3.connect(self.path)

    def make_service(self):
        return AnalysisOrchestrationService(connect=self.connect,
            find_item=lambda _: {"id": "synthetic323"},
            snapshot_builder=lambda _: copy.deepcopy(self.snapshot),
            source_fingerprint=lambda _: self.snapshot["input_hash"],
            agent_runner=lambda *_: self.fail("No model in context tests"),
            method_runner=lambda *_: self.fail("No method in context tests"), schedule=False)

    def start(self, **extra):
        return self.service.start("synthetic323", {"model": "synthetic-model", "obsidian_management": False,
            "context_evidence_limit": 120, "context_index_limit": 0, **extra})

    def context(self, run, role="core", **intent):
        with self.service._db() as db:
            fixed = self.service._read_run(db, run["run_id"])
            fixed["iteration"] = 1
            values = support.intent(role, **intent)
            if role == "critic":
                values.update(target_id="view", target_version=0)
            task = self.service._register(db, fixed, values, phase="core" if role == "core" else "specialists", automatic=True)
            return self.service._context(db, fixed, task)

    def test_omission_preserves_exact_public_base_context_bytes(self):
        run = self.start()
        context = self.context(run)
        # Full JSON wire bytes, including the task, labels, index and coverage.
        self.assertEqual(hashlib.sha256(wire_bytes(context)).hexdigest(), "6ddfc9fa2162e976e88974f88072cc1e0820a6b37fae84193662f06a8d73a8f2")
        self.assertEqual((len(context["raw_evidence"]), len(context["labels"])), (120, 120))
        self.assertEqual(context["coverage"]["available_count"], 323)

    def test_core_twelve_expert_one_twenty_preserves_source_index_and_labels(self):
        run = self.start(**{KEY: dict(CAPS)})
        before = self.service.result("synthetic323", run["run_id"])
        core = self.context(run)
        expert = self.context(run, "interpretation")
        for context, count in ((core, 12), (expert, 120)):
            self.assertEqual([r["evidence_id"] for r in context["raw_evidence"]], [f"e{i}" for i in range(1, count + 1)])
            self.assertEqual(set(context["labels"]), {f"u{i}" for i in range(1, count + 1)})
            self.assertEqual(context["coverage"], {"available_count": 323, "provided_count": count,
                "omitted_count": 323 - count, "complete": False, "scope": "dataset",
                "evidence_index": [{"evidence_id": f"e{i}", "utterance_id": f"u{i}"} for i in range(1, 324)],
                "index_available_count": 323, "index_provided_count": 323, "index_omitted_count": 0})
            self.assertEqual(context["data_version"], "synthetic-input-v1")
        after = self.service.result("synthetic323", run["run_id"])
        self.assertEqual(canonical(after["initial"]), canonical(before["initial"]))
        self.assertEqual(canonical(after["label_versions"]), canonical(before["label_versions"]))
        self.assertEqual(len(after["label_versions"][0]["labels"]), 323)
        self.assertEqual(after["run"]["config"]["context_evidence_limit"], 120)
        self.assertEqual(after["run"]["config"][KEY], CAPS)

    def test_missing_role_and_empty_mapping_fall_back_without_context_changes(self):
        run = self.start(**{KEY: {"core": 12}})
        actual = self.context(run, "interpretation")
        with self.service._db() as db:
            fixed = self.service._read_run(db, run["run_id"])
            fixed["iteration"] = 1
            task = actual["task"]
            for limits in ({}, None):
                if limits is None:
                    fixed["config"].pop(KEY)
                else:
                    fixed["config"][KEY] = limits
                self.assertEqual(wire_bytes(actual), wire_bytes(self.service._context(db, fixed, task)))

    def test_selected_scope_and_excluded_rows_keep_original_denominators(self):
        self.snapshot["analysis"]["segments"][19]["excluded"] = True
        run = self.start(**{KEY: {"core": 12}})
        selected = [f"e{i}" for i in range(21, 41)]
        context = self.context(run, evidence_ids=selected)
        self.assertEqual([r["evidence_id"] for r in context["raw_evidence"]], selected[:12])
        self.assertEqual(set(context["labels"]), {f"u{i}" for i in range(21, 33)})
        coverage = context["coverage"]
        self.assertEqual((coverage["scope"], coverage["available_count"], coverage["provided_count"], coverage["omitted_count"]),
                         ("selected", 20, 12, 8))
        self.assertEqual(coverage["index_available_count"], 322)
        self.assertNotIn("e20", {r["evidence_id"] for r in coverage["evidence_index"]})
        self.assertEqual(len(self.service.result("synthetic323", run["run_id"])["label_versions"][0]["labels"]), 323)
        with self.assertRaises(AnalysisContractError):
            self.context(run, evidence_ids=["e20"])

    def test_text_and_index_caps_remain_independent(self):
        text_cap = sum(len(row["text"]) for row in self.snapshot["analysis"]["segments"][:3])
        run = self.start(context_text_limit=text_cap, context_index_limit=7, **{KEY: {"core": 12}})
        context = self.context(run)
        self.assertEqual(len(context["raw_evidence"]), 3)
        self.assertEqual(len(context["labels"]), 3)
        self.assertEqual(context["coverage"]["omitted_count"], 320)
        self.assertEqual(context["coverage"]["index_provided_count"], 7)
        self.assertEqual(context["coverage"]["index_omitted_count"], 316)

    def test_blind_verification_and_critic_use_their_own_caps(self):
        run = self.start(**{KEY: {"core": 12, "verification": 3, "critic": 4}})
        verification = self.context(run, "verification")
        self.assertEqual(len(verification["raw_evidence"]), 3)
        self.assertTrue(verification["blind_first"])
        self.assertNotIn("labels", verification)
        self.assertNotIn("results", verification)
        critic = self.context(run, "critic")
        self.assertEqual((len(critic["raw_evidence"]), len(critic["labels"])), (4, 4))

    def test_verification_clarification_uses_cap_without_changing_saved_result(self):
        run = self.start(**{KEY: {"verification": 2}})
        with self.service._db() as db:
            fixed = self.service._read_run(db, run["run_id"])
            content = {"summary": "Synthetic verification", "claims": [{"claim_id": "c1", "kind": "observation",
                "text": "Synthetic claims", "evidence_ids": [f"e{i}" for i in range(1, 21)]}]}
            metadata = {"result_id": "result-fixture", "role": "verification", "validation_status": "valid",
                        "raw_hash": fingerprint(content), "dataset_version": fixed["input_hash"], "annotation_version": 0}
            db.execute("INSERT INTO orchestration_results VALUES (?,?,?,?,?)",
                (metadata["result_id"], run["run_id"], "task-fixture", canonical(content).decode(), canonical(metadata).decode()))
        context = self.context(run, "verification", kind="clarification", result_id="result-fixture")
        self.assertEqual(len(context["raw_evidence"]), 2)
        self.assertEqual(context["coverage"], {"available_count": 20, "provided_count": 2,
            "omitted_count": 18, "complete": False, "scope": "saved_verification_result"})
        self.assertFalse(context["execution_allowed"])
        self.assertEqual(context["clarification_target"]["content"], content)
        self.assertEqual(context["clarification_target"]["metadata"]["raw_hash"], fingerprint(content))

    def test_same_request_is_idempotent_and_changed_caps_conflict(self):
        options = {"request_id": "synthetic-role-request", KEY: dict(CAPS)}
        run = self.start(**options)
        self.assertEqual(self.start(**options)["run_id"], run["run_id"])
        with self.assertRaises(AnalysisContractError) as error:
            self.start(**{**options, KEY: {**CAPS, "core": 11}})
        self.assertEqual(error.exception.code, "request_conflict")

    def test_human_pending_gate_still_blocks_core_claim_adoption(self):
        run = self.start(**{KEY: dict(CAPS)})
        gate = {"status": "human_pending", "result_ids": ["synthetic-statistical-draft"]}
        with patch.object(self.service, "_statistical_review_gate", return_value=gate):
            context = self.context(run)
            self.assertEqual(context["statistical_review_gate"], gate)
            with self.service._db() as db, self.assertRaises(AnalysisContractError) as error:
                fixed = self.service._read_run(db, run["run_id"])
                self.service._validate_result(db, fixed, context["task"], support.core(claims=[{
                    "claim_id": "c1", "text": "Synthetic unconfirmed conclusion", "kind": "observation",
                    "evidence_ids": ["e1"]}]))
            self.assertEqual(error.exception.code, "statistical_human_review_required")

    def test_fresh_service_reads_same_config_and_getters_do_not_write(self):
        run = self.start(**{KEY: dict(CAPS)})
        original = self.context(run)
        fresh = self.make_service()
        before = self.path.read_bytes()
        expected = self.service.result("synthetic323", run["run_id"])
        self.assertEqual(fresh.result("synthetic323", run["run_id"]), expected)
        self.assertEqual(fresh.status("synthetic323", run["run_id"])["config"][KEY], CAPS)
        self.assertEqual(self.path.read_bytes(), before)
        with fresh._db() as db:
            fixed = fresh._read_run(db, run["run_id"])
            fixed["iteration"] = 1
            self.assertEqual(wire_bytes(fresh._context(db, fixed, original["task"])), wire_bytes(original))


class RoleCapAppIntegrationTests(unittest.TestCase):
    """Real API -> staged Handler -> fixed Store -> fresh reader, synthetic CPU only."""

    def setUp(self):
        import app
        import test_analysis_orchestration_integration as integration
        self.app, self.integration = app, integration
        self.guards = {}
        for target, name in ((app, "load_token_config"), (app.ai_client, "post_json"),
                             (app.AnalysisStore, "_publish_generated_vaults"),
                             (app.AnalysisStore, "_publish_research")):
            kwargs = ({"return_value": app.TokenConfig()} if name == "load_token_config" else
                      {"side_effect": AssertionError("No network, model or Vault publication")})
            guard = patch.object(target, name, **kwargs)
            self.guards[name] = guard.start(); self.addCleanup(guard.stop)
        network = patch("socket.socket.connect", side_effect=AssertionError("No network in synthetic CPU tests"))
        self.network = network.start(); self.addCleanup(network.stop)
        integration.OrchestrationIntegrationTests.setUp(self)
        self.source = segments()
        app.upsert_library_item(item_id="synthetic323", source_name="Synthetic CPU only",
            output_dir=Path(self.fixture.temp.name) / "synthetic-output", media_path=None, language="en",
            segments=self.source, speaker_names={}, files=[], outline=None, emotion_analysis=None,
            write_srt=False, write_json=False)
        self.fixture.url = "/api/library/synthetic323/analysis"
        self.url = self.fixture.url + "/orchestration"
        current = self.client.get(self.fixture.url).get_json()
        config = current["config"]
        config["codebook"] = [{"id": "synthetic-label", "label": "Synthetic label"}]
        for row in self.source:
            row["annotation"]["codes"] = ["synthetic-label"]
        saved = self.client.put(self.fixture.url, json={
            "source_revision": current["item"]["revision_count"],
            "analysis_revision": current["item"]["analysis_revision"], "config": config,
            "annotations": {row["id"]: row["annotation"] for row in self.source}})
        self.assertEqual(saved.status_code, 200, saved.get_json())
        self.wire_contexts = []
        self.interpretation_calls = 0

    def payload(self, request_id="synthetic-role-cap-integration"):
        value = self.integration.OrchestrationIntegrationTests.payload(self, request_id)
        value.update(model="google/gemma-4-12b", obsidian_management=False,
                     publication_targets=[], concurrency=1, context_evidence_limit=120,
                     context_text_limit=60000, context_index_limit=0)
        value[KEY] = dict(CAPS)
        return value

    def start(self, payload=None):
        return self.integration.OrchestrationIntegrationTests.start(self, payload)

    def response(self, *args, **kwargs):
        context = json.loads(args[4])
        role = args[5].removeprefix("analysis_orchestration_")
        self.wire_contexts.append((role, copy.deepcopy(context)))
        if role == "interpretation":
            self.interpretation_calls += 1
        return self.integration.OrchestrationIntegrationTests.response(self, *args, **kwargs)

    def assert_no_external_effects(self):
        self.guards["post_json"].assert_not_called()
        self.guards["_publish_generated_vaults"].assert_not_called()
        self.guards["_publish_research"].assert_not_called()
        self.network.assert_not_called()

    def test_real_api_rejects_invalid_caps_before_creating_run_or_calling_model(self):
        with self.service._db() as db:
            before = db.execute("SELECT COUNT(*) FROM orchestration_runs").fetchone()[0]
        with patch.object(self.app, "call_orchestration_ai_json", side_effect=AssertionError("No model")) as model:
            for limits in ({"unknown": 12}, {"core": True}, {"core": 0}, {"core": 121}, {"core": 12.0}):
                with self.subTest(limits=limits):
                    payload = self.payload()
                    payload[KEY] = limits
                    response = self.client.post(self.url, json=payload)
                    self.assertEqual(response.status_code, 400, response.get_json())
            model.assert_not_called()
        with self.service._db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_runs").fetchone()[0], before)
        self.assert_no_external_effects()

    def test_synthetic323_real_api_save_fresh_same_config_and_immutable_source(self):
        with patch.object(self.app, "call_orchestration_ai_json", side_effect=self.response):
            rid = self.start()
            self.assertTrue(self.service._build_initial(rid))
            before = self.service.result("synthetic323", rid)
            self.service.run(rid)
        state = self.client.get(self.url + "/" + rid).get_json()["run"]
        self.assertEqual(state["status"], "completed", state)
        self.assertTrue(all(t["status"] == "succeeded" for t in state["tasks"] if t["role"] == "core"))
        self.assertTrue(all(r["validation_status"] == "valid" for r in state["results"] if r["role"] == "core"))
        cores = [c for role, c in self.wire_contexts if role == "core"]
        self.assertTrue(cores)
        for context in cores:
            self.assertEqual((len(context["raw_evidence"]), len(context["labels"])), (12, 12))
            coverage = context["coverage"]
            self.assertEqual((coverage["available_count"], coverage["provided_count"], coverage["omitted_count"]), (323, 12, 311))
            self.assertEqual((coverage["index_available_count"], coverage["index_provided_count"], coverage["index_omitted_count"]), (323, 323, 0))
            index = coverage["evidence_index"]
            self.assertEqual(set(index), {"columns", "rows"})
            self.assertEqual(index["columns"], ["evidence_id"])
            self.assertEqual(len(index["rows"]), 323)
            self.assertTrue(all(len(row) == 1 for row in index["rows"]))
            self.assertEqual([dict(zip(index["columns"], row)) for row in index["rows"]],
                             [{"evidence_id": row["evidence_id"]} for row in before["initial"]["snapshot"]["evidence"]])
            self.assertIn("columns_rows_v1", coverage["evidence_index_format"])
            self.assertFalse(coverage["complete"])
        expert = next(c for role, c in self.wire_contexts if role == "interpretation")
        self.assertEqual(expert["expert_hooks"]["context_evidence_limit"], 120)
        self.assertEqual(expert["expert_hooks"]["max_rounds"], 2)
        # Existing Hook excerpt behavior is retained after the role's 120-row selection.
        self.assertEqual(len(expert["raw_evidence"]), 12)
        self.assertEqual(len(expert["labels"]), 120)
        exported = self.service.result("synthetic323", rid)
        self.assertEqual(canonical(exported["initial"]), canonical(before["initial"]))
        self.assertEqual(canonical(exported["label_versions"]), canonical(before["label_versions"]))
        labels = exported["label_versions"][0]["labels"]
        self.assertEqual(len(labels), 323)
        self.assertEqual(labels["u323"]["codes"], self.source[-1]["annotation"]["codes"])
        self.assertEqual(labels["u323"]["memo"], self.source[-1]["annotation"]["memo"])
        self.assertEqual(state["config"][KEY], CAPS)
        self.assertEqual(state["config"]["context_evidence_limit"], 120)
        publication = state["publication"]
        self.assertEqual(publication["save_status"], "saved", publication)
        self.assertEqual(publication["publication_status"], "not_selected")
        saved = publication["result_run"]
        artifact = next(a for a in saved["artifacts"] if a["name"] == "result.json")
        fresh = self.app.AnalysisStore(self.app.DATABASE_FILE, self.app.database_connection)
        _, saved_bytes = fresh.read_artifact(artifact["id"])
        self.assertEqual(saved_bytes, self.client.get(artifact["url"]).data)
        package = json.loads(saved_bytes)
        self.assertEqual(package["orchestration"]["run"]["config"][KEY], CAPS)
        self.assertEqual(package["orchestration"]["initial"], exported["initial"])
        self.assertEqual(package["orchestration"]["label_versions"], exported["label_versions"])
        database_before = self.app.DATABASE_FILE.read_bytes()
        with patch.object(self.app, "call_orchestration_ai_json", side_effect=AssertionError("GET must be read only")) as model:
            for _ in range(2):
                self.client.get(self.url + "/" + rid)
                self.client.get(self.url + "/" + rid + "/export.json")
                fresh.read_artifact(artifact["id"])
            model.assert_not_called()
        self.assertEqual(self.app.DATABASE_FILE.read_bytes(), database_before)
        self.assert_no_external_effects()

    def test_expert_keeps_two_additional_hook_rounds_and_shared_cap(self):
        from test_expert_data_hooks import request
        seen = []
        def response(*args, **kwargs):
            context = json.loads(args[4])
            role = args[5].removeprefix("analysis_orchestration_")
            if role == "interpretation" and len(seen) < 2:
                seen.append(copy.deepcopy(context))
                index = context["expert_hooks"]["evidence_index"]
                ids = [row["evidence_id"] for row in index[120 + 8 * (len(seen) - 1):128 + 8 * (len(seen) - 1)]]
                return {"expert_response": {"mode": "read", "hook_requests": [request(ids=ids)]}}
            return self.response(*args, **kwargs)
        with patch.object(self.app, "call_orchestration_ai_json", side_effect=response):
            rid = self.start()
            self.service.run(rid)
        state = self.service.status("synthetic323", rid)
        self.assertEqual(state["status"], "completed", state)
        task = next(t for t in state["tasks"] if t["role"] == "interpretation")
        self.assertEqual(task["status"], "succeeded", task)
        self.assertEqual(task["model_calls"], 3)
        self.assertEqual(len(task["expert_hook_reads"]), 2)
        self.assertEqual(len(task["expert_evidence_ids"]), 28)
        self.assertTrue(all(len(read["provided_evidence_ids"]) == 8 for read in task["expert_hook_reads"]))
        self.assertTrue(all(c["expert_hooks"]["context_evidence_limit"] == 120 and
                            c["expert_hooks"]["max_rounds"] == 2 for c in seen))
        self.assert_no_external_effects()

    def test_selected_scope_outside_id_cannot_be_read_or_accepted_as_expert_evidence(self):
        from test_expert_data_hooks import request
        for mode in ("read", "report"):
            with self.subTest(mode=mode):
                invalid_id = []
                selected = []
                def response(*args, **kwargs):
                    context = json.loads(args[4])
                    role = args[5].removeprefix("analysis_orchestration_")
                    if role == "core" and not selected:
                        index = context["coverage"]["evidence_index"]
                        self.assertEqual(index["columns"], ["evidence_id"])
                        self.assertEqual(len(index["rows"]), 323)
                        self.assertTrue(all(len(row) == 1 for row in index["rows"]))
                        ids = [row[0] for row in index["rows"]]
                        selected.extend(ids[20:40]); invalid_id.append(ids[-1])
                    value = self.response(*args, **kwargs)
                    if role == "core":
                        for intent in value["intents"]:
                            if intent["role"] == "interpretation":
                                intent["evidence_ids"] = selected
                    if role == "interpretation":
                        self.assertEqual(context["coverage"]["available_count"], 20)
                        self.assertEqual({r["evidence_id"] for r in context["expert_hooks"]["evidence_index"]}, set(selected))
                        self.assertNotIn(invalid_id[0], {r["evidence_id"] for r in context["raw_evidence"]})
                        if mode == "read":
                            return {"expert_response": {"mode": "read", "hook_requests": [request(ids=invalid_id)]}}
                        value["expert_response"]["result"]["expert_report"]["evidence_ids"] = invalid_id
                    return value
                with patch.object(self.app, "call_orchestration_ai_json", side_effect=response):
                    rid = self.start(self.payload("synthetic-scope-" + mode))
                    self.service.run(rid)
                state = self.service.status("synthetic323", rid)
                task = next(t for t in state["tasks"] if t["role"] == "interpretation")
                self.assertNotEqual(task["status"], "succeeded", task)
                self.assertEqual((task["status"], task["error"]),
                                 ("uncertain", "expert_hook_scope_mismatch") if mode == "read"
                                 else ("quarantined", "expert_reference_mismatch"))
                self.assertNotIn(invalid_id[0], task["expert_evidence_ids"])
                self.assertNotIn("expert_hook_reads", task)
                self.assertFalse(any(r["task_id"] == task["task_id"] and r["validation_status"] == "valid" for r in state["results"]))
                if mode == "report":
                    saved = self.service.result("synthetic323", rid, task["result_id"])
                    self.assertEqual(saved["raw"]["expert_report"]["evidence_ids"], invalid_id)
                    self.assertEqual(saved["validation_status"], "quarantined")
                    self.assertEqual(saved["raw_hash"], fingerprint(saved["raw"]))
                for role, context in self.wire_contexts:
                    if role == "core":
                        self.assertFalse(any(r.get("task_id") == task["task_id"] for r in context["results"]))
                        if task.get("result_id"):
                            self.assertNotIn(task["result_id"], [r["result_id"] for r in context["results"]])
                self.assert_no_external_effects()


if __name__ == "__main__":
    unittest.main()
