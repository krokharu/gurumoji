"""承認済みの共有Gemmaだけを16Kへ再ロードし、失敗時は元の設定へ戻す。"""
import argparse
import copy
import json
from pathlib import Path

import lmstudio as lms


parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()
identifier = "google/gemma-4-12b-qat"
with lms.Client() as client:
    loaded = {model.identifier: model for model in client.llm.list_loaded()}
    original = loaded[identifier]
    info = original.get_info().to_dict()
    previous = original.get_load_config().to_dict()
    desired = copy.deepcopy(previous)
    desired.update(contextLength=16384)
    desired["gpu"] = {**desired.get("gpu", {}), "ratio": 0.8}
    print(json.dumps({"identifier": identifier, "before": previous, "requested": desired}), flush=True)
    if not args.apply:
        raise SystemExit(0)
    backup = Path("output/validation/maf-shared-model-before-20261102.json")
    if backup.exists():
        raise RuntimeError("既存の復元用設定を上書きしません。")
    backup.write_text(json.dumps({"identifier": identifier, "model_key": info["modelKey"],
        "config": previous, "other_loaded_models": sorted(set(loaded) - {identifier})}, indent=2), encoding="utf-8")
    if original.get_info().to_dict() != info or original.get_load_config().to_dict() != previous:
        raise RuntimeError("確認後に共有モデルの状態が変わりました。")
    original.unload()
    try:
        model = client.llm.load_new_instance(info["modelKey"], identifier, ttl=None,
            config=lms.LlmLoadModelConfig.from_dict(desired))
        actual = model.get_load_config().to_dict()
        if model.get_context_length() != 16384 or actual.get("gpu", {}).get("ratio") != 0.8:
            raise RuntimeError("ロード済み設定が指定と一致しません。")
        after = {item.identifier for item in client.llm.list_loaded()}
        if not (set(loaded) - {identifier}).issubset(after):
            raise RuntimeError("他のロード済みモデルの状態が変わりました。")
        print(json.dumps({"status": "configured", "identifier": identifier, "config": actual,
                          "loaded_models": sorted(after)}), flush=True)
    except BaseException:
        for item in client.llm.list_loaded():
            if item.identifier == identifier:
                item.unload()
        restored = client.llm.load_new_instance(info["modelKey"], identifier, ttl=None,
            config=lms.LlmLoadModelConfig.from_dict(previous))
        print(json.dumps({"status": "restored", "config": restored.get_load_config().to_dict()}), flush=True)
        raise
