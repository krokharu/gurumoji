"""Composition-boundary tests: history/slide reads never initialize runtime."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import app
from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services.analysis_slide_templates import CATALOG_PATH, DESIGN_PATH, load_slide_templates


class HistoryAppBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "library.sqlite3"
        self.client = app.app.test_client()

    def test_missing_database_read_does_not_create_it(self):
        with patch.object(app, "DATABASE_FILE", self.db), patch.object(app, "analysis_orchestration_service") as execute:
            response = self.client.get("/api/library/synthetic/analysis/orchestration/viewer")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(self.db.exists())
        execute.assert_not_called()

    def test_legacy_database_list_is_empty_without_ddl_or_repair(self):
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE library_items(id TEXT PRIMARY KEY, source_name TEXT)")
            db.execute("INSERT INTO library_items VALUES ('synthetic','合成会話')")
        before = self.db.read_bytes()
        with patch.object(app, "DATABASE_FILE", self.db), patch.object(app, "analysis_orchestration_service") as execute:
            response = self.client.get("/api/library/synthetic/analysis/orchestration/viewer")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["runs"], [])
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.db.read_bytes(), before)
        execute.assert_not_called()

    def test_history_connection_cannot_write(self):
        sqlite3.connect(self.db).close()
        with patch.object(app, "DATABASE_FILE", self.db), app.analysis_history_connection() as db:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("CREATE TABLE forbidden(id INTEGER)")


class TemplateDesignBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_missing_catalog_has_no_implicit_template(self):
        self.assertEqual(load_slide_templates(self.root), {})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_only_saved_matching_design_enables_templates(self):
        design = self.root / DESIGN_PATH
        design.parent.mkdir(parents=True)
        design.write_text("Synthetic design record only", encoding="utf-8")
        catalog = self.root / CATALOG_PATH
        catalog.parent.mkdir(parents=True)
        value = {"schema_version": 1, "design_document": {"path": DESIGN_PATH,
                 "sha256": hashlib.sha256(design.read_bytes()).hexdigest()}, "templates": {"test": {"id": "test"}}}
        catalog.write_text(json.dumps(value))
        self.assertEqual(load_slide_templates(self.root), value["templates"])
        design.write_text("Changed record", encoding="utf-8")
        with self.assertRaises(AnalysisContractError):
            load_slide_templates(self.root)
        design.unlink()
        with self.assertRaises(AnalysisContractError):
            load_slide_templates(self.root)

    def test_catalog_cannot_select_arbitrary_source_document(self):
        catalog = self.root / CATALOG_PATH
        catalog.parent.mkdir(parents=True)
        catalog.write_text(json.dumps({"schema_version": 1, "design_document": {
            "path": "../private.md", "sha256": "none"}, "templates": {}}))
        with self.assertRaises(AnalysisContractError):
            load_slide_templates(self.root)


if __name__ == "__main__":
    unittest.main()
