"""共有モデルを操作せず、専用CPUモデルで合成会話の全工程を確認する。"""
import os
from pathlib import Path
import subprocess
import sys

import lmstudio as lms


identifier = "gurumoji-maf-validation-20261102"
with lms.Client() as client:
    before = {model.identifier for model in client.llm.list_loaded()}
    if identifier in before:
        raise RuntimeError("試験専用モデルが既に存在します。")
    model = client.llm.load_new_instance(
        "google/gemma-4-12b-qat", identifier, ttl=None,
        config={"context_length": 16384, "gpu": {"ratio": 0.0},
                "offload_kv_cache_to_gpu": False, "flash_attention": True})
    try:
        print("CPU_TEST_MODEL_LOADED", flush=True)
        environment = {**os.environ, "MOJIOKOSI_MAF_TEST_MODEL": identifier,
                       "MOJIOKOSI_MAF_TEST_TIMEOUT": "360",
                       "MOJIOKOSI_MAF_TEST_TIME_LIMIT": "3600"}
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("verify_maf_dev_model.py"))],
                                env=environment, check=False)
    finally:
        model.unload()
        after = {item.identifier for item in client.llm.list_loaded()}
        print("CPU_TEST_MODEL_RELEASED", flush=True)
        print({"other_models_before": sorted(before), "other_models_after": sorted(after)}, flush=True)
    raise SystemExit(result.returncode)
