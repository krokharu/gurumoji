---
note_id: method-ai-insights
method_id: ai_insights
method_version: text-analysis-store-2
algorithm_version: content-insights-3
execution_kind: builtin
title: AI見解・下書き
status: current
tags: [gurumoji/analysis, gurumoji/generative-ai, gurumoji/orchestrator]
---

# AI見解・下書き（`ai_insights`）

## 実装契約

保存済みの発話、話者情報、研究質問、手動コード、重要引用を入力に、総合、テーマ、共通意見、相違・少数意見、追加確認点の構造化下書きを生成する。各項目には1件以上の現行`segment_id`が必須で、許可リスト外のIDは検証で拒否する。provider、model、algorithm_version、fingerprint、生成日時を保存し、入力変更後は`stale`にする。

2026-09-14の作業ツリーでは、AI入力専用の参照番号（`E0001`等）を実行中だけ割り当てる。各呼び出しのJSON Schemaは、その入力にある番号だけを`enum`で許可する。部分結果の統合でも許可集合を絞り、参照番号と話者の対応を渡す。最終結果は元のIDへ戻して再検証し、DB／JSON／ObsidianのID契約は維持する。版更新で既存の見解は古い版として判定されるが、自動再生成はしない。

検証に失敗した場合は、項目位置・具体的なエラーと不正項目の短い抜粋を渡して1回だけ再試行し、進捗にも表示する。再試行後も不正なら全体を失敗として扱い、前回の保存済み結果を保持する。入力と統合対象は各6,000文字を目安に分割するが、モデル別のトークン上限を保証する値ではない。LM Studioの`finish_reason=length`は、JSON構文エラーとは別の上限エラーとして通知する。

実装参照：`src/gurumoji/analysis_insights.py`の`ai_schema`・`create_ai_insights`・`validate_findings`、`src/gurumoji/app.py`の`call_ai_json`。今回の変更は未テスト。[[../../50-Tests/ai-insights-reference-checklist|後日実施するテストチェックリスト]]を参照。

## オーケストレーターの判断

- モデル選択・データ送信先は明示し、同意・機密性・保持方針を確認する。ローカルと外部APIを同じ扱いにしない。
- 出力を研究者のコード・注釈・結論へ自動反映しない。根拠発話を原文で確認し、支持・矛盾・不確実性を人が追記する。
- ID検証は「発話に紐づく」ことだけを確認する。引用が見解を論理的に支持するか、漏れや幻覚がないかは別の人間レビューゲートにする。

## 言えないこと

構造化出力、根拠ID、モデルの高い注釈性能は、生成文の事実性、研究上の解釈妥当性、公平性、再現性を保証しない。

## 査読文献

- [Gilardi, Alizadeh & Kubli (2023)](https://doi.org/10.1073/pnas.2305016120) は限定されたテキスト注釈タスクでのLLM評価を報告した。対象はツイート・ニュースであり、本アプリの日本語会話の解釈や要約を検証した論文ではない。
- よって本機能は結論生成器ではなく、根拠付きの下書き・監査対象として扱う。
