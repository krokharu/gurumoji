---
note_id: program-module-map
note_type: module-index
title: 機能・コード・テストの対応表
status: current
verified: 2026-09-25
tags:
  - gurumoji/program
---

# 機能・コード・テストの対応表

コードのパスは `src/gurumoji/` から、それ以外（`tests/`、`docs/`、`scripts/`、`run.bat` など）はリポジトリルートからの相対パスです。2026-09-25 の `app.py` 分割で移った関数の一覧は [[70-Changes/app-py-phase5]] と同じフォルダーの JSON にあります。資料とコードの関連付けには、行番号より変更に強いファイル名・関数名を使います。

2026-09-14の優先修正：`obsidian_layout.sync_themes/sync_finishing`による人のノート保護、`obsidian_finishing.prepare/save_note`と`analysis_store.write_atomic(create_only=True)`による既存ノート保護、比較APIの`input_fingerprints`照合、`transcript_preparation.initialize`の更新待ち伝播トリガー、`static/app.js`の未保存・応答順序制御。詳細と検証先は[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]。

| 機能 | 実装・入口 | 主な検証先 |
| --- | --- | --- |
| 起動・更新 | `run.bat`, `run_launcher.ps1` | `tests/test_launcher.py`, `tests/test_ui_defaults.py` |
| 初期セットアップ | `setup_gui.bat`, `setup_gui.ps1` | `tests/test_setup_gui.py` |
| Colab | `notebooks/Gurumoji_Colab.ipynb` | `tests/test_colab.py` |
| マシン診断 | `services/machine_profile.py`: `get_machine_profile`, `detect_machine_profile`, `system_activity_snapshot` | `tests/test_machine_profile.py` |
| 音声前処理・空白補完 | `services/transcription/job_runner.py`: `run_transcription_job`（ASR、話者分離、任意の仕上げ、保存までのジョブ実行）; `services/transcription/audio.py`, `segments.py`; `app.py` は実行時依存を渡す入口 | `tests/test_audio_preprocess.py`, `tests/test_gap_supplement.py`, `tests/test_pipeline_regressions.py` |
| 文字起こし整形・確認レポート | `services/transcription/formatting.py`: `transcript_formatting_result`, `normalize_transcript_punctuation`。`app.py` は既存の呼び出し名と依存の接続を保持 | `tests/test_transcript_formatting.py`, `tests/test_pipeline_regressions.py` |
| 音声感情分析 | `services/emotion.py`: `run_aist_emotion_analysis`, `build_emotion_analysis_summary`（`app.py` は依存を渡す入口）; `docs/EMOTION_ANALYSIS.md`, `scripts/setup_emotion.bat`, `scripts/bootstrap_s3prl.py` | `tests/test_emotion_batch.py`, `tests/test_pipeline_regressions.py` |
| ライブラリ・DB初期化 | `services/library_schema.py`: `initialize_library`; `services/library_store.py`: `library_row`, `library_public`, `upsert_library_item`; `services/library_rows.py`: `row_segments`, `ensure_segment_ids`; `services/output_import.py`: 既存出力の取り込み | `tests/test_backend_safety.py`, `tests/test_analysis.py` |
| 話者管理 | `handlers/speaker_registry.py`: `SpeakerRegistryHandler`; `web/speaker_routes.py`; `web/export_routes.py`: `export_speaker_registry`; 話者名の推定は `services/speaker_identification.py`、再推定は `handlers/speaker_identification.py` | `tests/test_speaker_registry.py` |
| 編集保存と回復 | `services/library_edits.py`: `normalize_edited_segments`, `_update_library_from_payload_locked`; `services/edit_transactions.py`: マニフェスト・回復; 削除は `web/library_deletion.py` | `tests/test_edit_recovery.py`, `tests/test_outputs.py` |
| 会話集計・手動分析 | `services/group_analysis.py`: `group_analysis_for_row`, `normalize_analysis_config`, `normalize_analysis_annotations`; `services/group_analysis_exports.py`: レポート・CSV; `services/analysis_annotations.py`: 分析設定・注釈の保存 | `tests/test_analysis.py`, `tests/test_method_expert_samples.py` |
| 日本語解析・統計 | `research_analysis.py`: `build_research_analysis`, `_linguistic_analysis`, `_statistics_analysis` | `tests/test_research_analysis.py` |
| 見解・KWIC・特徴語 | `analysis_insights.py`: `build_content_analysis`, `search_kwic`, `create_ai_insights`, `validate_findings` | `tests/test_content_analysis.py` |
| AI見解の実行と保存 | `services/analysis_jobs.py`: `run_analysis_insight_job`, `start_analysis_insights_command`, `cancel_analysis_insights_command`; HTTPは `web/analysis_routes.py` | `tests/test_content_analysis.py`, `tests/test_content_browser.py` |
| 手法ごとの専門家定義 | `method_experts.py`: `ExpertCatalog`, `review_for_analysis`, `ai_context`, `attach_method_reviews`, `report_lines`; `app.py`: `group_analysis_for_row`; `services/analysis_jobs.py`: `start_analysis_insights_command`; `web/analysis_view_routes.py`: `get_analysis_experts`。定義はSoftware Vaultの `50-Analysis-Methods/10-Experts`（ADR-115）。実行環境ごとの `<data>/local_knowledge/…` があれば同じ相対パスで上書き・追加する（ADR-120） | `tests/test_method_experts.py`, `tests/test_method_expert_samples.py` |
| 手法別の分析画面 | `web/analysis_view_routes.py`: `get_analysis_method_overview`; `method_experts.py`: `method_overview`; `static/app.js`: `renderMethodAnalysis`, `buildExpertDetails`, `methodResultPanels`（パネルは `data-analysis-method` で対応付け、ADR-116） | `tests/test_analysis_method_view.py` |
| AI通信・モデル設定 | `ai_http_worker.py`; `services/ai/client.py`: `call_ai_json`; `services/ai/settings.py`: `TokenConfig`, `configured_ai_credentials`, `available_ai_models`（`app.py` の `call_ai_json` は依存を渡す入口） | `tests/test_ai_http_worker.py`, `tests/test_ai_model_settings.py`, `tests/test_ai_scaling.py` |
| 根拠付きAI仕上げ | `ai_finishing.py`: `clean_transcript`, `create_outline`, `finishing_changes` | `tests/test_ai_finishing.py`, `tests/test_pipeline_regressions.py` |
| 手法別の固定保存・Vault | `analysis_method_registry.py`, `analysis_store.py`; `services/analysis_archive.py`: `archive_group_analysis`, `archive_ai_finishing` | `tests/test_analysis_storage.py` |
| 4 Vaultへの書き出し | `vault_registry.py`: `VaultRegistry.publish_input`, `retire_input`, `publish_analysis`; `analysis_store.py`: `AnalysisStore.publish_vaults`, `refresh_vaults`; `app.py`: `publish_input_vault`, `retire_input_vault`, `whisper_vault_settings` | `tests/test_four_vaults.py`, `tests/test_vault_coverage.py` |
| 会議議事録・インタビュー比較の独立保存 | `services/interview_comparison.py`: `build_interview_comparison`; `services/analysis_archive.py`: `archive_meeting_minutes`, `archive_interview_comparison`, `interview_comparison_datasets`; `analysis_store.py`: `analysis_run_members`, `list_comparisons`; `static/interview-comparison.js` | `tests/test_vault_coverage.py`, `tests/test_meeting_minutes.py`, `tests/test_interview_comparison.py` |
| 保存履歴・Vaultからの発話参照 | `static/analysis-storage.js` | `tests/test_content_browser.py` |
| 分析出力 | `services/group_analysis.py`: `analysis_csv_rows`; `web/export_routes.py`: `export_library_analysis_json` ほか; `research_analysis.py`: `build_analysis_workbook` | `tests/test_analysis.py`, `tests/test_research_analysis.py` |
| 編集差分の学習データ | `services/training_corpus.py`: `training_export_contents`, `write_training_exports`, `refresh_training_exports`; `web/training_routes.py` | `tests/test_backend_safety.py`, `tests/test_outputs.py` |
| UI・分析実行・引用から音声確認（画面構成は [[20-Modules/ui-screens]]） | `templates/index.html`, `static/app.js`, `static/analysis-visualizations.js`（共通カード・チャート・ナビゲーション）, `static/analysis-method-view.js`（手法別表示・発話分類）, `static/analysis-content.js`, `static/analysis-execution.js`, `static/style.css`, `static/ai-effort.css` | `tests/test_content_browser.py`, `tests/test_browser_e2e.py`, `tests/test_ui_defaults.py` |
| メディアパス・リモートアクセス | `web/security.py`: 認証・CSRF・サイズ上限; `web/library_routes.py`: メディアAPI; `services/media_files.py`; `diagnostics.py`: ローカルパスの非表示 | `tests/test_media_paths.py`, `tests/test_backend_safety.py` |

## 現在の分析API

| 操作 | API |
| --- | --- |
| 分析取得・条件保存 | `GET/PUT /api/library/<id>/analysis` |
| 文脈検索・CSV | `GET /api/library/<id>/analysis/kwic` |
| AI生成・状態 | `POST/GET /api/library/<id>/analysis/insights` |
| AI中止 | `POST /api/library/<id>/analysis/insights/cancel` |
| JSON・Excel・CSV | `GET /api/library/<id>/analysis/export.json`, `export.xlsx`, `export.csv` |

固定保存・履歴・再試行・成果物取得の実装済みAPIは [[30-Data/analysis-storage-v1]] に記載します。後続の差分取り込み等の設計は [[40-Design/sync-contract]] を参照してください。

## 検証の実行

リポジトリルートで `python -m unittest discover -s tests -q` を実行します。ブラウザーテストはEdge／Chrome／Chromium、メディアテストの一部はFFmpegを利用します。テスト結果の記録には実行日・対象commitまたは作業ツリー識別値・成功／失敗／スキップ理由を付けます。

このノートはテストの対応表であり、現在の環境での全テスト合格を自動保証するものではありません。

機能の分類（Core／Duplicate／Legacyなど）は [[20-Modules/feature-inventory]]、Obsidian連携の書き込み主体と競合処理は [[20-Modules/obsidian-integration]] を参照してください。
