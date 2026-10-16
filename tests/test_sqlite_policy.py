import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from gurumoji.services import sqlite_policy as policy
from gurumoji.services.data_backup import create_backup, restore_backup


class SQLitePolicyTests(unittest.TestCase):
    def test_windows_fixed_disk_and_supported_filesystem_only(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(policy, "os", SimpleNamespace(name="nt")):
            # Construct Path before overriding os.name on non-Windows test hosts.
            for volume, expected in [((3, "NTFS"), True), ((3, "ReFS"), True),
                                     ((3, "FAT32"), False), ((2, "NTFS"), False),
                                     ((4, "NTFS"), False), ((0, ""), False)]:
                with self.subTest(volume=volume), patch.object(policy, "_windows_volume", return_value=volume):
                    self.assertEqual(policy.local_fixed_directory(Path(directory)), expected)
            with patch.object(policy, "_windows_volume", side_effect=OSError("unknown")):
                self.assertFalse(policy.local_fixed_directory(Path(directory)))

    def test_cloud_sync_unc_and_unknown_paths_fail_closed(self):
        for directory in ["/content/drive/MyDrive/data", "C:/OneDrive/data", "C:/Google Drive/data",
                          "C:/マイドライブ/data", "C:/Dropbox/data", "//server/share/data", "missing-path"]:
            with self.subTest(directory=directory):
                self.assertFalse(policy.local_fixed_directory(directory))
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(policy.local_fixed_directory(Path(directory), colab=True))

    def test_resolved_sync_directory_and_linux_mount_types(self):
        with tempfile.TemporaryDirectory() as temporary:
            synced = Path(temporary) / "OneDrive"
            synced.mkdir()
            with patch.object(policy.Path, "resolve", return_value=synced):
                self.assertFalse(policy.local_fixed_directory(Path(temporary)))
            with patch.object(policy, "os", SimpleNamespace(name="posix")), patch.object(policy.sys, "platform", "linux"):
                for filesystem, expected in [("ext4", True), ("xfs", True), ("nfs", False),
                                              ("fuse", False), ("overlay", False), ("", False)]:
                    with patch.object(policy, "_linux_filesystem", return_value=filesystem):
                        self.assertEqual(policy.local_fixed_directory(Path(temporary)), expected)

    def test_wal_reverts_after_relocation_and_backup_includes_committed_wal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "data"
            data.mkdir()
            with closing(sqlite3.connect(data / "library.sqlite3")) as connection:
                with patch.object(policy, "local_fixed_directory", return_value=True):
                    self.assertEqual(policy.configure_journal(connection, data), "WAL")
                connection.execute("PRAGMA wal_autocheckpoint=0")
                connection.execute("CREATE TABLE synthetic(value TEXT)")
                connection.execute("INSERT INTO synthetic VALUES ('committed WAL')")
                connection.commit()
                self.assertGreater((data / "library.sqlite3-wal").stat().st_size, 0)
                (data / "analysis-derived.sqlite3").write_bytes(b"rebuildable")
                backup = create_backup(data, root / "backup")
                self.assertEqual([f["path"] for f in backup["files"]], ["library.sqlite3"])
                restore_backup(backup["path"], root / "restored")
                with closing(sqlite3.connect(root / "restored/library.sqlite3")) as restored:
                    self.assertEqual(restored.execute("SELECT value FROM synthetic").fetchone()[0], "committed WAL")
                with patch.object(policy, "local_fixed_directory", return_value=False):
                    self.assertEqual(policy.configure_journal(connection, data), "DELETE")
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
