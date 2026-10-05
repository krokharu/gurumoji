import ast
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import app


def notebook_functions(cell_index, names, **namespace):
    """Execute the shipped helper functions without setup, secrets or network."""
    notebook_path = Path(app.PROJECT_DIRECTORY) / "notebooks" / "Gurumoji_Colab.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    source = "".join(notebook["cells"][cell_index]["source"])
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in functions} != set(names):
        raise AssertionError("Notebook helpers are missing")
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(notebook_path), "exec"), namespace)
    return namespace


class ColabNotebookTests(unittest.TestCase):
    def test_all_code_cells_compile_without_saved_output_or_execution(self):
        path = Path(app.PROJECT_DIRECTORY) / "notebooks" / "Gurumoji_Colab.ipynb"
        notebook = json.loads(path.read_text(encoding="utf-8"))
        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] == "code":
                compile("".join(cell["source"]), f"colab-cell-{index}", "exec")
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])

    def test_running_app_blocks_git_changes(self):
        git = Mock()
        functions = notebook_functions(1, ["prepare_colab_repository"], subprocess=git)
        with self.assertRaisesRegex(RuntimeError, "実行中"):
            functions["prepare_colab_repository"](Path("synthetic"), "synthetic-url", [Mock(poll=lambda: None)])
        git.run.assert_not_called()
        git.check_output.assert_not_called()

    def test_local_edits_or_other_branch_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            for branch, changes in [("main", " M notebook.py"), ("experiment", ""), ("", "")]:
                with self.subTest(branch=branch, changes=changes):
                    git = Mock(check_output=Mock(side_effect=[branch, changes]))
                    function = notebook_functions(1, ["prepare_colab_repository"], subprocess=git)["prepare_colab_repository"]
                    with self.assertRaisesRegex(RuntimeError, "保全"):
                        function(root, "synthetic-url")
                    git.run.assert_not_called()

    def test_clean_main_updates_and_reports_actual_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            git = Mock(check_output=Mock(side_effect=["main\n", "", "synthetic-commit\n"]))
            function = notebook_functions(1, ["prepare_colab_repository"], subprocess=git)["prepare_colab_repository"]
            self.assertEqual(function(root, "synthetic-url"), "synthetic-commit")
            git.run.assert_called_once_with(["git", "-C", str(root), "pull", "--ff-only", "origin", "main"], check=True)

    def test_inference_and_loaded_context_are_verified_before_ready(self):
        import urllib.request
        response = {"choices": [{"finish_reason": "stop", "message": {"content": '{"status":"ready"}'}}]}
        running = {"models": [{"name": "synthetic-model", "context_length": 32768, "size_vram": 1234}]}
        replies = [io.BytesIO(json.dumps(value).encode()) for value in [response, running]]
        functions = notebook_functions(4, ["ollama_json", "verify_colab_local_llm"], json=json, urllib=__import__("urllib"))
        with patch.object(urllib.request, "urlopen", side_effect=replies) as transport:
            result = functions["verify_colab_local_llm"]("synthetic-model", 32768)
        self.assertEqual(result, {"model": "synthetic-model", "context_length": 32768, "size_vram": 1234})
        requests = [call.args[0] for call in transport.call_args_list]
        self.assertEqual([r.full_url for r in requests], ["http://127.0.0.1:11434/v1/chat/completions", "http://127.0.0.1:11434/api/ps"])
        self.assertEqual(json.loads(requests[0].data)["response_format"]["type"], "json_schema")

    def test_invalid_or_truncated_inference_cannot_pass(self):
        for choice in [{"finish_reason": "length", "message": {"content": '{"status":"ready"}'}},
                       {"finish_reason": "stop", "message": {"content": 'not json'}},
                       {"finish_reason": "stop", "message": {"content": '{"status":"wrong"}'}}]:
            with self.subTest(choice=choice):
                transport = Mock(return_value={"choices": [choice]})
                function = notebook_functions(4, ["verify_colab_local_llm"], json=json, ollama_json=transport)["verify_colab_local_llm"]
                with self.assertRaisesRegex(RuntimeError, "JSON推論"):
                    function("synthetic-model", 32768)
                self.assertEqual(transport.call_count, 1)

    def test_missing_model_or_small_unknown_context_cannot_pass(self):
        valid = {"choices": [{"finish_reason": "stop", "message": {"content": '{"status":"ready"}'}}]}
        for loaded in [[], [{"name": "other", "context_length": 32768}],
                       [{"name": "synthetic-model", "context_length": 4096}],
                       [{"name": "synthetic-model"}]]:
            with self.subTest(loaded=loaded):
                transport = Mock(side_effect=[valid, {"models": loaded}])
                function = notebook_functions(4, ["verify_colab_local_llm"], json=json, ollama_json=transport)["verify_colab_local_llm"]
                with self.assertRaises(RuntimeError):
                    function("synthetic-model", 32768)

    def test_cpu_or_unknown_gpu_allocation_is_not_invented(self):
        valid = {"choices": [{"finish_reason": "stop", "message": {"content": '{"status":"ready"}'}}]}
        for fields, expected in [({"size_vram": 0}, 0), ({}, None)]:
            with self.subTest(fields=fields):
                transport = Mock(side_effect=[valid, {"models": [{"name": "synthetic-model", "context_length": 32768, **fields}]}])
                function = notebook_functions(4, ["verify_colab_local_llm"], json=json, ollama_json=transport)["verify_colab_local_llm"]
                self.assertEqual(function("synthetic-model", 32768)["size_vram"], expected)


class ColabRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_detects_colab_and_disables_native_dialog(self):
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False):
            runtime = app.runtime_info()

        self.assertEqual(runtime["kind"], "colab")
        self.assertTrue(runtime["browser_upload"])
        self.assertFalse(runtime["native_file_dialog"])

    def test_colab_page_uses_browser_file_picker(self):
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-picker-mode="browser"', response.data)
        self.assertIn("端末からアップロード".encode(), response.data)
        self.assertIn("Ollama（ColabローカルLLM）".encode(), response.data)

    def test_colab_config_identifies_ollama_local_provider(self):
        with (
            patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False),
            patch.object(app, "lmstudio_connection_status", return_value={
                "reachable": True,
                "model_count": 1,
                "message": "接続済み",
            }),
        ):
            response = self.client.get("/api/config")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["local_llm_short_label"], "Ollama")
        self.assertEqual(payload["local_llm_label"], "Ollama（ColabローカルLLM）")

    def test_notebook_can_select_and_start_a_colab_local_llm(self):
        notebook_path = Path(app.PROJECT_DIRECTORY) / "notebooks" / "Gurumoji_Colab.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        source = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
        )

        self.assertIn('LOCAL_LLM_MODEL = "qwen3:4b-instruct"', source)
        self.assertIn('["ollama", "serve"]', source)
        self.assertIn('["ollama", "pull", LOCAL_LLM_MODEL]', source)
        self.assertIn('"http://127.0.0.1:11434/v1"', source)

    def test_native_dialog_endpoint_directs_colab_to_upload(self):
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False):
            response = self.client.post("/api/select-input")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.get_json()["browser_upload_only"])

    def test_colab_page_allows_only_colab_frame_ancestors(self):
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-Frame-Options", response.headers)
        policy = response.headers["Content-Security-Policy"]
        self.assertIn("frame-ancestors https://colab.research.google.com", policy)
        self.assertIn("https://*.research.google.com", policy)

    def test_colab_loopback_proxy_may_rewrite_host_but_not_bypass_cross_site_guard(self):
        headers = {"Host": "random-tunnel.example"}
        environ = {"REMOTE_ADDR": "127.0.0.1"}
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False):
            page = self.client.get("/", headers=headers, environ_overrides=environ)
            cross_site = self.client.get(
                "/api/config",
                headers={**headers, "Sec-Fetch-Site": "cross-site"},
                environ_overrides=environ,
            )

        self.assertEqual(page.status_code, 200)
        self.assertEqual(cross_site.status_code, 403)


if __name__ == "__main__":
    unittest.main()
