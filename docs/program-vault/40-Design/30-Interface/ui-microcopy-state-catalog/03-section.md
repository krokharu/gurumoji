---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-microcopy-state-catalog-section-03
title: Gurumoji 日本語UI文言と状態の仕様案：4 現行25箇所の変更候補
summary: 4 現行25箇所の変更候補。出典ノート「Gurumoji 日本語UI文言と状態の仕様案」の分割本文。
parent_note_id: design-ui-microcopy-state-catalog
source_path: 40-Design/ui-microcopy-state-catalog.md
source_sha256: a380e655813a51346e817cb6f36f5fea46e2e56045e8019aa10d9ef5c0b64d29
source_body_lines:
- 71
- 106
split_on: '2026-10-11'
---

# Gurumoji 日本語UI文言と状態の仕様案：4 現行25箇所の変更候補

親索引・状態・確認版：[[40-Design/30-Interface/ui-microcopy-state-catalog/00-Index]]。必要な本文だけを取得する。

## 4 現行25箇所の変更候補

### 表の読み方

「現行」は実際の文字列または動的書式の抜粋。提案は表示条件と一体で採用する。表内のファイル名は特記がなければ`app/src/gurumoji/`相対。行番号は上記HEADのもの。括弧内のIDは関連作業。

変更区分は、**表示**＝既存事実の言い換え、**条件**＝分岐・操作の整合が必要、**契約**＝APIや保存・実行の改善後に限り使える文言、の3つ。表示区分でも通常画面の受入は必要。

| IDと現行文字列 | 提案する短い日本語 | 表示条件 | 許可する操作と約束の限界 | ソースと区分 |
|---|---|---|---|---|
| J01「設定・手動分析」「設定・手動」 | 「設定・コード付け」 | 設定、コード、研究者記録を編集するモード | モードを切り替えるだけ。自動計算・測定実行を暗黙に開始しない | `templates/views/analysis.html:111–129`。表示、W07 |
| J02「自動実行」「手動実行」 | 「基礎集計」「測定を追加」 | 同じ基礎集計に測定定義を足す選択 | 現行の規則を接続するまでは補助文「現在は発話の文字数を測定します」。自由記述で任意測定できると示さない | `templates/index.html:240–249`、`static/analysis-execution.js:50–64,95–107`。条件、W02 |
| J03「測定方法を入力してください。」／欄名「説明」 | 「測定の説明を入力してください」＋「説明文は計算規則を変えません」 | 説明欄が空、または説明を編集中 | 対応規則を別欄で確認する。名称「発話時間」だけでdurationへ変わると扱わない | `static/analysis-execution.js:85–90`、`templates/index.html:246`。表示、W02 |
| J04「開始」「固定計画と少数試行を確認しています。」 | 改修後は「少数の発話で試す」→「この定義を採用」→「全件で実行」 | 各操作が分離され、試行時の内容との一致を確かめられた状態 | 現行に文言のみ適用不可。現行処理のままなら「試行・採用して全件実行」と実態を明示する暫定策まで。レビューを挟んだと主張しない | `templates/index.html:271`、`static/analysis-execution.js:542–599`。契約、W02 |
| J05「試行 {n}件：有効{v}件・欠測{m}件。外部送信なし。」 | 「{n}発話を試行：算出{v}・欠測{m}」＋「除外後の先頭{n}発話」 | trial応答成功。nは実際のsample_size | 詳細値は現responseのvalues範囲のみ。発話別リンク、具体的欠測理由、試行した定義版はresponse拡張後。欠測0と未取得を区別 | `static/analysis-execution.js:550–552`、`analysis_pipeline.py:129–145,258–280`。表示＋契約、W02 |
| J06「結果を公開する」 | 「設定済みのVaultにも保存」 | checkboxは3先の配列を送るが、ONの処理はResearchVaultも扱う | Research／Input／Orchestrator／Visualizationを説明する。OFFは本体ファイル保存のみの経路で、Vault書出し工程を省略。3先のpayloadだけから実保存先を判断しない | `templates/index.html:268`、`static/analysis-execution.js:570–578`、`analysis_pipeline.py:476–482,583–588,620`、`app.py:1578`、`analysis_store.py:588–697`。条件、W03 |
| J07「公開だけ再試行」 | 「Vaultへの保存を再試行」 | `retry_publication`が返り、対象と結果が分かる | 保存済み結果から既存の保存処理を再実行。現publisherは保存先scopeを受け取らないため「失敗したVaultだけ」と限定しない。再計算・外部AIを同時実行しないことを受入で確認。成功を先取りしない | `static/analysis-execution.js:464–466,620–631`、`analysis_pipeline.py:620–631,847–881`、`analysis_store.py:588–697`。条件、W03 |
| J08「選択した成果物の保存と公開を確定しました。」 | 「分析が完了しました」＋「結果ファイル：保存済み」「{Vault名}：保存済み／対象外／未完了」 | 実行completedと各保存先status・保存の選択を取得済み | 3先はpublications、ResearchVaultはresult_runのvault_statusを別照合。OFFで工程省略ならResearchVaultのpendingを失敗にせず「対象外」。全体completedだけで4先成功としない | `static/analysis-execution.js:428–437`、`analysis_pipeline.py:476–482,737–750,797–812`、`analysis_store.py:689–697`。条件、W03 |
| J09「分析を実行しています」 | runningは「分析中」、failedは「分析が停止しました」、acceptedは「開始待ち」 | 取得した全体statusの厳密な分岐 | failedへ動くspinnerや残り時間を残さない。既知の保存済み結果は別に案内。見出しとchipの意味を統一 | `static/analysis-execution.js:435–437,475–476`、`templates/views/analysis.html:51`。条件、W03 |
| J10「分析を再開できます」 | 「分析が待機しています」＋「{確認できた待機理由}」 | status=waiting | 実際のallowed actionで主操作を決める。再試行を許可されない待機に「再開」を置かない | `static/analysis-execution.js:436,464–466`、`analysis_pipeline.py:823–831`。条件、W03 |
| J11「失敗した処理を再試行」 | `retry_failed`ありは現行文を維持、それ以外は「実行設定を見直す」 | waiting／failedのreviewボタン | 現行failedでは設定へ進む。新規分析と同じ実行の再試行を混ぜない | `static/analysis-execution.js:464–466,620–631`、`analysis_pipeline.py:823–831`。条件、W03 |
| J12「中止を待っています…」「分析を中止しました」 | 送信中「中止を依頼しています」／受付後「中止の完了を待っています」／cancelled「分析を中止しました」 | 送信前後の局所状態、cancelling、cancelledを区別 | 重複中止を防ぐ。失敗応答・timeoutなら「中止の受付を確認できません」。前回保存を確認できたもの以外の保持を約束しない | `static/analysis-execution.js:460,602–617`、`analysis_pipeline.py:833–845`。条件、W03 |
| J13「状態取得失敗：{error}」 | 「最新の実行状態を確認できません」＋「最後の確認 {時刻}：{状態}」 | polling失敗、または未知のstatus | 通信の問題として示す。停止・成功へ変更しない。段階2-1（2026-10-12）でGETを読取専用へ変更。再起動後は許可操作`resume`による「固定入力から分析を再開」だけが処理を再開し、待機中の反復取得を止める | `static/analysis-execution.js:analysisExecutionPoll/analysisExecutionReviewPlan`、`analysis_pipeline.py:status/resume`。条件、W03/04 |
| J14「結果を見る」 | 現行動作なら「現在の分析画面を開く」。固定viewer完成後は「この実行の結果を見る」 | 前者は現在itemを再読込、後者は同じrunのartifactのみを読む | 未実装の固定viewerへ言葉だけ先行させない。保存済みrunを取得不能なら現在値で埋めない | `templates/views/analysis.html:79`、`static/analysis-execution.js:651–656`。表示／後者は契約、W04 |
| J15「分析結果をObsidianに保存」 | 「分析結果を保存」＋「Gurumojiの保存先と設定済みVaultに保存します」 | archive保存。実際の保存先を表示できる | 端末のObsidianが開く／閲覧端末に保存されるとは保証しない。ResearchVaultと生成Vaultの成否を分ける | `static/analysis-storage.js:12–23,102–114,132–139`。条件、W03 |
| J16「分析結果とVaultを保存しています…」「分析結果とVaultを保存しました。」 | 「分析結果を保存しています」→「結果ファイル：保存済み」＋保存先別状態 | busyは処理中。完了は各実際の応答 | ネットワーク不明なら「保存結果を確認できません」。本体保存・ResearchVault・その他3Vaultを1つの成功文だけで表さない | `static/analysis-storage.js:33–36,108–118,132–156`。条件、W03 |
| J17「別の画面または処理でデータが更新されています。未保存内容をJSONで退避してから再読み込みしてください。」 | 「別の更新があるため保存できません」＋「未保存内容をダウンロードしてから、最新の内容を開いてください」 | 発話編集の409。現在の退避機能が使える | 退避形式JSONをボタンまたは補助文に表示。今の編集を自動上書きしない。定義編集へ流用するなら退避機能は別途必要 | `static/app.js:5657–5665`、退避説明`2136`。表示、W03 |
| J18「保存できませんでした。」 | 確定した拒否は「保存できませんでした：{原因}」。応答不明は「保存結果を確認できません」 | HTTPによる拒否と、応答を受け取れない場合を区別 | 現在の編集を残して次手順を示す。「変更は失われていません」は現在draftの存在を確認した場合だけ。保存開始後の追加編集を消さない | `static/app.js:5657–5688`、`static/analysis-storage.js:94–118`。条件、W03 |
| J19「更新が必要」 | 「保存後にデータが更新されています」 | run.stale=trueを照合できた | 古い結果を閲覧できるなら保持。未照合・取得不能は「現在のデータとの一致は未確認」。stale=falseの欠落を「最新」と読まない | `static/analysis-storage.js:43–47`、`analysis_store.py:315–317`。条件、W04 |
| J20「保存済みファイルが見つかりません。」「保存ファイルが移動または変更されています。」 | 「保存ファイルを開けません」＋404「ファイルを確認できません」／409「保存時と同じファイルか確認できません」 | artifactの実際の404／409。詳細原因は分かる範囲のみ | 同runの別ファイル・履歴へ戻る入口。アクセス権不足、利用者削除、全結果消失とは断定しない。現在結果へ置換しない | `analysis_store.py:304–312`、`web/analysis_routes.py:46–72`。条件、W04 |
| J21 根拠の時刻「{start}–{end}」、欠けた時刻も0秒表示 | 有効な両時刻は現行形式、欠けた場合は「時刻不明」 | null／空値／time_unknown／非有限値等を判別後 | 0は正しい時刻でもあり得るためtruthy判定禁止。欠測時は自動seekしない。見つからない根拠IDは黙って省かず「根拠{ID}を確認できません」 | `static/analysis-content.js:45–64,86–105`。条件、W04 |
| J22「ファイル選択済み・開始前の確認が必要です」「開始時にモデルを読み込みます」 | blockerあり「開始できません：{必要な準備}」／条件充足「開始できます」＋残るモデル読込条件 | createReadinessのblocker・acknowledgementを個別評価 | ファイル選択だけでreadyにしない。モデル取得・許諾・権限・読込成功を既成事実にしない。安全設定を緩める案内をしない | `static/app.js:841–893`、`templates/views/create.html:501`。条件、W00 |
| J23「未取得。開始時に配布元からダウンロードされます」「選択した認識モデルの取得状況は未確認です」 | missing「モデルは未取得です。開始時に取得を試みます」／unknown「モデルの取得状況を確認できていません」／cached「モデルファイルあり。読込は開始時に確認します」 | missing／unknown／cachedを取得した通り表示 | missingとunknownを区別。取得完了・権限OKを保証しない。追加取得の配布元・条件の確認と必要な承認は省略しない | `services/transcription_readiness.py:27–35`、`static/app.js:855–862`。表示、W00 |
| J24「LM Studioを選ぶとこのPCのローカルLLMだけで処理します。」「Transformer（このPC）」 | AI見解「送信先：{サービス／設定された接続先}」「送る内容：発話・話者情報・研究質問・分析用の付与情報」／Transformer「Gurumojiの実行環境」 | providerと実際の接続先を確かめた各操作 | 付与情報は役割・コード・重要フラグ。専門家設定があれば短い説明・手順も含む。LM Studioは設定先であり閲覧端末とは限らない。資格情報を表示しない。見解はAI下書き | `static/analysis-content.js:174–194`、`static/analysis-execution.js:151–153`、`services/analysis_jobs.py:224–230`、`analysis_insights.py:307–354,397–403`。条件、W01/03 |
| J25「原文は送信しません。クラウドを選ぶと分析目的・集計件数・手法カードを送ります。」 | 「{送信先}に、入力した分析目的・集計件数・手法の説明を送ります。発話本文は自動で含めません」 | 計画候補生成のproviderが選択済み | 分析目的に利用者が貼った本文も送られるので「原文は送らない」を無条件保証しない。目的に機密情報を入れない注意は該当時に近接表示。生成は全件分析の開始ではない | `templates/index.html:251–263`、`analysis_plan_advisor.py:60–74,142–153`、`static/analysis-execution.js:198–231`。表示、W03 |
