---
note_id: program-index
note_type: vault-index
title: Software Vault 索引
summary: Gurumoji のプログラム資料（Software Vault）の索引。問題点は追加調査9件を含む77件。最新の対応順は収束計画を参照。
status: current
verified: 2026-09-14
tags:
  - gurumoji/program
---

# Software Vault 索引

最新の修正：[[40-Design/convergence-plan#優先修正の実装（2026-09-14）|優先9件と統合2件の実装・検証・残課題]]。

問題点を選ぶ入口：[[40-Design/convergence-plan#追加調査と対応順（2026-09-14）|UI/UX・プログラム全体の追加調査と対応順]]。[[40-Design/convergence-plan#今回の取捨選択（2026-09-14）|初回68件の取捨選択]]も保持している。

Gurumojiの4 Vaultのうち、プログラムの構造・保存契約・手法定義・設計判断を扱うVault。人向けの入口は [[00-Home]]。4 Vault全体の契約は [[30-Data/four-vaults-v1]]。

| 領域 | 入口 | 内容 |
| --- | --- | --- |
| 構成 | [[10-Architecture/overview]]、[[10-Architecture/system-map]] | 処理の流れと担当モジュール、依存関係・データフロー・設定の所在 |
| モジュール | [[20-Modules/module-map]]、[[20-Modules/feature-inventory]]、[[20-Modules/obsidian-integration]] | 機能・コード・テストの対応、機能分類、Obsidian連携の構造と安全性 |
| 収束・問題点 | [[40-Design/convergence-plan]]、[[40-Design/known-issues]]、[[40-Design/decisions]]、[[40-Design/ai-development-rules]] | 整理計画、問題点と改善方法、ADR、AI開発ルール |
| テスト計画 | [[50-Tests/obsidian-safety-test-plan]] | Obsidian連携の安全性テスト |
| データ | [[30-Data/four-vaults-v1]]、[[30-Data/analysis-storage-v1]]、[[30-Data/current-storage]] | 4 Vault、分析の固定保存、既存の保存形式 |
| 設計 | [[40-Design/storage-policy]]、[[40-Design/sync-contract]]、[[40-Design/method-rules]]、[[40-Design/ui-ux-issues]] | 正本の分類、ID・同期、手法の登録規約、UI/UXの問題点 |
| 分析手法 | [[50-Analysis-Methods/00-Index]] | 18手法の定義・限界・オーケストレーター契約 |
| テンプレート | `90-Templates/` | 登録票。検索の既定対象外 |
