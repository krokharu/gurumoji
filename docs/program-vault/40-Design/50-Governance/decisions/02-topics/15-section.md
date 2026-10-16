---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-15
title: 設計判断の記録（ADR）：ADR-119 文字起こしの外部連携を `app.py` から分離する
summary: ADR-119 文字起こしの外部連携を `app.py` から分離する。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 465
- 493
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-119 文字起こしの外部連携を `app.py` から分離する

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

### ADR-119 文字起こしの外部連携を `app.py` から分離する

- **状態：** accepted、着手済み（2026-09-22）
- **背景：** `app.py` にAI通信、AI仕上げ、音声前処理、ASRの発話整形、出力生成が同居し、単一ファイルが肥大化していた。今回の目的は互換層を増やすことではなく、`app.py` の実装行を減らすことである。
- **決定：** AI通信は `services/ai/client.py`、AI整文・Jev・アウトラインは `services/ai/transcript_finishing.py`、ffmpeg音声前処理は `services/transcription/audio.py` へ置く。アプリ側は設定値と実行時依存を組み立てるだけにし、移設済みの旧実装を残さない。残る発話整形、議事録、字幕・出力、感情推論、文字起こしrunnerも同じ規則で段階的に移す。
- **理由：** Flask、SQLite、外部AI、ffmpeg、ジョブ状態の依存を一つのモジュールへ固定せず、個別にテスト・再利用できるようにするため。
- **結果・影響：** 既存のHTTP endpoint、ジョブ取消、SQLite・Vaultの確定順序は変更しない。テストの差し替えは移設先の依存注入へ移し、`app.py` の再export・互換ラッパーを恒久的なAPIにしない。
- **関連：** [[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]、[[20-Modules/10-Inventory/module-map/00-Index|module-map]]

### ADR-120 実行環境ごとのローカル知識を、Gitで共有するSoftware Vaultとは別の階層に置く

- **状態：** accepted、実装済み（2026-09-25）
- **背景：** 利用者から、専門家定義・文献ノートなどAI実行時の知識（ADR-115）はGitで共有する「ベース」だけにし、各実行環境（研究者の端末ごと）でローカルに知識を拡張・変更できるようにしたいという依頼があった。論文原本などの資料はローカルにのみ保持し、Gitには研究者が内容を理解したうえで書いた要約ノートだけを載せる方針も含む。
- **決定：**
  - `src/gurumoji/method_experts.py` の `ExpertCatalog` に、Git管理外の第2の読み込み元 `local_root`（既定は `<data>/local_knowledge`、`MOJIOKOSI_DATA_DIR` 配下）を追加する。`<data>` はVaultと同じく `runtime/` 配下でGit管理対象外（`.gitignore`）。
  - `local_root` の内部構造は `SOFTWARE_ROOT` と同じ相対パス（`50-Analysis-Methods/10-Experts/<専門家>/`、`20-Literature/`、`08-Common-Knowledge/`）にする。既存の相対パス定数（`EXPERTS_DIR`・`LITERATURE_DIR`・`COMMON_DIR`）をそのまま再利用できるようにするため。
  - ノート単位で解決する：同じ相対パスのファイルが `local_root` にあればそれを使い、なければ `SOFTWARE_ROOT` を使う（`ExpertCatalog._resolve`）。専門家フォルダーの一覧は両方の和集合とし、`index()` の各項目に `source`（`base`／`local`／`local_override`）を付けて、どの専門家・どのファイルがローカル限定かを常に判別できるようにする。
  - 知識hash（`ExpertCatalog.knowledge`）は実際に解決された（ローカル優先の）ファイル内容から計算するため、ローカルの追記・上書きは既存のhash機構でそのまま検知される。ローカル知識は原本文献の全文ではなく、ADR-115と同じ「専門家定義・文献ノート」の形式で書く。
  - `local_root` が存在しない・空の環境では、全ノートが `SOFTWARE_ROOT` から解決され、既存の17専門家・挙動と完全に一致する（後方互換）。
- **理由：**
  - 既存の `ExpertCatalog(root=...)` の差し替え可能な設計と、`<data>` がすでにGit管理外である慣習を再利用でき、新しい依存や別の同期機構を増やさない。
  - Vault側のVaultRegistry（所有hash・conflict判定）とは別領域とする。ローカル知識はVaultの利用者ノートではなく、実行時にだけ読むアプリ内部の設定に近いため、Obsidianの競合処理を流用する必要がない。
  - 相対パスをそのまま流用することで、ローカル追加・上書きの両方を同じ仕組みで表現できる（新規専門家フォルダーの追加＝`local`、既存フォルダー内の一部ノート差し替え＝`local_override`）。
- **結果・影響：**
  - `catalog_summary()`（`GET /api/analysis/experts`）に `source` が乗るため、画面側でローカル限定の専門家・上書きを表示する余地ができる（今回は表示側の変更は行わない）。
  - テスト：`tests/test_method_experts.py` の `LocalKnowledgeTests`（ローカル無し＝既存互換、ローカル専用フォルダーの追加、既存ノートのローカル上書きとhash変化）。
  - 原本資料（論文PDF等）自体はこの階層にもGitにも置かない前提は変わらない。研究者が要約・咀嚼した文章だけをノートとして置く運用は、[[40-Design/50-Governance/method-rules/00-Index|method-rules]] の登録手順に従う。
- **関連：** ADR-115、[[40-Design/50-Governance/method-rules/00-Index|method-rules]]、[[50-Analysis-Methods/10-Experts/00-Index]]
