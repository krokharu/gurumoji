---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-10
title: 配布用専門家の知識・プロンプト制作計画：12. 実行記録（2026-09-27）
summary: 12. 実行記録（2026-09-27）。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 454
- 469
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：12. 実行記録（2026-09-27）

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

## 12. 実行記録（2026-09-27）

以下は当日の時系列記録であり、途中の「未実装」「現在」はその記録時点を指す。現行の実装・未実行状況は末尾の「計画表の工程番号に対する実状態」と「07:28 UTC Colab A100 定期監視・本番worker更新」を優先して読む。

### 完了した基盤作業

- P0 inventory: 専門家定義17件、文献ノート76件、未解決参照0件を確認。出力は集計値に限定し、ノート本文や個人パスを出さない。
- P0 local preflight: RTX 5070の総VRAM 12,227 MiB・空き1,977 MiB、loopback LM Studio APIと5モデルを検出。`qwen/qwen3-8b`へ合成timeout状態だけを渡すJSON-schema分類を実行し、70 input + 26 output = 96 tokens、2.615秒で正しい`retryable`判定を得た。`json_object`応答形式はLM Studioで400となり、JSON schema指定へ変更。96 token上限ではthinkingに消費して空出力だったため256へ変更した。個人データは未送信。
- P0再計測: `inventory`で専門家17、文献ノート76、参照108、未解決0。metadata-only `source-audit --all-experts`で権利経路未確認100、status/correction status欠落0。LM Studio preflightはloopback API到達、RTX 5070空き1,574 MiB、モデル5件を確認し、モデルのload/inferenceは行わない。
- P0ローカル例外分類probe: 合成した5ケースをQwen3-8Bへ1回で渡し、既定rubricと4/5一致した。送信前にDNS解決が失敗したケースを`manual_review`とし、明示的に安全な再試行を保留する保守的な誤分類が1件あった。336 input + 136 output = 472 tokens、13.1秒。自動retryにモデル判定を使わず、Pythonが期限・状態・重複採用を決定する方針を維持する。実ログや個人データは送信していない。
- P0 Colab: 既存の接続確認Notebookの保存済み実行結果でA100、CUDA利用、512x512計算成功を確認。Drive APIからColabの実行ランタイムを直接操作する接続はない。
- P0合成roundtrip準備: `scripts/prepare_p0_colab_roundtrip.py`で世代1・7日期限の合成Job、承認Source registry、worker source bundle、A100確認Notebookを作成。合成データ以外を含まないbundle（27,358 bytes、SHA-256 `ad4041cee5600623ac5e9ca5a6855b3b9653266266e6de429d8626773c7c0415`）とNotebook（45,804 bytes、SHA-256 `1d2c0071285b9109458564a6bb97857d6dea1da3eb301a1e110d65d8a1dcc327`）を共有Driveへ新規アップロードし、Driveからの再取得hashとsize一致を確認。workerのローカル隔離preflight結果は複製state上で2 Artifactを一度受理し、同一ZIP再送が同じCommitへ冪等で戻ることを確認。実Jobのaccepted_generationは0のまま保護した。実A100実行・Drive保存Notebook出力・戻りZIP受理は未完了。Notebookは小さなCUDA演算でA100割当を確認し、workerは決定論的fixtureを使うため、このP0確認自体はLLM推論ではない。
- P0定期監視Notebook更新（06:06 UTC時点）: `scripts/add_p0_colab_runtime_scheduler.py`で60分ごとのRuntime/GPU・ジョブ候補確認、A100割当時の軽量な256x256 FP16健全性確認、80分ごとのbundle/resultのID・size・SHA-256照合、同じjob/generation用監視JSONの更新を行う。この版では本番model adapterは未実装だった。Colabの実行継続は保証されない。06:06 UTCにDrive上の同じfile IDへ更新し、Notebookは65,711 bytes、SHA-256 `5ef9b866381f1859035e148c81f0e2e6a6904cc1680c8c9b1319d935a1bb1ecb`。raw readbackは全byte一致。06:14 UTCの再接続後確認ではフォルダーにはNotebook、入力bundle、接続確認Notebookの3件だけで、結果ZIP・監視JSONは未作成。Run all後のA100実行は未確認。
- P1契約・台帳コア: `src/gurumoji/knowledge_builder/contracts.py` と `job_store.py` を追加。source/claim/job/commit/evaluation/packの閉じたschema、UTC deadline、generation・attempt・directive照合、SHA-256・canonical JSON・schema・パス検証、同一Commit再送の再検証、単一採用、accepted Commit参照、PackのClaim/Source照合と専門家ID照合を実装。Pack参照中のJobは再generationできない。Local Papers Packと任意runtime/documentation/licenseファイルは未実装の間fail closed。
- Sol最終レビュー: P1で指摘された再送、成果物照合、専門家ID、Job/Pack世代安定性のブロッカーは修正済みと確認。
