---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-19
title: 配布用専門家の知識・プロンプト制作計画：2026-09-28 01:37 UTC A100 context拡大probe準備
summary: 2026-09-28 01:37 UTC A100 context拡大probe準備。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 591
- 607
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：2026-09-28 01:37 UTC A100 context拡大probe準備

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 01:37 UTC A100 context拡大probe準備

- `scripts/prepare_a100_80b_context_probe.py`で8K/16K段階probeを作成し、[Notebook](https://drive.google.com/file/d/11anbU7pIFYN3pvosIlwbyfrIl0KsPvAu/view)を共有Driveへ追加した。実際のchat templateを適用後、固定model tokenizerで入力token数を測って各contextの75%を埋める。8Kが通った場合のみ16Kへ進み、最大64出力tokensでschema/evidence ID、VRAM、load・推論時間を記録する。入力は架空反復のみで、実文献は送らない。
- NotebookはDrive metadataで21,725 bytesと保存先を確認済み。まだ未実行。Colab runtime操作APIはないため次は利用者がNotebookを開いて`Run all`し、返却されたJSONをDriveへ置く必要がある。80Bは引き続き実測候補で、既存production workerの32B-AWQ profileは変更していない。

### 2026-09-28 11:00 UTC A100 FreeTxt追加分析

- 固定Qwen3-32B-AWQでFreeTxt §§3.2、3.4、4から3回生成し、英語モデルページの約95%と著者らのウェールズ語実験約73%を別根拠として記すClaim、および要約機能が調査回答より長文文書に向いていたというClaimの2件を未承認候補として受理した。最初の要約Claimは比較方向を逆転したため受理せず、方向を明記した抜粋で再生成した。
- 3生成合計は2,608 input tokens、354 output tokens、64.301秒。A100 High-RAM事前確認でGPUとTransformers 4.51.3 / Tokenizers 0.21.4 / Hub 0.30.2を検証。Colab残高差は0.53 CU、停止後の残高87.88 CU。選択節のSource SHA-256は編集済み根拠テキストを指し、PDF原本のhashではない。
- primary JobStoreは82 accepted Commit（81 Claim、82 Source）、17/17領域、整合性エラー0、Pack 0。P6は進行中のまま。体系的な重複・不足整理、全専門家の反復評価、配布承認は未完了。

### 2026-09-28 11:22 UTC A100 会話重複率・分母分析

- Levinson & Torreira (2015) §5.2.1–5.2.2から、NXT-Switchboard 348会話（約38時間）における全floor transfer中30.1%のbetween-overlap、および無音を除いた発話信号の95.3%が単一話者だったという2 ClaimをA100で生成して根拠照合した。異なる分母を個別に保持し、未承認候補として受理。
- 固定Qwen3-32B-AWQ、A100-SXM4-80GB High-RAMで2推論を実行。合計1,548 input tokens、251 output tokens、45.844秒。残高差0.33 CU、停止後残高87.55 CU。
- primary JobStoreは86 accepted Commit（85 Claim、86 Source）、全17領域、整合性エラー0、Pack 0。P6の体系整理・反復評価は引き続き未完了。
