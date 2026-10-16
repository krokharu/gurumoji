---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/analysis
- gurumoji/statistics
- gurumoji/design
note_id: design-quantification-statistics-plan-section-08
title: 発話の数値化とjamovi型統計の自動実行計画：10. 既存モジュールへの統合
summary: 10. 既存モジュールへの統合。出典ノート「発話の数値化とjamovi型統計の自動実行計画」の分割本文。
parent_note_id: design-quantification-statistics-plan
source_path: 40-Design/quantification-statistics-plan.md
source_sha256: 72fc8e49117b2416635ff3d9d9b2a07ed9a4e1287e75c4b43f96d73411bf9b04
source_body_lines:
- 218
- 247
split_on: '2026-10-11'
---

# 発話の数値化とjamovi型統計の自動実行計画：10. 既存モジュールへの統合

親索引・状態・確認版：[[40-Design/10-Analysis/quantification-statistics-plan/00-Index]]。必要な本文だけを取得する。

## 10. 既存モジュールへの統合

| 役割 | 統合先 | 変更の要点 | 解消する重複 |
| --- | --- | --- | --- |
| 検定の計算 | 新しいモジュール`statistical_tests.py`（ADR-110） | SciPyとstatsmodelsの計算をまとめ、`research_analysis`、`transformer_analysis`、`app`（事前アンケート、`study_statistics`）から呼ぶ。SciPyとstatsmodelsは関数内でimportする。結果の行は現行の`statistical_tests`の列を拡張する | カイ二乗の2実装、ブラウザー側の相関計算 |
| 変数とデータセット | `research_analysis._segment_dataset`、`RESEARCH_CSV_FIELDS` | 列の追加、話者・参加者・インタビュー単位への集約、`variable_catalog`、`validation_samples` | — |
| 比較軸 | `statistics_group_by` | `attribute:<項目>`、会話属性、参加者コードを追加し、`group_by`と選択肢の語彙を揃える | 統計と参加バランスで選べる比較軸が違う |
| ルール辞書 | `research_analysis`（形態素・正規形） | コーディングルールを宣言的なJSONで定義する。ファイル内のコードは実行しない | `transformer_analysis`の相づち辞書と話者リザルトの正規表現を、移行候補として棚卸しする |
| LLMのコード・評定 | `analysis_insights.create_ai_insights`の参照番号と検証再試行（`checked_call`）を共通化する | 引用の一致検証、試行と全件、キャッシュ、上限トークン、同意の判定、未判定の扱い | 検証再試行の複製を作らない |
| 画面のボタン | 新規作成（文字起こし）、「分析・可視化」の統計パネル | 「文字起こし」「AIで数値化」「統計を実行」を別のボタンにする。AI数値化は既存のAI要求台帳とキャンセルの方式で実行する。新しい画面は作らない | 文字起こしジョブの中でのAI数値化 |
| 埋め込み分類器 | `transformer_analysis`（`encode_texts`、保存したベクトル） | ロジスティック回帰、層化交差検証、確率の出力 | — |
| 複数会話の検定 | 別の実行種別`study_statistics`（`SEPARATE_RUN_METHODS`） | 比較パネルから始める。会話数や群のNが最小Nに届かない場合は記述だけにする | `interview_comparison`の記述的な契約を変えない |
| 事前アンケート | `static/app.js`の集計 | 相関とクロス集計をサーバーの同じ検定関数で計算し、画面は結果を表示する | ブラウザー側の独自計算 |
| 手法の登録 | `analysis_method_registry.METHODS`、`METHOD_GROUPS`、`method_results` | 下の手法IDを追加し、既存の統計3手法は版を上げる | — |
| 保存・Vault | `AnalysisStore`、`VaultRegistry.publish_analysis` | 既存の固定保存、Orchestratorの実行記録、Visualizationの図表仕様を使う。人のノートには書かない（ADR-109） | — |
| 依存とライセンス | `config/requirements.txt`、`LICENSE`、`THIRD_PARTY_NOTICES.md`、README | statsmodelsの追加と、12章の一覧の維持 | — |

手法ID（案）：

| `method_id` | `execution_kind` | 内容 |
| --- | --- | --- |
| `descriptive_statistics`、`group_statistics`、`correlation` | builtin（既存） | 版を上げ、計画に基づく検定・補正・効果量のCIへ拡張する |
| `rule_coding` | builtin | ルール辞書によるコード |
| `ai_coding` | builtin | LLMによるコード・評定の候補 |
| `embedding_classifier` | builtin | E5埋め込み＋分類器 |
| `coding_reliability` | builtin | 人手・AI・実行間の一致度とゲートの判定 |
| `study_statistics` | builtin（独立した実行） | 複数会話の計画に基づく検定 |
| `acoustic_features` | builtin（任意の依存） | F0、強度、ポーズ |
| 外部R（jmv、STM） | external | 入力hashに結び付かない結果は`unverified` |
