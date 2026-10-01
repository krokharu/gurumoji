"""Create a finite, synthetic Qwen3-Next 80B A100 Colab probe notebook."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


MODEL_REPO = "Qwen/Qwen3-Next-80B-A3B-Instruct-GGUF"
MODEL_REVISION = "4c8630cf7af926a9c5095cb4bbbbc65d36e20f77"
MODEL_FILE = "Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf"
MODEL_FILE_SIZE = 48_410_988_384
MODEL_SHA256 = "d103b2733ec1012a52d01edda66b7e5c24ae50508c9f99f5297ea459ef3c061a"
LLAMA_CPP_REVISION = "9adc7f420c37641921b32e326b3d4a538256b878"
DEFAULT_FOLDER_ID = "1wd69nc_9Xaw80Id54Nt7WW_9x3ztm9j5"


PROBE_CODE = r'''
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from google.colab import files

FOLDER_ID = @FOLDER_ID@
MODEL_REPO = @MODEL_REPO@
MODEL_REVISION = @MODEL_REVISION@
MODEL_FILE = @MODEL_FILE@
MODEL_FILE_SIZE = @MODEL_FILE_SIZE@
MODEL_SHA256 = @MODEL_SHA256@
LLAMA_CPP_REVISION = @LLAMA_CPP_REVISION@
MAX_SECONDS = 55 * 60
MODEL_ROOT = Path('/content/gurumoji_80b_probe_model')
SOURCE_ROOT = Path('/content/gurumoji_80b_probe_llama_cpp')
SERVER_PORT = 18180
GPU_LAYERS = 30
START_MONOTONIC = time.monotonic()
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
RESULT_NAME = f'Gurumoji_A100_80B_Probe_{RUN_ID}.json'
result = {
    'schema_version': 1,
    'kind': 'gurumoji_a100_80b_synthetic_probe',
    'run_id': RUN_ID,
    'started_at': datetime.now(timezone.utc).isoformat(),
    'status': 'running',
    'model_repo': MODEL_REPO,
    'model_revision': MODEL_REVISION,
    'model_file': MODEL_FILE,
    'expected_model_sha256': MODEL_SHA256,
    'llama_cpp_revision': LLAMA_CPP_REVISION,
    'max_seconds': MAX_SECONDS,
    'gpu_layers_requested': GPU_LAYERS,
    'synthetic_input_only': True,
    'steps': [],
}
server = None
server_log = None
gpu_samples = []
stop_sampling = threading.Event()
local_http = requests.Session()
local_http.trust_env = False

def remaining():
    left = MAX_SECONDS - (time.monotonic() - START_MONOTONIC)
    if left <= 0:
        raise TimeoutError('probe time budget expired')
    return left

def step(name, argv, maximum=900):
    print('START', name, flush=True)
    started = time.monotonic()
    completed = subprocess.run(
        argv, check=False, capture_output=True, text=True,
        timeout=min(maximum, remaining()),
    )
    record = {'step': name, 'seconds': round(time.monotonic() - started, 2),
              'exit_code': completed.returncode}
    result['steps'].append(record)
    if completed.returncode:
        raise RuntimeError(name + ' failed with exit code ' + str(completed.returncode))
    print('DONE', name, record['seconds'], 'seconds', flush=True)
    return completed.stdout

def gpu_memory_mib():
    raw = subprocess.check_output([
        'nvidia-smi', '--query-gpu=memory.used,memory.free,memory.total',
        '--format=csv,noheader,nounits',
    ], text=True, timeout=15).strip().splitlines()[0]
    used, free, total = [int(item.strip()) for item in raw.split(',')]
    return {'used_mib': used, 'free_mib': free, 'total_mib': total}

def sample_gpu():
    while not stop_sampling.wait(1):
        try:
            gpu_samples.append(gpu_memory_mib()['used_mib'])
        except Exception:
            pass

try:
    result['compute_started_at'] = datetime.now(timezone.utc).isoformat()

    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is unavailable')
    gpu_name = torch.cuda.get_device_name(0)
    result['gpu_name'] = gpu_name
    if 'A100' not in gpu_name.upper():
        raise RuntimeError('an A100 runtime is required')
    result['gpu_memory_before'] = gpu_memory_mib()
    if result['gpu_memory_before']['free_mib'] < 30_000:
        raise RuntimeError('A100 has insufficient free GPU memory for the probe')
    disk = shutil.disk_usage('/content')
    result['free_disk_bytes_before'] = disk.free
    if disk.free < 60_000_000_000:
        raise RuntimeError('runtime has insufficient free disk for the 48.4 GB GGUF')
    result['host_ram_bytes'] = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    if result['host_ram_bytes'] < 70_000_000_000:
        raise RuntimeError('runtime has insufficient host RAM for partial CPU offload')
    print('Preflight:', gpu_name, result['gpu_memory_before'],
          'disk bytes free:', disk.free, flush=True)

    if SOURCE_ROOT.exists() or MODEL_ROOT.exists():
        raise RuntimeError('probe paths already exist; use a fresh Colab runtime')
    SOURCE_ROOT.mkdir()
    MODEL_ROOT.mkdir()
    step('fetch_pinned_llama_cpp', [
        'git', '-C', str(SOURCE_ROOT), 'init', '-q',
    ], maximum=60)
    step('add_llama_cpp_origin', [
        'git', '-C', str(SOURCE_ROOT), 'remote', 'add', 'origin',
        'https://github.com/ggml-org/llama.cpp.git',
    ], maximum=60)
    step('fetch_llama_cpp_revision', [
        'git', '-C', str(SOURCE_ROOT), 'fetch', '--depth', '1', 'origin',
        LLAMA_CPP_REVISION,
    ], maximum=300)
    step('checkout_llama_cpp_revision', [
        'git', '-C', str(SOURCE_ROOT), 'checkout', '-q', '--detach', 'FETCH_HEAD',
    ], maximum=60)
    actual_revision = step('verify_llama_cpp_revision', [
        'git', '-C', str(SOURCE_ROOT), 'rev-parse', 'HEAD',
    ], maximum=30).strip()
    if actual_revision != LLAMA_CPP_REVISION:
        raise RuntimeError('llama.cpp revision mismatch')
    step('configure_cuda_llama_cpp', [
        'cmake', '-S', str(SOURCE_ROOT), '-B', str(SOURCE_ROOT / 'build'),
        '-DGGML_CUDA=ON', '-DLLAMA_BUILD_TESTS=OFF',
        '-DCMAKE_BUILD_TYPE=Release',
    ], maximum=300)
    step('build_llama_server', [
        'cmake', '--build', str(SOURCE_ROOT / 'build'), '--config', 'Release',
        '--target', 'llama-server', '-j', '4',
    ], maximum=1200)
    binary = SOURCE_ROOT / 'build/bin/llama-server'
    if not binary.is_file():
        raise RuntimeError('pinned llama-server binary is absent')

    step('install_pinned_huggingface_hub', [
        sys.executable, '-m', 'pip', 'install', '-q', 'huggingface_hub==0.36.0',
    ], maximum=300)
    # Use a subprocess so the overall 55-minute probe deadline bounds download.
    download_code = (
        'from huggingface_hub import hf_hub_download; '
        'print(hf_hub_download(repo_id=' + repr(MODEL_REPO) +
        ', filename=' + repr(MODEL_FILE) +
        ', revision=' + repr(MODEL_REVISION) +
        ', local_dir=' + repr(str(MODEL_ROOT)) + '))'
    )
    step('download_pinned_q4_gguf', [sys.executable, '-c', download_code],
         maximum=remaining())
    model_path = MODEL_ROOT / MODEL_FILE
    if not model_path.is_file() or model_path.stat().st_size != MODEL_FILE_SIZE:
        raise RuntimeError('downloaded GGUF size does not match the pinned file')
    digest = hashlib.sha256()
    with model_path.open('rb') as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            remaining()
            digest.update(chunk)
    result['model_sha256'] = digest.hexdigest()
    if result['model_sha256'] != MODEL_SHA256:
        raise RuntimeError('downloaded GGUF SHA-256 does not match the pinned file')
    result['model_size_bytes'] = model_path.stat().st_size

    server_log = (SOURCE_ROOT / 'llama_server.log').open('wb')
    server = subprocess.Popen([
        str(binary), '-m', str(model_path), '--host', '127.0.0.1',
        '--port', str(SERVER_PORT), '--alias', MODEL_REPO,
        '--jinja', '-ngl', str(GPU_LAYERS), '-c', '4096',
        '-np', '1',
    ], stdout=server_log, stderr=subprocess.STDOUT)
    load_started = time.monotonic()
    sampler = threading.Thread(target=sample_gpu, daemon=True)
    sampler.start()
    ready = False
    while time.monotonic() - load_started < min(600, remaining()):
        if server.poll() is not None:
            raise RuntimeError('llama-server exited during model load')
        try:
            response = local_http.get(f'http://127.0.0.1:{SERVER_PORT}/health', timeout=3)
            if response.status_code == 200:
                ready = True
                break
        except requests.RequestException:
            pass
        time.sleep(3)
    if not ready:
        raise TimeoutError('80B model did not become ready within 10 minutes')
    result['model_load_seconds'] = round(time.monotonic() - load_started, 2)
    result['gpu_memory_after_load'] = gpu_memory_mib()
    if result['gpu_memory_after_load']['free_mib'] < 4_096:
        raise RuntimeError('model loaded without enough GPU headroom for inference')

    synthetic_text = '架空の手順では、確認できない数値は推測せず「不明」と記録する。根拠IDは SYNTHETIC-1。'
    prompt = {
        'model': MODEL_REPO,
        'messages': [
            {'role': 'system', 'content': 'Use only the supplied synthetic text. Return one JSON object with exactly claim and evidence_id. Do not add facts.'},
            {'role': 'user', 'content': synthetic_text},
        ],
        'temperature': 0,
        'max_tokens': 128,
        'stream': False,
    }
    inference_started = time.monotonic()
    response = local_http.post(
        f'http://127.0.0.1:{SERVER_PORT}/v1/chat/completions',
        json=prompt, timeout=min(180, remaining()),
    )
    response.raise_for_status()
    body = response.json()
    content = body['choices'][0]['message']['content']
    result['inference_seconds'] = round(time.monotonic() - inference_started, 2)
    result['usage'] = body.get('usage')
    result['synthetic_response'] = content[:2_000]
    try:
        parsed = json.loads(content)
        result['json_valid'] = (isinstance(parsed, dict) and
                                set(parsed) == {'claim', 'evidence_id'})
        result['evidence_id_valid'] = (result['json_valid'] and
                                       parsed['evidence_id'] == 'SYNTHETIC-1')
    except (ValueError, TypeError):
        result['json_valid'] = False
        result['evidence_id_valid'] = False
    result['gpu_memory_after_inference'] = gpu_memory_mib()
    result['status'] = ('passed' if result['json_valid'] and
                        result['evidence_id_valid'] else 'inference_quality_failed')
except Exception as exc:
    result['status'] = 'failed'
    result['error_type'] = type(exc).__name__
    result['error_summary'] = str(exc)[:400]
finally:
    stop_sampling.set()
    if server is not None:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)
    if server_log is not None:
        server_log.close()
    result['peak_gpu_memory_mib'] = max(gpu_samples) if gpu_samples else None
    result['ended_at'] = datetime.now(timezone.utc).isoformat()
    result['elapsed_seconds'] = round(time.monotonic() - START_MONOTONIC, 2)
    print(json.dumps({k: v for k, v in result.items() if k != 'steps'},
                     ensure_ascii=False, indent=2), flush=True)
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':')).encode('utf-8')
    local_result = Path('/content') / RESULT_NAME
    local_result.write_bytes(raw)
    print('LOCAL_RESULT', local_result, 'SHA256',
          hashlib.sha256(raw).hexdigest(), flush=True)
    print('RESULT_JSON', raw.decode('utf-8'), flush=True)
    try:
        files.download(str(local_result))
    except Exception as download_exc:
        print('BROWSER_DOWNLOAD_UNAVAILABLE', type(download_exc).__name__,
              str(download_exc)[:200], flush=True)
'''


def build_notebook(folder_id: str) -> dict:
    substitutions = {
        "@FOLDER_ID@": json.dumps(folder_id),
        "@MODEL_REPO@": json.dumps(MODEL_REPO),
        "@MODEL_REVISION@": json.dumps(MODEL_REVISION),
        "@MODEL_FILE@": json.dumps(MODEL_FILE),
        "@MODEL_FILE_SIZE@": str(MODEL_FILE_SIZE),
        "@MODEL_SHA256@": json.dumps(MODEL_SHA256),
        "@LLAMA_CPP_REVISION@": json.dumps(LLAMA_CPP_REVISION),
    }
    code = PROBE_CODE
    for old, new in substitutions.items():
        code = code.replace(old, new)
    compile(code, "Gurumoji_A100_80B_Probe.ipynb", "exec")
    return {
        "nbformat": 4,
        "nbformat_minor": 4,
        "metadata": {
            "colab": {"gpuType": "A100", "include_colab_link": True},
            "accelerator": "GPU",
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
        },
        "cells": [
            {
                "cell_type": "markdown", "metadata": {},
                "source": [
                    "# Gurumoji A100 80B synthetic probe\n",
                    "Select a hosted A100 High RAM runtime and run this notebook once. "
                    "It checks GPU, host RAM, and disk capacity, "
                    "builds pinned CUDA llama.cpp, downloads and SHA-256 checks the "
                    "official Qwen3-Next-80B-A3B-Instruct Q4_K_M GGUF, then runs one "
                    "synthetic JSON prompt with 30 layers on A100 and the rest in host RAM. "
                    "It downloads a small result JSON through the "
                    "browser for later upload to Drive. It does not read local papers or generate expert knowledge. "
                    "The whole probe has a 55-minute software budget.\n",
                ],
            },
            {"cell_type": "code", "execution_count": None, "metadata": {},
             "outputs": [], "source": code.splitlines(keepends=True)},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder-id", default=DEFAULT_FOLDER_ID)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not args.folder_id or any(character in args.folder_id for character in "/\\?&#"):
        parser.error("folder ID is invalid")
    output = Path(args.output).resolve()
    if output.exists():
        parser.error("output Notebook already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    notebook = build_notebook(args.folder_id)
    output.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    print(json.dumps({"output": str(output), "model_repo": MODEL_REPO,
                      "model_revision": MODEL_REVISION,
                      "model_sha256": MODEL_SHA256,
                      "llama_cpp_revision": LLAMA_CPP_REVISION}, sort_keys=True))


if __name__ == "__main__":
    main()
