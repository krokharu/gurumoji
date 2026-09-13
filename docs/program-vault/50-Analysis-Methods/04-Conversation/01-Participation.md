---
note_id: method-participation
method_id: participation
method_version: text-analysis-store-2
algorithm_version: focus-group-local-1
execution_kind: builtin
title: 発話量・参加バランス
status: current
tags: [gurumoji/analysis, gurumoji/conversation, gurumoji/orchestrator]
---

# 発話量・参加バランス（`participation`）

## 実装契約

非除外発話を話者・属性群で集計し、ターン数、発話秒数、全体比、参加者内比、平均ターン秒数、文字数、文字／分、質問候補などを出す。司会・運営役を参加バランスの分母から除く設定があり、バランス指標としてGini、正規化evenness、HHI、最大参加者比を出す。閾値により発話時間集中、低参加、司会比率の確認候補を表示する。

## オーケストレーターの判断

- 分母が`participant_only`か`all_speakers`か、役割設定、除外発話、話者分離の不確かさを常に表示する。
- Gini、evenness、HHIは同じ対象話者集合から計算する。単独話者、総発話時間0、未知話者のケースは解釈不能として扱う。
- 低参加の閾値は診断条件であって研究の結論ではない。司会の質問、参加機会、記録外のやり取り、同意しない沈黙を人が確認する次アクションを出す。

## 言えないこと

長い発話・多いターン・低いGiniは、影響力、満足度、発言機会の公平性、会話の質を測定しない。発話量と発言内容の質を混同しない。

## 査読文献

- [Stephan & Mishler (1952)](https://doi.org/10.2307/2088227) は小集団の相対的参加頻度の分布を扱う。参加分布に規則性があっても、個別会話の望ましさを意味しないことを示唆する基礎文献。
- [Sacks, Schegloff & Jefferson (1974)](https://doi.org/10.2307/412243) はターン交替を会話の組織として分析する。単純な量的ターン数はその組織の一部にすぎない。
