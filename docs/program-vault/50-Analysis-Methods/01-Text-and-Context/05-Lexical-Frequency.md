---
note_id: method-lexical-frequency
method_id: lexical_frequency
method_version: text-analysis-store-2
algorithm_version: research-ja-3
execution_kind: builtin
title: 語彙頻度・TF／DF
status: current
tags: [gurumoji/analysis, gurumoji/text, gurumoji/orchestrator]
---

# 語彙頻度・TF／DF（`lexical_frequency`）

## 実装契約

対象は内容語（NOUN、PROPN、VERB、ADJ、ADV）かつ非ストップ語。発話を文書とし、`term_frequency`にTF（延べ出現）、DF（語を含む発話数）、話者数、TF割合、DF割合、`TF × (log((1+文書数)/(1+DF))+1)`を出す。話者別には上位50語も保持する。旧来の`keywords`は正規表現による簡易頻出語であり、同じ系列ではない。

## オーケストレーターの判断

- 原形・正規形・品詞選択、ストップ語、発話を文書とする定義を結果に必ず併記する。
- TF、DF、TF–IDFを混ぜて順位や意味を説明しない。研究質問に応じた尺度を選び、各語をKWICで確認する。
- 比較をするなら発話数・総内容語数の違いを表示し、少数の長発話だけが順位を支配していないか監査する。

## 言えないこと

頻出語は重要テーマ、共有理解、感情、因果を意味しない。単語の多義性・否定・質問文・転記誤りを失う。

## 査読文献

- [Salton & Buckley (1988)](https://doi.org/10.1016/0306-4573(88)90021-0) は単語重み付けとTF–IDF系の情報検索上の基礎を提示する。
- [Kilgarriff (2001)](https://kilgarriff.co.uk/Publications/2001-K-CompCorpIJCL.pdf) は頻度差を比較する際の標本量と統計的解釈の注意を扱う。
