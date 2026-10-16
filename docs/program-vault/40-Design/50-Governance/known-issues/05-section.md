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
note_id: design-known-issues-section-05
title: 既知の問題点と改善方法（収束フェーズ）：CFG：設定
summary: CFG：設定。出典ノート「既知の問題点と改善方法（収束フェーズ）」の分割本文。
parent_note_id: design-known-issues
source_path: 40-Design/known-issues.md
source_sha256: 93c0e1b715181e4d753e26636d16aa88dd9cf9b8c21d45e1ea6a76fb54c75414
source_body_lines:
- 82
- 101
split_on: '2026-10-11'
---

# 既知の問題点と改善方法（収束フェーズ）：CFG：設定

親索引・状態・確認版：[[40-Design/50-Governance/known-issues/00-Index]]。必要な本文だけを取得する。

## CFG：設定

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CFG-01 | 中 | 設定の置き場所が分散している | [[10-Architecture/10-System/system-map/00-Index\|system-map]] の「設定の所在」 | 同じ設定に正本が複数できる | 設定の種類ごとに正本を1つに決める（下表） | 未対応 | 保留：設定ごとの責務を維持 |
| CFG-02 | 中 | 秘密情報と利用者設定が同じファイルにあり、UIが秘密ファイルを書き換える | `config/tokens.json` に、APIキーと `openai_model` などの使用モデルが同居している。`update_token_model` がこのファイルを書き換える | 秘密ファイルの破損リスク。共有してよい設定と秘密が分けられない | 使用モデルは秘密ではない設定ファイルへ段階的に移す（読み込みは新旧両対応、書き込みは新しい方だけ） | 未対応 | 保留：移行・復元仕様が必要 |
| CFG-03 | 低 | 既定値が複数の場所に書かれている | 「Obsidianで仕上げ」の既定が、`JobOptions`・`parse_bool("finish_in_obsidian", default=True)`・`index.html` の `checked` の3か所。会話モードは `app.js` にだけある | 既定を変えるときに漏れる | サーバー側の既定を `GET /api/config` で返し、UIはそれを使う | 未対応 | 保留：既定値を変更する際に統合 |
| CFG-04 | 低 | AIエフォートが2か所にある | `localStorage`、`state.json` | 画面とObsidianで値が食い違う | 正本を会話ごとの `state.json`（仕上げ）とアプリ設定のどちらかに決める | 未対応 | 保留：既定値と実行別指定を区別してから |

設定ごとの正本（案）：

| 設定 | 正本 |
| --- | --- |
| APIキー・トークン | `tokens.json` だけ |
| 使用モデル・既定の処理条件 | アプリ設定ファイル（秘密を含まない） |
| 保存先・ポート・公開設定 | 環境変数（起動時に確定し、画面では表示だけ） |
| Vaultのルート | `vaults.json`（ResearchVaultも登録し、コード内の算出をやめる） |
| 会話ごとの分析条件 | SQLite |
| 仕上げの実行時オプション | 操作ノート → `state.json` |
