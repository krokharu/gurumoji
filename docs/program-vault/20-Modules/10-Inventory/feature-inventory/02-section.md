---
note_type: reference-section
status: current
verified: 2026-09-14
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/features
note_id: program-feature-inventory-section-02
title: 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：Supporting：Coreを支える機能
summary: Supporting：Coreを支える機能。出典ノート「機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）」の分割本文。
parent_note_id: program-feature-inventory
source_path: 20-Modules/feature-inventory.md
source_sha256: 452c464c3fa60e7f2a4cc230a48433daf715bc2dd5508dc9ea8a77ac12a373e4
source_body_lines:
- 31
- 50
split_on: '2026-10-11'
---

# 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：Supporting：Coreを支える機能

親索引・状態・確認版：[[20-Modules/10-Inventory/feature-inventory/00-Index]]。必要な本文だけを取得する。

## Supporting：Coreを支える機能

| 機能 | 状態 | 入口 | 実装 | データ／ファイル | Obsidian |
| --- | --- | --- | --- | --- | --- |
| 起動・セットアップ・ライブラリ更新 | Implemented | `run.bat`、`setup_gui.bat` | `scripts/run_launcher.ps1`、`scripts/setup_gui.ps1`、`main`、`initialize_application` | `.venv`、`runtime/logs` | watcher起動、旧階層移行 |
| データバックアップ・検証・復元 | Implemented | 接続と処理装置の「バックアップを作成」／`POST /api/system/backup`。CLI: `scripts/backup_data.py create|verify|restore` | `services/data_backup.py`: `create_backup`、`verify_backup`、`restore_backup` | `runtime/backups` または `MOJIOKOSI_BACKUP_DIR`。DB・分析成果物・Vault・台帳。元メディア・学習用音声は任意。ゴミ箱・出力ファイル・APIキーは含めない | 5 Vaultと各台帳を同じ時点で保存。復元CLIは空のデータフォルダーが対象（[[60-Operations/10-Data/backup-restore\|backup-restore]]） |
| マシン診断・リソースモニター | Implemented | 上部バー「接続と処理装置」・新規作成「認識・話者分離」・処理状況／`GET /api/config`、`GET /api/system/activity` | `get_machine_profile`、`recommend_machine_settings`、`system_activity_snapshot` | なし | なし |
| 音声前処理・小声対策・空白補完 | Implemented | 認識設定 | `audio.py` は話者分離用の元音声で小さすぎる声だけを最大4倍に補強。詳細処理は3秒以上の空白だけを再確認し、補助ASR結果を統合 | 一時ファイル | なし |
| 単語登録 | Implemented | 認識設定／`GET/PUT /api/custom-vocabulary` | `load_custom_vocabulary`、`save_custom_vocabulary` | `<data>/custom_vocabulary.json` | 語数とhashだけをInputVaultへ |
| 話者台帳（話者管理）・CSV入出力 | Implemented | 話者管理／`GET/PUT /api/speakers`、`POST …/import`、`GET …/export.csv` | `save_speaker_registry_records`、`import_speaker_registry_csv` | `speaker_registry`、`application_metadata` | 変更で保存分析をstaleにする（DBトリガー） |
| 会話プロファイル・会話話者連携 | Implemented | 作業画面「会話・話者」／`PUT /api/library/<id>`、`GET …/speakers.csv` | `normalize_session_profile`、`normalize_conversation_speaker_profiles` | `library_items` のJSON列 | InputVaultの会話種別 |
| 出力ファイル（TXT／JSON／SRT／アウトライン／感情CSV／ワードクラウド） | Implemented | ダウンロードリンク／`GET /api/jobs/<id>/files/<name>`、`GET /api/library/<id>/files/<name>` | `write_outputs`、`write_word_cloud` | `runtime/output` | なし |
| メディア保管・再生・サムネイル | Implemented | 作業画面「発話の確認・編集」、新規作成のファイル選択／`GET …/media`、`GET …/thumbnail`、`POST /api/source-thumbnail`、`POST /api/select-input` | `archive_media`、`stream_library_media`、`generate_video_thumbnail` | `<data>/media`、`thumbnails` | 相対パスとサイズをInputVaultへ |
| データ削除・復元 | Implemented | 一覧・作業画面「ファイル・管理」／`DELETE /api/library/<id>`、`GET /api/library/trash`、`POST /api/library/trash/<entry_id>/restore`、`DELETE /api/library/trash/<entry_id>` | `web/library_deletion.py`、`services/library_trash.py` | `<data>/trash/<entry_id>/manifest.json` にDB行・メディアの復元情報。既定30日で期限切れを削除 | ResearchVaultの概要・一覧とInputVault台帳を削除済みにする。復元時に表示を戻す |
| 出力JSONの自動取り込み | Implemented | 起動時 | `import_existing_outputs`、`repair_output_import_provenance` | `output_import_provenance`、`output_import_tombstones` | InputVault（`imported`） |
| リクエストのセキュリティ | Implemented | 全API | `enforce_request_security`（Host、CSRFヘッダー、リモート認証、サイズ上限） | なし | なし |
| AI接続・モデル選択・応答判定 | Implemented | 上部バーのトークン表示と「接続と処理装置」／`GET /api/ai/models`、`PUT /api/ai/model`、`GET /api/ai/lmstudio-reasoning` | `services/ai/client.py`: 拒否・途中終了の理由表示、429・一時的な5xxを最大2回再試行（`Retry-After`は最大30秒）; `available_ai_models`、`update_token_model`、`ai_http_worker.py` | `config/tokens.json` | APIキーは書かない |
| AIエフォート（思考モード） | Implemented | AI仕上げ欄 | `ai_effort.py`、`static/ai-effort.js` | `localStorage`、`state.json` | 操作ノートに引き継ぐ |
| 逐語録の分析準備（版・確認状態） | Implemented | 分析 → 設定・手動分析／`PUT …/preparation`、`GET …/preparation/export.json` | `transcript_preparation.py` | `transcript_versions`、`transcript_preparations`、`transcript_preparation_events` | 件数・hashだけをInputVaultへ（[[30-Data/30-Transcript/transcript-preparation-v1\|transcript-preparation-v1]]） |
