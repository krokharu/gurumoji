---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-05
title: 分析マイルストーン・可視化プログラム・UI統合設計：6. 可視化プログラムと表示の共通契約
summary: 6. 可視化プログラムと表示の共通契約。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 148
- 167
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：6. 可視化プログラムと表示の共通契約

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。

## 6. 可視化プログラムと表示の共通契約

### 6.1 ResultBundle → ChartSpec → 表示・出力

各MethodRunnerはResultBundle（dataset/artifact参照、対象数、欠測、前提、根拠）を返す。VisualizationServiceは成果物カタログの定義からChartSpecを作り、同じChartSpecをブラウザー表示と画像出力へ渡す。

ChartSpecは `chart_id, visual_id, dataset_ref, source_hash, grain, filters, encodings, category_order, palette, value_format, denominator, missing_policy, evidence_ref, layout_ref, title, captions, size, font` を必須または条件付き必須とする。特にネットワークはノード座標とlayoutのseedを固定し、画像と画面の関係配置を一致させる。

表示部品は `MetricCards / DataTable / BarChart / Heatmap / Timeline / RelationGraph / DistributionPlot / EffectPlot / QuotePanel / OutlineTree` に集約。現行のSVG・HTML表・発話への移動を再利用する。全図に代替表、単位、N、欠測、選択条件、根拠操作を付ける。数値表示と原表は同じ丸め規則を共有する。

現行の分析画面では `automatic.time_bins` と `session_outline.result.rows` を組み合わせ、経過時間×会話活発度のSVGにアウトライン・Transformer話題の時間帯を重ねる。会話活発度は各時間帯の発話時間割合65%と発話開始回数35%を合成した0〜100の表示用指標で、声量・感情・話題の重要性は測らない。分析APIの `session_outline` は保存済みアウトラインとテーマから作る表示用の結合結果であり、古いTransformer話題は画面で隠す。これは上記のChartSpec/画像出力とは別の現行UI機能である。

画像は統計値から決定的に描画する。UIコンセプトの画像生成を、研究用グラフの数値描画には使わない。静的出力はMatplotlib Figure/Aggを候補として手法別rendererを持つ。PNG/SVG/PDFに加え、JPEG/TIFFは対応バックエンドを検証して提供する。ブラウザーSVGと静的rendererが共有するのはChartSpec/数値/配置であり、ピクセル単位の完全一致は保証しない。

### 6.2 成果物カタログ

47成果物の **ID → 処理担当 → 入力 → 表示部品 → 画面 → 到達段階 → 条件** は [design-spec.json](../../../analysis-design/design-spec.json) と [UIプレビューの成果物一覧](../../../analysis-design/ui-blueprint.html#catalog) に記載する。最小表示段階と最終書き出し段階M7を区別する。IDは後続実装・テスト・出力ファイルで共通利用する。

全候補を無条件に実行しない。手動で選んだ手法、入力の有無、対象数、尺度、ライセンスと実行環境の適合性を計画時に検査する。結果としての空集合と、未実装・失敗を別状態で表示する。
