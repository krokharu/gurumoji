---
note_id: method-ai-finishing
note_type: analysis-method
method_id: ai_finishing
method_version: text-analysis-store-7
algorithm_version: ai-finishing-3
execution_kind: builtin
title: AI仕上げ・変更記録
status: current
tags: [gurumoji/analysis, gurumoji/generative-ai, gurumoji/orchestrator]
---

# AI仕上げ・変更記録（`ai_finishing`）

## 実装契約

AI仕上げは、アウトライン文脈を参照しつつ発話を分割して校正し、話者名の抽出・検証、必要に応じて仕上げ後アウトラインを作る。校正前後の発話、変更記録、ステージ状態、provider／model／使用量、根拠を固定保存する。Obsidian操作ノートでは、アウトライン作成→仕上げ→人による反映を分離する。

## オーケストレーターの判断

- 校正を意味の改変として扱わないため、各変更を原発話IDと差分に結び、入力本文を失わない。固有名詞・数値・否定・話者帰属は高リスク確認項目にする。
- ステージごとの`completed`、`failed`、`not_requested`を保存し、一部失敗を全成功として公開しない。
- 反映は明示的な人の操作に限定する。生成結果、原文、最終採用版を別artifactとして保持し、AI結果で手動注釈を上書きしない。

## Jev修正要否比較

任意で、校正前の同じ発話をTypeSafe Jevへ送り、各発話を`correction_needed`（修正が必要）または`no_correction_needed`（修正不要）のChoiceとして独立判定する。Jevは本文を生成・編集しない。現行AI側は、本文変更またはノイズ候補を記録した`ai_review`の有無を「修正あり」として比較する。

比較結果は発話メタデータ`jev_review`と`ai_jev_comparison.csv`に保存し、`both_flagged`、`current_only`、`jev_only`、`both_clear`の4区分で可視化する。モデル、修正必要確率、確信度、使用量、ステージ状態も保存する。判定対象は音声ではなく文字起こしと会話文脈であり、不一致を含む候補は必ず原音で確認する。

## 言えないこと

言語モデルによる校正は原発話の正確性・話者同定・意味保存を保証しない。文字起こしそのものの誤り、聴取不能箇所、話者分離誤りを自動で解消したと主張しない。

## 査読文献との関係

この工程はGurumoji固有の編集・監査ワークフローであり、独立した査読済み分析法ではない。[Gilardi et al. (2023)](https://doi.org/10.1073/pnas.2305016120)の注釈評価を過度に一般化せず、差分・根拠・人の承認を妥当性条件として扱う。

## 専門家定義との関係

AI仕上げは逐語録の編集・監査の工程で、分析手法ではないため、専用の専門家を置かない（[[50-Analysis-Methods/10-Experts/00-Index]]）。
