import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import test_pipeline_regressions


class TranscriptionCompleteCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_pipeline_regressions.TranscriptionJobRegressionTests()

    def run_success(self, external):
        with tempfile.TemporaryDirectory(prefix="gurumoji-complete-") as temporary:
            root = Path(temporary)
            job = self.fixture.job(root)
            options = self.fixture.options(root, device="cpu" if external else "cuda",
                                           transcription_backend="qwen3_nemotron" if external else "whisperx")
            events = []
            update = app.update_job
            def record(job, **kwargs):
                if "stage" in kwargs:
                    events.append(("stage", kwargs["stage"], kwargs["stage_progress"]))
                if "message" in kwargs:
                    events.append(("status", kwargs["message"]))
                return update(job, **kwargs)
            class Samples:
                def __mul__(self, _value): return self
                def astype(self, _dtype): return self
                def tobytes(self): return b"\0\0"
            numpy = types.ModuleType("numpy")
            numpy.asarray = lambda _samples: Samples()
            numpy.clip = lambda samples, _min, _max: samples
            segment = {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "text": "元の文字起こし"}
            with self.fixture.fake_pipeline(cuda_available=True) as calls, \
                    patch.object(app, "update_job", side_effect=record), \
                    patch.dict(sys.modules, {"numpy": numpy}), \
                    patch("gurumoji.services.transcription.qwen_stack.run_qwen_stack", return_value={"segments": [segment], "language": None}):
                app.run_transcription_job(job, options)
            self.assertEqual(job.status, "completed", job.error)
            stages = [event[1:] for event in events if event[0] == "stage"]
            self.assertEqual(stages[0], ("environment", 5))
            self.assertEqual(stages[-1], ("completed", 100))
            self.assertEqual([key for key, value in stages if value == 100],
                ["environment", "transcription", "alignment", "diarization", "speaker_assignment"] + (["speaker_assignment"] if external else []) + ["finishing", "completed"])
            statuses = [event[1] for event in events if event[0] == "status"]
            self.assertEqual(statuses[0], "処理環境を確認しています…")
            self.assertEqual(statuses[-1], "Transcription completed and output files were saved.")
            output = calls["write_outputs"].call_args
            upsert = calls["upsert"].call_args.kwargs
            self.assertEqual(output.args[0], "input.wav")
            self.assertEqual(output.args[2][0]["text"], "元の文字起こし")
            self.assertEqual(upsert["segments"], output.args[2])
            self.assertEqual(upsert["language"], output.args[3])
            self.assertEqual(upsert["speaker_names"], output.args[4])

    def test_external_complete(self):
        self.run_success(True)

    def test_whisperx_complete(self):
        self.run_success(False)

    def test_cancel_during_asr(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-asr-cancel-") as temporary:
            root = Path(temporary)
            job = self.fixture.job(root)
            class Model:
                def transcribe(self, *_args, **_kwargs):
                    job.cancel_event.set()
                    return {"language": None, "segments": []}
            with self.fixture.fake_pipeline() as calls, \
                    patch.object(sys.modules["whisper"], "load_model", return_value=Model()), \
                    patch.object(app, "cleanup_uncommitted_job_artifacts", return_value=[]):
                app.run_transcription_job(job, self.fixture.options(root))
            self.assertEqual(job.status, "cancelled")
            calls["write_outputs"].assert_not_called()
            calls["upsert"].assert_not_called()
