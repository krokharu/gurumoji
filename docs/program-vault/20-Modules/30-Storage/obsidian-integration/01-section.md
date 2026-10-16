---
note_type: reference-section
status: current
feature: obsidian-storage
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/obsidian
note_id: program-obsidian-integration-section-01
title: Obsidian連携の現状構造と安全性：Obsidian連携の現状構造と安全性
summary: Obsidian連携の現状構造と安全性。出典ノート「Obsidian連携の現状構造と安全性」の分割本文。
parent_note_id: program-obsidian-integration
source_path: 20-Modules/obsidian-integration.md
source_sha256: 3248688d4a6945a66bfa38de6b5a2475dcf5fb88a5a3f52b16573263e0e86f19
source_body_lines:
- 1
- 16
split_on: '2026-10-11'
---

# Obsidian連携の現状構造と安全性：Obsidian連携の現状構造と安全性

親索引・状態・確認版：[[20-Modules/30-Storage/obsidian-integration/00-Index]]。必要な本文だけを取得する。


# Obsidian連携の現状構造と安全性

- **確認元：** `src/gurumoji/obsidian_layout.py`、`obsidian_finishing.py`、`obsidian_migration.py`、`vault_registry.py`、`analysis_store.py`、`app.py`（`start_obsidian_watcher`、`run_obsidian_finishing`、`publish_input_vault`、`publish_meeting_minutes_to_obsidian`）、`web/library_deletion.py`（`_delete_library_item_locked`）。
- **確認条件：** mainの統合版`2f13f98`（2026-09-26）。2026-09-25の会話ゴミ箱、復元、共通ノート履歴ポリシーをコードと照合。
- **関連ノート：** 危険箇所の対応状況は [[40-Design/50-Governance/known-issues/00-Index|known-issues]] の `OBS-*` で管理する。改善方針は [[40-Design/50-Governance/convergence-plan/00-Index|convergence-plan]] と [[40-Design/50-Governance/decisions/00-Index|decisions]] に書く。利用者向けの操作手順は `docs/OBSIDIAN_FINISHING.md` と `docs/OBSIDIAN_GRAPH.md` にある。

## 接続方法

- Obsidianプラグインではない。Pythonアプリが、Vaultフォルダー内のMarkdown・JSONを `pathlib` で直接読み書きする。Obsidian本体との通信やAPI呼び出しはない。Obsidianを閉じていてもアプリは動作する。
- Obsidian Plugin API（`Vault.process`、`FileManager.processFrontMatter`、`normalizePath`、ゴミ箱への移動）は使えない。代わりに次の処理を自前で実装している。
  - `analysis_store.safe_path`：相対パスだけを許可する。`\`・`:`・`..`・`.` は拒否する。途中のシンボリックリンクとジャンクションも拒否し、ルートの外を指すパスを拒否する。
  - `analysis_store.write_atomic`：同じフォルダーに `.<name>.<uuid>.tmp` を作り、`fsync` してから `os.replace` で置き換える。`create_only=True`の場合は`os.link`で排他的に新規作成し、既存ファイルを置き換えない。いずれも一時ファイルを後片付けする。フォルダーの `fsync` はしない。
  - hash台帳と共通の書き込み判定：アプリが書いた内容のhashを記録し、`vault_note_policy.write_generated_note` が既存ファイルの扱いを決める（2026-09-25、OBS-04。下記「書き込み主体ごとの競合処理」）。
- 開く操作は `obsidian://open?path=<絶対パス>` のURIだけで行う（`ObsidianWorkbench.public`、`AnalysisStore.public`）。
