---
note_id: module-analysis-orchestration
note_type: module
title: Core・Handler自律分析と実行状態UI
summary: 固定分析を残した自律分析、初期全量保持、批判応答、停止・復旧の契約。
status: current
verified: 2026-10-05
updated: 2026-10-05
schema_version: 1
tags:
  - gurumoji/program
  - gurumoji/analysis
---

# Core・Handler自律分析と実行状態UI

基点は `0d9239ac9d041d78d298c68a235738b3fe549a2a`。初版は `dot/core-handler-orchestration-20261004`。継続版は `dot/core-handler-durable-output-20261004`（基点 `f3e16ba`）。実装と検証の最新状態は [[60-Operations/dot-cloud-development-handoff]] の自律分析節を参照する。

## 責務と既存機能

- Coreは問い、現在の見解、矛盾、不足、追加案、批判への採否理由、分析上の終了を返す
- HandlerはPythonコード。正式タスク、固定入力、予算、並列数、保存、停止、復旧を扱い、AIとして表示しない
- 会話解釈・独立検証・批判者は既存JSON AI transportを使う。役割ごとの実provider/modelを固定し台帳・画面へ表示する
- 数量・統計系統は既存決定的集計adapterと、版付きラベルの実再集計 `label_frequency` を利用する。モデル名は捏造せず、Python集計と表示する
- 従来M0–M7、測定定義、safe publication、再試行世代管理は残る。自律分析は実行設定から選ぶ追加経路

## 実行・保存

`src/gurumoji/analysis_orchestration.py` が追記型結果と状態機械、`services/analysis_orchestration_adapters.py` が既存providerとの境界、`web/analysis_orchestration_routes.py` がHTTPを担当する。SQLiteの追加テーブルを使い、既存カラムの削除・型変更はしない。

追加テーブルは `orchestration_initials`、`orchestration_runs`、`orchestration_tasks`、`orchestration_results`、`orchestration_events`、`orchestration_decisions`、`orchestration_issues`、`orchestration_responses`、`orchestration_label_versions`、`orchestration_label_proposals`、`orchestration_usage`。DBを通常バックアップしたうえで既存起動経路のCREATE IF NOT EXISTSで追加する。旧版アプリはこの追加データを読まず、既存形式を保つ。新機能の利用をやめる場合も追加履歴を削除せず保持する。

初期分析は入力版・テンプレート版・設定に紐付く全量スナップショット。反復結果で初期版を上書きしない。タスク、結果、主張、根拠、批判、採否、ラベル版はそれぞれ参照可能にする。不正な参照・形式は正常な採用結果にしない。

専門家の追加案はCoreの判断を経てHandlerが正式発注する。独立検証は初期/Coreの期待結論を見ない。批判者は対象版と根拠を見て、指摘なし・未判定も返せる。終了案への批判とCoreの採否理由を残し、手動停止や上限到達ではレビューを無断追加しない。

### 初期構築のcheckpoint

本番経路は `base → linguistics → statistics → content → snapshot` の5段階。runを先に保存してからバックグラウンドで実行し、段階の完了出力・入力hash・前段hash・アルゴリズム版を保存する。再起動/段階失敗では停止し、利用者の再開操作で未完段階だけを実行する。完成済みの数量・統計を再計算しない。初期全量snapshotが確定するまでCoreは呼ばない。保存rowと選択済み専門知識を固定し、段階間で新しい版を混ぜない。

追加テーブルは `orchestration_initial_builds`、`orchestration_initial_stages`。旧版の確定済み初期snapshotも保持・再利用する。

モデル呼出しとHTML表示は分離する。`app.call_orchestration_ai_json` は1タスクにつき1回のtransport dispatchとし、既存HTTP clientの内部再送をこの経路だけ無効にする。不明な外部実行を勝手に再送しない。既存AI経路の再試行方針は変更しない。

2026-10-05のWindows検証で、CSV上限設定のC long幅による起動失敗と、raw SQLite connection factoryでの未closeを修正した。Coreの要約は空白だけを含む空文字も拒否し、不正な原結果は隔離して成功回数へ数えない。解釈担当へlabel_frequencyを指定した案も、タスク登録前に隔離する。プロンプト版は `core-handler-prompts-3-explicit-decision`。Coreは追加タスクか終了案を明示し、モデル用の終了理由はquestion_satisfied/no_more_evidence/human_review_requiredを区別する。ラベル案ではutterance_idとevidence_idを区別する。既存の `no_new_tasks` は作業案がない場合の停止であり、分析完了に読み替えない。

## 停止設定

2026-10-05の利用者指定により、新規run/APIと画面の既定はAIお任せ。`config.min_iterations=3`を固定し、採用済みのCore判断が最低3回になるまで通常の自動終了を保留する。3回目以降はCoreが続行または終了を判断し、終了前レビューと批判応答の契約を維持する。プロンプト版は`core-handler-prompts-4-minimum-iterations`。最低回数は「十分な分析品質」の保証ではない。

回数は永続化済み`orchestration_decisions`から数え、登録・通信試行・隔離結果を含めない。Core contextのbudgetへmin_iterations/completed_core_iterationsを渡し、原文の根拠対応・代替説明・未読範囲・批判応答を再検討させる。終了を保留したイベントと元の終了理由も保存する。同じ版のレビューを不要に繰り返さない。版が更新されたレビューは今回の`review_target`を使い、古い版を転記した応答は引き続き隔離する。

AIお任せの時間/回数上限は既定で空欄。任意の回数上限は3以上を要求する。手動停止、時間/呼出し/タスク上限、障害・不正応答・レビュー失敗は最低回数より優先するため、これらの停止時に3回を達成したと扱わない。明示的な時間/回数/重要度モードには最低回数を追加しない。既存runの条件・履歴は書き換えず、min_iterationsがない保存条件は最低回数なしとして扱う。既存のadapter版不一致による復旧停止も維持する。

時間、Core巡回数、重要度、AIお任せの4モード。AIお任せでは時間・巡回数を無上限にできるが、呼出し数・タスク数等の運用上限と手動停止は残る。重要度の高/中/低は未校正の暫定基準であり、確率・LLM自信・p値ではない。実費用を確実に取得できないため金額上限は受理せず、呼出し数・タスク数の上限で制御する。

ブラウザーを閉じても取消しにはしない。再表示は台帳を読み、実行を再発注しない。プロセス中断や応答不明は、完了済み結果を残して復旧判断を待つ。時間上限到達後の外部処理の物理的停止はproviderにも依存する。

## API

批判者のissue対象ID/版は、今回のreview_targetに一致する単一候補を生成用JSON schemaへ渡す。共有schemaは変更せず呼出しごとにコピーし、別run/別版へ制約が漏れない。返答の対象版・状態と指摘一覧の整合性は採用前にも検証し、不正応答を後から補正して成功扱いにしない。

Coreのcritique_responses/label_decisionsも今回実在するissue_id/proposal_idを生成候補にする。存在しない場合は配列のmaxItems=0。生成時の制約に加え、既存の採用前参照検証を維持する。架空の批判応答やラベル判断を修復して採用しない。

基本パス: `/api/library/<item_id>/analysis/orchestration`

- POST: 開始。JSON条件、`request_id`、入力revision、`question`、停止設定、モデル設定を渡す
- GET: 保存済みrun一覧。モデル呼出しなし
- `/<run_id>` GET: 状態、役割、タスク、イベント、usage、批判応答
- `/<run_id>/cancel` POST: 新規発注停止と取消し
- `/<run_id>/resume` POST: 初期段階/分析の明示的な復旧。状態により確認が必要
- `/<run_id>/publication/retry` POST: 同じ封印済み成果物・同じ公開範囲の保存/公開だけ再試行。条件変更不可
- `/<run_id>/results` GET: 初期版と保存履歴
- `/<run_id>/results/<result_id>` GET: 個別結果
- `/<run_id>/export.json` / `export.md` GET: 完全履歴JSON / Obsidian用ノートのダウンロード

画面更新・アニメーションはstatus/eventフラグとCSSのみ。表示のためのLLM呼出しは0回。token数はproviderの実測を受信した場合だけ表示し、未計測や一部不明を0扱いしない。

開始条件に `context_evidence_limit`（1〜120、既定120）と `context_text_limit`（1〜60000文字、既定60000）を指定できる。ローカルモデルの入力枠に合わせて1呼び出しの原文量を減らしても、全量の固定入力は保持する。各contextの `coverage` は利用可能件数・提供件数・省略件数を区別する。未読範囲を既読や確認済みにしない。これらは文字数・発話数の上限であり、根拠索引や結果履歴も含む総token数の保証ではない。

`context_index_limit`（0〜120、既定0）は各呼出しの根拠ID索引を先頭から制限する。0は従来通り省略なし。原文だけを減らしても323件のランダムID索引が入力枠を圧迫したため追加した。coverageのindex_available_count/index_provided_count/index_omitted_countに索引の省略を別記する。固定入力全量は保持するが、索引外の発話を自動で順次読む機能はない。制限した範囲の試験を全発話の分析完了と扱わない。

Handlerの `call_timeout_seconds` は実際のAI通信へ渡す。通信worker側の上限600秒は残る。既定の通信240秒で一律に切る旧動作からの修正であり、内部再送を追加しない。

## 機密性・限界

既定はlocal_only。クラウドAIへ原文・分析結果を送る場合、選択providerと明示同意を必要とする。認証情報は既存設定から都度読み、run設定へ保存しない。会話中の命令は実行指示として扱わない。

この版は探索分析。未使用検証データの隔離を保証する確認的統計ワークフローは実装しないため、confirmatory要求は拒否する。統計手法は実装済み能力に限定し、自由なPython実行・ネット検索・追加インストール・自己権限拡大は許可しない。

ラベル案と採用版は自律分析run内で保持し、元の研究者ラベルを勝手に書き換えない。`label_frequency` は全対象または明示した根拠ID範囲で、現在の固定ラベル版から度数・分母・欠測を実際に再計算する。旧版依存結果はstaleとして残す。既存の参加量・時系列adapterは初期全範囲の参照に限定し、部分範囲やラベル依存の再計算へ転用しない。Obsidian用ノートは完全台帳のダウンロードに加え、新runの明示選択で既存安全経路から公開できる。元データ・研究者所有ノートの保護と既存出版経路を維持する。

## 固定成果物と4先一式の公開

正常に分析完了したrunは、台帳全量を一度封印し、既存 `AnalysisStore.save(publish=False)` で固定packageへ保存する。原結果、初期版、批判/採否、ラベル各版は `result.json` の `orchestration` に完全保存し、可読ノートには要約/根拠/未解決批判を投影する。封印後のイベントや遅延結果を再試行時に取り込まない。

Vault公開は新runの既定OFF。選択できる単位は **Input・Orchestrator・Visualization・Researchの4先一式**。内部requested_targetsは既存の3先配列、effective_writersはResearchを含む4先。個別Vault選択ではない。Researchには発話本文も複製する。旧runの公開範囲を後から拡張しない。

追加テーブルは `orchestration_publications`、`orchestration_publication_attempts`。公開先/封印hash/世代/試行主体をguardし、`AnalysisStore.publish(reuse_completed=True)` と既存生成ノートpolicyを使用する。汎用の直接再公開/refreshから専用guardを迂回させない。保存成功、分析完了、公開処理完了を別々に表示する。

一部失敗は同じpackageとscopeで公開だけ再試行し、AI・統計・初期構築を再実行しない。既存契約に合わせ4writer一式を再確認するため、失敗先だけの再試行ではない。編集済み生成ノートの履歴を保存し、削除済み生成ノートを勝手に復元しない。writerがpublishedでも全ノート存在の保証ではない。

入力変更後も固定成果物は保持してstaleを示し、Vaultへの公開は競合として止める。取消/停止/失敗runを自動公開しない。実際の私有Vaultや移入研究Vaultに接続した検証は行っていない。

## 検証

合成会話・一時DB・mock providerによる回帰対象は `tests/test_analysis_orchestration*.py`、`tests/test_orchestration_review.py` とUI回帰。Windowsの保存データ確認は `scripts/test_saved_autonomous_analysis.py` を使い、元DBを読取専用でコピーして既存POST開始・実AI・保存台帳の経路を実行する。Vault公開を禁止し、初期分析だけの成功や空結果では合格させない。具体的な成功/失敗/未実行、モデルの実入力枠、実データ検証の限界は [[60-Operations/gurumoji-improvement-session]] に記録する。外部クラウドAIの品質・費用や実Vault公開を確認したという意味ではない。

試験の`--no-think`は対応するQwen3の実capabilityを確認し、既存の推論設定変換からreasoning_effort=noneを実通信へ渡す。応答を代用しない。`loop_execution_verified`は2回以上の有効Core結果・実usage・不正タスクなしと、安全な終状態を確認する。人の確認待ちでも反復動作は確認できるが、`analysis_completed`と厳格な`passed`は成功に変えない。
