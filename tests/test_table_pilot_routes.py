"""Opt-in HTTP/service wiring with private SQLite, no models or network."""
import ast
import copy
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Flask

import test_analysis_asset_bindings as fixtures
from gurumoji.analysis_core import fingerprint
from gurumoji.analysis_store import AnalysisStore
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes


class TablePilotRouteTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TablePilotHandlerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f, self.service, self.run = self.fixture.f, self.fixture.service, self.fixture.run
        app = Flask(__name__)
        register_orchestration_routes(app, lambda: self.service, lambda _: self.fail("No model preflight"))
        self.client = app.test_client()
        self.url = f"/api/library/TEST-conversation/analysis/orchestration/{self.run['run_id']}/table-pilot"

    def options(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        return response.get_json()

    def request(self, method, assets=None):
        options = self.options()
        assets = assets or [self.fixture.asset]
        selected = [next(c for c in options["inputs"] if c["source"]["asset_key"] == a["asset_key"]) for a in assets]
        request = copy.deepcopy(selected[0]["projection_request"])
        request["parameters"] = self.fixture.request(method)["parameters"]
        request["bindings"]["slot"] = next(m["slot"] for m in options["methods"] if m["method_id"] == method)
        request["bindings"]["inputs"] = []
        for index, candidate in enumerate(selected):
            ref = copy.deepcopy(candidate["projection_request"]["bindings"]["inputs"][0])
            ref["input_ref_id"] = f"table-input-{index}"
            request["bindings"]["inputs"].append(ref)
        if method == "table_projection":
            request["parameters"] = copy.deepcopy(selected[0]["projection_request"]["parameters"])
        return request

    def post(self, method, request):
        response = self.client.post(self.url + "/" + method, json=request)
        self.assertEqual(response.status_code, 202, response.get_json())
        return response.get_json()["task"]

    def drain_scheduled(self):
        worker = self.service._workers[self.run["run_id"]]
        worker.join(timeout=10)
        self.assertFalse(worker.is_alive(), "Synthetic scheduler did not finish")

    def test_get_is_read_only_and_projection_template_is_directly_usable(self):
        with self.f.connect() as db:
            before = list(db.iterdump())
        scheduled = Mock()
        self.service._schedule = scheduled
        options = self.options()
        self.assertEqual(len(options["methods"]), 5)
        self.assertEqual(options["library_id"], "TEST-library")
        self.assertEqual(options["input"]["input_hash"], self.run["input_hash"])
        self.assertEqual(options["context"]["plan_hash"], fingerprint({"run_id": self.run["run_id"], "input_hash": self.run["input_hash"]}))
        self.assertEqual(options["scope_requirements"], ["scope_id", "scope_manifest_hash"])
        self.assertEqual(len(options["inputs"]), 1)
        self.assertEqual(self.client.get(self.url + "?offset=1").get_json()["inputs"], [])
        for offset in ("-1", "invalid", "10001"):
            self.assertEqual(self.client.get(self.url + "?offset=" + offset).status_code, 400)
        with self.f.connect() as db:
            self.assertEqual(list(db.iterdump()), before)
        scheduled.assert_not_called()
        task = self.post("table_projection", options["inputs"][0]["projection_request"])
        context = task["intent"]["table_pilot"]["bindings"]["context"]
        self.assertEqual(context["consumer_task_id"], task["task_id"])
        self.assertEqual(context["generation"], self.run["generation"])

    def test_five_methods_use_real_scheduler_handler_store_and_fresh_reload(self):
        # Narrow the existing thread driver's work to registered code tasks;
        # the production Core loop and all model adapters are deliberately unused.
        self.service.run = self.service._drain_tasks
        self.service.schedule = True
        original_schedule = self.service._schedule
        committed = []
        def scheduled(run_id):
            # Separate connection sees the task before the scheduler starts.
            with self.f.connect() as db:
                committed.append(db.execute("SELECT COUNT(*) FROM orchestration_tasks WHERE run_id=?", (run_id,)).fetchone()[0])
            original_schedule(run_id)
        self.service._schedule = scheduled
        outputs = []
        for method, assets in (("table_projection", None), ("table_aggregate", "projection"),
                               ("table_join", "parents"), ("table_frequency", "join"), ("table_crosstab", "join")):
            selected = None if assets is None else ([outputs[0]] if assets == "projection" else
                        outputs[:2] if assets == "parents" else [outputs[2]])
            task = self.post(method, self.request(method, selected))
            self.drain_scheduled()
            state = self.fixture.state_of(task)
            self.assertEqual(state["status"], "succeeded", state["error"])
            fresh = AnalysisStore(self.f.path, self.f.connect)
            saved = fresh.verified_package(state["table_store_run_id"])[1]
            raw = self.fixture.raw_of(task)
            self.assertEqual(saved["datasets"], raw["datasets"])
            self.assertEqual(saved["population"], raw["population"])
            table = fresh.read_table(state["table_store_run_id"], "table")
            self.assertEqual(table["row_count"], 6 if method in {"table_projection", "table_aggregate", "table_join"} else 2 if method == "table_frequency" else 4)
            if method in {"table_projection", "table_aggregate", "table_join"}:
                outputs.append(self.fixture.reusable(state))
        self.assertEqual(committed, [1, 2, 3, 4, 5])
        self.assertEqual(self.service.status("TEST-conversation", self.run["run_id"])["code_executions"], 5)

    def test_duplicate_request_returns_same_task_and_executes_once(self):
        request = self.request("table_crosstab")
        self.service.run = self.service._drain_tasks
        self.service.schedule = True
        task = self.post("table_crosstab", request)
        self.drain_scheduled()
        response = self.client.post(self.url + "/table_crosstab", json=request)
        self.assertEqual(response.status_code, 200, response.get_json())
        repeated = response.get_json()["task"]
        self.assertTrue(repeated["registration_duplicate"])
        self.assertEqual(repeated["task_id"], task["task_id"])
        self.assertEqual(self.service.status("TEST-conversation", self.run["run_id"])["code_executions"], 1)
        with self.f.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_tasks").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_results").fetchone()[0], 1)

    def test_invalid_contracts_are_rejected_before_registration(self):
        valid = self.request("table_frequency")
        mutations = {"plan": lambda r: r["bindings"]["context"].update(plan_hash=fixtures.h("wrong")),
                     "generation": lambda r: r["bindings"]["context"].update(generation=2),
                     "consumer": lambda r: r["bindings"]["inputs"][0].update(consumer_task_id="foreign"),
                     "scope": lambda r: r["bindings"]["context"].update(scope_manifest_hash=fixtures.h("wrong")),
                     "library": lambda r: r["bindings"]["inputs"][0]["source"]["asset_key"].update(library_id="foreign"),
                     "hash": lambda r: r["bindings"]["inputs"][0]["source"].update(content_hash=fixtures.h("wrong")),
                     "local_only": lambda r: r["bindings"]["context"].update(destination="cloud"),
                     "actor": lambda r: r.update(actor="AI")}
        for kind, mutate in mutations.items():
            with self.subTest(kind=kind):
                value = copy.deepcopy(valid)
                mutate(value)
                response = self.client.post(self.url + "/table_frequency", json=value)
                self.assertEqual(response.status_code, 400, response.get_json())
                self.assertIn("reason_code", response.get_json())
        for method in ("participation", "correlation", "not-registered"):
            response = self.client.post(self.url + "/" + method, json=valid)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json()["reason_code"], "table_method_unsupported")
        for value in ([], None, {"padding": "x" * 131072}):
            self.assertEqual(self.client.post(self.url + "/table_frequency", json=value).status_code, 400)
        with self.f.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_tasks").fetchone()[0], 0)

    def test_stopped_cancelled_stale_recovery_and_foreign_run_reject(self):
        request = self.request("table_frequency")
        for change, code in (({"status": "stopped"}, "table_run_stopped"), ({"cancel_requested": True}, "table_run_stopped"),
                             ({"stale": True}, "revision_conflict"), ({"status": "recovery_required"}, "table_run_unavailable")):
            with self.subTest(change=change):
                with self.service._db() as db:
                    run = self.service._read_run(db, self.run["run_id"])
                    original = copy.deepcopy(run)
                    run.update(change)
                    self.service._write_run(db, run)
                response = self.client.post(self.url + "/table_frequency", json=request)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.get_json()["reason_code"], code)
                self.assertEqual(self.client.get(self.url).status_code, 409)
                with self.service._db() as db:
                    self.service._write_run(db, original)
        self.service.source_fingerprint = lambda _: fixtures.h("changed source")
        self.assertEqual(self.client.post(self.url + "/table_frequency", json=request).status_code, 409)
        self.assertEqual(self.client.post(self.url.replace("TEST-conversation", "foreign") + "/table_frequency", json=request).status_code, 404)

    def test_revoke_before_registration_or_execution_never_saves(self):
        request = self.request("table_frequency")
        task = self.post("table_frequency", request)
        self.fixture.revoke()
        self.assertEqual(self.options()["inputs"], [])
        response = self.client.post(self.url + "/table_frequency", json=request)
        self.assertEqual(response.status_code, 400, response.get_json())
        self.service._drain_tasks(self.run["run_id"])
        state = self.fixture.state_of(task)
        self.assertNotEqual(state["status"], "succeeded")
        self.assertNotIn("table_store_run_id", state)

    def test_capacity_and_store_authority_are_not_bypassed(self):
        request = self.request("table_frequency")
        self.post("table_frequency", request)
        with self.service._db() as db:
            run = self.service._read_run(db, self.run["run_id"])
            run["config"]["max_tasks"] = 1
            self.service._write_run(db, run)
        response = self.client.post(self.url + "/table_crosstab", json=self.fixture.request("table_crosstab"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["reason_code"], "table_task_limit")
        self.service.table_store = SimpleNamespace(database_file=self.f.path.with_name("foreign.sqlite3"))
        self.assertEqual(self.client.post(self.url + "/table_frequency", json=request).get_json()["reason_code"], "table_store_mismatch")

    def test_foreign_source_snapshot_is_not_listed_or_registered(self):
        snapshot = {**self.f.snapshot, "input_hash": fixtures.h("foreign input")}
        saved = self.f.store.save(item_id="TEST-conversation", kind="ai_insights", snapshot=snapshot,
            result={"schema_version": 1, "parameters": {}, "TEST_fixture_only": True},
            datasets={"correlations": (self.fixture.fields, self.fixture.values)}, request_id="TEST-foreign-input",
            input_fingerprint=fingerprint(snapshot), source_revision=1, analysis_revision=1, publish=False)
        asset, state = self.f.descriptors(saved)
        original, original_state = self.f.descriptors(saved, original=True)
        for key in ("member_ids", "context_ids"):
            asset["scope"][key] = copy.deepcopy(self.fixture.asset["scope"][key])
        asset["scope"]["manifest_hash"] = fingerprint({k: v for k, v in asset["scope"].items() if k != "manifest_hash"})
        original["scope"] = copy.deepcopy(asset["scope"])
        asset["variables"] = copy.deepcopy(self.fixture.asset["variables"])
        self.f.register([asset], originals=[original], states=[state, original_state])
        self.assertNotIn(asset["asset_key"], [c["source"]["asset_key"] for c in self.options()["inputs"]])
        response = self.client.post(self.url + "/table_frequency", json=self.fixture.request("table_frequency", [asset]))
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(response.get_json()["reason_code"], "table_source_mismatch")


class TablePilotFactoryTests(unittest.TestCase):
    def test_actual_app_factory_passes_existing_archive_store_and_keeps_cache(self):
        # Execute the real factory alone, avoiding the app's global runtime/DB imports.
        path = Path(__file__).resolve().parents[1] / "src/gurumoji/app.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "analysis_orchestration_service")
        service, store = Mock(), object()
        namespace = {"DATABASE_FILE": path, "_orchestration_service_lock": threading.RLock(),
                     "_orchestration_services": {}, "AnalysisOrchestrationService": Mock(return_value=service),
                     "analysis_archive_store": Mock(return_value=store), "make_staged_initial_builder": Mock(),
                     "library_write_lock": threading.RLock(), "ORCHESTRATION_ADAPTER_VERSION": "TEST-only",
                     "make_obsidian_management_agent": Mock(), "make_expert_agent_registry": Mock()}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
        factory = namespace["analysis_orchestration_service"]
        self.assertIs(factory(), service)
        self.assertIs(factory(), service)
        namespace["AnalysisOrchestrationService"].assert_called_once()
        self.assertIs(namespace["AnalysisOrchestrationService"].call_args.kwargs["table_store"], store)
        namespace["analysis_archive_store"].assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
