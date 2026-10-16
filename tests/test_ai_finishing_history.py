import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from gurumoji import transcript_preparation as p
from gurumoji.ai_finishing import FINISHING_VERSION


class AiFinishingHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-i2-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, path in [("DATABASE_FILE", self.root / "library.sqlite3"),
                           ("DATA_DIRECTORY", self.root / "data"), ("MEDIA_DIRECTORY", self.root / "media")]:
            mock = patch.object(app, name, path)
            mock.start()
            self.addCleanup(mock.stop)
        app.initialize_library()
        fixture = json.loads((Path(__file__).parent / "fixtures/analysis_three_conversations.json").read_text(encoding="utf-8"))
        self.raw = [{key: value for key, value in s.items() if key in {"id", "speaker", "start", "end", "text"}}
                    for s in fixture["conversations"][0]["analysis"]["segments"]]
        self.ai = copy.deepcopy(self.raw)
        self.ai[0]["text"] = "朝の窓口を利用しやすい。"

    def step(self, segments=None, run="synthetic-run", names=None):
        return {"segments": segments or self.ai, "speaker_names": names or {}, "origin": "ai",
                "process": "ai_finishing", "process_version": FINISHING_VERSION,
                "metadata": {"run_id": run, "provider": "mock", "model": "synthetic-model",
                             "stages": {"cleanup": "completed"}}}

    def save(self, segments, history=None, **kw):
        return app.upsert_library_item(item_id="synthetic", source_name="架空.wav", output_dir=self.root,
            media_path=None, language="ja", segments=segments, speaker_names={}, outline=None,
            emotion_analysis=None, files=[], write_srt=False, write_json=True,
            original_segments=self.raw, finishing_history=history, **kw)

    def test_import_raw_metadata_ai_and_rule_share_one_version(self):
        final = copy.deepcopy(self.ai)
        final[1]["text"] = "句読点を整理。"
        row = self.save(final, [self.step()])
        with app.database_connection() as db:
            changes = p._changes(db, "synthetic")
            self.assertEqual([c["process"] for c in changes], ["import_metadata", "ai_finishing", "finishing_output_normalization"])
            self.assertEqual([c["version"] for c in changes], [1, 1, 1])
            self.assertEqual(p.read_version(db, "synthetic", 1)["source"], p.source(row))
            self.assertEqual(json.loads(row["original_segments_json"]), self.raw)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM transcript_versions").fetchone()[0], 0)
            self.assertEqual(json.loads(changes[1]["metadata_json"])["model"], "synthetic-model")

    def test_repeat_ai_then_researcher_edit_raw_and_old_deltas_unchanged(self):
        row = self.save(self.ai, [self.step()])
        with app.database_connection() as db:
            old = p._changes(db, "synthetic")
        second = copy.deepcopy(self.ai)
        second[0]["text"] = "再仕上げ。"
        self.save(second, [self.step(second, run="run-2")], increment_revision=True)
        manual = copy.deepcopy(second)
        manual[0]["text"] = "研究者の確定本文。"
        row = self.save(manual, increment_revision=True)
        with app.database_connection() as db:
            changes = p._changes(db, "synthetic")
            self.assertEqual(changes[:len(old)], old)
            self.assertEqual(changes[-1]["origin"], "researcher")
            self.assertEqual(p.current_version(db, row), 3)
            self.assertEqual(p.read_version(db, "synthetic", 3)["source"], p.source(row))
            rows = p.ai_change_rows(db, "synthetic", run_id="run-2")
            self.assertEqual(rows[0]["after_text"], "再仕上げ。")
            self.assertNotIn("研究者", rows[0]["after_text"])
            self.assertEqual(json.loads(row["original_segments_json"]), self.raw)

    def test_ai_rows_exclude_rule_normalization_and_require_matching_run(self):
        final = copy.deepcopy(self.ai)
        final[0]["text"] += "規則整形。"
        self.save(final, [self.step()])
        with app.database_connection() as db:
            rows = p.ai_change_rows(db, "synthetic", run_id="synthetic-run")
            self.assertEqual(rows[0]["after_text"], self.ai[0]["text"])
            self.assertEqual(p.ai_change_rows(db, "synthetic", run_id="missing"), [])
            self.assertEqual(rows[0]["process_version"], FINISHING_VERSION)

    def test_saved_analysis_uses_recorded_delta_instead_of_supplied_comparison(self):
        row = self.save(self.ai, [self.step()])
        bogus = copy.deepcopy(self.raw)
        bogus[0]["text"] = "比較引数にある架空の別本文。"
        with patch.object(app, "analysis_archive_store") as store:
            app.archive_ai_finishing(row, bogus, {"cleanup": "completed"}, "mock", "synthetic-model", {},
                                    request_id="synthetic-run")
            saved = store.return_value.save.call_args.kwargs
        changes = saved["datasets"]["ai_changes"][1]
        self.assertEqual(changes[0]["before_text"], self.raw[0]["text"])
        self.assertEqual(saved["result"]["finishing"]["change_source"], "transcript_changes")

    def test_unrecorded_current_value_cannot_be_archived_as_ai_result(self):
        self.save(self.ai, [self.step()])
        with app.database_connection() as db:
            db.execute("UPDATE library_items SET segments_json=? WHERE id='synthetic'", (json.dumps(self.raw),))
        with self.assertRaises(ValueError), patch.object(app, "analysis_archive_store") as store:
            app.archive_ai_finishing(app.library_row("synthetic"), self.raw, {}, "mock", "synthetic-model", {})
        store.return_value.save.assert_not_called()

    def test_workbench_input_ai_and_result_edits_have_correct_origins(self):
        self.save(self.raw)
        before = copy.deepcopy(self.raw)
        before[0]["text"] = "作業ノートの手動修正。"
        candidate = copy.deepcopy(before)
        candidate[0]["text"] = "AI修正。"
        final = copy.deepcopy(candidate)
        final[0]["text"] = "結果ノートの手動修正。"
        row = self.save(final, [
            {"segments": before, "origin": "researcher", "process": "workbench_input"},
            self.step(candidate, run="workbench-run"),
            {"segments": final, "origin": "researcher", "process": "workbench_result_edit"}], increment_revision=True)
        with app.database_connection() as db:
            changes = p._changes(db, "synthetic")
            self.assertEqual([c["origin"] for c in changes[-3:]], ["researcher", "ai", "researcher"])
            self.assertEqual([c["version"] for c in changes[-3:]], [2, 2, 2])
            self.assertEqual(p.ai_change_rows(db, "synthetic", run_id="workbench-run")[0]["before_text"], before[0]["text"])
            self.assertEqual(p.read_version(db, "synthetic", 2)["source"], p.source(row))

    def test_failure_rolls_back_current_value_and_entire_save(self):
        row = self.save(self.raw)
        with app.database_connection() as db:
            old = p._changes(db, "synthetic")
            db.execute("CREATE TRIGGER fail_ai BEFORE INSERT ON transcript_changes WHEN NEW.origin='ai' BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with self.assertRaises(sqlite3.Error):
            self.save(self.ai, [self.step()], increment_revision=True)
        self.assertEqual(dict(app.library_row("synthetic")), dict(row))
        with app.database_connection() as db:
            self.assertEqual(p._changes(db, "synthetic"), old)

    def test_schema_reinitialization_keeps_existing_history_and_adds_provenance(self):
        self.save(self.ai, [self.step()])
        with app.database_connection() as db:
            old = p._changes(db, "synthetic")
        app.initialize_library()
        with app.database_connection() as db:
            self.assertEqual(p._changes(db, "synthetic"), old)

    def test_substitute_raw_status_is_not_relabelled_after_ai(self):
        self.save(self.raw)
        with app.database_connection() as db:
            db.execute("DELETE FROM transcript_changes")
            db.execute("DELETE FROM transcript_change_bases")
            db.execute("UPDATE library_items SET original_segments_status='migrated_current_snapshot'")
        row = self.save(self.ai, [self.step()], increment_revision=True)
        with app.database_connection() as db:
            self.assertEqual(p._base(db, "synthetic")["raw_status"], "migrated_current_snapshot")
            self.assertEqual(p.read_version(db, "synthetic", 2)["source"], p.source(row))

    def test_ai_export_detects_corrupt_chain_without_writes(self):
        self.save(self.ai, [self.step()])
        with app.database_connection() as db:
            db.execute("UPDATE transcript_changes SET after_hash='bad' WHERE origin='ai'")
            before = db.total_changes
            with self.assertRaises(ValueError):
                p.ai_change_rows(db, "synthetic")
            self.assertEqual(db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
