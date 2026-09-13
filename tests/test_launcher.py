"""Exercise the Windows launcher with local Git repositories, without installing packages."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt" and shutil.which("git") and shutil.which("powershell"),
                     "Requires Windows PowerShell and Git")
class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji launcher ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.remote = self.base / "remote.git"
        self.seed = self.base / "seed"
        self.checkout = self.base / "checkout with spaces"
        self.git(self.base, "init", "--bare", str(self.remote))
        self.git(self.base, "clone", str(self.remote), str(self.seed))
        self.git(self.seed, "checkout", "-b", "main")
        shutil.copy2(ROOT / "run.bat", self.seed / "run.bat")
        (self.seed / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts" / "run_launcher.ps1", self.seed / "scripts" / "run_launcher.ps1")
        (self.seed / ".gitignore").write_text("*.log\n", encoding="utf-8")
        self.commit(self.seed)
        self.git(self.seed, "push", "-u", "origin", "main")
        self.git(self.base, "clone", "-b", "main", str(self.remote), str(self.checkout))

    def git(self, cwd, *args):
        result = subprocess.run(
            ["git", "-c", "user.name=Launcher Test", "-c", "user.email=launcher@example.invalid",
             "-c", "commit.gpgsign=false", *args],
            cwd=cwd, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit(self, directory):
        self.git(directory, "add", ".")
        self.git(directory, "commit", "-m", "Launcher fixture")

    def publish_update(self):
        # Changing the size of the running batch file must not corrupt its caller.
        batch = self.seed / "run.bat"
        batch.write_bytes(b"@rem New launcher revision\r\n" + batch.read_bytes())
        (self.seed / "revision.txt").write_text("updated", encoding="utf-8")
        self.commit(self.seed)
        self.git(self.seed, "push")

    def launch(self, direct=False, skip=False):
        env = {key: value for key, value in os.environ.items() if not key.startswith("MOJIOKOSI_")}
        env["MOJIOKOSI_NO_PAUSE"] = "1"
        # Hardened shells stop cmd from resolving commands in the current directory.
        env["NoDefaultCurrentDirectoryInExePath"] = "1"
        if skip:
            env["MOJIOKOSI_SKIP_UPDATE_CHECK"] = "1"
        command = (["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts\\run_launcher.ps1"]
                   if direct else [os.environ["ComSpec"], "/d", "/c", ".\\run.bat"])
        result = subprocess.run(command, cwd=self.checkout, env=env,
                                capture_output=True, text=True, errors="replace", timeout=30)
        logs = list((self.checkout / "runtime" / "logs").glob("startup-*.log"))
        self.assertEqual(len(logs), 1, result.stdout + result.stderr)
        self.log = logs[0].read_text(encoding="utf-8")
        return result

    def assert_missing_requirements(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("requirements.txt was not found", result.stdout)
        self.assertIn("requirements.txt was not found", self.log)
        self.assertIn("Startup failed (exit code", self.log)

    def test_current_version_and_failure_log(self):
        result = self.launch()
        self.assert_missing_requirements(result)
        self.assertIn("Source code is up to date", self.log)

    def test_updates_running_batch_and_starts_updated_version(self):
        self.publish_update()
        result = self.launch()
        self.assert_missing_requirements(result)
        self.assertIn("Source code update completed", self.log)
        self.assertEqual(self.git(self.checkout, "rev-parse", "HEAD"), self.git(self.seed, "rev-parse", "HEAD"))

    def test_updates_without_upstream(self):
        self.git(self.checkout, "branch", "--unset-upstream")
        self.publish_update()
        self.assert_missing_requirements(self.launch())
        self.assertIn("Source code update completed", self.log)

    def test_fetches_configured_remote(self):
        self.git(self.checkout, "remote", "rename", "origin", "source")
        self.publish_update()
        self.assert_missing_requirements(self.launch())
        self.assertIn("Updating source code from source/main", self.log)
        self.assertIn("Source code update completed", self.log)

    def test_preserves_local_changes(self):
        batch = self.checkout / "run.bat"
        original = batch.read_bytes() + b"\r\n@rem Local customization\r\n"
        batch.write_bytes(original)
        self.publish_update()
        self.assert_missing_requirements(self.launch())
        self.assertIn("skipped to protect local files", self.log)
        self.assertEqual(batch.read_bytes(), original)
        self.assertFalse((self.checkout / "revision.txt").exists())

    def test_diverged_history_is_preserved(self):
        (self.checkout / "local.txt").write_text("local", encoding="utf-8")
        self.commit(self.checkout)
        original = self.git(self.checkout, "rev-parse", "HEAD")
        self.publish_update()
        self.assert_missing_requirements(self.launch())
        self.assertIn("Automatic update failed", self.log)
        self.assertEqual(self.git(self.checkout, "rev-parse", "HEAD"), original)

    def test_fetch_failure_continues_startup(self):
        self.git(self.checkout, "remote", "set-url", "origin", str(self.base / "missing.git"))
        self.assert_missing_requirements(self.launch())
        self.assertIn("Source update check failed", self.log)

    def test_stdout_stderr_and_exit_code(self):
        (self.checkout / "run.bat").write_bytes(
            b"@echo off\r\necho application output\r\necho simulated traceback 1>&2\r\nexit /b 42\r\n"
        )
        result = self.launch(direct=True, skip=True)
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
        for text in ("application output", "simulated traceback", "exit code 42"):
            self.assertIn(text, self.log)
            self.assertIn(text, result.stdout)

    def test_success_exit_code(self):
        (self.checkout / "run.bat").write_bytes(b"@echo off\r\necho started\r\nexit /b 0\r\n")
        result = self.launch(direct=True, skip=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Startup failed", self.log)


if __name__ == "__main__":
    unittest.main()
