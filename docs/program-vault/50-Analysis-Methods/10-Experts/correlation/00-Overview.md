---
note_id: expert-correlation-overview
note_type: expert-overview
expert_id: exp-correlation
title: 相関の専門家：概要
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 相関の専門家：概要

専門家定義：[[50-Analysis-Methods/10-Experts/correlation/01-Expert]]

## この専門家が答える問い

- 発話単位の数値変数（発話時間、文字数、形態素数など）の組み合わせで、PearsonとSpearmanの相関係数、N、p値はどうか。計算できない状態（欠測、定数列、N不足）はどれか。[実装判断] 計算の定義は既存の手法ノート [[50-Analysis-Methods/03-Statistics/03-Correlation]] による。

## この専門家が答えない問い

| 問い | 移す先・理由 |
| --- | --- |
| 群の差 | [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert\|群間比較]] |
| 分布の要約 | [[50-Analysis-Methods/10-Experts/descriptive-statistics/01-Expert\|記述統計]] |
| 因果、方向、話者内の変化と話者間の差の区別 | 相関はそれらを示さない（既存ノート） |

## 流派

| 流派 | この定義での扱い |
| --- | --- |
| 発話単位のPearson・Spearman相関（既定） | 実装済み。探索的に扱う |
| 変換や並べ替え検定による検定 | 未実装。[文献] 非正規データでは変換や並べ替え検定が誤りを減らす場合があるとする研究を限界の根拠にする（[[50-Analysis-Methods/20-Literature/LIT-bishara-hittner-2012-correlation\|Bishara & Hittner 2012]]、要旨） |

## 担当する実装

- `correlation`（[[50-Analysis-Methods/03-Statistics/03-Correlation]]）


## スキル対応と知識充足の入口（提案）

[[50-Analysis-Methods/10-Experts/correlation/08-Skill-Hook-Binding|段階別のスキル・hook対応登録案]] と [[50-Analysis-Methods/50-Knowledge-Evaluation/expert-stage-readiness|17専門家の充足・不足表]]。currentPackは暫定維持し、08の実行readerは未接続。研究者の採否は未確認として保持する。
