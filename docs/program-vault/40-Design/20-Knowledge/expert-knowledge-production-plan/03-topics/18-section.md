---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-18
title: 配布用専門家の知識・プロンプト制作計画：2026-09-27 13:24 UTC A100 80B単発実測の準備
summary: 2026-09-27 13:24 UTC A100 80B単発実測の準備。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 579
- 590
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：2026-09-27 13:24 UTC A100 80B単発実測の準備

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

### 2026-09-27 13:24 UTC A100 80B単発実測の準備

- `scripts/prepare_a100_80b_probe.py`で架空入力専用の[80B実測Notebook](https://drive.google.com/file/d/1jkiDmNr9ywE34M1dpTbljpagmQp6YV_K/view)を作成し、共有Driveへアップロードした。Driveで確認したファイルは15,877 bytes、同じfile IDで更新済み。ローカル版SHA-256は`c42e9f73a88eb21a7c161fbd806551af27a59ada9edd211aa7eebf62ec320e46`。Driveのsize/場所/更新時刻を再読したが、raw bytes hashの再取得照合は行っていない。
- Notebookは利用者がColabでA100 High RAMを選んで`Run all`し、Drive認可した後に実行される。A100と空きGPU/ディスクを確認し、commit固定のCUDA llama.cppをビルドし、Qwen公式80B Q4_K_Mファイル48,410,988,384 bytesを固定revisionから取得してSHA-256 `d103b2733ec1012a52d01edda66b7e5c24ae50508c9f99f5297ea459ef3c061a`を検証する。8K context、1並列、架空入力1件でJSON/evidence ID、時間、GPU使用量を測り、結果JSONを`/content`と共有Driveへ保存する。計算部分は最大55分を目安に止めるが、対話的Drive認可と終了後のDriveアップロードはその計測外である。
- 13:24 UTCのフォルダー再確認では新Notebookと従来3ファイルの計4件だけで、80B実測結果JSON・A100モデルロード・推論の証跡はまだない。Colabランタイムをこの接続から直接起動するAPIはない。Solの読み取り専用静的監査では、Drive投入を止める確定的な重大バグは見つからなかった。

### 2026-09-27 14:26 UTC A100 80B合成probe実測

- 最初の実行は80GB向けの空きVRAM条件（70,000 MiB）で40GB A100をpreflight時に停止した。再実行では40GB対応としてGPU 30層・context 4,096に下げたprofileを使い、Qwen3-Next-80B Q4_K_MのrevisionとSHA-256を検証して、短い架空入力からJSONとevidence IDを返した。
- 実測は全体2,126.06秒、CUDA build 936.08秒、モデルdownload 781.54秒、model load 141.08秒、推論4.53秒。usage 119 tokens、peak VRAM 28,956 / 40,960 MiB、推論後の空き11,486 MiB。全体wall timeにはbuild/downloadが大半を占め、GPU推論時間の代用にはしない。
- 合格範囲はモデルload・部分GPU offload・4K設定での短い合成schema確認まで。計画に書いていた8K contextは未実施で、実文献・根拠品質・本番worker適合性も未評価。[結果JSON](https://drive.google.com/file/d/1Tb3W0TGWWIvChN30qTqd_6R53IcRGOst/view)
