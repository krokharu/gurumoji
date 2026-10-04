"""Run pure synthetic UI probes and validate their real preset payloads.

No browser process, socket, model, external AI, runtime DB or user data is used.
"""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from gurumoji.analysis_core import validate_definition
from gurumoji.analysis_pipeline import measure_segments

ROOT = Path(__file__).resolve().parents[1]


class AnalysisUiSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if not cls.node:
            raise unittest.SkipTest("Node is required for synthetic UI handler probes")

    def probe(self, filename):
        result = subprocess.run(
            [self.node, str(ROOT / "tests" / filename)], cwd=ROOT,
            check=True, capture_output=True, text=True, timeout=30,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload.get("passed") or payload.get("results"))
        return payload

    def test_fixed_run_viewer(self):
        self.assertGreaterEqual(len(self.probe("test_analysis_fixed_run_ui.cjs")["passed"]), 20)

    def test_owned_async_contexts(self):
        self.assertGreaterEqual(len(self.probe("test_analysis_ownership_ui.cjs")["passed"]), 36)

    def test_fixed_measurement_flow_and_backend_semantics(self):
        payload = self.probe("test_analysis_measurement_ui.cjs")
        self.assertEqual(set(payload["presetPayloads"]), {
            "text_length", "duration", "speaker_frequency", "role_frequency",
        })
        segments = [
            {"id": "zero", "text": "", "speaker": "A", "speaker_name": "Synthetic",
             "role": "facilitator", "role_source": "registered", "start": 0, "end": 0, "duration": 0, "valid_time": True},
            {"id": "missing", "text": "abc", "speaker": "B", "speaker_name": "Synthetic",
             "role": None, "start": None, "end": None, "duration": None, "valid_time": False},
        ]
        expected = {"text_length": [0, 3], "duration": [0, None],
                    "speaker_frequency": ["A", "B"], "role_frequency": ["facilitator", None]}
        for key, definition in payload["presetPayloads"].items():
            with self.subTest(preset=key):
                normalized = validate_definition({**definition, "version": 1}, require_version=True)
                rows = measure_segments({"segments": segments}, [normalized], limit=20)
                column = definition["output_column"]
                self.assertEqual([row[column] for row in rows], expected[key])
                self.assertNotIn("text", rows[0])
                self.assertNotIn("start", rows[0])
                self.assertEqual(rows[0][column + "__missing_reason"], "")
                if expected[key][1] is None:
                    self.assertTrue(rows[1][column + "__missing_reason"])

    def test_truthful_pipeline_status(self):
        self.assertEqual(len(self.probe("test_analysis_status_ui.cjs")["passed"]), 32)

    def test_evidence_audio_guard(self):
        result = self.probe("test_analysis_evidence_ui.cjs")
        self.assertEqual(len(result["results"]), 25)
        self.assertTrue(all(case["contractPassed"] for case in result["results"]))
