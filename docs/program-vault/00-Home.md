---
note_id: program-home
note_type: program-index
title: Gurumoji プログラム資料
status: current
updated: 2026-09-14
tags:
  - gurumoji/program
---

# Gurumoji プログラム資料

この `docs/program-vault` フォルダーをObsidianで「保管庫として開く」と、プログラムの構造・保存形式・分析手法・今回の拡張計画を参照できます。分析内容を置く研究用Vaultは、別の `data/obsidian/ResearchVault` に作成しました。それぞれのフォルダーを別々の保管庫として開きます。

ObsidianのVaultはMarkdownファイルを収める通常のフォルダーです。この資料はコミュニティプラグインなしで読める構成とし、両Vaultに独立した `.obsidian` 設定フォルダーを用意しています。[Obsidian公式：データの保存方式](https://help.obsidian.md/Files+and+folders/How+Obsidian+stores+data)

## 今回の計画と登録規約

1. [[40-Design/obsidian-plan|実装計画と受け入れ条件]]
2. [[40-Design/storage-policy|Obsidian・DB・CSV／JSONの保存分類]]
3. [[40-Design/method-rules|分析手法ごとの登録ルール]]
4. [[40-Design/sync-contract|識別子・更新・取り込み・APIの設計]]
5. [[40-Design/program-vault-rules|プログラム資料を維持するルール]]
6. [[40-Design/ui-ux-issues|Web UI デザイン・UX 問題点一覧]]（2026-09-14 調査）

## 収束フェーズ（2026-09-14 調査。新機能より整理・統合・安全化を優先）

**最新の実装：** [[40-Design/convergence-plan#優先修正の実装（2026-09-14）|優先9件と統合2件を修正]]。人のノート保護、未保存時の確認、逆順応答の防止、比較のCSRF・入力版照合、準備変更後の履歴更新を実装した。

**問題点の登録：** [[40-Design/convergence-plan#追加調査と対応順（2026-09-14）|未記載の問題を9件追加]]。UI/UX 5件、プログラム全体4件を追記し、計77件。実装済みの項目も記録として残している。

**前回の取捨選択：** [[40-Design/convergence-plan#今回の取捨選択（2026-09-14）|初回68項目の選別結果]]。元の記録と判断理由は残している。

1. [[40-Design/convergence-plan|アプリ収束計画：目的・重複・統合先・実施フェーズ・最終確認]]
2. [[40-Design/known-issues|既知の問題点と改善方法（BUG／ARCH／OBS／DATA／CFG／DOC／UI）]]
3. [[20-Modules/obsidian-integration|Obsidian連携の現状構造・書き込み主体・競合処理・危険箇所]]
4. [[20-Modules/feature-inventory|機能一覧と分類（Core／Duplicate／Legacy／Unknown）]]
5. [[10-Architecture/system-map|全体構造・データフロー・保存先・設定の所在]]
6. [[40-Design/decisions|設計判断の記録（ADR）]]
7. [[40-Design/ai-development-rules|AI・人の開発ルール（機能を拡散させない）]]
8. [[50-Tests/obsidian-safety-test-plan|Obsidian連携の安全性テスト計画]]

## 現在のプログラムを理解する

- [[30-Data/transcript-preparation-v1|逐語録の分析準備：原本・入力版・確認状態・発言表]]
- [[10-Architecture/overview|処理の流れと構成]]
- [[20-Modules/module-map|機能・コード・テストの対応表]]
- [[30-Data/current-storage|現在の保存形式と不足している点]]
- [[30-Data/analysis-storage-v1|実装済み：AI仕上げ・文章分析の保存仕様と使い方]]
- [[30-Data/four-vaults-v1|実装済み：Software・Input・Visualization・Orchestrator の4 Vault]]（このVaultはSoftware。索引は [[00-Index]]）
- [[50-Analysis-Methods/00-Index|実装済み分析手法とオーケストレーター知識]]

## 登録テンプレート

- [[90-Templates/research-result|分析結果ノート]]
- [[90-Templates/research-memo|研究メモ・コード案]]
- [[90-Templates/method-registration|新しい分析手法の登録票]]

この資料の「現在」は2026-09-13時点の作業ツリーを確認した記述です（4 Vaultの記述は2026-09-14）。研究用Vault・ガイド、AI仕上げ／文章分析の固定保存・ノート生成、Input・Visualization・Orchestratorの3 Vaultへの書き出しは実装済みです。既存会話の一括移行は行いません。計画に含まれる差分取り込み・外部分析登録等は後続工程で、実装済みの契約は上記の保存仕様を参照してください。
