---
note_type: reference-section
status: current
feature: obsidian-storage
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/obsidian
note_id: program-obsidian-integration-section-07
title: Obsidian連携の現状構造と安全性：削除方法
summary: 削除方法。出典ノート「Obsidian連携の現状構造と安全性」の分割本文。
parent_note_id: program-obsidian-integration
source_path: 20-Modules/obsidian-integration.md
source_sha256: 3248688d4a6945a66bfa38de6b5a2475dcf5fb88a5a3f52b16573263e0e86f19
source_body_lines:
- 188
- 215
split_on: '2026-10-11'
---

# Obsidian連携の現状構造と安全性：削除方法

親索引・状態・確認版：[[20-Modules/30-Storage/obsidian-integration/00-Index]]。必要な本文だけを取得する。

## 削除方法

- アプリは通常動作でVaultのノートを削除しない。
- 会話削除はアプリ側の `<data>/trash/<entry_id>/` にDB行とメディアを隔離する。既定30日以内は復元でき、期限切れ後または利用者が完全削除した場合にアプリのゴミ箱から消える（DATA-01）。これはObsidianの `.trash` とは別の機能。
- ResearchVaultのノートと `interviews.json` の登録は残し、`ObsidianLayout.mark_deleted` が概要・一覧の状態を「アプリから削除済み」にする。InputVault台帳も `status: deleted` とする。生成済み分析ノート、`analysis_store`、`obsidian_workbench` は削除しない。
- 復元または同じIDでの再取り込みでは、削除状態を解除し、ResearchVaultとInputVaultの表示を更新する。
- 移行処理だけは、バックアップ後に内容が変わっていない移行元ファイルを `unlink` し、Vault全体の空フォルダーを `rmdir` する（OBS-13）。

## テスト方法

- 既存の自動テストは、すべて一時ディレクトリにDB・Vaultを作る。実際のVaultは使わない。
  - `tests/test_obsidian_layout.py`
  - `tests/test_obsidian_finishing.py`
  - `tests/test_analysis_storage.py`
  - `tests/test_four_vaults.py`
  - `tests/test_vault_coverage.py`
  - `tests/test_vault_note_policy.py`
- Obsidian実機での表示確認は `scripts/check_obsidian_graph.py`（CLIを有効にした環境）で行う。
- 不足しているケースと、テスト用Vaultの設計は [[50-Tests/10-Storage/obsidian-safety-test-plan/00-Index|obsidian-safety-test-plan]] にまとめた。

## 制限事項

- Obsidian公式APIに相当する安全策（原子的な内容の変更、frontmatterの部分更新、ゴミ箱、パスの正規化）は自前の実装で、機能が限られる。
- ポーリングのため、変更の反映に2〜10秒かかる。
- Windowsのパス長上限（260文字）を超える深いパスを事前に確認していない（OBS-14）。
- 同期ソフトやウイルス対策ソフトがファイルをロックすると、`os.replace` が失敗しうる。
- 利用者がVaultの親フォルダーを保管庫として開くと、Vaultが入れ子になる（実環境に痕跡あり、OBS-10）。
