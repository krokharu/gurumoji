---
note_id: method-group-statistics
note_type: analysis-method
method_id: group_statistics
method_version: text-analysis-store-2
algorithm_version: research-ja-3
execution_kind: builtin
title: クロス集計・群間比較
status: current
tags: [gurumoji/analysis, gurumoji/statistics, gurumoji/orchestrator]
---

# クロス集計・群間比較（`group_statistics`）

## 実装契約

比較軸は話者または役割。比較軸×質問候補、比較軸×手動コード（上位50）、比較軸×選択語（上位30）のクロス集計と行・列・全体百分率を作る。SciPyが使える場合、Pearsonカイ二乗（Cramér's V、期待度数5未満セル数）、一元配置ANOVA（η²）、Kruskal–Wallis（ε²）を発話単位で計算する。

## オーケストレーターの判断

- 各検定でN、群数、期待度数、効果量、p値、仮定注記、未計算理由を保存する。p値だけを返さない。
- `statistics_group_by`、選択語、コードブック、発話の除外をfingerprintへ含める。後からコード定義を変えた結果を混ぜない。
- 同一話者・同一会話内発話の依存性を必ず警告する。複数会話を一般化する研究には発話を独立標本とする結果を最終推論にしない。
- 多重比較補正は未実装。多数のコード・語・変数を走らせるときは、実行前に補正方針か探索的分析としての扱いをユーザーに選ばせる。

## 言えないこと

有意差は因果、実質的重要性、個人差の安定性を意味しない。小さい期待度数や少数群ではカイ二乗の近似を過信しない。

## 査読文献

- [Cochran (1952)](https://doi.org/10.1214/aoms/1177729380) はカイ二乗検定の適用上の問題を詳細に扱う。
- [Kruskal & Wallis (1952)](https://doi.org/10.1080/01621459.1952.10483441) は一要因の順位に基づく分布比較を提案した。

ANOVA、Cramér's V、η²、ε²の計算はSciPy実装へ委ねている。論文報告ではライブラリ版と検定の前提確認も併記する。

## 担当専門家

[[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert|群間比較の専門家]]。結果の解釈の適用条件・手順・禁止事項と、文献の確認範囲は専門家定義を参照する。
