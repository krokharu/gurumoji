---
note_id: design-ai-development-rules
note_type: documentation-rules
title: AI・人の開発ルール（機能を拡散させない）
status: current
updated: 2026-09-14
tags:
  - gurumoji/program
  - gurumoji/rules
---

# AI・人の開発ルール（機能を拡散させない）

Codex・Claude などのAIや人がこのリポジトリを変更するときのルール。資料の登録規約は [[40-Design/program-vault-rules]] を、判断の背景は [[40-Design/decisions]] の ADR-106 を参照する。

現在、このリポジトリには `AGENTS.md`・`CONTRIBUTING.md` がない。AIツールが自動で読み込むように、`AGENTS.md` を作る場合は次の方針にする。

- 本文を複製しない。このノートへの参照と、下の「必須ルール」だけを書く。
- ルールの正本は、このノートを1つだけにする。

## 必須ルール

1. **新機能を追加する前に、既存の実装を検索する。** 関数名・API・画面の文言・保存先を検索し、[[20-Modules/feature-inventory]] で同じ目的の機能がないか確認する。
2. **同じ役割のServiceや関数を複数作らない。** 次の優先順で選ぶ。
   1. 既存機能を拡張する
   2. 既存機能に統合する
   3. 小規模に新しく実装する
   4. 新しいシステムを作る

   新しいファイルやクラスを作る場合は、既存のモジュールに統合できない理由を、変更説明と [[40-Design/decisions]] に書く。
3. **変更前に、既存のアーキテクチャを確認する。** [[10-Architecture/system-map]] と [[40-Design/known-issues]] を読み、関係する問題IDを変更説明に書く。
4. **既存処理を残したまま、別の方式を追加しない。** 置き換える場合は、同じ変更の中で呼び出し元を移す。旧実装は [[20-Modules/feature-inventory]] の「削除判断の確認項目」に従って整理する。
5. **似た機能を別の画面として追加しない。** UIの入口を増やす前に、既存のパネルに統合できないか確認する（[[40-Design/ui-ux-issues]]）。
6. **Obsidian関連の変更は特に慎重に行う。** 下記の「Obsidianを変更するときの追加手順」を必ず行う。
7. **Vaultのパスをハードコードしない。** `C:\Users\…`、`Documents\Obsidian`、`.obsidian` の位置を前提にしない。既存の算出元（`VaultRegistry`、`<data>`）から取得し、ユーザーのVaultを推測しない。
8. **ユーザーデータを勝手に削除しない。** ノート・添付・メディア・`runtime/` のファイルは、利用者の確認なしに削除・移動しない。削除が必要な場合は、アーカイブかゴミ箱方式にする。
9. **既存のMarkdownを全体上書きしない。** 「読む → AIで処理 → 全文を再生成 → 上書き」の方式は禁止する。変更するのは、対象のキーと管理区間だけにする。
10. **仕様を変えたら、ドキュメントも同じ変更の中で更新する**（[[40-Design/program-vault-rules]] の対応表）。
11. **大規模な全面書き換えをしない。** 移動と変更を別々のレビュー単位にし、既存のテストを全て通す。
12. **判断できない状態では推測して書き込まず、処理を止める。**

## 変更前チェックリスト

- [ ] 目的に近い既存の関数・APIを検索した（例：`rg "def .*outline" src`、`rg "/api/library/<" src/gurumoji/app.py`）
- [ ] [[20-Modules/feature-inventory]] で分類（Core／Duplicateなど）を確認した
- [ ] 関係する `ARCH-*`・`OBS-*`・`UX-*` の問題IDを確認した
- [ ] 設定を追加する場合、[[40-Design/known-issues]] の「設定ごとの正本」に従った
- [ ] フロントエンドのAPI呼び出しに `apiFetch` を使った（ADR-107）
- [ ] 追加する行数より、統合して削除できる行数を先に検討した

## Obsidianを変更するときの追加手順

1. [[20-Modules/obsidian-integration]] の「書き込み主体ごとの競合処理」で、対象の書き込み主体を特定する。
2. 新しい書き込み処理を作らず、ADR-101 の書き込み判定（将来統合する予定の関数）を使う。統合が済むまでは、同じノートの種類の既存の判定方式に合わせる。
3. 人が所有するノート（研究メモ、`20-テーマ`、`managed_by: researcher`、`.obsidian`）の書き込みでは、次を守る。
   - 書く直前にhashを再確認する。
   - 未知のプロパティ、コメント、Wikilink（`[[note]]`、`[[note|alias]]`、`[[note#heading]]`、`[[note#^block]]`、`![[embed]]`）、callout、ブロックIDを変えない。
4. ファイル名は、Windowsの禁止文字・末尾のドットと空白・予約名・パス長・同名ファイルを考慮する。同じ名前のファイルがあれば、上書きせず停止するか別名にする。
5. 移動・改名・一括変換・移行を行う場合は、次を先に作る。
   - バックアップ
   - Dry Run（件数、作成・更新・移動・削除の予定、競合）
   - 再開できる記録
6. テストは一時フォルダーのテスト用Vaultで行う。`runtime/data/obsidian` などの実際のVaultは使わない（[[50-Tests/obsidian-safety-test-plan]]）。
7. 操作ログに本文を残さない。
8. 次の状態では停止し、理由を表示する。
   - Vaultが特定できない
   - 保存先が分からない
   - 同じ名前のノートと競合する
   - frontmatterを解析できない
   - 同期が競合している
   - `note_id` が重複している
   - revisionが一致しない

## 完了報告に含めること

- 変更した責務と、統合・削除した重複（件数）
- 関係する問題IDと、その状態の更新
- 実行したテストと結果（失敗やスキップも書く）
- 更新したノート（system-map、feature-inventory、obsidian-integration、decisions、known-issues のうち該当するもの）
- 利用者データ（Vault・`runtime/`）に触れたかどうか
