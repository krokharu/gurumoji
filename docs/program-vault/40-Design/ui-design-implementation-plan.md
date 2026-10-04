---
note_id: "design-ui-implementation-plan"
note_type: "implementation-plan"
title: "Gurumoji UI改善の実装計画"
summary: "設計資料v0.4の作業用正本。設計提案の採用・アプリ実装・UI受入は未完了。"
status: "proposed"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
review_repository_head: "88f5e3eea245166ee68ed4dc6c3f99c31e149228"
tags: ["gurumoji/design", "gurumoji/ui"]
---

# Gurumoji UI改善の実装計画

第4稿 0.4 · 2026-10-02 UTC · 実装承認前の計画  
確認HEAD `88f5e3e`（0.3設計文書統合）／ソース基準 `ddc23abe`・実装 `59ebd24`。本0.4更新はSoftware Vault内の文書差分で、コード変更・push・deploy・実データ移行を含まない。

## 1 結論と根拠の扱い

**先に既存の処理を正しく使えるようにし、その後で作業目的に沿った配置を試す。** P1はDG-01の可視入口とDG-02の測定意味・定義版の整合。DG-02はUIだけで完了しない。追加の文言監査で、保存targetと実書出し経路の不一致も確認したため、W03のscope対策をP1候補として先行判定する。IAや外観の改善効果は仮説であり、これらの修正条件にしない。

DG番号は[監査対応表](../50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md)。UX:S番号は[UX出典台帳](ui-design-research/2026-10-02/ux-source-ledger.json)、PR:番号は[プロンプト出典台帳](ui-design-research/2026-10-02/prompt-source-ledger.json)。文献は設計理由、ソース／probeは現行事実、実操作は受入を支える。それぞれ代用しない。

原25件の **15 addressed / 10 UI partial / 0 open** は[元受入表](../50-Tests/ui-design-evidence/2026-10-02/prior-25-acceptance-matrix.md)で維持する。今回14項目は新規不整合、既知課題、設計提案、旧画像由来の仮説の混在であり、「新規14バグ」と集計しない。

## 2 優先順と依存

工数は対象コードを読んだ概算の実作業量。1人の実装＋局所確認を想定した人日で、モデル取得、環境接続、Windows／AT待ち、利用者募集を含まない。合計を納期約束に使わない。

| 作業 | 根拠／種別 | 優先 | 概算 | 期待する影響 | 依存 |
|---|---|---|---|---|---|
| W00 現行能力・証拠を固定 | DG-13／文書不一致 | 前提 | 0.5日 | 未実装の二重開発と誤案内を防ぐ | なし |
| W01 個別実行入口を戻す | DG-01／確認済み不整合 | P1 | 2〜3日 | 主要分析を通常操作で開始できる | W00の能力表 |
| W02 測定定義を試して採用 | DG-02／確認済み不整合 | P1 | 5〜9日 | 名称・採用版・実計算の不一致を防ぐ | W00、definition／実行境界 |
| W03 状態と保存先を揃える | DG-03/11＋追加契約probe／不整合＋文言 | scope対策P1候補／表示P2 | 表示1〜2日、保存契約は再見積 | 待機・失敗・保存範囲の誤認を防ぐ | W00、publisher契約。W01/02と並行可 |
| W04 版と根拠の往復を示す | DG-06/12／設計提案 | P2 | 2〜4日 | 過去runと現在入力の取り違えを抑える | W03の状態語彙 |
| W05 目的名・contrast・focus | DG-09/10／コード＋指定色 | P2 | 1〜2日 | 中心操作の認識・操作性を改善 | W00。局所箇所は並行可 |
| W06 履歴の上限と全件導線 | DG-04／既知UX-34 | P2 | 表示0.5日、paging1〜3日 | 古いrunを発見できる | W04のrun文脈 |
| W07 タスク別入口を試作 | DG-05／ADR-118未実装 | P2 | 5〜10日 | 次の仕事を予測しやすくする仮説 | W01〜04、W06の一覧契約 |
| W08 日本語密度と狭幅を調整 | DG-07/08/14＋12／混合 | P2/P3 | 2〜4日 | 長文照合・現在地の読み取り改善仮説 | 現行描画取得、W05、対象画面安定 |
| W09 横断受入と記録 | 全体／回帰と引継ぎ | 各段階 | 1〜3日＋環境待ち | 原25件と科学的保護の維持 | 各Wの実装・対象版固定 |

W01→W02の直列固定は不要。template／analysis-execution.jsの同時編集は担当範囲と取り込み順を調整する。W07は低忠実度の構成比較を先に行い、全機能の新UI化を一括発注しない。

## 3 作業単位の実装契約

### W00 現行能力を短く固定する

- 文書同期の進捗（2026-10-02）: `ui-screens.md`の上部4入口、M0〜M7永続pipeline、初回能力の限定をコード照合して更新済み。入口→handler/API→capabilityの対応表と可視入口の受入は残るため、W00全体の完了にはしない。日付付きDG-13の監査snapshotは当時の観測として維持する

- 対象: `analysis_core.py:80–100,311–338`、`analysis_pipeline.py`、`analysis-execution.js`、Software Vaultの`ui-screens.md`とマイルストーン設計
- 作業: 基礎pipeline、個別Transformer／見解／分類、O01計画相談、固定package出力を別行にした能力表を作る。M0〜M7は既存のサーバー永続処理と明記する。旧6段階／client逐次説明を同期する
- 境界: 47成果物・7役割・全推測統計を既に使えるとも、永続化が未実装とも書かない。通常分析のXLSXとpipeline固定packageのXLSX未提供を分ける
- 合格: 各可視入口→handler/API→capability→説明先を一対一で追跡。unsupportedには理由、案内する画面には入口が存在する。コードと文書差分のリンクを確認
- 依存／出典: DG-01/13、ADR-118、PR:T1/PR:T4
- 戻し方: 文書差分のみ戻せる。能力表を新しい実行エンジンにしない

### W01 個別分析の実行と案内を一致させる

- 対象: `style.css:2088–2093`、`analysis-content.js:184–188,561–568`、`analysis-method-view.js:254–264`、`app.js:6760–6769`、`index.html:236`
- 推奨: 既存の個別controlを各結果panelで可視・操作可能に戻し、見解が概要にある現構成なら案内を合わせる。見えなくした全selectorを機械的に復活させず、取消・provider・表示条件を確認する
- 送信表示: AI見解は「発話・話者情報・研究質問・分析用の付与情報」と短く示し、詳細に話者名／役割、コードID・label、重要フラグ、専門家設定時の短い説明・ID／版・手順／根拠IDを含める。本文だけの送信と説明しない。LM Studioも設定された接続先であり、閲覧端末の「このPC」と決めつけない。実prompt captureとの照合を受入に含める（[文言仕様](ui-microcopy-state-catalog.md)J24、[合成probe](../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-probes.json)）
- 代案: 共通確認panelから既存handlerへ送る。将来IAと揃うが、対象版／dirty guard／送信要約／取消／二重送信を再結合するコストがある。対応runnerのない基礎pipelineへ統合したふりはしない
- 合格: シナリオS01。通常一覧からのpointerとkeyboardで3入口へ到達し、visible/enabled・実矩形・production CSSを確認。route spyで正しい対象／provider／APIが1回。dirty、連打、取消対応のある処理の中止、条件不足も検証
- 可視化前のhandler gate: 分類のA要求を保留してBへ移ると、Aの遅い応答がBの表示へ入ることを[隔離probe](../50-Tests/ui-design-evidence/2026-10-02/classification-late-response-probe.json)で再現した。要求時item／入力・分析revisionを保持し、応答時の表示対象／版と照合してからstateと通知へ反映する。不一致ではBを変更せず、Aの保存済み結果は後で正規読取する。通信abortだけでserver処理の取消と見なさない。現行はCSS-hiddenのため通常UI発生済みとは呼ばないが、入口復旧の必須回帰に含める
- 能力の限定: 取消を確認できたのはTransformer／AI見解。分類は`analysis-method-view.js:312–347`のPOSTで、同じ取消handlerは確認できていない。3入口一律の中止を提供せず、分類の遅延responseと対象移動の保護も別に試験する
- 既存試験: `test_content_browser.py`、`test_transformer_content_browser.py`等のhandler試験を保ち、可視入口の試験を追加。hidden要素のJS clickを可視受入に数えない
- 出典: DG-01、反証H1、UX:S01/UX:S12/UX:S22、PR:T7/PR:T10
- 移行／rollback: 保存schema不要。入口adapter単位で戻せるようにする。問題時は旧の非表示状態を正当化せず、利用不可の理由と保存済み結果の入口を明示する

### W02 手動測定を意味の確認から採用へつなぐ

- 対象: `index.html:243–249`、`analysis-execution.js:50–64,542–557`、`analysis_core.py:151–198`、`analysis_pipeline.py`の定義保存／試行
- 推奨: backendが対応する入力列・規則・型・尺度・手法をUIへ接続する。まず文字数、duration、カテゴリの度数等の検証済み組合せを説明付きで提示し、詳細選択は実validatorの制約と合わせる。独自の許可組合せを推測しない
- 必須の小さいAPI拡張: 現行`trial_definition:258–280`は`values[:20]`と件数・`input_hash`を返すが、発話ID・欠測行／理由・定義revisionを落としている。既存values／件数を保ち、`measure_segments`が持つrowsと欠測理由、試行した定義revisionをresponseへ追加する。現在の本文から有効値の発話対応を推測しない。入力hashは既存値を利用し、新しいfingerprint体系を作らない。rowsだけにも元の本文／時刻はないため、同じtrial snapshotから測定に用いた入力値を上限付きsampleとして返すか、その固定入力への参照を返す。現在本文とのjoinは禁止。保存するsampleの範囲・サイズ制限は契約レビュー事項で、再open時に固定入力を復元できない古いtrialは再試行を案内する
- 採用の区切り: 試行の個票・要約・欠測理由→明示採用→全件実行。定義revisionと入力版が試行時から変われば再試行を要求するか、確認無効を明示する。Close／Cancelで意図せずadopt/pipelineを送らない
- 表示と失効: 試行した定義版・入力版、全体／除外／試行数、欠測と真の0、測定の限界を採用前に短く示す。編集後は古い試行を履歴扱いに下げ、確認と採用を無効にして再試行を主操作へ。変更field・未保存内容・focusは保ち、補助storyboardのために編集面全体を置換しない。欠測行の確認linkは発話IDを含む名前を持ち、固定試行入力を開く。採用応答不明では成功を推測せず正式状態を再確認する（[静止批評](../50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md)MC-01/03/04/05。描画上の補強であり動作は未検証）
- 既採用版の保護: `analysis_definitions`はitem＋definition IDごとの1行で、draft PUTも旧adopted payloadを上書きする。第1段階は既採用を直接編集せず別draft IDに複製し、採用時に新IDを選択する案を推奨。旧IDとの関係表示を設計し、将来の版履歴schemaへ暗黙に広げない。取消時は未採用draftとして残す範囲を示し、旧payloadへの逆PUTで並行更新を巻き戻さない
- 小さい代案: 現行を「文字数測定」と明示し、text／text_length／number／ratio／descriptiveを読み取り専用表示に限定する。即時の誤認抑制には有効だが、既存APIのduration等はUIから使えない。採用確認は省略しない
- API判断: 第1段階は既存draft/adoptedを利用。採用PUTでもrevisionが増えるため、試行した内容の版rと、同内容を採用した版r+1の対応を示す。画面変更があれば内容を比較し直し、単なるstatus更新を別の測定内容と混同しない。クライアントの『試行レビュー済み』を永続保証と呼ばない。サーバーでレビューgateを保証するなら、definition revision＋入力fingerprint＋trial IDを結ぶ追加契約を別レビューし、既存client互換と旧adopted定義の扱いを決める。上記5〜9日は画面2〜4日＋backend契約／競合回帰3〜5日の概算。人のレビューを永続保証するserver gateは含めず、契約設計後に追加見積りする
- 合格: シナリオS02。受付後に定義を変えても固定内容で実行するか、理由付きで安全停止し、異なる値を正常確定しない。本文3/10文字・実時間60/2秒の対照で、選んだdurationは60/2、文字数は3/10。名義尺度への平均は拒否。明示採用前はadopted PUT/pipeline POSTが0回。編集／対象変更／revision競合後の古い試行を採用しない
- 出典: DG-02、反証H3＋[定義lifecycle probe](../50-Tests/ui-design-evidence/2026-10-02/definition-lifecycle-probe.json)／[全pipeline合成probe](../50-Tests/ui-design-evidence/2026-10-02/definition-full-pipeline-probe.json)、UX:S01/UX:S05/UX:S15/UX:S17、PR:T11。採用UIが研究の妥当性を保証するとの主張はしない
- 必須の実行境界対策: `_run:635–643`はbinding記載versionでなく現行IDを再読する。`definition-lifecycle-probe.json`は受付binding v1→同IDのduration v2→実測定60秒（v1なら3文字）を隔離再現。`definition-full-pipeline-probe.json`は元の_runをM0〜M7 completedまで実行し、保存adapterにbinding v1／definitions v2／値60が混在することも確認した。合成adapterによる試験で、実ディスク保存・GUIは未試験。最小修正は版／内容不一致で安全停止し、最新定義へ自動置換しないこと。推奨の本対応は、受付時に採用定義の完全なpayload・版・hashを固定して実行／再開／保存で同じ内容を使うこと。人のレビュー確認gateとは別に必須とし、UIの完了条件から外さない
- 旧runの扱い: 固定payloadのない既存待機runは一致を証明できる場合だけ進め、不一致・不明を現行定義で埋めない。安全停止案は変更後の継続性が下がるが誤計算を止められる。snapshot案は元定義で再開できる一方、契約version・旧run互換・原子的な固定の追加試験が必要。完了済み成果物は再計算・来歴の書換えをしない
- 移行／rollback: 旧定義やrunの再計算・自動改名なし。既存adoptedは『過去の定義・確認記録不明』等、取得できる来歴だけ表示。追加metadataを入れた場合は旧reader互換を試し、rollbackで新定義を削除しない

#### W02 保存とrollbackの提案契約

以下は**新設する契約案で、現行実装ではない**。最小の版不一致停止を先行し、本対応はこの境界を満たしてから有効にする。

- 保存先は既存`analysis_pipeline_requests.binding_json`を拡張する。`resolved`を残し、`definition_snapshots`にIDごとの採用payload／version／canonical hashを保持する案。別DBやmutableな定義参照を正本にしない。新contract versionとbinding hashの対象へsnapshotも含め、入力snapshotと区別する
- 受理境界は単にJSONを同時INSERTすることではない。同じ受理transactionでdefinitionを読取り、expected version／採用状態を再確認し、payloadとhashを固定してplan／binding／input snapshotと保存する。previewと受付の間の更新は409。別connectionを開く現`_definitions`をそのまま呼んで原子的とみなさない。workerは確定payloadのみを検証・計算・再開・保存へ渡す
- 旧manual runに固定payloadがない場合は、現在値から旧版を復元したふりをしない。再開は既定で止め、旧成果を保持し、現在の定義から別runを作る判断へつなぐ。定義を持たない旧automatic runは別の互換fixtureで検証する。completed成果物は変更しない
- 旧workerは未知のbinding field/versionを安全に拒否せず、最新IDを読み直す。したがって**新形式を保存した同じruntimeへ旧binaryを直接戻すrollbackは未承認・未検証**。通常の戻し方は安全性修正を残すhotfix版へのUI撤回。旧binaryが必要なら別途互換計画と一時DBでの試験を完了するまで起動しない
- compat guardはDB初期化／回復より前に必要。現`handlers/application_lifecycle.py:43–49`はOS lock後にinitialize、`services/library_schema.py:387`からpipeline初期化がactiveをwaiting/interruptedへ更新する。OS lockは複数processを防ぐが、同processのHTTP／worker並行実行まで直列化しない
- 互換検査はpending数だけで判定しない。`retry:847–899`が扱うfailed/interrupted/cancelledを含む全非completed新形式runと再開可能attempt、definition row、新artifactを対象にする。backup取得・guard・全対象の分類・復元dry runが揃うまで全アプリdowngradeは停止条件。復元で後続の研究者編集を消さない

必要な追加受入は、受理直前／直後の並行編集、複数HTTP、restart/retry、旧manual／旧automatic／新形式の3種読取、旧worker起動前guard、artifactのbyte/hash保持。保存field名とcontract versionの最終採用、実DB dry run、実worker互換は未実施であり、この文書の追記では解決済みにならない。

### W03 実行状態と実際のVault書出しを一致させる

- 対象: `analysis-execution.js:393–476,602–636`、`index.html:267–268`、`analysis_pipeline.py:476–482,583–588,607–632,737–750,823–831`、`analysis_store.py:175–209,588–697`、`app.py:1562–1582`
- 表示: accepted／running／waiting／failed／cancelling／cancelled／completedを同じ表示mapから出す。failedのallowed_actionsは現行で空なので、設定画面を開くreviewを「再試行」と呼ばない。中止の送信中・受付済み・完了と、通信取得失敗を別にする。同状態pollでは通知を重ねず、保存成功後の追加編集は未保存のまま示す
- 確認した保存境界: API enumと台帳は3生成先だが、非空targetsは`store.publish(run_id)`へ渡り、選択を渡さず3生成先＋ResearchVaultを試みる。inputだけの指定でも他2先はnot_selectedと記録され、Research conflictでもcompletedになった。元M0〜M7＋元store.publishと合成adapterによる[probe](../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-probes.json)であり、実Vault書込みやGUIでの発生確認ではない。通常UIは全3先ON／空OFFのcheckboxで、部分指定はAPI条件として区別する
- 直近のguard案: 当面は空配列、または正確な全3先集合だけを許し、ONはResearch込み4経路の一括保存と説明する。部分集合はwriter前に明示4xxで拒否し、Researchをenumへ無断追加しない。現APIは部分指定を受理するため、contract versionと既存client／再試行の互換試験が必要。全4先成功は各結果の照合まで表示しない
- 完全対応のgate: requested targetsと実際の保存先集合を受理時に固定し、各writerへscopeを渡す。Researchの選択規則も明示し、対象外writerは呼ばない。run／attemptごとに各先のrequested・実行有無・成否／競合／不明を記録し、取得不能を成功やnot_selectedへ変換しない。3先台帳だけで4先の完了を判定しない。旧completedは3先gateの履歴として保ち、新しい4先成功へ遡及変換しない。本体・各先の結果とnote policy上のmissingを別表示し、publishedを全ノート存在の保証にしない。研究者の削除を再作成して見かけの成功にしない
- 再試行のgate: 表示した範囲だけのwriterを再度呼び、保存済み固定packageを使う。計算・外部AIや未対象先を起動しない。Research conflictでも既存保存履歴の「保存済み結果から再試行」→`POST /api/analysis/runs/<run>/vault`→`AnalysisStore.retry:447–451`は全保存工程を再訪できるので、範囲を示して再利用する。OFFで未実行のrunもpendingからこの入口が出るため、その場合は「Vaultにも保存」と新たな保存範囲を明示し、失敗した処理の再試行とは説明しない。pipeline completedの新しい再試行action、Researchのみ等の部分再試行は別契約。Researchのみ失敗・generated先のみ失敗・再起動後の不明を分けて試験する
- 合格: S03で空・全3・部分集合、各先の成功／競合／失敗／不明をstubに注入。空はこのpipelineの全Vault callbackが0回、未対象writerも0回。要求→有効保存先→writer trace→返却outcome→台帳→画面が一致する。全3成功＋Research conflictを全保存成功にしない。OFFは他のAI見解自動archive等を止める全体設定ではない
- 文言: 「設定済みのVaultにも保存」と実際の4経路・場所・実行環境を対応付ける。本体ファイル／Research／各生成先を分け、閲覧端末へのダウンロードと混同しない。計画相談の「発話本文を自動では含めない」は入力目的文に貼った本文まで送らない保証ではない。具体文は[文言仕様](ui-microcopy-state-catalog.md)J06〜18/J25を条件付きで再利用する
- 出典: DG-03/11、反証H4、文言仕様、[独立契約確認](../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-review.md)と追加probe、UX:S12/UX:S26/UX:S31、PR:T5。旧14項目の監査を上書きせず、追加の契約所見として追跡する
- 移行／rollback: 表示adapterは単独で戻せるが、scope guardを外して広い副作用へ戻さない。新しい保存先／outcome fieldは後方互換・旧run／旧client・再開のfixtureを先に用意する。新契約と実Vault dry runは未実施。未知stateは最終確認時刻と再取得／詳細を示し、実行中／停止／成功を推測しない

### W04 固定runと根拠への往復を見える契約にする

- 対象: `app.js:5757–5814`、`analysis-storage.js:43–69`、`analysis-content.js:45–122`、`analysis-execution.js:316–325,651–655`
- 作業: 対象／表示版／対象集合／fresh-stale／作成時刻を共通帯へ。完了から固定runを開く入口を設計し、通常の現在データ集計と区別する。`AnalysisStore.public:315–321`のartifact URL、保存packageのinput.json／result.json／manifest、既存artifact読取APIを先に再利用できるか調べる。不足分だけ最小のread API追加を別契約にする
- 読取境界: 固定成果物の閲覧と実行中jobの状態取得を分ける。現行pipeline statusは再起動でinterruptedになった待機runを自動retryする場合がある（`analysis_pipeline.py:766–770`）。GETという形式だけで副作用なしと仮定せず、固定結果ビューからその回復経路を呼ばない
- 復帰: `{item, run, page, filter, selectedEvidence, scroll, focusOrigin}`相当を既存navigation stateへ対応付ける。新しい永続session storeを先に作らない。根拠panel案は既存detailsを使う案と比較する
- 狭幅の文脈: 主張全文又は意味を保つ要約、AI下書き、取得できた確認状態、解釈の限界、選択発話IDを根拠と一緒に残す。「確認記録なし」と読取不能を分け、人の未読と同一視しない。B mobileで研究者メモを別状態へ置く負担を比較に含める。現在発話の対応元を確定できない場合、その移動buttonも有効にしない（MC-02/06）
- 合格: シナリオS04/S05。入力更新後も旧runの版・引用が変わらず、stale/unknownを保持。根拠から同じ結果・位置へ戻る。出力と画面のrun/hash/revisionが一致
- 出典: DG-06/12、UX:S04/UX:S06/UX:S17/UX:S20、PR:T5/PR:T6
- 移行／rollback: readonly表示を先行。新paneを戻しても既存根拠リンクが使える。hash・結果の再生成や旧runへの情報補完は行わない

#### W04 固定viewerの最小契約案

現行の結果buttonは現在itemを再読込するため固定viewerではない。まず`ai_insights`と`milestone_analysis`の保存済みpackageをread-onlyで扱い、他kindは既存の正しいartifact downloadを残して「画面表示は未対応」とする。current/live workspaceへの無言fallbackを禁止する。

| 表示するもの | 現行の取得元 | 新adapterでの扱い |
|---|---|---|
| run／対象／入力版／日時 | manifest.jsonのanalysis_id/conversation_id/source_revision/analysis_revision/created_at/input_fingerprint | 選択run・一覧metadata・input.jsonの識別子と照合。不一致なら停止、欠落は不明 |
| 生成時の発話・条件 | input.jsonのsegments/config/annotations/preparation、original_source | snapshot内の発話IDへ戻す。現在本文から補完しない。時刻欠測を0秒表示にしない |
| AI見解と引用 | ai_insightsのresult.json内analysis.insights.ai.findings/evidence | AI下書き表示とvalidation_noteを維持。欠けた引用は欠落として示す |
| 基礎pipeline結果 | milestone_analysisのresult.json内methods/chart_specs/parameters、tables/*.csv | 対応したmethodの読み取り表示のみ。schema未知はdownloadへ。全手法rendererやXLSXを装わない |
| 保存byteのhash整合 | 既存artifact API→AnalysisStore.read_artifactのDB hash照合 | 既存読取を維持し、409/404を現在値で埋めない。hash一致を意味・版の整合と同一視しない |

根拠: `services/analysis_archive.py:60–103`、`services/analysis_jobs.py:114–130`、`analysis_pipeline.py:557–603`、`analysis_store.py:304–321,400–423`。`result.analysis`を丸ごとliveの`analysisState.data`へ差し込まず、既存の表示用部品を使うadapterで取得元を分離する。ただしevidenceDetailsは欠落IDをskipし、欠測時刻を0表示するため無変更では使えない。欠落ID・件数を明示し、時刻不明の表示へ修正する。根拠・音声guardはcallback／文脈を明示して再利用し、liveのpoll・再集計・保存handlerを呼ばない。

- 意味の整合: milestone結果のparameters.binding内の定義版とparameters.definitionsの版も照合する。旧runの不一致・確認不能は『定義版の整合を確認できない』と表示し、自動比較・確認済み表現を止める。元artifactを保持し、最新定義で来歴や値を書き直さない
- 読取入口: 一覧由来なら既存artifact URLを使う。現在は任意run IDのJSON lookupがなく一覧は100件で切れるため、再読込／深いリンク用に`GET /api/analysis/runs/<run_id>`相当の小さいread lookupを提案。既存store.get/publicと対象存在確認、runsと同じ現入力fingerprint照合を再利用し、artifact URLを返す。現入力を照合できなければfreshとせず不明。worker/status/retryを呼ばない。全bundleの再構築や任意filesystem pathを受けるAPIは不要
- URL案: `#/analysis/<item>/saved/<run>`。既存`/run`実行画面・旧hash/queryと分け、live routeより先に判定する。現parseRouteHashは後続要素を無視するため、route拡張は必須。lookup完了前に現在データを表示しない
- 復帰範囲: 同tabの根拠往復とBack/Forwardはentryごとのpage/filter/evidence/scroll/focus識別子をhistory.stateへ保持。全文／DOM node／tokenは保存しない。reloadは同じ固定runをURLから復元し、history contextが有効なら復元、欠落なら同じrunの概要・見出しへ戻す。新tab／sessionを越えた完全な位置復元は約束しない。既存syncRouteHashのnull state上書きを調整する必要がある
- 原音と現在編集への移動は明示操作。本文・話者・有効な時刻が照合できない引用は自動seekしない。既存Number差分比較はmissing/NaNを明示拒否しないため、生成時と現在の両方でnull／空値／time_unknownを拒否し、有限・非負・start≤endを確認してから差分を照合する。変更後のreturnは固定readerを呼び、現在itemを開く`returnToAnalysisEvidence/openAnalysisForItem`へ戻して済ませない。未保存確認を保つ
- rollbackは表示adapterを外しても固定URLのguardと正しいrunのdownloadを残す。旧parserへ全面撤回してsaved URLを現在データとして解釈させない。404／hash conflict／未知schema／引用欠落／履歴100件外／reload state欠落のfixtureが通るまでW04は契約レビュー中

### W05 ラベルとcontrastを用途ごとに修正する

- 対象: `app.js:7317–7347`、`style.css`のroot／drop zone／registry unsaved／focusと各上書き
- 作業: 相互作用の対象select・関係select・根拠memoに見えるlabelと関連付け。memoを絶対無名とは扱わない。指定色ではなくcomputed foreground/backgroundを採取して、必要なテキスト・状態・focusの役割色を調整する
- 新しい測定／根拠UIでは、採用不可の理由とdisabled状態、mobile main navの現在地を色以外と役割・状態で示す。静止批評MC-07は実UIでの残留確認事項であり、現行アプリの新規欠陥数やAT失敗数へ加算しない
- 合格: シナリオS06。role/nameから通常操作、accessibility treeで目的名、実ATをした場合のみ音声確認済み。文字4.5:1／該当する非テキスト3:1、focusが完全に隠れない。濃色sidebar等の良い既存箇所を改悪しない
- 出典: DG-09/10、反証第2巡、UX:S22/UX:S25/UX:S28/UX:S29/UX:S30a
- 移行／rollback: 局所CSS／labelを小さく分割。全ブランド色一括置換を避け、state別before/afterを保持する

### W06 履歴を探し直せるようにする

- 対象: `analysis_store.py:274–297`、`handlers/analysis_queries.py:58–79`、`analysis-storage.js:27–85`、比較履歴
- 第1段階: 既存上限なら「直近100件を表示」と明示し、保存総数と呼ばない
- 出力説明: 固定runか現在filterか、本文／時刻／話者／コード／ノート／来歴のどれを含み、どれを含まない形式かを表示する。これは[公式参照パターン](ui-design-research/2026-10-02/reference-patterns.md)A04からの適用案で、既存exportを無断に拡張する要求ではない
- 第2段階: 安定した`created_at + id`降順のkeyset cursor、次ページ有無を加える。初期案はlive一覧で、次ページはcursorより古い範囲を取得する。走査中にcursorより新しいrunが加わった場合は現在の走査へ割り込ませず、更新で先頭から見せる。初回時点の全件固定snapshotとは呼ばない。総数を出すなら取得時点を付ける。既存responseを壊さず、通常runと比較runへ同じ契約。厳密なsnapshot一覧が必要になった場合は別のserver境界tokenを設計する
- 合格: シナリオS05。変更なしの0/1/99/100/101/105/201件と同時刻fixtureで全件到達・重複／欠落なし。並行追加では既出IDの重複なし、新しいrunは更新後に通常操作で見つかる。101件目へ到達し、既知のartifactリンクは引き続き読め、保存件数は減らない
- 出典: DG-04＝UX-34、反証第2巡、UX:S08/UX:S13/UX:S20
- 移行／rollback: 原則schema変更なし。index等の追加時も削除・型変更なし。旧clientの既定100件応答を保持し、全件取得をブラウザーへ無制限転送しない

### W07 タスク別入口を段階導入する

- 対象: `templates/views/analysis.html:111–139`、`app.js`のnavigation、`analysis-visualizations.js:1014–1031`、ADR-118
- UI-0: 現行と候補の同一fixtureの画面map。UI-1: 結果を見る入口。UI-2: 比較入口。UI-3: 計画・試行・採用。UI-4: データ・出力。これは導入単位の提案で、既存再編計画の詳細番号との整合を着手前に確認する
- 比較案: [初期仕様8図の契約説明](ui-design-assets/2026-10-02/prototypes/comparison.md)を保持し、密度・日本語表示は[clean v2](ui-design-assets/2026-10-02/prototypes/v2/index.html)を使う。v2は同一fixtureの1280px／390px比較8図＋定義変更後の補助2図で、18件の独立比較ではない。Aは既存モード＋段階レビュー／根拠details、Bは4タスク＋対照面／根拠pane。初期候補はA、Bの各要素は独立比較。既存実装との距離と静止レビューに基づく暫定案で、学習・速度・好みの優位は未確認
- 引継ぐレビュー: [画面外凡例](ui-design-assets/2026-10-02/prototypes/v2/outside-legend.md)にAPI・保存・移行条件、[独立批評](../50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md)に初回と修正後のhashを置く。MC-02〜06の情報不足は静止図で補われ、MC-01は試行版と失効状態を補強。MC-01の動作とMC-07のdisabled／現在地は受入待ち。初回8図と修正後10図の再レビューを重複した実験数にしない
- 比較の分離: Mはnavを固定して段階レビュー対対照面、Eはnavと結果を固定してdetails対pane、NはM/Eを固定して3モード対4タスクを調べる。A/B全体の差を1つの要素の因果効果にしない。静止図は情報の所在だけをレビューし、click数・focus・完遂率を測定済みとしない
- 合格: S01〜S05の同等課題で正しい初手、完遂、戻り回数、対象版の説明、誤実行を比較。重大な保存／研究誤認が増えれば採用しない。速度差だけで決めない
- 出典: DG-05、ADR-118、UX:S08/UX:S11/UX:S13、PR:T2/PR:T3/PR:T8
- 移行／rollback: top navと旧hash/queryを維持。既存rendererを使う小さなadapterと切替点を設け、新旧結果の二重描画を避ける。入力draft／filter／履歴を保ったまま旧配置へ戻せるようにする

### W08 日本語の読みやすさと狭幅を調整する

- 対象: DG-07/08/12/14の指定selector、作成以外の表、話者・履歴・分析nav
- 作業: 現行HEADの画像を取得して旧画像の仮説を再確認。本文16px相当・label14〜15px相当・補助13px相当、本文行間1.6〜1.8は比較候補。表の列優先順位、長文折返し、要約／詳細の分離を先に検討する
- 比較条件: v1の開発注釈による密度を評価対象へ持ち込まない。v2は全長の静止図で、first viewportや実reflowではない。B mobileが短い分には研究者メモを別状態へ移した差もあるため、画像高を効率点へ換算しない。短い日本語、版・欠測・限界の可視性を維持して比較する
- nav: selected項目をnav内でnearest表示、または狭幅で選択メニューを比較。本文のスクロールや編集中focusを不用意に動かさない。reduced-motion時の直接smooth呼出しも確認する
- 合格: S06/S07。日本語IME、長い氏名・ファイル名・発話、320/390/959/960/1440px、200%拡大、必要な400%相当、Windows font環境。主作業到達までの操作／スクロールを比較し、警告・欠測説明を隠して見かけだけ短縮しない
- 出典: DG-07/08/12/14、UX:S11/UX:S13/UX:S22/UX:S27、PR:T3/PR:T8/PR:T9
- 移行／rollback: 画面単位でCSSを変更し、既存breakpointを理由なく全面変更しない。style差分を戻しても状態・保存契約は維持

## 4 W09 受入のゲート

詳細は[受入方法](../50-Tests/ui-design-acceptance.md)。表の各列を独立記録する。

| 層 | 証明するもの | 合格へ含めないもの |
|---|---|---|
| V1 contract/unit | 計算値、validator、payload、revision、保存状態 | 可視性、hit testing、人の理解 |
| V2 component | 合成DOM、属性、文言、指定CSS | 通常の開始入口、実AT音声 |
| V3 browser operability | production CSS＋通常pointer/keyboard＋画面遷移 | forced click、hidden解除、操作の代わりの直接state設定 |
| V4 assistive technology | 実accessibility treeと実AT発話 | ARIA属性だけによる音声合格 |
| V5利用者理解 | 対象版・測定意味・送信先の理解、タスク成績 | エージェントの模擬ペルソナ、見た目の好みだけ |

V1/V2で失敗原因を早く特定し、V3で通常到達性、V4で中心作業を確認する。W07の採用判断はV5の形成的比較を含める。参加者を確保できない場合は未実施として戻せる試作に留め、効果を断定しない。

v2の10図は静止表示レビューとして別記する。生成側の寸法／文字境界検査と独立した画素批評は、アプリのV1〜V5合格へ転記しない。修正版の明白な欠け・重なりが見つからなかったことも、実font／pointer／focus／AT／利用者理解の成功を意味しない。

既存test_ui_safety_browserのlocator＋実Tabは良い土台。初期render直接呼出しがあるため、一覧→対象を開く外側の導線も追加する。test_content_browserのDOM click、Transformer fixtureのproduction CSS欠如、閉じたadvisor dialogへの値代入は別層と記録する。

全試験は合成録音・一時DB／Vault・stub providerを原則にする。これはUI/APIの検証であり実モデル精度ではない。外部AI・実録音・追加モデルはこの計画だけでは使用しない。sandbox拒否やsocket制限は安全条件を緩めず、利用可能な正規環境で確認する。

### リリース判断の最低条件

- 対象commitと変更ファイルhashを固定し、該当シナリオ、隣接unit/integration、影響に応じた全体試験を最終差分で実行
- W01/02の可視入口・測定対照がV3で成功。V1/V2だけならUI受入済みとしない
- 原25件の関連回帰を再確認。Windows UI10件は該当環境での実受入が揃ったときだけ元表を更新
- 失敗／未実施／skipを分ける。過去の864 passed等を新commitの証拠へ流用しない
- 研究者データ保護・引用版・欠測・対象集合・出力整合に退行なし。発見した差分は既存issue IDと結ぶ
- 配置・push・Windows反映は別の承認・実施結果を持つ。試験成功だけで公開済みとしない

## 5 移行と記録の共通方針

保存済みrun／定義／研究者メモの一括変換を前提にしない。UI adapter、文言、readonly文脈表示から始める。保存契約を広げる段階では旧reader互換、一時データのdry run、backup、前版へ戻したときの読取、再開方法を先に用意する。rollbackはコードを戻しても新しい研究者編集を消さない方法にする。

dotで調査・実装・検証を進め、節目に既存Software Vaultを更新する。0.3文書は`88f5e3e`で統合済み。本0.4更新をSoftware Vaultの文書へ反映した。以下のruntime修正・受入は未実施であり、文書の統合を実装完了にしない。

- `20-Modules/ui-screens.md`: 現行map、入口、操作・状態の説明
- `40-Design/decisions.md`: 採用した代案、互換性、採用しなかった案の理由。局所CSS変更ごとにADRを量産しない
- `60-Operations/dot-cloud-development-handoff.md`: commit、成功／失敗／未実施、成果物参照、残る環境・受け渡し課題

節目の記録形式: 「対象commit／W・DG ID／採用した変更と理由／守った契約／実行した検証と対象版／未実施／次の担当が判断する点」。研究者所有ノート、runtime、移入Vaultには開発記録を書き込まない。

## 6 開発着手チェックリスト

**確認済み事実・既存契約として引き継ぐ**
- [ ] 対象HEADでDG-01の入口、DG-02の暗黙規則／採用／版ずれを再確認する。修正をレイアウト選好の決定待ちにしない
- [ ] 原25件の区分、既存API／URL／ID、研究者編集、固定run、欠測と0、AI下書きと人の採用を保護する
- [ ] 仕様v1は8図、clean v2は比較8図＋補助2図と識別する。MCの静止改善を実行・保存・GUI・ATの合格に数えない

**技術判断と実装のgateが残る**
- [ ] W02はルール復元を推奨し、文字数限定の短期案も明示する。不一致安全停止／固定snapshot、trial固定入力、旧worker互換を決めて試験する。永続レビューgateは別判断
- [ ] W04は固定viewerのlookup／field／route／復帰／legacy停止条件を満たす。利用不能な原音や現在発話への入口を成功状態として描かない
- [ ] W03は3種のAPI targetと実際の4書出し経路を区別し、scope guard・各先outcome・再試行範囲を試験する。送信説明はAI見解の付与情報まで含める
- [ ] V3／Windows／ATの正規実行環境と未実施の記録先を確保する。sandbox Chromium起動失敗は未解決として引き継ぐ

**将来の利用者検証で選ぶ**
- [ ] Aを暫定導入候補に留め、M＝定義配置、E＝根拠表示、N＝入口再編を分けて比較する。B mobileのメモ往復も課題へ含める
- [ ] 密度・文字・狭幅は同じ必須情報で比較する。主指標は正しい版での完遂と誤認発見、時間・好みは補助。重大な保存／研究誤認があれば採用を止める

チェックは着手担当の確認用で、現時点の実装完了を表さない。W00とfixture設計は独立に進められ、今すぐ利用者へ全選択の回答を求める必要はない。
