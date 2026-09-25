---
note_id: program-index
note_type: vault-index
title: Software Vault 索引
summary: Gurumoji のプログラム資料（Software Vault）の索引。分析・AI・UI再設計への入口と、既存の問題点・対応計画を示す。
status: current
verified: 2026-09-15
updated: 2026-09-25
tags:
  - gurumoji/program
---

# Software Vault 索引

最新の構造変更：[[70-Changes/app-py-phase5|app.py 分割 Phase 5（2026-09-25）]]。`app.py` を組み立て役に縮め、処理を `web/`・`handlers/`・`services/` へ移した。旧関数の移動先は同じフォルダーのJSONにある。

最新の設計：[[40-Design/core-handler-routing-reorganization-plan|分析・AI・UI再設計（2026-09-20）]]。LLM／Jev、ローカルの専用オーケストレーター、疑似人格の相談、結果の型と追加分析、RAWと出力の分離、7つの設計図、現行21手法と追加予定の手法に対応するUIを記録。分析ボタンの統合、自動／手動実行、進捗画面、段階分析の具体案は [[40-Design/analysis-execution-ux-plan]]。[[00-Home#分析・AI・UIの再設計（2026-09-20、設計案）|ホームの入口]]から関連計画・設計判断・HTML見本も辿れる。

現状の入口：[[40-Design/convergence-plan#プッシュ済みの対応状況（2026-09-15）|コミット1b8fe41の対応状況と残課題]]。優先修正に加え、先行UI改善の対応状態もまとめた。

最新の修正：[[40-Design/convergence-plan#優先修正の実装（2026-09-14）|優先9件と統合2件の実装・検証・残課題]]。

問題点を選ぶ入口：[[40-Design/convergence-plan#追加調査と対応順（2026-09-14）|UI/UX・プログラム全体の追加調査と対応順]]。[[40-Design/convergence-plan#今回の取捨選択（2026-09-14）|初回68件の取捨選択]]も保持している。

Gurumojiの4 Vaultのうち、プログラムの構造・保存契約・手法定義・設計判断を扱うVault。人向けの入口は [[00-Home]]。4 Vault全体の契約は [[30-Data/four-vaults-v1]]。

| 領域 | 入口 | 内容 |
| --- | --- | --- |
| AI向けタスク別入口 | [[00-AI-Entry]] | 依頼を分類し、必要最小限のノートとコードへ進むための入口 |
| 構成 | [[10-Architecture/overview]]、[[10-Architecture/system-map]] | 処理の流れと担当モジュール、依存関係・データフロー・設定の所在 |
| モジュール | [[20-Modules/module-map]]、[[20-Modules/feature-inventory]]、[[20-Modules/obsidian-integration]]、[[20-Modules/ui-screens]] | 機能・コード・テストの対応、機能分類、Obsidian連携の構造と安全性、Web UIの画面構成と旧画面からの移動先 |
| 収束・問題点 | [[40-Design/convergence-plan]]、[[40-Design/known-issues]]、[[40-Design/decisions]]、[[40-Design/ai-development-rules]] | 整理計画、問題点と改善方法、ADR、AI開発ルール |
| テスト計画 | [[50-Tests/obsidian-safety-test-plan]] | Obsidian連携の安全性テスト |
| データ | [[30-Data/four-vaults-v1]]、[[30-Data/analysis-storage-v1]]、[[30-Data/current-storage]] | 4 Vault、分析の固定保存、既存の保存形式 |
| 設計 | [[40-Design/storage-policy]]、[[40-Design/sync-contract]]、[[40-Design/method-rules]]、[[40-Design/ui-ux-issues]]、[[40-Design/video-ui-redesign-plan]]、[[40-Design/quantification-statistics-plan]]、[[40-Design/core-handler-routing-reorganization-plan]]、[[40-Design/analysis-execution-ux-plan]] | 正本の分類、ID・同期、手法の登録規約、UI/UXの問題点、動画処理・確認画面UI改善設計図、発話の数値化とjamovi型統計の自動実行計画、コア再編案、分析実行UXと段階分析（提案） |
| 分析手法・知識 | [[50-Analysis-Methods/00-Index]] | 19手法の定義・限界・オーケストレーター契約、専門家定義、共通知識、文献・調査記録 |
| 変更履歴 | [[70-Changes/app-py-phase5]] | 構造変更の記録、互換性、機械可読の移動先データ |
| テンプレート | `90-Templates/` | 登録票。検索の既定対象外 |
