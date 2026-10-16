---
note_type: reference-section
status: in-progress
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/tests
- gurumoji/obsidian
note_id: tests-obsidian-safety-plan-section-01
title: Obsidian連携の安全性テスト計画：Obsidian連携の安全性テスト計画
summary: Obsidian連携の安全性テスト計画。出典ノート「Obsidian連携の安全性テスト計画」の分割本文。
parent_note_id: tests-obsidian-safety-plan
source_path: 50-Tests/obsidian-safety-test-plan.md
source_sha256: 5244a19b68353e0baee8e78523afc1299e1d0d9188c030b57c1153b7afb63f7b
source_body_lines:
- 1
- 19
split_on: '2026-10-11'
---

# Obsidian連携の安全性テスト計画：Obsidian連携の安全性テスト計画

親索引・状態・確認版：[[50-Tests/10-Storage/obsidian-safety-test-plan/00-Index]]。必要な本文だけを取得する。


# Obsidian連携の安全性テスト計画

Obsidian連携で、利用者のノートを壊さないことを確認するためのテスト計画。現状の構造は [[20-Modules/30-Storage/obsidian-integration/00-Index|obsidian-integration]]、問題IDは [[40-Design/50-Governance/known-issues/00-Index|known-issues]] を参照する。2026-09-14のテーマ・仕上げ・比較・未保存保護に加え、最新版`2f13f98`では生成ノートの共通履歴ポリシーと会話削除・復元の回帰テストを追加した。

## 追加済みの検証（2026-09-14）

| 対象 | テスト | 確認すること |
| --- | --- | --- |
| テーマの保護 | `test_obsidian_layout.py:test_theme_sync_keeps_all_human_bytes_and_tracks_removed_links` | CRLF・YAMLコメント・アンカー・独自タグ・不正YAMLを持つ人のテーマのバイト一致、別の関連ノートの更新・リンク解除・冪等性 |
| 仕上げの保護 | `test_obsidian_layout.py:test_finishing_sync_does_not_read_or_write_researcher_notes` | 人の全文・アウトライン・操作ノートが不正YAMLでも読み書きせず保持 |
| 管理状態の消失 | `test_obsidian_finishing.py:test_missing_state_never_overwrites_existing_initial_notes` | 初期ノートが残る状態で再作成を止め、繰り返しても全ノートを保持 |
| 新規作成の競合 | `test_obsidian_finishing.py:test_create_only_write_preserves_a_concurrent_file` | 作成直前に他者が同名ノートを置いても上書きせず、一時ファイルを除去 |
| 比較の保存契約 | `test_interview_comparison.py:test_browser_requests_require_csrf_and_save_the_displayed_input_version` | CSRF拒否と正常送信、版なし400・版違い409、同一要求の重複排除 |
| UIからの保存と移動 | `test_browser_e2e.py:test_comparison_and_unsaved_navigation_regressions` | 実ブラウザーで比較の集計・保存、処理中の条件固定、未保存取消、逆順応答と画面移動後の応答無視 |
| 準備の更新待ち伝播 | `test_vault_coverage.py:test_preparation_save_invalidates_single_and_comparison_runs_atomically` | 単独・比較履歴のstale、Vault状態への反映、トランザクション取消時の整合 |

以下の対応表も最新版`2f13f98`へ更新した。「あり」は記載範囲の検証があることを示し、機能全体の安全性の保証ではない。過去の全393件成功はコミット`1b8fe41`収録前の記録。最新版の全テストは2026-09-26に655件を実行し3件失敗した。絞り込みで再現したのは分析結果の公開テストと、改行コード差を編集と判定するノート履歴テスト。ブラウザー分析画面のタイムアウトは全体実行でのみ発生し、単独実行では通過した。診断時には一時Vaultの`vaults.json`置換でWindows `WinError 5`も確認した。実Vaultは使用していない。
