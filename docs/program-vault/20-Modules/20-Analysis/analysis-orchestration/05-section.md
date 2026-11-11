---
note_type: reference-section
status: current
verified: 2026-10-05
updated: 2026-11-06
schema_version: 1
tags:
- gurumoji/program
- gurumoji/analysis
note_id: module-analysis-orchestration-section-05
title: Core・Handler自律分析と実行状態UI：固定成果物と4先一式の公開
summary: 固定成果物と4先一式の公開。出典ノート「Core・Handler自律分析と実行状態UI」の分割本文。
parent_note_id: module-analysis-orchestration
source_path: 20-Modules/analysis-orchestration.md
source_sha256: 145ca8522ee906fad2e00812f0dcd27f6c2c4f143f52b9c715fc81da9060e96c
source_body_lines:
- 128
- 160
split_on: '2026-10-11'
---

# Core・Handler自律分析と実行状態UI：固定成果物と4先一式の公開

親索引・状態・確認版：[[20-Modules/20-Analysis/analysis-orchestration/00-Index]]。必要な本文だけを取得する。

## 固定成果物と4先一式の公開

2026-11-09追記：新しい終了手順 `completion_protocol_version=1` では、分析処理を完了した人手確認待ちの実行を、AI下書きとして固定保存できる。`status=stopped`、`stop_reason=human_review_required`、`analysis_processing_complete=true`、`human_review_status=required` を区別して保持し、改訂版が未レビューなら `review_status=incomplete` とする。この例外は固定保存だけに適用し、Vaultへの自動公開は `review_required` で保留する。元のモデルの停止理由は `model_stop_reason` と原応答に保持する。全タスク・分割範囲・有効結果・採否・終了前レビュー・批判応答・必須手法の処理完了を封印時にも照合し、フラグだけで保存を許可しない。過去のrunと採否の記録がない旧プロトコルは従来の扱いを維持する。詳細は [[20-Modules/20-Analysis/analysis-orchestration/06-section|結果IDによる再分析・分析処理の完了・必須手法]] を参照。

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

会話解釈へ既存の手法別briefを接続し、`expert_step_ids`では許可済み手順だけを選べる。適用条件・範囲外・禁止結論を保持し、古い定義/hash・AI補助不可は送信前に拒否する。独立検証は他担当の結果・期待結論を含まない。詳細と未実装範囲は[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index|model-context-and-work-memory-plan]]と[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index|expert-knowledge-production-plan]]を参照する。

合成試験は`tests/test_model_context.py`と`tests/test_selected_expert_context.py`。実試験は従来CLIの`--model-context --max-calls N --max-tasks N`を使う。`scripts/test_model_context_packet.py`は試験コピーの単発packetを読取専用で検証し、元runを再開しない。これらの合格を研究上の内容品質や全体分析の完了へ読み替えない。

合成会話・一時DB・mock providerによる回帰対象は `tests/test_analysis_orchestration*.py`、`tests/test_orchestration_review.py` とUI回帰。Windowsの保存データ確認は `scripts/test_saved_autonomous_analysis.py` を使い、元DBを読取専用でコピーして既存POST開始・実AI・保存台帳の経路を実行する。Vault公開を禁止し、初期分析だけの成功や空結果では合格させない。具体的な成功/失敗/未実行、モデルの実入力枠、実データ検証の限界は [[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]] に記録する。外部クラウドAIの品質・費用や実Vault公開を確認したという意味ではない。

試験の`--no-think`は対応するQwen3の実capabilityを確認し、既存の推論設定変換からreasoning_effort=noneを実通信へ渡す。応答を代用しない。`loop_execution_verified`は2回以上の有効Core結果・実usage・不正タスクなしと、安全な終状態を確認する。人の確認待ちでも反復動作は確認できるが、`analysis_completed`と厳格な`passed`は成功に変えない。

## 2026-11-06 分析エージェント用テンプレート

- 対象作業: `krokharu/transcription-finish-20261102` / `d8707f2` の未コミット実装。既存の未コミット変更を保持し、自律分析の選択画面とAI担当5役へ19種の分析手順を接続した。
- `agent-analysis-templates-1` とIDをrun設定に保存し、旧版runには指示を加えない。選択IDの検査と送信前エラーを設けた。定義は `src/gurumoji/analysis_templates.py`。初回分析などでsystem指示を作り直した後に追加し、LM Studioの入力予算計測に含める。
- 雛形は研究質問、対象・単位、根拠ID、欠測・反例・適用条件、未実施範囲の確認を促す。STC、テンプレート分析、Joint Display、迅速質的分析、遅延逐次分析、クリティカル・インシデント法、QCAを含む。新しい統計計算、研究者の採否確定、jamoviネイティブ形式の生成は実装範囲外。既存CSV/SAV出力の経路は変更していない。
- 検証: 19件の画面ID・定義ID・確認視点の一致、19件×5役の指示生成、未知ID拒否と旧run互換、合成入力で実際のAI system指示への到達、Python AST、`node --check`、`git diff --check`。実モデル応答、実利用者DB/Vault、ブラウザー操作、jamoviの実アプリ取込は未実行。研究上の内容品質は未判定。

### マーラータン保存コピーによる出力確認（2026-11-09）
- 利用者の明示指定により、保存済み323発話のDBコピーと一時アプリ・一時Vaultを使用。元DB・実Vaultへの書込みとクラウド送信は行わない。モデルはローカルGemma 4 12B QAT。
- テーマ分析を既存POST経路で指定。初期の固定・参加量・時間・語彙・数量・内容処理は完了したが、AI呼出し上限16・登録タスク上限24の試行は最終出力なし。5分制限ありでは300.143秒、4呼出し開始でexecution_failure。制限なしでは591.801秒、8呼出し開始でcall_budget_limit。
- 追加調査で停止位置を訂正: 時間無制限の試行は議題生成を完了し、47区間を固定した後、初回専門分析の登録中に停止していた。「区間生成中にcall_budget_limit」は不正確だった。区間生成を無効にした切り分けは1.723秒、呼出し0、登録16件で同じ上限停止。

### 停止原因の照合と合成再現（2026-11-09）
- 実行場所・HEADは `krokharu/transcription-finish-20261102` / `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。調査開始時の未コミット項目101件。主要3ファイルの一時コピーと作業コードのSHA-256一致を確認。保存済み試行はSQLite読取専用、新規の挙動再現は合成323発話・一時DBで行い、追加のモデル呼出しはしていない。
- 試験設定の不足: 前回の実試行はAI上限16・タスク上限24。画面既定は160・400。最初の試行はiterationsモードでtime_limit_secondsを省略したため、サーバ既定300秒も入った。GUIはiterationsモードで明示的にnullを送る。前回は画面と同じPOSTを使っていても、画面既定条件での試験ではなかった。
- 前処理の実態: 使用した古い保存コピーにsource_outlineのsectionは0件。323発話から本体と同じ分割処理で8バッチ（41/40/41/42/40/40/42/37）を生成し、モデル呼出し8回で議題27件を作った。入力幅と未被覆範囲の補完により47区間（generated29・time18、1発話だけの区間7）になった。前処理のusageコールバックは破棄されるため、保存済みusageから各呼出しのtoken・個別時間・応答を検証することはできない。
- 登録方式: `_initial_specialist_intents` は全区間を解釈・独立検証・批判の3担当へ展開するためAI141タスク、Python3タスク。`_run_analysis` は全タスクを登録してから `_drain_tasks` を呼ぶ。`_register` は開始済み呼出しとqueued数の合計で上限を判定し、`_stop` は登録済みqueuedを全てcancelledへ変更する。実試行は8+8=16に達し、登録済み解釈8件が全取消、専門結果0件だった。区間なしも24発話ずつ14ページ×3担当=42呼出しが必要であり、16回では開始できない。
- 合成再現4条件: 47区間・開始済み8・上限16/24は8登録後call_budget_limit、160/24は24登録後task_budget_limit、160/400はAI141+Python3の144件を登録して実行直前まで到達。最後の条件は診断用例外で意図的に停止し、実モデル出力の成功とは扱わない。区間なし・16/24は16登録・開始0でcall_budget_limit。いずれも元の研究本文は使わない。
- 時間停止理由の不具合を別途再現: `_check` は `_db` トランザクション内で `_stop(time_limit)` した直後にExecutionStoppedを送出する。その例外で停止更新・イベントがロールバックされるため、外側の `_run_analysis` がerror=ExecutionStopped・stop_reason=execution_failureで保存し直す。期限切れ合成runで、例外理由time_limit、直後の保存理由は空、ドライバ後execution_failureとなることを確認。最初の300.143秒停止の表示と整合する。
- 判断: 今回の出力不能の直接原因は試験予算不足と全件予約方式。テーマ分析の指示を受けた専門モデル実行まで到達していないため、テンプレート・解釈品質・モデル応答不正を原因と断定しない。画面既定160/400は初回登録を通るが、前処理8+初回141=149呼出しで残り11回となり、後続の尺度設計・レビュー・統合まで足りるかは未検証。19種と必須4手法の実モデル完了・品質は未検証。
- 改善候補: 前処理前と区間確定後の必要予算表示、段階的なタスク登録・不足時の成果保持、区間生成の保存・再利用、時間停止更新の確実なcommit。今回は原因調査のみで実装変更はしていない。集計証拠は一時作業先のdiagnosis-metadata.json、合成再現証拠はdiagnosis-synthetic.jsonに保持。

### 利用者指定1000回上限での実モデル再試行（2026-11-10）
- 利用者の追加指示は「実行してよい、1000回を上限、時間を計測」。前回と同じ保存コピー・隔離アプリ・一時DB・一時Program Vault・ローカルGemma 4 12B QATで、テーマ分析を既存POST経路から新規実行した。runは `run_4dd79644bf154b9f851fa7641b041729`。AI上限1000、タスク上限2000、同時実行1、auto、時間・反復上限なし、1呼出し上限600秒、local_reasoning=off。発話上限24・文字上限6000・区間生成を有効とし、必須4手法（participation、conversation_dynamics、label_frequency、cross_tabulation）を指定。クラウド送信・実Vault公開はなし。
- 時間: JST 11月9日23:33:56.260開始、11月10日00:34:54.696停止。台帳上の実行は3658.436秒（60分58.4秒）。開始要求直前の単調時計からJSON/Markdown取得終了までは3669.366秒（61分9.4秒）。監視は30秒間隔であり、ポーリング検出時刻から算出した3667.782秒を実行の厳密な停止時間とは扱わない。モデルは開始時点で読込済みで、読込時間は含まない。
- 今回の区間生成は22区間となった。前回の47区間は当時の生成結果であり、固定の必要区間数ではない。呼出し90回の内訳は議題生成8、初回専門分析66（22区間×3担当）、Coreによる尺度設計の担当指示8、尺度設計8。初回専門分析66件とPython集計3件はすべて成功。初回要件78件は入力上限で分割され、親7タスクはcontext_requirement_splitとしてblockedになったが、子8タスクは成功した。
- 終状態はstopped / initial_labels_missing。尺度設計は7件受理、1件quarantined / initial_label_definitions_invalid。拒否された出力の2件目がdata_type=number、measurement_level=nominal、recommended_analysis=descriptiveを組み合わせており、`analysis_core.validate_label_definitions` の名義尺度へdescriptiveを許可しない条件（686行）で拒否されたことを、保存応答の再検証で確認した。応答の書換え・再推論による採点変更はしていない。今回は予算不足の停止ではない。
- raw結果85件のうち有効84件・隔離1件、Coreの担当指示8件。統合判断の完了数は0。初回尺度が揃わない場合は全体を停止する現行条件により、尺度レビュー・最終統合・必須クロス集計へ進まなかった。初回集計3件の実行成功を必須手法の評価・Core統合までの完了と読み替えない。
- 出力: JSONとMarkdownのGETはいずれも200、22,735,162 / 22,904,641 bytes。これは未完了・隔離応答を含む全量の実行記録であり、完成したテーマ分析レポートではない。元の発話JSONの前後SHA-256は一致。元DB・実Vault・アプリコードへの変更なし。
- 要求、30秒ごとの計測、全結果、JSON/Markdown出力、summary.json、measurement.jsonはGit除外の `output/validation/template-timed-20261110/run_4dd79644bf154b9f851fa7641b041729/` に保持。19種すべての出力完了・研究内容の妥当性は未検証。今回は指定された上限でテーマ分析と必須4手法の実行を試し、失敗理由と実時間を記録した。
- 利用者の「結果をスライドにまとめて」に対応し、発言本文・個人名を含めない7枚の検証結果資料を作成。保存サービスは作成後の編集が2回ともartifact_executor_unavailableで拒否されたため、空の下書きを片付けてローカルPPTXを納品。完成ファイルは `output/validation/analysis-result-slides-20261110/output/マーラータン分析_実行検証結果_完成版.pptx`。実行時間60分58.4秒・出力取得まで61分9.4秒、90回の内訳8/66/8/8、66専門結果と3集計の完了、尺度7受理・1隔離、最終統合と必須クロス集計の未完了を明示した。
- スライドの表3個・グラフ1個は編集可能なオブジェクトとして保存し、全7ページの画像を確認した。グラフの項目名と数値の対応を修正後に再表示・再検証。Artifact Toolの構造・配置・フォント・再取込・グラフ参照検証とOffice構造検証を通過。PowerPoint実アプリでの表示は未確認。検証用コード・画像・記録は同じGit除外作業先のbuildに保持。

- 2026-11-10追記：利用者の「マーラータンの分析結果をスライドにして」に対応し、保存済み初回所見と発言原文を照合した暫定分析の9枚資料を作成。実行検証資料とは別の内容分析資料として `output/validation/malatang-findings-slides-20261110/output/マーラータンの分析結果.pptx` に保存。個人名を載せず、発言数・観測話者数・単純語数を人数や支持率として扱わないこと、研究者による最終コーディングと音声再確認が未完了であることを明記した。
- 引用候補13件の原文包含を確認し、実際に採用した引用に発言IDを付与。編集可能な表2個・グラフ1個を使用し、全9枚の描画を目視確認。改行修正後の再描画、Artifact Toolの構造・配置・フォント・再取込・グラフ参照検証、およびOffice構造検証を通過。PowerPoint実アプリでの表示は未確認。生成コード・画像・照合記録は同じGit除外先のbuildに保持し、実DB・実Vault・アプリコードへの変更なし。研究者の発言本文・個人名・具体的所見は本ノートへ転記していない。
- 2026-11-10追記：利用者の分析手法明記の指示により、既存資料を読み込み、質的・量的それぞれの手順、集計式、結論と根拠発話・判断手順の対応を加えた13枚版を作成。成果物は `output/validation/malatang-findings-slides-20261110/output/マーラータンの分析結果_分析手法付き.pptx`。質的分析はAI支援の探索的テーマ整理、量的分析は記述集計・簡易語彙頻度と明記。全発話コーディング・研究者間一致度・飽和判定は未実施、支持率・因果効果・統計的有意差は結論に用いないことを可視化した。
- 保存入力から対象発話数・話者ラベル数・最大終了時刻・掲載6語の出現回数を再計算して保存値との一致を確認。元グラフの部品・関係定義・埋込ワークブックを元と同一バイト列で保持。全13枚を描画して確認し、追加注記と表の間隔を修正後に再確認。構造・配置・フォント・再取込・グラフ参照とOffice構造の検証を通過。PowerPoint実アプリでの表示は未確認。原資料は保持し、実DB・実Vault・アプリコードへの変更なし。検証コードと詳細記録はGit除外先buildに保持し、研究者の発言本文・個人名・具体的所見は本ノートへ転記していない。
- 2026-11-10追記：利用者のスライド構成修正指示により、全11枚を再構成。各内容ページに分析区分と図表から読める知見のタイトル、実施手法、図表、読み取りを配置。量的3ページは記述統計・簡易語彙頻度・時間区分別頻度、質的5ページは意味の要約と対照比較、その他2ページは相互作用の文脈確認・結果統合と分類。編集可能なグラフ3個、表6個、関係図2個を作成。成果物は `output/validation/malatang-findings-slides-20261110/output/マーラータン分析_図表と分析手法.pptx`。
- 既存の保存コピーだけから匿名話者集計・時刻差の合計・3等分区間の語彙頻度を再計算し、件数と語の区間合計を照合。図に使う引用部分を原文に照合し、相互作用図は同一発話内の明示的な自己説明だけを使用。支持率・代表性・因果効果や正式な研究者コーディングを主張しない。全11枚を描画確認し、不自然な改行を修正。最終版の構造・配置・参照フォント・再取込・ネイティブグラフ参照とOffice構造の検証を通過。PowerPoint実アプリ表示は未確認。最終納品コピーと検証済みファイルのSHA-256一致を確認。前版を保持し、実DB・実Vault・アプリコードへの変更なし。生成コード・照合記録はGit除外先build/visual-redesignに保持。研究者の発言本文・個人名・具体的所見は本ノートへ転記していない。
- 2026-11-10追記：利用者の「調査した量的可視化をテンプレートへ組み込み、まずクロス表とカイ二乗を可視化」に対応。実行場所はメインチェックアウト、ブランチkrokharu/transcription-finish-20261102、HEAD d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486。無関係な未コミット変更は保持。既定スライドテンプレートを2.1.0、分析エージェント雛形をagent-analysis-templates-2、研究分析をresearch-ja-6へ更新。旧agent-analysis-templates-1の指示を維持。選定指針へ語彙頻度・ヒートマップ・共起・対応分析・分布・関連等を追加したが、この版で新規実装した専用可視化はクロス表とカイ二乗の残差図であり、全候補の実装完了を意味しない。
- 新規analysis_contingencyは整数度数、周辺合計、期待度数、行割合、Pearson残差とχ²寄与、χ²・自由度・参考p・CramérのV、独立性と期待度数基準を別項目で固定する。推測条件を満たさないp_valueはnullとしreference_p_valueを分ける。すべての有効期待度数5以上を保守的基準と明記。スライド側は保存された専用結果だけを投影し追加検定しない。既存SQLカラム・CSV列の変更なし。設計6ファイルの版とカタログのindex/part hashを再照合。大きい表・長文は既存の完全な文字fallbackと重大留保チェックへ戻す。
- 合成度数のみの隣接・統合・既存回帰試験31件を実行して成功（test_contingency_visualization、test_analysis_slides_visuals、test_analysis_slides_generation、test_research_analysis）。一時Vault/DBを使用し実利用者DBは試験に使っていない。SciPy照合、寄与和、ゼロ周辺度数、非整数拒否、独立性未確認・低期待度数の保留、旧テンプレートの互換、保存結果のネイティブ表出力を確認。Windowsの既存CRLFを考慮しgit -c core.whitespace=cr-at-eol diff --checkを通過。ブラウザーUI、起動中アプリへの反映、PowerPoint実アプリ表示は未確認。
- 保存済みコピーを用いた利用者指定の実分析を別途実施し、クロス表・行割合・残差・期待度数の4枚を `output/validation/malatang-findings-slides-20261110/output/マーラータン_クロス表とカイ二乗検定.pptx` に出力。観測単位と対象語の定義を明示し、今回の推測条件未達を参考計算・判断保留として可視化。元result.jsonの前後SHA-256一致を確認し、元run・DB・実Vaultを変更していない。編集可能な表3個とグラフ1個、全4枚の描画確認、構造・配置・フォント・再取込・グラフ/埋込ワークブック参照・Office構造の検証を通過。図表・計算・根拠ID対応・生成コードはGit除外先build/crosstabに保持。研究者の本文・個人名・実分析の具体的数値はこのGitノートやテストfixtureへ転記しない。