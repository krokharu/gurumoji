---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-09
title: 分析マイルストーン・可視化プログラム・UI統合設計：11. 参照した公式仕様
summary: 11. 参照した公式仕様。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 265
- 331
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：11. 参照した公式仕様

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。

## 11. 参照した公式仕様

- [Apache Parquet](https://parquet.apache.org/docs/overview/)：列指向の保存形式。大きな表への採用判断は実測する。
- [Apache Arrow](https://arrow.apache.org/docs/format/Intro.html)：メモリー内の列指向データ交換。
- [SQLite WAL](https://www.sqlite.org/wal.html)：読み取りと書き込みの並行、単一writerの制約。
- [JSON Schema](https://json-schema.org/understanding-json-schema/reference/type)：型・必須項目・値域の検証。
- [pyreadstat](https://github.com/Roche/pyreadstat/blob/master/README.md)：SAVと変数・値ラベル・欠測の読み書き。
- [jamovi FAQ](https://www.jamovi.org/faq.html)、[変数仕様](https://docs.jamovi.org/usermanual/um_4_spreadsheet.html)：SAV/CSV読込と尺度設定。
- [Matplotlib savefig](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html)：静的図の保存、サイズ・dpi・背景の指定。
- [Mermaid sequence](https://mermaid.js.org/syntax/sequenceDiagram)：par/altを使った分析シーケンスの原本。

外部仕様からの採用案と、Gurumojiで実装済みの機能を区別する。対応モデル、変換ライブラリーの版、ソフトウェア実機互換性は実装時に固定・検証する。

## 12. 成果物とプログラム・表示の対応一覧

詳細条件は構造JSON、試作の「47成果物の対応表」から検索できる。下表の担当名は責務名であり、同名の実装ファイルが存在することを意味しない。

| ID | 成果物 | 初回段階 | 作成プログラムの責務 | 表示部品 | 画面 |
| --- | --- | --- | --- | --- | --- |
| V01 | 分析サマリー | M2 | 基礎集計Adapter | MetricCards | S01 |
| V02 | 予定質問と実際の論点 | M1 | OutlineRunner | DataTable | S01 |
| V03 | インタビュー評価8軸 | M3 | InterviewEvaluationRunner | BarChart | S01 |
| V04 | 論点別の評価 | M3 | InterviewEvaluationRunner | Heatmap | S01 |
| V05 | 評価の根拠一覧 | M3 | EvidenceResolver | QuotePanel | S01 |
| V06 | 階層アウトライン | M1 | OutlineRunner | OutlineTree | S01 |
| V07 | 論点別の議論量 | M2 | 参加集計Adapter | BarChart | S01 |
| V08 | 論点別の立場分布 | M2 | StanceRunner＋集計 | BarChart | S01 |
| V09 | 共通意見・対立点・代替案 | M2 | 論点集約Adapter | DataTable | S01 |
| V10 | 主張と理由・条件 | M2 | 論点集約Adapter | RelationGraph | S01 |
| V11 | 未解決点・未回答質問 | M3 | InteractionRunner | DataTable | S01 |
| V12 | 論点別キーワード | M2 | 語彙Adapter | Heatmap | S01 |
| V13 | 話者プロフィール | M2 | 話者集計Adapter | MetricCards | S01 |
| V14 | 話者×論点の立場 | M2 | StanceRunner | Heatmap | S01 |
| V15 | 話者×論点の参加 | M2 | 参加集計Adapter | Heatmap | S01 |
| V16 | 話者別キーワード | M2 | 語彙Adapter | BarChart | S01 |
| V17 | 話者別の関心候補 | M2 | 関心分析Runner | Heatmap | S01 |
| V18 | 立場の変化 | M3 | StanceRunner＋時系列集計 | Timeline | S01 |
| V19 | 話者間の共通点・相違点 | M2 | 論点集約Adapter | DataTable | S01 |
| V20 | 会話タイムライン | M3 | 時間集計Adapter | Timeline | S01 |
| V21 | 話題の遷移 | M3 | 時間集計Adapter | RelationGraph | S01 |
| V22 | 質問→回答→深掘り | M3 | InteractionRunner | RelationGraph | S01 |
| V23 | 同意・反論・補足の関係 | M3 | InteractionRunner | RelationGraph | S01 |
| V24 | 話者交代 | M3 | 時間集計Adapter | Heatmap | S01 |
| V25 | 参加バランスの推移 | M3 | 参加集計Adapter | Timeline | S01 |
| V26 | 相づち・応答状況 | M3 | Transformer相づちAdapter | BarChart | S01 |
| V27 | 無音・重なり候補 | M3 | 時間集計Adapter | Timeline | S01 |
| V28 | 変数・尺度一覧 | M4 | DefinitionService | DataTable | S01 |
| V29 | ラベルの付与状況 | M5 | MeasurementRunner＋集計 | BarChart | S01 |
| V30 | 評定値の分布 | M5 | StatisticsRunner | DistributionPlot | S01 |
| V31 | 欠測・未判定の状況 | M5 | DatasetBuilder | Heatmap | S01 |
| V32 | 判定元の比較 | M5 | 判定比較Adapter | DataTable | S05 |
| V33 | 定義変更前後の比較 | M6 | 比較Adapter | DataTable | S05 |
| V34 | 記述統計 | M5 | StatisticsRunner | DataTable | S01 |
| V35 | 群別の分布 | M5 | StatisticsRunner | DistributionPlot | S01 |
| V36 | クロス集計 | M5 | StatisticsRunner | Heatmap | S01 |
| V37 | 相関 | M5 | StatisticsRunner | Heatmap | S01 |
| V38 | 群間比較 | M5 | StatisticsRunner | EffectPlot | S05 |
| V39 | 対応のある比較 | M5 | StatisticsRunner | DistributionPlot | S05 |
| V40 | 語の共起 | M5 | 語彙Adapter | RelationGraph | S01 |
| V41 | テーマとコードの構造 | M5 | QualitativeRunner | OutlineTree | S05 |
| V42 | ケース×テーマ | M5 | QualitativeRunner | Heatmap | S05 |
| V43 | 重要引用・反例・少数意見 | M5 | QualitativeRunner | QuotePanel | S05 |
| V44 | 量的結果と質的解釈 | M6 | 統合分析Runner | DataTable | S05 |
| V45 | 複数インタビュー比較 | M6 | 既存interview_comparison拡張 | Heatmap | S05 |
| V46 | 分析結果の統合 | M6 | 統合分析Runner | RelationGraph | S05 |
| V47 | 追加調査の候補 | M6 | 統合分析Runner | DataTable | S05 |
