---
note_id: program-four-vaults-v1
note_type: data-model
title: 4 Vault の保存契約 v1
status: current
verified: 2026-09-14
schema_version: 1
tags:
  - gurumoji/program
  - gurumoji/obsidian
---

# 4 Vault の保存契約 v1

Whisperの文字起こしと各分析の保存結果を、役割の異なる4つの独立したObsidian Vaultへ書き出す。Vault同士は内部リンクでつながず、`conversation_id`・`input_snapshot_id`・`run_id`・`artifact_id`・`note_id` で対応付ける。正本はこれまでどおりSQLite・`analysis_store` のJSON／CSV・メディアで、Vaultのノートは台帳・仕様・来歴の要約である。

## 構成

| Vault | ルート | アプリの書き込み | 置くもの |
| --- | --- | --- | --- |
| Software | `docs/program-vault`（このVault） | しない。Git管理 | アーキテクチャ、モジュール契約、手法の定義、設計判断 |
| Input | `<data>/obsidian/InputVault` | する | `10-Inputs` 取り込み台帳、`20-Snapshots` 分析入力スナップショット |
| Visualization | `<data>/obsidian/VisualizationVault` | する | `10-Visuals/run-<run_id>/<method_id>.md` 図表の問い・推奨表示・列・CSVの来歴 |
| Orchestrator | `<data>/obsidian/OrchestratorVault` | する | `10-Methods` 手法カード、`20-Runs` 実行記録（状態・警告・環境・成果物） |

`<data>` はDBファイルの親ディレクトリで、通常は `MOJIOKOSI_DATA_DIR`。各Vaultは `00-Home.md`、`00-Index.md`、`.obsidian/`、`99-Archive/` を持つ。既存の `ResearchVault` は研究者が読むノートとAI仕上げの操作に使い続け、移動・改名しない。

## 書き出しの契機

| 契機 | 実装 | 書き出すノート |
| --- | --- | --- |
| Whisperジョブの保存 | `app.py`: `whisper_vault_settings` → `publish_input_vault` | Input台帳。モデル・言語・デバイス・VAD等、話者分離モデル、カスタム語彙の語数とhash（語そのものは書かない）、発話数・話者数・長さ、空本文・UNKNOWN話者・時刻不正の件数 |
| 本文・話者の編集保存、AI話者特定、Obsidian仕上げの反映 | `update_library_from_payload`、`rerun_library_speaker_identification`、`run_obsidian_finishing` → `publish_input_vault` | Input台帳の `revision`・`source_hash` を更新。記録済みのWhisper設定と取り込み元は保持 |
| 起動時の出力JSON取り込み | `import_existing_outputs` → `publish_input_vault(source_kind="imported")` | 「出力JSONの取り込み」として台帳を作成 |
| 会話の削除 | `_delete_library_item_locked` → `retire_input_vault` | 台帳を `status: deleted` にする。保存済みの実行と各Vaultのノートは来歴として残す |
| 分析の固定保存（全件分析、KWIC、AI見解、Transformer、AI仕上げ） | `AnalysisStore.publish` → `publish_vaults` → `VaultRegistry.publish_analysis` | Inputスナップショット、Orchestratorの手法カードと実行記録、表を持つ手法のVisualization仕様 |
| 会議議事録（別の実行 `meeting_minutes`） | ジョブ完了時と「議事録をObsidianへ保存」: `archive_meeting_minutes` | 会話1件の独立した実行。タスク候補・決定事項候補・発話量の表、Orchestrator・Visualization・ResearchVault |
| グループインタビュー比較（別の実行 `interview_comparison`） | `POST /api/library/interview-comparison/runs`: `archive_interview_comparison`（一覧は同じパスのGET） | 複数会話の実行。構成会話は `analysis_run_members`。Inputは比較入力（構成会話と各revision）、ResearchVaultは `40-研究/インタビュー比較/` |
| 入力・分析条件・話者台帳の変更 | `AnalysisStore.publish_index` → `refresh_vaults` | 実行記録と図表仕様を `status: stale` で再出力。その会話を含む比較も対象 |

同じ条件で再保存すると、まだ4 Vaultに出ていない既存の実行（4 Vault導入前の保存）も出力する。保存済みデータのない会話は、編集保存・分析保存・取り込みまで台帳を作らない。会議議事録と比較は、会話ごとの全件分析に混ぜず、それぞれ独立した実行・手法（`meeting_minutes`、`interview_comparison`）として保存する。

## ノート契約

管理ノートのプロパティは `note_id`、`vault_kind`、`note_type`、`title`、`summary`、`source_ids`、`artifact_ids`、`revision`、`source_hash`、`status`（`current`／`stale`）、`updated`、`schema_version`、`managed_by: gurumoji`。実行記録と図表仕様は `run_id`、`input_snapshot_id`、`method_id` を追加する。ファイル名はASCIIのIDで、日本語の名前は `title` に置く。

`<data>/obsidian_layout/vaults.json` がVaultのルートと、ノートごとの書き込みhash・`revision`・`source_hash` を記録する。ノートがObsidianで編集されていれば上書きせず `conflict`、移動・削除されていれば再作成せず `missing` として `00-Index.md` に表示する。書き込み前に予定hashを記録するため、途中で止まった書き込みは次回に完了し、競合とは扱わない。

## 含めないもの

- 発話本文、話者名、音声、全件の表の行（ResearchVault と `analysis_store` に残る）
- APIキー、Hugging Faceトークン、個人PCの絶対パス（メディアは `<data>` からの相対パスだけ）
- AI呼び出し・再分析。書き出しと stale の反映は保存済みの成果物だけで行う

## 検証と未実装

検証先：`tests/test_four_vaults.py`（Whisper台帳・秘密情報の除外・再出力の不変・手動編集の保持・分析の3 Vault分割・stale反映）、`tests/test_vault_coverage.py`（Whisper設定、AI話者特定・Obsidian反映・取り込み・削除の台帳、再保存時の出力、会議議事録と比較の独立保存・比較のstale）、既存の `tests/test_analysis_storage.py`、`tests/test_obsidian_layout.py`。

未実装：保存先変更UI、ResearchVaultから4 Vaultへの移行、取り込み済みでない保存済み会話の一括台帳作成、外部分析結果の登録、保存済み比較の一覧を表示する画面（APIは実装済み）。

関連：[[30-Data/analysis-storage-v1]]、[[40-Design/storage-policy]]、[[50-Analysis-Methods/00-Orchestrator-Common-Contract]]。
