---
note_id: method-cooccurrence
method_id: cooccurrence
method_version: text-analysis-store-2
algorithm_version: research-ja-3
execution_kind: builtin
title: 共起
status: current
tags: [gurumoji/analysis, gurumoji/text, gurumoji/orchestrator]
---

# 共起（`cooccurrence`）

## 実装契約

発話を文書とし、語彙頻度上位`cooccurrence_top_terms`（既定60、10–200）の内容語から、同一発話に存在する重複なし語ペアを数える。`cooccurrence_min_count`（既定2）以上を残し、共起発話数、各語のDF、Jaccard `c/(dfa+dfb-c)`、Dice `2c/(dfa+dfb)`を出し、Jaccard、共起数、語順で最大500辺へ整列する。

## オーケストレーターの判断

- 分析単位、候補語数、最小共起数、ストップ語をネットワーク図と結果に常に表示する。
- 単一発話の長さや司会の質問が辺を作るため、重要辺は代表発話とKWICを返して人が確認する。
- 比較対象間で閾値や語集合を変えない。ネットワークの見た目で重み・孤立語を隠さない。

## 言えないこと

同じ発話にある二語は、概念的関係、因果、同意、Obsidianリンク、話者間の関係を意味しない。

## 査読文献

- [Callon et al. (1983)](https://doi.org/10.1177/053901883022002003) は共語分析を問題領域のネットワークとして扱う基礎論文。
- [Salton & Buckley (1988)](https://doi.org/10.1016/0306-4573(88)90021-0) は、語の重み付けが表現と検索結果へ強く影響することを示す。現実装のJaccard/Diceは同論文のTF–IDFと別の尺度である。
