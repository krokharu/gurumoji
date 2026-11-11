import unittest
from unittest.mock import patch

import app
import test_transcription_complete_characterization as complete


class TranscriptionStageSequenceTests(unittest.TestCase):
    def test_complete_stage_sequences(self):
        for external in (True, False):
            with self.subTest(external=external):
                stages = []
                update = app.update_job
                def record(job, **kwargs):
                    if "stage" in kwargs:
                        stages.append(kwargs["stage"])
                    return update(job, **kwargs)
                fixture = complete.TranscriptionCompleteCharacterizationTests()
                fixture.setUp()
                with patch.object(app, "update_job", side_effect=record):
                    fixture.run_success(external)
                expected = ["environment", "environment"]
                expected += ["transcription"] * (2 if external else 4)
                expected += ["alignment"] + ["diarization"] * (1 if external else 2)
                expected += ["speaker_assignment"] * 2 + ["finishing"] * 2
                expected += ["output"] * 3 + ["completed"]
                self.assertEqual(stages, expected)
