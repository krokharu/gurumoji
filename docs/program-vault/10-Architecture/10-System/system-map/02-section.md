---
note_type: reference-section
status: current
feature: architecture
verified: 2026-09-14
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/architecture
note_id: program-system-map-section-02
title: システム全体構造・データフロー・設定の所在：主要なデータフロー（操作から保存まで）
summary: 主要なデータフロー（操作から保存まで）。出典ノート「システム全体構造・データフロー・設定の所在」の分割本文。
parent_note_id: program-system-map
source_path: 10-Architecture/system-map.md
source_sha256: b51430e47959bba035a47fefde19f5942b7014f183c331b6cecd7d7207d6ea14
source_body_lines:
- 63
- 126
split_on: '2026-10-11'
---

# システム全体構造・データフロー・設定の所在：主要なデータフロー（操作から保存まで）

親索引・状態・確認版：[[10-Architecture/10-System/system-map/00-Index]]。必要な本文だけを取得する。

## 主要なデータフロー（操作から保存まで）

図で見るときは、同じフォルダーの `data-flow.html` をブラウザーで開く。流れを選ぶと、通るモジュールと書き込み先が強調される。

### 1. 新規文字起こし

1. 「新規作成」フォームを `POST /api/jobs` に送る。`create_job` が `JobOptions` を作り、スレッドで `run_transcription_job` を実行する。
2. 処理は FFmpeg前処理 → WhisperX → pyannote → 任意の感情分析 の順に進む。
3. 既定の `finish_in_obsidian=True` の場合、`ObsidianWorkbench.prepare` がResearchVaultへ保存原文・全文・操作ノート・状態ノートを書く。このときジョブ内のAI校正・話者特定・アウトラインは実行しない。無効の場合は、ジョブ内で `clean_segments_with_ai`・`detect_speaker_names_with_ai`・`create_outline_with_ai` を実行する。
4. `write_outputs` が `runtime/output` にTXT／JSON／SRTなどを書く。続いて `upsert_library_item` が SQLite の `library_items` に保存し、メディアを `<data>/media` へ移す。
5. `publish_input_vault` でInputVaultの台帳を更新する。会議の場合は `archive_meeting_minutes` を実行し、`analysis_store` と各Vaultに保存する。その後 `ObsidianWorkbench.activate` を呼び、会議なら `publish_meeting_minutes_to_obsidian` も呼ぶ。

### 2. 逐語録の編集保存

1. `PUT /api/library/<id>` → `update_library_from_payload` → `_update_library_from_payload_locked` の順に呼ぶ。ここでrevisionを確認し、編集トランザクション（出力ファイルの差し替えと回復）を実行する。学習イベントと `transcript_versions` への記録もここで行う。
2. `refresh_archive_index` を呼ぶ。保存済み分析をstaleにし、その状態をResearchVaultの索引と3 Vaultに反映する。
3. `publish_input_vault` を呼ぶ。

`PUT /api/jobs/<id>/transcript`（`save_transcript`）という別の保存APIもある。

### 3. 分析と固定保存

- **閲覧：** `GET /api/library/<id>/analysis` → `group_analysis_for_row` → `research_analysis`（キャッシュあり）。
- **条件・手動コードの保存：** `PUT /api/library/<id>/analysis` でDBの列へ保存する。
- **固定保存：** `POST /api/library/<id>/analysis/runs` → `archive_group_analysis` → `AnalysisStore.save` の順に呼ぶ。
  - `analysis_store` に `inputs/<snapshot>/input.json` と `runs/<run>/…` を書き、SQLite の `analysis_runs` と `analysis_artifacts` を確定する。
  - 次に `AnalysisStore.publish` を呼ぶ。`publish_vaults` で3 Vaultへ、続けてResearchVaultへ分析ノート・引用原文・グラフ用ノードを書き、`publish_index` で分析まとめを更新する。
- **AI見解・Transformer：** `POST …/insights` と `POST …/transformer` をスレッドで実行する。要求台帳はSQLiteに置く。成功すると固定保存する。

### 4. Obsidianでの仕上げ（双方向）

1. `POST /api/library/<id>/obsidian-finishing` で作業版を作る（`prepare`）。
2. 常駐スレッド `start_obsidian_watcher` が2秒ごとに `poll_once` を実行し、操作ノートのチェックと `provider` を読む。
3. チェックが変わると `execute` → `run_obsidian_finishing` の順にAIを呼び、結果を新しいパスのノートへ書く。
4. 「結果をアプリへ反映」を選ぶと、revisionと元ノートのfingerprintを再確認してから、`_update_library_from_payload_locked` → `publish_input_vault` → `archive_ai_finishing` の順に実行する。

### 5. テーマ同期（Obsidianからの読み込み）

同じ常駐スレッドが10秒ごとに `ObsidianLayout.sync_themes` を実行する。研究メモの `[[20-テーマ/…]]` を読み、`20-テーマ` のノートのプロパティと関連欄を書き換える。

### 6. 削除

1. `DELETE /api/library/<id>` → `_delete_library_item_locked` を呼ぶ。
2. メディアとサムネイルを隔離フォルダーへ移す。
3. 削除する行（会話・逐語録の版と準備・取り込み来歴・置き換えるtombstone）を `library_trash.snapshot_rows` で写し、SQLiteの行と準備履歴を削除し、tombstoneを記録する。同じトランザクションのコミット前に、ゴミ箱の保留manifest（`<data>/trash/<日時-ID>/manifest.pending.json`）を書く。
4. `retire_input_vault` を呼ぶ。InputVaultの台帳を `deleted` にし、ResearchVaultでは `ObsidianLayout.mark_deleted` が `interviews.json` と概要ノート・一覧を「アプリから削除済み」にする（OBS-11）。同じIDで再取り込みされると `publish_input_vault` が `clear_deleted` で元の状態に戻す。
5. 隔離したファイルをゴミ箱の項目へ移し、`manifest.json` を確定する（DATA-01）。ゴミ箱の一覧・復元・完全削除は `GET /api/library/trash`、`POST /api/library/trash/<id>/restore`、`DELETE /api/library/trash/<id>`。復元はファイルを戻してから行とtombstoneを戻し、`publish_input_vault` でVaultの削除表示を外す。起動時は `recover_delete_quarantines` が保留項目を完了させ、保持日数（`MOJIOKOSI_TRASH_RETENTION_DAYS`、既定30日、0で自動削除なし）を過ぎた項目を完全に削除する。

出力ファイル、`analysis_store`、ResearchVault、`obsidian_workbench` は削除せずに残る。

### 7. 起動

1. `run.bat` → `scripts/run_launcher.ps1` → `python -m gurumoji.app` の `main` の順に起動する。
2. `initialize_application` が次の処理を行う。
   - 単一インスタンスのロック
   - DBの初期化
   - 編集トランザクションの回復
   - 出力取り込み来歴の修復
   - 削除隔離の回復
   - 学習データの修復
   - 孤立したアップロードの掃除
   - 既存の出力JSONの取り込み
3. `start_obsidian_watcher` を起動する。最初に `recover` と旧階層の `migrate` を実行し、その後Flaskを起動する。
