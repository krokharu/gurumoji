---
note_id: method-kwic
note_type: analysis-method
method_id: kwic
method_version: text-analysis-store-2
algorithm_version: content-insights-2
execution_kind: builtin
title: 文脈検索（KWIC）
status: current
tags: [gurumoji/analysis, gurumoji/text, gurumoji/orchestrator]
---

# 文脈検索（`kwic`）

## 実装契約

検索語（1–200文字）を、文字列一致または正規化形一致で、除外されていない本文あり発話から探す。各一致に発話ID、話者、時刻、文字位置、前後40文字、全文、直前・当該・直後の`context_ids`を保存する。最大件数は表示を制御するだけで、`total`は全一致数である。

## オーケストレーターの判断

- `literal`と`normalized`、検索語、話者フィルター、offset、limitを検索結果の一部として保存する。
- 同形異義、否定、引用、言い直しを前後発話まで読んで判断する。検索ヒット数を主張の強さへ変換しない。
- 正規化検索は形態素解析に依存する。簡易解析時は検索の再現性と語形の限界を警告する。

## 言えないこと

KWICは発見・監査の道具であり、頻度比較、テーマ抽出、感情・態度推定の手続きそのものではない。

## 査読文献

- [Kilgarriff (2001)](https://kilgarriff.co.uk/Publications/2001-K-CompCorpIJCL.pdf) はコーパス比較を、[Kudo et al. (2004)](https://aclanthology.org/W04-3230/) は日本語の語境界を論じる。KWICの正規化検索では、どの分割・正規化を用いたかを記録する根拠になる。

## 担当専門家

[[50-Analysis-Methods/10-Experts/quantitative-text-analysis/01-Expert|計量テキスト分析の専門家]]（原文への往復の手順）。
