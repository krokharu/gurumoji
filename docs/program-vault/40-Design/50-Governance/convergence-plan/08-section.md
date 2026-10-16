---
note_type: reference-section
status: in-progress
updated: 2026-09-15
tags:
- gurumoji/program
- gurumoji/design
note_id: design-convergence-plan-section-08
title: アプリ収束計画（整理・統合・安全化）：実装後の最終確認（各フェーズの終わりに記入する）
summary: 実装後の最終確認（各フェーズの終わりに記入する）。出典ノート「アプリ収束計画（整理・統合・安全化）」の分割本文。
parent_note_id: design-convergence-plan
source_path: 40-Design/convergence-plan.md
source_sha256: b60640ba092a802e2735beeefa7dc160b6c69c609f7930b46554a0d1751d92d6
source_body_lines:
- 309
- 349
split_on: '2026-10-11'
---

# アプリ収束計画（整理・統合・安全化）：実装後の最終確認（各フェーズの終わりに記入する）

親索引・状態・確認版：[[40-Design/50-Governance/convergence-plan/00-Index]]。必要な本文だけを取得する。

## 実装後の最終確認（各フェーズの終わりに記入する）

### Architecture

- [ ] 責務が明確（[[10-Architecture/10-System/system-map/00-Index|system-map]] と一致している）
- [ ] 同じ役割のServiceや関数が重複していない
- [ ] 循環依存がない（関数内importによる回避も残っていない）
- [ ] 不要なコードが残っていない（削除判断の確認項目の記録がある）

### App

- [ ] 既存機能が動く（全テスト、ブラウザーE2E）
- [ ] 新旧の方式が混在していない
- [ ] UIが複雑になっていない（入口の数が増えていない）

### Data

- [ ] DBを壊していない（migrationに版とバックアップがある）
- [ ] データの欠損がない（件数・hashの比較）

### Obsidian

- [ ] Vaultを誤認しない（入れ子・存在しないルートで停止する）
- [ ] ノートを壊さない
- [ ] frontmatterの未知のキー・型・コメントを保持する
- [ ] Wikilink（`[[note]]`、`[[note|alias]]`、`[[note#heading]]`、`[[note#^block]]`、`![[embed]]`）を保持する
- [ ] 添付ファイルを移動・削除しない
- [ ] 利用者の編集を消さない（競合時は停止して表示する）
- [ ] 同じ入力で二重に生成しない
- [ ] 同期がループしない
- [ ] 削除したデータを復旧できる
- [ ] 日本語のファイル名・長いパス・禁止文字を扱える

### Documentation

- [ ] [[10-Architecture/10-System/system-map/00-Index|system-map]] を更新した
- [ ] [[20-Modules/10-Inventory/feature-inventory/00-Index|feature-inventory]] を更新した
- [ ] [[20-Modules/30-Storage/obsidian-integration/00-Index|obsidian-integration]] を更新した
- [ ] [[40-Design/50-Governance/decisions/00-Index|decisions]] に判断を記録した
- [ ] [[40-Design/50-Governance/known-issues/00-Index|known-issues]] の状態を更新した
- [ ] README・`docs/*.md` と矛盾していない
