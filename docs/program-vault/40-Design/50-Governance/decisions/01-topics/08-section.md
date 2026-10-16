---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-08
title: 設計判断の記録（ADR）：ADR-108 問題点を影響と根拠で選別し、大規模統合を前提にしない
summary: ADR-108 問題点を影響と根拠で選別し、大規模統合を前提にしない。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 297
- 323
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-108 問題点を影響と根拠で選別し、大規模統合を前提にしない

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

### ADR-108 問題点を影響と根拠で選別し、大規模統合を前提にしない

- **状態：** accepted（2026-09-14、課題の選別のみ。コード変更・設定移行・ファイル削除の採用ではない）
- **背景：** 利用者から、プログラム用Obsidianに格納した問題点の取捨選択を依頼された。39件の既知の問題と29件のUI/UX項目には、重複、未計測のリスク、用途の違う機能の統合案が混在していた。
- **決定：** [[40-Design/50-Governance/convergence-plan/04-section#今回の取捨選択（2026-09-14）|convergence-plan#今回の取捨選択（2026-09-14）]] を対応順の正本とし、最優先4件、優先13件、後続8件、統合7件、保留36件に分ける。問題ID・元の記述を残して選別欄を追加し、実装状態とは分けて管理する。
- **理由：** テーマノートのコメント・独自タグ消失と、管理状態のない既存全文の上書きを一時Vaultで再現した。比較POSTのCSRFヘッダー欠落もコードに残るため、実害に近い経路を先に扱う。全体移設やデザイン統一を先に行う必要はない。
- **代替案：** 全項目を旧Phase 0〜6の順に実装する、低優先の項目を削除する、一覧の重要度だけで並べる。いずれも採用しない。未計測項目と元の指摘は再検討できるよう保つ。
- **結果・影響：** ADR-101〜107は引き続き提案であり、一括採用しない。ADR-102の書き込み直前hash確認を排他制御と同等とは扱わない。ADR-107はまず比較機能の修正に絞り、`apiFetch` 本体まで禁止するような一律の文字列検査は採用しない。全保存停止、一律の保存パネル集約、削除行数を基準にした完了条件も採用しない。
- **関連コード・検証：** `static/interview-comparison.js:runComparison/saveComparison`、`app.py:enforce_request_security`、`obsidian_layout.py:sync_themes/sync_finishing/decorate`、`obsidian_finishing.py:prepare/save_note`。再現確認は一時フォルダーで実施。実ブラウザー・同時編集の競合は未確認。コードと実データは変更していない。

### ADR-110 発話の数値化とjamovi型統計の自動実行を、既存の分析層の拡張として段階的に実装する

- **状態：** proposed（計画第2版の方針、2026-09-15。着手の順序は利用者の委任により人格パネルで決定。実装は未着手）
- **背景：** 逐語録をLLMやTransformerなどで数値化し、jamoviで実行できる検定を自動で行いたい。現在の統計は発話単位の4種類の検定だけで、AI由来の変数を検証して検定に使う仕組みがない。
- **決定（案）：**
  - [[40-Design/10-Analysis/quantification-statistics-plan/00-Index|quantification-statistics-plan]]に従う。検定の選択、統計量、報告文の数値はコードが作り、LLMは数値化の候補だけを作る。AI由来の変数は、妥当性ゲートを通してから確認的な検定に使う。
  - 順序は、進行中の作業の確定 → Phase 0 → OBS-18 → Phase 1a → 1b → 2 → 3 → 4 → 5。
  - 検定の計算は、新しいモジュール`statistical_tests.py`にまとめる。
  - 複数会話の推測統計は、別の実行種別`study_statistics`にする。
- **理由：**
  - 検定の計算は`research_analysis`、`transformer_analysis`、`app`（事前アンケート、複数会話）の3か所から使う。1つのモジュールにまとめると、カイ二乗の2実装とブラウザー側の相関計算を置き換えられる（ADR-106の統合の条件）。
  - 新しい実行記録も生成Vaultへ出力するため、書き出し失敗の集約（OBS-18）を先に直す。
  - `interview_comparison`は2〜8件の記述的な比較という契約を持つため、多数の会話の推測統計と混ぜない。
- **代替案：** LLMに検定まで任せる。LLMの機能から始める。検定を`research_analysis.py`の中に置く。`interview_comparison`を拡張する。
- **結果・影響：** Phase 0で保存契約、golden値、依存、ライセンスを先に固める。議論の記録はPersonaVaultの`DLB-20260915-quantification-statistics`（IDで参照）。
- **関連コード：** `research_analysis._statistics_analysis`、`transformer_analysis._backchannel_test`、`static/app.js:speakerSurveyCorrelation`、`app.build_interview_comparison`、`analysis_method_registry.SEPARATE_RUN_METHODS`
