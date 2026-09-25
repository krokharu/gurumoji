"""The shared write policy for notes Gurumoji generates in a Vault (OBS-04)."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gurumoji.obsidian_finishing import ObsidianWorkbench, read_text
from gurumoji.obsidian_layout import ObsidianLayout, unpack
from gurumoji.vault_note_policy import (
    RESEARCH_HISTORY, history_copy, recent_changes, write_generated_note,
)

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


class WriteGeneratedNoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Path(self.temp.name) / "vault"
        self.log = Path(self.temp.name) / "note_changes.jsonl"
        self.relative = "10-インタビュー/I001-会議/I001-概要.md"
        self.path = self.vault / self.relative

    def write(self, text, known=(), *, ever=False, navigation=False, minutes=0):
        return write_generated_note(
            self.vault, self.relative, text.encode(), known_hashes=set(known), ever_written=ever,
            recreate_missing=navigation, log_file=self.log, now=NOW + timedelta(minutes=minutes))

    def history(self):
        return sorted((self.vault / "10-インタビュー/I001-会議/履歴/ノート変更").rglob("*.md"))

    def test_new_note_keeps_its_first_version_in_the_interview_history(self):
        result = self.write("---\nnote_id: overview\ntags: [graph/overview]\n---\n\n# 概要\n")
        self.assertEqual(result.action, "created")
        self.assertEqual(self.path.read_text(encoding="utf-8"), "---\nnote_id: overview\ntags: [graph/overview]\n---\n\n# 概要\n")
        [first] = self.history()
        self.assertTrue(first.name.endswith("-最初の版.md"))
        props, body = unpack(first.read_text(encoding="utf-8"))
        self.assertEqual(props["history_of"], self.relative)
        self.assertEqual(props["history_of_note_id"], "overview")
        self.assertNotEqual(props["note_id"], "overview")
        self.assertEqual(props["tags"], ["graph/history"])
        self.assertIn("# 概要", body)

    def test_unedited_app_version_is_replaced_without_a_new_copy(self):
        created = self.write("# v1\n")
        result = self.write("# v2\n", {created.sha256}, ever=True, minutes=1)
        self.assertEqual((result.action, result.history), ("updated", []))
        self.assertEqual(self.path.read_text(encoding="utf-8"), "# v2\n")
        self.assertEqual(len(self.history()), 1)

    def test_researcher_edit_is_kept_then_latest_version_is_written(self):
        created = self.write("# v1\n")
        self.path.write_text("# v1\n\n研究者の書き込み\n", encoding="utf-8")
        result = self.write("# v2\n", {created.sha256}, ever=True, minutes=1)
        self.assertEqual(result.action, "edit_saved")
        self.assertEqual(self.path.read_text(encoding="utf-8"), "# v2\n")
        names = [path.name.split("-", 1)[1] for path in self.history()]
        self.assertEqual(sorted(names), ["最初の版.md", "研究者の編集.md"])
        edited = next(path for path in self.history() if path.name.endswith("研究者の編集.md"))
        self.assertIn("研究者の書き込み", edited.read_text(encoding="utf-8"))

    def test_note_written_before_this_policy_gets_its_first_copy_before_update(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("# 旧版\n", encoding="utf-8")
        import hashlib
        old = hashlib.sha256("# 旧版\n".encode()).hexdigest()
        result = self.write("# 新版\n", {old}, ever=True)
        self.assertEqual(result.action, "updated")
        [first] = self.history()
        self.assertIn("# 旧版", first.read_text(encoding="utf-8"))

    def test_deleted_content_note_is_reported_once_and_navigation_is_recreated(self):
        created = self.write("# v1\n")
        self.path.unlink()
        for minute in (1, 2):
            self.assertEqual(self.write("# v2\n", {created.sha256}, ever=True, minutes=minute).action, "missing")
        self.assertFalse(self.path.exists())
        self.assertEqual(self.write("# v2\n", {created.sha256}, ever=True, navigation=True, minutes=3).action,
                         "recreated")
        self.assertTrue(self.path.exists())
        actions = [json.loads(line)["action"] for line in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(actions, ["created", "missing", "recreated"])
        self.assertEqual([e["action"] for e in recent_changes(self.log)], ["recreated", "missing"])

    def test_unknown_file_at_the_path_is_kept_and_first_version_recorded(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("研究者が置いたノート\n", encoding="utf-8")
        result = self.write("# app\n")
        self.assertEqual(result.action, "edit_saved")
        self.assertEqual(sorted(p.name.split("-", 1)[1] for p in self.history()), ["最初の版.md", "研究者の編集.md"])

    def test_same_content_is_unchanged_and_not_logged(self):
        created = self.write("# v1\n")
        self.assertEqual(self.write("# v1\n", {created.sha256}, ever=True).action, "unchanged")
        self.assertEqual(len(self.log.read_text(encoding="utf-8").splitlines()), 1)

    def test_history_copy_of_broken_frontmatter_keeps_the_text(self):
        copy = history_copy("---\n: [broken\n---\n本文\n".encode(), relative="a.md", label="研究者の編集",
                            saved_at="2026-09-25T12:00:00+00:00", note_id="history-x").decode()
        props, body = unpack(copy)
        self.assertEqual(props["note_id"], "history-x")
        self.assertIn("本文", body)
        self.assertIn(": [broken", body)

    def test_research_history_for_shared_notes_goes_to_operations(self):
        self.assertTrue(RESEARCH_HISTORY.directory("00-ホーム.md").startswith("90-運用/変更履歴/00-ホーム-"))


class LayoutPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        database = Path(self.temp.name) / "library.sqlite3"
        self.layout = ObsidianLayout(database)
        self.workbench = ObsidianWorkbench(database)

    def test_edited_navigation_is_updated_and_listed_in_sync_status(self):
        self.layout.update("a", "会議.wav", {})
        home = self.layout.vault / "00-ホーム.md"
        generated = home.read_bytes()
        home.write_bytes(generated + "\n手書き\n".encode())
        self.layout.publish_navigation()
        self.assertEqual(home.read_bytes(), generated)
        sync = (self.layout.vault / "90-運用/同期状況.md").read_text(encoding="utf-8")
        self.assertIn("研究者の編集を履歴に保存して更新", sync)
        self.assertIn("[[00-ホーム]]", sync)
        self.assertIn("\\|履歴]]", sync)

    def test_deleted_overview_is_not_recreated_but_home_is(self):
        record = self.layout.register("a", "会議.wav")
        self.layout.update("a", "会議.wav", {})
        (self.layout.vault / record["hub"]).unlink()
        (self.layout.vault / "00-ホーム.md").unlink()
        self.layout.update("a", "会議.wav", {}, status="完了")
        self.assertFalse((self.layout.vault / record["hub"]).exists())
        self.assertTrue((self.layout.vault / "00-ホーム.md").exists())
        self.assertIn("削除を検出", (self.layout.vault / "90-運用/同期状況.md").read_text(encoding="utf-8"))

    def test_status_note_edit_is_kept_in_history_and_research_notes_are_never_rewritten(self):
        segments = [{"id": "s1", "speaker": "A", "start": 0, "end": 1, "text": "本文"}]
        state = self.workbench.prepare("a", "会議.wav", segments, revision=0)
        status = self.workbench.note_path(state["status_note"])
        work = self.workbench.note_path(state["work"])
        work_before = work.read_bytes()
        status.write_text(read_text(status) + "\n手書きの状態メモ\n", encoding="utf-8")
        state["message"] = "更新しました"
        self.workbench.publish_status(state)
        self.assertNotIn("手書きの状態メモ", read_text(status))
        self.assertIn("更新しました", read_text(status))
        kept = [p for p in self.layout.vault.rglob("*-研究者の編集.md")]
        self.assertEqual(len(kept), 1)
        self.assertIn("手書きの状態メモ", kept[0].read_text(encoding="utf-8"))
        self.assertEqual(work.read_bytes(), work_before)


if __name__ == "__main__":
    unittest.main()
