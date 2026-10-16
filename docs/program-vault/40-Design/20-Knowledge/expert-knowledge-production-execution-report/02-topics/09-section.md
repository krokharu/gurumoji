---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-09
title: 専門家知識制作・実行報告書：2026-09-27 14:26 UTC A100 Qwen3-Next-80B 合成probe
summary: 2026-09-27 14:26 UTC A100 Qwen3-Next-80B 合成probe。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 159
- 172
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-27 14:26 UTC A100 Qwen3-Next-80B 合成probe

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-27 14:26 UTC A100 Qwen3-Next-80B 合成probe

- 最初のNotebookはA100の空きVRAMを70,000 MiB以上要求し、40GB A100を事前確認で終了した。これは容量不足の実測ではなく、80GB向けpreflight条件との不一致だった。
- 40GB用Notebookを使った再実行は `NVIDIA A100-SXM4-40GB` 上で成功した。Qwen公式 `Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf` を固定revisionから取得しSHA-256を照合、llama.cppもcommit `9adc7f420c37641921b32e326b3d4a538256b878` に固定した。GPUへ30層を載せ、残りをhost RAM側で動かす構成だった。
- 実際のcontext設定は4,096 tokens、入力72 tokens、出力47 tokensであり、当初計画の8K入力試験ではない。架空の1要求に対してJSON schemaと `SYNTHETIC-1` のevidence IDは適合した。実文献の根拠支持・専門家知識の品質を測った結果ではない。
- run全体は2,126.06秒（35分26秒）。うちCUDA llama.cpp buildは936.08秒（15分36秒）、モデルdownloadは781.54秒（13分02秒）、model loadは141.08秒、推論は4.53秒だった。全体時間をGPU計算時間とは扱わない。usageは119 tokens。最大GPU memoryは28,956 MiB / 40,960 MiB、推論後の空きは11,486 MiB。
- [実測JSON](https://drive.google.com/file/d/1Tb3W0TGWWIvChN30qTqd_6R53IcRGOst/view)を共有Driveで確認した。これにより80Bモデルの部分GPU offload・ロード・短い合成生成までは通ったが、本番worker、Drive roundtrip、文献処理を実証したものではない。

### 2026-09-28 01:37 UTC A100 8K/16K context probe準備

- 4K実測を受け、`scripts/prepare_a100_80b_context_probe.py` と [8K/16K context probe Notebook](https://drive.google.com/file/d/11anbU7pIFYN3pvosIlwbyfrIl0KsPvAu/view) を作成・共有Driveへ追加した。Notebookは8,192 contextを先に、合格後のみ16,384 contextを試す。各段階で会話template込みのtokenizer計測を行い、contextの75%を使う架空入力、最大64出力tokens、1並列、30 GPU layers、VRAM・ロード・推論時間・schema/evidence IDを記録する。
- Drive metadataでNotebook名、21,725 bytes、保存先folderを照合した。Notebookは未実行で、A100実測結果はまだない。Colab runtimeをこの接続から起動するAPIはないため、利用者がNotebookを開き`Run all`する必要がある。新runtimeでは前回と同様にビルド・モデル取得時間も55分budgetへ含まれる。
