"""Focused tests for the Flask-free analysis query boundary."""

import unittest

import app
import test_content_analysis as support
from gurumoji.analysis_store import StoreConflict
from gurumoji.handlers.analysis_commands import AnalysisCommands, AnalysisCommandNotFound
from gurumoji.handlers.analysis_queries import AnalysisQueries, AnalysisQueryNotFound
from gurumoji.analysis_method_registry import METHODS, REGISTRY_VERSION


class FakeStore:
    def __init__(self):
        self.rows = [{
            "id": "run-1", "stale": False, "input_fingerprint": "old",
            "local_path": "C:/private/result.json",
        }]

    def list(self, item_id):
        return self.rows

    def public(self, row, *, local=False):
        result = dict(row)
        if not local:
            result.pop("local_path", None)
        return result

    def read_artifact(self, artifact_id):
        if artifact_id == "missing":
            raise LookupError(artifact_id)
        return ({"run_id": "run-1", "media_type": "application/json",
                 "name": "nested/result.json"}, b"{}")

    def get(self, run_id):
        return {"id": run_id, "item_id": "item-1"}


class AnalysisQueryHandlerTests(unittest.TestCase):
    def queries(self, *, local=False, find_item=lambda item_id: {"id": item_id}):
        return AnalysisQueries(
            store=FakeStore(), find_item=find_item,
            source_fingerprint=lambda _item: "current",
            expose_local_paths=local,
        )

    def test_runs_mark_stale_and_only_publish_local_paths_when_allowed(self):
        remote = self.queries().runs("item-1")["runs"][0]
        local = self.queries(local=True).runs("item-1")["runs"][0]
        self.assertTrue(remote["stale"])
        self.assertNotIn("local_path", remote)
        self.assertEqual(local["local_path"], "C:/private/result.json")

    def test_missing_item_and_artifact_are_not_found_without_flask(self):
        missing_item = self.queries(find_item=lambda _item_id: None)
        with self.assertRaises(AnalysisQueryNotFound):
            missing_item.runs("missing")
        with self.assertRaises(AnalysisQueryNotFound):
            self.queries().artifact("missing")

    def test_artifact_contract_is_framework_independent(self):
        artifact = self.queries().artifact("artifact-1")
        self.assertEqual((artifact.data, artifact.media_type, artifact.download_name),
                         (b"{}", "application/json", "result.json"))


class TrackingLock:
    def __init__(self):
        self.active = False

    def __enter__(self):
        self.active = True

    def __exit__(self, *_args):
        self.active = False


class FakeCommandStore(FakeStore):
    def __init__(self):
        super().__init__()
        self.run = {
            "id": "run-1", "item_id": "item-1",
            "input_fingerprint": "saved",
        }
        self.retry_count = 0

    def get(self, run_id):
        return self.run if run_id == self.run["id"] else None

    def retry(self, run_id):
        self.retry_count += 1
        return self.get(run_id)


class AnalysisCommandHandlerTests(unittest.TestCase):
    def setUp(self):
        self.item = {"id": "item-1", "revision_count": 2, "analysis_revision": 3}
        self.store = FakeCommandStore()
        self.lock = TrackingLock()
        self.archived = []
        self.stale = []
        self.build_count = 0

        def build(_item):
            self.build_count += 1
            return {"research": {"linguistics": {"morphemes": []}}}

        def archive(item, analysis, request_id, **options):
            self.assertTrue(self.lock.active)
            self.assertIs(options["store"], self.store)
            self.archived.append((item, analysis, request_id, options))
            return self.store.run

        self.commands = AnalysisCommands(
            store=self.store,
            find_item=lambda item_id: self.item if item_id == "item-1" else None,
            build_analysis=build,
            search_kwic=lambda *_args, **_kwargs: {"hits": [], "query": "q",
                                                   "mode": "literal", "speaker": ""},
            archive_analysis=archive,
            source_fingerprint=lambda _item: "current",
            mark_stale=self.stale.append,
            write_lock=self.lock,
            expose_local_paths=False,
        )

    def test_save_keeps_revision_check_calculation_and_archive_under_shared_lock(self):
        result = self.commands.save(
            "item-1", request_id="archive-request-0001",
            source_revision=2, analysis_revision=3, kwic_request=None,
            app_url="http://127.0.0.1:7860/",
        )
        self.assertEqual(result["id"], "run-1")
        self.assertEqual((self.build_count, len(self.archived)), (1, 1))
        self.assertFalse(self.lock.active)

    def test_revision_conflict_stops_before_calculation(self):
        with self.assertRaises(StoreConflict):
            self.commands.save(
                "item-1", request_id="archive-request-0001",
                source_revision=1, analysis_revision=3, kwic_request=None,
                app_url="http://127.0.0.1:7860/",
            )
        self.assertEqual((self.build_count, self.archived), (0, []))

    def test_retry_marks_changed_input_stale_and_never_recalculates(self):
        result = self.commands.retry_vault("run-1")
        self.assertEqual(result["id"], "run-1")
        self.assertEqual(self.stale, ["run-1"])
        self.assertEqual((self.store.retry_count, self.build_count), (1, 0))

    def test_missing_run_is_reported_without_entering_the_lock(self):
        with self.assertRaises(AnalysisCommandNotFound):
            self.commands.retry_vault("missing")
        self.assertFalse(self.lock.active)


class AnalysisRouteStructureTests(unittest.TestCase):
    def test_three_read_routes_are_registered_once_with_expected_methods(self):
        expected = {
            "/api/analysis/methods",
            "/api/library/<item_id>/analysis/runs",
            "/api/analysis/artifacts/<artifact_id>",
        }
        rules = [rule for rule in app.app.url_map.iter_rules()
                 if str(rule.rule) in expected and "GET" in rule.methods]
        self.assertEqual({str(rule.rule) for rule in rules}, expected)
        self.assertEqual(len(rules), len(expected))
        for rule in rules:
            self.assertEqual(rule.methods, {"GET", "HEAD", "OPTIONS"})
            self.assertTrue(rule.endpoint.startswith("analysis_queries."))

        writes = {
            str(rule.rule): rule for rule in app.app.url_map.iter_rules()
            if "POST" in rule.methods and str(rule.rule) in {
                "/api/library/<item_id>/analysis/runs",
                "/api/analysis/runs/<run_id>/vault",
            }
        }
        self.assertEqual(len(writes), 2)
        self.assertTrue(all(rule.endpoint.startswith("analysis_queries.")
                            for rule in writes.values()))


class AnalysisReadRouteContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests(
            "test_generated_result_persists_and_becomes_stale_on_edit"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client

    def test_methods_runs_and_artifact_keep_the_http_contract(self):
        catalog = self.client.get("/api/analysis/methods")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.get_json()["version"], REGISTRY_VERSION)
        self.assertEqual(len(catalog.get_json()["methods"]), len(METHODS))

        self.assertEqual(
            self.client.get("/api/library/missing/analysis/runs").status_code, 404
        )
        self.assertEqual(
            self.client.get("/api/analysis/artifacts/missing").status_code, 404
        )

        payload = self.fixture.payload("query-route-contract-0001")
        saved = self.client.post(self.fixture.url + "/runs", json=payload).get_json()["run"]
        runs = self.client.get(self.fixture.url + "/runs")
        self.assertEqual(runs.status_code, 200)
        self.assertEqual(runs.get_json()["runs"][0]["id"], saved["id"])
        artifact = self.client.get(saved["artifacts"][0]["url"])
        self.assertEqual(artifact.status_code, 200)
        self.assertIn("attachment", artifact.headers["Content-Disposition"])

    def test_save_validation_stays_at_the_http_boundary(self):
        response = self.client.post(self.fixture.url + "/runs", json={"kwic": []})
        self.assertEqual(response.status_code, 400)
        payload = self.fixture.payload("query-route-invalid-0001")
        response = self.client.post(self.fixture.url + "/runs", json={**payload, "kwic": []})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "検索条件が正しくありません。")


if __name__ == "__main__":
    unittest.main()
