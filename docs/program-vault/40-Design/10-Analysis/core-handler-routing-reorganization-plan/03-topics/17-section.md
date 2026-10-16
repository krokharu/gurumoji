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
note_id: design-core-handler-routing-reorganization-section-17
title: コア・ハンドラー・ルーティング再編案：現行ER図（成果物・Obsidianを含む概念関係）
summary: 現行ER図（成果物・Obsidianを含む概念関係）。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 1034
- 1117
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：現行ER図（成果物・Obsidianを含む概念関係）

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

## 現行ER図（成果物・Obsidianを含む概念関係）

```mermaid
erDiagram
  CONVERSATION {
    text conversation_id PK
    int revision
    text source_hash
  }
  INPUT_SNAPSHOT {
    text snapshot_id PK
    text input_json
    text source_hash
  }
  ANALYSIS_RUN {
    text run_id PK
    text method_id
    text status
    text fingerprint
  }
  ARTIFACT {
    text artifact_id PK
    text relative_path
    text sha256
  }
  MANAGED_NOTE {
    text note_id PK
    text vault_kind
    text path
    text written_hash
    text status
  }
  INPUT_LEDGER_NOTE {
    text conversation_id
    int revision
  }
  ORCHESTRATOR_RUN_NOTE {
    text run_id
    text snapshot_id
    text method_id
  }
  VISUAL_SPEC_NOTE {
    text run_id
    text method_id
    text artifact_ids
  }
  RESEARCH_NOTE {
    text note_id
    text run_id
    text evidence_ids
  }
  WORKBENCH_STATE {
    text conversation_id
    text source_fingerprint
    text result_id
  }
  VAULT_CATALOG {
    text schema_version
    text roots
    text managed_hashes
  }

  CONVERSATION ||--o{ INPUT_SNAPSHOT : captured_as
  INPUT_SNAPSHOT ||--o{ ANALYSIS_RUN : analyzed_by
  ANALYSIS_RUN ||--o{ ARTIFACT : produces
  CONVERSATION ||--o| INPUT_LEDGER_NOTE : summarized_in
  ANALYSIS_RUN ||--o{ ORCHESTRATOR_RUN_NOTE : recorded_in
  ANALYSIS_RUN ||--o{ VISUAL_SPEC_NOTE : visualized_by
  ANALYSIS_RUN ||--o{ RESEARCH_NOTE : interpreted_in
  CONVERSATION ||--o| WORKBENCH_STATE : finishing_state
  WORKBENCH_STATE ||--o{ RESEARCH_NOTE : writes_versions
  VAULT_CATALOG ||--o{ MANAGED_NOTE : tracks
  MANAGED_NOTE ||--o| INPUT_LEDGER_NOTE : specializes
  MANAGED_NOTE ||--o| ORCHESTRATOR_RUN_NOTE : specializes
  MANAGED_NOTE ||--o| VISUAL_SPEC_NOTE : specializes
```

重要な境界は次のとおり。

- Vault間の関係はWikilinkではなく`conversation_id`、`snapshot_id`、`run_id`、`artifact_id`、`note_id`で解決する。
- Input／Visualization／Orchestratorの管理ノートは`vaults.json`のhashと`VaultRegistry`の競合処理を通す。
- ResearchVaultは`AnalysisStore`、`ObsidianLayout`、`ObsidianWorkbench`の既存経路を維持する。
- Software VaultはGit管理であり、実行中のアプリは書き込まない。
