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


class FakeWorkbench:
    database_file = "library.sqlite3"

    def __init__(self, *, recover_error=None, poll_errors=()):
        self.recover_error = recover_error
        self.poll_errors = list(poll_errors)
        self.polls = 0
        self.polled = threading.Event()
        self.layout = self

    def recover(self):
        if self.recover_error:
            raise self.recover_error

    def poll_once(self, engine, stopping):
        self.polls += 1
        if self.poll_errors:
            error = self.poll_errors.pop(0)
            if error:
                raise error
        self.polled.set()

    def sync_themes(self):
        pass


class ObsidianWatcherStatusTests(unittest.TestCase):
    def run_watcher(self, workbench):
        from gurumoji.services.obsidian_watcher import ObsidianWatcher, WatcherStatus
        status = WatcherStatus()
        logged = []
        stop, worker = ObsidianWatcher(
            workbench=lambda: workbench,
            engine=lambda *args: {},
            migrate=lambda database_file: None,
            log_exception=logged.append,
            status=status,
        ).start()
        self.addCleanup(lambda: (stop.set(), worker.join(timeout=5)))
        return status, stop, worker, logged

    def test_not_started_is_reported_before_the_watcher_runs(self):
        from gurumoji.services.obsidian_watcher import WatcherStatus
        snapshot = WatcherStatus().snapshot()
        self.assertEqual(snapshot["state"], "not_started")
        self.assertFalse(snapshot["active"])

    def test_startup_recovery_failure_is_visible_after_the_thread_exits(self):
        status, _stop, worker, logged = self.run_watcher(
            FakeWorkbench(recover_error=OSError("state.json is locked"))
        )
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        snapshot = status.snapshot()
        self.assertEqual(snapshot["state"], "failed")
        self.assertFalse(snapshot["active"])
        self.assertIn("再起動", snapshot["message"])
        self.assertEqual(snapshot["detail"], "OSError: state.json is locked")
        self.assertTrue(snapshot["last_error_at"])
        self.assertEqual(logged, ["Obsidian workbench recovery failed"])

    def test_polling_error_is_reported_and_cleared_by_the_next_success(self):
        workbench = FakeWorkbench(poll_errors=[ValueError("broken note")])
        status, stop, worker, _logged = self.run_watcher(workbench)
        self.assertTrue(workbench.polled.wait(10))
        snapshot = status.snapshot()
        self.assertEqual(snapshot["state"], "running")
        self.assertEqual(snapshot["detail"], "")
        self.assertTrue(snapshot["last_error_at"])
        stop.set()
        worker.join(timeout=5)
        self.assertEqual(status.snapshot()["state"], "stopped")


if __name__ == "__main__":
    unittest.main()
