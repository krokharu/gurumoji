---
note_id: "ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks"
note_type: "design-evidence"
title: "Gurumoji デザイン監査の独立反証チェック"
summary: "2026-10-02の研究・設計・検証記録の保存版。提案や静止図を実装・操作合格へ置き換えない。"
status: "current"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
tags: ["gurumoji/design", "gurumoji/ui"]
---

# Gurumoji デザイン監査の独立反証チェック

対象: `ddc23ab`（実装差分の直近 `59ebd24`）／初回検証 2026-10-02 18:26–18:33 UTC

## 結論

- **H1: 採用（P1候補）**。Transformer・AI見解・発話分類の個別実行入口は現行ソース上、通常のUI操作から到達できない。APIと保存済み結果の表示は残っている。「機能そのものを削除した」「保存済み結果も読めない」は不正確
- **H2: 採用（P2）**。`ui-screens.md`の「6段階・ブラウザーが順次API実行・永続pipelineは後続」という現行説明は実装と不一致。サーバーはM0–M7と永続台帳を持つ。ただし、より広い設計書の47成果物や7 LLM役割がすべて実装済みという意味ではない
- **H3: 採用（P1候補）**。手動測定の4入力欄は名称等のみ。実行規則は非表示の選択肢ではなく、存在しない5要素から `text / text_length / number / ratio / descriptive` にフォールバックする。自然文の説明は測定ルールへ変換されない。試行から採用へ確認待ちなしで進む
- **H4: 部分採用（P2）**。失敗状態の主見出しが「分析を実行しています」になる。結果ボタンが `completed` 限定なのも事実。ただし画面を抜ける導線があり、「失敗すると全結果へのアクセスを失う」は反証された

この判定は**ソース検証と隔離した実行プローブ**に基づく。実ブラウザーの画面操作・スクリーンリーダー・実際のレスポンシブ表示は未検証。Chromiumをsandbox維持で起動したが `socket() failed: Operation not permitted` で起動前停止した。制約の解除・別経路での回避は行っていない。

## H1: 個別実行の入口消失

### 成立する最小の主張

通常ロードされるスタイルシートを適用したUIでは、Transformerテーマの新規/再実行、AI見解生成、分類実行の対象ボタンは `display:none!important` になる。現行の「基礎分析」pipelineにはこれらの代替実行stepがない。

### 根拠

1. `templates/index.html:8–9` は `style.css` と `ai-effort.css` を通常読み込み。`style.css:2088–2093` はmedia queryの外にあり、次を非表示にする
   - `[data-transformer-run]`, `[data-transformer-cancel]`
   - `[data-insight-generate]`, `[data-insight-cancel]`
   - `[data-run-segment-classification]`
   - AI見解providerを含む `.content-ai-section .content-ai-toolbar`
2. 対象ボタンは実際に作成される
   - `analysis-content.js:184–188`: `startContentInsights` に結び付く生成・中止ボタン
   - `analysis-content.js:561–568`: `startTransformerAnalysis` に結び付く実行・中止ボタン
   - `analysis-method-view.js:254–264`: 分類実行ボタン。`app.js:8116–8120` がイベントを受ける
3. `analysis-content.js:839–845,1113–1119` の状態更新はdisabled、ラベル、cancelのhiddenを変更する。属性削除、重要度付きdisplay解除、別表示ボタンの生成はない
4. `analysis-execution.js:560–594` の統合開始はplan previewとpipelineのPOST。`analysis_core.py:80–100,311–338` の実行計画は participation、conversation_dynamics、manual_measurement。AIを使うO01計画相談も既存2手法の優先順位付けであり、見解生成/Transformerテーマ/分類実行の代替ではない
5. `templates/index.html:236` は「Transformerテーマ分析とAI見解は『内容・文脈検索』から個別に実行」と案内。`analysis-content.js:1126` にもAI見解の同じ案内が残る

### 代替・反例を調べた結果

- **desktop/mobile別入口:** 対象selectorに対するトップレベル重要宣言のため、同じ属性を持つどちらのレイアウトにも適用。mobile用 `.content-ai-toolbar` のgrid指定は `style.css:2008` にあるが、後続の非表示規則を打ち消さない。実画面の幅別テストは未実施
- **feature flag / 後続CSS:** src全体の該当selector、実行関数呼出し、style変更を検索。後続の解除規則や属性削除、条件付きの別入口は確認できなかった
- **別の表示ページ:** `app.js:6760–6769` ではAI見解を作る `buildInsightSummary()` は「概要」に入り、「内容・文脈検索」にはKWIC・分類・Transformerが入る。つまりAI見解は非表示問題に加えて案内先も不一致
- **API:** `web/analysis_routes.py:205–305` にinsights、transformer、classificationsのPOSTが存在し、`handlers/analysis_commands.py:180–199` が実サービスへ委譲する。APIやコンソールから呼べることは、人向けUIの代替入口にはならない。一方「backendも未提供」と断定してはならない
- **保存済み結果:** 読み込み・結果表示・出力経路は存続。分析を「新規実行できない」と「過去の結果を閲覧できない」に分ける

### テストが見逃す理由

`tests/test_content_browser.py:146–148` はDOMの対象ボタンをJavaScript `.click()`で直接押す。非表示要素でもプログラム的イベントは発火するため、テストが成功しても人が見つけてクリックできる保証はない。

受入条件は、保存済み合成データを開く → 案内されたtabへ移動 → 可視・enabledなbuttonへポインター/キーボードで到達 → 正しいAPIだけ1回送信、まで確認すること。provider、送信対象、保存前ブロック、実行中中止も同じ表示状態で確認する。

## H2: 旧6段階の現行説明

### 確認できた不一致

- `docs/program-vault/20-Modules/ui-screens.md:21`: 6段階、画面側の順次API実行、永続pipelineは後続Phase 3–4
- 同 `:52`: 詳細設定でTransformer・AI実行先・Jev・再利用を指定する説明
- 同 `:86`: 旧入口を非表示にして新画面へ統合したと説明
- 実際の `analysis-execution.js:1–12,439`: M0–M7、サーバー永続ゲート。ブラウザーはpipelineを開始し状態をpollする
- `analysis_pipeline.py:44–93`: 定義、pipeline要求、step attempts、公開先状態、イベントのSQLite台帳と再起動回復
- 同 `:332–377,635–750`: 受付保存、段階実行、完了状態の保存。`analysis_core.py:311–338` に具体的な8段階計画
- `analysis-milestone-visualization-design.md:19` は初回導入範囲のM0–M7実装済みを明記

### 過大解釈しないこと

古い記述があることと実装が非永続であることは逆。M0–M7の存在を否定する根拠にはならない。また大きい設計書には将来の全構想が含まれるため、全機能の実装漏れを無条件で不具合として数えない。現在の初回導入範囲は同文書18.7節およびcapabilitiesに絞る。

## H3: 手動定義と測定意味のずれ

### UI・契約・計算をつないだ根拠

- `templates/index.html:243–249` の手動欄は定義名・ID・説明・出力列の4つ
- `analysis-execution.js:50–64` が参照するsource、rule、type、level、methodの5要素は現行templatesに存在しない。src全体にもこれらを作るコードを確認できない
- 欠落時の値は source=text, rule=text_length, type=number, level=ratio, method=descriptive
- `analysis_core.py:151–198` は構造化された測定ルールを検証するが、説明文を意味解析してルールへ変換しない
- `analysis_pipeline.py:104–126` はtext_lengthなら本文文字数を返す。`:157–168` はその値を数値記述統計として要約する
- backend自体はidentity、text_length、nonempty、duration、boolean_trueとfrequency/descriptiveを持つ。欠けているのはUI選択・伝達と、その意味の説明

### 独立した合成プローブ

`adversarial-contract-probes.py` とJSONで再現。Flask appはimportせず、純粋契約・測定モジュールに合成データだけを渡した。

- 説明「各発話の持続時間を秒数で測る」、出力列 `synthetic_duration`
- 2発話の本文文字数3/10、実時間60秒/2秒
- UI既定の構造化payloadによる算出値: **3 / 10**
- API契約でdurationルール/列を明示した対照: **60.0**

これはユーザーが自然文だけで任意測定できると解釈した場合に、出力名と実際の計算が食い違うことを示す。既定ルールが常に誤りという意味ではない。文字数を意図して入力した場合は整合する。

### 試行と採用

`analysis-execution.js:542–557` はdraft PUT → trial POST → adopted PUTを1回のsubmit内で連続実行する。trial値の個票は表示せず、件数だけを文面へ入れる。利用者が測定値や尺度を見てから採用する待ち状態はない。その後pipeline受付が成功するとdialogを閉じる。

追加のin-memory SQLite対照では `save_definition(..., status='adopted')` はtrial未実行でも成功し、`last_trial_json='{}'` のまま採用できた。これはAPIに人のレビューを保証するゲートがない証拠。ただし、ユーザー操作の意図をAPIが必ず別確認すべきだと単独で断定するものではない。UIの意味を修正する際、どこでレビュー・採用を保証するかを設計上明確にする。

### 妥当な修正方向・受入条件

- 限定文字数機能として提供するなら「文字数測定」とルール・型・尺度・単位を明示し、任意測定のように見せない
- 手動定義として提供するなら実在するsource/rule/type/level/method選択と互換性検査を復元。少数の実測値、欠測理由、要約を見て採用する導線を設ける
- 意図がdurationの合成定義をUIから作って、出力が文字数にならないことを確認。名義尺度の平均を拒否する対照も含める

## H4: failed状態の表示と出口

- `analysis-execution.js:435–437`: completed / waiting / cancelled以外は「分析を実行しています」。failedも該当
- `:462`: 結果を見るbuttonはcompleted以外でhidden
- 反例: `templates/views/analysis.html:77` の「バックグラウンドで続ける」はhiddenでなく、`analysis-execution.js:650` が `hideAnalysisExecutionView()` に結び付ける。同 `:511–515` でworkspaceへ戻れる。Back/Forward経路も`:661–664`にある
- 判定: 状態と次の行動の誤案内。失敗時の出口label、部分成果・公開だけ失敗の読み取りを改善すべき。「完全に閉じ込められる」「成果物を失う」は未成立

## 実施・未実施

### 成功

- 指示・HEAD・clean状態、現行templateとJS/CSS、API/handler、純粋契約と測定実装の確認
- 全src内のselector/実行関数呼出し/代替生成を検索
- 独立Pythonプローブ: templatesの欠落ID、測定意味の対照、in-memory採用状態の確認
- audit担当の `static-design-probes.{js,json}` の実装と限界を確認。こちらのPythonプローブとは独立した補助証拠

### 失敗・未実施

- sandbox維持のChromiumは起動失敗（exit 134）。ログ `visibility-probe.stderr.txt`。ブラウザーのプロセスソケット制約を変更していない
- 実際のアプリページのcomputed style、画面画像、キーボード導線、幅別表示は未確認
- 実データ、app/runtime、移入Vault、秘密、モデル推論、外部AIには接触していない
- ソース編集・commit・pushなし。チェックアウトはclean

### 再実行

```sh
cd /workspace/scratch/be1eb353f7eb/projects/gurumoji/app
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python ../artifacts/design-sprint-20261003/adversarial-contract-probes.py
```

現在のプローブは監査用の再現で、将来修正後の期待値を検証する回帰テストとは別。修正後は欠落IDや誤測定が存在しないことを検証するテストへ反転させる必要がある。

## 第2巡: contrast、履歴上限、相互作用リンク（18:35–18:42 UTC）

### DG-09: 計算そのものは再現したが、実際のcascadeで条件を修正

独立sRGB線形化・相対輝度計算: `adversarial-secondary-probes.py/.json`。比率比較は丸める前に行った。ここでの値はスタイルシートに基づく推論で、computed styleの採取ではない。

1. **drop-zoneの補助文字:** `#8a948f`と旧base gradientの両端の比率2.891838/3.028643は数学的に正しい。しかし `style.css:1617,1635` の>=960px規則と `:2257,2274` の<=959px規則で `.create-form .file-drop-zone` はwhiteへ上書きされる。現在の初期状態の適切な指定ペアは **#8a948f / #fff = 3.128142:1**。`.8125rem`の通常文字なので4.5:1に達しない。結論は維持、画面の数字としてgradient比率を使わない
2. **橙色の未保存文字:** #e87941/cardの2.871495は参考ペア。registry overviewは実際には`:941`のgradient #f8faf5/#f1f5edで **2.759298 / 2.626739**。保存barは`:1052,1578`に95%/96%cardの半透明背景。下地が黒〜白の範囲で比率は **2.570902〜2.872889 / 2.629390〜2.872610** となり、いずれも通常文字4.5未満。単一の2.871を全箇所へ適用しない
3. **反例:** 分析sidebarの未保存は`:2313`で#97451dに上書きされ、背景#f2f5efで **5.991741**。「すべての未保存表示が低contrast」は反証
4. **35%緑focus ring:** card/paper/whiteに合成した1.692321〜1.725046は再現。ただしfield focusは`:579`で濃緑border、matrix focusは`:1456`で#2975beの専用outlineがある。前者はwhite比6.425377、後者4.791960。したがって「全controlのfocusがAA不合格」とは断定しない。ringだけしか変わらないcontrolを実際にfocusし、隣接色・clip・全体指標を確認する必要がある

規範の切り分け: 通常文字は4.5:1、大きな文字は3:1。作者が設定した非テキストの必要な状態表示は隣接色に対する3:1が問題になる。Focus Appearanceの面積等はSC 2.4.13（AAA）であり、AA基準と混ぜない。参考: [W3C Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)、[W3C Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)、[W3C Focus Appearance](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance.html)。

### DG-04: 履歴上限は成立、既知問題・非破壊と限定

- `analysis_store.py:274–297`: `list_comparisons`と`list`が最新100件で切る
- `analysis-storage.js:36,74–84`: 取得数だけ「N件の保存履歴」と表示し、取得にpage/cursorを渡さない
- `handlers/analysis_queries.py:58–79`: responseにtotal/cursorなし。元のrun数より少ないか判別できない
- 独立プローブでは元コードのreadメソッドだけをAST抽出し、105件の合成in-memory SQLiteへ実行。両一覧は100件、105件全ては残存、最古IDも`get`で取得可能
- `AnalysisQueries.run_bundle:95–107`はIDで取得してbundle化するため、既知のrun/artifactリンクを一律無効にする上限ではない。通常の一覧から古いrunを発見できない問題
- `ui-ux-issues.md:127` のUX-34に既に記録済み。同じ欠点を新規発見として集計しない。P2の未解決継続

### DG-10: select2つの命名欠落は採用、memoの「無名」は限定

`app.js:7317–7347` のtarget selectとrelation selectはlabel要素、aria-label/aria-labelledby、titleを付けずdivへ直接appendする。全srcの属性参照にも後付けlabelは見つからない。周囲のsummaryと説明文は各controlへ名前として結び付けられておらず、選択肢の現在値はcontrolの目的名の代わりにならない。

memo inputはplaceholderのみ。常時見えるlabelがないため入力後に用途が見えなくなる点は成立するが、「AT上の名前も絶対に空」は誤り。HTML-AAMはtext inputのplaceholderを名前のfallbackとして定義している。select2つのprogrammatic name欠落とmemoのpersistent visible label欠落を分ける。実際のaccessibility tree/AT発話は未測定。根拠: [HTML-AAM accessible name](https://www.w3.org/TR/html-aam-1.0/#accessible-name-and-description-computation)、[W3C control labels](https://www.w3.org/WAI/tutorials/forms/labels/)。

### 検証方法の成果物

`browser-acceptance-methodology.md`に既存4 browser suiteとstatic assertionの区分、通常操作を迂回する箇所、修正後に必要な受入手順を記録した。既存テストの有用性を否定せず、API/handler・DOM構成・可視操作・ATの証明範囲を分ける。

## 第3巡: DESIGN初稿と実装計画の契約レビュー（18:57–19:06 UTC）

対象: `draft-DESIGN.md`、`design-implementation-plan.md` W00–W09、`agent-design-knowledge.md`、`user-scenario-walkthroughs.md` 初稿0.1。本文は編集せず統合担当へ修正要求を送った。

### 1. W02の個票レビューにはtrial response拡張が必要

現行 `analysis_pipeline.py:258–280` は `input_hash`、definition ID、sample/valid/missing件数、**欠測を除いたvalues配列（最大20個）**を返す。元の `measure_segments:129–146` はsegment IDと欠測理由を持つがtrial返却時に落としている。したがって、S02の「e3は欠測理由付き、e4は0」という個別確認をUIだけで作れない。

要求した修正: 既存fieldsを保持してrows（segment ID/value/missing reason）と測定したdefinition revisionを追加する小さなresponse契約変更を、永続review gateの強化と分ける。現在の本文とvaluesをUIが順番で推測して対応付けてはならない。input_hashは既存なので重複導入しない。

### 2. W02の既採用保護と固定版実行は、現行APIの無料の保証ではない

**同じIDのdraft保存で旧採用を置換する:** `analysis_definitions`は(item_id, definition_id)を主キーとする1行の現行状態。`:227–256`はdraft PUTでもpayload/status/revisionを上書きする。adopted v1→draft v2を行うと旧adoptedは定義表から取得できなくなり、`:221–224`は `definition_not_adopted`を返す。既存runのsnapshotまで削除するという意味ではない。

**bindingの版とworkerの定義がずれ得る:** `start:358–365`はversion付きbindingを保存するが、`_run:640–643`はIDだけで現在の定義を読み直す。`_execute_step:496–499`はその現在定義で測り、`_save_package:569–572`は古いbindingと現在definitionsを同じpackageに入れる。

独立再現:

- `definition-lifecycle-probe.py/.json`: in-memory SQLite。draft上書きで1行だけ残り旧adopted lookup失敗。別例でaccepted binding v1→現行adopted v2更新→元worker定義ロードprefix＋元manual stepを実行。v1文字数3のはずがv2duration60秒をcommittedにする
- `definition-full-pipeline-probe.py/.json`: 一時合成SQLite、元M0–M7 `_run`。受付後の `_schedule`だけをpauseして定義更新を挟み、実orchestratorを実行。全M0–M7はcommitted、pipeline completed。**save adapterへ渡されたpackageはbinding version1、definitions version2、測定値60.0**。元v1なら3文字
- 後者のmethod_runner・save/publication adaptersはstub。実モデル、実成果物ファイル保存、Vault公開、HTTP UI、通常schedulerでの発生頻度は試していない。保存adapterへの不整合payloadと元pipelineの状態確定を証明する。これを「実ファイル破損を観測」とは書かない

要求した修正: W02をUIレビューだけで完了としない。既採用の編集を別draft ID/不変版/非保存trialのどれで保持するか決める。Cancel時の逆PUTによる巻戻しは他clientの更新を壊し得るので避ける。workerでは受理時の定義実体を保持して使うか、bindingと現在版の不一致を実行前に拒否する保証が要る。再試行・再起動でも同じ保証を確認する。元25件の計数は変更せず、DG-02に対応する追加技術依存として記録する。

### 3. W04は既存artifact読取を先に検証する

`AnalysisStore.public:315–321` はartifact URLを返し、保存物には `input.json`、`parameters.json`、`result.json`、`manifest.json`がある（`:400–430`）。manifestにrun ID、snapshot ID、入力fingerprint、revision、artifact hashが入る。`AnalysisQueries.artifact:81–92`と`run_bundle:95–107`が読取を提供する。

要求した修正: 固定run画面のための新read APIを必須と決めず、これらのsnapshot/result/manifestを安全に再利用できるか先に調べる。public runの要約だけにはhashが出ないため、取得していないhashを表示へ補完しない。未取得・legacy欠落はunknownとする。

注意: `AnalysisPipelineService.status:766–770` は再起動由来のinterrupted待ちをstatus GETから自動retryする条件を持つ。**GETだからすべて副作用なし**とは扱わない。固定成果物の閲覧と、既に承認された実行の復旧を区別し、閲覧APIへpipeline statusの自動回復を無条件に混ぜない。

### 4. W06のcursor受入は対象集合を定義する

`created_at + id`のkeysetは固定行の安定順序には適切。しかしページ途中の新規runがcursorより前に挿入されれば、進行中scanには入らない。これを「新規も全部含めて欠落なし」と呼ぶのは過剰。単なる最大key cutoffも、後から同時刻・より小さいIDの行が入る場合の厳密なsnapshot membershipを自動では保証しない。

要求した修正: 初回時点の集合を固定する方式か、新規はrefresh後に表示するlive方式かを選び、受入の集合を明示。cursorにfilter/sort/集合条件を結び、別条件への使い回しを拒否する。旧clientの既定100件応答と既知artifactリンクを保つ。厳密snapshotの追加sequence/tokenが必要なら「schema変更なし」を絶対条件にしない。

### 5. S02の真の0秒は現行契約に整合する

`transcript_preparation.valid_time:105–113`は0<=start<=endを許す。`analysis_pipeline.py:114–123`はvalidな非負durationを受け入れる。e4をstart=end=80、duration=0、time_unknown=falseと明記すれば0は正しい。e3は時刻欠測、またはtime_unknown=true/valid_time=falseでdurationの数値placeholderが0でも欠測とする。既存 `test_analysis_research_protocol.py:34–49` に同じ対照がある。

要求した修正: fixtureの真の0と「時刻が不明なので内部値だけ0」を明示。現在のtrial APIには欠測の個票返却がない点は上記1へ戻る。

### 6. 状態不明とdirty navigationの安全な表現

- W03の「未知stateは停止／詳細確認」はbackend停止を保証できない。未知状態・最終確認時刻・再取得/詳細確認とし、実行中/停止/成功を推測しないよう修正要求
- S03でBを未保存編集してAへ移るときは既存confirmLeaveの分岐を含める。移動を取り消してBを保つ、または保存してから移るのも成功経路。未保存guardを迂回して複数item draftを保持できることを既実装契約としない。Aの完了がBの編集画面を自動置換しない条件は維持

### 7. 受入とrollback全体の判定

初稿のV1〜V5分離、source/GUI/ATの未確認表示、原25件の維持、実データと外部AIの除外、局所adapterから戻す方針は妥当。上記W02の定義版保護は、見た目のrollbackだけでは解決しないため別の保存・互換性条件にする。安全な既存readerは新定義を消さず、取得不能な版を現在版で置換せず、停止理由を説明する。

## 第4巡: 固定定義snapshotの旧worker互換（19:20–19:22 UTC、追加probeなし）

統合担当の「version付き完全definition payload＋canonical hashをbinding JSONに保存し、旧binaryへ無条件rollbackしない」という方向は現コードと整合する。ただし次を追加要件として送った。

1. **pendingゼロだけでは旧worker安全性を判定できない。** `analysis_pipeline.retry:847–861`はfailed/interrupted/cancelled stepも再実行候補にする。新形式の非completed runと再開可能attempt全体を互換確認対象にする。完了済みartifactの読取互換は実行互換と分ける
2. **互換guardはDB初期化・回復より前。** `handlers/application_lifecycle.py:43–49`はinstance lock取得後にlibraryを初期化し、`services/library_schema.py:387`が`initialize_pipeline_store`を呼ぶ。同`:79–90`はactive stepをinterrupted、active pipelineをwaitingへ更新する。旧binaryを一度起動してから互換性を判定する運用では、すでにstateが変わり得る。launcher/互換hotfix側の起動前guardが必要
3. **単一process≠単一request。** `services/instance_lock.py:17–30,57–80`と`app.py:445–453`のOS file lockは同data/uploadsへの第二app processを防ぐ。`analysis_pipeline.py:37,402–413`のRUNTIME_LOCKはprocess内のworker二重起動を防ぐ。一方でHTTP要求や独立stepは同process内で並行できる。snapshot、plan、bindingの書込みを1transactionにするだけでなく、対象定義の読取・expected revisionの再検証・内容固定を同じ受理境界で行う

これらは現コードの静的確認で、旧binary起動・データ移行・rollback実行を行った結果ではない。新しい保存契約の採用前に一時データで互換／停止／再開を検証する必要がある。

## 第5巡: W01復旧時の分類late-response境界（19:22–19:24 UTC）

統合担当の指摘を `classification-late-response-probe.js/.json` で独立検証した。元 `runSegmentClassification` 関数とsynthetic deferred fetchを使い、AへのPOSTを保留→表示対象をBへ変更→Aの成功responseを返すと、**Bの`analysisState.data.segment_classification`がAの結果に置き換わり、成功通知もB上へ出る**。

- `analysis-method-view.js:312–347`は送信時のitem/revisionをPOSTに入れるが、await後`:335`で現在のglobal stateへ直接代入する。復帰時item/revision/sequence照合はない
- `app.js:356–364`のapiFetchはheaderを付けてfetchするだけ。`:5878–5892`のAbortControllerはanalysis GETに渡され、分類POSTには渡されていない
- `segmentClassificationInProgress`は分類開始buttonのdisabledに用いられるが、dirtyなしの対象変更をロックする条件ではない（全src参照、`:1072–1073,1113–1135,5868–5917`）
- 比較上の反例: TransformerとAI見解はitem別content stateを保持し、開始responseのfinallyでもitem IDを照合する（`analysis-content.js:933–944,1171–1191`）。したがって3入口すべてが同じlate-response問題だと一般化しない

**制限:** 現在の分類開始buttonはDG-01のCSSで非表示。今回の結果はhandler境界の確定した隔離再現であり、現行通常UIから起きた観測ではない。サーバー側保存の取り違え・実データ損失・実ブラウザーの表示は検証していない。W01で入口を復旧する前のitem/revision/要求世代guard、target-switch/late response受入へ接続する。原25件の完了評価は変更しない。

## 第6巡: 固定viewer提案と既存helperの境界（19:28–19:30 UTC）

第2稿W02保存／rollback、W04固定viewer最小契約を静的照合。提案を未実装と明記し、artifact再利用・任意run lookup案・route/history拡張・旧binaryguardを分けた点は現コードと整合した。新しいprobeは作っていない。

W04へ次の補足を要求:

- `AnalysisStore.read_artifact:304–312`のDB sha256照合は**保存時bytesとの整合性**を検証する。「真正性」という語で発信者の真正性・攻撃者に対する保証まで含めない
- `evidenceDetails:45–73`は欠落引用IDを`:58`でskipし、欠測時刻を`:62`で0へ寄せる。新viewerが要求する「引用欠落を明示」「欠測時刻を0秒としない」は既存factory無変更では満たさない
- `openInsightMedia:86–90`は数値差を比較するがNaN/欠測を明示拒否しない。固定viewerの原音guardは、保存時／現在の双方の時刻が有限かつvalidであることを先に確かめる必要がある。text/speaker/time一致、target ID、run文脈はadapterで明示し、既存live-state依存をそのまま持ち込まない

これは固定viewerの設計依存の指摘であり、現行GUIで誤seekや欠落表示を実観測した記録ではない。既存artifact payloadとAPIのfield位置は `services/analysis_archive.py:60–103`、`analysis_store.py:315–321,400–423` に照合済み。
