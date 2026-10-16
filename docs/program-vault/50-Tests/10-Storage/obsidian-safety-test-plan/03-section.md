---
note_type: reference-section
status: in-progress
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/tests
- gurumoji/obsidian
note_id: tests-obsidian-safety-plan-section-03
title: Obsidian連携の安全性テスト計画：追加するテストケース（期待する結果）
summary: 追加するテストケース（期待する結果）。出典ノート「Obsidian連携の安全性テスト計画」の分割本文。
parent_note_id: tests-obsidian-safety-plan
source_path: 50-Tests/obsidian-safety-test-plan.md
source_sha256: 5244a19b68353e0baee8e78523afc1299e1d0d9188c030b57c1153b7afb63f7b
source_body_lines:
- 72
- 106
split_on: '2026-10-11'
---

# Obsidian連携の安全性テスト計画：追加するテストケース（期待する結果）

親索引・状態・確認版：[[50-Tests/10-Storage/obsidian-safety-test-plan/00-Index]]。必要な本文だけを取得する。

## 追加するテストケース（期待する結果）

1. **テーマノートを変更しない（OBS-01、07、追加済み）**
   - 準備：fixtureの `20-テーマ/働き方.md` を用意する。
   - 操作：`sync_themes` を2回実行する。
   - 期待：人のノートは初回からバイト一致。別の関連ノートだけを更新し、2回目は差分が出ない。
2. **人のノートへの同期書き込みをなくす（OBS-01、02、追加済み）**
   - 準備：人のテーマ・作業ノートへ独自プロパティと不正YAMLを含む内容を入れる。
   - 期待：人のノートを同期対象として読まず、書き込みも発生しない。生成ノート一般の書き込み直前競合（OBS-04）は別途必要。
3. **状態ファイルを失ってから作り直す（OBS-05、追加済み）**
   - 操作：`prepare` の後に全文ノートを編集し、`state.json` を削除して再度 `prepare` する。
   - 期待：編集した全文とほかの初期ノートが残り、復元確認のエラーで停止する。別パスの新規作成や既存ノートの自動採用はしない。
4. **Vaultの入れ子（OBS-10）**
   - 準備：`<data>/obsidian/.obsidian` を作る。
   - 期待：`publish_input` と `publish_navigation` がエラーで停止し、ファイルを作らない。
5. **ファイル名（OBS-14）**
   - 入力：`CON`、`a:b*c?`、末尾が `.` や空白、260文字に近いタイトル、同じタイトルが2件。
   - 期待：保存できる。上書きしない。パスが上限以内になる。
6. **Wikilinkの保持**
   - 準備：fixtureの `wikilinks.md` を、アプリ所有ではない場所に置く。
   - 操作：移行、テーマ同期、ナビゲーション再生成を実行する。
   - 期待：内容のバイト列が変わらない。
7. **添付**
   - 操作：同じ議事録を2回保存する。
   - 期待：添付は増えず、既存の添付も変わらない。日本語の添付名が扱える。
8. **CSRF（BUG-01、追加済み）**
   - 操作：`Origin: http://127.0.0.1:7860` と `Sec-Fetch-Site: same-origin` を付けて、比較APIへPOSTする。
   - 期待：ヘッダーがなければ403、`X-Gurumoji-Request: 1` があれば200。あわせて `static/*.js` に `apiFetch` 以外の `fetch(` がないことを検査する。
9. **削除後の表示（OBS-11）**
   - 操作：会話を削除する。
   - 期待：概要ノートの状態が「アプリから削除済み」になり、ノートは残る。
10. **操作ログ（OBS-15）**
    - 操作：作成・更新・競合・スキップを発生させる。
    - 期待：ログに操作とhashが残り、発話本文・APIキーは含まれない。
