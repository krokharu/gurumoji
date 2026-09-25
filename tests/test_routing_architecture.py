"""Architecture gates for the completed handler/routing extraction."""

import ast
import importlib
import json
import re
import unittest
from pathlib import Path

import app


class RoutingArchitectureTests(unittest.TestCase):
    def test_compatibility_import_remains_the_canonical_module(self):
        self.assertIs(
            importlib.import_module("app"),
            importlib.import_module("gurumoji.app"),
        )

    def test_handlers_and_routes_never_import_the_composition_module(self):
        source_root = Path(__file__).resolve().parents[1] / "src" / "gurumoji"
        violations = []
        # Everything except the composition module itself must stay importable
        # without it; otherwise extracted modules silently re-couple to app.py.
        for folder in (source_root,):
            for path in folder.rglob("*.py"):
                if path == source_root / "app.py":
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        if any(alias.name == "gurumoji.app" for alias in node.names):
                            violations.append(str(path))
                    elif isinstance(node, ast.ImportFrom):
                        if node.module in {"app", "gurumoji.app"}:
                            violations.append(str(path))
        self.assertEqual(violations, [])

    def test_migrated_http_operations_are_registered_once(self):
        expected = {
            ("/api/analysis/methods", "GET"),
            ("/api/analysis/artifacts/<artifact_id>", "GET"),
            ("/api/analysis/runs/<run_id>/vault", "POST"),
            ("/api/library/<item_id>/analysis/runs", "GET"),
            ("/api/library/<item_id>/analysis/runs", "POST"),
            ("/api/library/<item_id>/analysis/insights", "GET"),
            ("/api/library/<item_id>/analysis/insights", "POST"),
            ("/api/library/<item_id>/analysis/insights/cancel", "POST"),
            ("/api/library/<item_id>/analysis/transformer", "GET"),
            ("/api/library/<item_id>/analysis/transformer", "POST"),
            ("/api/library/<item_id>/analysis/transformer/cancel", "POST"),
            ("/api/library/<item_id>/analysis/classifications", "GET"),
            ("/api/library/<item_id>/analysis/classifications", "POST"),
            ("/api/library/<item_id>/preparation", "PUT"),
            ("/api/library/<item_id>", "PUT"),
            ("/api/library/interview-comparison/runs", "POST"),
            ("/api/speakers", "GET"),
            ("/api/speakers", "PUT"),
            ("/api/speakers/import", "POST"),
            ("/api/library/<item_id>/speaker-identification", "POST"),
            ("/api/jobs", "POST"),
            ("/api/jobs/<job_id>", "GET"),
            ("/api/jobs/active", "GET"),
            ("/api/jobs/<job_id>/cancel", "POST"),
            ("/api/jobs/<job_id>/transcript", "PUT"),
            ("/api/jobs/<job_id>/files/<path:filename>", "GET"),
        }
        for path, method in expected:
            matches = [
                rule for rule in app.app.url_map.iter_rules()
                if str(rule.rule) == path and method in rule.methods
            ]
            self.assertEqual(len(matches), 1, (path, method, matches))

        endpoints = {
            rule.endpoint: str(rule.rule) for rule in app.app.url_map.iter_rules()
        }
        self.assertEqual(endpoints["create_job"], "/api/jobs")
        self.assertEqual(
            endpoints["import_speaker_registry"], "/api/speakers/import"
        )

    def test_adapters_receive_names_that_tests_patch_on_app(self):
        """A patch on ``app.X`` only reaches code that looks X up through app.

        Routing and handler modules therefore take such names as injected
        dependencies (the composition passes late-bound lambdas) instead of
        importing them. Otherwise a test that patches ``app.X`` would keep
        passing while exercising the real implementation.
        """
        tests_root = Path(__file__).resolve().parent
        pattern = re.compile(
            r"patch(?:\.object)?\(\s*app\s*,\s*['\"](\w+)"
            r"|patch\(['\"]app\.(\w+)['\"]"
        )
        patched = set()
        for path in tests_root.glob("test_*.py"):
            for match in pattern.finditer(path.read_text(encoding="utf-8")):
                patched.add(match.group(1) or match.group(2))
        source_root = tests_root.parent / "src" / "gurumoji"
        violations = []
        for folder in (source_root / "handlers", source_root / "web"):
            for path in folder.glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                imported = {
                    alias.asname or alias.name
                    for node in tree.body if isinstance(node, ast.ImportFrom)
                    for alias in node.names
                }
                for name in sorted(imported & patched):
                    violations.append(f"{path.name}: {name}")
        self.assertEqual(violations, [])

    def test_route_map_matches_the_committed_snapshot(self):
        """URL, method and endpoint stay identical while routes move modules.

        ``enforce_request_security`` keys upload limits on endpoint names, so
        an endpoint rename is a behavior change. Regenerate the fixture only
        for an intentional API change.
        """
        fixture = Path(__file__).resolve().parent / "fixtures" / "route_map.json"
        expected = json.loads(fixture.read_text(encoding="utf-8"))
        actual = sorted(
            [rule.rule, sorted(rule.methods - {"HEAD", "OPTIONS"}), rule.endpoint]
            for rule in app.app.url_map.iter_rules()
        )
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
