---
note_type: reference-section
status: current
feature: obsidian-storage
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/obsidian
note_id: program-obsidian-integration-section-05
title: Obsidian連携の現状構造と安全性：添付ファイル
summary: 添付ファイル。出典ノート「Obsidian連携の現状構造と安全性」の分割本文。
parent_note_id: program-obsidian-integration
source_path: 20-Modules/obsidian-integration.md
source_sha256: 3248688d4a6945a66bfa38de6b5a2475dcf5fb88a5a3f52b16573263e0e86f19
source_body_lines:
- 127
- 161
split_on: '2026-10-11'
---

# Obsidian連携の現状構造と安全性：添付ファイル

親索引・状態・確認版：[[20-Modules/30-Storage/obsidian-integration/00-Index]]。必要な本文だけを取得する。

## 添付ファイル

- アプリが作る添付は、会議議事録の `タスクCSV` と `連携JSON` だけ。保存先は各インタビューの `添付/` フォルダー。
  - ファイル名にrevisionと内容hashを含め、同じ名前のファイルがあれば書かない。
  - Obsidianの「添付ファイルの保存場所」設定は読まない。
- `80-添付/` はフォルダーを作るだけで、アプリは使っていない。
- 分析の表CSVはVaultへ複製しない。ノートにはアプリ経由のURL（`http://127.0.0.1:<port>/api/analysis/artifacts/<id>`）だけを書く。端末固有の `file:///` 絶対パスは新しく書かない（OBS-12）。既存ノートに残るリンクは、そのノートが再生成されたときに置き換わる。
- 画像添付と、既存添付の移動・削除を行う処理はない（移行処理では `80-Attachments/` → `80-添付/` へ移す）。

## 書き込み主体ごとの競合処理

| 書き込み主体 | 対象 | 所有・変更の判定 | 外部で編集済みの場合 | 外部で削除・移動済みの場合 |
| --- | --- | --- | --- | --- |
2026-09-25から、生成ノートの書き込みは `vault_note_policy.write_generated_note` の1つの判定を通る（OBS-04）。台帳は書き込み主体ごとに併存する。

- 新規作成：書いたうえで、その内容を「最初の版」として履歴に写す。
- アプリが前回書いた内容のまま：最新版で置き換える。この方式の導入前に作られたノートは、初回の置き換えの前に現在の内容を「最初の版」として写す。
- 研究者が編集していた（台帳にない内容）：編集した版を「研究者の編集」として履歴に写し、最新版で上書きする。
- 研究者が削除していた：ナビゲーション（ホーム・一覧・使い方・同期状況・分析まとめ・生成Vaultの00-Home／00-Index・状態ノート）だけ作り直す。分析ノート・概要・引用原文・テーマ関連などは作り直さず「欠落」とする。
- 履歴の写しは、ResearchVaultでは各インタビューの `履歴/ノート変更/`（共通ノートは `90-運用/変更履歴/`）、生成Vaultでは `99-Archive/history/` に置く。`graph/history` タグを付けてグラフから除き、`note_id` は履歴用に付け替え、`aliases` は外す。
- 変更はすべて `<data>/obsidian_layout/note_changes.jsonl` に記録する（5MBで `.1` へ切り替え）。研究者の編集の保存・欠落・再作成は、ResearchVaultの `90-運用/同期状況.md` と、分析保存の応答 `vault_notes`（画面のメッセージ）に出す。

| 書き込み主体 | 対象 | 所有・変更の判定 | 外部で編集済みの場合 | 外部で削除・移動済みの場合 |
| --- | --- | --- | --- | --- |
| `VaultRegistry._write` | 3 Vaultの全ノート | `vaults.json` の `sha256`・`pending`（書き込み前に予定hashを記録）＋共通判定 | 履歴に写して上書き（`overwritten`） | 00-Home／00-Indexは作り直す。他は `missing` |
| `AnalysisStore.write_note` | ResearchVaultの分析ノート | SQLite `obsidian_notes.sha256`＋共通判定 | 履歴に写して上書き | 分析まとめ・SavedAnalysesは作り直す。他は欠落として報告 |
| `ObsidianLayout.managed_note` | ナビ・概要・同期状況・状態ノート | `interviews.json` の `managed` hash＋共通判定（`.md` のみ） | 履歴に写して上書き | ナビは作り直す。概要・テーマ関連は作り直さない |
| `ObsidianLayout.managed_note`（`.base`・CSS） | 設定に近いファイル | `managed` hash | 何も通知せずスキップ | 再作成する |
| `ObsidianWorkbench.save_note`、`note` | 仕上げノート | 排他的な新規作成。管理状態を失い初期ノートが残る場合は停止 | 同名ノートがあれば停止して保持 | 新しい生成パスに作成。移動済み作業ノートは既存の探索規則に従う |
| `ObsidianLayout.sync_finishing` | 概要・ナビゲーション | 生成側の所有hashを確認。人の作業ノートは読み書きしない | 人の編集をそのまま保持 | 人のノートは作らない |
| `ObsidianLayout.sync_themes` | `40-研究/テーマ関連/*.md` | `managed_note`の所有hash。人のテーマノートは存在確認のみ | 生成関連ノートの編集は履歴に写して上書き | 管理済み関連ノートの欠落は再作成しない |
| `ObsidianLayout.configure` | `.obsidian/*.json` | `.obsidian/` がなかった新規Vaultだけ初回に書く（`obsidian_settings` に記録）。以後はアプリのブックマークグループが残っていれば更新するだけ。CSSスニペットは `managed_note` | 既存Vaultの設定は変更しない（OBS-03、ADR-103） | 作成する |
| `ObsidianWorkbench.execute`（反映） | DB | revision一致、元ノートのfingerprint一致、反映中の結果ノートの変更なし、`library_write_lock` | 停止してエラーを状態ノートに表示 | `note_id` で1件に特定できなければ停止 |
| `obsidian_migration.migrate` | ResearchVault全体 | バックアップと移行前後のhash | 中断（`ValueError`） | 移行先に別の内容があれば中断 |
