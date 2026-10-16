---
note_type: reference-section
status: in-progress
updated: 2026-09-15
tags:
- gurumoji/program
- gurumoji/design
note_id: design-convergence-plan-section-06
title: アプリ収束計画（整理・統合・安全化）：I. 変更予定のファイル（今後のフェーズ）
summary: I. 変更予定のファイル（今後のフェーズ）。出典ノート「アプリ収束計画（整理・統合・安全化）」の分割本文。
parent_note_id: design-convergence-plan
source_path: 40-Design/convergence-plan.md
source_sha256: b60640ba092a802e2735beeefa7dc160b6c69c609f7930b46554a0d1751d92d6
source_body_lines:
- 252
- 278
split_on: '2026-10-11'
---

# アプリ収束計画（整理・統合・安全化）：I. 変更予定のファイル（今後のフェーズ）

親索引・状態・確認版：[[40-Design/50-Governance/convergence-plan/00-Index]]。必要な本文だけを取得する。

## I. 変更予定のファイル（今後のフェーズ）

| ファイル | 主な変更 |
| --- | --- |
| `src/gurumoji/obsidian_layout.py` | `sync_themes`・`decorate` の書き込み前の再確認、キー単位のfrontmatter更新、`configure` の書き込み条件、Vaultの入れ子検出 |
| `src/gurumoji/obsidian_finishing.py` | `save_note` の既存ファイル確認、frontmatterの統一 |
| `src/gurumoji/vault_registry.py` | ResearchVaultの登録、共通の書き込み判定の基準 |
| `src/gurumoji/analysis_store.py` | `write_note` を共通の判定に移す、`local_links` の廃止、共通関数の移動 |
| `src/gurumoji/obsidian_migration.py` | 空フォルダー削除の範囲、Dry Run |
| `src/gurumoji/app.py` | watcherの状態表示、削除時のResearchVault状態更新、URL・パス取得の統一、既定値APIの提供、責務ごとの関数移動（最後に行う） |
| `src/gurumoji/static/interview-comparison.js` | `apiFetch` へ置き換え |
| `src/gurumoji/static/app.js`、`templates/index.html` | Obsidianの入口の集約、ボタン名、UX項目 |
| `tests/test_obsidian_*.py`、`test_four_vaults.py`、`test_vault_coverage.py`、`test_interview_comparison.py`、`test_browser_e2e.py` | [[50-Tests/10-Storage/obsidian-safety-test-plan/00-Index\|obsidian-safety-test-plan]] のケースを追加 |
| `README.md`、`docs/OBSIDIAN_*.md`、このVault | Vaultの数・構成の統一、役割の分担 |

## J. 削除候補

いずれも [[20-Modules/10-Inventory/feature-inventory/00-Index|feature-inventory]] の「削除判断の確認項目」をすべて満たすまで削除しない。

| 候補 | 判断に必要なこと |
| --- | --- |
| `app.chunk_segments` | `tests/test_ai_scaling.py` の意図を `ai_finishing.fragments` 側のテストへ移す |
| `runtime/gurumoji.sqlite3`（0バイト） | 利用者に確認する（Git管理外の利用者データ領域） |
| `runtime/` 直下の `*-check.json`・`*.png` | 生成したスクリプトを特定し、利用者に確認する |
| `runtime/data/obsidian/.obsidian`、`無題のファイル*.base` | 利用者がそのフォルダーを保管庫として使っていないか確認する。ファイルは消さず、案内だけ行う |
| 手作業で退避した `navigation-backup-*` など | 利用者に確認する |
