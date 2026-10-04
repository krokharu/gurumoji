"""Pure launcher contracts: all process and Playwright operations are mocked."""

import ast
from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

import browser_support as support


class BrowserSupportTests(unittest.TestCase):
    def setUp(self):
        cleanup = ExitStack()
        self.addCleanup(cleanup.close)
        cleanup.enter_context(patch.dict(os.environ, {support.OPT_IN_ENV: "1"}))
        self.find = cleanup.enter_context(patch.object(support, "browser_executable", return_value="/mock/chromium"))
        self.run = cleanup.enter_context(patch.object(support.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "<body>ok</body>", "")))
        self.spawn = cleanup.enter_context(patch.object(support.subprocess, "Popen", side_effect=AssertionError("Unexpected process spawn")))

    def launch(self, **kwargs):
        return support.run_browser_dom(
            "http://gurumoji.test/", profile=Path("/synthetic/profile"),
            virtual_time_budget_ms=7000, timeout_seconds=30, **kwargs,
        )

    def test_opt_out_never_discovers_or_spawns_a_browser(self):
        for value in (None, "", "0", "true", "yes", "01"):
            with self.subTest(value=value), patch.dict(os.environ, {}, clear=True):
                if value is not None:
                    os.environ[support.OPT_IN_ENV] = value
                with self.assertRaisesRegex(unittest.SkipTest, "not-run:"):
                    self.launch()
                with self.assertRaisesRegex(unittest.SkipTest, "not-run:"):
                    with support.sandboxed_playwright_browser():
                        self.fail("Opt-out yielded a browser")
        self.find.assert_not_called()
        self.run.assert_not_called()
        self.spawn.assert_not_called()

    def test_fixed_safe_flags_and_named_dimensions_budget_timeout(self):
        result = self.launch(viewport=(390, 844), device_scale_factor_one=True)
        self.assertIs(result, self.run.return_value)
        self.run.assert_called_once_with(
            ["/mock/chromium", "--headless=new", "--disable-gpu",
             "--disable-background-networking", "--disable-extensions",
             "--no-first-run", "--no-default-browser-check",
             "--window-size=390,844", "--force-device-scale-factor=1",
             f"--user-data-dir={Path('/synthetic/profile').resolve()}",
             "--virtual-time-budget=7000", "--dump-dom", "http://gurumoji.test/"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, check=False,
        )

    def test_profile_is_mandatory_and_existing_profile_can_be_reused(self):
        with self.assertRaises(TypeError):
            support.run_browser_dom("http://gurumoji.test/", virtual_time_budget_ms=1, timeout_seconds=1)
        self.launch()
        first = self.run.call_args.args[0]
        self.launch()
        self.assertEqual(first, self.run.call_args.args[0])

    def test_media_fixture_opt_in_does_not_change_default_autoplay(self):
        self.launch()
        self.assertFalse(any(flag.startswith("--autoplay-policy") for flag in self.run.call_args.args[0]))
        self.launch(allow_media_autoplay=True)
        self.assertIn("--autoplay-policy=no-user-gesture-required", self.run.call_args.args[0])

    def test_arbitrary_or_security_arguments_cannot_be_supplied(self):
        for kwargs in (
            {"extra_args": ["--no-sandbox"]}, {"args": ["--disable-web-security"]},
            {"chromium_sandbox": False}, {"ignore_https_errors": True},
            {"executable": "--no-sandbox"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                self.launch(**kwargs)
        self.run.assert_not_called()

    def test_named_fields_cannot_inject_flags(self):
        for kwargs in (
            {"viewport": ("--no-sandbox", 900)}, {"viewport": (1440, 0)},
            {"viewport": (True, 900)}, {"allow_media_autoplay": "--no-sandbox"},
            {"device_scale_factor_one": "--disable-web-security"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.launch(**kwargs)
        for budget in ("7000 --no-sandbox", 0, -1, True):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                support.run_browser_dom("http://gurumoji.test/", profile=Path("/synthetic/profile"),
                                        virtual_time_budget_ms=budget, timeout_seconds=30)
        for timeout in (0, -1, True, float("inf"), float("nan"), "30"):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                support.run_browser_dom("http://gurumoji.test/", profile=Path("/synthetic/profile"),
                                        virtual_time_budget_ms=7000, timeout_seconds=timeout)
        with self.assertRaises(ValueError):
            support.run_browser_dom("--no-sandbox", profile=Path("/synthetic/profile"),
                                    virtual_time_budget_ms=7000, timeout_seconds=30)
        self.run.assert_not_called()

    def test_missing_executable_is_blocked_without_spawn(self):
        self.find.return_value = None
        with self.assertRaisesRegex(unittest.SkipTest, "blocked: an installed"):
            self.launch()
        self.run.assert_not_called()

    def test_disappearing_or_inaccessible_executable_is_blocked(self):
        for error in (FileNotFoundError("gone"), PermissionError("not executable")):
            self.run.side_effect = error
            with self.subTest(error=error), self.assertRaisesRegex(unittest.SkipTest, "blocked:"):
                self.launch()

    def test_only_explicit_startup_diagnostics_are_blocked(self):
        for diagnostic in (
            "[FATAL] No usable sandbox!",
            "Running as root without --no-sandbox is not supported",
            "Failed to move to new namespace: Operation not permitted",
            "Failed to unshare namespaces: Operation not permitted",
            "socket() failed: Operation not permitted (1)",
        ):
            self.run.return_value = subprocess.CompletedProcess([], 1, "", diagnostic)
            with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(unittest.SkipTest, "blocked: browser launch:"):
                self.launch()

    def test_application_errors_missing_markers_and_nonzero_exits_are_not_skips(self):
        for stdout, stderr, returncode in (
            ('<body data-test="failed: assertion"></body>', "", 0),
            ('<body data-script-error="TypeError"></body>', "", 0),
            ("<body>missing marker</body>", "", 0),
            ("", "unknown browser crash", 1),
            ("", "app sandbox assertion failed: permission denied", 1),
            ('<body data-test="failed: assertion"></body>', "No usable sandbox!", 1),
        ):
            expected = subprocess.CompletedProcess([], returncode, stdout, stderr)
            self.run.return_value = expected
            with self.subTest(stdout=stdout, stderr=stderr):
                self.assertIs(self.launch(), expected)

    def test_regular_timeout_and_unexpected_errors_remain_failures(self):
        for error in (
            subprocess.TimeoutExpired("chromium", 30, stderr="No usable sandbox!"),
            OSError("unexpected launch error"), AssertionError("marker missing"),
        ):
            self.run.side_effect = error
            with self.subTest(error=error), self.assertRaises(type(error)) as raised:
                self.launch()
            self.assertIs(raised.exception, error)


class BrowserDiscoveryTests(unittest.TestCase):
    def test_path_discovery_prefers_first_existing_candidate_without_processes(self):
        with patch.object(support.shutil, "which", side_effect=[None, "/mock/chrome", "/mock/chromium", None]) as which, \
                patch.object(Path, "is_file", return_value=True), \
                patch.object(support.subprocess, "Popen") as spawn:
            self.assertEqual(support.browser_executable(), "/mock/chrome")
        self.assertEqual([call.args[0] for call in which.call_args_list], ["msedge", "chrome", "chromium", "chromium-browser"])
        spawn.assert_not_called()

    def test_windows_fallback_and_missing_browser(self):
        with patch.object(support.shutil, "which", return_value=None), \
                patch.object(Path, "is_file", side_effect=[False, True]):
            self.assertEqual(support.browser_executable(), r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
        with patch.object(support.shutil, "which", return_value=None), \
                patch.object(Path, "is_file", return_value=False):
            self.assertIsNone(support.browser_executable())


class PlaywrightSupportTests(unittest.TestCase):
    def setUp(self):
        cleanup = ExitStack()
        self.addCleanup(cleanup.close)
        cleanup.enter_context(patch.dict(os.environ, {support.OPT_IN_ENV: "1"}))
        cleanup.enter_context(patch.object(support, "browser_executable", return_value="/mock/chromium"))
        self.spawn = cleanup.enter_context(patch.object(subprocess, "Popen", side_effect=AssertionError("Unexpected process spawn")))
        self.api = ModuleType("playwright.sync_api")
        self.api.Error = type("PlaywrightError", (Exception,), {})
        self.api.TimeoutError = type("PlaywrightTimeoutError", (self.api.Error,), {})
        self.api.sync_playwright = Mock()
        self.playwright = self.api.sync_playwright.return_value.start.return_value
        self.browser = self.playwright.chromium.launch.return_value
        self.events = []
        self.playwright.stop.side_effect = lambda: self.events.append("stop")
        self.browser.close.side_effect = lambda: self.events.append("close")
        cleanup.enter_context(patch.dict(sys.modules, {"playwright": ModuleType("playwright"), "playwright.sync_api": self.api}))

    def test_sandbox_is_fixed_and_cleanup_order_is_browser_then_driver(self):
        with support.sandboxed_playwright_browser() as browser:
            self.assertIs(browser, self.browser)
            self.assertEqual(self.events, [])
        self.playwright.chromium.launch.assert_called_once_with(
            executable_path="/mock/chromium", headless=True, chromium_sandbox=True,
        )
        self.assertEqual(self.events, ["close", "stop"])
        self.spawn.assert_not_called()

    def test_playwright_managed_executable_fallback_is_preserved(self):
        with patch.object(support, "browser_executable", return_value=None):
            with support.sandboxed_playwright_browser():
                pass
        self.playwright.chromium.launch.assert_called_once_with(
            executable_path=None, headless=True, chromium_sandbox=True,
        )

    def test_playwright_cannot_receive_extra_or_unsafe_arguments(self):
        for kwargs in ({"args": ["--no-sandbox"]}, {"chromium_sandbox": False}, {"ignore_https_errors": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                with support.sandboxed_playwright_browser(**kwargs):
                    self.fail("Unsafe arguments were accepted")
        self.api.sync_playwright.assert_not_called()

    def test_missing_optional_dependency_is_blocked(self):
        with patch.dict(sys.modules, {"playwright.sync_api": None}):
            with self.assertRaisesRegex(unittest.SkipTest, "blocked: optional Playwright"):
                with support.sandboxed_playwright_browser():
                    self.fail("Missing dependency yielded a browser")
        self.api.sync_playwright.assert_not_called()

    def test_dependency_import_bug_is_not_a_skip(self):
        original_import = __import__

        def import_with_bug(name, *args, **kwargs):
            if name == "playwright.sync_api":
                raise ModuleNotFoundError("unrelated dependency bug", name="unrelated_dependency")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_with_bug):
            with self.assertRaises(ModuleNotFoundError):
                with support.sandboxed_playwright_browser():
                    self.fail("Import bug yielded a browser")

    def test_blocked_launch_stops_driver_even_before_class_setup_completes(self):
        for message in ("No usable sandbox!", "Executable doesn't exist at /mock/missing"):
            self.events.clear()
            self.playwright.chromium.launch.side_effect = self.api.Error(message)
            with self.subTest(message=message), self.assertRaisesRegex(unittest.SkipTest, "blocked: browser launch:"):
                with support.sandboxed_playwright_browser():
                    self.fail("Blocked launch yielded a browser")
            self.assertEqual(self.events, ["stop"])

    def test_unexpected_launch_failure_stops_driver_and_remains_an_error(self):
        error = self.api.Error("unexpected launch failure")
        self.playwright.chromium.launch.side_effect = error
        with self.assertRaises(self.api.Error) as raised:
            with support.sandboxed_playwright_browser():
                self.fail("Failed launch yielded a browser")
        self.assertIs(raised.exception, error)
        self.assertEqual(self.events, ["stop"])

    def test_launch_timeout_never_turns_into_a_blocker_skip(self):
        error = self.api.TimeoutError("No usable sandbox!")
        self.playwright.chromium.launch.side_effect = error
        with self.assertRaises(self.api.TimeoutError) as raised:
            with support.sandboxed_playwright_browser():
                self.fail("Timed-out launch yielded a browser")
        self.assertIs(raised.exception, error)
        self.assertEqual(self.events, ["stop"])

    def test_body_assertion_javascript_error_or_timeout_cleans_up_without_skipping(self):
        for error in (AssertionError("marker missing"), self.api.Error("No usable sandbox!"), self.api.TimeoutError("wait timed out")):
            self.events.clear()
            with self.subTest(error=error), self.assertRaises(type(error)) as raised:
                with support.sandboxed_playwright_browser():
                    raise error
            self.assertIs(raised.exception, error)
            self.assertEqual(self.events, ["close", "stop"])

    def test_driver_stop_still_runs_if_browser_close_fails(self):
        self.browser.close.side_effect = self.api.Error("close failed")
        with self.assertRaises(self.api.Error):
            with support.sandboxed_playwright_browser():
                pass
        self.assertEqual(self.events, ["stop"])


class BrowserCollectionContracts(unittest.TestCase):
    def test_class_opt_out_skips_before_any_fixture_or_test_process(self):
        events = []
        with patch.dict(os.environ, {}, clear=True):
            @support.ui_browser_test
            class BrowserOnly(unittest.TestCase):
                @classmethod
                def setUpClass(cls):
                    events.append("class setup")

                def setUp(self):
                    events.append("setup")

                def test_browser(self):
                    events.append("browser")

        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(BrowserOnly).run(result)
        self.assertEqual(events, [])
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.skipped), 1)
        self.assertTrue(result.skipped[0][1].startswith("not-run:"))

    def test_method_opt_out_keeps_nonbrowser_tests_in_mixed_classes(self):
        events = []
        with patch.dict(os.environ, {}, clear=True):
            class Mixed(unittest.TestCase):
                def setUp(self):
                    events.append("setup")

                @support.ui_browser_test
                def test_browser(self):
                    events.append("browser")

                def test_api(self):
                    events.append("api")

        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(Mixed).run(result)
        self.assertEqual(events, ["setup", "api"])
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])

    def test_opt_in_decorator_keeps_test_assertion_failures(self):
        with patch.dict(os.environ, {support.OPT_IN_ENV: "1"}):
            @support.ui_browser_test
            class Failing(unittest.TestCase):
                def test_browser(self):
                    self.fail("marker missing")

        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(Failing).run(result)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.skipped, [])

    def test_browser_modules_use_common_launcher_without_unsafe_flags(self):
        files = (
            "test_browser_e2e.py", "test_analysis_method_view.py", "test_content_browser.py",
            "test_qualitative_visualization.py", "test_transcript_preparation.py",
            "test_transformer_content_browser.py", "test_ui_safety_browser.py",
        )
        forbidden = (
            "--no-sandbox", "--disable-setuid-sandbox", "--disable-web-security",
            "--ignore-certificate-errors", "--allow-running-insecure-content",
        )
        for filename in files:
            with self.subTest(filename=filename):
                source = Path(__file__).with_name(filename).read_text(encoding="utf-8")
                for flag in forbidden:
                    self.assertNotIn(flag, source)
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        self.assertNotIn(node.func.attr, ("Popen", "launch"), "Use the common launcher")
                        if isinstance(node.func.value, ast.Name):
                            self.assertFalse(node.func.value.id == "subprocess", "Use the common launcher")
                    if isinstance(node, ast.keyword) and node.arg in ("chromium_sandbox", "ignore_https_errors"):
                        self.fail("Sandbox/security launch options belong only in browser_support")

    def test_repository_decorators_gate_browser_cases_only(self):
        expected = {
            "test_browser_e2e.py": {"BrowserJobRecoveryTests"},
            "test_analysis_method_view.py": {"MethodViewBrowserTests"},
            "test_content_browser.py": {"ContentBrowserTests"},
            "test_qualitative_visualization.py": {"QualitativeVisualizationTests"},
            "test_transcript_preparation.py": {"test_browser_preparation_save_desktop_and_mobile"},
            "test_transformer_content_browser.py": {"TransformerContentBrowserTests"},
            "test_ui_safety_browser.py": {"UiSafetyBrowser"},
        }
        for filename, names in expected.items():
            with self.subTest(filename=filename):
                tree = ast.parse(Path(__file__).with_name(filename).read_text(encoding="utf-8"))
                decorated = {
                    node.name for node in ast.walk(tree)
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef))
                    and any(ast.unparse(decorator) == "browser_support.ui_browser_test"
                            for decorator in node.decorator_list)
                }
                self.assertEqual(decorated, names)


if __name__ == "__main__":
    unittest.main()
