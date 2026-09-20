---
note_id: method-descriptive-statistics
note_type: analysis-method
method_id: descriptive_statistics
method_version: text-analysis-store-2
algorithm_version: research-ja-3
execution_kind: builtin
title: 記述統計・度数
status: current
tags: [gurumoji/analysis, gurumoji/statistics, gurumoji/orchestrator]
---

# 記述統計・度数（`descriptive_statistics`）

## 実装契約

除外されていない発話を対象に、発話時間、文字数、形態素数、内容語数、語彙多様性、文字／分について全体と比較群ごとのN、欠測、平均、標準偏差、中央値、最小、Q1、Q3、最大を出す。度数は話者、役割、質問候補の件数と割合である。

## オーケストレーターの判断

- 比較軸（話者／役割）、分母、除外規則、0秒発話・形態素未取得などの欠測を明示する。
- 平均だけでなく中央値・四分位を提示し、発話時間や文字数の歪みを隠さない。
- `characters_per_minute`は文字起こしテキストと時刻からの派生値であり、音響的な発話速度とは別物として扱う。

## 言えないこと

記述量は影響力、関与の質、理解度、会話の成功を測定しない。数値の比較に因果的な語りを加えない。

## 査読文献との関係

記述統計は実装上の要約手続きであり、単独の査読論文に依拠する新規手法ではない。後段の群間比較では[Cochran (1952)](https://doi.org/10.1214/aoms/1177729380)のように、分母・期待度数・前提を報告する統計的規律を引き継ぐ。現実装の数値定義と欠測規則が一次資料である。

## 担当専門家

[[50-Analysis-Methods/10-Experts/descriptive-statistics/01-Expert|記述統計の専門家]]。
