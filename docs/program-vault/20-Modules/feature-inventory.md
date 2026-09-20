---
note_id: program-feature-inventory
note_type: module-index
title: 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）
status: current
verified: 2026-09-14
updated: 2026-09-16
tags:
  - gurumoji/program
  - gurumoji/features
---

# 機能一覧と分類

2026-09-14の調査を基に作成し、コミット`1b8fe41`へ収録・プッシュ済み。2026-09-15に収録版の表記を更新した。分類は機能の位置づけを表し、問題の対応済み／未対応は[[40-Design/convergence-plan#プッシュ済みの対応状況（2026-09-15）]]と課題一覧を参照する。

**分類：** 役割による分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）。1つの機能が複数に該当する場合は、主な分類を先に書く。

**状態：**

| 状態 | 意味 |
| --- | --- |
| Implemented | 使用中 |
| Experimental | 新しい、または実データでの検証が少ない |
| Deprecated候補 | 削除前に確認が必要 |
| Planned | 未実装 |

構造とデータの流れは [[10-Architecture/system-map]]、テストとの対応は [[20-Modules/module-map]]、問題点のIDは [[40-Design/known-issues]] を参照する。

## Core：アプリの中心機能

入口の画面名は2026-09-16のUI再設計後の名称。旧画面との対応は [[20-Modules/ui-screens]]。

| 機能 | 状態 | 入口（UI／API） | 実装（呼び出し先） | DB | ファイル | Obsidian |
| --- | --- | --- | --- | --- | --- | --- |
| 文字起こし・話者分離ジョブ | Implemented | 新規作成／`POST /api/jobs`、`GET /api/jobs/<id>`、`GET /api/jobs/active`、`POST …/cancel` | `create_job` → `run_transcription_job`（FFmpeg、WhisperX、pyannote） | `library_items` | `runtime/uploads`、`runtime/output`、`<data>/media` | `ObsidianWorkbench.prepare`、`publish_input_vault` |
| 逐語録の確認・編集保存 | Implemented | 作業画面「発話の確認・編集」（`#/data/<id>`）／`PUT /api/library/<id>`、`PUT /api/jobs/<id>/transcript` | `update_library_from_payload`、`save_transcript`、編集トランザクション群（`write_edit_transaction_manifest` ほか） | `library_items`、`transcript_versions`、`training_events` | 出力を再生成 | InputVault更新、ResearchVault索引のstale化 |
| 処理済みデータ一覧・検索 | Implemented | 処理済みデータ（`#/data`）／`GET /api/library`、`GET /api/library/<id>` | `list_library`、`library_public` | `library_items` | サムネイル | なし |
| 分析・可視化（自動集計・手動コード） | Implemented | 分析・可視化（`#/analysis/<id>`）／`GET/PUT /api/library/<id>/analysis` | `group_analysis_for_row`、`research_analysis.build_research_analysis`、`save_group_analysis` | `analysis_config_json`、`analysis_annotations_json` | 解析キャッシュ | なし（保存時のみ） |
| 分析結果の固定保存 | Implemented | 「分析結果をObsidianに保存」／`POST/GET …/analysis/runs`、`POST /api/analysis/runs/<id>/vault`、`GET /api/analysis/artifacts/<id>` | `archive_group_analysis` → `AnalysisStore.save` → `publish` | `analysis_runs`、`analysis_artifacts`、`analysis_pending_packages`、`obsidian_notes` | `<data>/analysis_store` | ResearchVaultと3 Vault |

## Supporting：Coreを支える機能

| 機能 | 状態 | 入口 | 実装 | データ／ファイル | Obsidian |
| --- | --- | --- | --- | --- | --- |
| 起動・セットアップ・ライブラリ更新 | Implemented | `run.bat`、`setup_gui.bat` | `scripts/run_launcher.ps1`、`scripts/setup_gui.ps1`、`main`、`initialize_application` | `.venv`、`runtime/logs` | watcher起動、旧階層移行 |
| マシン診断・リソースモニター | Implemented | 上部バー「接続と処理装置」・新規作成「認識・話者分離」・処理状況／`GET /api/config`、`GET /api/system/activity` | `get_machine_profile`、`recommend_machine_settings`、`system_activity_snapshot` | なし | なし |
| 音声前処理・小声対策・空白補完 | Implemented | 認識設定 | `run_audio_preprocess`、`run_audio_interval_preprocess`、`merge_supplemental_asr_segments` | 一時ファイル | なし |
| 単語登録 | Implemented | 認識設定／`GET/PUT /api/custom-vocabulary` | `load_custom_vocabulary`、`save_custom_vocabulary` | `<data>/custom_vocabulary.json` | 語数とhashだけをInputVaultへ |
| 話者台帳（話者管理）・CSV入出力 | Implemented | 話者管理／`GET/PUT /api/speakers`、`POST …/import`、`GET …/export.csv` | `save_speaker_registry_records`、`import_speaker_registry_csv` | `speaker_registry`、`application_metadata` | 変更で保存分析をstaleにする（DBトリガー） |
| 会話プロファイル・会話話者連携 | Implemented | 作業画面「会話・話者」／`PUT /api/library/<id>`、`GET …/speakers.csv` | `normalize_session_profile`、`normalize_conversation_speaker_profiles` | `library_items` のJSON列 | InputVaultの会話種別 |
| 出力ファイル（TXT／JSON／SRT／アウトライン／感情CSV／ワードクラウド） | Implemented | ダウンロードリンク／`GET /api/jobs/<id>/files/<name>`、`GET /api/library/<id>/files/<name>` | `write_outputs`、`write_word_cloud` | `runtime/output` | なし |
| メディア保管・再生・サムネイル | Implemented | 作業画面「発話の確認・編集」、新規作成のファイル選択／`GET …/media`、`GET …/thumbnail`、`POST /api/source-thumbnail`、`POST /api/select-input` | `archive_media`、`stream_library_media`、`generate_video_thumbnail` | `<data>/media`、`thumbnails` | 相対パスとサイズをInputVaultへ |
| データ削除 | Implemented | 一覧・作業画面「ファイル・管理」／`DELETE /api/library/<id>` | `_delete_library_item_locked`（隔離 → DB削除 → `rmtree`） | tombstone | `retire_input_vault`（台帳を `deleted` にする）。ResearchVaultは変更しない |
| 出力JSONの自動取り込み | Implemented | 起動時 | `import_existing_outputs`、`repair_output_import_provenance` | `output_import_provenance`、`output_import_tombstones` | InputVault（`imported`） |
| リクエストのセキュリティ | Implemented | 全API | `enforce_request_security`（Host、CSRFヘッダー、リモート認証、サイズ上限） | なし | なし |
| AI接続・モデル選択 | Implemented | 上部バーのトークン表示と「接続と処理装置」／`GET /api/ai/models`、`PUT /api/ai/model`、`GET /api/ai/lmstudio-reasoning` | `available_ai_models`、`update_token_model`、`call_ai_json`、`ai_http_worker.py` | `config/tokens.json` | APIキーは書かない |
| AIエフォート（思考モード） | Implemented | AI仕上げ欄 | `ai_effort.py`、`static/ai-effort.js` | `localStorage`、`state.json` | 操作ノートに引き継ぐ |
| 逐語録の分析準備（版・確認状態） | Implemented（未コミット） | 分析 → 設定・手動分析／`PUT …/preparation`、`GET …/preparation/export.json` | `transcript_preparation.py` | `transcript_versions`、`transcript_preparations`、`transcript_preparation_events` | 件数・hashだけをInputVaultへ（[[30-Data/transcript-preparation-v1]]） |

## Optional：なくてもアプリは成立する機能

| 機能 | 状態 | 入口 | 実装 | 補足 |
| --- | --- | --- | --- | --- |
| Obsidianで仕上げる（既定） | Implemented | 新規作成「AI仕上げ」のチェック（既定ON）、作業画面の保存バー「Obsidianで仕上げ」／`POST/GET …/obsidian-finishing` | `ObsidianWorkbench`、`start_obsidian_watcher`、`run_obsidian_finishing` | 下記「アプリ内AI仕上げ」と目的が重複する（Duplicate） |
| アプリ内AI仕上げ（ジョブ内の校正・話者特定・アウトライン） | Implemented（既定では使われない） | `finish_in_obsidian=0` のときだけ有効。校正のチェック欄はUIで非表示（`data-app-finishing-only hidden`） | `run_transcription_job` 内の `clean_segments_with_ai`、`detect_speaker_names_with_ai`、`create_outline_with_ai` | Duplicate |
| 話者名のAI再特定 | Implemented | 作業画面「会話・話者」の「自己紹介から話者名を再特定」／`POST …/speaker-identification` | `rerun_library_speaker_identification` | ジョブ・仕上げと合わせて入口が3つ（Duplicate） |
| 音声感情分析（AIST） | Implemented | 新規作成「設定」の「音声感情分析」 | `run_aist_emotion_analysis` | 追加の依存とモデル同意が必要 |
| 字幕付き動画 | Implemented | 出力形式 | `write_subtitled_video_assets`、`burn_ass_subtitles_into_video` | なし |
| 会議議事録・タスク候補（規則ベース） | Implemented | 作業画面「議事録・アウトライン」／`GET …/meeting.json`、`…/meeting-tasks.csv`、`…/meeting-minutes.md`、`GET/POST …/meeting-obsidian` | `build_meeting_minutes`、`format_meeting_minutes_markdown`、`obsidian_finishing.meeting_minutes_note`、`archive_meeting_minutes` | Markdown生成が2実装、Vaultへの出力が2系統（Duplicate） |
| 分析エクスポート（JSON／Markdown／Excel／CSV） | Implemented | 分析ヘッダー／`GET …/analysis/export.{json,md,xlsx,csv}` | `export_library_analysis_*`、`build_analysis_workbook` | 現在値を都度生成する。固定保存のCSVとは目的が異なるが、画面上で区別しにくい |
| KWIC・見解 | Implemented | 分析内容／`GET …/analysis/kwic` | `analysis_insights.search_kwic`、`build_content_analysis` | KWICは固定保存も可能 |
| AI見解 | Experimental | 分析内容／`GET/POST …/analysis/insights`、`POST …/cancel` | `run_analysis_insight_job`、`create_ai_insights` | `analysis_insight_requests` |
| アウトライン（予定と結果） | Stable | 作業画面の見出し直下／`GET /api/library/<id>` の `session_outline` | `analysis_insights.build_session_outline`、`row_session_outline` | 質問ガイド・自動アウトライン・保存済みテーマの結合。再計算はしない |
| Transformerテーマ分析・意味検索 | Experimental | 分析内容／`GET/POST …/analysis/transformer`（`mode`：自動・候補・手動）、`…/cancel`、`GET …/semantic-search` | `run_transformer_analysis_job`、`transformer_analysis.py` | モデルの取得が必要。手動テーマは `config.transformer_topics` に保存 |
| グループインタビュー比較 | Experimental（未コミット） | 分析・可視化の下部の折りたたみ／`POST /api/library/interview-comparison`、`POST/GET …/runs` | `build_interview_comparison`、`archive_interview_comparison`、`static/interview-comparison.js` | ブラウザーからのPOSTが403になる疑い（BUG-01） |
| 事前アンケート分析 | Implemented | 話者管理 | `app.js`（クライアント側で集計） | 話者台帳の属性を使う |
| くしなだ学習データ | Implemented | 一覧の学習状態／`GET /api/training`、`…/corrections.jsonl`、`…/manifest.csv` | `record_training_corrections`、`write_training_exports` | `training_events`、`<data>/kushinada_training` |
| ResearchVaultのナビゲーション・グラフ・テーマ同期 | Implemented | Obsidian側 | `ObsidianLayout.publish_navigation`、`configure`、`sync_themes` | `.obsidian` も変更する（OBS-03） |
| 4 Vaultへの書き出し | Experimental（未コミット、実データでは未生成） | 自動 | `vault_registry.py`、`AnalysisStore.publish_vaults`、`publish_input_vault` | [[30-Data/four-vaults-v1]] |
| Google Colab | Implemented | `notebooks/Gurumoji_Colab.ipynb` | `is_colab_runtime` | なし |
| 保守スクリプト | Implemented | 手動 | `scripts/check_*.py`、`repair_qwen_download.py`、`bootstrap_s3prl.py`、`cleanup_env.bat`、`setup_emotion.bat` | 開発・診断用 |

## Duplicate：目的が重なる機能と、併存の理由

| 重複 | 併存している理由（推定を含む） | 収束の方向 |
| --- | --- | --- |
| AI仕上げ：アプリ内ジョブ／Obsidian作業台 | Obsidian方式を既定にした後も、API互換（`finish_in_obsidian=0`）とテストのためにジョブ内の経路が残った | Obsidian方式を正にする。ジョブ内の経路はAPI互換として残し、UIからは出さない（[[40-Design/decisions]] ADR-010） |
| 話者特定：ジョブ／作業画面の再特定／仕上げのオプション | 機能を追加するたびに入口が増えた | 実装は `detect_speaker_names_with_ai` の1つ。UIの入口を整理する |
| 議事録Markdown：`format_meeting_minutes_markdown`（出力・API）／`meeting_minutes_note`（Obsidian） | Obsidian用にリンク付きの形式を別途作った | 同じ中間データからレンダラーを2つ作る形に整理する |
| 議事録のVault出力：作業台の会議ノート（`I###-会議議事録-*.md`）／固定保存の実行（`meeting_minutes` run） | 閲覧用と、再現用の固定保存を分けた | ノートの役割をドキュメントに明記し、ナビでは一方へ誘導する |
| 文字起こし保存API：`PUT /api/jobs/<id>/transcript`／`PUT /api/library/<id>` | ジョブ完了直後の保存と、ライブラリからの保存 | 内部の実装は共通。APIは互換として残す |
| ダウンロードAPI：`/api/jobs/<id>/files/…`／`/api/library/<id>/files/…` | 同上 | 同上 |
| 分析のCSV：都度エクスポート／固定保存の成果物 | 「今の値」と「再現用に固定した値」 | UIの文言で区別する |
| Vaultノートの台帳：SQLite `obsidian_notes`／`interviews.json`／`vaults.json`／`state.json` | モジュールごとに段階的に追加された | 書き込みの判定を共通化する（OBS-04） |
| Frontmatterの生成・解析 | 同上 | 1組に統合する（OBS-06） |
| 原子的書き込み関数 | `analysis_store` と `app.py` で個別に実装した | 1つに統合する（ARCH-04） |
| AI入力の分割：`chunk_segments`／`analysis_insights.bounded_batches`／`ai_finishing.fragments` | 用途ごとに実装した | `chunk_segments` はテストからしか参照されていない |

## Legacy：過去の方式・互換用

| 対象 | 状態 | 使用状況 | 扱い |
| --- | --- | --- | --- |
| `obsidian_migration.migrate`（ResearchVaultの旧階層移行） | Implemented（互換） | 起動時に毎回呼ばれるが、`migration-v1.json` があれば何もせず戻る。現環境は移行済み | 他の環境から移行するために残す。削除しない |
| 旧形式の作業ノート（```` ```text ```` ブロック）の解析 | 互換 | `obsidian_finishing.BLOCK` | 旧ノートがある限り残す |
| 操作ノート本文に書く `provider:` 行 | 互換 | `ObsidianWorkbench.selection` の正規表現 | 同上 |
| `src/app.py` ほか5件の互換import | 互換 | テスト約20ファイルが `import app` などで使用 | 削除不可。テストのimportを移すまで残す |
| `chunk_segments` | Deprecated候補 | 本体からは呼ばれず、`tests/test_ai_scaling.py` だけが参照 | 下記「削除判断の確認項目」を満たしてから整理する |
| `legacy_training_events` | 互換 | `repair_training_artifacts` が使用 | 残す |
| 空データ追加の `window.prompt` による代替手段 | 互換 | `<dialog>` が使えないブラウザー向け | 残す（UIの統一時に再検討） |

## Unknown：役割を判断できないもの（削除しない）

| 対象 | 観察 | 推定 |
| --- | --- | --- |
| `runtime/gurumoji.sqlite3` | 0バイト。src・scripts・tests・docsから参照なし | 過去の試行か誤作成。Deprecated候補 |
| `runtime/` 直下の `lmstudio-*-check.json`、`*.png` | コードの保存先ではない | `scripts/check_*` などの検証出力 |
| `runtime/data/obsidian/.obsidian` と `無題のファイル*.base` | ResearchVaultの親フォルダーに作られている | 親の `obsidian` フォルダーを保管庫として開いた痕跡。Vaultが入れ子になる危険がある（OBS-10） |
| `runtime/data/obsidian_layout/navigation-backup-*`、`method-navigation-backup-*`、`runtime/data/backups/before-analysis-test-*.sqlite3` | コードに作成する処理がない | 開発中に手作業で退避したもの |

## Planned（未実装。既存ノートに記載済み）

- ObsidianからアプリへのDB取り込み（研究メモ・解釈・コード案の差分取り込み）：[[40-Design/sync-contract]]
- Vaultの保存先を変更するUI、ResearchVaultから4 Vaultへの移行、外部分析結果の登録、保存済み比較の一覧画面：[[30-Data/four-vaults-v1]]
- 可搬パッケージ・整合バックアップ：[[40-Design/storage-policy]]

## 削除判断の確認項目

Deprecated候補を整理する前に、次をすべて確認し、結果をこのノートに追記する。1つでも判断できなければ削除しない。

- [ ] import されていない（`gurumoji.*` と、互換の `src/*.py` 経由の両方）
- [ ] UI（`index.html`、`static/*.js`）から呼ばれていない
- [ ] API・CLI・`scripts/`・ノートブックから呼ばれていない
- [ ] テストから使われていない（使われている場合は、テストの意図を先に移す）
- [ ] 環境変数や設定で有効化されない
- [ ] 動的に読み込まれていない（`import_module`、文字列によるディスパッチ）
- [ ] Obsidianの既存ノート・作業状態（`state.json`）・移行処理が依存していない
