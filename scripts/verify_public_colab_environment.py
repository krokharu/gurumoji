"""公開版ノートブックの専用環境を実際に導入し、隔離状態と画面応答を検査する。"""
import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv


parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path)
parser.add_argument("--evidence", required=True, type=Path)
parser.add_argument("--environment-root", required=True, type=Path)
args = parser.parse_args()
notebook = json.loads((args.source / "notebooks/Gurumoji_Colab.ipynb").read_text(encoding="utf-8"))
tree = ast.parse("".join(notebook["cells"][1]["source"]))
helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "prepare_colab_environment")
namespace = dict(Path=Path, hashlib=hashlib, sys=sys, venv=venv, subprocess=subprocess)
exec(compile(ast.Module(body=[helper], type_ignores=[]), "colab-environment", "exec"), namespace)
before = {name: importlib.metadata.version(name) for name in ("gradio", "huggingface-hub", "numpy")}
subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
target = namespace["prepare_colab_environment"](args.source, args.environment_root)
assert target != Path(sys.executable)
assert namespace["prepare_colab_environment"](args.source, args.environment_root) == target
after = {name: importlib.metadata.version(name) for name in before}
assert before == after, (before, after)
subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
versions = json.loads(subprocess.check_output([
    str(target), "-c",
    'import importlib.metadata as m, json, sys; print(json.dumps({"python": sys.version, "packages": {n: m.version(n) for n in ["whisperx", "torch", "torchaudio", "numpy", "huggingface-hub"]}, "gradio_installed": any(d.metadata["Name"].lower() == "gradio" for d in m.distributions())}))',
], text=True))
assert not versions["gradio_installed"]
smoke_code = '''
import json
import torch, torchaudio, whisperx.asr, whisperx.diarize
from gurumoji import app
client = app.app.test_client()
page = client.get("/")
assert page.status_code == 200, page.status_code
assert b'data-picker-mode="browser"' in page.data
configuration = client.get("/api/config")
assert configuration.status_code == 200, configuration.status_code
runtime = app.runtime_info()
assert runtime["kind"] == "colab" and not runtime["native_file_dialog"]
print(json.dumps({"page_status": page.status_code, "config_status": configuration.status_code, "runtime_kind": runtime["kind"], "torch_cuda_build": torch.version.cuda}))
'''
with tempfile.TemporaryDirectory(prefix="gurumoji-colab-smoke-", dir="/var/tmp") as temporary:
    root = Path(temporary)
    shutil.copytree(args.source / "src", root / "src")
    shutil.copytree(args.source / "config", root / "config", ignore=shutil.ignore_patterns("tokens.json"))
    environment = os.environ.copy()
    environment.update({
        "PYTHONPATH": str(root / "src"),
        "MOJIOKOSI_RUNTIME": "colab",
        "MOJIOKOSI_NO_BROWSER": "1",
        "MOJIOKOSI_DATA_DIR": str(root / "data"),
        "MOJIOKOSI_OUTPUT_DIR": str(root / "output"),
        "MOJIOKOSI_BACKUP_DIR": str(root / "backups"),
        "HF_HOME": str(root / "models"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    })
    result = subprocess.run([str(target), "-c", smoke_code], cwd=root, env=environment, capture_output=True, text=True, timeout=120)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    result.check_returncode()
    smoke = json.loads(result.stdout.strip().splitlines()[-1])
args.evidence.write_text(json.dumps({"kernel_before": before, "kernel_after": after, "application": versions, "smoke": smoke}, indent=2) + "\n", encoding="utf-8")
print("Colab専用環境の実導入・分離・画面応答を確認しました。")
