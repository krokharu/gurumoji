"""公開版専用試験の明示的なソース選択。通常版のpackageは置換しない。"""
import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import sys
import unittest


def public_source(*required, environ=None):
    configured = (os.environ if environ is None else environ).get("GURUMOJI_COLAB_SOURCE")
    if not configured:
        raise unittest.SkipTest("not-run: 公開版専用試験にはGURUMOJI_COLAB_SOURCEを明示してください。")
    root = Path(configured).expanduser().resolve(strict=True)
    for name in required:
        if not (root / name).is_file():
            raise ValueError(f"公開版の試験ソースに必要なファイルがありません: {name}")
    return root


def load_public_module(root, name):
    if name not in {"colab_llm", "colab_monitor", "colab_support"}:
        raise ValueError("公開版の試験対象moduleが正しくありません。")
    directory = Path(root).resolve() / "src/gurumoji"
    identifier = "_gurumoji_public_tests_" + hashlib.sha256(str(directory).encode("utf-8")).hexdigest()[:16]
    if identifier not in sys.modules:
        spec = importlib.util.spec_from_file_location(identifier, directory / "__init__.py",
            submodule_search_locations=[str(directory)])
        if spec is None or spec.loader is None:
            raise ImportError("公開版のpackageを読み込めません。")
        module = importlib.util.module_from_spec(spec)
        sys.modules[identifier] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[identifier]
            raise
    return importlib.import_module(identifier + "." + name)
