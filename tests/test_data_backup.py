"""Consistent backup and restore of the data directory (DATA-03)."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import app
from support import use_temporary_library
from gurumoji.services.data_backup import BackupError, create_backup, restore_backup, verify_backup
from gurumoji.services.instance_lock import InstanceLock

import importlib.util

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_data.py"
_spec = importlib.util.spec_from_file_location("backup_data_script", _SCRIPT)
backup_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backup_script)


def make_data(root: Path) -> Path:
    data = root / "data"
    data.mkdir()
    with closing(sqlite3.connect(data / "library.sqlite3")) as connection:
        connection.execute("CREATE TABLE library_items (id TEXT PRIMARY KEY, text TEXT)")
        connection.execute("INSERT INTO library_items VALUES ('a', '発話')")
        connection.commit()
    files = {
        "analysis_store/runs/r1/result.json": "{}",
        "obsidian/ResearchVault/10-インタビュー/I001/I001-概要.md": "# 概要",
        "obsidian_layout/interviews.json": "{}",
        "obsidian_layout/backup-old/library.sqlite3": "old",
        "obsidian_workbench/k/state.json": "{}",
        "custom_vocabulary.json": "[]",
        "media/a/meeting.wav": "audio",
        "kushinada_training/audio/a.wav": "clip",
        "kushinada_training/corrections.jsonl": "{}",
        "thumbnails/word_cloud_a.svg": "<svg/>",
        "trash/20260101T000000Z-x/trash.json": "{}",
        "analysis_store/.result.json.abc.tmp": "partial",
        ".gurumoji.instance.lock": "",
    }
    for relative, text in files.items():
        path = data / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return data


class DataBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = make_data(self.root)

    def listed(self, backup: Path) -> set[str]:
        return {entry["path"] for entry in json.loads((backup / "manifest.json").read_text(encoding="utf-8"))["files"]}

    def test_backup_keeps_only_what_cannot_be_recreated(self):
        result = create_backup(self.data, self.root / "backups")
        self.assertEqual(self.listed(result["path"]), {
            "library.sqlite3", "analysis_store/runs/r1/result.json",
            "obsidian/ResearchVault/10-インタビュー/I001/I001-概要.md", "obsidian_layout/interviews.json",
            "obsidian_workbench/k/state.json", "custom_vocabulary.json",
        })
        self.assertFalse(result["include_media"])
        self.assertEqual(verify_backup(result["path"]), [])
        self.assertFalse(list((self.root / "backups").glob("*.partial")))

    def test_media_and_training_clips_are_optional(self):
        result = create_backup(self.data, self.root / "backups", include_media=True)
        self.assertTrue({"media/a/meeting.wav", "kushinada_training/audio/a.wav"} <= self.listed(result["path"]))

    def test_verify_reports_changed_missing_and_extra_files(self):
        backup = create_backup(self.data, self.root / "backups")["path"]
        (backup / "data/custom_vocabulary.json").write_text("[\"changed\"]", encoding="utf-8")
        (backup / "data/obsidian_layout/interviews.json").unlink()
        (backup / "data/extra.txt").write_text("x", encoding="utf-8")
        problems = "\n".join(verify_backup(backup))
        self.assertIn("内容が一致しません: custom_vocabulary.json", problems)
        self.assertIn("ファイルがありません: obsidian_layout/interviews.json", problems)
        self.assertIn("manifest にないファイル: extra.txt", problems)
        with self.assertRaises(BackupError):
            restore_backup(backup, self.root / "restored")

    def test_restore_writes_only_into_an_empty_folder(self):
        backup = create_backup(self.data, self.root / "backups")["path"]
        with self.assertRaisesRegex(BackupError, "空ではありません"):
            restore_backup(backup, self.data)
        target = self.root / "restored"
        target.mkdir()
        restore_backup(backup, target)
        with closing(sqlite3.connect(target / "library.sqlite3")) as connection:
            self.assertEqual(connection.execute("SELECT text FROM library_items").fetchone()[0], "発話")
        self.assertEqual((target / "obsidian/ResearchVault/10-インタビュー/I001/I001-概要.md").read_text(encoding="utf-8"), "# 概要")
        self.assertFalse((target / "media").exists())

    def test_command_refuses_while_the_app_holds_the_data_directory(self):
        lock = InstanceLock(lambda: [self.data / ".gurumoji.instance.lock"])
        self.assertTrue(lock.acquire())
        self.addCleanup(lock.release)
        with patch("builtins.print"):
            code = backup_script.main(["create", "--data-dir", str(self.data), "--backup-dir", str(self.root / "b")])
        self.assertEqual(code, 2)
        self.assertFalse((self.root / "b").exists())

    def test_command_creates_verifies_and_restores(self):
        with patch("builtins.print"):
            self.assertEqual(backup_script.main(["create", "--data-dir", str(self.data),
                                                 "--backup-dir", str(self.root / "b")]), 0)
            backup = next((self.root / "b").iterdir())
            self.assertEqual(backup_script.main(["verify", str(backup)]), 0)
            self.assertEqual(backup_script.main(["restore", str(backup), "--data-dir", str(self.root / "new")]), 0)
        self.assertTrue((self.root / "new/library.sqlite3").is_file())


class BackupRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        use_temporary_library(self, self.root)
        patcher = patch.object(app, "BACKUP_DIRECTORY", self.root / "backups")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = app.app.test_client()

    def test_local_browser_creates_a_backup(self):
        response = self.client.post("/api/system/backup", json={"include_media": False})
        self.assertEqual(response.status_code, 200, response.get_json())
        backup = Path(response.get_json()["path"])
        self.assertEqual(backup.parent, self.root / "backups")
        self.assertEqual(verify_backup(backup), [])

    def test_remote_viewer_cannot_start_a_backup(self):
        token = "remote-token-for-tests-1234567890"
        with (
            patch.object(app, "REMOTE_ACCESS_ENABLED", True),
            patch.object(app, "REMOTE_ACCESS_TOKEN", token),
            patch.object(app, "REMOTE_LOCAL_PATHS_ENABLED", False),
        ):
            response = self.client.post(
                "/api/system/backup", json={},
                headers={"Authorization": f"Bearer {token}", "Host": "localhost", "X-Gurumoji-Request": "1"},
                environ_base={"REMOTE_ADDR": "192.0.2.10"},
            )
        self.assertEqual(response.status_code, 403)
        self.assertIn("保存PCから", response.get_json()["error"])
        self.assertFalse((self.root / "backups").exists())


if __name__ == "__main__":
    unittest.main()
