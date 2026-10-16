---
note_type: reference-section
status: current
verified: 2026-10-05
updated: 2026-10-06
schema_version: 1
tags:
- gurumoji/program
- gurumoji/analysis
note_id: module-analysis-orchestration-section-01
title: Core・Handler自律分析と実行状態UI：Core・Handler自律分析と実行状態UI
summary: Core・Handler自律分析と実行状態UI。出典ノート「Core・Handler自律分析と実行状態UI」の分割本文。
parent_note_id: module-analysis-orchestration
source_path: 20-Modules/analysis-orchestration.md
source_sha256: 145ca8522ee906fad2e00812f0dcd27f6c2c4f143f52b9c715fc81da9060e96c
source_body_lines:
- 1
- 49
split_on: '2026-10-11'
---

# Core・Handler自律分析と実行状態UI：Core・Handler自律分析と実行状態UI

親索引・状態・確認版：[[20-Modules/20-Analysis/analysis-orchestration/00-Index]]。必要な本文だけを取得する。


# Core・Handler自律分析と実行状態UI

基点は `0d9239ac9d041d78d298c68a235738b3fe549a2a`。初版は `dot/core-handler-orchestration-20261004`。継続版は `dot/core-handler-durable-output-20261004`（基点 `f3e16ba`）。実装と検証の最新状態は [[60-Operations/20-Development/dot-cloud-development-handoff/00-Index|dot-cloud-development-handoff]] の自律分析節を参照する。

## 責務と既存機能

- 新規runのCoreは初回の尺度要件の担当指示、分野間の統合、分析上の終了案を返す
- 専門オーケストレータは分野別の結果採否、批判への応答、具体的な追加分析を返す。Coreの見解・終了状態を更新しない。尺度下書きは会話解釈専門家が作成し、独立した批判者が先に検証する
- HandlerはPythonコード。正式タスク、固定入力、予算、並列数、保存、停止、復旧を扱い、AIとして表示しない
- 会話解釈・独立検証・批判者は既存JSON AI transportを使う。役割ごとの実provider/modelを固定し台帳・画面へ表示する
- 数量・統計系統は既存決定的集計adapterと、版付きラベルの実再集計 `label_frequency` を利用する。モデル名は捏造せず、Python集計と表示する
- 従来M0–M7、測定定義、safe publication、再試行世代管理は残る。自律分析は実行設定から選ぶ追加経路

## 実行・保存

### Orcaで分析担当を確認する

2026-10-06に `scripts/watch_analysis_agents.py` を追加した。Orcaのターミナルで既存 `AnalysisHistoryService.agents()` の読み取り専用投影を表示する。Core・Handler・会話解釈・数量/統計・独立検証・批判者・専門オーケストレータについて、保存されたprovider/model、状態別件数、実行中/不明なtask IDを確認できる。Handlerと数量/統計はCODEと表示する。発話本文・問い・raw応答・認証設定は出力しない。

```powershell
.\.venv\Scripts\python.exe scripts/watch_analysis_agents.py --watch
.\.venv\Scripts\python.exe scripts/watch_analysis_agents.py --database <試験DBのパス> --run-id <run_id> --watch
```

既定DBは `MOJIOKOSI_DATA_DIR`、未指定なら `runtime/data/library.sqlite3`。`--item-id`で会話を限定でき、`--run-id`なしでは対象DB/会話の最後に登録されたrunを表示する。試験は隔離DBを明示し、本番台帳と混同しない。`--json`は単発JSON、`--watch --json`は変更時のJSON行を出力する。Ctrl+Cはモニターだけを終了する。

接続はSQLite `mode=ro` と `query_only=ON`。既存閲覧サービスのread transactionでrun/taskを一貫して読み、AI実行・schema初期化・復旧・公開を呼ばない。DBがない場合は作成せず取得不能を表示する。台帳のrunningはプロセス生存を証明せず、保存更新時刻と「保存状態」の注意を常時示す。各担当をOrcaネイティブのCodexワーカーとして登録する機能ではない。

基点 `75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b` の未コミット変更上で検証。`tests/test_analysis_agents_monitor.py` 6件成功（DB非変更、未作成、所属不一致拒否、状態更新、run固定、本文/秘密除外）。隣接 `test_analysis_history_viewer.py` は19/20成功、日時境界の `test_timeline_filters_and_sql_pagination` が2件対期待1件で失敗し、履歴サービスをHEAD版に戻してメモリー内実行しても同じ失敗を再現。最新の隔離試験DBの担当状態をOrcaターミナルで確認した。本番DBは履歴有無の読取のみ、元会話・注釈・Vaultへの書込みなし。今回の検証で実AIを新規実行せず、Web UIの画面操作は対象外。

`src/gurumoji/analysis_orchestration.py` が追記型結果と状態機械、`services/analysis_orchestration_adapters.py` が既存providerとの境界、`web/analysis_orchestration_routes.py` がHTTPを担当する。SQLiteの追加テーブルを使い、既存カラムの削除・型変更はしない。

追加テーブルは `orchestration_initials`、`orchestration_runs`、`orchestration_tasks`、`orchestration_results`、`orchestration_events`、`orchestration_decisions`、`orchestration_issues`、`orchestration_responses`、`orchestration_label_versions`、`orchestration_label_proposals`、`orchestration_usage`。DBを通常バックアップしたうえで既存起動経路のCREATE IF NOT EXISTSで追加する。旧版アプリはこの追加データを読まず、既存形式を保つ。新機能の利用をやめる場合も追加履歴を削除せず保持する。

初期分析は入力版・テンプレート版・設定に紐付く全量スナップショット。反復結果で初期版を上書きしない。タスク、結果、主張、根拠、批判、採否、ラベル版はそれぞれ参照可能にする。不正な参照・形式は正常な採用結果にしない。

新規runでは専門オーケストレータの具体的な追加案をHandlerが直接発注する。元の問いをそのまま繰り返す分析案は保留し、既存の版・範囲・条件による重複抑止を維持する。独立検証は初期/Coreの期待結論を見ない。批判者は対象版と根拠を見て、指摘なし・未判定も返せる。終了案への批判は専門側が応答し、Coreは全体の終了判断を返す。手動停止や上限到達ではレビューを無断追加しない。

### 初期構築のcheckpoint

本番経路は `base → linguistics → statistics → content → snapshot` の5段階。runを先に保存してからバックグラウンドで実行し、段階の完了出力・入力hash・前段hash・アルゴリズム版を保存する。再起動/段階失敗では停止し、利用者の再開操作で未完段階だけを実行する。完成済みの数量・統計を再計算しない。初期全量snapshotが確定するまでCoreは呼ばない。保存rowと選択済み専門知識を固定し、段階間で新しい版を混ぜない。

追加テーブルは `orchestration_initial_builds`、`orchestration_initial_stages`。旧版の確定済み初期snapshotも保持・再利用する。

モデル呼出しとHTML表示は分離する。`app.call_orchestration_ai_json` は1タスクにつき1回のtransport dispatchとし、既存HTTP clientの内部再送をこの経路だけ無効にする。不明な外部実行を勝手に再送しない。既存AI経路の再試行方針は変更しない。

2026-10-05のWindows検証で、CSV上限設定のC long幅による起動失敗と、raw SQLite connection factoryでの未closeを修正した。Coreの要約は空白だけを含む空文字も拒否し、不正な原結果は隔離して成功回数へ数えない。解釈担当へlabel_frequencyを指定した案も、タスク登録前に隔離する。プロンプト版は `core-handler-prompts-3-explicit-decision`。Coreは追加タスクか終了案を明示し、モデル用の終了理由はquestion_satisfied/no_more_evidence/human_review_requiredを区別する。ラベル案ではutterance_idとevidence_idを区別する。既存の `no_new_tasks` は作業案がない場合の停止であり、分析完了に読み替えない。
