---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-15
title: 分析マイルストーン・可視化プログラム・UI統合設計：18. 全体レビューを反映した確定方針
summary: 18. 全体レビューを反映した確定方針。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 660
- 677
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：18. 全体レビューを反映した確定方針

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。

## 18. 全体レビューを反映した確定方針

本節は前節までの基本構成を維持し、実装前の契約不足を補う。第18節と旧図・旧表現に差異がある場合は本節を新規実装の基準とする。現行コード・保存契約の説明を実装済みに書き換えない。

### 18.1 機械可読契約と状態遷移

LLM共通Schemaはあくまで提案の入口であり、実行権限や確定計画ではない。ホストが提案を検証し、`PlanEnvelope / ExecutionBinding / AnalysisRequest / HandlerDirective / HandlerReport / EligibilityAssessment / CoreDecision / AnalysisResponse`へ変換する。これら8契約を [core-control.schema.json](../../../analysis-design/core-control.schema.json) で構造検証する。

`core-control-contract.json`の`state_machines`を状態遷移表とする。遷移にはfrom/toに加えてguard IDを必須にし、コアの純粋規則がguardを評価、Runtimeが永続状態を比較更新する。表にない遷移は拒否する。Schema合格だけで遷移を許可しない。

- step：検査、資源待ち、計算、検証、保存待ち、確定を分ける。`validating → committed`の途中で保存できない場合は`persisting / blocked`に残す。取消中も明示する。
- pipeline：`accepted / running / waiting / cancelling / completed / failed / cancelled`を用い、待機理由は`data / definition / retry / resource / remote_unknown / storage / publication`で区別する。複数taskの待機理由は一覧で返す。
- milestone：`pending / active / waiting / committed / failed / cancelled`。同じ段階内に実行中の独立taskがあればactiveを維持し、待ちだけになればwaitingとする。
- publication：選択先ごとに`pending / publishing / published / failed / conflict / unknown`。未選択は`not_selected`。
- 終端状態から同じattemptをrunningへ戻さない。再試行は新attempt、確定計画外の変更は新pipeline。取消のない一時待機からの再開は、元の版・判断・許容予算を再検証する。

意味検証には、IDの実在と一意性、入力hash、要求と報告の対応、DAG、段階・bindingの整合、列・尺度・単位、許可provider、予算、代替の互換性、独立単位、研究区分を含める。決定記録は既存の要求・attempt台帳拡張に紐付け、別の実行台帳を増設しない。
