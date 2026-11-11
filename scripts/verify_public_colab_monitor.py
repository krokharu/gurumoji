"""専用Pythonの実計測と、停止後にスレッドが残らないことを確認する。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import threading

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--environment-root", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source / "src"))
from gurumoji.colab_monitor import RuntimeMonitor, render_monitor_html

requirements = (args.source / "config/requirements.txt").read_bytes()
environment_hash = hashlib.sha256(requirements + sys.version.encode() + b"colab-cu128-venv-v1").hexdigest()[:12]
environment = args.environment_root / environment_hash
assert (environment / ".setup-complete").is_file()
ready = threading.Event()
frames = []

def publish(content):
    frames.append(content)
    if "直近3回" in content:
        ready.set()

instance = RuntimeMonitor(environment / "bin/python", args.source, publish, interval=1)
try:
    instance.start()
    assert ready.wait(20), "実計測の応答がありません。"
finally:
    instance.stop()
assert not instance._thread.is_alive()
assert "停止済み" in frames[-1]
assert len(instance.history) >= 3
for record in instance.history:
    assert not record.get("sample_failed"), record
    assert record["cpu_percent"] is not None
    assert record["ram_percent"] is not None
args.output.mkdir(parents=True, exist_ok=True)
(args.output / "live.json").write_text(json.dumps({"samples": list(instance.history), "thread_stopped": True}, ensure_ascii=False, indent=2), encoding="utf-8")
preview = '<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:16px">' + render_monitor_html(instance.history, interval=1, running=False) + '</body></html>'
(args.output / "preview.html").write_text(preview, encoding="utf-8")
print("専用Pythonの実計測3回・表示生成・停止後のスレッド終了を確認しました。")
