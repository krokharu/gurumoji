---
note_id: program-home
note_type: program-index
title: Gurumoji プログラム資料
status: current
updated: 2026-09-20
tags:
  - gurumoji/program
---

# Gurumoji プログラム資料

## 分析・AI・UIの再設計（2026-09-20、設計案）

今回の会話で整理した設計は、このSoftware Vaultに保存している。以下は提案・設計モックを含み、実装済みの範囲とは本文で区別する。

- [[40-Design/core-handler-routing-reorganization-plan|設計の本体：分析フロー・LLM/Jev・疑似人格の相談・型・RAWと出力・UI]] — 7つの設計図、ローカル／クラウドと知識の管理、手法とUIの対応表、導入順序・完了条件。
- [[40-Design/quantification-statistics-plan|生成したカラムを統計分析へつなぐ計画]] — 変数定義、妥当性確認、分析単位と統計処理。
- [[40-Design/decisions|設計判断]] — ADR-117：LLM分析専用オーケストレーターと相談、ADR-118：結果閲覧・比較・計画・出力のUI。
- [[90-Templates/method-registration|手法の登録票]] — 分析処理とUIをセットで確認する項目。

閲覧用の[7つの設計図](40-Design/analysis-flow-diagrams.html)と[操作できるUI見本](40-Design/analysis-workspace-prototype.html)も同じVault内に保存している。HTMLはブラウザーで閲覧するためのファイルで、設計の正本は上記Markdown。UI見本は架空データのみで、AI実行や実データの保存は行わない。

**現在の対応状況：** [[40-Design/convergence-plan#プッシュ済みの対応状況（2026-09-15）|対応済み・一部対応・残課題]]。実装の基準はプッシュ済みコミット`1b8fe41`。全77件の課題について、対応状態と優先度を別々に管理しています。

この `docs/program-vault` フォルダーをObsidianで「保管庫として開く」と、プログラムの構造・保存形式・分析手法・今回の拡張計画を参照できます。分析内容を置く研究用Vaultは、別の `data/obsidian/ResearchVault` に作成しました。それぞれのフォルダーを別々の保管庫として開きます。

ObsidianのVaultはMarkdownファイルを収める通常のフォルダーです。この資料はコミュニティプラグインなしで読める構成とし、両Vaultに独立した `.obsidian` 設定フォルダーを用意しています。[Obsidian公式：データの保存方式](https://help.obsidian.md/Files+and+folders/How+Obsidian+stores+data)

## 今回の計画と登録規約

1. [[00-AI-Entry|AI向けタスク別入口]]
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
7. [[40-Design/ai-development-rules|AI・人の開発ルール（必要な情報だけで安全に変更する）]]
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

入口・課題一覧・保存仕様は2026-09-15にプッシュ済みコミット`1b8fe41`と照合しました。各ノートの確認日は`verified`または`updated`を参照してください。Software・Input・Visualization・Orchestratorの4 Vaultに加え、既存のResearchVaultを継続利用しています。物理的な保管庫は計5つです。分析準備、会議議事録・複数インタビュー比較の固定保存も実装済みです。差分取り込み・外部分析登録等は後続工程で、現在の契約は上記の保存仕様を参照してください。
