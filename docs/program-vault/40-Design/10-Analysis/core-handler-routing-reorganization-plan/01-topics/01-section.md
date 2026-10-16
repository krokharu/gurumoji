---
note_type: reference-section
status: complete
verified: 2026-09-20
updated: 2026-10-05
feature: architecture
tags:
- gurumoji/program
- gurumoji/architecture
- gurumoji/plan
note_id: design-core-handler-routing-reorganization-section-01
title: コア・ハンドラー・ルーティング再編案：コア・ハンドラー・ルーティング再編案
summary: コア・ハンドラー・ルーティング再編案。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 1
- 32
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：コア・ハンドラー・ルーティング再編案

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。


# コア・ハンドラー・ルーティング再編案

## 作業の進め方：実装を依頼されたときの入口

追加分析コアの新規実装では [統合設計の第18〜19節](../../analysis-milestone-visualization-design/00-Index.md) と [実装テストゲート](../../../analysis-design/implementation-gates.json) を優先する。D0〜D7の各工程はTerraの実装・確認とLunaの限定テストを基本とし、当該差分の必須テストが合格するまで次工程を実装しない。M0〜M7はアプリ内分析の段階であり、この開発ゲートとは別。完了済みの旧Phase 0〜4を初めからやり直さない。

**最初の実装単位はPhase 0〜1の読み取り3ルートとする。** 本書には構造再編、AI管理、追加分析、UIの長期計画を含むが、一度の変更で全部を実装しない。利用者が段階・機能を指定した場合はその指定を優先し、以下で対象・依存・完了条件を固定する。計画の文書修正だけを依頼された場合は、構造再編の開始とは扱わない。

### 1回の作業で行うこと

1. **現在の基準を確認する。** `AGENTS.md`と[[00-AI-Entry]]を入口に、対象コード・隣接テスト・契約だけを読む。未コミット変更を含む対象差分と既存テスト結果を確認し、今回の修正と区別する。日付・行数・手法数を固定の合否条件にしない。
2. **実装単位を宣言する。** 対象段階、変更する入口、維持する契約、必要な検証、終了条件を作業開始時に示す。初回は`GET /api/analysis/methods`、`GET /api/library/<item_id>/analysis/runs`、`GET /api/analysis/artifacts/<artifact_id>`に限定する。
3. **その操作を通して完成させる。** 既存責務を再利用してRouting・Handler・必要な依存を一緒に変更する。初回の新規機能ファイルは`web/analysis_routes.py`と`handlers/analysis_queries.py`を基本とする。後続段階の空パッケージ・汎用基盤を先に作らない。
4. **互換性と失敗経路を確認する。** 対象の既存テストと不足する境界検証を行う。初回は3ルートのHTTP契約、成果物hash、ローカル／リモートの公開情報、設定差し替え、FlaskなしのHandler検証を完了する。fixtureは一時DB・架空データとし、実Vault・実APIを使わない。
5. **結果を残し、指示された範囲まで進める。** 変更点、検証結果、未解決点を報告し、実装した段階に関係する既存資料の状態を更新する。後続まで依頼されている場合は受け入れ条件を満たして次へ進む。段階ごとの形式的な再承認は求めず、破壊的・不可逆・重大な非互換変更が必要な場合だけ対象を具体化して確認する。

### 段階の選び方と終了条件

| 作業系列 | 着手条件・順序 | その変更での終了条件 |
| --- | --- | --- |
| 初回の構造再編 | Phase 0 → Phase 1 | 読み取り3ルートが互換、実用的なHandlerをFlaskなしで検証、逆import・二重登録なし |
| 保存と後続機能の分離 | Phase 1の効果確認 → Phase 2 → 必要なPhase 3 → Phase 4 | 移行対象の保存・取消・回復が維持され、未移行機能を完成条件に含めない |
| AI管理 | Phase 1後にAI-0 → AI-1、Phase 2後にAI-2 | 接続抽出と送信方針・来歴拡張を別変更にし、各AI段階の条件を満たす |
| 追加分析 | Phase 2＋AI-2 → FLOW-0 → FLOW-1 → FLOW-2 → FLOW-3 | 最初は手動で親結果から1つの追加分析を実行・保存・再表示できる |
| 統計・型・相談 | FLOW-4／5a／5bの個別依存と統計計画を確認 | 公開する手法ごとに処理・保存・設定／結果UI・一連の操作を完成させる |
| UI | UI-0から独立着手可。実行機能は対応するFLOW段階へ接続 | 選択した保存runの結果を表示し、旧リンク・未保存確認・戻る操作を維持する |

初回を依頼された場合はPhase 1までを完了単位にする。保存契約・新しいAI機能・全UIの変更は別の実装単位に分ける。既存不具合は再編に先行する独立修正にできるが、修正後の挙動を後続の比較基準にする。

FLOW-1以降を始める前に、本書の「計画案から確定入力への変換」「再送・再利用・新規実行の識別」「段階実行の状態と再開」、図4の型付き正本、AI-2の指示固定を確認する。新しい保存形式は版付き拡張として実装し、旧runの読取と旧形式の扱いを同じ変更で検証する。
