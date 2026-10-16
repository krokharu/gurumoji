---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-07
title: 分析マイルストーン・可視化プログラム・UI統合設計：8. 出力設計
summary: 8. 出力設計。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 201
- 235
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：8. 出力設計

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。

## 8. 出力設計

| 形式 | プログラム候補 | 内容・検証 |
| --- | --- | --- |
| SPSS .sav | pyreadstat.write_sav（導入前に依存・ライセンス確認） | ASCII列名、日本語ラベル、値ラベル、尺度、欠測。再読み込みで型・値・ラベルを照合 |
| SPSS .sps | 対応手法の構文テンプレート | 再現対象の手法とパラメーターのみ出力。未対応手法を再現可能と表示しない |
| jamovi | 同じ.savと.csv、変数辞書、手順、対応するR/jmv構文 | nominal/ordinal/continuous/IDを対応付ける。CSVの推定だけに依存しない。初期は.omvを自作せずjamovi側で保存 |
| Excel .xlsx | 既存openpyxl出力を拡張 | 分析単位別データ、集計、統計、変数定義、根拠一覧、分析条件。各データシートは1行1観測 |
| CSV/JSON/Parquet | 共通dataset serializer | 同じ固定datasetから生成。CSVから正本へ逆変換しない |
| PNG/JPEG/SVG/PDF/TIFF | 共通ChartSpec＋renderer | 寸法、フォント、背景、解像度。JPEGは白背景、SVG/PDFはベクトル。対応形式を実環境で検証 |
| ZIP | 標準アーカイブ | 選択成果物、data dictionary、manifest、図に使った表、再現条件を格納 |

画像は幅/高さpxか印刷寸法mm＋dpiを選び、一方から他方を計算する。dpiメタデータだけ変更して画素数が増えたように見せない。PNG透過は任意、JPEG選択時は透過を無効化して理由を表示する。日本語フォントの存在を確認し、利用フォントを記録。凡例・数値・注記の切れを検査する。

観測単位（発話、話者、論点、話者×論点、会話）ごとに別datasetを出力。複数選択時はファイルを分ける。長い原文、ID、日付、欠測の意味が形式制限で失われる場合は変換規則と補助ファイルを明示。元値を黙って切り詰めない。

SPSS/jamoviで開けるデータの提供と、各ソフトの分析結果ウィンドウを丸ごと再現することは別。対応する検定のみ構文/手順で再現し、アプリ内の質的見解はExcel/JSON/引用表として提供する。

## 9. API案と既存境界

初回導入範囲では計画、定義、試行、pipeline状態・取消・再試行とZIP取得を実装済み。図の単独取得と任意形式のexport要求は後続候補である。既存 `web/analysis_routes.py` → `handlers/analysis_commands.py` / `analysis_queries.py` の境界を使い、参照・ダウンロードは既存artifact APIを再利用する。

| 操作 | 候補API | 要点 |
| --- | --- | --- |
| 定義検証・計画プレビュー | POST /api/library/{id}/analysis/plans/preview | 副作用なし。入力版、定義、列、手法→steps、ゲート、エラー、利用不可理由 |
| 定義下書き保存 | PUT /api/library/{id}/analysis/definitions/{definition_id} | revisionを検証、既存コードを上書きしない |
| 定義の少数試行 | POST /api/library/{id}/analysis/definitions/{definition_id}/trials | 明示実行。対象ID、provider、上限を固定、全件実行と別request |
| 計画確定・開始 | POST /api/library/{id}/analysis/pipelines | plan_hash、source_revision、request_idを検証。応答はpipeline_idと状態。保存runのIDと区別 |
| 状態取得 | GET /api/library/{id}/analysis/pipelines/{pipeline_id} | milestones、steps、events、usage、失敗理由。表示範囲と実行対象を混同しない |
| 中止・再試行 | POST .../{pipeline_id}/cancel または /retry | 冪等。retryは対象step、親hash、attemptを照合 |
| 図の仕様取得 | GET /api/library/{id}/analysis/charts/{chart_id} | 確定結果とChartSpecの参照。読み取りでAIを起動しない |
| 出力要求 | POST /api/library/{id}/analysis/exports | 固定dataset/ChartSpec、形式、寸法を指定。M7 taskまたは完了runへの独立export attempt |

エラー区分は入力不正、版競合、利用不可、適用条件不足、provider失敗、保存失敗を分ける。APIが選択手法を黙って置換しない。画面更新は初期はpollingを再利用し、イベント配信方式の変更を必須にしない。
