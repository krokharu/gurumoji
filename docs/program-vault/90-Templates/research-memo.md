---
note_id: template-research-memo
note_type: template
title: 研究メモ・解釈・コード案のテンプレート
status: proposed
updated: 2026-09-13
tags:
  - gurumoji/template
---

# 研究メモ・解釈・コード案のテンプレート

人が編集するノートは研究用Vaultの `60-ResearchNotes` に保存する。自由な考察とアプリへの取り込み案を区別する。以下の値は登録時に設定する例であり、そのまま取り込める実データではない。

````markdown
---
note_id: "memo-{{uuid}}"
note_type: research-memo
title: "{{メモの題名}}"
schema_version: 1
managed_by: researcher
library_id: "{{library_id}}"
conversation_id: "{{conversation_id}}"
input_snapshot_id: "{{参照した入力版}}"
author: "{{記入者の識別名}}"
review_status: draft
import_kind: none
created: "{{ISO日時}}"
updated: "{{ISO日時}}"
tags:
  - gurumoji/research-note
---

# {{メモの題名}}

## 問い・仮説

{{何を理解したいか}}

## 考察

{{自由記述。原文の事実と自分の解釈を区別する}}

## 支持する根拠

- [[25-Sources/{{snapshot_id}}/part-0001#^{{block_id}}|{{話者・時刻}}]]

## 反証・文脈・追加確認

{{別の読み方や不足している情報}}

## 関連する分析・概念

{{分析実行・コード・概念へのリンク}}

## アプリへの取り込み案

{{取り込みたい場合だけ、提案内容を記入する。自由記述は自動適用されない}}
````

`import_kind` は `none`／`analyst_memo`／`interpretation`／`code_proposal` を提案する。取り込みschemaの実装後、`code_proposal` は `code_id`（既存コードへの提案時）、`proposed_label`、定義、包含／除外例、適用を提案する発話IDを明示する欄を追加する。

取り込みプレビューは、新規コード案、既存コードの定義変更案、コード付与案を区別する。採用しても元ノートは保持し、同じ内容の二重適用は防ぐ。根拠IDはアプリが入力版と照合する。手順は [[40-Design/sync-contract]]。
