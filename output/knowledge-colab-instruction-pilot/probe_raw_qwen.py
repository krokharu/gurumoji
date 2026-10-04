"""Inspect bounded raw tokens from the pinned A100 model without accepting output."""
from __future__ import annotations

import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import torch

sys.path.insert(0, "/content/gurumoji_pilot_worker/src")
from gurumoji.knowledge_builder import colab_qwen3, contracts

with zipfile.ZipFile("/content/gurumoji_pilot_job.zip") as bundle:
    with zipfile.ZipFile(BytesIO(bundle.read("request.zip"))) as request_zip:
        payload = json.loads(request_zip.read("request.json"))

model, tokenizer, runtime = colab_qwen3.load_qwen3_a100()
excerpt = payload["excerpts"][0]
source = payload["sources"][0]
user_payload = {
    "expert_definition": payload["task"]["expert_context"]["definition"],
    "source_excerpt": {
        "source_title": source["title"],
        "source_id": source["source_id"],
        "anchor_id": excerpt["anchor_id"],
        "text": excerpt["text"],
    },
    "output_shape": {"candidates": [{"claim": "string", "applicability": ["string"],
                                      "exceptions": ["string"], "claim_type": "literature"}]},
}
messages = [
    {"role": "system", "content": colab_qwen3.SYSTEM_INSTRUCTIONS.decode("utf-8")},
    {"role": "user", "content": contracts.canonical_json(user_payload).decode("utf-8")},
]
inputs = tokenizer.apply_chat_template(
    messages, add_generation_prompt=True, tokenize=True, return_dict=True,
    return_tensors="pt", enable_thinking=False,
).to(model.device)
with torch.inference_mode():
    output = model.generate(
        **inputs, max_new_tokens=256, do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )
tokens = output[0][int(inputs["input_ids"].shape[-1]):]
report = {
    "input_tokens": int(inputs["input_ids"].shape[-1]),
    "generated_tokens": int(tokens.shape[-1]),
    "raw": tokenizer.decode(tokens, skip_special_tokens=False)[:3000],
    "decoded": tokenizer.decode(tokens, skip_special_tokens=True)[:3000],
}
Path("/content/gurumoji_pilot_raw_probe.json").write_text(
    json.dumps(report, ensure_ascii=False, sort_keys=True), encoding="utf-8"
)
print(json.dumps({"input_tokens": report["input_tokens"], "generated_tokens": report["generated_tokens"]}))
