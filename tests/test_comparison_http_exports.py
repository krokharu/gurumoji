"""Real HTTP exports of fixed comparisons; synthetic temporary data only."""

from contextlib import contextmanager, ExitStack
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import app
from gurumoji import research_analysis
from gurumoji.analysis_store import AnalysisStore, canonical


class ComparisonHttpExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="comparison-http-exports-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name, value in {
            "DATABASE_FILE": self.root / "library.sqlite3",
            "DATA_DIRECTORY": self.root,
            "MEDIA_DIRECTORY": self.root / "media",
            "THUMBNAIL_DIRECTORY": self.root / "thumbnails",
            "TRAINING_AUDIO_DIRECTORY": self.root / "training",
        }.items():
            self.enterContext(patch.object(app, name, value))
        for name in ("_load_ginza", "_load_sudachi"):
            self.enterContext(patch.object(research_analysis, name, return_value=(None, "synthetic fallback")))
        self.enterContext(patch.object(app, "call_ai_json", side_effect=AssertionError("No AI allowed")))
        research_analysis._RESEARCH_CACHE.clear()
        self.addCleanup(research_analysis._RESEARCH_CACHE.clear)
        app.initialize_library()
        self.application = app.create_app()
        self.client = self.application.test_client()
        self.store = app.analysis_archive_store()
        self.counter = 0
        for item_id in ("synthetic_a", "synthetic_b"):
            app.upsert_library_item(
                item_id=item_id, source_name=item_id, output_dir=self.root / item_id,
                media_path=None, language="ja", speaker_names={"S": "合成話者"},
                segments=[{"id": item_id + "_1", "speaker": "S", "start": 0, "end": 1,
                           "text": "合成の発話", "emotions": {"synthetic": {"label": "sad"}}}],
                outline=None, emotion_analysis=None, files=[], write_srt=False, write_json=True,
                session_profile={"comparison_group": "synthetic", "session_type": "focus_group"},
            )

    def save_comparison(self):
        self.counter += 1
        if self.counter > 1:
            # Each negative subcase needs its own immutable run, not deduplication.
            with app.database_connection() as connection:
                connection.execute("UPDATE library_items SET revision_count=revision_count+1 WHERE id='synthetic_a'")
        selection = {"item_ids": ["synthetic_a", "synthetic_b"], "allow_different_content": False}
        preview = self.client.post("/api/library/interview-comparison", json=selection)
        self.assertEqual(preview.status_code, 200, preview.get_json())
        response = self.client.post("/api/library/interview-comparison/runs", json={
            **selection, "request_id": f"comparison-http-{self.counter:04}",
            "input_fingerprints": preview.get_json()["input_fingerprints"],
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        run = response.get_json()["run"]
        self.assertEqual((run["status"], run["kind"]), ("completed", "interview_comparison"))
        self.assertTrue(run["item_id"].startswith("comparison-"))
        self.assertIsNone(app.library_row(run["item_id"]))
        self.assertEqual(self.store.members(run["id"]), selection["item_ids"])
        return run

    def fresh_reader(self):
        old_store, old_application = self.store, self.application
        self.store = app.analysis_archive_store()
        self.application = app.create_app()
        self.client = self.application.test_client()
        self.assertIsNot(self.store, old_store)
        self.assertIsNot(self.application, old_application)

    def state(self):
        with app.database_connection() as connection:
            database = "\n".join(connection.iterdump())
        hashes = {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in self.root.rglob("*") if path.is_file()}
        return database, hashes

    @contextmanager
    def read_only(self):
        before = self.state()
        connect = app.database_connection

        @contextmanager
        def read_connection():
            with connect() as connection:
                connection.execute("PRAGMA query_only=ON")
                yield connection

        with ExitStack() as stack:
            stack.enter_context(patch.object(app, "database_connection", read_connection))
            for name in ("group_analysis_for_row", "build_interview_comparison", "archive_source_stamp"):
                stack.enter_context(patch.object(app, name, side_effect=AssertionError("No current analysis on export")))
            for name in ("save", "retry", "publish"):
                stack.enter_context(patch.object(AnalysisStore, name, side_effect=AssertionError("No write on export")))
            yield
        self.assertEqual(self.state(), before, "GET must preserve database, source and saved file hashes")

    def artifact(self, run, name):
        return next(row for row in self.store.artifacts(run["id"]) if row["name"] == name)

    def replace_artifact(self, run, name, data):
        """Mutate a synthetic package with matching hashes to test deeper guards."""
        artifact = self.artifact(run, name)
        (self.store.root / artifact["path"]).write_bytes(data)
        artifact.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
        with self.store.connect() as connection:
            connection.execute("UPDATE analysis_artifacts SET sha256=?,bytes=? WHERE id=?",
                               (artifact["sha256"], artifact["bytes"], artifact["id"]))
        if name != "manifest.json":
            manifest = json.loads(self.store.read_artifact(self.artifact(run, "manifest.json")["id"])[1])
            manifest["artifacts"] = [artifact if row["name"] == name else row for row in manifest["artifacts"]]
            self.replace_artifact(run, "manifest.json", canonical(manifest))

    def make_legacy_package(self, run):
        """Remove only the additive typed-table extension in a temporary fixture."""
        manifest = json.loads(self.store.read_artifact(self.artifact(run, "manifest.json")["id"])[1])
        typed = [row for row in run["artifacts"] if row["name"].startswith("tables/") and row["name"].endswith(".json")]
        for row in typed:
            artifact = self.artifact(run, row["name"])
            (self.store.root / artifact["path"]).unlink()
            with self.store.connect() as connection:
                connection.execute("DELETE FROM analysis_artifacts WHERE id=?", (artifact["id"],))
        removed = {row["id"] for row in typed}
        manifest["artifacts"] = [row for row in manifest["artifacts"] if row["id"] not in removed]
        manifest.pop("table_format_version")
        manifest.pop("typed_tables")
        self.replace_artifact(run, "manifest.json", canonical(manifest))
        return self.store.public(self.store.get(run["id"]))

    def assert_exports(self, run, expected):
        with self.read_only():
            response = self.client.get(f"/api/analysis/runs/{run['id']}/export.zip")
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(response.mimetype, "application/zip")
            with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
                self.assertEqual(len(archive.namelist()), len(expected))
                self.assertEqual({name: archive.read(name) for name in archive.namelist()}, expected)
            for artifact in run["artifacts"]:
                with self.subTest(artifact=artifact["name"]):
                    response = self.client.get(artifact["url"])
                    self.assertEqual(response.status_code, 200, response.get_json())
                    self.assertEqual(response.data, expected[artifact["name"]])
                    self.assertEqual(hashlib.sha256(response.data).hexdigest(), artifact["sha256"])
                    self.assertEqual(len(response.data), artifact["bytes"])

    def assert_refused(self, run, status=409):
        self.fresh_reader()
        with self.read_only():
            response = self.client.get(f"/api/analysis/runs/{run['id']}/export.zip")
            self.assertEqual(response.status_code, status, response.get_json())
            # Even an intact sibling cannot escape a corrupt comparison package.
            for artifact in run["artifacts"]:
                response = self.client.get(artifact["url"])
                self.assertEqual(response.status_code, status, (artifact["name"], response.get_json()))

    def test_api_save_fresh_application_zip_and_every_artifact_are_exact_and_read_only(self):
        run = self.save_comparison()
        self.fresh_reader()
        snapshot, result, manifest, content = self.store.verified_package(run["id"])
        self.assertEqual(snapshot["kind"], run["kind"])
        self.assertEqual(result["parameters"]["item_ids"], self.store.members(run["id"]))
        self.assertEqual(manifest["table_format_version"], 1)
        self.assertIn("tables/comparison_interviews.json", content)
        self.assertIn("tables/comparison_interviews.csv", content)
        self.assert_exports(run, content)
        self.assertIsNone(app.library_row(run["item_id"]))

    def test_stale_historical_comparison_keeps_saved_bytes_after_new_source_and_run(self):
        first = self.save_comparison()
        content = self.store.verified_package(first["id"])[3]
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET source_name='new synthetic title',segments_json=?,"
                               "revision_count=revision_count+1 WHERE id='synthetic_a'",
                               (json.dumps([{"id": "new", "speaker": "S", "text": "現在の別発話"}]),))
        latest = self.save_comparison()
        self.assertNotEqual(first["id"], latest["id"])
        self.fresh_reader()
        self.assertTrue(self.store.get(first["id"])["stale"])
        self.assertNotEqual(content["input.json"], self.store.verified_package(latest["id"])[3]["input.json"])
        self.assert_exports(first, content)

    def test_unknown_missing_and_incomplete_exports_keep_404(self):
        run = self.save_comparison()
        with self.read_only():
            for url in ("/api/analysis/runs/unknown/export.zip", "/api/analysis/artifacts/unknown"):
                self.assertEqual(self.client.get(url).status_code, 404)
        for status in ("writing", "failed", "interrupted"):
            with self.subTest(status=status):
                with self.store.connect() as connection:
                    connection.execute("UPDATE analysis_runs SET status=? WHERE id=?", (status, run["id"]))
                self.assert_refused(run, 404)
        with self.store.connect() as connection:
            connection.execute("DELETE FROM analysis_runs WHERE id=?", (run["id"],))
        self.assert_refused(run, 404)

    def test_normal_item_run_preview_exports_and_missing_item_rules_are_unchanged(self):
        run = self.store.save(item_id="synthetic_a", kind="text_analysis", snapshot={"segments": []},
                              result={"parameters": {}}, datasets={"values": (["value"], [{"value": 0}])},
                              request_id="normal-http-0001", input_fingerprint="saved",
                              source_revision=0, analysis_revision=0, publish=False)
        public = self.store.public(run)
        self.fresh_reader()
        self.assert_exports(public, self.store.verified_package(run["id"])[3])
        url = f"/api/library/synthetic_a/analysis/runs/{run['id']}"
        artifact_id = self.artifact(run, "tables/values.csv")["id"]
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url + "/previews/" + artifact_id).status_code, 200)
        self.assertEqual(self.client.get(url.replace("synthetic_a", "synthetic_b")).status_code, 404)
        self.assertEqual(self.client.get(url + "/previews/unknown").status_code, 404)
        with self.store.connect() as connection:
            connection.execute("DELETE FROM library_items WHERE id='synthetic_a'")
        self.assert_refused(public, 404)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(url + "/previews/" + artifact_id).status_code, 404)
        # A comparison-looking item ID does not turn another kind into a comparison.
        with self.store.connect() as connection:
            connection.execute("UPDATE analysis_runs SET item_id='comparison-missing' WHERE id=?", (run["id"],))
        self.assert_refused(public, 404)

    def test_comparison_export_exception_does_not_expand_item_scoped_read_routes(self):
        run = self.save_comparison()
        with self.read_only():
            url = f"/api/library/{run['item_id']}/analysis/runs/{run['id']}"
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.get(url + "/previews/" + run["artifacts"][0]["id"]).status_code, 404)
            self.assertEqual(self.client.get(url.replace(run["item_id"], "synthetic_a")).status_code, 404)

    def test_hash_bytes_and_missing_artifact_refuse_whole_comparison(self):
        for damage in ("hash", "bytes", "missing"):
            with self.subTest(damage=damage):
                run = self.save_comparison()
                artifact = self.artifact(run, "result.json")
                path = self.store.root / artifact["path"]
                if damage == "missing":
                    path.unlink()
                else:
                    original = path.read_bytes()
                    path.write_bytes(b" " + original[1:] if damage == "hash" else original + b" ")
                self.assert_refused(run)

    def test_hash_consistent_malformed_json_refuses(self):
        for name, data in (("result.json", b"{"), ("result.json", b"[]"),
                           ("manifest.json", b'{"artifacts":42}')):
            with self.subTest(name=name, data=data):
                run = self.save_comparison()
                self.replace_artifact(run, name, data)
                self.assert_refused(run)

    def test_hash_consistent_nonfinite_json_refuses_with_other_bindings_intact(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                run = self.save_comparison()
                result = self.store.verified_package(run["id"])[1]
                result["nonfinite_test"] = value
                self.replace_artifact(run, "result.json", json.dumps(result, ensure_ascii=False).encode())
                self.assert_refused(run)

    def test_legacy_comparison_exports_without_adding_typed_tables(self):
        run = self.make_legacy_package(self.save_comparison())
        self.fresh_reader()
        content = self.store.verified_package(run["id"])[3]
        self.assertFalse(any(name.startswith("tables/") and name.endswith(".json") for name in content))
        self.assert_exports(run, content)

    def test_legacy_csv_row_count_width_and_syntax_are_still_checked(self):
        for data in (b"value\r\n", b"value\r\none,two\r\n", b'value\r\n"unfinished'):
            with self.subTest(data=data):
                run = self.make_legacy_package(self.save_comparison())
                self.replace_artifact(run, "tables/comparison_interviews.csv", data)
                self.assert_refused(run)

    def test_missing_artifact_catalog_row_refuses_package_and_keeps_unknown_url_404(self):
        run = self.save_comparison()
        missing = self.artifact(run, "tables/comparison_interviews.csv")
        with self.store.connect() as connection:
            connection.execute("DELETE FROM analysis_artifacts WHERE id=?", (missing["id"],))
        run["artifacts"] = [row for row in run["artifacts"] if row["id"] != missing["id"]]
        self.assert_refused(run)
        with self.read_only():
            self.assertEqual(self.client.get("/api/analysis/artifacts/" + missing["id"]).status_code, 404)

    def test_snapshot_manifest_catalog_and_typed_table_mismatch_refuse(self):
        for damage in ("snapshot", "manifest", "catalog", "typed_rows", "csv_rows"):
            with self.subTest(damage=damage):
                run = self.save_comparison()
                snapshot, _result, manifest, content = self.store.verified_package(run["id"])
                if damage == "snapshot":
                    snapshot["title"] = "changed fixed snapshot"
                    self.replace_artifact(run, "input.json", canonical(snapshot))
                elif damage == "manifest":
                    manifest["analysis_id"] = "different-run"
                    self.replace_artifact(run, "manifest.json", canonical(manifest))
                elif damage == "catalog":
                    with self.store.connect() as connection:
                        connection.execute("UPDATE analysis_artifacts SET rows=999 WHERE id=?",
                                           (self.artifact(run, "tables/comparison_interviews.csv")["id"],))
                elif damage == "typed_rows":
                    name = "tables/comparison_interviews.json"
                    table = json.loads(content[name]); table["row_count"] += 1
                    self.replace_artifact(run, name, canonical(table))
                else:
                    self.replace_artifact(run, "tables/comparison_interviews.csv", b"id,value\r\nwrong,0\r\n")
                self.assert_refused(run)

    def test_saved_comparison_kind_item_and_membership_mismatch_refuse(self):
        for damage in ("run_item", "manifest_kind", "manifest_item", "member_missing", "member_extra", "parameter_members"):
            with self.subTest(damage=damage):
                run = self.save_comparison()
                _snapshot, result, manifest, _content = self.store.verified_package(run["id"])
                if damage == "run_item":
                    with self.store.connect() as connection:
                        connection.execute("UPDATE analysis_runs SET item_id='comparison-other' WHERE id=?", (run["id"],))
                elif damage.startswith("manifest_"):
                    manifest["kind" if damage == "manifest_kind" else "conversation_id"] = "other"
                    self.replace_artifact(run, "manifest.json", canonical(manifest))
                elif damage == "member_missing":
                    with self.store.connect() as connection:
                        connection.execute("DELETE FROM analysis_run_members WHERE run_id=? AND item_id='synthetic_a'", (run["id"],))
                elif damage == "member_extra":
                    with self.store.connect() as connection:
                        connection.execute("INSERT INTO analysis_run_members(run_id,item_id) VALUES (?,?)", (run["id"], "other"))
                else:
                    result["parameters"]["item_ids"] = ["synthetic_a", "other"]
                    self.replace_artifact(run, "result.json", canonical(result))
                    self.replace_artifact(run, "parameters.json", canonical(result["parameters"]))
                self.assert_refused(run)

    def test_relabeling_normal_missing_item_run_cannot_bypass_comparison_identity(self):
        run = self.store.save(item_id="comparison-fake", kind="text_analysis", snapshot={"segments": []},
                              result={"parameters": {}}, datasets={}, request_id="fake-comparison-0001",
                              input_fingerprint="saved", source_revision=0, analysis_revision=0, publish=False)
        public = self.store.public(run)
        self.assert_refused(public, 404)
        with self.store.connect() as connection:
            connection.execute("UPDATE analysis_runs SET kind='interview_comparison' WHERE id=?", (run["id"],))
        self.assert_refused(public)

    def test_unsafe_catalog_member_refuses_even_intact_sibling(self):
        run = self.save_comparison()
        with self.store.connect() as connection:
            connection.execute("UPDATE analysis_artifacts SET name='../outside.csv' WHERE id=?",
                               (self.artifact(run, "tables/comparison_interviews.csv")["id"],))
        self.assert_refused(run)


if __name__ == "__main__":
    unittest.main()
