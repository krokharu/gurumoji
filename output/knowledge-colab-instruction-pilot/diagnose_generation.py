"""Capture bounded raw model output for one pilot prompt without accepting it."""
from __future__ import annotations

import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, "/content/gurumoji_pilot_worker/src")
from gurumoji.knowledge_builder import colab_qwen3

with zipfile.ZipFile("/content/gurumoji_pilot_job.zip") as bundle:
    with zipfile.ZipFile(BytesIO(bundle.read("request.zip"))) as request_zip:
        job = json.loads(request_zip.read("handoff.json"))["job"]
        payload = json.loads(request_zip.read("request.json"))
    registry = json.loads(bundle.read("approved_sources.json"))
sources = {item["source_id"]: item for item in registry["sources"]}
model, tokenizer, runtime = colab_qwen3.load_qwen3_a100()
real_decode = tokenizer.decode
captured = {}


def recording_decode(ids, *args, **kwargs):
    captured["raw_with_special_tokens"] = real_decode(ids, skip_special_tokens=False)[:3000]
    decoded = real_decode(ids, *args, **kwargs)
    captured["decoded"] = decoded[:3000]
    captured["generated_token_count"] = int(ids.shape[-1])
    return decoded


tokenizer.decode = recording_decode
try:
    generate = colab_qwen3.create_generator(
        job=job, approved_sources=sources,
        expert_definition=payload["task"]["expert_context"]["definition"],
    )
    result = generate(payload["task"], payload["excerpts"])
    captured["result_status"] = "valid_candidate" if result else "no_candidate"
except Exception as exc:
    captured["result_status"] = "failed"
    captured["error_type"] = type(exc).__name__
    captured["error"] = str(exc)
finally:
    tokenizer.decode = real_decode

Path("/content/gurumoji_pilot_generation_diagnostic.json").write_text(
    json.dumps(captured, ensure_ascii=False, sort_keys=True), encoding="utf-8"
)
print(json.dumps({k: v for k, v in captured.items() if k not in {"decoded", "raw_with_special_tokens"}},
                 ensure_ascii=False))
