import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gurumoji.analysis_store import write_atomic
from gurumoji.services import durable_files


def locked(winerror=32):
    error = PermissionError(13, "The process cannot access the file")
    error.winerror = winerror
    return error


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_vault_and_output_writes_share_one_durable_move(self):
        # ARCH-04: write_atomic is the durable_files write, including the directory sync.
        target = self.root / "note.md"
        with patch.object(durable_files, "sync_directory_metadata") as sync:
            write_atomic(target, b"first")
            write_atomic(target, b"second")
        self.assertEqual(target.read_bytes(), b"second")
        self.assertTrue(sync.called)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["note.md"])

    def test_create_only_never_replaces_an_existing_file(self):
        target = self.root / "note.md"
        target.write_bytes(b"researcher")
        with self.assertRaises(FileExistsError):
            write_atomic(target, b"generated", create_only=True)
        self.assertEqual(target.read_bytes(), b"researcher")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["note.md"])

    def test_a_briefly_locked_target_is_retried(self):
        # OBS-17: a sync client or scanner holding the file does not fail the save.
        target = self.root / "note.md"
        original = durable_files.durable_move
        failures = [locked(), locked(5)]

        def move(source, destination, **kwargs):
            if failures:
                raise failures.pop(0)
            return original(source, destination, **kwargs)

        with (
            patch.object(durable_files, "durable_move", side_effect=move) as mocked,
            patch.object(durable_files.time, "sleep"),
        ):
            durable_files.durable_move_with_retry(
                self._temporary(b"saved"), target, delays=(0, 0, 0))
        self.assertEqual(target.read_bytes(), b"saved")
        self.assertEqual(mocked.call_count, 3)

    def test_other_errors_and_a_lock_that_stays_are_raised(self):
        target = self.root / "note.md"
        with (
            patch.object(durable_files, "durable_move", side_effect=OSError("disk full")) as mocked,
            patch.object(durable_files.time, "sleep"),
        ):
            with self.assertRaisesRegex(OSError, "disk full"):
                durable_files.durable_move_with_retry(self._temporary(b"x"), target, delays=(0, 0))
        self.assertEqual(mocked.call_count, 1)
        with (
            patch.object(durable_files, "durable_move", side_effect=locked()) as mocked,
            patch.object(durable_files.time, "sleep"),
            self.assertLogs(durable_files.__name__, "WARNING") as logs,
        ):
            with self.assertRaises(PermissionError):
                durable_files.durable_move_with_retry(self._temporary(b"x"), target, delays=(0, 0))
        self.assertEqual(mocked.call_count, 3)
        self.assertIn("note.md", logs.output[0])
        self.assertNotIn(str(self.root), logs.output[0])

    def test_long_paths_are_refused_before_writing_with_a_clear_reason(self):
        # OBS-14: the check runs before any file (or temporary file) is created.
        with self.assertRaisesRegex(OSError, "ファイル名が長すぎます"):
            write_atomic(self.root / ("長" * 90 + ".md"), b"x")
        deep = self.root / ("d" * 120) / ("e" * 120) / "note.md"
        with patch.object(durable_files, "windows_long_paths_enabled", return_value=False):
            with self.assertRaisesRegex(OSError, "Windowsの上限259文字"):
                durable_files.ensure_path_fits(deep, windows=True)
        with patch.object(durable_files, "windows_long_paths_enabled", return_value=True):
            durable_files.ensure_path_fits(deep, windows=True)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_temporary_name_stays_close_to_the_target_length(self):
        target = self.root / ("結果-" + "x" * 70 + ".md")
        temporary = durable_files.temporary_output_path(target)
        self.assertLessEqual(len(temporary.name), 24 + 16 + 8 + len(target.suffix))
        self.assertTrue(temporary.name.endswith(".tmp.md"))

    def _temporary(self, data):
        path = self.root / f".tmp-{len(list(self.root.iterdir()))}"
        path.write_bytes(data)
        return path



class SharedLocationTests(unittest.TestCase):
    def test_every_research_vault_writer_uses_one_root(self):
        # ARCH-03: ResearchVault is defined once, in analysis_store.research_vault_root.
        from gurumoji.analysis_store import research_vault_root
        from gurumoji.obsidian_finishing import ObsidianWorkbench
        from gurumoji.obsidian_layout import ObsidianLayout
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "library.sqlite3"
            expected = research_vault_root(database)
            self.assertEqual(ObsidianLayout(database).vault, expected)
            self.assertEqual(ObsidianWorkbench(database).vault, expected)

    def test_app_url_follows_the_configured_port(self):
        from gurumoji.env_settings import local_app_url
        with patch.dict("os.environ", {"MOJIOKOSI_PORT": "8123"}):
            self.assertEqual(local_app_url(), "http://127.0.0.1:8123")
        for invalid in ("", "0", "70000", "abc"):
            with patch.dict("os.environ", {"MOJIOKOSI_PORT": invalid}):
                self.assertEqual(local_app_url(), "http://127.0.0.1:7860")


class LayeringTests(unittest.TestCase):
    def test_vault_writers_depend_on_the_bottom_layer_not_on_each_other(self):
        # ARCH-02: vault_files is the bottom layer; the Vault writers never import
        # analysis_store at module level, so the store can import them one way.
        import ast
        package = Path(__file__).resolve().parents[1] / "src" / "gurumoji"

        def top_level_imports(name):
            tree = ast.parse((package / f"{name}.py").read_text(encoding="utf-8"))
            return {node.module for node in tree.body
                    if isinstance(node, ast.ImportFrom) and node.level and node.module}

        self.assertEqual(top_level_imports("vault_files"), set())
        for name in ("obsidian_layout", "obsidian_finishing", "vault_registry", "vault_note_policy",
                     "obsidian_migration"):
            imports = top_level_imports(name)
            self.assertIn("vault_files", imports, name)
            self.assertNotIn("analysis_store", imports, name)

if __name__ == "__main__":
    unittest.main()
