import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import app


SEGMENTS = [
    {"start": 0.0, "end": 0.6, "speaker": "SPEAKER_00", "text": "山田です。"},
    {"start": 0.6, "end": 1.1, "speaker": "SPEAKER_01", "text": "佐藤です。"},
]
SPEAKER_NAMES = {"SPEAKER_00": "山田", "SPEAKER_01": "佐藤"}
SPEAKER_PROFILES = {
    "SPEAKER_00": {"theme_color": "#E86A5A"},
    "SPEAKER_01": {"theme_color": "#2F80ED"},
}


class TranscriptOutputTests(unittest.TestCase):
    def test_json_is_written_even_when_legacy_flag_is_false(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-output-") as temporary:
            output_dir = Path(temporary)
            files = app.write_outputs(
                "自己紹介.mp4",
                output_dir,
                SEGMENTS,
                "ja",
                SPEAKER_NAMES,
                False,
                False,
                speaker_profiles=SPEAKER_PROFILES,
            )

            json_path = output_dir / "自己紹介_話者分離.json"
            self.assertIn(json_path, files)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["speaker_names"]["SPEAKER_00"], "山田")
            self.assertEqual(payload["speaker_theme_colors"]["SPEAKER_00"], "#E86A5A")
            self.assertNotEqual(
                payload["speaker_theme_colors"]["SPEAKER_00"],
                payload["speaker_theme_colors"]["SPEAKER_01"],
            )

    def test_ass_contains_identified_names_and_theme_colors(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-ass-") as temporary:
            target = Path(temporary) / "字幕.ass"
            app.write_ass_subtitles(
                target,
                "自己紹介.mp4",
                SEGMENTS,
                SPEAKER_NAMES,
                SPEAKER_PROFILES,
            )

            body = target.read_text(encoding="utf-8-sig")
            self.assertIn("山田", body)
            self.assertIn("佐藤", body)
            self.assertIn(app.rgb_to_ass_color("#E86A5A"), body)
            self.assertIn(app.rgb_to_ass_color("#2F80ED"), body)

    def test_long_subtitle_is_wrapped_to_video_width_and_paged(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-ass-wrap-") as temporary:
            target = Path(temporary) / "字幕.ass"
            long_text = "横幅を超えないように字幕を自然に改行します。" * 12
            pages = app.subtitle_text_pages(long_text, max_width=280, font_size=16)

            self.assertGreater(len(pages), 1)
            for page in pages:
                lines = page.splitlines()
                self.assertLessEqual(len(lines), 2)
                self.assertTrue(all(app.subtitle_text_width(line, 16) <= 280 for line in lines))

            app.write_ass_subtitles(
                target,
                "縦動画.mp4",
                [{"start": 0.0, "end": 12.0, "speaker": "SPEAKER_00", "text": long_text}],
                {"SPEAKER_00": "山田"},
                SPEAKER_PROFILES,
                video_width=320,
                video_height=180,
            )
            body = target.read_text(encoding="utf-8-sig")
            self.assertIn("PlayResX: 320", body)
            self.assertIn("PlayResY: 180", body)
            self.assertGreater(body.count("Dialogue:"), 1)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_burns_ass_subtitles_into_mp4(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-video-") as temporary:
            root = Path(temporary)
            source = root / "source.mp4"
            generated = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=320x180:r=24",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-t", "1.2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", source.name,
                ],
                cwd=str(root),
                capture_output=True,
                check=False,
            )
            if generated.returncode != 0:
                self.skipTest("test video could not be encoded with libx264")

            files = app.write_subtitled_video_assets(
                source,
                "自己紹介.mp4",
                root,
                SEGMENTS,
                SPEAKER_NAMES,
                SPEAKER_PROFILES,
            )

            self.assertTrue(any(path.suffix == ".ass" for path in files))
            ass_path = next(path for path in files if path.suffix == ".ass")
            ass_body = ass_path.read_text(encoding="utf-8-sig")
            self.assertIn("PlayResX: 320", ass_body)
            self.assertIn("PlayResY: 180", ass_body)
            video = root / "自己紹介_字幕付き.mp4"
            self.assertIn(video, files)
            self.assertGreater(video.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
