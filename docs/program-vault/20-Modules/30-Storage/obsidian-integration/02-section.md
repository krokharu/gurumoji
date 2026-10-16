---
note_type: reference-section
status: current
feature: obsidian-storage
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/obsidian
note_id: program-obsidian-integration-section-02
title: Obsidian連携の現状構造と安全性：Vaultの指定方法
summary: Vaultの指定方法。出典ノート「Obsidian連携の現状構造と安全性」の分割本文。
parent_note_id: program-obsidian-integration
source_path: 20-Modules/obsidian-integration.md
source_sha256: 3248688d4a6945a66bfa38de6b5a2475dcf5fb88a5a3f52b16573263e0e86f19
source_body_lines:
- 17
- 61
split_on: '2026-10-11'
---

# Obsidian連携の現状構造と安全性：Vaultの指定方法

親索引・状態・確認版：[[20-Modules/30-Storage/obsidian-integration/00-Index]]。必要な本文だけを取得する。

## Vaultの指定方法

| Vault | ルート | 決め方 | アプリの書き込み |
| --- | --- | --- | --- |
| ResearchVault | `<data>/obsidian/ResearchVault` | `ObsidianLayout.__init__`、`ObsidianWorkbench.__init__`、`AnalysisStore.__init__` の3か所で、それぞれ `database_file.parent` から算出 | する |
| Input／Visualization／Orchestrator | `<data>/obsidian/InputVault` など | `vaults.json` の `root`。`obsidian/<英数字_->` だけを許可し、`ResearchVault` と重複は拒否（`VaultRegistry.root`、`roots`） | する |
| Software | `docs/program-vault` | `vault_registry.SOFTWARE_ROOT` と、`app.vault_registry()` から渡す引数の2か所 | しない（`_write` が拒否） |

- `<data>` は `MOJIOKOSI_DATA_DIR`、未設定なら `runtime/data`。
- Vaultの場所を変える設定UIはない。
- 利用者のDocuments配下や既存Vaultを探したり推測したりする処理はない。
- アプリ専用のVaultは、存在しなければアプリが作成する。

## 保存場所とノートの種類

### ResearchVault

| パス | 内容 | 書く処理 | 所有 |
| --- | --- | --- | --- |
| `00-ホーム.md`、`01-分析結果.md`、`インタビュー一覧.base`、`10-インタビュー/インタビュー一覧.md`、`90-運用/使い方.md`、`90-運用/同期状況.md`、`40-研究/分析手法/<group>.md` | ナビゲーション | `ObsidianLayout.publish_navigation` → `managed_note` | アプリ（共通判定） |
| `10-インタビュー/I###-<名前>/I###-概要.md` | インタビューの入口 | `ObsidianLayout.update` → `managed_note` | アプリ（共通判定。削除されても作り直さない） |
| `…/履歴/ノート変更/<ノート名>-<hash8>/<日時>-{最初の版,研究者の編集}.md`、`90-運用/変更履歴/…` | 生成ノートの履歴の写し。`graph/history`、履歴用の `note_id` | `vault_note_policy` | アプリ（作成のみ） |
| `…/I###-研究メモ.md` | 研究者のメモ | 無いときだけ作成 | 研究者 |
| `…/I###-保存原文.md`、`I###-全文.md`、`I###-アウトライン.md`、`I###-操作.md`、`I###-状態.md` | 仕上げの作業台 | `ObsidianWorkbench.prepare` → `save_note` | 全文・アウトライン・操作は研究者（`managed_by: researcher`）、状態・原文はアプリ |
| `…/履歴/仕上げ/I###-{アウトライン,仕上げ結果,仕上げ後アウトライン}-<run>.md` | AIの生成版。常に新しいパス | `ObsidianWorkbench.execute` | 結果は研究者が編集してよい |
| `…/I###-会議議事録-r<rev>-<hash>.md`、`…/添付/I###-{タスク,連携}-*.{csv,json}` | 会議議事録と添付 | `ObsidianWorkbench.publish_meeting_minutes` | アプリ（既存なら書かない） |
| `…/I###-分析まとめ.md`、`…/履歴/分析/<run>/…`、`…/履歴/引用/<snapshot>/part-*.md`、`40-研究/インタビュー比較/comparison-<run>.md`、`90-運用/Gurumoji-SavedAnalyses.md` | 分析結果・引用原文・グラフ用ノード | `AnalysisStore.write_note` | アプリ（SQLite `obsidian_notes` のhashで確認） |
| `20-テーマ/*.md` | テーマ。研究者が作成する | `sync_themes`は存在確認だけを行い、読み書きしない | 研究者 |
| `40-研究/テーマ関連/<hash>.md` | テーマとインタビューの関連一覧 | `sync_themes` → `managed_note` | アプリ（共通判定。削除済みは作り直さない） |
| `.obsidian/core-plugins.json`、`appearance.json`、`bookmarks.json`、`workspaces.json`、`workspace.json`、`graph.json`、`snippets/gurumoji-reading.css` | 表示設定 | `ObsidianLayout.configure` | 利用者（アプリも書く） |

### 3つの生成Vault

`00-Home.md`、`00-Index.md`、`10-Inputs`、`20-Snapshots`、`10-Visuals`、`10-Methods`、`20-Runs`、`99-Archive`、`.obsidian/app.json`（無いときだけ `{}` を作成）。ファイル名はASCIIのIDだけ。詳細は [[30-Data/40-Vaults/four-vaults-v1|four-vaults-v1]]。

### Vault外の制御ファイル

| ファイル | 内容 |
| --- | --- |
| `<data>/obsidian_layout/interviews.json` | 会話IDとインタビューコード・フォルダーの対応。`managed` にナビ系ノートのhashを保存 |
| `<data>/obsidian_layout/vaults.json` | 3 Vaultのルート、ノートごとの `sha256`・`pending`・`sync` |
| `<data>/obsidian_layout/migration-v1.json`、`migration-pending.json`、`backup-*` | 移行記録とバックアップ |
| `<data>/obsidian_workbench/<sha(item)>/state.json` ほか | 仕上げの状態、`note_ids`、元ノートのfingerprint、候補結果 |
| SQLite `obsidian_notes`、`analysis_runs.note_path`・`vault_status` | 分析ノートのhashと公開状態 |
