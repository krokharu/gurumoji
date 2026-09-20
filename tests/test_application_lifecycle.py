"""Focused tests for startup and watcher ownership without Flask."""

import threading
import unittest
import importlib

from gurumoji.handlers.application_lifecycle import ApplicationLifecycle


class FakeWorker:
    def __init__(self):
        self.alive = True
        self.joined = []

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.joined.append(timeout)
        self.alive = False


class ApplicationLifecycleTests(unittest.TestCase):
    def test_compatibility_import_is_the_package_module(self):
        self.assertIs(importlib.import_module("app"), importlib.import_module("gurumoji.app"))

    def lifecycle(self, calls, *, fail_at=None):
        def step(name, value=None):
            def run():
                calls.append(name)
                if name == fail_at:
                    raise RuntimeError(name)
                return value
            return run

        self.stop = threading.Event()
        self.worker = FakeWorker()
        self.spawn_count = 0

        def spawn():
            self.spawn_count += 1
            return self.stop, self.worker

        return ApplicationLifecycle(
            acquire_instance_lock=step("lock", True),
            release_instance_lock=step("release"),
            initialize_library=step("library"),
            recover_edits=step("edits", ["edit-warning"]),
            repair_provenance=step("provenance"),
            recover_deletes=step("deletes", ["delete-warning"]),
            repair_training=step("training"),
            cleanup_uploads=step("uploads"),
            import_outputs=step("import"),
            report_edit_warning=lambda value: calls.append(("edit-warning", value)),
            report_delete_warning=lambda value: calls.append(("delete-warning", value)),
            spawn_watcher=spawn,
        )

    def test_startup_recovery_order_is_explicit(self):
        calls = []
        self.lifecycle(calls).initialize()
        self.assertEqual(calls, [
            "lock", "library", "edits", ("edit-warning", "edit-warning"),
            "provenance", "deletes", ("delete-warning", "delete-warning"),
            "training", "uploads", "import",
        ])

    def test_failed_startup_releases_the_instance_lock(self):
        calls = []
        with self.assertRaises(RuntimeError):
            self.lifecycle(calls, fail_at="training").initialize()
        self.assertEqual(calls[-1], "release")
        self.assertNotIn("uploads", calls)

    def test_watcher_is_single_and_shutdown_stops_before_unlock(self):
        calls = []
        lifecycle = self.lifecycle(calls)
        first = lifecycle.start_watcher()
        second = lifecycle.start_watcher()
        self.assertIs(first, second)
        self.assertEqual(self.spawn_count, 1)
        lifecycle.shutdown()
        self.assertTrue(self.stop.is_set())
        self.assertEqual(self.worker.joined, [2])
        self.assertEqual(calls[-1], "release")


if __name__ == "__main__":
    unittest.main()
