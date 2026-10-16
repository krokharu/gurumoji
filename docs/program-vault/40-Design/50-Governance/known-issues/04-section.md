---
note_type: reference-section
status: current
feature: project-status
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/issues
note_id: design-known-issues-section-04
title: 既知の問題点と改善方法（収束フェーズ）：DATA：データ・保存
summary: DATA：データ・保存。出典ノート「既知の問題点と改善方法（収束フェーズ）」の分割本文。
parent_note_id: design-known-issues
source_path: 40-Design/known-issues.md
source_sha256: 93c0e1b715181e4d753e26636d16aa88dd9cf9b8c21d45e1ea6a76fb54c75414
source_body_lines:
- 74
- 81
split_on: '2026-10-11'
---

# 既知の問題点と改善方法（収束フェーズ）：DATA：データ・保存

親索引・状態・確認版：[[40-Design/50-Governance/known-issues/00-Index]]。必要な本文だけを取得する。

## DATA：データ・保存

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DATA-01 | 中 | 元メディアの削除が恒久削除になっている | `_delete_library_item_locked`：隔離フォルダーへ移したあと `shutil.rmtree` | 誤って削除すると元音声を復旧できない（出力は残る） | 既存の隔離の仕組みを使い、保持期間つきのゴミ箱にする。完全に削除する操作は別にする（[[40-Design/40-Storage/storage-policy\|storage-policy]] の「別操作とする」方針） | 対応済み（2026-09-25：`services/library_trash`。削除はゴミ箱へ移り、一覧から復元・完全削除できる。保持日数は`MOJIOKOSI_TRASH_RETENTION_DAYS`（既定30日、利用者の選択）で、起動時に期限切れを削除） | P1：優先 |
| DATA-02 | 中 | Vaultの数と構成がドキュメントごとに食い違っている | `docs/OBSIDIAN_VAULTS.md` と `README.md` は「2つのVault」、[[30-Data/40-Vaults/four-vaults-v1\|four-vaults-v1]] は Input／Visualization／Orchestrator に ResearchVault と Software を加えた構成 | 利用者やAIが保存先を誤解する | [[40-Design/50-Governance/convergence-plan/00-Index\|convergence-plan]] のドキュメント統一で直す | 対応済み（`708948b`：`docs/OBSIDIAN_VAULTS.md`とREADMEを5つのVaultに統一。DOC-01／02の全件整理は含まない） | P1：優先 |
| DATA-03 | 低 | 同じ会話の情報が多くの場所に分散している | SQLite、`runtime/output`、`analysis_store`、ResearchVault、InputVault、`obsidian_workbench` | バックアップの漏れや、復元時の不整合 | 正本の分類は [[40-Design/40-Storage/storage-policy\|storage-policy]] にある。バックアップと復元の単位を `60-Operations` の手順として作る | 対応済み（2026-09-25。`services/data_backup.py`。画面の「バックアップを作成」（書き込みロックを取って同時点で写す）と `scripts/backup_data.py create/verify/restore`。対象はDB（backup API）・analysis_store・全Vault・obsidian_layout・作業台・単語登録。メディアと学習用音声は任意。出力・サムネイル・ゴミ箱・tokens.json は除外。復元はhash検証後、空のフォルダーにだけ行う。手順は [[60-Operations/10-Data/backup-restore\|backup-restore]]） | P1：優先 |
