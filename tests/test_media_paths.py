import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import app


class MediaPathSafetyTests(unittest.TestCase):
    def test_embedded_video_creation_date_becomes_session_date(self):
        completed = CompletedProcess(
            ["ffprobe"],
            0,
            '{"format":{"tags":{"creation_time":"2026-07-25T16:30:00Z"}}}',
            "",
        )
        with patch.object(app.shutil, "which", return_value="ffprobe"), patch.object(
            app, "run_cancellable_subprocess", return_value=completed
        ):
            profile = app.session_profile_from_media(Path("meeting.mp4"))

        self.assertEqual(profile["session_date"], "2026-07-25")
        self.assertEqual(profile["session_date_source"], "media_metadata")

    def test_missing_embedded_date_stays_empty_for_manual_entry(self):
        completed = CompletedProcess(["ffprobe"], 0, '{"format":{"tags":{}}}', "")
        with patch.object(app.shutil, "which", return_value="ffprobe"), patch.object(
            app, "run_cancellable_subprocess", return_value=completed
        ):
            profile = app.session_profile_from_media(Path("meeting.mp4"))

        self.assertEqual(profile, {})

    def test_session_profile_drops_legacy_confidentiality_memo(self):
        profile = app.normalize_session_profile({
            "session_date": "2026-07-25",
            "confidentiality_notes": "削除対象",
        })

        self.assertEqual(profile["session_date_source"], "manual")
        self.assertNotIn("confidentiality_notes", profile)

    def test_non_ascii_media_name_keeps_original_suffix(self):
        safe_name = app.safe_media_filename("会議.mp4", fallback_stem="input")

        self.assertEqual(safe_name, "input.mp4")
        self.assertTrue(app.is_video_path(Path(safe_name)))

    def test_archived_non_ascii_video_remains_a_video(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "会議.mp4"
            source.write_bytes(b"video")
            media_root = root / "media"

            with patch.object(app, "MEDIA_DIRECTORY", media_root):
                archived = app.archive_media("item", source)

            self.assertEqual(archived.suffix, ".mp4")
            self.assertEqual(app.media_kind(archived), "video")
            self.assertEqual(archived.read_bytes(), b"video")

    def test_manual_records_with_same_name_use_distinct_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(app, "DEFAULT_OUTPUT_DIRECTORY", root):
                first = app.manual_output_directory("同名データ", "a" * 32)
                second = app.manual_output_directory("同名データ", "b" * 32)

            self.assertNotEqual(first, second)
            self.assertEqual(first.parent, root)
            self.assertEqual(second.parent, root)


if __name__ == "__main__":
    unittest.main()
