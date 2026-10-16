---
note_type: reference-section
status: current
feature: obsidian-storage
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/obsidian
note_id: program-obsidian-integration-section-06
title: Obsidian連携の現状構造と安全性：同期とファイル監視
summary: 同期とファイル監視。出典ノート「Obsidian連携の現状構造と安全性」の分割本文。
parent_note_id: program-obsidian-integration
source_path: 20-Modules/obsidian-integration.md
source_sha256: 3248688d4a6945a66bfa38de6b5a2475dcf5fb88a5a3f52b16573263e0e86f19
source_body_lines:
- 162
- 187
split_on: '2026-10-11'
---

# Obsidian連携の現状構造と安全性：同期とファイル監視

親索引・状態・確認版：[[20-Modules/30-Storage/obsidian-integration/00-Index]]。必要な本文だけを取得する。

## 同期とファイル監視

- 監視は、OSのファイル監視APIではなくポーリングで行う。`app.py` の `start_obsidian_watcher` がデーモンスレッドを1本起動する（`main` から起動する場合だけ）。
  1. 最初に `ObsidianWorkbench.recover`（`running` の状態を `interrupted` にする）と `migrate` を実行する。
  2. その後、2秒ごとに `poll_once`、10秒ごとに `sync_themes` を実行する。
- ループを防ぐ仕組みは次のとおり。
  - 操作ノートの選択が、前回確認した選択（`observed`）と同じなら何もしない（ラッチ）。再実行するには、一度チェックを外して保存する必要がある。
  - AIの生成物は常に新しいパスに書くため、監視対象の元ノートを書き換えない。
  - テーマ同期と生成Vaultへの書き出しは、生成結果が同じなら書かない（冪等）。
  - 反映後に更新するのは別のVault（InputVault）とDBで、操作ノートは状態ノート経由の表示だけ。
- 起動時の `recover`・`migrate` が失敗すると、監視スレッドは停止する。停止と理由は `GET /api/config` と仕上げ状況APIの `watcher` で返し、画面に表示する（OBS-09、2026-09-25）。

## エラー処理

- Vaultへの書き出しに失敗しても、正本（文字起こし・編集保存・分析の固定保存）は失敗させない。該当する処理は `publish_input_vault`、`retire_input_vault`、`AnalysisStore.publish_vaults`、`refresh_archive_index`。失敗は `logging` のwarningに出すか、`vault_status` に記録する。
- 仕上げの例外は `state.json` と状態ノートに `error` として表示する。
- 監視ループの例外はログに出して継続する。
- 生成ノートの作成・更新・編集の保存・欠落・再作成は `note_changes.jsonl` に記録する。`.base`・CSSのスキップ、移行、`.obsidian` 設定の変更は記録しない（OBS-15の残り）。

## バックアップ

- 自動バックアップは移行処理だけ。Vault、`obsidian_workbench`、`analysis_store`、`interviews.json`、SQLite（backup API）を `obsidian_layout/backup-<uuid>` にコピーする。
- DATA-03の整合データバックアップは別経路で、実行中は書き込みロックを取って一時点のDB・固定成果物・5 Vault・台帳・作業状態をコピーする。アプリ画面の「バックアップを作成」または `POST /api/system/backup` から作成でき、詳細な除外対象と復元方法は [[60-Operations/10-Data/backup-restore|backup-restore]] に記録する。ゴミ箱はこのバックアップに含まれない。
- 通常の書き込みでは、生成ノートの最初の版と、上書きする研究者の編集版を履歴に写す。アプリ同士の更新（固定保存から作り直せる内容）は写さず、変更記録だけ残す。
- 手動の手順は `docs/PROJECT_LAYOUT.md`（アプリを停止して `runtime/` 全体をコピー）と `docs/OBSIDIAN_VAULTS.md` にある。
