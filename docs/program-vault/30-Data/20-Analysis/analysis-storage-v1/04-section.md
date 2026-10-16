---
note_type: reference-section
status: current
feature: analysis-storage
verified: 2026-10-05
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/program
- gurumoji/analysis
- gurumoji/obsidian
note_id: program-analysis-storage-v1-section-04
title: AI仕上げ・文章分析の保存契約 v1：発話時間の欠測契約（2026-10-04）
summary: 発話時間の欠測契約（2026-10-04）。出典ノート「AI仕上げ・文章分析の保存契約 v1」の分割本文。
parent_note_id: program-analysis-storage-v1
source_path: 30-Data/analysis-storage-v1.md
source_sha256: 31b48be809af0922124aea608b12aec7e8f935b513ca61743fecd5d9e06bc885
source_body_lines:
- 137
- 154
split_on: '2026-10-11'
---

# AI仕上げ・文章分析の保存契約 v1：発話時間の欠測契約（2026-10-04）

親索引・状態・確認版：[[30-Data/20-Analysis/analysis-storage-v1/00-Index]]。必要な本文だけを取得する。

## 発話時間の欠測契約（2026-10-04）

`focus-group-local-5`／手法registry `text-analysis-store-9` から、観測済み発話がすべて時刻欠測なら話者・属性群・司会・全体の時間を `null` とする。有効な時刻のある真の0秒は0、空集合の合計も0を維持する。一部欠測時の `speaking_seconds`／`total_speaking_seconds` は時刻あり発話の小計で、`timed_turn_count` と `missing_time_turn_count` を併記する。既存話者CSVのcoverage列を維持し、属性群CSVには同2列を追加する。

全体割合は含めた全発話、参加者割合・Gini・HHI・均等度はその対象話者集合に時刻欠測がある、または総時間0の場合に `null`。除外発話は対象集合へ戻さず、UNKNOWN・未観測話者・欠測のみの話者を0秒の分母として補完しない。従来の有効時刻話者の分母人数は保ち、その対象候補に欠測があることを別coverageで示す。割合を算出できない場合の集中・低比率候補は出力しない。数値文字列の既存Python float互換は維持し、巨大整数の変換overflowは欠測扱いとする。

固定CSVの欠測は空欄、型付きJSONは `null` を保持する。pipelineは受付済みsnapshotの計算版から `result.algorithms.automatic` と手法engine版を記録する。旧snapshot・旧固定packageの値を新仕様へ再計算・書換えせず、旧計算版を保持する。新版の表にはcoverageの要約を添える。実データ移行・DB schema変更はない。


## 発話別役割が混在する話者（2026-10-04）

`focus-group-local-6`／registry `text-analysis-store-10` では、含めた発話の同一話者に複数役割がある場合、派生話者行を `role=mixed`、`role_status=mixed` とし、`observed_roles` に元の役割集合を順序固定で保存する。これは表示・集計の状態であり、人が選ぶ役割や原発話・会話プロファイル・準備記録を書き換えない。原因発話を分析から除外すれば残る単一役割へ戻る。

話者総時間・全体時間・全体割合は時間coverageが有効なら保持する。司会等を除く参加者集合は役割配分が不確定なので割合・最大割合・Gini・HHI・均等度を算出せず、`unavailable_reason=mixed_roles` を返す。実参加人数は研究者の登録値を維持し、観測参加発言者人数は混在時 `null` として推測しない。司会時間・司会割合・司会質問候補と `group_by=role` の時間・割合は `null`、`role_aggregation_status=mixed` を添え、時刻欠測とは区別する。

`exclude_moderator=false` の全観測話者集合は役割に依存しないため、時間coverageが完全なら従来名 `participant_percent` を含む割合・均等度を保持し、分母を全観測話者と明示する。UNKNOWNや未観測者を新規分母へ加えない。旧v4/v5のsnapshotや固定packageは保存時の値・元計算版で保持し、v6へ再計算・再ラベルしない。
