"""Run cached Whisper tiny against locally synthesized, non-private speech.

This smoke test does not download a model, call a provider API, change a vault,
or submit a Gurumoji UI job. It validates only the CPU recognition component.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

MODEL_SHA256 = "65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9"
TEXT = (
    "This is a simple test of the speech recognition system. "
    "The meeting will begin at ten in the morning."
)


def main() -> int:
    import torch
    import whisper

    project = Path(__file__).resolve().parents[2]
    model_file = project / "runtime/models/whisper/tiny.pt"
    if not model_file.is_file():
        raise SystemExit("Cached tiny.pt is missing. This test never downloads a model.")
    digest = hashlib.sha256(model_file.read_bytes()).hexdigest()
    if digest != MODEL_SHA256:
        raise SystemExit("Cached tiny.pt did not match the official model checksum.")
    artifacts = project / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    audio = artifacts / "synthetic-asr-test.wav"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
            "-i", f"flite=text='{TEXT}':voice=slt", "-ar", "16000", "-ac", "1", str(audio),
        ],
        check=True,
        timeout=30,
    )
    torch.set_num_threads(4)
    model = whisper.load_model(str(model_file), device="cpu")
    started = time.monotonic()
    result = model.transcribe(
        str(audio), language="en", fp16=False, verbose=False,
        condition_on_previous_text=False, word_timestamps=True,
    )
    report = {
        "model": "tiny", "device": "cpu", "input_text": TEXT,
        "audio_source": "FFmpeg built-in flite synthetic speech; no personal recording",
        "recognized_text": result["text"],
        "inference_seconds": round(time.monotonic() - started, 2),
        "segments": len(result["segments"]), "model_sha256": digest,
        "model_bytes": model_file.stat().st_size,
    }
    (artifacts / "whisper-cpu-smoke.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    text = result["text"].lower()
    if "speech recognition" not in text or "morning" not in text:
        raise SystemExit("CPU inference ran, but the expected synthetic words were absent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
