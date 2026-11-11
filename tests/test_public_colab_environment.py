"""公開版Colabの依存分離と、失敗・再実行時の準備状態を検証する。"""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock


SOURCE = Path(os.environ["GURUMOJI_COLAB_SOURCE"])
NOTEBOOK = json.loads((SOURCE / "notebooks/Gurumoji_Colab.ipynb").read_text(encoding="utf-8"))


def load_helper(**overrides):
    tree = ast.parse("".join(NOTEBOOK["cells"][1]["source"]))
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "prepare_colab_environment")
    namespace = dict(Path=Path, hashlib=hashlib, sys=sys, venv=Mock(), subprocess=Mock())
    namespace.update(overrides)
    exec(compile(ast.Module(body=[helper], type_ignores=[]), "colab-environment", "exec"), namespace)
    return namespace


class ColabEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        (self.repo / "config").mkdir(parents=True)
        self.requirements = self.repo / "config/requirements.txt"
        self.requirements.write_text("Flask>=3.1,<4\n", encoding="utf-8")
        self.environments = self.root / "environments"
        self.namespace = load_helper()
        self.namespace["venv"].EnvBuilder.return_value.create.side_effect = self.create_environment
        self.prepare = self.namespace["prepare_colab_environment"]

    def create_environment(self, directory):
        (directory / "bin").mkdir(parents=True, exist_ok=True)
        (directory / "bin/python").touch()

    def test_install_and_check_only_target_the_isolated_environment(self):
        target = self.prepare(self.repo, self.environments)
        self.namespace["venv"].EnvBuilder.assert_called_once_with(with_pip=False, system_site_packages=False)
        calls = self.namespace["subprocess"].run.call_args_list
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0].args[0][:5], [sys.executable, "-m", "pip", "--python", str(target)])
        for call in calls[1:]:
            self.assertEqual(call.args[0][0], str(target))
            self.assertTrue(call.kwargs["check"])
        self.assertIn("torch==2.8.0+cu128", calls[1].args[0])
        self.assertEqual(calls[-1].args[0][-2:], ["pip", "check"])
        self.assertTrue((target.parent.parent / ".setup-complete").exists())

    def test_cached_environment_is_checked_without_reinstall(self):
        target = self.prepare(self.repo, self.environments)
        self.namespace["subprocess"].reset_mock()
        self.namespace["venv"].reset_mock()
        self.assertEqual(self.prepare(self.repo, self.environments), target)
        self.namespace["venv"].EnvBuilder.assert_not_called()
        self.namespace["subprocess"].run.assert_called_once_with([str(target), "-m", "pip", "check"], check=True)

    def test_failed_install_is_not_marked_ready_and_can_retry(self):
        self.namespace["subprocess"].run.side_effect = [None, subprocess.CalledProcessError(1, "pip")]
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare(self.repo, self.environments)
        self.assertEqual(list(self.environments.glob("*/.setup-complete")), [])
        self.namespace["subprocess"].run.side_effect = None
        target = self.prepare(self.repo, self.environments)
        self.assertTrue((target.parent.parent / ".setup-complete").exists())

    def test_failed_cached_check_invalidates_readiness(self):
        target = self.prepare(self.repo, self.environments)
        self.namespace["subprocess"].run.side_effect = subprocess.CalledProcessError(1, "pip check")
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare(self.repo, self.environments)
        self.assertFalse((target.parent.parent / ".setup-complete").exists())

    def test_changed_requirements_select_a_new_environment(self):
        previous = self.prepare(self.repo, self.environments)
        self.requirements.write_text("Flask==3.1.3\n", encoding="utf-8")
        target = self.prepare(self.repo, self.environments)
        self.assertNotEqual(previous, target)
        self.assertTrue(previous.is_file())

    def test_changed_python_selects_a_new_environment(self):
        previous = self.prepare(self.repo, self.environments)
        self.namespace["sys"] = Mock(version=sys.version + "-different", executable=sys.executable)
        self.assertNotEqual(self.prepare(self.repo, self.environments), previous)

    def test_missing_python_recreates_cached_environment(self):
        target = self.prepare(self.repo, self.environments)
        target.unlink()
        self.namespace["subprocess"].reset_mock()
        self.prepare(self.repo, self.environments)
        self.assertEqual(self.namespace["subprocess"].run.call_count, 4)

    def test_failed_recreation_does_not_leave_the_old_ready_marker(self):
        target = self.prepare(self.repo, self.environments)
        target.unlink()
        self.namespace["subprocess"].run.side_effect = subprocess.CalledProcessError(1, "pip install")
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare(self.repo, self.environments)
        self.assertFalse((target.parent.parent / ".setup-complete").exists())
        self.namespace["subprocess"].run.side_effect = None
        self.namespace["subprocess"].reset_mock()
        self.prepare(self.repo, self.environments)
        self.assertEqual(self.namespace["subprocess"].run.call_count, 4)

    def test_shipped_cells_compile_and_launch_the_environment_python(self):
        for index, cell in enumerate(NOTEBOOK["cells"]):
            if cell["cell_type"] == "code":
                compile("".join(cell["source"]), f"colab-cell-{index}", "exec")
                self.assertFalse(cell["outputs"])
                self.assertIsNone(cell["execution_count"])
        tree = ast.parse("".join(NOTEBOOK["cells"][5]["source"]))
        launch = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Popen")
        target = self.root / "environment/bin/python"
        command = eval(compile(ast.Expression(launch.args[0]), "colab-launch", "eval"), {"COLAB_PYTHON": target})
        self.assertEqual(command, [str(target), "-m", "gurumoji.app"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
