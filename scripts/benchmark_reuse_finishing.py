"""公開音声で前処理とおすすめ仕上げを比較する独立実験。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import unicodedata
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests
from scipy.signal import resample_poly


DATASET = "FluidInference/JSUT-basic5000"
DATA_REV = "cd13cc9c9fe70d8d4f62ffe6fbbb872aef79835c"
SPACE = "https://nvidia-nvidia-nemotronlabs-re-use.hf.space"
RATE = 16000
SNRS = [0, 10, 20]


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def download(url, destination):
    destination = Path(destination)
    if not destination.exists():
        response = requests.get(url, timeout=90)
        response.raise_for_status()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
    return destination


def read_wav(path):
    with wave.open(str(path), "rb") as stream:
        sr = stream.getframerate()
        channels = stream.getnchannels()
        assert stream.getsampwidth() == 2
        audio = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").astype(np.float64) / 32768
    audio = audio.reshape(-1, channels).mean(axis=1)
    if sr != RATE:
        divisor = math.gcd(sr, RATE)
        audio = resample_poly(audio, RATE // divisor, sr // divisor)
    return audio


def write_wav(path, audio):
    assert np.isfinite(audio).all()
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes((np.clip(audio, -1, 32767/32768) * 32768).astype("<i2").tobytes())


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text)
                   if not c.isspace() and unicodedata.category(c)[0] not in {"P", "Z"})


def distance(left, right):
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (a != b)))
        previous = current
    return previous[-1]


def official_enhance(source, destination, metadata, token=""):
    if destination.exists():
        return
    headers = {"Authorization": "Bearer " + token} if token else {}
    with source.open("rb") as stream:
        response = requests.post(SPACE + "/gradio_api/upload", headers=headers, files={"files": (source.name, stream, "audio/wav")}, timeout=90)
    response.raise_for_status()
    uploaded = response.json()[0]
    response = requests.post(SPACE + "/gradio_api/call/unified_enhance", json={
        "data": [{"path": uploaded, "meta": {"_type": "gradio.FileData"}, "orig_name": source.name}, None, "", ""],
    }, headers=headers, timeout=90)
    response.raise_for_status()
    event_id = response.json()["event_id"]
    event = ""
    with requests.get(SPACE + "/gradio_api/call/unified_enhance/" + event_id, headers=headers, stream=True, timeout=(30, 600)) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith("event:"):
                event = line[6:].strip()
            if line.startswith("data:"):
                payload = json.loads(line[5:].strip())
                if event == "error":
                    metadata["remote_error"] = payload
                    raise RuntimeError("RE-USE公式デモの推論が失敗しました。")
                if event == "complete":
                    result = payload[1]
                    url = result.get("url") or SPACE + "/gradio_api/file=" + result["path"]
                    download(url, destination)
                    metadata.update({"event_id": event_id, "input_sha256": sha(source), "output_sha256": sha(destination)})
                    return
    raise RuntimeError("RE-USE公式デモの完了結果がありません。")


def prepare(args):
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    data = root / "public-audio"
    data.mkdir(exist_ok=True)
    base = f"https://huggingface.co/datasets/{DATASET}/resolve/{DATA_REV}/"
    transcript = download(base + "basic5000/transcript_utf8.txt", data / "transcript_utf8.txt")
    download(base + "LICENCE.txt", data / "LICENCE.txt")
    references = dict(line.split(":", 1) for line in transcript.read_text(encoding="utf-8-sig").splitlines() if ":" in line)
    token = json.loads((args.source/"config/tokens.json").read_text(encoding="utf-8-sig")).get("huggingface_token", "")
    clean = []
    for sample_id in sorted(references)[:args.samples]:
        path = download(base + f"basic5000/{sample_id}.wav", data / f"{sample_id}.wav")
        audio = read_wav(path)
        clean.append((sample_id, audio, references[sample_id], sha(path)))
    spec = importlib.util.spec_from_file_location("current_audio", args.source / "src/gurumoji/services/transcription/audio.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    filters = module.filters("standard", module.AUDIO_PREPROCESS_PRESETS, RATE)
    rows = []
    for snr in SNRS:
        condition = root / f"snr-{snr}"
        condition.mkdir(exist_ok=True)
        groups, group, length = [], [], 0
        for item in clean:
            if group and length + len(item[1]) + RATE//4 > 24*RATE:
                groups.append(group)
                group, length = [], 0
            group.append(item)
            length += len(item[1]) + RATE//4
        if group:
            groups.append(group)
        for group_index, group in enumerate(groups):
            audio_parts, spans, position = [], [], 0
            for sample_id, audio, reference, audio_hash in group:
                rng = np.random.default_rng(20261102 + int(sample_id[-4:]))
                noise = rng.normal(size=len(audio))
                speech_rms = np.sqrt(np.mean(audio**2))
                noise *= speech_rms / (np.sqrt(np.mean(noise**2)) * 10**(snr/20))
                mixture = audio + noise
                # 両方式へ完全に同じ入力を渡し、クリッピングを避ける。
                mixture *= min(1.0, 0.95 / max(np.max(np.abs(mixture)), 1e-8))
                audio_parts.extend([mixture, np.zeros(RATE//4)])
                spans.append((sample_id, position, position + len(audio), reference, audio_hash))
                position += len(audio) + RATE//4
            noisy = condition / f"group-{group_index}-noisy.wav"
            standard = condition / f"group-{group_index}-standard.wav"
            reuse = condition / f"group-{group_index}-reuse.wav"
            if not noisy.exists():
                write_wav(noisy, np.concatenate(audio_parts))
            if not standard.exists():
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(noisy),
                                "-af", ",".join(filters), "-ac", "1", "-ar", str(RATE), "-c:a", "pcm_s16le", str(standard)], check=True)
            print(f"REUSE_START snr={snr} group={group_index}", flush=True)
            metadata_path = condition / f"group-{group_index}-remote.json"
            metadata = {}
            try:
                official_enhance(noisy, reuse, metadata, token)
            finally:
                if metadata:
                    save(metadata_path, metadata)
            for method, path in [("standard", standard), ("reuse", reuse)]:
                audio = read_wav(path)
                assert abs(len(audio) - position) < RATE//20, (len(audio), position)
                for sample_id, start, end, reference, audio_hash in spans:
                    clip = condition / f"{sample_id}-{method}.wav"
                    write_wav(clip, audio[start:end])
                    rows.append({"id": sample_id, "snr": snr, "method": method, "path": str(clip),
                                 "reference": reference, "source_sha256": audio_hash,
                                 "audio_sha256": sha(clip), "seconds": (end-start)/RATE})
            print(f"REUSE_DONE snr={snr} group={group_index}", flush=True)
    provenance = {"dataset": DATASET, "dataset_revision": DATA_REV, "samples": args.samples,
                  "snr_db": SNRS, "noise": "固定シードの白色ガウス雑音。発話全体RMSでSNRを定義。",
                  "source_checkout": str(args.source), "python": sys.executable,
                  "asr": "faster-whisper base / CPU int8 / language=ja / beam_size=5 / VADなし",
                  "finishing": "Jev候補判定 + 現行repair_recommended_segments / medium / Google設定モデル",
                  "segmentation": "正解音声ファイルの境界を固定。ASR断片をファイル単位に結合。",
                  "reuse_execution": "NVIDIA公式Hugging Face Space API。帯域拡張なし。速度は比較しない。",
                  "current_source_sha256": {str(p): sha(args.source/p) for p in [
                      Path("src/gurumoji/services/transcription/audio.py"), Path("src/gurumoji/ai_finishing.py"),
                      Path("src/gurumoji/jev_review.py"), Path("src/gurumoji/services/ai/client.py")]}}
    save(root/"manifest.json", {"provenance": provenance, "rows": rows})


def transcribe(args):
    from faster_whisper import WhisperModel
    manifest = json.loads((args.output/"manifest.json").read_text(encoding="utf-8"))
    model_root = Path.home()/".cache/huggingface/hub/models--Systran--faster-whisper-base"
    revision = (model_root/"refs/main").read_text().strip()
    model = WhisperModel(str(model_root/"snapshots"/revision), device="cpu", compute_type="int8", cpu_threads=8, num_workers=1)
    rows = manifest["rows"]
    output = args.output/"asr.json"
    cached = json.loads(output.read_text(encoding="utf-8")) if output.exists() else []
    results = {(r["id"], r["snr"], r["method"]): r for r in cached}
    for row in rows:
        key = (row["id"], row["snr"], row["method"])
        if key in results:
            continue
        pieces, info = model.transcribe(read_wav(row["path"]).astype(np.float32), language="ja", beam_size=5, vad_filter=False,
                                       condition_on_previous_text=False, no_speech_threshold=0.6)
        fragments = [{"start": s.start, "end": s.end, "text": s.text} for s in pieces]
        text = "".join(s["text"] for s in fragments).strip()
        results[key] = {**row, "text": text, "asr_fragments": fragments, "asr_revision": revision}
        save(output, list(results.values()))
        print(f"ASR_DONE {row['snr']} {row['method']} {row['id']}", flush=True)


def finish(args):
    sys.path.insert(0, str(args.source/"src"))
    from gurumoji.jev_review import review_transcript
    from gurumoji.ai_finishing import repair_recommended_segments
    from gurumoji.services.ai.client import call_ai_json
    config = json.loads((args.source/"config/tokens.json").read_text(encoding="utf-8-sig"))
    source = json.loads((args.output/"asr.json").read_text(encoding="utf-8"))
    destination = args.output/"finishing.json"
    results = json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else []
    requested_model = args.model or config.get("google_model", "gemini-flash-latest")
    if any(r.get("llm_provider")!=args.provider or r.get("llm_requested_model")!=requested_model for r in results):
        raise RuntimeError("既存結果と異なる仕上げモデルです。別の実験出力先を指定してください。")
    completed = {(r["snr"], r["method"], r["repeat"]) for r in results}
    resolved_models = set()
    cache = args.output/"finishing-response-cache"
    cache.mkdir(exist_ok=True)

    def post(url, headers, payload, **_kwargs):
        fingerprint = hashlib.sha256(json.dumps({"url":url,"payload":payload}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        cached = cache/(fingerprint + ".json")
        if cached.exists():
            data = json.loads(cached.read_text(encoding="utf-8"))
            if data.get("modelVersion"):
                resolved_models.add(data["modelVersion"])
            elif url.startswith("http://127.0.0.1:1234/") and data.get("model"):
                resolved_models.add(data["model"])
            return data
        for attempt in range(3):
            response = requests.post(url, headers=headers, json=payload, timeout=180)
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(3*(attempt+1))
                continue
            if response.status_code != 200:
                # URL・ヘッダー・レスポンス本文に含まれうる資格情報は記録しない。
                raise RuntimeError(f"AI endpoint HTTP {response.status_code}")
            data = response.json()
            if data.get("modelVersion"):
                resolved_models.add(data["modelVersion"])
            elif url.startswith("http://127.0.0.1:1234/") and data.get("model"):
                resolved_models.add(data["model"])
            save(cached, data)
            return data
        raise RuntimeError("AI endpoint retry exhausted")

    def generate(system, prompt, name, schema):
        model = args.model or config.get("google_model", "gemini-flash-latest")
        return call_ai_json(args.provider, config.get("google_api_key", "") if args.provider=="google" else config.get("lmstudio_api_key", ""), model,
                            system, prompt, name, schema, post=post,
                            lmstudio_base=lambda value: value, lmstudio_model_id=str,
                            lmstudio_reasoning=lambda *_: {}, providers={"google","lmstudio"},
                            ai_efforts={"cleanup": "medium"}, base_url="http://127.0.0.1:1234/v1",
                            **({"max_output_tokens":2048} if args.provider=="lmstudio" else {}))

    for repeat in range(args.repeats):
        for snr in SNRS:
            for method in ["standard", "reuse"]:
                if (snr, method, repeat) in completed:
                    continue
                rows = sorted([r for r in source if r["snr"] == snr and r["method"] == method], key=lambda r:r["id"])
                segments = [{"id":r["id"], "speaker":"PUBLIC_SPEAKER", "start":i*10., "end":i*10.+r["seconds"], "text":r["text"]}
                            for i,r in enumerate(rows)]
                nonempty = [s for s in segments if s["text"].strip()]
                def jev(state, questions):
                    return post("https://api.typesafe.ai/v1/systemone",
                                {"Authorization":"Bearer " + config["typesafe_api_key"], "Content-Type":"application/json"},
                                {"state":state, "model":config.get("typesafe_model", "jev-latest"), "questions":questions})
                status = lambda message: print(message, flush=True)
                print(f"FINISH_START {snr} {method} repeat={repeat}", flush=True)
                reviews, usage = review_transcript(nonempty, None, jev, status, lambda:None,
                                                   model=config.get("typesafe_model", "jev-latest"))
                # 中は対象発話だけを読むため、候補ごとの独立実行でも同じ入力になる。
                after_by_id = {s["id"]:s for s in segments}
                def repair_one(segment_id):
                    corrected = repair_recommended_segments(segments, {segment_id:reviews[segment_id]}, generate,
                                                            lambda _message:None, lambda:None, effort="medium")
                    return next(s for s in corrected if s["id"]==segment_id)
                candidates = [sid for sid,review in reviews.items() if review.get("flagged")]
                with ThreadPoolExecutor(max_workers=4) as pool:
                    tasks = {pool.submit(repair_one,sid):sid for sid in candidates}
                    for task in as_completed(tasks):
                        corrected = task.result()
                        after_by_id[corrected["id"]] = corrected
                        print(f"REPAIR_DONE {snr} {method} {corrected['id']}", flush=True)
                after = list(after_by_id.values())
                after_by_id = {s["id"]:s for s in after}
                output_rows = []
                for row in rows:
                    fixed = after_by_id[row["id"]]
                    raw, revised, reference = row["text"], fixed["text"], row["reference"]
                    raw_norm, revised_norm, ref_norm = map(normalize, [raw, revised, reference])
                    output_rows.append({**row, "after":revised, "flagged":bool(reviews.get(row["id"],{}).get("flagged")),
                                        "changed":raw != revised, "substantive_changed":raw_norm != revised_norm,
                                        "edit_chars":distance(raw_norm, revised_norm), "raw_chars":len(raw_norm),
                                        "reference_chars":len(ref_norm), "cer_before_errors":distance(ref_norm,raw_norm),
                                        "cer_after_errors":distance(ref_norm,revised_norm), "missing":not raw_norm,
                                        "review":fixed.get("recommended_review")})
                results.append({"snr":snr, "method":method, "repeat":repeat, "rows":output_rows,
                                "jev_usage":usage, "llm_provider":args.provider,
                                "llm_requested_model":args.model or config.get("google_model"),
                                "llm_resolved_models":sorted(resolved_models)})
                save(destination, results)
                print(f"FINISH_DONE {snr} {method} repeat={repeat}", flush=True)


def summarize(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "Yu Gothic"
    results = json.loads((args.output/"finishing.json").read_text(encoding="utf-8"))
    summary = []
    for result in results:
        rows, n = result["rows"], len(result["rows"])
        refs = sum(r["reference_chars"] for r in rows)
        summary.append({"snr":result["snr"], "method":result["method"], "repeat":result["repeat"], "n":n,
                        "changed":sum(r["changed"] for r in rows),
                        "correction_pct":100*sum(r["changed"] for r in rows)/n,
                        "substantive_correction_pct":100*sum(r["substantive_changed"] for r in rows)/n,
                        "edit_pct":100*sum(r["edit_chars"] for r in rows)/max(1,sum(r["raw_chars"] for r in rows)),
                        "cer_before_pct":100*sum(r["cer_before_errors"] for r in rows)/refs,
                        "cer_after_pct":100*sum(r["cer_after_errors"] for r in rows)/refs,
                        "missing":sum(r["missing"] for r in rows), "flagged":sum(r["flagged"] for r in rows)})
    save(args.output/"summary.json", summary)
    plt.rcParams["font.size"] = 12
    fig, axes = plt.subplots(3, 1, figsize=(8, 11), constrained_layout=True)
    x, width = np.arange(len(SNRS)), 0.35
    for method, label, color, shift in [("standard","おすすめ", "#3879b3",-width/2),("reuse","RE-USE", "#d38129",width/2)]:
        selected = [next(r for r in summary if r["snr"]==snr and r["method"]==method and r["repeat"]==0) for snr in SNRS]
        for ax, metric, title in zip(axes, ["correction_pct","cer_before_pct","cer_after_pct"],
                                    ["仕上げで変更した発話の割合","仕上げ前の文字誤り率","仕上げ後の文字誤り率"]):
            values = [r[metric] for r in selected]
            bars = ax.bar(x+shift, values, width=width, label=label, color=color)
            labels = [f"{r['correction_pct']:.1f}%\n({r['changed']}/{r['n']})" for r in selected] if metric=="correction_pct" else [f"{v:.1f}%" for v in values]
            ax.bar_label(bars, labels=labels, padding=4)
            ax.set_title(title)
            ax.set_xticks(x, [f"{snr} dB" for snr in SNRS])
            ax.set_xlabel("入力SNR（小さいほど雑音が強い）")
            ax.set_ylabel("割合（%）")
            ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylim(0,110)
    cer_max = max(r[k] for r in summary for k in ["cer_before_pct","cer_after_pct"])
    for ax in axes[1:]:
        ax.set_ylim(0, max(10,cer_max*1.25))
    axes[0].legend(loc="upper right")
    totals = {method:(sum(r['changed'] for r in summary if r['method']==method),sum(r['n'] for r in summary if r['method']==method)) for method in ['standard','reuse']}
    axes[0].set_title("仕上げで変更した発話の割合\n全体：" + " ／ ".join(f"{label} {100*totals[method][0]/totals[method][1]:.1f}% ({totals[method][0]}/{totals[method][1]})" for method,label in [('standard','おすすめ'),('reuse','RE-USE')]))
    fig.suptitle(f"公開JSUT {args.samples}発話 × 白色雑音3条件・Whisper base\nJev＋Qwen3-VL-8B おすすめ仕上げ 中（1回測定）", fontsize=13)
    fig.savefig(args.output/"comparison.png", dpi=180)
    fig.savefig(args.output/"comparison.svg")
    print(json.dumps(summary,ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "transcribe", "finish", "summarize"])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--provider", choices=["google","lmstudio"], default="google")
    parser.add_argument("--model", default="")
    args = parser.parse_args()
    args.source, args.output = args.source.resolve(), args.output.resolve()
    try:
        globals()[args.stage](args)
    except Exception as exc:
        # 秘密情報を含む可能性がある例外文字列をログへ出さない。
        print(f"FAILED stage={args.stage} exception={type(exc).__name__}", flush=True)
        import traceback
        traceback.print_tb(exc.__traceback__)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
