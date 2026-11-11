"""任意計測の停止・再実行・欠測表示・秘密値を含めない境界を検証する。"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from public_colab_source import public_source, load_public_module

SOURCE = public_source("src/gurumoji/colab_monitor.py", "notebooks/Gurumoji_Colab.ipynb")
monitor = load_public_module(SOURCE, "colab_monitor")


def statistics():
    return SimpleNamespace(cpu_percent=Mock(return_value=25), virtual_memory=Mock(return_value=SimpleNamespace(total=16 * 1024**3, available=4 * 1024**3)))


def snapshot():
    return {"cpu_percent": 25, "ram_percent": 75, "ram_used_gib": 12, "ram_total_gib": 16,
            "gpus": [{"id": "GPU-test", "name": "NVIDIA T4", "utilization_percent": 60,
                      "memory_percent": 50, "memory_used_gib": 8, "memory_total_gib": 16}]}


class SnapshotTests(unittest.TestCase):
    def test_collects_cpu_ram_gpu_and_vram_without_loading_models(self):
        metrics = statistics()
        run = Mock(return_value=SimpleNamespace(stdout='0, GPU-test, NVIDIA T4, 60, 8192, 16384\n'))
        result = monitor.collect_runtime_snapshot(runner=run, environ={}, statistics=metrics)
        self.assertEqual(result["cpu_percent"], 25)
        self.assertEqual(result["ram_percent"], 75)
        self.assertEqual(result["ram_used_gib"], 12)
        self.assertEqual(result["gpus"][0]["memory_percent"], 50)
        self.assertEqual(result["gpus"][0]["memory_used_gib"], 8)
        metrics.cpu_percent.assert_called_once_with(interval=0.1)
        self.assertEqual(run.call_args.args[0][0], "nvidia-smi")
        self.assertEqual(run.call_args.kwargs["timeout"], 2)

    def test_gpu_missing_does_not_hide_cpu_and_ram_or_report_a_fake_zero(self):
        result = monitor.collect_runtime_snapshot(runner=Mock(side_effect=FileNotFoundError), environ={}, statistics=statistics())
        self.assertEqual(result["cpu_percent"], 25)
        self.assertEqual(result["ram_percent"], 75)
        self.assertEqual(result["gpu_status"], "unavailable")
        self.assertFalse(result["gpus"])

    def test_cuda_visibility_is_respected(self):
        output = '0, GPU-first, T4, 10, 1024, 16384\n1, GPU-second, L4, 90, 20480, 24576\n'
        for visibility in ("1", "GPU-second"):
            with self.subTest(visibility=visibility):
                result = monitor.collect_runtime_snapshot(runner=Mock(return_value=SimpleNamespace(stdout=output)), environ={"CUDA_VISIBLE_DEVICES": visibility}, statistics=statistics())
                self.assertEqual([gpu["id"] for gpu in result["gpus"]], ["GPU-second"])

    def test_explicit_cpu_mode_never_queries_nvidia(self):
        run = Mock()
        result = monitor.collect_runtime_snapshot(runner=run, environ={"CUDA_VISIBLE_DEVICES": "-1"}, statistics=statistics())
        run.assert_not_called()
        self.assertEqual(result["gpu_status"], "disabled")

    def test_unavailable_gpu_utilization_keeps_valid_memory_values(self):
        run = Mock(return_value=SimpleNamespace(stdout='0, GPU-test, T4, N/A, 8192, 16384\n'))
        result = monitor.collect_runtime_snapshot(runner=run, environ={}, statistics=statistics())
        self.assertIsNone(result["gpus"][0]["utilization_percent"])
        self.assertEqual(result["gpus"][0]["memory_percent"], 50)

    def test_invalid_and_nonfinite_values_are_not_rendered_as_measurements(self):
        metrics = statistics()
        metrics.cpu_percent.return_value = float("nan")
        metrics.virtual_memory.return_value.available = 20 * 1024**3
        run = Mock(return_value=SimpleNamespace(stdout='bad row\n0, GPU-test, T4, inf, -1, 16384\n'))
        result = monitor.collect_runtime_snapshot(runner=run, environ={}, statistics=metrics)
        self.assertIsNone(result["cpu_percent"])
        self.assertIsNone(result["ram_percent"])
        self.assertIsNone(result["gpus"][0]["memory_percent"])


class RenderingTests(unittest.TestCase):
    def test_has_accessible_bars_and_history_for_cpu_gpu_ram(self):
        content = monitor.render_monitor_html([snapshot(), snapshot()])
        for label in ("CPU", "GPU", "RAM", "GPUメモリー", "12.00 / 16.00 GiB", "ランタイム全体", "直近2回"):
            self.assertIn(label, content)
        self.assertEqual(content.count("<progress "), 4)
        self.assertEqual(content.count('role="img"'), 3)

    def test_gpu_name_is_html_escaped(self):
        value = snapshot()
        value["gpus"][0]["name"] = '<script>private-value</script>'
        content = monitor.render_monitor_html([value])
        self.assertNotIn("<script>", content)
        self.assertIn("&lt;script&gt;", content)

    def test_missing_samples_are_not_joined_or_displayed_as_zero(self):
        content = monitor.render_monitor_html([{"cpu_percent": 10}, {"cpu_percent": None}, {"cpu_percent": 30}])
        self.assertNotIn("<polyline", content)
        self.assertEqual(content.count("<circle "), 2)
        self.assertIn("未取得", content)
        self.assertNotIn('value="0.0"', content)

    def test_failed_and_stopped_states_are_clear(self):
        content = monitor.render_monitor_html([{"sample_failed": True}], running=False)
        self.assertIn("停止済み", content)
        self.assertIn("取得できませんでした", content)


class LifecycleTests(unittest.TestCase):
    def test_start_is_nonblocking_and_idempotent_and_stop_ends_sampling(self):
        sampled = threading.Event()
        output = []

        def publish(content):
            output.append(content)
            if "直近1回" in content:
                sampled.set()

        run = Mock(return_value=SimpleNamespace(stdout=json.dumps(snapshot())))
        instance = monitor.RuntimeMonitor("synthetic-python", Path("synthetic-repo"), publish, interval=1, runner=run)
        try:
            self.assertIs(instance.start(), instance)
            thread = instance._thread
            self.assertIs(instance.start()._thread, thread)
            self.assertTrue(sampled.wait(2))
        finally:
            instance.stop()
        self.assertFalse(thread.is_alive())
        self.assertTrue(instance._stop.is_set())
        self.assertIn("停止済み", output[-1])
        self.assertEqual(run.call_args.args[0], ["synthetic-python", "-m", "gurumoji.colab_monitor", "--snapshot"])
        self.assertEqual(run.call_args.kwargs["timeout"], 5)

    def test_history_is_bounded(self):
        instance = monitor.RuntimeMonitor("python", Path("repo"), Mock())
        for _ in range(1000):
            instance.history.append(snapshot())
        self.assertEqual(len(instance.history), 60)

    def test_timeout_and_invalid_worker_output_never_echo_private_values(self):
        for failure in (subprocess.TimeoutExpired(["private-value"], 5), "not-json private-value", "[]"):
            with self.subTest(failure=failure):
                run = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=SimpleNamespace(stdout=failure))
                instance = monitor.RuntimeMonitor("python", Path("repo"), Mock(), runner=run)
                result = instance._sample()
                self.assertTrue(result["sample_failed"])
                self.assertNotIn("private-value", monitor.render_monitor_html([result]))

    def test_invalid_intervals_do_not_start_a_thread(self):
        for interval in (0, 31, True, "2"):
            with self.subTest(interval=interval), self.assertRaises(monitor.ColabSetupError):
                monitor.RuntimeMonitor("python", Path("repo"), Mock(), interval=interval)

    def test_stop_before_start_never_samples(self):
        run = Mock()
        instance = monitor.RuntimeMonitor("python", Path("repo"), Mock(), runner=run)
        instance.stop()
        run.assert_not_called()

    def test_lost_display_stops_background_sampling(self):
        failed = threading.Event()

        def publish(content):
            if "直近1回" in content:
                failed.set()
                raise RuntimeError("private-value")

        instance = monitor.RuntimeMonitor("python", Path("repo"), publish, interval=1, runner=Mock(return_value=SimpleNamespace(stdout=json.dumps(snapshot()))))
        instance.start()
        self.assertTrue(failed.wait(2))
        instance.stop()
        self.assertFalse(instance._thread.is_alive())


class NotebookTests(unittest.TestCase):
    def setUp(self):
        notebook = json.loads((SOURCE / "notebooks/Gurumoji_Colab.ipynb").read_text(encoding="utf-8"))
        self.source = "".join(notebook["cells"][6]["source"])
        self.shutdown = "".join(notebook["cells"][7]["source"])

    def test_default_off_stops_a_previous_monitor_without_starting_anything(self):
        previous, factory = Mock(), Mock()
        namespace = {"gurumoji_runtime_monitor": previous}
        with patch.object(monitor, "start_runtime_monitor", factory), patch("sys.stdout", io.StringIO()):
            exec(self.source, namespace)
        previous.stop.assert_called_once()
        factory.assert_not_called()
        self.assertIsNone(namespace["gurumoji_runtime_monitor"])

    def test_enabling_and_rerunning_stops_previous_measurement_first(self):
        previous, current = Mock(), Mock()

        def start(*args, **kwargs):
            previous.stop.assert_called_once()
            return current

        namespace = {"gurumoji_runtime_monitor": previous, "COLAB_PYTHON": Path("environment/bin/python"), "REPO_DIR": Path("repo")}
        with patch.object(monitor, "start_runtime_monitor", Mock(side_effect=start)) as factory, patch("sys.stdout", io.StringIO()):
            exec(self.source.replace("ENABLE_RUNTIME_MONITOR = False", "ENABLE_RUNTIME_MONITOR = True"), namespace)
        factory.assert_called_once_with(namespace["COLAB_PYTHON"], namespace["REPO_DIR"], interval=2)
        self.assertIs(namespace["gurumoji_runtime_monitor"], current)

    def test_shutdown_stops_monitor_and_both_application_processes(self):
        instance = Mock()
        server = Mock(poll=Mock(return_value=None))
        ollama = Mock(poll=Mock(return_value=None))
        with patch("sys.stdout", io.StringIO()):
            exec(self.shutdown, {"gurumoji_runtime_monitor": instance, "gurumoji_server": server, "ollama_server": ollama})
        instance.stop.assert_called_once()
        server.terminate.assert_called_once()
        ollama.terminate.assert_called_once()

    def test_stop_button_stops_measurement_and_disables_itself(self):
        display = Mock()
        canvas = Mock()
        button = Mock()
        instance = Mock()
        instance.start.return_value = instance
        modules = {"IPython.display": SimpleNamespace(HTML=lambda value: value, display=display),
                   "ipywidgets": SimpleNamespace(HTML=Mock(return_value=canvas), Button=Mock(return_value=button), VBox=lambda values: values)}
        with patch.dict(sys.modules, modules), patch.object(monitor, "RuntimeMonitor", return_value=instance) as factory:
            self.assertIs(monitor.start_runtime_monitor("python", Path("repo")), instance)
        publish = factory.call_args.args[2]
        publish("updated monitor")
        self.assertEqual(canvas.value, "updated monitor")
        display.assert_called_once_with([canvas, button])
        callback = button.on_click.call_args.args[0]
        callback(button)
        instance.stop.assert_called_once()
        self.assertTrue(button.disabled)

    def test_missing_widgets_uses_the_display_handle_without_installing_packages(self):
        handle = Mock()
        display = Mock(return_value=handle)
        instance = Mock()
        instance.start.return_value = instance
        modules = {"IPython.display": SimpleNamespace(HTML=lambda value: value, display=display), "ipywidgets": None}
        with patch.dict(sys.modules, modules), patch.object(monitor, "RuntimeMonitor", return_value=instance) as factory:
            self.assertIs(monitor.start_runtime_monitor("python", Path("repo")), instance)
        factory.call_args.args[2]("updated monitor")
        handle.update.assert_called_once_with("updated monitor")


if __name__ == "__main__":
    unittest.main(verbosity=2)
