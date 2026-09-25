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

    def _temporary(self, data):
        path = self.root / f".tmp-{len(list(self.root.iterdir()))}"
        path.write_bytes(data)
        return path


if __name__ == "__main__":
    unittest.main()
