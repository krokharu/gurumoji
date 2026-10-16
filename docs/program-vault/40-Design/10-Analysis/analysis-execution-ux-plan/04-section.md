---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/program
- gurumoji/analysis
- gurumoji/ui
- gurumoji/orchestrator
note_id: analysis-execution-ux-plan-section-04
title: 分析実行UX統合・段階分析設計：7. 自動実行の規則
summary: 7. 自動実行の規則。出典ノート「分析実行UX統合・段階分析設計」の分割本文。
parent_note_id: analysis-execution-ux-plan
source_path: 40-Design/analysis-execution-ux-plan.md
source_sha256: 1bc504e638f40bdced00fbee6a2763e8bffc51f74a85ded0fd11d17cdacf2d93
source_body_lines:
- 202
- 260
split_on: '2026-10-11'
---

# 分析実行UX統合・段階分析設計：7. 自動実行の規則

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-execution-ux-plan/00-Index]]。必要な本文だけを取得する。

## 7. 自動実行の規則

自動実行の既定計画は次の順で作る。

1. 入力・設定の未保存と版競合を確認する。
2. 完了済みで現行入力に一致する結果は再利用候補にする。
3. ローカル・決定的・無料の基礎分析を選ぶ。
4. ローカルモデルの準備状況を確認し、利用可能なら構造化処理を選ぶ。
5. 外部送信、費用、研究者判断を伴う処理は、事前に利用者が有効化したものだけ選ぶ。
6. 親結果、必要列、件数、尺度、手法前提が揃った後続だけ実行可能にする。
7. 新しい概念、尺度、コードブックの採用が必要なら、実行せず確認待ちにする。

自動実行の設定は、少なくとも次の3プリセットから始める。

- `ローカルのみ（推奨）`：段階0〜3のうち外部送信なしで実行可能なもの。
- `AI支援を含む`：許可したprovider・上限の範囲で段階4まで含める。
- `更新が必要な分析のみ`：現行入力で`stale`または未実行の段階だけを計画する。

常時監視による無操作の自動再実行は初期対象外とする。本文保存直後に高コスト処理が勝手に始まらないよう、最初は利用者が `分析を実行`を押した後の計画内だけを自動進行させる。

## 8. 手動実行の規則

手動実行では「手法名の一覧」だけでなく、目的から選べるようにする。

- 会話全体を把握する
- 発言のテーマを整理する
- 発話を分類・数値化する
- 話者や群を比較する
- AIで見解の下書きを作る
- 保存済み結果から追加分析する

目的を選ぶと候補手法を提示し、利用不可の手法も不足条件を添えて表示する。詳細設定では手法を直接選べる。選択結果は実行前の計画一覧に戻り、そこで対象・依存・外部送信を最終確認する。

## 9. API・保存への影響

### 9.1 初期段階で再利用するもの

- 現在の分析取得・保存API
- AI見解とTransformerの開始・状態取得・取消API
- 発話分類API
- 分析履歴・成果物・Vault再試行API
- `request_id`、`source_revision`、`analysis_revision`、fingerprintによる競合・重複防止
- 現在の`AnalysisStore`と固定成果物

### 9.2 段階実行で追加するもの

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/05-section#段階実行の状態と再開（FLOW-1〜2で追加）|既存の提案]]どおり、`analysis_pipeline_requests`と`analysis_step_attempts`を版付き拡張として追加する。既存の文字起こしジョブや`analysis_pending_packages`へ統合しない。

想定する操作APIは次のとおり。URLとpayloadは実装時に既存Routing規約へ合わせて確定する。

| 操作 | 目的 |
| --- | --- |
| 計画プレビュー | 自動／手動設定から、段階、依存、再利用、送信、見積り、実行不可理由を返す。副作用なし |
| 計画受付 | 固定計画と入力を保存し、同じ`request_id`の二重受付を防ぐ |
| 実行状態取得 | 計画、各段階、使用量、警告、結果runを返す。取得だけで再実行しない |
| 取消要求 | 未開始段階を取消し、実行中段階へ取消要求を伝える |
| 段階再試行 | 失敗・中断段階に新しい試行番号を作り、完了済み親結果を検証して再利用する |
| 明示再開 | 再起動後の`interrupted`を、入力・方針・残予算確認後に再開する |
