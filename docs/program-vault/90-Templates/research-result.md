---
note_id: template-research-result
note_type: template
title: 分析結果ノートのテンプレート
status: proposed
updated: 2026-09-13
tags:
  - gurumoji/template
---

# 分析結果ノートのテンプレート

以下は生成する研究用ノートのひな型であり、実際の分析結果ではない。`{{...}}` は登録時に検証済みの値で置き換える。複雑なパラメーターと全結果は参照先JSON／CSVに保存する。

````markdown
---
note_id: "analysis-{{analysis_id}}"
note_type: analysis-result
title: "{{表示名}}"
schema_version: 1
managed_by: gurumoji
library_id: "{{library_id}}"
conversation_id: "{{conversation_id}}"
analysis_id: "{{analysis_id}}"
input_snapshot_id: "{{input_snapshot_id}}"
method_id: "{{method_id}}"
method_version: "{{method_version}}"
execution_kind: "{{builtin_external_manual}}"
run_status: completed
review_status: unreviewed
needs_update: false
created: "{{ISO日時}}"
updated: "{{ISO日時}}"
conversation: "[[20-Conversations/conversation-{{conversation_id}}]]"
method: "[[45-Methods/method-{{method_id}}-v{{method_version}}]]"
tags:
  - gurumoji/analysis
---

# {{表示名}}

## 見解・観察

{{確認できる内容。AI生成なら「AI見解・下書き」と表示する}}

## 条件と対象

- 研究質問：{{研究質問または会話目的}}
- 対象：{{入力版・対象話者・対象発話数}}
- 除外：{{除外規則・除外件数}}
- 計算法・環境：{{式・エンジン・モデル・版}}
- 条件ファイル：{{parameters_artifact_idと取得リンク}}

## 主な結果

{{定義、単位、分母を含めた主要な表または図}}

## 根拠

### 支持する発話

- [[25-Sources/{{input_snapshot_id}}/part-0001#^{{block_id}}|{{話者・時刻}}]]

### 反例・追加確認

{{反証・文脈・要確認事項。該当がなければ無理に作らない}}

## 限界・代替説明

{{未実施・利用不可・解析器の代替動作・解釈上の限界}}

## 全件データ

{{artifact_id、形式、行数、hash、取得リンク}}

## 関連する研究メモ

{{この結果について人が書いた別ノートへのリンク}}
````

統計集計では、発話リンクの代わりに対象集合と表の行キーを根拠として記載できる。詳細は [[40-Design/method-rules]]。`needs_update` 等の現況属性は管理項目として更新できるが、見解本文・数値・根拠・入力版は書き換えない。
