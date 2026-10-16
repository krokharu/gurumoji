---
note_type: reference-section
status: current
verified: 2026-09-14
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/features
note_id: program-feature-inventory-section-01
title: 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：機能一覧と分類
summary: 機能一覧と分類。出典ノート「機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）」の分割本文。
parent_note_id: program-feature-inventory
source_path: 20-Modules/feature-inventory.md
source_sha256: 452c464c3fa60e7f2a4cc230a48433daf715bc2dd5508dc9ea8a77ac12a373e4
source_body_lines:
- 1
- 30
split_on: '2026-10-11'
---

# 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：機能一覧と分類

親索引・状態・確認版：[[20-Modules/10-Inventory/feature-inventory/00-Index]]。必要な本文だけを取得する。


# 機能一覧と分類

2026-09-14の調査を基に作成し、コミット`1b8fe41`へ収録・プッシュ済み。2026-09-26に最新版`2f13f98`の追加機能と状態を反映した。分類は機能の位置づけを表し、問題の対応済み／未対応は[[40-Design/50-Governance/known-issues/00-Index|known-issues]]を参照する。

**分類：** 役割による分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）。1つの機能が複数に該当する場合は、主な分類を先に書く。

**状態：**

| 状態 | 意味 |
| --- | --- |
| Implemented | 使用中 |
| Experimental | 新しい、または実データでの検証が少ない |
| Deprecated候補 | 削除前に確認が必要 |
| Planned | 未実装 |

構造とデータの流れは [[10-Architecture/10-System/system-map/00-Index|system-map]]、テストとの対応は [[20-Modules/10-Inventory/module-map/00-Index|module-map]]、問題点のIDは [[40-Design/50-Governance/known-issues/00-Index|known-issues]] を参照する。

## Core：アプリの中心機能

入口の画面名は2026-09-16のUI再設計後の名称。旧画面との対応は [[20-Modules/40-Interface/ui-screens/00-Index|ui-screens]]。

| 機能 | 状態 | 入口（UI／API） | 実装（呼び出し先） | DB | ファイル | Obsidian |
| --- | --- | --- | --- | --- | --- | --- |
| 文字起こし・話者分離ジョブ | Implemented | 新規作成／`POST /api/jobs`、`GET /api/jobs/<id>`、`GET /api/jobs/active`、`POST …/cancel` | `create_job` → `run_transcription_job`（FFmpeg、WhisperX、pyannote） | `library_items` | `runtime/uploads`、`runtime/output`、`<data>/media` | `ObsidianWorkbench.prepare`、`publish_input_vault` |
| 逐語録の確認・編集保存 | Implemented | 作業画面「発話の確認・編集」（`#/data/<id>`）／`PUT /api/library/<id>`、`PUT /api/jobs/<id>/transcript` | `update_library_from_payload`、`save_transcript`、編集トランザクション群（`write_edit_transaction_manifest` ほか） | `library_items`、`transcript_versions`、`training_events` | 出力を再生成 | InputVault更新、ResearchVault索引のstale化 |
| 処理済みデータ一覧・検索・グループ整理 | Implemented | 処理済みデータ（`#/data`）／`GET /api/library`、`POST/PUT/DELETE /api/library/groups`、`PUT /api/library/<id>/group` | `list_library`、`library_public`、グループ管理API | `library_items.group_id`、`library_groups` | サムネイル | なし |
| 分析・可視化（自動集計・手動コード） | Implemented | 分析・可視化（`#/analysis/<id>`）／`GET/PUT /api/library/<id>/analysis` | `group_analysis_for_row`、`research_analysis.build_research_analysis`、`save_group_analysis` | `analysis_config_json`、`analysis_annotations_json` | 解析キャッシュ | なし（保存時のみ） |
| 分析結果の固定保存 | Implemented | 「分析結果をObsidianに保存」／`POST/GET …/analysis/runs`、`POST /api/analysis/runs/<id>/vault`、`GET /api/analysis/artifacts/<id>` | `archive_group_analysis` → `AnalysisStore.save` → `publish` | `analysis_runs`、`analysis_artifacts`、`analysis_pending_packages`、`obsidian_notes` | `<data>/analysis_store` | ResearchVaultと3 Vault |
