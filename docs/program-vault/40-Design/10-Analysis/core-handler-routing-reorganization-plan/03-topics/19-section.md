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
note_id: design-core-handler-routing-reorganization-section-19
title: コア・ハンドラー・ルーティング再編案：維持する契約と分けて扱う課題
summary: 維持する契約と分けて扱う課題。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 1218
- 1246
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：維持する契約と分けて扱う課題

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

## 維持する契約と分けて扱う課題

### 分析プログラム

- `analysis_method_registry.METHODS`、`REGISTRY_VERSION`、`method_results`を正本として継続利用する。現在は21手法。再編だけを理由に契約の版を上げない。
- 手法IDは利用者向け分類であり、実行単位とは限らない。`research_analysis`などの一括計算を手法ごとに分割実行すると、共通計算・モデル読込・保存が重複し得る。実行単位と呼び出し回数を維持する。
- 同期集計、非同期AI／Transformer、保存済み結果、議事録・比較の独立runを無理に同じrunnerへ変換しない。共通化は具体的な重複を確認した時点で検討する。
- `completed / empty / not_run / unavailable / fallback / stale / partial`等の現行結果表現を保持する。これをジョブやVault同期の状態名として流用しない。
- 「手法追加はcatalog・runner・schema・テストだけで完了する」という保証は外す。独自入力や画面が必要ならAPI/UI変更も必要になる。

### 状態と回復

| 状態 | 現行の所有先 | 再編時の扱い |
| --- | --- | --- |
| 文字起こし受付・進捗・取消 | `jobs`、`jobs_lock`、受付ID、JobRecord | 同じメモリー状態と受付制御を共有。プロセス再起動後の自動再実行は追加しない |
| AI見解・Transformer要求 | SQLite要求行＋cancel event／lock | 永続状態とプロセス内イベントを区別し、終了時の解除を維持 |
| Obsidian仕上げ | Workbenchの既存JSON、watcher | 原文・結果・再試行条件を保持。一般ジョブの状態へ置換しない |
| 固定保存途中 | `analysis_pending_packages`、AnalysisStore | 元の入力・結果を使う回復を保持。cacheや一時ファイルとして掃除しない |
| 編集・削除途中 | 既存manifest、staging、隔離・回復処理 | 操作単位の確定順と起動時回復を保持 |
| 分析の古さ・公開状態 | revision／fingerprint／DB trigger、`vault_status`等 | 入力の古さと公開失敗を別軸のまま扱う |

既存機能の構造再編では、統合状態API、新しい永続ジョブ基盤、汎用`ExecutionWorkspace`のcommit／rollbackを導入しない。FLOW-1〜2では、新しい追加分析に必要な受付・試行状態だけを「段階実行の状態と再開」に従って同じSQLiteへ追加する。既存ジョブの状態は移行・統合しない。SQLite、ファイル、Vaultを1つの原子トランザクションとして扱わず、既存の確定・部分失敗・再試行の境界を維持する。

### 出力・Vault

`AnalysisStore`が既に持つ「正本保存を先に確定し、Vault公開は再試行可能にする」責務を、Handler・Repository・ArtifactStoreに分解し直さない。ResearchVaultと生成3Vaultの所有権・公開経路も維持する。

OBS-18（生成Vaultの失敗がAPIへ伝わらない問題）は[[40-Design/50-Governance/known-issues/00-Index|known-issues]]／[[40-Design/50-Governance/convergence-plan/00-Index|convergence-plan]]の優先課題として、既存経路で独立して修正する。全面再編や共通Publisherの完成を前提にしない。修正後はその新しい契約を後続の再編の基準に取り込む。新しい部分失敗API・UIの設計は、この挙動維持の計画とは別の変更で扱う。
