---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-17
title: 分析マイルストーン・可視化プログラム・UI統合設計：18.4 並列計算と短い保存ロック
summary: 18.4 並列計算と短い保存ロック。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 709
- 744
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：18.4 並列計算と短い保存ロック

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。

### 18.4 並列計算と短い保存ロック

現行`AnalysisCommands.save`は`_write_lock`内で`_build_analysis`等を呼ぶ。`AnalysisStore.save`も`STORE_LOCK`内の保存と公開経路を持つため、単にワーカー数を増やすだけでは並列化が成立しない。新pipelineでは次の境界へ段階的に移す。

| 区間 | 処理 | ロック・トランザクション |
| --- | --- | --- |
| 入力取得 | 原文/条件の版を一貫した読取で取得し、不変snapshot参照を確保 | 短い読取トランザクション。必要な版確認だけ既存ロック内 |
| 検査・計算 | 同じsnapshotで適用性検査、CPU/GPU処理、外部LLM呼出し | library/Storeの大域書込ロック外。資源枠は別に取得 |
| 出力準備 | attempt固有パスへ成果物を書き、hash・行数・schemaを検証 | 固有パス単位。SQLiteの書込トランザクション外 |
| 確定 | 取消世代・attempt・入力hash・期待状態を照合し、artifact参照と状態を一度だけ登録 | 短いトランザクションと比較更新。一意制約で重複を拒否 |
| 公開 | 確定成果物から選択したVaultへ公開 | 計算用大域ロック外。既存のノート所有権・公開先単位の競合制御 |

原文が並行編集された場合、実行中のsnapshotは変えない。旧snapshotの結果として保存し、現在入力との差をstaleとして表示する。現在版のキャッシュや手動定義へは上書きしない。取消と確定が競合した場合は永続状態の比較更新で勝った側を採用し、旧世代の応答は後続へ渡さない。

ファイルとSQLiteの同時確定は保証しない。登録前のファイルはattemptの仮成果物であり、再起動時に照合する。公開要求は確定結果と対応するattemptへ永続記録し、停止後に同じIDで回復する。旧APIの既存ロックを先に外すのではなく、固定snapshotと短い確定経路を新アダプターで成立させてから置換する。

性能評価では、同じ固定入力・手法・モデル条件の逐次/並列を比較し、総時間、計算時間、ロック待ち、保存時間、最大メモリー、provider使用量、失敗率を記録する。独立taskの実行区間の重なりと、次段階の先行開始0件を別々に確認する。

### 18.5 計算・保存・公開・pipeline完了の分離

| 識別子・状態 | 正本と意味 | 完了条件 |
| --- | --- | --- |
| pipeline_id / pipeline_status | 計画全体の要求台帳。analysis_pipeline_requests等の既存計画を拡張 | M0〜M7の全選択成果・ゲートが確定 |
| step_id / attempt_id | 一処理の実行と再試行。analysis_step_attemptsの計画を拡張 | 結果検証・保存確定、または計画で許容した適用外判定の確定 |
| result_run_id / result_status | 既存AnalysisStoreのanalysis_runs.id/status | その保存パッケージが不変artifactとして確定。従来のcompletedの意味を変更しない |
| publication target / status | pipelineのM7公開stepに紐づく公開先別結果 | 指定package/artifact hashに対応するノート・添付を公開し、書込結果を検証 |
| calculation_status / export_status | pipeline内の該当stepから導出する表示軸 | 計算対象/出力対象それぞれの確定。独立した別台帳を作らない |

公開先の識別は`result_run_id + target_role + package_hash`、試行はattempt IDで区別する。既存ResearchVaultの`vault_status`を全Vaultの合成状態へ読み替えない。Input/Orchestrator/Visualizationの成否は各対象から記録し、Software Vaultへは公開しない。未選択先はnot_selectedと記録し、ゲートには含めない。

順序は **結果パッケージ確定（result_run completed）→ 選択先公開 → 公開先別状態確定 → M7確定 → pipeline completed** とする。公開はresult_runの確定だけを前提にし、pipeline completedを待たない。これにより計算完了と公開完了の循環待ちを作らない。UIは「計算済み・公開失敗・全体未完了」を同時に表示できる。

現行`AnalysisStore.save`の自動公開を新pipelineへ無条件に持ち込まない。既存APIは従来の自動公開を維持し、新pipeline用アダプターでは保存と公開を分離できる明示モードを設ける設計とする。未対応のadapterで新pipelineを開始しない。`publish_vaults`内部の例外処理は公開先別のOutcomeを返すか永続記録する局所改修に限定し、汎用Publisherへの全面置換は行わない。

既存履歴にはpipeline_idを捏造しない。新pipelineが既存結果を再利用する場合のみ明示的に関連付ける。旧公開状態で個別成否が分からないものはunknownとし、全公開済みへ補完しない。公開再試行は同じ保存パッケージから行い、AI・統計計算を呼ばない。移行は一時DB/Vault、dry-run、旧APIの互換、切戻しを条件とする。
