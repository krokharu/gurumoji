---
note_type: reference-section
status: current
verified: 2026-09-14
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/features
note_id: program-feature-inventory-section-05
title: 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：Legacy：過去の方式・互換用
summary: Legacy：過去の方式・互換用。出典ノート「機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）」の分割本文。
parent_note_id: program-feature-inventory
source_path: 20-Modules/feature-inventory.md
source_sha256: 452c464c3fa60e7f2a4cc230a48433daf715bc2dd5508dc9ea8a77ac12a373e4
source_body_lines:
- 90
- 110
split_on: '2026-10-11'
---

# 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：Legacy：過去の方式・互換用

親索引・状態・確認版：[[20-Modules/10-Inventory/feature-inventory/00-Index]]。必要な本文だけを取得する。

## Legacy：過去の方式・互換用

| 対象 | 状態 | 使用状況 | 扱い |
| --- | --- | --- | --- |
| `obsidian_migration.migrate`（ResearchVaultの旧階層移行） | Implemented（互換） | 起動時に毎回呼ばれるが、`migration-v1.json` があれば何もせず戻る。現環境は移行済み | 他の環境から移行するために残す。削除しない |
| 旧形式の作業ノート（```` ```text ```` ブロック）の解析 | 互換 | `obsidian_finishing.BLOCK` | 旧ノートがある限り残す |
| 操作ノート本文に書く `provider:` 行 | 互換 | `ObsidianWorkbench.selection` の正規表現 | 同上 |
| `src/app.py` ほか5件の互換import | 互換 | テスト約20ファイルが `import app` などで使用 | 削除不可。テストのimportを移すまで残す |
| `chunk_segments` | 削除済み（2026-09-26、ARCH-06） | 本体・UI・API・scripts・ノートブック・Obsidianの状態から参照なし。動的読み込みなし | 確認項目をすべて満たした。`tests/test_ai_scaling.py` の意図（文字予算で大きく分ける）は `tests/test_ai_finishing.py` の `test_cleanup_batches_use_a_character_budget_not_small_fixed_batches` へ移した |
| `legacy_training_events` | 互換 | `repair_training_artifacts` が使用 | 残す |
| 空データ追加の `window.prompt` による代替手段 | 互換 | `<dialog>` が使えないブラウザー向け | 残す（UIの統一時に再検討） |

## Unknown：役割を判断できないもの（削除しない）

| 対象 | 観察 | 推定 |
| --- | --- | --- |
| `runtime/gurumoji.sqlite3` | 0バイト。src・scripts・tests・docsから参照なし | 過去の試行か誤作成。Deprecated候補 |
| `runtime/` 直下の `lmstudio-*-check.json`、`*.png` | コードの保存先ではない | `scripts/check_*` などの検証出力 |
| `runtime/data/obsidian/.obsidian` と `無題のファイル*.base` | ResearchVaultの親フォルダーに作られている | 親の `obsidian` フォルダーを保管庫として開いた痕跡。Vaultが入れ子になる危険がある（OBS-10） |
| `runtime/data/obsidian_layout/navigation-backup-*`、`method-navigation-backup-*`、`runtime/data/backups/before-analysis-test-*.sqlite3` | コードに作成する処理がない | 開発中に手作業で退避したもの |
