---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-01
title: 分析マイルストーン・可視化プログラム・UI統合設計：分析マイルストーン・可視化プログラム・UI統合設計
summary: 分析マイルストーン・可視化プログラム・UI統合設計。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 1
- 21
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：分析マイルストーン・可視化プログラム・UI統合設計

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。


# 分析マイルストーン・可視化プログラム・UI統合設計

## 1. この文書の位置づけと閲覧入口

第18.7節の初回導入範囲（既存の記述集計2手法、手動測定、M0〜M7、JSON/CSV/ZIP、3生成Vault公開）まで実装済み。47成果物、LLM 7役割、推測統計、静止画像、SAV/jamovi/XLSXは能力一覧で未提供として返し、成功扱いしない。画像とUI試作の数値・発話は架空データであり、実装試験も一時DB・一時Vaultだけを使う。

- [UI設計プレビュー](../../../analysis-design/ui-blueprint.html)：外部通信なしで開く画面試作。結果、手動設計、実行状況、比較、出力、根拠を確認できる。
- [画像生成によるUI案](../../../analysis-design/ui-concept-v2.png)：4画面の視覚的な方向性。文字・状態・操作の正本は下記構造定義。
- [構造化したUI・成果物定義](../../../analysis-design/design-spec.json)：画面ID、領域、操作、状態、データ連携、47成果物の対応。
- [図の一覧](../../../analysis-design/diagrams.html)：分析・Obsidianのシーケンス、マイルストーン、UI、データ、システム構成、実装テスト工程の7図。
- [画像生成プロンプト](../../../analysis-design/image-prompt.md)：生成方法と原文。
- [分析コア・LLM・Obsidianの構成図](../../../analysis-design/analysis-architecture.svg) / [連携シーケンス](../../../analysis-design/obsidian-sequence.svg)：メインコアとの分離と往復連携。
- [システム構成の構造JSON](../../../analysis-design/analysis-architecture.json) / [LLM共通契約Schema](../../../analysis-design/llm-contract.schema.json) / [要求・応答例](../../../analysis-design/llm-contract.examples.json)：第13〜16節の機械可読定義。
- [分析コアの制御契約](../../../analysis-design/core-control-contract.json)：第17節の要求・指示・報告・判断・集約応答とデータ不足の例。
- [確定計画・分析コアのSchema](../../../analysis-design/core-control.schema.json)：第18節の二段階確定、停止・警告、公開状態の構造検証。状態遷移表と正常例は制御契約に収録。

関連：[[40-Design/10-Analysis/analysis-execution-ux-plan/00-Index|analysis-execution-ux-plan]]、[[40-Design/10-Analysis/quantification-statistics-plan/00-Index|quantification-statistics-plan]]、[[40-Design/10-Analysis/conversation-analysis-extension-plan/00-Index|conversation-analysis-extension-plan]]、[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]、[[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]]、[[20-Modules/40-Interface/ui-screens/00-Index|ui-screens]]。

今回の利用者指定は、従来計画の「既存手法のチェック選択としての手動」「段階内は逐次でもよい」を更新する。**手動＝ラベル・測定・尺度を手入力し、カラムと分析手法を選択すること。独立した分析は段階内で並列実行し、全必須処理が完了するまで次段階は開始しない。** 現行実装の説明は書き換えず、新規開発時の要件として扱う。
