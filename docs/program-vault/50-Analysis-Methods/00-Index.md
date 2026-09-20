---
note_id: analysis-methods-index
note_type: knowledge-index
title: 実装済み分析手法とオーケストレーター知識
summary: 実装済みの分析手法、専門家定義、共通知識、文献・調査記録への入口。
status: current
feature: analysis
verified: 2026-09-14
tags:
  - gurumoji/analysis
  - gurumoji/orchestrator
---

# 実装済み分析手法とオーケストレーター知識

`src/gurumoji/analysis_method_registry.py` に登録されている19手法を、実装と査読文献の両方から整理した知識ベース。将来のオーケストレーターは、ここにある入力契約・検証・解釈境界を守って実行計画を作る。

## 使い方

1. 実行候補の手法ノートで `method_id`、必要入力、出力、停止条件を確認する。
2. [[00-Orchestrator-Common-Contract|共通オーケストレーター契約]]に従い、入力revision・設定・エンジン／モデル版を固定する。
3. 数値・モデル出力を解釈へ変換する前に、その手法ノートの「言えないこと」と根拠発話を確認する。
4. 文献の書誌情報と、実装に直接対応する範囲は[[99-Peer-Reviewed-References|査読文献一覧]]を参照する。
5. 手法の前提・適用条件・手順・禁止事項は、担当する[[10-Experts/00-Index|専門家定義]]を確認する。文献の査読状態と確認範囲は[[20-Literature/00-Index|文献ノート]]を正とする。

## 専門家定義と方法論の知識（2026-09-16追加）

- [[10-Experts/00-Index|分析手法ごとの専門家定義]] — 17人。実行時に `src/gurumoji/method_experts.py` が、選んだ手法の専門家だけを読み込む
- [[00-Method-Selection-Guide|分析手法と専門家の選び方]]
- [[08-Common-Knowledge/00-Index|全専門家に共通する知識]]
- [[20-Literature/00-Index|文献ノート]] — 1文献1ノートで、査読状態、確認範囲、訂正の有無を記録
- [[30-Research-Logs/00-Index|調査記録]]

## 方法群

- [[01-Text-and-Context/00-Index|テキスト・文脈]] — `local_insights`、`speaker_characteristics`、`morphology`、`syntax`、`lexical_frequency`、`cooccurrence`、`kwic`
- [[02-Semantic-and-Audio/00-Index|意味・音声]] — `transformer_topics`、`audio_emotion`
- [[03-Statistics/00-Index|統計]] — `descriptive_statistics`、`group_statistics`、`correlation`
- [[04-Conversation/00-Index|会話構造]] — `participation`、`conversation_dynamics`、`segment_classification`
- [[05-Qualitative/00-Index|質的分析]] — `qualitative_coding`
- [[06-Generative-and-Workflow/00-Index|生成AI・ワークフロー]] — `ai_insights`、`outline`、`ai_finishing`

## このノート群の範囲

- 「査読文献」は学術誌論文または査読付き国際会議論文を優先する。ソフトウェア文書、モデルカード、KH Coderマニュアルは実装確認用であり、査読根拠としては混同しない。
- `intfloat/multilingual-e5-small` の直接の技術報告はプレプリントであるため、Transformerテーマ分析では査読済みの文埋め込み・クラスタリング研究を方法の基礎として引用し、E5そのものは実装依存情報として分ける。
- `local_insights`、`outline`、`ai_finishing` は独立した確立分析法ではなく、Gurumoji固有の根拠付き補助／編集機能である。直接の妥当性を査読論文が保証するものではない。

関連: [[40-Design/method-rules|分析手法ごとのObsidian登録規約]]、[[90-Templates/method-registration|分析手法の登録票]]、[[10-Architecture/overview|処理の流れと構成]]
