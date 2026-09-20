---
note_id: method-local-insights
note_type: analysis-method
method_id: local_insights
method_version: text-analysis-store-2
algorithm_version: content-insights-2
execution_kind: builtin
title: ローカル見解
status: current
tags: [gurumoji/analysis, gurumoji/text, gurumoji/orchestrator]
---

# ローカル見解（`local_insights`）

## 実装契約

`analysis_insights.build_content_analysis` が、除外されていない本文あり発話と形態素表から最大5件の確認用メッセージを決定的に作る。優先順は、手動コード、重要引用、複数話者に出る内容語、話者別特徴語、最後に頻出の確認語である。各メッセージは必ず`segment_ids`を持つ。

## オーケストレーターの判断

- これは研究結論ではなく、原文を読む順番を提案する**探索補助**として扱う。
- 形態素エンジンが`fallback`なら、ひらがなの断片を見解へ昇格させない現行仕様を維持し、結果にエンジン状態を表示する。
- 見解の文字列ではなく`segment_ids`を根拠の正本にし、本文・設定・注釈・話者属性を含むfingerprintが変われば再計算する。

## 言えないこと

語が複数話者に現れることは合意を、コード数や重要引用数は重要性を、発話率差は話者の性質を意味しない。人が前後文脈、反例、コード定義を確認する。

## 査読文献との関係

この機能そのものに対応する査読済みの標準分析法はない。頻度・比較の部品は[[05-Lexical-Frequency|語彙頻度]]と[[02-Speaker-Characteristics|話者別特徴語]]を参照し、質的な解釈は[[../05-Qualitative/01-Qualitative-Coding|手動コード・重要引用]]に従う。[Braun & Clarke (2006)](https://doi.org/10.1191/1478088706qp063oa)が示すように、テーマ・解釈は反復的な研究者の仕事である。したがって論文では「自動見解」として研究結果に引用せず、探索・監査用の補助として記述する。

## 専門家定義との関係

ローカル見解は分析手法ではなく、原文を読む順番を提案する探索補助のため、専用の専門家を置かない（[[50-Analysis-Methods/10-Experts/00-Index]]）。頻度・特徴語の部品の解釈は[[50-Analysis-Methods/10-Experts/quantitative-text-analysis/01-Expert|計量テキスト分析の専門家]]の定義を参照する。
