---
note_type: reference-section
status: current
feature: architecture
verified: 2026-09-14
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/architecture
note_id: program-system-map-section-04
title: システム全体構造・データフロー・設定の所在：外部サービス・外部ツール
summary: 外部サービス・外部ツール。出典ノート「システム全体構造・データフロー・設定の所在」の分割本文。
parent_note_id: program-system-map
source_path: 10-Architecture/system-map.md
source_sha256: b51430e47959bba035a47fefde19f5942b7014f183c331b6cecd7d7207d6ea14
source_body_lines:
- 146
- 172
split_on: '2026-10-11'
---

# システム全体構造・データフロー・設定の所在：外部サービス・外部ツール

親索引・状態・確認版：[[10-Architecture/10-System/system-map/00-Index]]。必要な本文だけを取得する。

## 外部サービス・外部ツール

| 対象 | 用途 | 経路 |
| --- | --- | --- |
| FFmpeg | 前処理、クリップ、字幕焼き込み、サムネイル | サブプロセス（タイムアウトは環境変数で指定） |
| Whisper／WhisperX、pyannote | 文字起こし、話者分離 | Python内。Hugging Faceトークンが必要（gatedモデル） |
| AIST感情モデル | 音声感情分析 | Hugging Faceから初回取得し、ローカルで実行 |
| OpenAI、Google Gemini、LM Studio | 校正、話者特定、アウトライン、見解 | `call_ai_json` → `ai_http_worker.py`（別プロセス、リダイレクト拒否）。HTTP 429・5xxは `services/ai/client.py:post_json` が最大2回再試行（`Retry-After` は30秒まで尊重、キャンセル可）。出力上限・安全判定・拒否による未完了応答は `ensure_complete_response` が理由付きのエラーにする |
| Transformerモデル | テーマ分析、意味検索 | `transformer_analysis.py`（`MOJIOKOSI_TRANSFORMER_MODEL`） |
| Obsidian | 閲覧、仕上げ・テーマの編集 | ファイルを直接読み書きする。Obsidian本体とは通信せず、`obsidian://open?path=` で開くだけ |

## 設定の所在（現状の正本）

| 設定 | 保存先 | 書き込む処理 |
| --- | --- | --- |
| 保存先・上限・ポート・リモート公開・モデル名など | 環境変数 `MOJIOKOSI_*`（約25種） | 起動前に利用者が設定する |
| APIキー・使用モデル・LM StudioのURL | `config/tokens.json` | 手作業。モデルは画面の選択ダイアログからも書き込まれる（`update_token_model`） |
| 単語登録 | `<data>/custom_vocabulary.json` | `PUT /api/custom-vocabulary` |
| 文字起こしの既定値 | 分散している（下の注を参照） | 各所 |
| AIエフォート | ブラウザーの `localStorage`（`gurumoji.ai-efforts`）と、会話ごとの `obsidian_workbench` の `state.json` | `ai-effort.js`、`prepare` |
| 仕上げで使うAIプロバイダー | 操作ノートの `provider` プロパティ（Obsidian側） | 研究者 |
| 分析条件・コードブック | `library_items.analysis_config_json`（会話ごと） | `PUT …/analysis` |
| Vault保存先 | 生成Vaultは `vaults.json` の `root`。ResearchVaultとSoftwareはコード内で算出 | 設定UIなし |

注：文字起こしの既定値は、`views/create.html` の初期値、`app.js` の会話モード設定（`conversationModePresets`）、`JobOptions` の既定、`parse_bool` の既定、`recommend_machine_settings` に分散している。

関連：[[10-Architecture/10-System/overview|overview]]、[[20-Modules/10-Inventory/feature-inventory/00-Index|feature-inventory]]、[[20-Modules/30-Storage/obsidian-integration/00-Index|obsidian-integration]]、[[30-Data/10-Inventory/current-storage|current-storage]]、[[40-Design/40-Storage/storage-policy|storage-policy]]。
