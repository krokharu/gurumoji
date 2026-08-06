import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app


def command_wav_outputs(command: list[str]) -> list[Path]:
    return [
        Path(argument)
        for argument in command
        if isinstance(argument, str) and Path(argument).name.startswith("seg_")
    ]


class EmotionSegmentBatchTests(unittest.TestCase):
    def test_many_segments_use_a_small_number_of_ffmpeg_processes(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-emotion-batch-") as temporary:
            root = Path(temporary)
            audio_path = root / "audio.wav"
            audio_path.write_bytes(b"source")
            segments = [
                {"start": index * 0.5, "end": index * 0.5 + 0.4, "text": "発話"}
                for index in range(100)
            ]
            commands: list[list[str]] = []
            cancellation_checks = 0

            def cancellation_callback():
                nonlocal cancellation_checks
                cancellation_checks += 1

            class FakeProcess:
                returncode = 0

                def __init__(self, command, **_kwargs):
                    commands.append(command)
                    for output_path in command_wav_outputs(command):
                        output_path.write_bytes(b"RIFFdata")

                def communicate(self, timeout=None):
                    return "", ""

            with patch.dict(
                app.os.environ,
                {"MOJIOKOSI_FFMPEG_CLIP_BATCH_SIZE": "24"},
            ), patch.object(app.subprocess, "Popen", side_effect=FakeProcess) as popen:
                _wav_root, extracted = app.extract_emotion_segment_wavs(
                    audio_path,
                    segments,
                    root,
                    cancellation_callback,
                )

            self.assertEqual(len(extracted), 100)
            self.assertEqual(len(commands), 5)
            self.assertEqual(popen.call_count, 5)
            self.assertLess(len(commands), len(segments) // 10)
            self.assertGreater(cancellation_checks, len(segments))
            self.assertTrue(all("-filter_complex" in command for command in commands))
            self.assertTrue(all(command.index("-ss") < command.index("-i") for command in commands))
            self.assertTrue(all("-t" in command for command in commands))
            later_seek = float(commands[-1][commands[-1].index("-ss") + 1])
            self.assertGreater(later_seek, 0.0)
            first_filter = commands[0][commands[0].index("-filter_complex") + 1]
            self.assertIn("asplit=24", first_filter)

    def test_failed_later_batch_removes_all_partial_wavs(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-emotion-cleanup-") as temporary:
            root = Path(temporary)
            audio_path = root / "audio.wav"
            audio_path.write_bytes(b"source")
            segments = [
                {"start": index * 0.5, "end": index * 0.5 + 0.4, "text": "発話"}
                for index in range(30)
            ]
            call_count = 0

            def fake_run(command, **_kwargs):
                nonlocal call_count
                call_count += 1
                outputs = command_wav_outputs(command)
                if call_count == 1:
                    for output_path in outputs:
                        output_path.write_bytes(b"RIFFdata")
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                outputs[0].write_bytes(b"partial")
                return SimpleNamespace(returncode=1, stdout="", stderr="ffmpeg failed")

            with patch.dict(
                app.os.environ,
                {"MOJIOKOSI_FFMPEG_CLIP_BATCH_SIZE": "24"},
            ), patch.object(app, "run_cancellable_subprocess", side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, "音声切り出しに失敗"):
                    app.extract_emotion_segment_wavs(
                        audio_path,
                        segments,
                        root,
                        lambda: None,
                    )

            self.assertEqual(call_count, 2)
            self.assertEqual(list((root / "emotion_segments").glob("*.wav")), [])


if __name__ == "__main__":
    unittest.main()
