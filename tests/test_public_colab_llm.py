"""資源別のモデル選択、直接指定、出荷セルの起動・保存境界を検証する。"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.error

SOURCE = Path(os.environ["GURUMOJI_COLAB_SOURCE"])
sys.path.insert(0, str(SOURCE / "src"))
from gurumoji import colab_llm
from gurumoji.colab_support import ColabSetupError, colab_step


def runtime(free=15, total=16, ram=12, cores=4):
    return {"ram_available_gib": ram, "cpu_count": cores, "gpu_detection": "detected",
            "gpus": [{"id": "GPU-synthetic", "name": "synthetic GPU", "free_gib": free, "total_gib": total}] if total else []}


class SelectionTests(unittest.TestCase):
    def test_colab_gpu_tiers_select_model_quantization_and_context(self):
        cases = ((runtime(), "qwen3:4b-instruct-2507-q4_K_M", 32768),
                 (runtime(23, 24, 24), "qwen3:4b-instruct-2507-q8_0", 32768),
                 (runtime(39, 40, 60), "qwen3:30b-a3b-instruct-2507-q4_K_M", 32768),
                 (runtime(79, 80, 80), "qwen3:30b-a3b-instruct-2507-q8_0", 32768))
        for resources, model, context in cases:
            with self.subTest(model=model):
                plan = colab_llm.select_colab_llm(resources)
                self.assertEqual(plan["model"], model)
                self.assertEqual(plan["context_length"], context)
                self.assertTrue(plan["automatic"])
                self.assertEqual(plan["cuda_visible_devices"], "GPU-synthetic")

    def test_occupied_large_gpu_selects_a_smaller_model_from_free_memory(self):
        plan = colab_llm.select_colab_llm(runtime(19, 80, 80))
        self.assertEqual(plan["model"], "qwen3:4b-instruct-2507-q4_K_M")
        self.assertEqual(plan["gpu_reserve_gib"], 8)

    def test_low_host_ram_prevents_a_large_gpu_model(self):
        plan = colab_llm.select_colab_llm(runtime(79, 80, 7))
        self.assertEqual(plan["model"], "qwen3:4b-instruct-2507-q4_K_M")

    def test_cpu_and_small_gpu_choose_lightweight_profiles(self):
        cases = ((runtime(0, 0, 12), "qwen2.5:3b-instruct", 32768),
                 (runtime(0, 0, 4), "qwen2.5:1.5b-instruct", 32768),
                 (runtime(9, 10, 8), "qwen2.5:3b-instruct", 32768),
                 (runtime(7, 8, 4), "qwen2.5:1.5b-instruct", 32768))
        for resources, model, context in cases:
            with self.subTest(resources=resources):
                plan = colab_llm.select_colab_llm(resources)
                self.assertEqual((plan["model"], plan["context_length"]), (model, context))

    def test_cpu_fallback_does_not_take_the_reserved_gpu_capacity(self):
        plan = colab_llm.select_colab_llm(runtime(3, 16, 12))
        self.assertEqual(plan["cuda_visible_devices"], "-1")

    def test_multiple_gpus_are_not_added_together(self):
        resources = runtime(15, 16, 80)
        resources["gpus"].append({"id": "GPU-other", "name": "other", "free_gib": 14, "total_gib": 16})
        plan = colab_llm.select_colab_llm(resources)
        self.assertEqual(plan["model"], "qwen3:4b-instruct-2507-q4_K_M")
        self.assertEqual(plan["cuda_visible_devices"], "GPU-synthetic")

    def test_missing_detection_data_is_conservative_and_not_reported_as_verified(self):
        resources = runtime(0, 0, None)
        resources["gpu_detection"] = "unavailable"
        plan = colab_llm.select_colab_llm(resources)
        self.assertEqual(plan["model"], "qwen2.5:1.5b-instruct")
        self.assertIsNone(plan["cuda_visible_devices"])
        self.assertIn("未確認", plan["reason"])

    def test_explicit_custom_model_and_context_always_take_precedence(self):
        plan = colab_llm.select_colab_llm(runtime(), "hf.co/team/custom-model:Q4_K_M", 8192)
        self.assertEqual(plan["model"], "hf.co/team/custom-model:Q4_K_M")
        self.assertEqual(plan["context_length"], 8192)
        self.assertFalse(plan["automatic"])

    def test_model_without_a_tag_is_normalized_for_catalog_and_running_model_matches(self):
        plan = colab_llm.select_colab_llm(runtime(), " custom/model ")
        self.assertEqual(plan["model"], "custom/model:latest")
        self.assertTrue(colab_llm.ollama_model_matches("custom/model", plan["model"]))
        self.assertFalse(colab_llm.ollama_model_matches(None, plan["model"]))
        self.assertFalse(colab_llm.ollama_model_matches("other:latest", plan["model"]))

    def test_auto_aliases_and_context_override(self):
        for value in ("auto", "", " AUTO "):
            self.assertEqual(colab_llm.select_colab_llm(runtime(), value, 4096)["context_length"], 4096)

    def test_invalid_model_inputs_and_cloud_models_are_rejected(self):
        for value in ("--help", "name other", "https://example.invalid/model", "../model", "model\nother", "model;command", "model:cloud", "model:large-cloud", None):
            with self.subTest(value=value), self.assertRaises(ColabSetupError) as caught:
                colab_llm.select_colab_llm(runtime(), value)
            self.assertEqual(caught.exception.code, "LLM_MODEL")

    def test_invalid_contexts_are_rejected(self):
        for value in (True, 2048, 32769, "8192", -1):
            with self.subTest(value=value), self.assertRaises(ColabSetupError) as caught:
                colab_llm.select_colab_llm(runtime(), "auto", value)
            self.assertEqual(caught.exception.code, "LLM_CONTEXT")

    def test_insufficient_cpu_ram_blocks_auto_but_does_not_rewrite_explicit_models(self):
        with self.assertRaises(ColabSetupError) as caught:
            colab_llm.select_colab_llm(runtime(0, 0, 2))
        self.assertEqual(caught.exception.code, "LLM_MEMORY")
        self.assertEqual(colab_llm.select_colab_llm(runtime(0, 0, 2), "custom:small")["model"], "custom:small")


class DetectionTests(unittest.TestCase):
    def detect(self, output, environ=None):
        with tempfile.TemporaryDirectory() as temporary:
            memory_file = Path(temporary) / "meminfo"
            memory_file.write_text("MemTotal: 33554432 kB\nMemAvailable: 12582912 kB\n", encoding="utf-8")
            run = Mock(return_value=SimpleNamespace(stdout=output))
            result = colab_llm.detect_colab_llm_runtime(runner=run, meminfo_path=memory_file, environ=environ or {})
        return result, run

    def test_reads_ram_and_gpu_free_capacity_in_gib(self):
        resources, run = self.detect('0, GPU-first, NVIDIA T4, 16384, 15360\n')
        self.assertEqual(resources["ram_available_gib"], 12)
        self.assertEqual(resources["gpus"][0]["free_gib"], 15)
        self.assertEqual(run.call_args.kwargs["timeout"], 10)

    def test_cuda_visibility_is_respected_by_index_or_uuid(self):
        output = '0, GPU-first, NVIDIA T4, 16384, 15360\n1, GPU-second, NVIDIA A100, 81920, 80896\n'
        for value in ("0", "GPU-first"):
            with self.subTest(value=value):
                resources, _ = self.detect(output, {"CUDA_VISIBLE_DEVICES": value})
                self.assertEqual([gpu["id"] for gpu in resources["gpus"]], ["GPU-first"])

    def test_explicit_cpu_mode_does_not_query_nvidia(self):
        for value in ("", "-1"):
            resources, run = self.detect('', {"CUDA_VISIBLE_DEVICES": value})
            self.assertFalse(resources["gpus"])
            self.assertEqual(resources["gpu_detection"], "disabled")
            run.assert_not_called()

    def test_malformed_gpu_rows_are_ignored(self):
        resources, _ = self.detect('bad row\n0, GPU-a, T4, N/A, 12\n1, GPU-b, T4, 10, 20\n2, GPU-c, T4, inf, inf\n')
        self.assertFalse(resources["gpus"])

    def test_detection_failure_is_not_fabricated_as_a_large_gpu(self):
        resources = colab_llm.detect_colab_llm_runtime(runner=Mock(side_effect=FileNotFoundError), meminfo_path=Path("synthetic-missing-meminfo"), environ={})
        self.assertEqual(resources["gpu_detection"], "unavailable")
        self.assertIsNone(resources["ram_available_gib"])
        self.assertFalse(resources["gpus"])


class ShippedLlmCellTests(unittest.TestCase):
    def execute_cell(self, *, model="auto", context=0, enabled=True, failed_json=False, small_context=False, unsupported=False, small_native_context=False, low_memory=False):
        notebook = json.loads((SOURCE / "notebooks/Gurumoji_Colab.ipynb").read_text(encoding="utf-8"))
        source = "".join(notebook["cells"][4]["source"])
        source = source.replace('LOCAL_LLM_MODEL = "auto"', f'LOCAL_LLM_MODEL = {model!r}')
        source = source.replace('LOCAL_LLM_CONTEXT_LENGTH = 0', f'LOCAL_LLM_CONTEXT_LENGTH = {context!r}')
        source = source.replace('USE_LOCAL_LLM = True', f'USE_LOCAL_LLM = {enabled!r}')
        resources = runtime()
        plan = colab_llm.select_colab_llm(resources, model, context)
        requests = []

        def urlopen(request, **kwargs):
            url = request if isinstance(request, str) else request.full_url
            if url.endswith('/api/tags'):
                response = {"models": []}
            elif url.endswith('/v1/models'):
                response = {"data": [{"id": plan["model"]}]}
            elif url.endswith('/api/show'):
                response = {"capabilities": ["embedding"] if unsupported else ["completion"],
                            "model_info": {"general.architecture": "synthetic", "synthetic.context_length": 1024 if small_native_context else 131072}}
            elif url.endswith('/v1/chat/completions'):
                if low_memory:
                    raise urllib.error.HTTPError(url, 500, "synthetic failure", {}, io.BytesIO(b'{"error":"model requires more system memory: private-value"}'))
                requests.append(json.loads(request.data))
                response = {"choices": [{"finish_reason": "length" if failed_json else "stop", "message": {"content": '{"status":"ready"}'}}]}
            elif url.endswith('/api/ps'):
                response = {"models": [{"name": plan["model"], "context_length": 1024 if small_context else plan["context_length"], "size_vram": 1234}]}
            else:
                raise AssertionError(url)
            return io.BytesIO(json.dumps(response).encode())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token_path = root / "tokens.json"
            original = {"lmstudio_model": "previous-model"}
            token_path.write_text(json.dumps(original), encoding="utf-8")
            process = SimpleNamespace(run=Mock(), Popen=Mock(return_value=Mock(poll=Mock(return_value=None))), STDOUT=subprocess.STDOUT)
            paths = lambda value: root / str(value).removeprefix('/content/')
            namespace = dict(Path=paths, json=json, os=os, subprocess=process, storage_root=root,
                             token_path=token_path, tokens=original.copy(), colab_step=colab_step, ColabSetupError=ColabSetupError)
            detector = Mock(return_value=resources)
            error = None
            try:
                with patch.object(colab_llm, "detect_colab_llm_runtime", detector), patch('shutil.which', return_value='/synthetic/ollama'), patch('urllib.request.urlopen', side_effect=urlopen), patch('sys.stdout', io.StringIO()):
                    exec(compile(source, "colab-llm-cell", "exec"), namespace)
            except ColabSetupError as exc:
                error = exc
            finally:
                if "ollama_log" in namespace:
                    namespace["ollama_log"].close()
            saved = json.loads(token_path.read_text(encoding="utf-8"))
        return namespace, process, detector, requests, saved, error

    def test_auto_selection_is_used_for_pull_service_context_and_saved_model(self):
        namespace, process, detector, requests, saved, error = self.execute_cell()
        self.assertIsNone(error)
        self.assertEqual(namespace["LOCAL_LLM_MODEL"], "qwen3:4b-instruct-2507-q4_K_M")
        process.run.assert_called_once()
        self.assertEqual(process.run.call_args.args[0], ["ollama", "pull", namespace["LOCAL_LLM_MODEL"]])
        environment = process.Popen.call_args.kwargs["env"]
        self.assertEqual(environment["OLLAMA_CONTEXT_LENGTH"], "32768")
        self.assertEqual(environment["CUDA_VISIBLE_DEVICES"], "GPU-synthetic")
        self.assertEqual(environment["OLLAMA_NO_CLOUD"], "1")
        self.assertEqual(saved["lmstudio_model"], namespace["LOCAL_LLM_MODEL"])
        self.assertEqual(requests[0]["response_format"]["type"], "json_schema")

    def test_custom_model_and_context_reach_the_warmup_and_config_unchanged(self):
        namespace, process, detector, requests, saved, error = self.execute_cell(model="team/custom:Q4_K_M", context=8192)
        self.assertIsNone(error)
        self.assertEqual(requests[0]["model"], "team/custom:Q4_K_M")
        self.assertEqual(saved["lmstudio_model"], "team/custom:Q4_K_M")
        self.assertEqual(namespace["LOCAL_LLM_READY"]["context_length"], 8192)

    def test_failed_json_or_context_does_not_change_the_model_or_save_readiness(self):
        for failure in ({"failed_json": True}, {"small_context": True}):
            with self.subTest(failure=failure):
                namespace, process, detector, requests, saved, error = self.execute_cell(model="team/custom:Q4", **failure)
                self.assertIsNotNone(error)
                self.assertIsNone(namespace["LOCAL_LLM_READY"])
                self.assertEqual(namespace["LOCAL_LLM_MODEL"], "team/custom:Q4")
                self.assertEqual(saved["lmstudio_model"], "previous-model")
                self.assertEqual(process.run.call_count, 1)

    def test_disabled_llm_does_not_detect_hardware_download_or_launch(self):
        namespace, process, detector, requests, saved, error = self.execute_cell(enabled=False)
        self.assertIsNone(error)
        detector.assert_not_called()
        process.run.assert_not_called()
        process.Popen.assert_not_called()
        self.assertEqual(saved["lmstudio_model"], "")

    def test_embedding_models_and_excessive_native_context_stop_before_warmup(self):
        for failure, code in (({"unsupported": True}, "LLM_MODEL"), ({"small_native_context": True}, "LLM_CONTEXT")):
            with self.subTest(failure=failure):
                namespace, process, detector, requests, saved, error = self.execute_cell(model="team/custom:Q4", **failure)
                self.assertEqual(error.code, code)
                self.assertFalse(requests)
                self.assertEqual(saved["lmstudio_model"], "previous-model")

    def test_memory_load_failure_is_explained_without_switching_models_or_echoing_the_body(self):
        namespace, process, detector, requests, saved, error = self.execute_cell(model="team/custom:Q4", low_memory=True)
        self.assertEqual(error.code, "LLM_MEMORY")
        self.assertNotIn("private-value", str(error))
        self.assertEqual(namespace["LOCAL_LLM_MODEL"], "team/custom:Q4")
        self.assertIsNone(namespace["LOCAL_LLM_READY"])
        self.assertEqual(saved["lmstudio_model"], "previous-model")


if __name__ == "__main__":
    unittest.main(verbosity=2)
