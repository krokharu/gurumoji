---
note_id: program-index
note_type: vault-index
title: Software Vault 索引
summary: Software Vaultのフォルダー別・目的別入口をまとめる詳細索引。
status: current
verified: 2026-09-27
updated: 2026-09-27
tags:
  - gurumoji/program
---

# Software Vault 索引

このノートは資料群別の詳細索引です。概要と目的別の入口は [[00-Home]]、作業内容ごとの資料の選び方は [[00-AI-Entry]] を参照してください。現在の動作はコードと設定を正本とし、提案中の設計は実装済みの仕様と分けて扱います。

Gurumojiの4 Vaultのうち、プログラムの構造・保存契約・手法定義・設計判断を扱うVault。人向けの入口は [[00-Home]]。4 Vault全体の契約は [[30-Data/four-vaults-v1]]。

| 領域 | 入口 | 内容 |
| --- | --- | --- |
| AI向けタスク別入口 | [[00-AI-Entry]] | 依頼を分類し、必要最小限のノートとコードへ進むための入口 |
| 構成 | [[10-Architecture/overview]]、[[10-Architecture/system-map]] | 処理の流れと担当モジュール、依存関係・データフロー・設定の所在 |
| モジュール | [[20-Modules/module-map]]、[[20-Modules/feature-inventory]]、[[20-Modules/obsidian-integration]]、[[20-Modules/ui-screens]] | 機能・コード・テストの対応、機能分類、Obsidian連携の構造と安全性、Web UIの画面構成と旧画面からの移動先 |
| 収束・問題点 | [[40-Design/convergence-plan]]、[[40-Design/known-issues]]、[[40-Design/decisions]]、[[40-Design/ai-development-rules]] | 整理計画、問題点と改善方法、ADR、AI開発ルール |
| テスト計画 | [[50-Tests/obsidian-safety-test-plan]] | Obsidian連携の安全性テスト |
| 運用 | [[60-Operations/backup-restore]] | DB・メディア・成果物・各Vault・台帳を1組でバックアップ・復元する手順 |
| データ | [[30-Data/four-vaults-v1]]、[[30-Data/analysis-storage-v1]]、[[30-Data/current-storage]]、[[30-Data/transcript-preparation-v1]] | 4 Vault、分析の固定保存、既存の保存形式 |
| 設計 | [[40-Design/obsidian-plan]]、[[40-Design/program-vault-rules]]、[[40-Design/storage-policy]]、[[40-Design/sync-contract]]、[[40-Design/method-rules]]、[[40-Design/ui-ux-issues]]、[[40-Design/video-ui-redesign-plan]]、[[40-Design/quantification-statistics-plan]]、[[40-Design/core-handler-routing-reorganization-plan]]、[[40-Design/analysis-execution-ux-plan]] | 正本の分類、ID・同期、手法の登録規約、UI/UXの問題点、動画処理・確認画面UI改善設計図、発話の数値化とjamovi型統計の自動実行計画、コア再編案、分析実行UXと段階分析（提案） |
| 分析手法・知識 | [[50-Analysis-Methods/00-Index]] | 手法の定義・限界・オーケストレーター契約、専門家定義、共通知識、文献・調査記録 |
| 変更履歴 | [[70-Changes/app-py-phase5]] | 構造変更の記録、互換性、機械可読の移動先データ |
| テンプレート | [[90-Templates/method-registration]]、[[90-Templates/research-result]]、[[90-Templates/research-memo]] | 登録票。検索の既定対象外 |
