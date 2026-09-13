import base64
import codecs
import os
import shutil
import subprocess
import unittest
from pathlib import Path

import app


class SetupGuiTests(unittest.TestCase):
    def test_windows_setup_gui_bootstraps_without_python_and_preserves_local_llm_settings(self):
        root = app.PROJECT_DIRECTORY
        script_path = root / "scripts" / "setup_gui.ps1"
        launcher_path = root / "setup_gui.bat"
        raw = script_path.read_bytes()
        script = raw.decode("utf-8-sig")
        launcher = launcher_path.read_text(encoding="utf-8")

        self.assertTrue(raw.startswith(codecs.BOM_UTF8))
        self.assertIn("System.Windows.Forms", script)
        self.assertIn("Python.Python.3.12", script)
        self.assertIn("Gyan.FFmpeg", script)
        self.assertIn("MOJIOKOSI_SETUP_ONLY", script)
        self.assertIn("lmstudio_base_url", script)
        self.assertIn("Normalize-LmStudioUrl", script)
        self.assertIn("127.0.0.1", script)
        self.assertIn("UseSystemPasswordChar", script)
        self.assertIn("秘密鍵は画面上で伏せて表示し、ログには書き込みません", script)
        self.assertIn('setup_gui.ps1', launcher)

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "Requires Windows PowerShell")
    def test_environment_report_runs_before_the_form_is_shown(self):
        # The report fills the form before ShowDialog; a runtime error there
        # prevents the setup window from opening at all.
        command = r"""
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$path = $env:GURUMOJI_SETUP_SCRIPT
$ast = [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$null, [ref]$null)
$functions = $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false)
$script:Root = $env:GURUMOJI_PROJECT_ROOT
$script:TokenFile = Join-Path $script:Root 'config\tokens.json'
foreach ($function in $functions) { . ([scriptblock]::Create($function.Extent.Text)) }
Get-EnvironmentReport
"""
        encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
        env = dict(os.environ)
        env["GURUMOJI_SETUP_SCRIPT"] = str(Path(app.PROJECT_DIRECTORY) / "scripts" / "setup_gui.ps1")
        env["GURUMOJI_PROJECT_ROOT"] = str(app.PROJECT_DIRECTORY)
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            capture_output=True, text=True, errors="replace", env=env, timeout=60,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for label in ("Python:", "FFmpeg:", "tokens.json:"):
            self.assertIn(label, result.stdout)


if __name__ == "__main__":
    unittest.main()
