"""Run dependency-free Node boundary probes in the normal Python test suite.

These are source/handler tests with synthetic fixtures, not native browser or AT
acceptance. They do not start a server or touch user data.
"""
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UiBoundaryProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if cls.node is None:
            raise unittest.SkipTest("Node is required for offline UI boundary probes; browser acceptance is not run")

    def probe(self, filename):
        result = subprocess.run(
            [self.node, str(ROOT / "tests" / filename)], cwd=ROOT,
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"{filename}\n{result.stdout}\n{result.stderr}")
        self.assertTrue(result.stdout.strip(), f"{filename} did not report its test result")

    def test_speaker_literal_keys(self):
        self.probe("test_speaker_literal_keys_ui.cjs")

    def test_speaker_time_semantics(self):
        self.probe("test_speaker_time_ui.cjs")

    def test_history_url_boundaries(self):
        self.probe("test_analysis_history_urls_ui.cjs")

    def test_route_response_ownership(self):
        self.probe("test_route_ownership_ui.cjs")

    def test_analysis_save_response_ownership(self):
        self.probe("test_analysis_save_ownership_ui.cjs")

    def test_analysis_missing_time_display(self):
        self.probe("test_analysis_time_display_ui.cjs")

    def test_speaker_role_insight_provenance(self):
        self.probe("test_speaker_role_insights_ui.cjs")

    def test_speaker_timing_projection_binding(self):
        self.probe("test_speaker_timing_projection_ui.cjs")
