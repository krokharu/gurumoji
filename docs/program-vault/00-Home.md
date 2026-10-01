---
note_id: program-home
note_type: program-index
title: Gurumoji プログラム資料
summary: Software Vaultの目的と、目的別の読み始め方を案内するトップページ。
status: current
updated: 2026-09-27
tags:
  - gurumoji/program
---

# Gurumoji プログラム資料

## 現行の機能と課題

実装済み機能と対応状態は [[20-Modules/feature-inventory]]、最新課題は [[40-Design/known-issues]] を参照してください。Obsidianの保存契約は [[20-Modules/obsidian-integration]]、バックアップと復元は [[60-Operations/backup-restore]] にあります。

## 分析・AI・UIの再設計（2026-09-20、設計案）

今回の会話で整理した設計は、このSoftware Vaultに保存している。以下は提案・設計モックを含み、実装済みの範囲とは本文で区別する。

- [[40-Design/core-handler-routing-reorganization-plan|設計の本体：分析フロー・LLM/Jev・疑似人格の相談・型・RAWと出力・UI]] — 7つの設計図、ローカル／クラウドと知識の管理、手法とUIの対応表、導入順序・完了条件。
- [[40-Design/quantification-statistics-plan|生成したカラムを統計分析へつなぐ計画]] — 変数定義、妥当性確認、分析単位と統計処理。
- [[40-Design/decisions|設計判断]] — ADR-117：LLM分析専用オーケストレーターと相談、ADR-118：結果閲覧・比較・計画・出力のUI。
- [[90-Templates/method-registration|手法の登録票]] — 分析処理とUIをセットで確認する項目。

閲覧用の[7つの設計図](40-Design/analysis-flow-diagrams.html)と[操作できるUI見本](40-Design/analysis-workspace-prototype.html)も同じVault内に保存している。HTMLはブラウザーで閲覧するためのファイルで、設計の正本は上記Markdown。UI見本は架空データのみで、AI実行や実データの保存は行わない。


この `docs/program-vault` フォルダーをObsidianで「保管庫として開く」と、プログラムの構造・保存形式・分析手法・拡張計画を参照できます。分析内容を置くResearchVaultは設定済みのデータフォルダー `<data>/obsidian/ResearchVault` にあります。それぞれのフォルダーを別々の保管庫として開きます。

ObsidianのVaultはMarkdownファイルを収める通常のフォルダーです。この資料はコミュニティプラグインなしで読める構成とし、両Vaultに独立した `.obsidian` 設定フォルダーを用意しています。[Obsidian公式：データの保存方式](https://help.obsidian.md/Files+and+folders/How+Obsidian+stores+data)

## 詳細な資料

[[00-Index]] にフォルダー別の資料一覧、設計計画、テスト、運用、テンプレートをまとめています。作業ごとの探索順は [[00-AI-Entry]] を参照してください。
