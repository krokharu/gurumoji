---
note_id: expert-group-comparison-statistics-open-issues
note_type: expert-open-issues
expert_id: exp-group-comparison-statistics
title: 群間比較の専門家：未解決事項
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 群間比較の専門家：未解決事項

知識の確認日：2026-09-15。

## 知識が不足している点

- カイ二乗検定の期待度数の基準の文献（Cochran 1952、1954）、Kruskal & Wallis（1952）、Rasch et al.（2011）、Holm（1979）は書誌のみの確認。
- Delacre et al.（2017）の訂正記事（International Review of Social Psychology, 35(1), 2022）の内容を読んでいない。
- 3群以上の分散が等しくない場合の検定（Welch型の分散分析など）の文献は確認していない。

## 実装上の課題

- Welch型の検定、多重比較の補正、入れ子を考慮したモデルは未実装（計画：[[40-Design/quantification-statistics-plan]]）。
- 期待度数の20%の目安は実装上の判断。
