"""Tests to ensure that transcription jobs do not automatically generate unrequested analysis runs or files."""

import tempfile
import unittest
from pathlib import Path

import app


class TranscriptionAnalysisSuppressionTests(unittest.TestCase):
    def test_write_outputs_does_not_create_word_cloud_by_default(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-test-") as temp_dir:
            output_dir = Path(temp_dir)
            files = app.write_outputs(
                source_name="test_video.mp4",
                output_dir=output_dir,
                segments=[{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00", "text": "こんにちは"}],
                language="ja",
                speaker_names={"SPEAKER_00": "話者1"},
                write_srt=False,
                write_json=True,
                write_word_cloud_file=False,
            )
            file_names = [f.name for f in files]
            self.assertFalse(any("ワードクラウド" in name for name in file_names))
            self.assertFalse(any(output_dir.glob("*ワードクラウド*")))

    def test_write_outputs_creates_word_cloud_only_when_requested(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-test-") as temp_dir:
            output_dir = Path(temp_dir)
            files = app.write_outputs(
                source_name="test_video.mp4",
                output_dir=output_dir,
                segments=[{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00", "text": "こんにちは"}],
                language="ja",
                speaker_names={"SPEAKER_00": "話者1"},
                write_srt=False,
                write_json=True,
                write_word_cloud_file=True,
            )
            file_names = [f.name for f in files]
            self.assertTrue(any("ワードクラウド" in name for name in file_names))

    def test_job_options_default_analysis_flags(self):
        # Verify defaults do not auto-generate analysis
        options = app.JobOptions(
            input_path=Path("dummy.mp4"),
            work_dir=Path("dummy_work"),
            source_name="dummy.mp4",
            output_dir=Path("dummy_out"),
            model_name="base",
            language="ja",
            hf_token="",
            audio_preprocess="none",
            min_speakers=None,
            max_speakers=None,
            device="cpu",
            diarization_device="cpu",
            triple_pass=False,
            boost_quiet_speech=False,
            vad_onset=0.5,
            vad_offset=0.363,
            no_speech_threshold=0.6,
            write_srt=False,
            write_json=True,
            burn_subtitled_video=False,
            ai_provider="none",
            clean_transcript=False,
            detect_speaker_names=False,
            create_outline=False,
            emotion_analysis=False,
            emotion_model="",
        )
        self.assertFalse(options.write_word_cloud)
        self.assertFalse(options.generate_meeting_minutes)


if __name__ == "__main__":
    unittest.main()
