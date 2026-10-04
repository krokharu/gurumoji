"""Synthetic design-gate storage checks. These tests do not generate slides."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gurumoji.analysis_store import StoreConflict
from gurumoji.vault_registry import VaultRegistry


class SlideDesignVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.registry = VaultRegistry(self.base / "data" / "library.sqlite3", self.base / "software")
        self.artifact = {
            "schema_version": 1, "template_id": "test", "template_version": "test-1",
            "design_hash": "sha256:test", "snapshot_signature": "sha256:source-1",
            "item_id": "synthetic-item", "run_id": "synthetic-run",
            "provenance": {"annotation_version": 0}, "design": {"name": "storage fixture"},
            "prompt": "TEST ONLY: no slide content", "source_references": [],
        }

    def save(self, artifact=None):
        return self.registry.publish_slide_design("synthetic-item", "synthetic-run", artifact or self.artifact)

    def test_read_before_save_is_closed_and_has_no_side_effects(self):
        with self.assertRaises(StoreConflict):
            self.registry.read_slide_design("synthetic-item", "synthetic-run")
        self.assertFalse(self.registry.catalog_file.exists())
        self.assertFalse(self.registry.root("visualization").exists())

    def test_save_read_and_idempotency_only_touch_visualization(self):
        receipt = self.save()
        self.assertEqual(receipt["status"], "written")
        self.assertEqual(self.registry.read_slide_design("synthetic-item", "synthetic-run"), self.artifact)
        root = self.registry.root("visualization")
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()}
        self.assertEqual(self.save()["status"], "unchanged")
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()})
        for kind in ("software", "input", "orchestrator"):
            self.assertFalse(self.registry.root(kind).exists())
        with self.assertRaises(StoreConflict):
            self.registry.read_slide_design("other-item", "synthetic-run")

    def test_deleted_note_is_not_recreated_even_for_changed_design(self):
        receipt = self.save()
        path = self.registry.root("visualization") / receipt["path"]
        path.unlink()
        changed = {**self.artifact, "snapshot_signature": "sha256:source-2"}
        with self.assertRaises(StoreConflict):
            self.registry.read_slide_design("synthetic-item", "synthetic-run")
        with self.assertRaises(StoreConflict):
            self.save(changed)
        self.assertFalse(path.exists())

    def test_researcher_edit_blocks_read_and_explicit_save_preserves_edit(self):
        receipt = self.save()
        path = self.registry.root("visualization") / receipt["path"]
        path.write_text(path.read_text() + "\nResearcher synthetic edit\n")
        with self.assertRaises(StoreConflict):
            self.registry.read_slide_design("synthetic-item", "synthetic-run")
        self.assertEqual(self.save()["status"], "overwritten")
        history = list(self.registry.root("visualization").glob("99-Archive/history/**/*.md"))
        self.assertTrue(any("Researcher synthetic edit" in p.read_text() for p in history))
        self.assertEqual(self.registry.read_slide_design("synthetic-item", "synthetic-run"), self.artifact)

    def test_artifact_and_note_hash_tampering_fail_closed(self):
        self.save()
        data = self.registry.load()
        record = next(iter(data["slide_designs"].values()))
        record["artifact"]["prompt"] = "changed"
        self.registry.save(data)
        with self.assertRaises(StoreConflict):
            self.registry.read_slide_design("synthetic-item", "synthetic-run")

    def test_scope_size_and_unexpected_fields_rejected_before_write(self):
        for value in ({**self.artifact, "item_id": "other"},
                      {**self.artifact, "raw_transcript": "never save this"},
                      {**self.artifact, "prompt": "x" * 100000}):
            with self.assertRaises(StoreConflict):
                self.save(value)
        self.assertFalse(self.registry.catalog_file.exists())

    def test_write_failure_does_not_return_success(self):
        with patch.object(self.registry, "_write", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                self.save()
        with self.assertRaises(StoreConflict):
            self.registry.read_slide_design("synthetic-item", "synthetic-run")

    def test_tampered_note_path_never_escapes_the_vault(self):
        receipt = self.save()
        data = self.registry.load()
        data["notes"][receipt["note_id"]]["path"] = "../../outside.md"
        self.registry.save(data)
        with self.assertRaises(StoreConflict):
            self.registry.read_slide_design("synthetic-item", "synthetic-run")


if __name__ == "__main__":
    unittest.main()
