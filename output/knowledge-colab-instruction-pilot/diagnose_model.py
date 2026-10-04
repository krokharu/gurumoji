"""Report the root cause of the pinned model loading failure."""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, "/content/gurumoji_pilot_worker/src")
from gurumoji.knowledge_builder import colab_qwen3

try:
    _, _, details = colab_qwen3.load_qwen3_a100()
    report = {"status": "loaded", "runtime": details}
except Exception as exc:
    root = exc
    while root.__cause__ is not None:
        root = root.__cause__
    report = {
        "status": "failed",
        "error_type": type(exc).__name__,
        "error": str(exc),
        "root_type": type(root).__name__,
        "root_error": str(root)[:2000],
        "root_trace": "".join(traceback.format_exception(root))[-4000:],
    }
Path("/content/gurumoji_pilot_model_diagnostic.json").write_text(
    json.dumps(report, ensure_ascii=False, sort_keys=True), encoding="utf-8"
)
print(json.dumps({k: v for k, v in report.items() if k != "root_trace"}, ensure_ascii=False))
