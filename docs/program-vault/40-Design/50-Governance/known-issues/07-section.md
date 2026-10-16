---
note_type: reference-section
status: current
feature: project-status
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/issues
note_id: design-known-issues-section-07
title: 既知の問題点と改善方法（収束フェーズ）：追加調査：プログラム全体（2026-09-14）
summary: 追加調査：プログラム全体（2026-09-14）。出典ノート「既知の問題点と改善方法（収束フェーズ）」の分割本文。
parent_note_id: design-known-issues
source_path: 40-Design/known-issues.md
source_sha256: 93c0e1b715181e4d753e26636d16aa88dd9cf9b8c21d45e1ea6a76fb54c75414
source_body_lines:
- 124
- 134
split_on: '2026-10-11'
---

# 既知の問題点と改善方法（収束フェーズ）：追加調査：プログラム全体（2026-09-14）

親索引・状態・確認版：[[40-Design/50-Governance/known-issues/00-Index]]。必要な本文だけを取得する。

## 追加調査：プログラム全体（2026-09-14）

以下4件は追加登録。登録後の修正状況は各行の状態に反映した。調査範囲・確認版・調査時の検証は [[40-Design/50-Governance/convergence-plan/03-section#追加調査と対応順（2026-09-14）|convergence-plan#追加調査と対応順（2026-09-14）]]。既存の台帳統合・監視停止・UI配置の問題とは分けて扱う。

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法・受け入れ条件 | 状態 | 選別（追加調査） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BUG-02 | 高 | 比較結果の保存が、画面に表示した時点の入力版を確認せず、保存時点のデータで再集計する | `app.py:compare_group_interviews`、`save_interview_comparison_run`、`interview_comparison_request`。要求には会話IDと異内容比較の指定だけで、表示時の各revision・入力fingerprintがない。`static/interview-comparison.js:lastRequest`にも版を持たない | 比較を見た後に別画面・別タブで本文を編集すると、利用者が確認した結果と違うものが保存される。BUG-01のCSRF修正後にも残る独立した不具合 | 表示結果に構成会話ごとの入力fingerprint等を付け、保存時に照合。不一致なら409と再集計案内。クライアントの結果本文を無検証で保存しない。一時DBで表示時の対象発話2件→元データ編集→保存された結果1件、HTTP 200を再現した | 対応済み（[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）\|convergence-plan#優先修正の実装（2026-09-14）]]） | P1：優先 |
| DATA-04 | 中 | 分析準備のrevision変更が、保存済み実行のDB上の`stale`へ伝播しない | `transcript_preparation.py:save/write_state`は準備テーブルだけを更新。`analysis_store.py:initialize_store`のstale用triggerに準備テーブルがなく、`refresh_vaults`はDBのstaleだけを参照。`app.py:archive_source_stamp`は準備revisionを含むが、`list_interview_comparison_runs`はfingerprintを再検証しない | 準備状態を含む固定成果物が古くなっても、比較一覧・Orchestratorの更新要否に反映されない。単一会話の履歴APIはfingerprintで補正するため、表示先によって判定が違う | 準備更新と同じトランザクションで当該会話・構成比較の実行をstaleにするか、同じ版照合を各経路で共有する。一時DBで準備revision更新後のfingerprint変化と、一覧再生成後も比較APIのstaleが0のままであることを再現。通常の準備保存APIを通すE2Eは未実施 | 対応済み（[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）\|convergence-plan#優先修正の実装（2026-09-14）]]） | P1：優先 |
| OBS-18 | 中 | Input・Visualization・Orchestratorへの書き出し失敗が、保存結果APIの状態へ集約されない | `AnalysisStore.publish_vaults`は例外をwarningに記録し、`VaultRegistry.publish_analysis`の戻り値も利用しない。その後`publish`はResearchVault成功時に`vault_status=completed,error=''`とする。`public`には生成3Vaultの同期結果がない。`VaultRegistry.run_status`は内容のcurrent/staleを返し、同期のconflict/missingとは異なる | 生成Vaultが欠けてもUIでは「Vaultを保存しました」となり、再試行ボタンの条件も満たさない。OBS-09のwatcher停止やOBS-04の書き込み所有判定とは異なる、保存APIの結果集約漏れ | 正本保存の成功は維持したまま、Vaultごとの書き出し状態・理由をAPIで返し、未完了の出力を再試行できるようにする。一時Vaultで生成側の書き込み例外を注入し、ResearchVault成功後もAPIに公開する値がcompleted・空errorであることを再現 | 対応済み（`7c1cfeb`：保存APIに`vault_outputs`／`vault_outputs_complete`。障害注入テストあり） | P1：優先 |
| PERF-01 | 中 | 会話一覧APIがページ分割なしで全会話・全発話JSONを読み込む | `app.py:list_library`の`SELECT * FROM library_items`→`fetchall`→各行の`row_segments`→全候補の`library_public`。検索語が空でも全文を展開する。`static/app.js:loadLibrary/loadAnalysisCatalog`と`interview-comparison.js:loadCatalog`が同じ一覧を要求する | 会話・発話が増えるほど、一覧表示や検索のたびに処理量とメモリー使用量が増える構造。Obsidian監視のI/O負荷（OBS-08）とは別。実環境で遅延が発生する件数・秒数は未計測 | まず100会話×各1万発話等のfixtureで時間・メモリー・応答サイズを測定。絞り込み用メタデータの索引、一覧用の軽い取得、ページ分割を検討し、検索・話者・感情facetの意味を保つ。負荷測定前に性能改善を断定しない | 一部対応（`b739bb9`：100会話×1,000発話で0.50秒→0.33秒。発話JSONの二重解析とID計算を省いた。件数に比例する構造は残るため、一覧用の集計列とページ分割は後続） | P2：測定後に判断 |
