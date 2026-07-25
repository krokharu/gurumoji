import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from app import (
    find_long_asr_gaps,
    offset_asr_segments_to_gap,
    run_audio_interval_preprocess,
)


class FindLongAsrGapsTests(unittest.TestCase):
    def test_finds_only_long_leading_middle_and_trailing_gaps(self):
        segments = [
            {"start": 4.0, "end": 8.0, "text": "最初"},
            {"start": 9.0, "end": 14.0, "text": "次"},
            {"start": 19.0, "end": 25.0, "text": "最後"},
        ]

        self.assertEqual(
            find_long_asr_gaps(segments, 30.0),
            [(0.0, 4.0), (14.0, 19.0), (25.0, 30.0)],
        )

    def test_overlapping_segments_are_treated_as_continuous_coverage(self):
        segments = [
            {"start": 1.0, "end": 6.0, "text": "a"},
            {"start": 4.0, "end": 9.0, "text": "b"},
            {"start": 12.0, "end": 14.0, "text": "c"},
        ]

        self.assertEqual(
            find_long_asr_gaps(segments, 16.0),
            [(9.0, 12.0)],
        )

    def test_gap_threshold_is_inclusive(self):
        segments = [{"start": 3.0, "end": 7.0, "text": "speech"}]

        self.assertEqual(
            find_long_asr_gaps(segments, 10.0),
            [(0.0, 3.0), (7.0, 10.0)],
        )


class OffsetAsrSegmentsTests(unittest.TestCase):
    def test_offsets_segment_and_word_timestamps(self):
        segments = [{
            "start": 0.5,
            "end": 2.0,
            "text": "補完",
            "words": [{"start": 0.6, "end": 1.1, "word": "補完"}],
        }]

        shifted = offset_asr_segments_to_gap(segments, 10.0, 10.75, 13.0)

        self.assertEqual(len(shifted), 1)
        self.assertEqual(shifted[0]["start"], 10.5)
        self.assertEqual(shifted[0]["end"], 12.0)
        self.assertEqual(shifted[0]["words"][0]["start"], 10.6)
        self.assertEqual(shifted[0]["words"][0]["end"], 11.1)

    def test_drops_speech_found_only_in_context_padding(self):
        segments = [{"start": 0.0, "end": 0.5, "text": "既存発話"}]

        shifted = offset_asr_segments_to_gap(segments, 9.25, 10.0, 13.0)

        self.assertEqual(shifted, [])


class AudioIntervalPreprocessTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_extracts_only_requested_interval(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-gap-test-") as temporary:
            source = Path(temporary) / "source.wav"
            clip = Path(temporary) / "clip.wav"
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=5",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(source),
                ],
                check=True,
            )

            run_audio_interval_preprocess(source, clip, 1.0, 3.5, "light")

            with wave.open(str(clip), "rb") as audio_file:
                duration = audio_file.getnframes() / audio_file.getframerate()
            self.assertAlmostEqual(duration, 2.5, places=1)


if __name__ == "__main__":
    unittest.main()
