---
note_type: reference-section
status: current
feature: obsidian-storage
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/obsidian
note_id: program-obsidian-integration-section-08
title: Obsidian連携の現状構造と安全性：今後変更するときの注意事項
summary: 今後変更するときの注意事項。出典ノート「Obsidian連携の現状構造と安全性」の分割本文。
parent_note_id: program-obsidian-integration
source_path: 20-Modules/obsidian-integration.md
source_sha256: 3248688d4a6945a66bfa38de6b5a2475dcf5fb88a5a3f52b16573263e0e86f19
source_body_lines:
- 216
- 237
split_on: '2026-10-11'
---

# Obsidian連携の現状構造と安全性：今後変更するときの注意事項

親索引・状態・確認版：[[20-Modules/30-Storage/obsidian-integration/00-Index]]。必要な本文だけを取得する。

## 今後変更するときの注意事項

1. 新しい書き込み処理を作らない。まず [[40-Design/50-Governance/decisions/00-Index|decisions]] ADR-101 の方針（1つの書き込み関数、書き込み前の予定hash、conflict・missingの表示）に合わせる。
2. 人が所有するノートの全体を再生成して上書きしない。テーマと仕上げノートにはADR-109を適用し、関連情報・現在の参照を別の生成ノートへ書く。hash再確認だけを外部編集に対する排他保証と扱わない。`.obsidian`は新規Vaultの初回だけ書く（OBS-03、ADR-103）。
3. Vaultのパスは既存の算出元から得る。新しくパスを組み立てない。ユーザーのVaultを推測しない。
4. 判断できない状態では書かずに止め、理由を状態ノート・索引・ログに残す。対象は、Vaultが特定できない、同じ名前がある、YAMLを解析できない、`note_id` が重複している、revisionが一致しない、など。
5. 削除・移動・一括変換を追加する場合は、バックアップ、変更予定の一覧を出すDry Run、再開可能な記録を先に設計する。
6. 変更したら、このノートの該当箇所、[[40-Design/50-Governance/known-issues/00-Index|known-issues]]、[[50-Tests/10-Storage/obsidian-safety-test-plan/00-Index|obsidian-safety-test-plan]]、利用者向けの `docs/OBSIDIAN_*.md` を同じレビュー単位で更新する。

## 危険箇所の要約（G）

| ID | 重要度 | 内容 |
| --- | --- | --- |
| OBS-01 | 高 | テーマ同期が、研究者のテーマノートを所有確認なしで10秒ごとに再シリアライズ・上書きする |
| OBS-04 | 高 | 書き込み主体が5つあり、台帳が4つ、競合時の挙動も4通り |
| OBS-02 | 中高 | 仕上げノートのプロパティ更新に、読み込みから書き込みまでの間の変更検出がない |
| OBS-05 | 中 | `state.json` を失ったり片側だけ復元したりすると、作業台の初期ノートが上書きされうる |
| OBS-03 | 中 | `.obsidian` の設定をアプリが変更する（対応済み 2026-09-25：新規Vaultの初回だけ） |
| OBS-10 | 中 | Vaultの入れ子の痕跡があるのに、検出していない（対応済み 2026-09-26：`vault_registry.nesting_warnings` で警告。保存は継続） |
| OBS-06／07 | 中 | frontmatterの実装が複数あり、全体を再シリアライズする |
| OBS-09／15 | 中 | 監視の停止とスキップが見えない（OBS-09対応済み、OBS-15はスキップのログのみ。2026-09-25） |
| OBS-11／12／13／14 | 低〜中 | 削除後の表示、`file:///` 絶対パス、移行時の空フォルダー削除、パス長（OBS-11・12は2026-09-25、OBS-13・14は2026-09-26に対応済み） |
