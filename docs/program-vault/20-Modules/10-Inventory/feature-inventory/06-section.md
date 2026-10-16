---
note_type: reference-section
status: current
verified: 2026-09-14
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/features
note_id: program-feature-inventory-section-06
title: 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：Planned（未実装。既存ノートに記載済み）
summary: Planned（未実装。既存ノートに記載済み）。出典ノート「機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）」の分割本文。
parent_note_id: program-feature-inventory
source_path: 20-Modules/feature-inventory.md
source_sha256: 452c464c3fa60e7f2a4cc230a48433daf715bc2dd5508dc9ea8a77ac12a373e4
source_body_lines:
- 111
- 127
split_on: '2026-10-11'
---

# 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：Planned（未実装。既存ノートに記載済み）

親索引・状態・確認版：[[20-Modules/10-Inventory/feature-inventory/00-Index]]。必要な本文だけを取得する。

## Planned（未実装。既存ノートに記載済み）

- ObsidianからアプリへのDB取り込み（研究メモ・解釈・コード案の差分取り込み）：[[40-Design/40-Storage/sync-contract|sync-contract]]
- Vaultの保存先を変更するUI、ResearchVaultから4 Vaultへの移行、外部分析結果の登録、保存済み比較の一覧画面：[[30-Data/40-Vaults/four-vaults-v1|four-vaults-v1]]
- 可搬パッケージ・整合バックアップ：[[40-Design/40-Storage/storage-policy|storage-policy]]

## 削除判断の確認項目

Deprecated候補を整理する前に、次をすべて確認し、結果をこのノートに追記する。1つでも判断できなければ削除しない。

- [ ] import されていない（`gurumoji.*` と、互換の `src/*.py` 経由の両方）
- [ ] UI（`index.html`、`static/*.js`）から呼ばれていない
- [ ] API・CLI・`scripts/`・ノートブックから呼ばれていない
- [ ] テストから使われていない（使われている場合は、テストの意図を先に移す）
- [ ] 環境変数や設定で有効化されない
- [ ] 動的に読み込まれていない（`import_module`、文字列によるディスパッチ）
- [ ] Obsidianの既存ノート・作業状態（`state.json`）・移行処理が依存していない
