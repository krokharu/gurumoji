---
note_id: program-current-storage
note_type: data-model
title: 現在の保存形式と拡張点
status: current
verified: 2026-09-13
tags:
  - gurumoji/program
  - gurumoji/storage
---

# 現在の保存形式と拡張点

確認元は `app.py` の `initialize_library`、`group_analysis_for_row`、出力・再取込処理、および `research_analysis.py` です。個々の研究データの内容はこの資料に含めません。

## SQLite：`data/library.sqlite3`

| テーブル | 保存しているもの |
| --- | --- |
| `library_items` | 発話JSON、話者名、会話・話者プロフィール、アウトライン、感情推定、成果物パス、元データrevision |
| 同テーブルの分析列 | `analysis_config_json`, `analysis_annotations_json`, `analysis_revision`, `analysis_updated_at` |
| 同テーブルのAI列 | 最新成功結果の `analysis_insights_json`、AI使用量 |
| `analysis_insight_requests` | AI見解のリクエストID、対象revision、fingerprint、モデル、進捗、中止・失敗・完了、使用量 |
| `analysis_runs`, `analysis_artifacts` | 固定結果の実行台帳、成果物のhash・行数・保存先 |
| `obsidian_notes` | アプリが書いたノートのID・hash・同期状態 |
| `analysis_pending_packages` | ファイル保存の中断・失敗から復旧するための一時記録。成功後に削除 |
| `speaker_registry` | 話者の共通プロフィール、属性、同意状態等 |
| `application_metadata` | 話者台帳revision、移行状態等 |
| `training_events` | 編集に由来する学習イベント |
| `output_import_provenance` | 出力ファイル取込の出所 |
| `output_import_tombstones` | 削除済み出力の再取込防止情報 |

`MOJIOKOSI_DATA_DIR` で保存先を変更できます。既存IDは会話ID・発話ID・話者台帳IDとして維持します。発話IDは英数字・アンダースコア・ハイフンを許容するため、ObsidianブロックIDへは別途変換が必要です。

## ファイル

| 場所・形式 | 現在の用途 |
| --- | --- |
| `data/media` | 原音声・動画 |
| `data/thumbnails` | 再生成可能なサムネイル |
| `data/kushinada_training` | 学習用音声クリップ・派生ファイル |
| `output/*_話者分離.json` | 機械可読な文字起こし結果。既存データの復旧・取込にも利用 |
| `output/*_話者分離.txt`, `.srt` | 閲覧用文字起こし・字幕 |
| `output/*_アウトライン.txt`, `*_感情分析.json`, `*_感情分析.csv` | 任意処理の結果 |
| `output` のSVG・MP4 | ワードクラウド・字幕焼き込み動画 |
| 分析出力APIのJSON／CSV／Excel | 保存済み入力から必要時に生成してダウンロード |
| `tokens.json` | 秘密情報を含むローカル設定。Vaultへ出力しない |

通常の分析GETには形態素・係り受け等のプレビュー上限があります。固定保存APIは全件を再取得し、`data/analysis_store` のCSV／JSONと `ResearchVault` のノートへ保存します。AI仕上げの校正前後・議題の根拠も同じ保存層を使います。

## 今回補った点と後続工程

1. 全件出力を使い、入力スナップショット・実行条件・結果を実行IDで固定保存する。
2. DB上の最新版と、引用された過去版を区別する。
3. 見解・研究メモ・手法・根拠をMarkdownで関連付ける。
4. 組み込み手法の共通契約を設ける。外部分析結果の取り込みは後続工程とする。
5. ファイルとDBの同期途中で失敗しても、既存の編集保存と復旧動作を維持する。

現在の詳細：[[analysis-storage-v1]]。全体設計：[[40-Design/storage-policy]]、[[40-Design/sync-contract]]。
