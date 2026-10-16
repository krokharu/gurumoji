---
note_type: reference-section
status: complete
verified: 2026-09-20
updated: 2026-10-05
feature: architecture
tags:
- gurumoji/program
- gurumoji/architecture
- gurumoji/plan
note_id: design-core-handler-routing-reorganization-section-16
title: コア・ハンドラー・ルーティング再編案：現行ER図（SQLite）
summary: 現行ER図（SQLite）。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 918
- 1033
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：現行ER図（SQLite）

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

## 現行ER図（SQLite）

`library_items`が会話の最新状態をJSON列でまとめて持ち、固定分析は`analysis_runs`を中心に別管理する。図のうち`transcript_versions`、`transcript_preparations`、`transcript_preparation_events`はSQLite外部キーを宣言している。その他の線は、現行コードがIDで維持する論理関係である。図では`TRANSCRIPT_PREPARATION_EVENT`、`OBSIDIAN_NOTES`がそれぞれ実テーブル`transcript_preparation_events`、`obsidian_notes`に対応する。

```mermaid
erDiagram
  LIBRARY_ITEM {
    text id PK
    text segments_json
    text speaker_names_json
    text speaker_profiles_json
    text session_profile_json
    int revision_count
    int analysis_revision
    text analysis_config_json
    text analysis_annotations_json
    text segment_classification_json
  }
  TRANSCRIPT_VERSION {
    text item_id PK, FK
    int version PK
    text source_hash
    text source_json
    text origin
  }
  TRANSCRIPT_PREPARATION {
    text item_id PK, FK
    int revision
    text state_json
  }
  TRANSCRIPT_PREPARATION_EVENT {
    text item_id PK, FK
    int revision PK
    text state_json
  }
  ANALYSIS_RUN {
    text id PK
    text request_id UK
    text item_id
    text kind
    text snapshot_id
    int source_revision
    int analysis_revision
    text status
    int stale
    text vault_status
  }
  ANALYSIS_RUN_MEMBER {
    text run_id PK
    text item_id PK
  }
  ANALYSIS_ARTIFACT {
    text id PK
    text run_id
    text path
    text sha256
    int bytes
    int rows
  }
  ANALYSIS_PENDING_PACKAGE {
    text run_id PK
    text payload_json
  }
  INSIGHT_REQUEST {
    text request_id PK
    text item_id
    int source_revision
    int analysis_revision
    text status
  }
  TRANSFORMER_REQUEST {
    text request_id PK
    text item_id
    int source_revision
    int analysis_revision
    text status
  }
  OBSIDIAN_NOTES {
    text path PK
    text note_id UK
    text item_id
    text sha256
  }
  OUTPUT_IMPORT_PROVENANCE {
    text item_id PK
    text canonical_path PK
    text content_sha256
  }
  SPEAKER_REGISTRY {
    text id PK
    text participant_code
    text consent_status
    text attributes_json
  }

  LIBRARY_ITEM ||--o{ TRANSCRIPT_VERSION : versions
  LIBRARY_ITEM ||--o| TRANSCRIPT_PREPARATION : current_preparation
  LIBRARY_ITEM ||--o{ TRANSCRIPT_PREPARATION_EVENT : preparation_history
  LIBRARY_ITEM ||--o{ INSIGHT_REQUEST : insight_jobs
  LIBRARY_ITEM ||--o{ TRANSFORMER_REQUEST : transformer_jobs
  LIBRARY_ITEM ||--o{ ANALYSIS_RUN : primary_target
  LIBRARY_ITEM ||--o{ ANALYSIS_RUN_MEMBER : comparison_member
  ANALYSIS_RUN ||--o{ ANALYSIS_RUN_MEMBER : members
  ANALYSIS_RUN ||--o{ ANALYSIS_ARTIFACT : artifacts
  ANALYSIS_RUN ||--o| ANALYSIS_PENDING_PACKAGE : interrupted_write
  LIBRARY_ITEM ||--o{ OBSIDIAN_NOTES : generated_notes
  LIBRARY_ITEM ||--o{ OUTPUT_IMPORT_PROVENANCE : imported_from
  SPEAKER_REGISTRY }o--o{ LIBRARY_ITEM : mapped_in_JSON
```

次の補助テーブルは図を読みやすくするため省略した。

- `application_metadata`：話者台帳revision、移行済みフラグなどのkey-value
- `training_events`：編集から作った学習イベント。関連IDを独立列ではなくpayloadに持つ
- `output_import_tombstones`：削除済み取り込み元の再取り込み防止
