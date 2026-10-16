---
note_type: reference-section
status: current
updated: 2026-09-25
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: analysis-experts-index-section-03
title: 分析手法ごとの専門家定義：担当の統合・分割と、専門家を置かない機能
summary: 担当の統合・分割と、専門家を置かない機能。出典ノート「分析手法ごとの専門家定義」の分割本文。
parent_note_id: analysis-experts-index
source_path: 50-Analysis-Methods/10-Experts/00-Index.md
source_sha256: 6835e27a046b96994777b408f3d69461316d4bc1dc03b458398a4fc19d8d8466
source_body_lines:
- 72
- 90
split_on: '2026-10-11'
---

# 分析手法ごとの専門家定義：担当の統合・分割と、専門家を置かない機能

親索引・状態・確認版：[[50-Analysis-Methods/10-Experts/00-Index]]。必要な本文だけを取得する。

## 担当の統合・分割と、専門家を置かない機能

- 形態素解析と係り受けは、同じGiNZAの解析結果を後段の分析に渡す前処理で、確認すべき事項（解析器・版・簡易解析への切り替え・書き言葉で評価された精度）も共通のため、1人の専門家にまとめた。
- 語彙頻度、共起、話者別特徴語、文脈検索（KWIC）は、計量テキスト分析の方法論（[[50-Analysis-Methods/20-Literature/LIT-higuchi-2017-khcoder|樋口 2017]]）の中で、探索と原文への往復に使う道具として扱うため、計量テキスト分析の専門家1人が担当する。
- 手動コード・重要引用（`qualitative_coding`）は、質的分析の各専門家が共通に使う記録の道具で、手法ではないため専門家を置かない。
- 専門家を置かない機能：`local_insights`（アプリ固有の入口の要約）、`ai_insights`（方法論の専門家の手順を実行する手段）、`autonomous_analysis`（Core／Handlerの実行・保存経路で、単独の研究手法ではない）、`outline`・`ai_finishing`・`meeting_minutes`（研究手法ではない補助・編集の機能）。
- 計画中の手法（[[40-Design/10-Analysis/quantification-statistics-plan/00-Index|quantification-statistics-plan]]）は、実装されるまで専門家を置かない。

## 各専門家のフォルダーの構成

| ファイル | 内容 |
| --- | --- |
| `00-Overview.md` | 答えられる問い・答えられない問い、流派の違い、既存の手法ノートへのリンク |
| `01-Expert.md` | 専門家定義と実行定義（アプリが読む） |
| `02-Procedure.md` | 手順、各段階の確認事項、迷いやすい点、典型的な失敗と修正、結果のまとめ方 |
| `03-Quality.md` | 判断基準と品質確認 |
| `04-Applicability-and-Limits.md` | 入力の条件、適用できない条件、言えないこと、グループインタビューでの注意 |
| `05-Cases.md` | 文献で確認できた適用例 |
| `06-Open-Issues.md` | 知識が不足している点、文献間で意見が分かれる点 |
