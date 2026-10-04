"""Collection and legacy-entrypoint safety; no real browser or server is started."""

import ast
from contextlib import ExitStack, contextmanager, nullcontext, redirect_stderr, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

import browser_support

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (
    "scripts/browser_video_input_settings_qa.py",
    "scratch/analysis_visual_qa.py",
    "scratch/test_browser_e2e_recovered.py",
)


def load_entrypoint(relative_path):
    spec = importlib.util.spec_from_file_location("qa_entrypoint_under_test", ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, "path", list(sys.path)):
        spec.loader.exec_module(module)
    return module


class BrowserEntrypointTests(unittest.TestCase):
    def test_import_and_default_opt_out_have_no_process_server_or_file_side_effects(self):
        for relative_path in ENTRYPOINTS:
            with self.subTest(path=relative_path), ExitStack() as cleanup:
                cleanup.enter_context(patch.dict(os.environ, {}, clear=True))
                spawn = cleanup.enter_context(patch.object(subprocess, "Popen", side_effect=AssertionError("Unexpected spawn")))
                launch = cleanup.enter_context(patch.object(browser_support, "sandboxed_playwright_browser", side_effect=AssertionError("Unexpected browser")))
                mkdir = cleanup.enter_context(patch.object(Path, "mkdir", side_effect=AssertionError("Unexpected output write")))
                write = cleanup.enter_context(patch.object(Path, "write_text", side_effect=AssertionError("Unexpected report")))
                # The opt-out path must not even import runtime/server/Playwright.
                original_import = __import__

                def guarded_import(name, *args, **kwargs):
                    if name == "app" or name.startswith(("werkzeug", "playwright")):
                        raise AssertionError(f"Unexpected runtime import: {name}")
                    return original_import(name, *args, **kwargs)

                cleanup.enter_context(patch("builtins.__import__", side_effect=guarded_import))
                output = io.StringIO()
                cleanup.enter_context(redirect_stdout(output))
                cleanup.enter_context(redirect_stderr(output))
                module = load_entrypoint(relative_path)
                self.assertEqual(module.main(), 2)
                self.assertIn("not-run:", output.getvalue())
                for mocked in (spawn, launch, mkdir, write):
                    mocked.assert_not_called()

    def test_retired_copy_cannot_be_reenabled_or_collected(self):
        with patch.dict(os.environ, {browser_support.OPT_IN_ENV: "1"}), \
                patch.object(subprocess, "Popen") as spawn, redirect_stdout(io.StringIO()):
            module = load_entrypoint(ENTRYPOINTS[2])
            self.assertFalse(module.__test__)
            self.assertEqual(unittest.defaultTestLoader.loadTestsFromModule(module).countTestCases(), 0)
            self.assertEqual(module.main(), 2)
        spawn.assert_not_called()

    def test_cli_status_distinguishes_blocked_assertions_and_timeouts(self):
        for relative_path in ENTRYPOINTS[:2]:
            module = load_entrypoint(relative_path)
            with self.subTest(path=relative_path), redirect_stderr(io.StringIO()):
                with patch.object(module, "_run", side_effect=unittest.SkipTest("blocked: sandbox")):
                    self.assertEqual(module.main(), 2)
                for error in (AssertionError("missing marker"), TimeoutError("page timed out"), RuntimeError("JavaScript error")):
                    with patch.object(module, "_run", side_effect=error), self.assertRaises(type(error)) as raised:
                        module.main()
                    self.assertIs(raised.exception, error)

    def test_remaining_entrypoints_only_use_the_common_safe_launcher(self):
        for relative_path in ENTRYPOINTS:
            with self.subTest(path=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                tree = ast.parse(source)
                for flag in ("--no-sandbox", "--disable-setuid-sandbox", "--disable-web-security", "--ignore-certificate-errors"):
                    self.assertNotIn(flag, source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        self.assertNotIn(node.func.attr, ("launch", "launch_persistent_context", "Popen"))
                    if isinstance(node, ast.ImportFrom):
                        self.assertNotEqual(node.module, "playwright.sync_api")
                if relative_path != ENTRYPOINTS[2]:
                    run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_run")
                    self.assertEqual(ast.unparse(run.body[0]), "browser_support.require_ui_browser()")
                    self.assertIn("browser_support.sandboxed_playwright_browser()", source)


class ScriptLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.cleanup = ExitStack()
        self.addCleanup(self.cleanup.close)
        enter = self.cleanup.enter_context
        enter(patch.dict(os.environ, {browser_support.OPT_IN_ENV: "1"}))
        enter(patch.object(subprocess, "Popen", side_effect=AssertionError("Unexpected spawn")))
        enter(redirect_stdout(io.StringIO()))
        self.app = ModuleType("app")
        self.original_database = Path("/synthetic/original.sqlite3")
        self.app.DATABASE_FILE = self.original_database
        self.app.initialize_library = Mock()
        self.app.jobs_lock = nullcontext()
        self.app.jobs = {}
        self.app._job_admission_id = None
        self.app.app = object()
        self.app.get_machine_profile = Mock()
        self.app.load_token_config = Mock()
        self.app.TokenConfig = Mock()
        self.serving = ModuleType("werkzeug.serving")
        self.serving.make_server = Mock()
        self.server = self.serving.make_server.return_value
        self.server.server_port = 12345
        enter(patch.dict(sys.modules, {"app": self.app, "werkzeug.serving": self.serving}))
        self.browser = Mock()
        self.closed = Mock()

        @contextmanager
        def browser_context():
            try:
                yield self.browser
            finally:
                self.closed()

        self.launch = enter(patch.object(browser_support, "sandboxed_playwright_browser", side_effect=browser_context))
        self.mkdir = enter(patch.object(Path, "mkdir"))
        self.write = enter(patch.object(Path, "write_text"))

    def video_script(self):
        module = load_entrypoint(ENTRYPOINTS[0])
        self.temporary = self.cleanup.enter_context(patch.object(module.tempfile, "TemporaryDirectory"))
        self.temporary.return_value.__enter__.return_value = "/synthetic/qa"
        self.thread = self.cleanup.enter_context(patch.object(module.threading, "Thread")).return_value
        self.cleanup.enter_context(patch.object(module, "install_fixtures", return_value={}))
        self.initial = self.cleanup.enter_context(patch.object(module, "inspect_initial", return_value={
            "form_visible": True, "all_panels_closed": True, "no_horizontal_overflow": True,
            "cta_initially_disabled": True, "cta_visible": True,
        }))
        self.cleanup.enter_context(patch.object(module, "inspect_fonts", return_value={
            key: 16 for key in ("setting_label", "setting_value", "mode_title", "panel_title", "mode_help", "panel_help")
        }))
        self.interactions = self.cleanup.enter_context(patch.object(module, "run_interactions", return_value={"check": True}))
        self.cleanup.enter_context(patch.object(module, "run_mobile", return_value={"check": True}))
        self.contexts = [Mock() for _ in range(5)]
        self.browser.new_context.side_effect = self.contexts
        return module

    def test_video_qa_preserves_viewports_reports_and_cleanup(self):
        module = self.video_script()
        self.assertEqual(module.main(), 0)
        self.launch.assert_called_once_with()
        self.assertEqual([call.kwargs["viewport"] for call in self.browser.new_context.call_args_list], [
            {"width": 1440, "height": 900}, {"width": 1280, "height": 800},
            {"width": 390, "height": 844}, {"width": 1440, "height": 900},
            {"width": 390, "height": 844},
        ])
        for context in self.contexts:
            context.close.assert_called_once_with()
        self.server.shutdown.assert_called_once_with()
        self.server.server_close.assert_called_once_with()
        self.thread.join.assert_called_once_with(timeout=5)
        self.temporary.return_value.__exit__.assert_called_once()
        self.closed.assert_called_once_with()
        self.assertEqual(self.app.DATABASE_FILE, self.original_database)
        self.write.assert_called_once()

    def test_failed_checks_return_failure_and_do_not_become_skip(self):
        module = self.video_script()
        self.interactions.return_value = {"marker": False}
        self.assertEqual(module.main(), 1)

    def test_video_assertion_cleans_up_browser_context_server_and_database(self):
        module = self.video_script()
        self.initial.side_effect = AssertionError("marker missing")
        with self.assertRaisesRegex(AssertionError, "marker missing"):
            module.main()
        self.contexts[0].close.assert_called_once_with()
        self.server.shutdown.assert_called_once_with()
        self.server.server_close.assert_called_once_with()
        self.closed.assert_called_once_with()
        self.assertEqual(self.app.DATABASE_FILE, self.original_database)
        self.write.assert_not_called()

    def test_video_initialization_failure_restores_database_before_server_start(self):
        module = self.video_script()
        self.app.initialize_library.side_effect = RuntimeError("fixture failed")
        with self.assertRaisesRegex(RuntimeError, "fixture failed"):
            module.main()
        self.serving.make_server.assert_not_called()
        self.closed.assert_called_once_with()
        self.assertEqual(self.app.DATABASE_FILE, self.original_database)

    def test_analysis_fixture_failure_still_cleans_up_without_server(self):
        module = load_entrypoint(ENTRYPOINTS[1])
        fixtures = ModuleType("test_analysis_method_view")
        fixtures.MethodViewFixture = Mock()
        fixture = fixtures.MethodViewFixture.return_value
        fixture.setUp.side_effect = AssertionError("fixture failed")
        with patch.dict(sys.modules, {"test_analysis_method_view": fixtures}):
            with self.assertRaisesRegex(AssertionError, "fixture failed"):
                module.main(["before"])
        fixture.doCleanups.assert_called_once_with()
        self.serving.make_server.assert_not_called()
        self.closed.assert_called_once_with()


class PytestCollectionSafetyTests(unittest.TestCase):
    def test_root_collect_only_matches_explicit_canonical_tests_without_launch(self):
        try:
            import pytest
        except ModuleNotFoundError:
            self.skipTest("optional pytest dependency is not installed")

        class CaptureCollection:
            def pytest_collection_finish(self, session):
                self.nodeids = [item.nodeid for item in session.items]
                self.testpaths = session.config.getini("testpaths")

        collected = []
        previous_cwd = Path.cwd()
        with patch.dict(os.environ, {"GURUMOJI_RUN_UI_BROWSER": "0", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}), \
                patch.object(subprocess, "Popen", side_effect=AssertionError("Collection spawned a process")) as spawn, \
                patch.object(browser_support, "sandboxed_playwright_browser", side_effect=AssertionError("Collection launched browser")) as launch:
            try:
                os.chdir(ROOT)
                for paths in ([], ["tests/"]):
                    capture = CaptureCollection()
                    output = io.StringIO()
                    with redirect_stdout(output), redirect_stderr(output):
                        status = pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider", *paths], plugins=[capture])
                    self.assertEqual(status, 0, output.getvalue()[-5000:])
                    self.assertEqual(capture.testpaths, ["tests"])
                    collected.append(capture.nodeids)
            finally:
                os.chdir(previous_cwd)
        self.assertEqual(collected[0], collected[1])
        self.assertTrue(collected[0])
        self.assertTrue(all(nodeid.startswith("tests/") for nodeid in collected[0]))
        for expected in (
            "test_analysis_method_view.py::MethodOverviewApiTests::test_missing_item_is_reported",
            "test_transcript_preparation.py::TranscriptPreparationTests::test_unknown_metadata_stays_unknown",
            "test_browser_e2e.py::BrowserJobRecoveryTests::test_real_browser_restores_the_active_job",
        ):
            self.assertIn("tests/" + expected, collected[0])
        spawn.assert_not_called()
        launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
