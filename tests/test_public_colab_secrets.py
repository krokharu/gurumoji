"""シークレットの優先順位・既存設定保護・安全なエラー分類を検証する。"""
import errno
import io
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.error

from public_colab_source import public_source, load_public_module

SOURCE = public_source("src/gurumoji/colab_support.py", "notebooks/Gurumoji_Colab.ipynb")
support = load_public_module(SOURCE, "colab_support")


class SecretNotFoundError(Exception):
    pass


class NotebookAccessError(Exception):
    pass


class TimeoutException(Exception):
    pass


def userdata(values=None, error=None):
    values = values or {}

    def get(name):
        if error:
            raise error
        if name not in values:
            raise SecretNotFoundError(name)
        return values[name]

    return SimpleNamespace(get=Mock(side_effect=get), SecretNotFoundError=SecretNotFoundError,
                           NotebookAccessError=NotebookAccessError, TimeoutException=TimeoutException)


class ColabSecretsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "tokens.json"

    def test_reads_all_supported_secrets_without_displaying_the_values(self):
        values = {"HF_TOKEN": "synthetic-hf-value", "OPENAI_API_KEY": "synthetic-openai-value",
                  "GOOGLE_API_KEY": "synthetic-google-value", "TYPESAFE_API_KEY": "synthetic-typesafe-value"}
        output = io.StringIO()
        with patch("sys.stdout", output):
            tokens, sources = support.load_colab_tokens(self.path, userdata(values))
        self.assertEqual(tokens["huggingface_token"], values["HF_TOKEN"])
        self.assertEqual(tokens["openai_api_key"], values["OPENAI_API_KEY"])
        self.assertEqual(tokens["google_api_key"], values["GOOGLE_API_KEY"])
        self.assertEqual(tokens["typesafe_api_key"], values["TYPESAFE_API_KEY"])
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), tokens)
        for value in values.values():
            self.assertNotIn(value, str(sources))
            self.assertNotIn(value, output.getvalue())

    def test_aliases_and_whitespace(self):
        tokens, _ = support.load_colab_tokens(self.path, userdata({"HUGGINGFACE_TOKEN": "  synthetic-hf  ", "GEMINI_API_KEY": " synthetic-gemini "}))
        self.assertEqual(tokens["huggingface_token"], "synthetic-hf")
        self.assertEqual(tokens["google_api_key"], "synthetic-gemini")
        self.assertEqual(tokens["openai_api_key"], "")

    def test_primary_name_takes_precedence_over_alias(self):
        value, _ = support.read_colab_secret(userdata({"HF_TOKEN": "primary", "HUGGINGFACE_TOKEN": "alias"}), ("HF_TOKEN", "HUGGINGFACE_TOKEN"))
        self.assertEqual(value, "primary")

    def test_missing_secrets_preserve_existing_credentials_and_unknown_settings(self):
        original = {"huggingface_token": "existing-hf", "openai_api_key": "existing-openai", "lmstudio_base_url": "http://127.0.0.1:11434/v1", "google_model": "existing-model"}
        self.path.write_text(json.dumps(original), encoding="utf-8")
        tokens, sources = support.load_colab_tokens(self.path, userdata())
        for key, value in original.items():
            self.assertEqual(tokens[key], value)
        self.assertEqual(sources["HF_TOKEN"], "既存設定")

    def test_missing_required_secret_does_not_create_a_file(self):
        with self.assertRaises(support.ColabSetupError) as caught:
            support.load_colab_tokens(self.path, userdata())
        self.assertEqual(caught.exception.code, "SECRET_MISSING")
        self.assertIn(support.HF_TOKEN_URL, str(caught.exception))
        self.assertFalse(self.path.exists())

    def test_denied_access_cannot_silently_fall_back_to_an_old_key(self):
        with self.assertRaises(support.ColabSetupError) as caught:
            support.read_colab_secret(userdata(error=NotebookAccessError("private-value")), ("HF_TOKEN",), current="old-key")
        self.assertEqual(caught.exception.code, "SECRET_ACCESS")
        self.assertNotIn("private-value", str(caught.exception))
        self.assertNotIn("old-key", str(caught.exception))

    def test_timeout_and_unknown_secret_errors_do_not_echo_the_original_exception(self):
        for error, code in ((TimeoutException("private-value"), "SECRET_TIMEOUT"), (RuntimeError("private-value"), "SECRET_READ")):
            with self.subTest(code=code), self.assertRaises(support.ColabSetupError) as caught:
                support.read_colab_secret(userdata(error=error), ("HF_TOKEN",))
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn("private-value", str(caught.exception))

    def test_corrupt_existing_config_is_not_overwritten(self):
        for original in ("invalid config", "[]"):
            self.path.write_text(original, encoding="utf-8")
            with self.assertRaises(support.ColabSetupError) as caught:
                support.load_colab_tokens(self.path, userdata({"HF_TOKEN": "new-value"}))
            self.assertEqual(caught.exception.code, "TOKEN_FILE")
            self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_late_secret_failure_does_not_partially_update_the_config(self):
        original = '{"huggingface_token":"existing-hf"}'
        self.path.write_text(original, encoding="utf-8")
        source = userdata({"HF_TOKEN": "new-hf"})
        source.get.side_effect = ["new-hf", NotebookAccessError("private-value")]
        with self.assertRaises(support.ColabSetupError):
            support.load_colab_tokens(self.path, source)
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_manual_input_is_explicit_and_does_not_read_colab_secrets(self):
        source = userdata(error=RuntimeError("should not read"))
        tokens, _ = support.load_colab_tokens(self.path, source, manual_input=Mock(side_effect=["manual-hf", "", "", ""]))
        self.assertEqual(tokens["huggingface_token"], "manual-hf")
        source.get.assert_not_called()

    def test_write_failure_is_reported_without_private_paths_or_values(self):
        with patch.object(support, "atomic_write_text", side_effect=PermissionError("private-value")), self.assertRaises(support.ColabSetupError) as caught:
            support.load_colab_tokens(self.path, userdata({"HF_TOKEN": "private-hf"}))
        self.assertEqual(caught.exception.code, "TOKEN_WRITE")
        self.assertNotIn("private", str(caught.exception))


class ColabDiagnosticTests(unittest.TestCase):
    def test_runtime_api_errors_direct_colab_users_to_the_secrets_sidebar(self):
        from gurumoji.services.ai.client import http_error_message
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}):
            self.assertIn("シークレット", http_error_message(401))
            self.assertIn("セル2", http_error_message(401))
        self.assertIn("残高", http_error_message(429))
        self.assertIn("課金設定", http_error_message(429))

    def test_runtime_diarization_errors_include_the_token_and_model_links(self):
        from gurumoji.services.transcription.diarization import diarization_access_error_message
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}):
            message = diarization_access_error_message("synthetic-model")
        self.assertIn("HF_TOKEN", message)
        self.assertIn("セル2", message)
        self.assertIn(support.HF_TOKEN_URL, message)
        self.assertIn("https://huggingface.co/pyannote/speaker-diarization-community-1", message)

    def test_http_classes_are_distinct_and_never_echo_response_bodies(self):
        for status, code in ((400, "REQUEST_400"), (401, "AUTH_401"), (403, "PERMISSION_403"), (404, "MODEL_404"), (429, "LIMIT_429"), (503, "SERVICE_5XX")):
            with self.subTest(status=status):
                error = urllib.error.HTTPError("https://example.invalid/private-value", status, "private-value", {}, None)
                diagnostic = support.diagnose_colab_error(error, "HUGGINGFACE")
                self.assertEqual(diagnostic.code, code)
                self.assertNotIn("private-value", str(diagnostic))

    def test_runtime_errors_have_actionable_categories(self):
        cases = ((ssl.SSLError("private-value"), "TLS"), (TimeoutError("private-value"), "TIMEOUT"),
                 (urllib.error.URLError(TimeoutError("private-value")), "TIMEOUT"),
                 (urllib.error.URLError("private-value"), "NETWORK"),
                 (OSError(errno.ENOSPC, "private-value"), "DISK_FULL"),
                 (RuntimeError("CUDA out of memory: private-value"), "GPU_MEMORY"),
                 (RuntimeError("CUDA driver private-value"), "GPU_RUNTIME"))
        for error, code in cases:
            with self.subTest(code=code):
                diagnostic = support.diagnose_colab_error(error, "APP_START")
                self.assertEqual(diagnostic.code, code)
                self.assertNotIn("private-value", str(diagnostic))

    def test_unknown_errors_use_the_current_step(self):
        for stage, code in (("ENVIRONMENT", "ENVIRONMENT"), ("DRIVE", "DRIVE"), ("LOCAL_LLM", "LOCAL_LLM"), ("SECRETS", "SECRET_READ"), ("HUGGINGFACE", "HF_CHECK"), ("APP_START", "APP_START")):
            with self.subTest(stage=stage):
                self.assertEqual(support.diagnose_colab_error(RuntimeError("private-value"), stage).code, code)

    def test_context_preserves_known_codes_and_suppresses_raw_exception_chains(self):
        with self.assertRaises(support.ColabSetupError) as caught:
            with support.colab_step("APP_START"):
                raise RuntimeError("private-value")
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertNotIn("private-value", str(caught.exception))
        known = support.ColabSetupError("SECRET_ACCESS", "safe message")
        self.assertIs(support.diagnose_colab_error(known, "SECRETS"), known)

    def test_subprocess_failures_are_classified_by_stage(self):
        error = subprocess.CalledProcessError(1, ["private-value"])
        self.assertEqual(support.diagnose_colab_error(error, "ENVIRONMENT").code, "ENVIRONMENT")
        self.assertEqual(support.diagnose_colab_error(error, "LOCAL_LLM").code, "LOCAL_LLM")


class HuggingFaceCheckTests(unittest.TestCase):
    def setUp(self):
        module = SimpleNamespace(HfApi=Mock(), get_hf_file_metadata=Mock(), hf_hub_url=lambda model, filename: f"https://huggingface.co/{model}/resolve/main/{filename}")
        self.module_patch = patch.dict(sys.modules, {"huggingface_hub": module})
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.api = Mock()
        self.metadata = Mock()

    def test_only_checks_authentication_and_the_active_model_metadata(self):
        support.check_huggingface_access("synthetic-value", api=self.api, metadata=self.metadata)
        self.api.whoami.assert_called_once_with(token="synthetic-value")
        self.metadata.assert_called_once_with("https://huggingface.co/pyannote/speaker-diarization-community-1/resolve/main/config.yaml", token="synthetic-value", timeout=15)

    def test_invalid_authentication_stops_before_model_access(self):
        self.api.whoami.side_effect = urllib.error.HTTPError("private-url", 401, "private-value", {}, None)
        with self.assertRaises(support.ColabSetupError) as caught:
            support.check_huggingface_access("synthetic-value", api=self.api, metadata=self.metadata)
        self.assertEqual(caught.exception.code, "AUTH_401")
        self.metadata.assert_not_called()

    def test_missing_agreement_provides_the_model_and_token_links(self):
        self.metadata.side_effect = urllib.error.HTTPError("private-url", 403, "private-value", {}, None)
        with self.assertRaises(support.ColabSetupError) as caught:
            support.check_huggingface_access("synthetic-value", api=self.api, metadata=self.metadata)
        self.assertEqual(caught.exception.code, "PERMISSION_403")
        self.assertIn("https://huggingface.co/pyannote/speaker-diarization-community-1", str(caught.exception))
        self.assertIn(support.HF_TOKEN_URL, str(caught.exception))
        self.assertNotIn("private-value", str(caught.exception))

    def test_cli_failure_never_prints_the_token_or_original_exception(self):
        with tempfile.TemporaryDirectory() as temporary:
            token_file = Path(temporary) / "tokens.json"
            token_file.write_text('{"huggingface_token":"synthetic-private-value"}', encoding="utf-8")
            output = io.StringIO()
            with patch.object(sys, "argv", ["colab_support", str(token_file)]), patch.object(support, "check_huggingface_access", side_effect=RuntimeError("synthetic-private-value")), patch("sys.stdout", output):
                self.assertEqual(support.main(), 1)
            self.assertIn("HF_CHECK", output.getvalue())
            self.assertNotIn("synthetic-private-value", output.getvalue())


class ShippedSecretCellTests(unittest.TestCase):
    def test_secret_cell_uses_the_sidebar_and_passes_no_keys_on_the_command_line(self):
        notebook = json.loads((SOURCE / "notebooks/Gurumoji_Colab.ipynb").read_text(encoding="utf-8"))
        source = "".join(notebook["cells"][2]["source"])
        secret_module = SimpleNamespace(userdata=userdata({"HF_TOKEN": "synthetic-hf", "OPENAI_API_KEY": "synthetic-openai"}))
        process = Mock(run=Mock(return_value=SimpleNamespace(returncode=0)))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config").mkdir()
            namespace = dict(REPO_DIR=root, COLAB_PYTHON=root / "environment/bin/python", os=os, subprocess=process,
                             load_colab_tokens=support.load_colab_tokens, colab_step=support.colab_step, ColabSetupError=support.ColabSetupError)
            output = io.StringIO()
            with patch.dict(sys.modules, {"google.colab": secret_module}), patch("sys.stdout", output):
                exec(compile(source, "colab-secret-cell", "exec"), namespace)
            call = process.run.call_args
            self.assertEqual(call.args[0][:3], [str(namespace["COLAB_PYTHON"]), "-m", "gurumoji.colab_support"])
            self.assertNotIn("synthetic-hf", str(call))
            self.assertNotIn("synthetic-openai", str(call))
            self.assertNotIn("synthetic-hf", output.getvalue())
            self.assertNotIn("synthetic-openai", output.getvalue())
            self.assertIn("シークレット HF_TOKEN", output.getvalue())

    def test_secret_cell_stops_when_the_preflight_fails(self):
        notebook = json.loads((SOURCE / "notebooks/Gurumoji_Colab.ipynb").read_text(encoding="utf-8"))
        source = "".join(notebook["cells"][2]["source"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config").mkdir()
            namespace = dict(REPO_DIR=root, COLAB_PYTHON=root / "environment/bin/python", os=os,
                             subprocess=Mock(run=Mock(return_value=SimpleNamespace(returncode=1))),
                             load_colab_tokens=support.load_colab_tokens, colab_step=support.colab_step, ColabSetupError=support.ColabSetupError)
            with patch.dict(sys.modules, {"google.colab": SimpleNamespace(userdata=userdata({"HF_TOKEN": "synthetic-hf"}))}), patch("sys.stdout", io.StringIO()), self.assertRaises(support.ColabSetupError) as caught:
                exec(compile(source, "colab-secret-cell", "exec"), namespace)
            self.assertEqual(caught.exception.code, "HF_CHECK_FAILED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
