import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import test_pipeline_regressions


class TranscriptionFailureCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_pipeline_regressions.TranscriptionJobRegressionTests()

    def test_asr_failure_marks_failed_and_cleans_uncommitted_artifacts(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-asr-failure-") as temporary:
            root = Path(temporary)
            job = self.fixture.job(root)
            with self.fixture.fake_pipeline() as calls, \
                    patch.object(sys.modules["whisper"], "load_model", side_effect=RuntimeError("ASR failed")), \
                    patch.object(app, "cleanup_uncommitted_job_artifacts", return_value=[]) as cleanup:
                app.run_transcription_job(job, self.fixture.options(root))
            self.assertEqual(job.status, "failed")
            self.assertEqual(job.error, "RuntimeError: ASR failed")
            cleanup.assert_called_once()
            calls["write_outputs"].assert_not_called()
            calls["upsert"].assert_not_called()

    def test_cancellation_after_staging_removes_staged_file(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-staging-cancel-") as temporary:
            root = Path(temporary)
            staged = root / "staged.tmp"
            staged.write_text("temporary", encoding="utf-8")
            job = self.fixture.job(root)
            def stage(_id, path, _check):
                job.cancel_event.set()
                return path, staged
            with self.fixture.fake_pipeline() as calls, \
                    patch.object(app, "cleanup_uncommitted_job_artifacts", return_value=[]) as cleanup:
                calls["stage_media"].side_effect = stage
                app.run_transcription_job(job, self.fixture.options(root))
            self.assertEqual(job.status, "cancelled")
            self.assertFalse(staged.exists())
            cleanup.assert_called_once()
            calls["commit_media"].assert_not_called()
            calls["upsert"].assert_not_called()
