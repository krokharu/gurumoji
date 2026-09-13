---
note_id: program-home
note_type: program-index
title: Gurumoji プログラム資料
status: current
updated: 2026-09-13
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

## 現在のプログラムを理解する

- [[10-Architecture/overview|処理の流れと構成]]
- [[20-Modules/module-map|機能・コード・テストの対応表]]
- [[30-Data/current-storage|現在の保存形式と不足している点]]
- [[30-Data/analysis-storage-v1|実装済み：AI仕上げ・文章分析の保存仕様と使い方]]
- [[50-Analysis-Methods/00-Index|実装済み分析手法とオーケストレーター知識]]

## 登録テンプレート

- [[90-Templates/research-result|分析結果ノート]]
- [[90-Templates/research-memo|研究メモ・コード案]]
- [[90-Templates/method-registration|新しい分析手法の登録票]]

この資料の「現在」は2026-09-13時点の作業ツリーを確認した記述です。2つのVault・ガイドと、AI仕上げ／文章分析の固定保存・ノート生成は実装済みです。既存会話の一括移行は行いません。計画に含まれる差分取り込み・外部分析登録等は後続工程で、実装済みの契約は上記の保存仕様を参照してください。
