---
note_id: method-speaker-characteristics
note_type: analysis-method
method_id: speaker_characteristics
method_version: text-analysis-store-2
algorithm_version: content-insights-2
execution_kind: builtin
title: 話者別特徴語
status: current
tags: [gurumoji/analysis, gurumoji/text, gurumoji/orchestrator]
---

# 話者別特徴語（`speaker_characteristics`）

## 実装契約

内容語かつ非ストップ語について、各話者の「その語を含む発話数／その話者の発話数」と、他話者側の同じ率を比較する。自話者率が高い語だけを`difference_pp`降順で各話者上位10語まで出し、全該当発話の`segment_ids`を残す。比較単位は出現回数でなく**発話内出現率**である。

## オーケストレーターの判断

- 少数発話の話者では率が不安定である。発話数、語の実数、他群の分母を表示し、最小Nを満たさない場合は探索結果として警告する。
- `difference_pp`は効果の説明量であり、有意差検定・キーネス検定ではない。検定が必要なら、対象集合と多重比較計画を別に設計する。
- 各語についてKWICを開き、語義、引用、否定、言い直しを確認する導線を返す。

## 言えないこと

特徴語は話者の信念、立場、属性による因果差を証明しない。発話長、司会の質問、文字起こし誤り、語の多義性で変わる。

## 査読文献

- [Kilgarriff (2001), *Comparing Corpora*](https://kilgarriff.co.uk/Publications/2001-K-CompCorpIJCL.pdf) はコーパス間の頻度比較を扱う。現実装は同論文の検定手順を実装していないため、比率差を有意差と読まない。
- [Salton & Buckley (1988)](https://doi.org/10.1016/0306-4573(88)90021-0) は単語重み付けの基礎を示す。現実装の話者比較はTF–IDFではなく発話率差である。

## 担当専門家

[[50-Analysis-Methods/10-Experts/quantitative-text-analysis/01-Expert|計量テキスト分析の専門家]]。
