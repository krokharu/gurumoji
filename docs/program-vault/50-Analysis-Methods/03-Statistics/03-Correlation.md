---
note_id: method-correlation
note_type: analysis-method
method_id: correlation
method_version: text-analysis-store-2
algorithm_version: research-ja-3
execution_kind: builtin
title: 相関
status: current
tags: [gurumoji/analysis, gurumoji/statistics, gurumoji/orchestrator]
---

# 相関（`correlation`）

## 実装契約

除外されていない発話について、数値変数の全ペアをPearsonとSpearmanで計算し、係数、N、p値、0.05フラグ、実行不能状態を`correlations`へ保存する。欠測、無限値、定数列、N不足は成功値に変換しない。

## オーケストレーターの判断

- 相関の種類、対象変数、N、欠測規則、分析単位、同一話者／会話内依存を返す。
- Pearsonは線形関係と外れ値、Spearmanは順位関係と同順位を含む前提を人が確認する。散布図・発話IDへのドリルダウンを推奨する。
- 多数ペアのp値は多重比較補正なしである。探索的マークを既定にし、確証的な結論は別の事前計画・モデルへ渡す。

## 言えないこと

相関は因果、方向、話者内変化と話者間差の区別を示さない。発話を独立観測とみなせない設計ではp値の一般化をしない。

## 査読文献

- [Spearman (1904)](https://doi.org/10.2307/1412159) は順位に基づく関連の測定を提示した。
- [Kruskal & Wallis (1952)](https://doi.org/10.1080/01621459.1952.10483441) と同様、順位ベースの手続きでもデータの設計・独立性は別途検討が必要である。

## 担当専門家

[[50-Analysis-Methods/10-Experts/correlation/01-Expert|相関の専門家]]。
