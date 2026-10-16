---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/analysis
- gurumoji/statistics
- gurumoji/design
note_id: design-quantification-statistics-plan-section-06
title: 発話の数値化とjamovi型統計の自動実行計画：7. 妥当性ゲート
summary: 7. 妥当性ゲート。出典ノート「発話の数値化とjamovi型統計の自動実行計画」の分割本文。
parent_note_id: design-quantification-statistics-plan
source_path: 40-Design/quantification-statistics-plan.md
source_sha256: 72fc8e49117b2416635ff3d9d9b2a07ed9a4e1287e75c4b43f96d73411bf9b04
source_body_lines:
- 133
- 161
split_on: '2026-10-11'
---

# 発話の数値化とjamovi型統計の自動実行計画：7. 妥当性ゲート

親索引・状態・確認版：[[40-Design/10-Analysis/quantification-statistics-plan/00-Index]]。必要な本文だけを取得する。

## 7. 妥当性ゲート

AIの変数を検定に使う前の条件。ルール辞書の変数は規則そのものを定義として報告し（例：「『かもしれない』を含む発話の割合」）、構成概念の代わり（例：不確実性）として解釈する場合だけ同じゲートを使う。

1. **検証サンプル：** 会話・話者・AI判定の有無で層別して無作為に抽出し、抽出確率を保存する（Phase 5の補正に使う）。研究者はAIのラベルを見ない状態で、キーボードで操作できる画面からコードする。件数の既定値はPhase 0で、αの信頼区間の幅から決める。
2. **指標：** 名義はKrippendorffのα、Cohenのκ、適合率・再現率・F1、混同行列。順序評定は順序尺度のαまたはICC。LLMの実行間の一致もαで出す。αは点推定とブートストラップ95%信頼区間を出し（Hayes & Krippendorff 2007）、下限がしきい値を下回る場合は検証件数の追加を促す。
3. **判定の既定案：** Krippendorff（2004）の推奨に合わせ、α≧.800を`validated`、.667≦α<.800を`tentative`（探索的な分析だけ）、α<.667を`failed`（検定に使わない）とする。研究者が変える場合は理由を記録する。
4. **群ごとの誤り：** 群ごとに適合率・再現率を出す。群によって誤りの傾向が違う場合、その群比較は`tentative`以下に下げる。群と相関する誤分類は、実際にはない差を作り得る（TeBlunthuis et al. 2024）。
5. **コードブックの見直し：** 不一致の発話を研究者が読み、定義を直した場合は、コードブックの版を上げて検証をやり直す。
6. **報告：** 検定結果の行に、変数の出所、ゲートの判定、検証の件数を付ける。
7. **発展（Phase 5）：** 検証サンプルを使うDesign-based Supervised Learning（Egami et al. 2023）やPrediction-powered Inference（Angelopoulos et al. 2023）で、AIラベルに基づく割合や差の信頼区間を補正する。

## 8. 分析単位とデータセット

| データセット（案） | 1行の単位 | 主な列 | 主な用途 |
| --- | --- | --- | --- |
| `stat_utterances` | 発話 | 発話ID、会話ID、話者、参加者コード、役割、時刻、数値変数、コード（人手・ルール・AIを別の列に分ける）、テーマ、感情ラベル | 記述統計、GEE・混合モデル、探索的なクロス集計 |
| `stat_speakers` | 会話×話者 | 発話数、発話時間の割合、コードごとの発話率とその分母、評定の平均、事前アンケート項目 | 群比較の既定（t検定など） |
| `stat_participants` | 参加者（会話をまたぐ） | 条件ごとの値（例：事前／事後のセッション） | 対応のある検定 |
| `stat_interviews` | インタビュー | 会話属性、集計値 | 会話間の比較。件数が少なければ記述だけ |
| `variable_catalog` | 変数 | ASCIIの列名、日本語の表示名、尺度（名義・順序・連続・ID）、出所、手法IDと版、単位、集約の規則、欠測の規則、妥当性の状態 | jamoviでの型設定、報告 |
| `validation_samples` | 検証対象の発話×コード | 層、抽出確率、人手のラベル、AIのラベル、コーダー、日時、コードブック版 | 一致度、ゲートの判定、Phase 5の補正 |

- 率には分母の列を必ず添える。発話が少ない話者の率は不安定なので、最小発話数を計画で決める。
- 「未判定」「対象外」「同意による除外」を0にしない。欠測として数え、理由を残す。
- 会話をまたいで参加者を同一とみなすのは、話者台帳の参加者コードで結び付いている場合だけにする。

アプリ内のデータセットの正本は型・尺度・行キー・欠測理由を持つJSON等とし、CSVはそこから生成する交換・表計算用出力とする。既存のJev／Transformer列は固定`result.json`の型付き値から取り込む。現行CSVは`null`と空文字、数式対策の`'`と元の文字列を一意に復元できないため、CSVしかない列の意味を推測で埋めない。必要な値を復元できない場合は理由付きで利用不可にする。詳細は[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]の図4に従い、既存CSVの数式対策とhashを維持する。
