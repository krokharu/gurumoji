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
note_id: design-core-handler-routing-reorganization-section-15
title: コア・ハンドラー・ルーティング再編案：現行システム構成図
summary: 現行システム構成図。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 837
- 917
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：現行システム構成図

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

## 現行システム構成図

```mermaid
flowchart LR
  Researcher[研究者] --> Browser[ブラウザー]
  Researcher <--> Obsidian[Obsidian]

  subgraph Web[Web UI]
    HTML[index.html]
    JS[app.js と分析用JS]
  end

  subgraph Monolith[Flaskプロセス]
    Router[app.py: 69 HTTP routes]
    Service[app.py: handler・service・core処理]
    Runtime[メモリー内状態<br/>jobs・cancel events・cache・locks]
    Watcher[Obsidian watcher thread]
    Analysis[分析モジュール群]
    Store[AnalysisStore]
    Layout[ObsidianLayout／Workbench／Migration]
    Registry[VaultRegistry]
  end

  subgraph Engines[処理エンジン]
    Media[FFmpeg／WhisperX／pyannote]
    LocalModels[感情・Transformerモデル]
    AIWorker[ai_http_worker subprocess]
    RemoteAI[OpenAI／Gemini／LM Studio]
  end

  subgraph Persistence[永続・一時保存]
    DB[(library.sqlite3)]
    Files[media・output・uploads・training]
    Artifacts[analysis_store<br/>immutable JSON／CSV]
    WorkState[obsidian_workbench<br/>state・source・result JSON]
  end

  subgraph Vaults[Obsidian Vaults]
    Research[ResearchVault]
    Input[InputVault]
    Visual[VisualizationVault]
    Orch[OrchestratorVault]
    Software[Software Vault<br/>docs/program-vault]
  end

  Browser --> HTML --> JS -->|HTTP| Router
  Router --> Service
  Service <--> Runtime
  Service --> Analysis
  Service --> Media
  Service --> LocalModels
  Service -->|subprocess| AIWorker --> RemoteAI
  Service --> DB
  Service --> Files
  Service --> Store
  Store --> DB
  Store --> Artifacts
  Store --> Layout
  Store --> Registry
  Watcher <--> Obsidian
  Watcher --> Layout
  Layout --> WorkState
  Layout --> Research
  Registry --> Input
  Registry --> Visual
  Registry --> Orch
  Research -. 人が編集 .-> Obsidian
  Software -. アプリは書き込まない .-> Monolith
```

### 現行構成で責務が交差している場所

| 交差 | 現状 | 結果 |
| --- | --- | --- |
| Routingと業務処理 | ルート定義と保存・分析・スレッド起動が同じ`app.py` | HTTPなしのユースケーステストが難しい |
| Coreと保存技術 | `app.py`の処理がSQLite行、ファイルパス、Flask応答を直接扱う | 保存先やUI都合が業務ルールへ入り込む |
| 一時状態 | `jobs`、cancel event、cacheはメモリー、AI要求はSQLite、仕上げは`state.json`、固定保存途中は`analysis_pending_packages` | 「現在の処理状態」を1か所から説明できない |
| 分析の起動 | 分析本体は分割済みだが、集約・状態・保存・API変換は`app.py`に残る | 手法追加時の変更範囲が広い |
| 出力 | 通常出力、固定成果物、ResearchVault、3生成Vault、エクスポートが別経路 | 成功・失敗・再試行状態の集約が難しい |
| 共通処理 | パス検証、原子的書き込み、Markdown処理が`analysis_store`にあり、Obsidian側から上位層を参照する | 関数内importを含む循環依存がある |
