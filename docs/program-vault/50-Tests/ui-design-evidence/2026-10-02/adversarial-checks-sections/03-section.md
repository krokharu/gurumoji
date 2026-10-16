---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks-section-03
title: 'Gurumoji デザイン監査の独立反証チェック：H4: failed状態の表示と出口'
summary: 'H4: failed状態の表示と出口。出典ノート「Gurumoji デザイン監査の独立反証チェック」の分割本文。'
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks
source_path: 50-Tests/ui-design-evidence/2026-10-02/adversarial-checks.md
source_sha256: fec531750b3b1eeb8616de26b52688a81b740a197d67d9f5682156883db2fd50
source_body_lines:
- 100
- 163
split_on: '2026-10-11'
---

# Gurumoji デザイン監査の独立反証チェック：H4: failed状態の表示と出口

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/adversarial-checks]]。必要な本文だけを取得する。

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
