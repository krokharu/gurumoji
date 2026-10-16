---
note_type: reference-section
status: current
verified: 2026-09-14
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/features
note_id: program-feature-inventory-section-03
title: 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：Optional：なくてもアプリは成立する機能
summary: Optional：なくてもアプリは成立する機能。出典ノート「機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）」の分割本文。
parent_note_id: program-feature-inventory
source_path: 20-Modules/feature-inventory.md
source_sha256: 452c464c3fa60e7f2a4cc230a48433daf715bc2dd5508dc9ea8a77ac12a373e4
source_body_lines:
- 51
- 73
split_on: '2026-10-11'
---

# 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：Optional：なくてもアプリは成立する機能

親索引・状態・確認版：[[20-Modules/10-Inventory/feature-inventory/00-Index]]。必要な本文だけを取得する。

## Optional：なくてもアプリは成立する機能

| 機能 | 状態 | 入口 | 実装 | 補足 |
| --- | --- | --- | --- | --- |
| Obsidianで仕上げる（既定） | Implemented | 新規作成「AI仕上げ」のチェック（既定ON）、作業画面の保存バー「Obsidianで仕上げ」／`POST/GET …/obsidian-finishing` | `ObsidianWorkbench`、`start_obsidian_watcher`、`run_obsidian_finishing` | 下記「アプリ内AI仕上げ」と目的が重複する（Duplicate） |
| アプリ内AI仕上げ（ジョブ内の校正・話者特定・アウトライン） | Implemented | `finish_in_obsidian=0` のときだけ有効。新規作成の文章整形モード「おすすめ」「高度」、または「Obsidianに保存してあとで整える」を外したときに使われる（`handlers/transcription_start.py`） | `run_transcription_job` 内。校正の手順は `run_full_cleanup`（Obsidian方式と共通）、ほかに `clean_recommended_segments_with_ai`、`detect_speaker_names_with_ai`、`create_outline_with_ai` | Duplicate |
| 話者名のAI再特定 | Implemented | 作業画面「会話・話者」の「自己紹介から話者名を再特定」／`POST …/speaker-identification` | `rerun_library_speaker_identification` | ジョブ・仕上げと合わせて入口が3つ（Duplicate） |
| 音声感情分析（AIST） | Implemented | 新規作成「設定」の「音声感情分析」 | `run_aist_emotion_analysis` | 追加の依存とモデル同意が必要 |
| 字幕付き動画 | Implemented | 出力形式 | `write_subtitled_video_assets`、`burn_ass_subtitles_into_video` | なし |
| 会議議事録・タスク候補（規則ベース） | Implemented | 作業画面「議事録・アウトライン」／`GET …/meeting.json`、`…/meeting-tasks.csv`、`…/meeting-minutes.md`、`GET/POST …/meeting-obsidian` | `build_meeting_minutes`、`format_meeting_minutes_markdown`、`obsidian_finishing.meeting_minutes_note`、`archive_meeting_minutes` | Markdown生成が2実装、Vaultへの出力が2系統（Duplicate） |
| 分析エクスポート（JSON／Markdown／Excel／CSV） | Implemented | 分析ヘッダー／`GET …/analysis/export.{json,md,xlsx,csv}` | `export_library_analysis_*`、`build_analysis_workbook` | 現在値を都度生成する。固定保存のCSVとは目的が異なるが、画面上で区別しにくい |
| KWIC・見解 | Implemented | 分析内容／`GET …/analysis/kwic` | `analysis_insights.search_kwic`、`build_content_analysis` | KWICは固定保存も可能 |
| AI見解 | Experimental | 分析内容／`GET/POST …/analysis/insights`、`POST …/cancel` | `run_analysis_insight_job`、`create_ai_insights` | `analysis_insight_requests` |
| アウトライン（予定と結果） | Stable | 作業画面の見出し直下／`GET /api/library/<id>` の `session_outline` | `analysis_insights.build_session_outline`、`row_session_outline` | 質問ガイド・自動アウトライン・保存済みテーマの結合。再計算はしない |
| Transformerテーマ分析・意味検索 | Experimental | 分析内容／`GET/POST …/analysis/transformer`（`mode`：自動・候補・手動）、`…/cancel`、`GET …/semantic-search` | `run_transformer_analysis_job`、`transformer_analysis.py` | モデルの取得が必要。手動テーマは `config.transformer_topics` に保存 |
| グループインタビュー比較 | Experimental | 分析・可視化の下部の折りたたみ／`POST /api/library/interview-comparison`、`POST/GET …/runs` | `build_interview_comparison`、`archive_interview_comparison`、`static/interview-comparison.js` | 比較値は独立した固定保存runとして記録する。ブラウザーPOSTの既知課題は[[40-Design/50-Governance/known-issues/02-section#BUG：動作不良\|known-issues#BUG：動作不良]] |
| 事前アンケート分析 | Implemented | 話者管理 | `app.js`（クライアント側で集計） | 話者台帳の属性を使う |
| くしなだ学習データ | Implemented | 一覧の学習状態／`GET /api/training`、`…/corrections.jsonl`、`…/manifest.csv` | `record_training_corrections`、`write_training_exports` | `training_events`、`<data>/kushinada_training` |
| ResearchVaultのナビゲーション・グラフ・テーマ同期 | Implemented | Obsidian側 | `ObsidianLayout.publish_navigation`、`configure`、`sync_themes` | `.obsidian` は新規Vaultの初回だけ書く（OBS-03） |
| 4 Vaultへの書き出し | Experimental（実運用での確認は未記録） | 自動 | `vault_registry.py`、`AnalysisStore.publish_vaults`、`publish_input_vault` | [[30-Data/40-Vaults/four-vaults-v1\|four-vaults-v1]] |
| Google Colab | Implemented | `notebooks/Gurumoji_Colab.ipynb` | `is_colab_runtime` | なし |
| 保守スクリプト | Implemented | 手動 | `scripts/check_*.py`、`repair_qwen_download.py`、`bootstrap_s3prl.py`、`cleanup_env.bat`、`setup_emotion.bat` | 開発・診断用 |
