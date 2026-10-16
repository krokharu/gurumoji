import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from gurumoji.services import change_log as h, vocabulary_store as v, library_trash as trash
from gurumoji.services.transcription.vocabulary import normalize_custom_vocabulary, whisper_vocabulary_prompt


class VocabularyHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-i3a-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "custom_vocabulary.json"
        self.db_path = Path(self.temp.name) / "library.sqlite3"
        with self.connect() as db:
            v.initialize(db)
        self.store = v.VocabularyStore(self.connect, lambda: self.path, threading.Lock(), normalize_custom_vocabulary)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def file(self, values):
        self.path.write_text(json.dumps({"version": 1, "terms": values}), encoding="utf-8")

    def history(self, entity="vocabulary_terms"):
        with self.connect() as db:
            return h.rows(db, entity, "global")

    def test_initial_file_import_one_unknown_origin_record_and_v1_copy(self):
        self.file(["グルモジ", "WhisperX"])
        self.assertEqual(self.store.reconcile(), ("グルモジ", "WhisperX"))
        history = self.history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["origin"], "rule")
        self.assertEqual(h.reconstruct(history), ["グルモジ", "WhisperX"])
        self.assertEqual(json.loads(history[0]["ops_json"])["past_origin"], "unknown")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"version": 1, "terms": ["グルモジ", "WhisperX"]})
        self.assertEqual(whisper_vocabulary_prompt(self.store.load()), "用語・固有名詞: グルモジ、WhisperX。")

    def test_no_file_initializes_empty_and_restart_is_idempotent(self):
        self.store.reconcile()
        first = self.history()
        self.store.reconcile()
        self.assertEqual(self.history(), first)
        self.assertEqual(self.store.load(), ())

    def test_get_never_imports_or_writes_external_file(self):
        self.store.reconcile()
        self.file(["外部で変更"])
        before = self.history()
        content = self.path.read_bytes()
        self.assertEqual(self.store.load(), ())
        self.assertEqual(self.history(), before)
        self.assertEqual(self.path.read_bytes(), content)

    def test_external_edits_imported_as_rule_on_startup(self):
        self.store.reconcile()
        self.store.save(["前"])
        self.file(["外部", "編集"])
        self.store.reconcile()
        history = self.history()
        self.assertEqual(history[-1]["origin"], "rule")
        self.assertEqual(json.loads(history[-1]["ops_json"])["process"], "vocabulary_file_import")
        self.assertEqual(h.reconstruct(history), list(self.store.load()))

    def test_bad_file_is_preserved_and_does_not_erase_database(self):
        self.store.reconcile()
        self.store.save(["保持"])
        for content in ["broken", '{"version": 2, "terms": []}', '{"version": 1, "terms": [1]}']:
            self.path.write_text(content, encoding="utf-8")
            before = self.history()
            with self.assertRaises((ValueError, json.JSONDecodeError)):
                self.store.reconcile()
            self.assertEqual(self.store.load(), ("保持",))
            self.assertEqual(self.history(), before)
            self.assertEqual(self.path.read_text(encoding="utf-8"), content)

    def test_missing_copy_is_recreated_without_changing_truth(self):
        self.store.reconcile()
        self.store.save(["保持"])
        self.path.unlink()
        before = self.history()
        self.store.reconcile()
        self.assertEqual(self.history(), before)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["terms"], ["保持"])

    def test_dictionary_survives_term_removal_and_reordering(self):
        self.store.reconcile()
        self.store.save(["グルモジ", "WhisperX"])
        with self.connect() as db:
            v.save_variant(db, "ぐるもじ", "グルモジ")
            before = h.rows(db, "notation_variants", "global")
        self.store.save(["WhisperX"])
        with self.connect() as db:
            self.assertEqual(v.variants(db), {"ぐるもじ": "グルモジ"})
            self.assertEqual(h.rows(db, "notation_variants", "global"), before)
        self.assertEqual(h.reconstruct(self.history()), ["WhisperX"])

    def test_explicit_dictionary_edit_delete_and_replay(self):
        self.store.reconcile()
        with self.connect() as db:
            v.save_variant(db, "ＡＩ", "AI")
            v.save_variant(db, "ＡＩ", "人工知能")
            v.save_variant(db, "別", "保持")
            v.save_variant(db, "ＡＩ", None)
            self.assertEqual(h.reconstruct(h.rows(db, "notation_variants", "global")), v.variants(db))
            self.assertEqual(v.variants(db), {"別": "保持"})

    def test_shared_save_window_commits_terms_dictionary_and_histories_together(self):
        self.store.reconcile()
        self.store.save(["AI"], notation_changes={"ＡＩ": "AI"})
        with self.connect() as db:
            self.assertEqual(v.variants(db), {"ＡＩ": "AI"})
        before = self.history()
        with self.assertRaises(ValueError):
            self.store.save(["変更"], notation_changes={"": "不正"})
        self.assertEqual(self.store.load(), ("AI",))
        self.assertEqual(self.history(), before)

    def test_db_failure_rolls_back_history_and_values_even_if_caught(self):
        self.store.reconcile()
        self.store.save(["前"])
        with self.connect() as db:
            db.execute("CREATE TRIGGER fail_terms BEFORE INSERT ON vocabulary_terms BEGIN SELECT RAISE(ABORT, 'injected'); END")
        before = self.history()
        copy = self.path.read_bytes()
        with self.assertRaises(sqlite3.Error):
            self.store.save(["後"])
        self.assertEqual(self.store.load(), ("前",))
        self.assertEqual(self.history(), before)
        self.assertEqual(self.path.read_bytes(), copy)

    def test_history_failure_rolls_back_dictionary(self):
        self.store.reconcile()
        with self.connect() as db:
            v.save_variant(db, "a", "A")
            db.execute("CREATE TRIGGER fail_history BEFORE INSERT ON change_log BEGIN SELECT RAISE(ABORT, 'injected'); END")
            with self.assertRaises(sqlite3.Error):
                v.save_variant(db, "a", "B")
            self.assertEqual(v.variants(db), {"a": "A"})
            self.assertEqual(h.reconstruct(h.rows(db, "notation_variants", "global")), {"a": "A"})

    def test_copy_failure_keeps_committed_db_and_restart_rewrites_stale_copy(self):
        self.store.reconcile()
        self.store.save(["前"])
        with patch.object(v, "atomic_write_text", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.store.save(["後"])
        self.assertEqual(self.store.load(), ("後",))
        self.assertEqual(h.reconstruct(self.history()), ["後"])
        before = self.history()
        self.store.reconcile()
        self.assertEqual(self.history(), before)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["terms"], ["後"])

    def test_common_replay_missing_null_and_tamper_detection(self):
        with self.connect() as db:
            h.capture(db, "synthetic", "x", {}, {"missing": None, "number": 0})
            h.capture(db, "synthetic", "x", {"missing": None, "number": 0}, {"number": 0.0})
            history = h.rows(db, "synthetic", "x")
            self.assertEqual(h.reconstruct(history), {"number": 0.0})
            for field in ("seq", "base_hash", "after_hash"):
                damaged = [dict(row) for row in history]
                damaged[-1][field] = 99 if field == "seq" else "bad"
                with self.assertRaises(ValueError):
                    h.reconstruct(damaged)
            with self.assertRaises(ValueError):
                h.capture(db, "synthetic", "x", {}, {"x": 1})

    def test_conversation_snapshot_delete_restore_never_touches_global_history(self):
        with self.connect() as db:
            for entity, key in [("conversation", "c"), ("analysis_config", "c"),
                                ("conversation", "other"), ("vocabulary_terms", "global"), ("speaker_registry", "c")]:
                h.capture(db, entity, key, {}, {"synthetic": True})
            snapshot = trash.snapshot_rows(db, "c")["change_log"]
            self.assertEqual({row["entity"] for row in snapshot}, {"conversation", "analysis_config"})
            trash.delete_disposable_rows(db, "c")
            self.assertEqual(len(h.rows(db, "conversation", "c")), 0)
            self.assertTrue(h.rows(db, "conversation", "other"))
            self.assertTrue(h.rows(db, "speaker_registry", "c"))
            self.assertTrue(h.rows(db, "vocabulary_terms", "global"))
            trash._insert(db, "change_log", snapshot)
            self.assertEqual(h.reconstruct(h.rows(db, "conversation", "c")), {"synthetic": True})

    def test_real_trash_manifest_restores_only_conversation_history(self):
        root = Path(self.temp.name) / "trash"
        with self.connect() as db:
            db.execute("CREATE TABLE library_items(id TEXT PRIMARY KEY, source_name TEXT)")
            db.execute("INSERT INTO library_items VALUES ('c', '架空.wav')")
            h.capture(db, "conversation", "c", {}, {"synthetic": True})
            h.capture(db, "vocabulary_terms", "global", {}, {"keep": True})
            before = h.rows(db, "vocabulary_terms", "global")
            snapshot = trash.snapshot_rows(db, "c")
            entry = trash.begin(root, item_id="c", source_name="架空.wav", rows=snapshot,
                                tombstones_added=[], tombstones_replaced=[], assets=[])
            trash.delete_disposable_rows(db, "c")
            db.execute("DELETE FROM library_items WHERE id='c'")
        self.assertEqual(trash.finish(entry, lambda *_: None), [])
        self.assertEqual(trash.restore(root, entry.name, connect=self.connect, targets={}, move=lambda *_: None), "c")
        with self.connect() as db:
            self.assertEqual(h.reconstruct(h.rows(db, "conversation", "c")), {"synthetic": True})
            self.assertEqual(h.rows(db, "vocabulary_terms", "global"), before)


if __name__ == "__main__":
    unittest.main()
