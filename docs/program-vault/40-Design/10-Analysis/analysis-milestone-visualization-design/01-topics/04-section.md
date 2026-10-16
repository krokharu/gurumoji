---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-04
title: 分析マイルストーン・可視化プログラム・UI統合設計：5. 分析データの契約
summary: 5. 分析データの契約。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 117
- 147
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：5. 分析データの契約

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。

## 5. 分析データの契約

### 5.1 形式と正本

既存の原文・編集・実行台帳の正本はSQLite/既存snapshot契約を維持。新しい大きな分析表はParquetを候補とし、まず同値性・性能を評価する。定義、主張の構造、ChartSpec、manifestはJSON。CSV/Excel/SAVは交換用の派生物である。Arrowはメモリー内交換の候補、DuckDBは表の検索・結合が必要になった場合の候補とし、両方の導入を前提にしない。

旧result.jsonが正本のrunはそのまま読む。新runではmanifestが各datasetの正本artifactを1つ指定する。JSONとParquetを独立編集する二重正本を作らない。保存先は既存の設定解決済みdata/AnalysisStore配下。Vaultに大量の表を埋め込まない。

| 論理データ | 粒度とキー | 必須の意味 |
| --- | --- | --- |
| segments | snapshot_id × segment_id | 本文版、話者、時刻、順序、除外。引用範囲は原文offsetの規約を固定 |
| outlines | outline_version × outline_id | 親論点、名称、予定質問対応 |
| outline_segments | outline_id × segment_id × snapshot_id | 多対多対応、未分類、対応方法。重複を人数として数えない |
| claims | claim_id | 対象論点、主張、理由、条件、生成元、確認状態 |
| stances | stance_id | 話者、claim/target_id、論点、時間範囲、立場、条件付き/混合、出所 |
| measurements | measurement_id | 対象の型とID、variable_id、定義版、型付き値、欠測理由、run_id |
| evidence | result_id × evidence_id | snapshot、発話、引用範囲、supports/contradicts/context |
| interactions | relation_id | source＝応答側、target＝参照先、関係、方向、推定/確認、根拠 |
| datasets | dataset_id × row_id | 1行の観測単位、主キー、採用列、親artifact、集約・除外・重複規則 |
| charts | chart_id × chart_version | dataset、列、単位、順序、色、条件、根拠、layout、出力寸法 |

話者IDは会話内、参加者IDは会話をまたぐ識別とする。表示名でJOINしない。measurementは縦持ちで保存し、統計入力は粒度・集約を指定して横持ちにする。1セルに複数の観測値が生じる場合、集約規則なしのpivotを拒否する。

立場は賛成/反対/中立/第三案。表明なし、対象不明、根拠不足を別状態とする。中立と沈黙を混同しない。第三案は案IDで分ける。名義コード1〜4に数値上の大小を与えない。関心は本人の明示/自発言及/質問への回答を区別する。

### 5.2 定義と尺度

VariableDefinitionにはID、名称、description、unit_of_analysis、source_columns、出力列、data_type、measurement_level、levelsと順序、値域、採用/除外例、測定規則、欠測規則、分母、集約、provenance、定義版、試行結果、採用状態を持つ。任意のPython/JavaScriptを入力・実行する欄は設けない。

名義・順序・間隔・比率と物理型を分ける。nullに欠測理由を併記。JEVの選択値・確率分布・confidence・人手確認は別列。ordinalの0〜4を自動的に連続変数へ変換しない。尺度の適合性はJSON Schemaだけでは保証できないため意味検証も行う。
