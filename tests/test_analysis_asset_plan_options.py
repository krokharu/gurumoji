"""Synthetic normal Web choices -> registered Handler -> immutable fresh Store."""
import copy
import hashlib
import json
import threading
import unittest
from unittest.mock import Mock, patch
from flask import Flask
from gurumoji.analysis_store import AnalysisStore, canonical, safe_path
from gurumoji.analysis_core import AnalysisContractError
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
import test_analysis_asset_execution as execution
import test_analysis_human_record_options as human_options
import test_table_pilot_routes as pilot
from test_analysis_table_units import request_for


class AssetPlanOptionsTests(unittest.TestCase):
    def setUp(self):
        constructor = execution.bindings.SyntheticStore.__init__
        def fixed_source_fixture(fixture, **kwargs):
            constructor(fixture, **kwargs)
            with fixture.connect() as db:
                db.execute("UPDATE library_items SET revision_count=1,analysis_revision=1 WHERE id='TEST-conversation'")
        self.e = execution.AssetExecutionTests()
        with patch.object(execution.bindings.SyntheticStore, "__init__", fixed_source_fixture): self.e.setUp()
        self.addCleanup(self.e.doCleanups)
        self.e.h.item.update(revision_count=1, analysis_revision=1)
        self.e.service.source_fingerprint = lambda _: self.e.run["input_hash"]
        self.helper = pilot.TablePilotFactoryTests()
        self.namespace, self.traces, self.connections = self.helper.reader_namespace(
            self.e.fixture.path, source_hash=self.e.run["input_hash"])
        self.writer = Mock(return_value=self.e.service)
        app = Flask(__name__)
        register_orchestration_routes(app, self.writer, lambda _: self.fail("No model preparation"),
            table_reader=self.namespace["analysis_table_pilot_reader"])
        self.client = app.test_client(); self.url = self.e.url; self.options_url = self.url + "/options"
        self.human_url = self.url.replace("asset-plans", "human-records")

    def options(self):
        r = self.client.get(self.options_url)
        self.assertEqual(r.status_code, 200, r.get_json()); self.assertEqual(r.headers["Cache-Control"], "no-store")
        return r.get_json()

    def plan(self, options=None):
        options = options or self.options()
        choice = next(i for i in options["inputs"] if "unit_projection" in i["compatible_methods"])
        return {**options["plan_template"], "steps": [{"step_id": "PREP", "method_id": "unit_projection",
            "parameters": {"columns": choice["fields"], "unit_ids": choice["unit_ids"]},
            "scope": {k: choice["scope"][k] for k in ("scope_id", "manifest_hash")},
            "inputs": [{"input_ref_id": choice["input_ref_id"], "role": "data_input", "selection": "selected",
                        "omission_reason": None, "source": choice["source"]}]}]}

    def post(self, plan):
        r = self.client.post(self.url, json=plan)
        self.assertEqual(r.status_code, 202, r.get_json()); return r.get_json()

    def test_options_real_post_saved_reload_and_exact_replay_current_policy(self):
        page = self.options(); self.assertTrue(page["enabled"])
        self.assertEqual(page["participant_context"]["known_participants"], [])
        self.assertEqual(page["participant_context"]["reason_code"], "require_saved_output")
        self.writer.assert_not_called()
        plan = self.plan(page); outcome = self.post(plan)
        self.e.service._drain_tasks(self.e.run["run_id"])
        task = next(t for t in self.e.tasks() if t["task_id"] == outcome["tasks"]["PREP"])
        self.assertEqual(task["status"], "succeeded", task.get("error"))
        fresh = AnalysisStore(self.e.fixture.path, self.e.fixture.connect)
        asset = fresh.connected_output_descriptor(task["table_store_run_id"])
        self.assertEqual(asset["meaning"]["unit"], "utterance")
        sealed = fresh.verified_package(task["table_store_run_id"])[3]
        self.assertEqual(self.options()["plan_template"]["plan_version"], 2)
        replay = self.client.post(self.url, json=plan)
        self.assertEqual(replay.status_code, 200, replay.get_json()); self.assertTrue(replay.get_json()["duplicate"])
        self.assertEqual(len(self.e.calls), 1); self.assertEqual(len(self.e.tasks()), 1)
        self.assertEqual(fresh.verified_package(task["table_store_run_id"])[3], sealed)
        changed = copy.deepcopy(plan); changed["steps"][0]["parameters"]["columns"].remove("speaker_id")
        self.assertEqual(self.client.post(self.url, json=changed).status_code, 409)
        with self.e.service._db() as db:
            run = self.e.service._read_run(db, self.e.run["run_id"])
            self.e.service._stop(db, run, "TEST synthetic completed decision", completed=True)
        replay = self.client.post(self.url, json=plan)
        self.assertEqual(replay.status_code, 200, replay.get_json()); self.assertEqual(len(self.e.calls), 1)

    def test_invalid_query_before_reader_and_get_sql_files_readonly(self):
        factory = Mock(side_effect=AssertionError("invalid cursor cannot open reader"))
        app = Flask("invalid"); register_orchestration_routes(app, self.writer, lambda _: {}, table_reader=factory)
        client = app.test_client()
        for offset in ("", "00", "-1", "+1", "１", "1e3", "10001", "9" * 10000):
            self.assertEqual(client.get(self.options_url, query_string={"offset": offset}).status_code, 400)
        for query in ({"limit": "20"}, [("offset", "0"), ("offset", "0")]):
            self.assertEqual(client.get(self.options_url, query_string=query).status_code, 400)
        factory.assert_not_called()
        root = self.e.fixture.path.parent
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
        with self.e.fixture.connect() as db: dump = list(db.iterdump())
        self.options(); self.options(); self.writer.assert_not_called()
        read = []
        with self.e.fixture.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            worker = threading.Thread(target=lambda: read.append(self.client.get(self.options_url).status_code))
            worker.start(); worker.join(15)
            self.assertFalse(worker.is_alive()); self.assertEqual(read, [200]); db.rollback()
        with self.e.fixture.connect() as db: self.assertEqual(list(db.iterdump()), dump)
        self.assertEqual(before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()})
        self.assertTrue(all(args[0].endswith("?mode=ro") for args, _ in self.connections))
        self.assertFalse(any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "CREATE", "DELETE", "ALTER", "BEGIN IMMEDIATE")) for s in self.traces))

    def mapping_statement(self, option, *, decision="adopt"):
        helper = human_options.HumanRecordOptionsTests()
        statement = helper.statement(option, option["human_steps"][0], decision=decision)
        text = json.dumps({"participant_mapping": [{"conversation_id": "TEST-conversation", "speaker_id": "TEST-A", "participant_id": "TEST-person"}]})
        statement["source_text"] = text
        statement["record"]["record_ref"]["content_hash"] = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
        return statement

    def test_dedicated_mapping_human_get_post_participant_save_fresh_and_correction(self):
        outcome = self.post(self.plan()); self.e.service._drain_tasks(self.e.run["run_id"])
        prep = next(t for t in self.e.tasks() if t["task_id"] == outcome["tasks"]["PREP"])
        page = self.options(); context = page["participant_context"]
        self.assertEqual(context["speakers"], [{"conversation_id": "TEST-conversation", "speaker_id": "TEST-A"}])
        option = context["human_record_option"]
        self.assertEqual((option["owner_item_id"], option["owner_run_id"]), ("TEST-conversation", self.e.run["run_id"]))
        self.assertEqual(option["target_kind"], "participant_mapping")
        self.assertEqual([s["step_id"] for s in option["human_steps"]], ["participant-mapping-review"])
        self.assertEqual(set(option["target"]), {"domain", "library_id", "store_run_id", "artifact_id", "output_name", "version", "content_hash"})
        statement = self.mapping_statement(option)
        for text in ("TEST free memo is not assignments", '{"participant_mapping": [], "participant_mapping": []}', json.dumps({"participant_mapping": [{"conversation_id": "TEST-other", "speaker_id": "TEST-A", "participant_id": "TEST-person"}]}),
                     json.dumps({"participant_mapping": [{"conversation_id": "TEST-conversation", "speaker_id": "TEST-A", "participant_id": "TEST-person", "extra": True}]})):
            bad = copy.deepcopy(statement); bad["source_text"] = text
            bad["record"]["record_ref"]["content_hash"] = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
            rejected = self.client.post(self.human_url, json=bad)
            self.assertEqual(rejected.status_code, 409, rejected.get_json())
            self.assertEqual(self.e.service.table_store._human_packages()[0], [])
        # Context carries owner keys for navigation; only existing POST fields
        # are submitted, with explicit TEST researcher statement/actor.
        response = self.client.post(self.human_url, json=statement)
        self.assertEqual(response.status_code, 201, response.get_json()); hc = response.get_json()
        fresh = AnalysisStore(self.e.fixture.path, self.e.fixture.connect)
        sealed = fresh.verified_package(prep["table_store_run_id"])[3]
        page = self.options(); mapping = page["participant_context"]["confirmed_mapping"]
        self.assertEqual(mapping["actor"], hc["record"]["actor"])
        self.assertEqual(mapping["record_ref"], hc["record_ref"])
        self.assertNotEqual(mapping["record_ref"], hc["record"]["record_ref"])
        source = next(i for i in page["inputs"] if i["source"].get("asset_key", {}).get("store_run_id") == prep["table_store_run_id"])
        plan = {**page["plan_template"], "steps": [{"step_id": "PARTICIPANT", "method_id": "unit_aggregate",
            "parameters": {"value_column": "n", "operation": "sum", "unit": "participant", "participant_mapping": mapping},
            "scope": {k: source["scope"][k] for k in ("scope_id", "manifest_hash")},
            "inputs": [{"input_ref_id": source["input_ref_id"], "role": "data_input", "selection": "selected", "omission_reason": None, "source": source["source"]}]}]}
        self.assertEqual(source["confirmed_participant_mapping"], mapping)
        native = next(i for i in page["inputs"] if i["source"].get("asset_key") == self.e.h.asset["asset_key"])
        self.assertIsNone(native["confirmed_participant_mapping"])
        self.assertEqual(native["participant_mapping_reason_code"], "participant_mapping_target_lineage")
        unrelated = copy.deepcopy(plan)
        unrelated["steps"][0]["inputs"][0].update(input_ref_id=native["input_ref_id"], source=native["source"])
        denied = self.client.post(self.url, json=unrelated)
        self.assertEqual(denied.status_code, 400, denied.get_json()); self.assertEqual(len(self.e.tasks()), 1)
        # The public/programmatic Store seam must enforce the same real
        # dependency boundary even without the normal Web choice validator.
        with self.assertRaises(AnalysisContractError) as rejected:
            fresh.prepare_connected("unit_aggregate", request_for(self.e.run, self.e.h.asset,
                "unit_aggregate", plan["steps"][0]["parameters"]))
        self.assertEqual(rejected.exception.code, "connected_participant_lineage")
        for key, bad_value in (("actor", {"kind": "researcher", "actor_id": "TEST-forged-actor"}), ("record_ref", hc["record"]["record_ref"])):
            bad = copy.deepcopy(plan); bad["steps"][0]["parameters"]["participant_mapping"][key] = bad_value
            denied = self.client.post(self.url, json=bad)
            self.assertEqual(denied.status_code, 400, denied.get_json()); self.assertEqual(len(self.e.tasks()), 1)
        registered = self.post(plan); self.e.service._drain_tasks(self.e.run["run_id"])
        aggregate = next(t for t in self.e.tasks() if t["task_id"] == registered["tasks"]["PARTICIPANT"])
        self.assertEqual(aggregate["status"], "succeeded", aggregate.get("error"))
        fixed = fresh.verified_package(aggregate["table_store_run_id"])[1]
        self.assertIn(hc["record_ref"], fixed["unit_contract"]["definition_adoption_refs"])
        self.assertEqual(fixed["datasets"]["table"]["rows"][0]["value"], 2)
        self.assertEqual(fixed["datasets"]["table"]["rows"][0]["participant_id"], "TEST-person")
        human = self.client.get(self.human_url).get_json()
        option = next(o for o in human["options"] if o["target_kind"] == "participant_mapping")
        correction = self.mapping_statement(option, decision="defer")
        response = self.client.post(self.human_url, json=correction)
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertIn(fresh.connected_output_descriptor(aggregate["table_store_run_id"])["asset_key"], response.get_json()["stale_assets"])
        self.assertEqual(fresh.verified_package(prep["table_store_run_id"])[3], sealed)
        self.assertIsNone(self.options()["participant_context"]["confirmed_mapping"])
        denied = self.client.post(self.url, json=plan)
        self.assertEqual(denied.status_code, 400, denied.get_json()); self.assertEqual(len(self.e.tasks()), 2)

    def test_mapping_correction_during_get_rejects_old_definition_values(self):
        self.post(self.plan()); self.e.service._drain_tasks(self.e.run["run_id"])
        option = self.options()["participant_context"]["human_record_option"]
        self.assertEqual(self.client.post(self.human_url, json=self.mapping_statement(option)).status_code, 201)
        option = next(o for o in self.client.get(self.human_url).get_json()["options"] if o["target_kind"] == "participant_mapping")
        correction = self.mapping_statement(option, decision="defer")
        original = AnalysisStore.bind_asset_inputs; corrected = []
        def concurrent_correction(store, **kwargs):
            receipt = original(store, **kwargs)
            if not corrected:
                corrected.append(self.client.post(self.human_url, json=correction).status_code)
            return receipt
        with patch.object(AnalysisStore, "bind_asset_inputs", concurrent_correction):
            response = self.client.get(self.options_url)
        self.assertEqual(corrected, [201])
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(len(self.e.tasks()), 1)
        self.assertIsNone(self.options()["participant_context"]["confirmed_mapping"])

    def test_normal_bound_old_generation_cancel_source_revocation_and_tamper_no_task(self):
        page = self.options(); plan = self.plan(page)
        with self.e.fixture.connect() as db:
            old = db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (self.e.run["run_id"],)).fetchone()[0]
        for change, reason in (({"generation": 2}, "asset_plan_changed"), ({"cancel_requested": True}, "table_run_stopped"),
                               ({"stale": True}, "revision_conflict")):
            with self.e.fixture.connect() as db:
                run = json.loads(old); run.update(change)
                db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (canonical(run).decode(), self.e.run["run_id"]))
            response = self.client.post(self.url, json=plan)
            self.assertEqual(response.status_code, 409, response.get_json()); self.assertEqual(response.get_json()["reason_code"], reason)
            self.assertEqual(self.e.tasks(), [])
        with self.e.fixture.connect() as db:
            db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (old, self.e.run["run_id"]))
        self.e.service.source_fingerprint = lambda _: "TEST-updated-source"
        self.assertEqual(self.client.post(self.url, json=plan).status_code, 409); self.assertEqual(self.e.tasks(), [])
        self.e.service.source_fingerprint = lambda _: self.e.run["input_hash"]
        self.namespace["archive_source_stamp"] = lambda *args, **kwargs: "TEST-updated-source"
        self.assertEqual(self.client.get(self.options_url).status_code, 409)
        self.namespace["archive_source_stamp"] = lambda *args, **kwargs: self.e.run["input_hash"]
        state = copy.deepcopy(self.e.h.state); state.update(revoked=True, state_revision=2, policy_revision=2)
        self.e.fixture.register(states=[state])
        response = self.client.post(self.url, json=plan)
        self.assertEqual(response.status_code, 400, response.get_json()); self.assertEqual(self.e.tasks(), [])
        self.assertNotIn(plan["steps"][0]["inputs"][0]["source"], [o["source"] for o in self.options()["inputs"]])
        artifact = next(a for a in self.e.service.table_store.artifacts(self.e.h.source_id) if a["name"] == "tables/correlations.json")
        path = safe_path(self.e.service.table_store.root, artifact["path"]); path.write_bytes(path.read_bytes() + b" ")
        response = self.client.post(self.url, json=plan)
        self.assertNotIn(response.status_code, (200, 202)); self.assertEqual(self.e.tasks(), [])
        self.assertEqual(self.e.service.table_store._human_packages()[0], [])

    def test_normal_bound_rejects_client_columns_units_and_missing_reader(self):
        plan = self.plan()
        for key, value in (("unit_ids", ["TEST-forged-unit"]), ("columns", ["unit_id", "conversation_id", "value_status", "TEST-forged-column"])):
            bad = copy.deepcopy(plan); bad["steps"][0]["parameters"][key] = value
            response = self.client.post(self.url, json=bad)
            self.assertEqual(response.status_code, 400, response.get_json()); self.assertEqual(self.e.tasks(), [])
        app = Flask("no-reader"); register_orchestration_routes(app, self.writer, lambda _: {})
        self.writer.reset_mock(); self.assertEqual(app.test_client().get(self.options_url).status_code, 503); self.writer.assert_not_called()

    def test_get_generation_drift_is_fenced_and_saved_projection_join_uses_real_choices(self):
        method = AnalysisStore.asset_plan_options
        def drift(store, **kwargs):
            result = method(store, **kwargs)
            with self.e.fixture.connect() as db:
                run = self.e.service._read_run(db, self.e.run["run_id"]); run["generation"] = 2
                db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (canonical(run).decode(), run["run_id"]))
            return result
        with patch.object(AnalysisStore, "asset_plan_options", drift):
            r = self.client.get(self.options_url)
        self.assertEqual(r.status_code, 409, r.get_json()); self.assertEqual(r.get_json()["reason_code"], "asset_plan_changed")
        self.writer.assert_not_called(); self.assertEqual(self.e.tasks(), [])
        page = self.options(); plan = self.plan(page)
        left = plan["steps"][0]; left["step_id"] = "LEFT"; left["parameters"]["columns"] = ["unit_id", "conversation_id", "value_status", "n"]
        right = copy.deepcopy(left); right["step_id"] = "RIGHT"; right["parameters"]["columns"][-1] = "category"
        plan["steps"].append(right)
        registration = self.post(plan); self.e.service._drain_tasks(self.e.run["run_id"])
        page = self.options(); task_ids = registration["tasks"]
        carriers = [next(o for o in page["inputs"] if o["source"].get("asset_key", {}).get("store_run_id") ==
            next(t for t in self.e.tasks() if t["task_id"] == task_ids[s])["table_store_run_id"]) for s in ("LEFT", "RIGHT")]
        joined = {**page["plan_template"], "steps": [{"step_id": "JOIN", "method_id": "unit_join", "parameters": {"keys": ["unit_id"]},
            "scope": left["scope"], "inputs": [{"input_ref_id": o["input_ref_id"], "role": "data_input", "selection": "selected",
                "omission_reason": None, "source": o["source"]} for o in carriers]}]}
        outcome = self.post(joined); self.e.service._drain_tasks(self.e.run["run_id"])
        task = next(t for t in self.e.tasks() if t["task_id"] == outcome["tasks"]["JOIN"])
        self.assertEqual(task["status"], "succeeded", task.get("error"))
        fixed = AnalysisStore(self.e.fixture.path, self.e.fixture.connect).verified_package(task["table_store_run_id"])[1]
        self.assertEqual(len(fixed["datasets"]["table"]["rows"]), 6)
        self.assertEqual({r["value_status"] for r in fixed["datasets"]["table"]["rows"]}, {"observed", "missing", "unprocessed", "unknown", "excluded"})

    def test_conflicting_saved_mapping_records_require_resolution_not_last_wins(self):
        plan = self.plan(); second = copy.deepcopy(plan["steps"][0]); second["step_id"] = "SECOND"
        second["parameters"]["columns"].remove("category"); plan["steps"].append(second)
        self.post(plan); self.e.service._drain_tasks(self.e.run["run_id"])
        records = self.client.get(self.human_url).get_json()["options"]
        options = [o for o in records if o["target_kind"] == "participant_mapping"]
        self.assertEqual(len(options), 2)
        for index, option in enumerate(options):
            statement = self.mapping_statement(option)
            statement["record"]["record_id"] += ":" + option["asset_key"]["artifact_id"]
            statement["record"]["record_ref"]["target_id"] = "human-source:" + statement["record"]["record_id"]
            statement["source_text"] = statement["source_text"].replace("TEST-person", "TEST-person-" + str(index))
            statement["record"]["record_ref"]["content_hash"] = "sha256:" + hashlib.sha256(statement["source_text"].encode()).hexdigest()
            response = self.client.post(self.human_url, json=statement); self.assertEqual(response.status_code, 201, response.get_json())
        context = self.options()["participant_context"]
        self.assertFalse(context["enabled"]); self.assertIsNone(context["confirmed_mapping"])
        self.assertEqual(context["reason_code"], "participant_mapping_ambiguous")
        option = next(o for o in self.client.get(self.human_url).get_json()["options"] if o["asset_key"] == options[1]["asset_key"])
        correction = self.mapping_statement(option, decision="defer")
        response = self.client.post(self.human_url, json=correction); self.assertEqual(response.status_code, 201, response.get_json())
        context = self.options()["participant_context"]
        self.assertTrue(context["enabled"]); self.assertEqual(context["human_record_option"]["asset_key"], options[0]["asset_key"])
        self.assertEqual(context["confirmed_mapping"]["assignments"][0]["participant_id"], "TEST-person-0")


if __name__ == "__main__": unittest.main()
