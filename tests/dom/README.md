# オフライン DOM 統合検証

この層は **DOM ライブラリによる統合テスト**。ブラウザー／視覚／AT の検証ではない。
実 `index.html` と include 群を Jinja2 で展開し、HTML に記載された順番で全 project JS を読み込む。
関数をソースから抜き出さず、同一 jsdom realm の実 selector、イベント、FormData、handler を通す。
既存の高速 mock/source contract と Python suite は維持し、この層は別 command で明示実行する。

## 実行

Node は jsdom の要求する `^22.22.2 || ^24.15.0 || >=26.0.0`、Python は Jinja2 が必要。
既存 project Python を指定できる。アプリ／モデル／DB は import せず、サーバーも起動しない。
アプリ root から:

```sh
npm ci --prefix tests/dom --ignore-scripts --registry=https://registry.npmjs.org --cache ../npm-cache --no-audit --no-fund
GURUMOJI_TEST_PYTHON="$(pwd)/../app/.venv/bin/python" npm test --prefix tests/dom
```

通常は対象 checkout の `.venv/bin/python` を指定する。上は sibling main の venv を利用する cloud worktree 例。
Windows 等では環境変数と Python path を使用 shell に合わせる。
`GURUMOJI_TEST_PYTHON` 未指定時は `python3`。
インストール済み dependency が揃えばテスト本体は完全にオフライン。

独立した修正版 worktree を検証する場合は `GURUMOJI_DOM_SOURCE_ROOT=/absolute/trusted/worktree` を追加する。
HTML と JS はすべて同じ source root から取得し、harness/package はこの checkout を使う。
対象の `git rev-parse HEAD` と `git status --short` を証跡へ併記する。
任意の外部 HTML や未信頼 JS を source root に指定しない。

## 依存と安全境界

- `tests/dom/package.json` は private、jsdom **30.1.1** の dev dependency のみ。アプリ runtime dependency ではない
- lockfile v3 は全 transitive version／integrity を固定。node_modules はローカル ignore、commit しない
- 配布元は official npm registry、jsdom 本体 integrity は `sha512-FahmoPK5vbPc+jxV1iErMHmAZypCZ942NHF4+qqaWAuvaKKTBZxawnmAtrbGWLU7MtlxfqIP0qw6aSI+aWGtLg==`
- upstream 文書: https://github.com/jsdom/jsdom （インストール済み `node_modules/jsdom/README.md` も30.1.1の仕様確認に使用）
- `runScripts: outside-only`、resources 未指定。外部 script/style/media/frame を読み込まない。trusted project JS のみ `vm.Script` と `getInternalVMContext()` で評価する
- `global.window` 等の Node global 差替えはしない。fixture は JSON として DOM realm に parse し、本文／結果文字列をコードとして eval しない
- fetch は同一 synthetic origin の `/api/` fixture のみ。外部宛ては禁止。XHR/WebSocket/EventSource/sendBeacon も禁止。現実の network implementation に委譲する経路はない
- teardown は全 intercepted API が fixture で回答されたこと、禁止 API 呼出しゼロ、jsdom error ゼロを確認する。API payload は synthetic のみ。実 API／Vault／model／auth には接触しない
- hostile text は literal text/value と禁止 element/event attribute/unsafe URL が存在しないことを確認。outside-only で inline script が動かないことだけを成功基準にしない

## 明示的な代替 API と未検証範囲

- matchMedia は desktop false match の固定値、scroll/scrollIntoView と media load/pause/play は無処理
- dialog.showModal/close は open と close event だけの semantic shim。top layer、modal focus trap、背景 inert、native Escape、native keyboard、focus の視覚表示は検証していない
- setTimeout/setInterval/rAF は記録して自動実行しない。boot animation、polling、実時間 timeout、layout、rendering、responsive、browser navigation、AT 読上げは保証しない
- confirm は fixture 内で true。Headers と fetch response は test-owned 最小 adapter。実 transport、abort、HTTP、権限を保証しない
- `.click()`、synthetic change/input/submit は DOM event wiring の検証。人の native 操作、非表示要素への実クリック可能性、browser accessibility の代用ではない

## ケース

`npm test` は下記の `*.test.cjs` をすべて実行する。修正版の境界受入も既定経路に含める。

- `integration.test.cjs`: 4カードの実 mode handler と simple/detail の独立値・FormData、role確認と detached control、Save 成功/409/500/二重押し/後続編集/別item/ABA、本文の literal 表示、fixed run lookup/history/preview と stale response、malformed identity/integrity/artifacts、table/metadata/encoded artifact URL
- `boundaries.test.cjs`: prototype名を含む話者ID、role以外も含む話者control名/再描画focus、固定runの移動・取消・遅延応答、履歴URI/同一runの更新、時刻不明・真のゼロ・部分的な時刻カバレッジ
- `navigation.test.cjs`: 実popstate listenerの応答順2通り、読込中に新規画面へ移動、未保存移動取消、tablistのsynthetic keydownとclick。ブラウザーのBack/Forwardやnative keyboard試験ではない
- `analysis-save.test.cjs`: 実Saveとitem selector経由のB/ABA遷移、200/409/500、正常保存、保存中の追加編集。未修正ソースでは所有権回帰が失敗するため、source commitと合否を必ず併記する
- `fixed-save.test.cjs`: live Save完了と固定run読込/previewの競合。lookupは実mode/export導線から開き、固定modalがloadingのまま、または表示済みcontrolが無反応で残らないことを検証する
- `fixed-version.test.cjs`: 同じsource rootのpure saved-summary projectionから合成保存値を生成し、実lookup→modalで計算版・手法registry版・算法一覧を照合。v4/v5/v6、欠落、矛盾、数値0、非scalar/bool、hostile text、長文・共有16 KiB上限を検証。`project_saved_summary.py`はquery moduleとregistryのみを読み、app／DB／serverは起動しない
- `measurement.test.cjs`: 実Settings・簡単/詳細・input/change・Save/Trial/Confirm/Adopt・form submitで手動測定を受入。固定した計画payload、二重押し、再試行確認失効、response喪失後の読取確認、409、modal再open/navigationを含む。storage拒否は起動後のsimulationで、privacy-mode起動試験ではない
- `measurement-save.test.cjs`: live Save中にSettingsを開く場合の入力版更新、編集した定義文言/未送信IDの保持、採用済み定義の保護分岐、実Saveの再開、追加の未保存分析編集による操作制限を確認する
- `analysis-time.test.cjs`: nullableな分析API値をoverview・話者一覧/詳細・属性groupへ渡し、実scope/話者選択のhandlerで欠測/部分小計/真のゼロ/完全観測を区別。v5 backend由来の合成fixture subsetも使用し、null割合を0%のARIA画像へ変換しないことを確認する
- `mixed-role.test.cjs`: v6 backend合成fixtureの最小投影を使い、役割混在を人数不明・role依存指標の非算出として表示しつつ、全観測話者集合の50/50・Gini0・全体20秒/各10秒を保持。実scope/話者/並べ替えhandler、編集enum非追加、非混在の合成対照を含む。fixture出典・hash・派生条件は `fixtures/mixed-role-provenance.json`
- `remaining-timing.test.cjs`: v7 backend合成fixtureの最小投影から、全sourceの最終終了位置とincluded発話時間のcoverage、感情・コードのnullable時間/部分小計/真のゼロ、空timeline、真0イベント保持を実mode/page handlerで照合。コードbarの件数尺度と表示前後のAPI値を保持
- `library-timing.test.cjs`: 同じbackend由来のjob投影を一覧card・上部合計・実analysis item selectorへ渡し、null終端/部分観測/真0/既知終端を区別。集計では既知小計と欠測ありrecord件数を明示
- `timing-editor-limit.test.cjs`: backendの31日上限を超える時刻・finite1e308・上限超過の真0が参加比率/警告へ入らないこと、上限丁度の1秒/真0は保持すること、実Save payloadでraw時刻をclamp/coerceしないことを検証
- `timing-projection.test.cjs`: full GETのsource binding付きread-only時刻投影でASCII/全角/Arabic/underscore/指数/空白付き数値と真0を保持。実start/end change、削除/Undo、ID/原値/順序/件数/重複/不正projectionのfallback、legacy数値fallback、Saveに派生投影を混入せずraw型を保持することを確認。音声guardの緩和はしない。普通のoutput-JSON importから取得したfull DTOも使用し、Pythonでfalseになる空配列/空object markerのnumeric/string/真0、実時刻編集、raw markerのSave payload保持、非空/type-changeのstale bindingを確認
- `harness.test.cjs`: 起動fixture、realm分離、JSON文字列のliteral保持、fixture応答、外部fetch/XHR/WebSocket/EventSource/beacon拒否、未回答APIの失敗検出、timer/dialog shimの限定された意味

旧版negative controlも同じ期待値で、信頼できる旧commitを別ディレクトリーに展開して明示source rootで実行する。旧版での既知不具合を成功条件にしない。

```sh
GURUMOJI_TEST_PYTHON=/absolute/python GURUMOJI_DOM_SOURCE_ROOT=/absolute/old-source \
  node --test tests/dom/boundaries.test.cjs tests/dom/navigation.test.cjs
```

他担当が修正中のworktreeを検証する場合は、そのcommitの `git archive` 等による読み取り専用snapshotをsource rootに使い、対象版がsuiteの途中で変わらないようにする。

`probe-regressions.cjs` は診断 JSON を出すだけで pass 判定しない。旧版で発見した prototype key、speaker control name/再描画、modal navigation の証跡を保存する用途。既知不具合を期待値として passing test に固定しない。
追加受入テストも `*.test.cjs` に置き、対応 commit を検証記録に残す。
