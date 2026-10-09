---
note_id: module-analysis-orchestration
note_type: module
title: Core・Handler自律分析と実行状態UI
summary: 固定分析を残した自律分析、初期全量保持、批判応答、停止・復旧の契約。
status: current
verified: 2026-10-05
updated: 2026-10-06
schema_version: 1
tags:
  - gurumoji/program
  - gurumoji/analysis
---

# Core・Handler自律分析と実行状態UI

基点は `0d9239ac9d041d78d298c68a235738b3fe549a2a`。初版は `dot/core-handler-orchestration-20261004`。継続版は `dot/core-handler-durable-output-20261004`（基点 `f3e16ba`）。実装と検証の最新状態は [[60-Operations/dot-cloud-development-handoff]] の自律分析節を参照する。

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

## 停止設定

2026-10-06の現行版は`core-handler-prompts-25-referenced-context`。実provider resolverは新規runの`specialist_orchestration_version=1`を既定にする。通常のAIお任せは`min_iterations=0`で固定回数を強制せず、専門側の分割評価をCoreの反復回数に含めない。Core統合前に全ての有効な未評価結果を分野別に査定し、Coreへは原結果ID・hashを保持した短い`domain_reports`を渡す。Coreの個別採否・批判応答・ラベル採否は拒否する。下記の最低3回・Core個別査定は明示的な旧経路`specialist_orchestration_version=0`の契約で、旧runの条件と履歴は変更しない。任意の上限1巡も受け付けるが、終了前レビューを完了できず上限停止する可能性を保つ。

2026-10-05の利用者指定により、新規run/APIと画面の既定はAIお任せ。`config.min_iterations=3`を固定し、採用済みのCore判断が最低3回になるまで通常の自動終了を保留する。3回目以降はCoreが続行または終了を判断し、終了前レビューと批判応答の契約を維持する。プロンプト版は`core-handler-prompts-4-minimum-iterations`。最低回数は「十分な分析品質」の保証ではない。

回数は永続化済み`orchestration_decisions`から数え、登録・通信試行・隔離結果を含めない。Core contextのbudgetへmin_iterations/completed_core_iterationsを渡し、原文の根拠対応・代替説明・未読範囲・批判応答を再検討させる。終了を保留したイベントと元の終了理由も保存する。同じ版のレビューを不要に繰り返さない。版が更新されたレビューは今回の`review_target`を使い、古い版を転記した応答は引き続き隔離する。

AIお任せの時間/回数上限は既定で空欄。任意の回数上限は3以上を要求する。手動停止、時間/呼出し/タスク上限、障害・不正応答・レビュー失敗は最低回数より優先するため、これらの停止時に3回を達成したと扱わない。明示的な時間/回数/重要度モードには最低回数を追加しない。既存runの条件・履歴は書き換えず、min_iterationsがない保存条件は最低回数なしとして扱う。既存のadapter版不一致による復旧停止も維持する。

同日の内容点検で、旧版の実AI成功runはCore3回の回答が完全一致していた。新しい実行契約`core-handler-prompts-5-progress`は`core_progress_version=1`を固定し、同じ回答の再送を採用済み判断へ加算しない。主張本文/区分/根拠集合、代替説明、未解決点、具体的な作業案を既存判断と比較し、同じ状態への循環も検出する。要約だけの変更、claim_id、配列順、重複要素、NFKC/空白/文末句読点の違いは進展にしない。数値の符号・小数点・語の境界は保持する。意味が等しい任意の言い換えをすべて検出する意味判定器ではない。

Coreへ`iteration_review`で未評価の専門家結果IDを最大20件渡し、`result_assessments`に各結果の採否・理由・結論への影響を要求する。未提示の未評価結果を直近20件で落とさず、必要なら次のCoreで評価する。独立検証は引き続きCoreの期待結論を見ない。新しい結果への採否、初回の批判応答/ラベル判断は、結論を変えない再検討の根拠にもなる。ただし同じ役割・入力/ラベル版・対象範囲・原結果hashの再生成は新IDでも新しい根拠にしない。存在しない結果、Core自身の結果、既評価結果、同一IDの重複、空の採否理由/影響は採用しない。

新しい検討の根拠がなく既存判断と同じなら`no_progress`で停止し、最低3回未満でも完了・自動公開にしない。未評価の専門家結果を無視した応答は隔離し、`unreviewed_results`で停止する。原応答とhash、重複元decision ID、停止イベントを保持する。APIの`completed_core_iterations`と画面は採用済み判断数を示し、実呼出し回数と区別する。旧runの条件・完了状態・封印済み成果物は変更せず、旧adapter版の実行再開は従来通り拒否する。

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

## 初回の専門エージェントによるラベル・尺度出力

利用者指定（2026-10-05）により、現行adapterは`core-handler-prompts-12-initial-evidence`。実provider resolverは`initial_specialist_analysis_version=1`、`initial_label_definitions_version=1`、`core_progress_version=1`を固定する。初回は全専門家の予備分析、Handlerによる要件集約、Coreの担当指示、専門家による尺度設計、1回目のCore統合の順に進む。Coreは尺度の作成主体ではない。予備分析と担当指示はCore反復回数へ加算しない。

初期snapshot確定後、Handlerは`initial_analysis`で会話解釈・独立検証・批判者、および数量統計の既存3手法（participation/conversation_dynamics/label_frequency）へ正式タスクを登録する。AI担当は同じ提示範囲の原文を独立に読む。批判者の初回対象は研究の問いと分析計画で、まだ存在しない結論ではない。数量統計は既存の確定入力/保存集計と現行ラベルを使い、任意の新しい尺度を作らない。

各担当は`label_requirements`を初回結果としてHandlerへ報告する。要件は一意ID、label/scale、名称、分析用途、必要な理由、読んだ根拠IDを含み、不要なら空配列を明示する。Handlerは各結果の受領をイベントへ保存し、全6タスクの成功/hash/入力版を照合して`initial_analysis_report`へ集約する。同じ要件は出所を保ってまとめ、担当の失敗・報告欠落は`initial_analysis_incomplete`で停止する。未実行を不要や成功へ置換しない。

予備分析の要約だけを成功扱いにしないため、会話解釈・独立検証には空でない要約と根拠付きclaimsを1件以上要求する。数量統計のlabel_frequencyが対象全件のcodes欠測を返した場合は、分類の定義と発話への付与が必要だと要件へ明示する。数量集計は全対象の分母を使い、AIへ提示した発話数とは区別する。定義が作成されたことだけで発話の欠測が埋まったと扱わない。

Coreは`initial_routing`（iteration=0）で集約報告を読み、専門家への問い・理由・採用基準を含む1件の`interpretation/label-design-v1`をintentsとしてHandlerに指示する。Handlerが依存関係を付けて`initial_labels`へ正式発注する。現在、尺度設計を実行できる担当は会話解釈専門エージェントであり、別のオーケストレータサービスや任意のプログラム実行は追加しない。担当指示の原結果とdecisionは保存するが、採用済みCore統合回数から除外する。終了案・尺度の自作・発話ラベル変更を含む不正な担当指示は隔離し、`initial_routing_invalid`で停止する。

尺度設計タスクは原文と問いに加え、集約された各担当の要件とCoreの依頼を受け取る。出力を保存・検証してから1回目の統合へ進み、Coreが予備分析全件と尺度結果の採否・根拠付き主張・限界を評価する。専門家の追加分析案はCoreが既存の各担当へのintentsに変換し、Handlerが発注する。独立検証は引き続き他担当/Coreの結論を受け取らない。保存済みの旧runは従来の段階契約を保持し、現行adapterへ自動移行しない。

`label_definitions`は1〜12件必須。安定ID/版、名前、測定対象、発話単位、型、尺度水準とその理由、値の意味・判定基準、判定規則、欠測条件、推奨集計方法、提示された根拠IDを検証する。名義/順序尺度は異なる値を2件以上。初回の順序尺度はnumber型の数値符号を昇順で出力し、category/booleanは名義尺度へ限定する。生成schemaの型別分岐でlevels.valueも同じ型に固定する。名義/順序尺度に平均を適用せず、欠測は`null_with_reason`としゼロにしない。「欠測」「未読」「missing」「null」「none」「n/a」を通常値へ混ぜた案を拒否する。空配列・形式不正・未提示の発話根拠は原回答を隔離し、Core実行前に`initial_labels_missing`で停止する。Provider障害・取消・予算上限は出力成功として扱わない。

保存した専門家原結果のhash・入力版・task/attempt/作成主体を再確認して、`initial_label_catalog`をCoreと後続解釈/批判へ渡す。独立検証のblind packetには渡さない。初回Coreにも専門家結果の採否・理由・影響を要求する。中断後は保存済み専門家結果を再利用し、同じ作成タスクを再発注しない。

実データ試験で入力枠超過とID誤写を確認したため、AIパケットでは各発話の重複したdataset_version/source_hash/idを省き、根拠ID・発話ID・原文・話者・時刻とルートの入力版を渡す。全量の固定根拠とhashは保存台帳で維持する。尺度設計は原文と問いだけの専用パケットとし既存AIラベルを渡さない。後続のlabelsは既存の変更可能フィールドへ限定し、catalogの重複送信も避ける。

生成schemaは主張/批判の根拠IDを提示済み原文と保存済み主張に、追加タスクの根拠IDを提示索引に限定する。依存task ID・保存result ID・initial ID/節も実在値へ固定し、statisticsの計算とAIの解釈を型別分岐する。主張と尺度の中心根拠は各8件以内にする。schemaコピーはJSON往復で共有コンテナーを分離し、依存taskの制約を根拠IDへ誤適用しない。採用時の既存実在参照/hash検証を省かず、AIが生成した不正なIDを事後に置換しない。指示強化だけで意味上の尺度妥当性を保証したとは扱わない。

定義は`ai_draft`であり研究者が確定したコードブックではない。発話ラベル・既存codebook_version・研究者ノートを書き換えず、実行可能なmanual測定定義へ自動登録しない。原結果、runのcatalogとCore判断の参照IDを既存台帳/固定`result.json`へ保存し、画面の「ラベル・尺度の定義を読む」とJSON/Markdown書き出しから閲覧できる。以前のrunへ定義を捏造して補完しない。旧adapter版のrunの履歴閲覧は維持し、再開には既存の版一致guardが適用される。

## 固定成果物と4先一式の公開

正常に分析完了したrunは、台帳全量を一度封印し、既存 `AnalysisStore.save(publish=False)` で固定packageへ保存する。原結果、初期版、批判/採否、ラベル各版は `result.json` の `orchestration` に完全保存し、可読ノートには要約/根拠/未解決批判を投影する。封印後のイベントや遅延結果を再試行時に取り込まない。

Vault公開は新runの既定OFF。選択できる単位は **Input・Orchestrator・Visualization・Researchの4先一式**。内部requested_targetsは既存の3先配列、effective_writersはResearchを含む4先。個別Vault選択ではない。Researchには発話本文も複製する。旧runの公開範囲を後から拡張しない。

追加テーブルは `orchestration_publications`、`orchestration_publication_attempts`。公開先/封印hash/世代/試行主体をguardし、`AnalysisStore.publish(reuse_completed=True)` と既存生成ノートpolicyを使用する。汎用の直接再公開/refreshから専用guardを迂回させない。保存成功、分析完了、公開処理完了を別々に表示する。

一部失敗は同じpackageとscopeで公開だけ再試行し、AI・統計・初期構築を再実行しない。既存契約に合わせ4writer一式を再確認するため、失敗先だけの再試行ではない。編集済み生成ノートの履歴を保存し、削除済み生成ノートを勝手に復元しない。writerがpublishedでも全ノート存在の保証ではない。

入力変更後も固定成果物は保持してstaleを示し、Vaultへの公開は競合として止める。取消/停止/失敗runを自動公開しない。実際の私有Vaultや移入研究Vaultに接続した検証は行っていない。

## 検証

### モデル予算と段階別入力の試験経路

`model_context_version=1`を指定した新規runで現行adapterと`services/model_context.py`を使用する。APIの未指定時は0を維持し、全担当がローカルのUI起動では1とする。旧runはadapter版を照合し、新契約で自動再実行しない。現在はLM Studioだけを予算計測の対象とし、ロード済みhandleのtemplate/tokenizer・実枠・設定hashで確認する。schemaは保守的に加算し、結果数・提示した批判の応答数に応じた出力予約と512tokenの余裕を残す。初期分析も3200token以上を予約する。予測予算は課金usageへ加算しない。

`context_reference_version=1`は実測経路で既定有効。`task_instruction`にDBの論理パスとObsidian参照を置き、Handlerが解決した内容を別の`resource_data`メッセージへ分離する。パスはモデルの任意filesystem権限ではない。必要な原文・結果・専門報告だけを固定snapshot/resultから選び、既存`ExpertCatalog`が共通知識2ノートの指定節と許可済みbriefを読む。知識の適用条件・禁止事項は維持し、全Vault・他専門家・研究者所有ノートは読まない。参照path・ID・版・hash、メッセージ群hash、実提示範囲は既存manifestに保存する。system/user/dataとschemaを合計して実測するため、メッセージ分離だけでトークンを節約したとは扱わない。詳細はADR-127。

統合では未評価の結果だけを順序付きで取得し、その主張・批判・尺度要求が引用した原文を入力版から取り直す。過去の批判の引用を現在batchより優先して取り直さない。未提示の結果や批判を読了扱いにせず、提示ID・評価対象・残数をmanifestに記録する。全件専用のコード統計は、部分範囲を指定できない出力schemaにする。

初期全役割へ全発話の分割タスクを発注し、所有範囲と前後1発話の境界を区別する。予算不足の未送信ページはDBで親を保持して再分割する。Core報告と尺度設計の要件も、本文と適用条件を落とさず別タスクへ分割する。すべての専門家の読了、全要件の担当指示、専門家の尺度下書きが揃ってから統合へ進む。尺度名の衝突は保存し、自動的に確定・上書きしない。

Coreは未評価結果の順序付きbatchだけを読み、残りを次の判断へ保持する。尺度定義も今回の評価対象の結果から取得し、未取得数と完全catalogのhashを残す。DBのtask JSONへ入力manifestとhashを保存し、原結果は同じmanifest hashを参照する。発話・結果・prompt・schema・専門家知識・モデル設定へ追跡できる。

会話解釈へ既存の手法別briefを接続し、`expert_step_ids`では許可済み手順だけを選べる。適用条件・範囲外・禁止結論を保持し、古い定義/hash・AI補助不可は送信前に拒否する。独立検証は他担当の結果・期待結論を含まない。詳細と未実装範囲は[[40-Design/model-context-and-work-memory-plan]]と[[40-Design/expert-knowledge-production-plan]]を参照する。

合成試験は`tests/test_model_context.py`と`tests/test_selected_expert_context.py`。実試験は従来CLIの`--model-context --max-calls N --max-tasks N`を使う。`scripts/test_model_context_packet.py`は試験コピーの単発packetを読取専用で検証し、元runを再開しない。これらの合格を研究上の内容品質や全体分析の完了へ読み替えない。

合成会話・一時DB・mock providerによる回帰対象は `tests/test_analysis_orchestration*.py`、`tests/test_orchestration_review.py` とUI回帰。Windowsの保存データ確認は `scripts/test_saved_autonomous_analysis.py` を使い、元DBを読取専用でコピーして既存POST開始・実AI・保存台帳の経路を実行する。Vault公開を禁止し、初期分析だけの成功や空結果では合格させない。具体的な成功/失敗/未実行、モデルの実入力枠、実データ検証の限界は [[60-Operations/gurumoji-improvement-session]] に記録する。外部クラウドAIの品質・費用や実Vault公開を確認したという意味ではない。

試験の`--no-think`は対応するQwen3の実capabilityを確認し、既存の推論設定変換からreasoning_effort=noneを実通信へ渡す。応答を代用しない。`loop_execution_verified`は2回以上の有効Core結果・実usage・不正タスクなしと、安全な終状態を確認する。人の確認待ちでも反復動作は確認できるが、`analysis_completed`と厳格な`passed`は成功に変えない。
