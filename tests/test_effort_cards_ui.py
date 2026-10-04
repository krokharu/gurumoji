"""Run deterministic effort-card DOM/network contracts without a browser or AI."""
import shutil
import subprocess
import unittest
from pathlib import Path


class EffortCardSyntheticTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is required for synthetic UI contracts")
    def test_synthetic_effort_cards(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which("node"), "--test", "tests/ui/effort-cards.test.cjs"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
