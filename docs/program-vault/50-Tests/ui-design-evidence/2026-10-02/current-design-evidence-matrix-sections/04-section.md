---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix-section-04
title: Gurumoji デザイン監査・証拠対応表：DG-06 現在データと固定runの由来を主画面で継続表示する
summary: DG-06 現在データと固定runの由来を主画面で継続表示する。出典ノート「Gurumoji デザイン監査・証拠対応表」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix
source_path: 50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md
source_sha256: 802a60c49581ed2fa58b53e0f6cf7c89e53cf3b8245598118fa442eccfa049cc
source_body_lines:
- 85
- 117
split_on: '2026-10-11'
---

# Gurumoji デザイン監査・証拠対応表：DG-06 現在データと固定runの由来を主画面で継続表示する

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix]]。必要な本文だけを取得する。

### DG-06 現在データと固定runの由来を主画面で継続表示する

- 優先度: P2
- 根拠: `src/gurumoji/static/app.js:5757-5775,5791-5814`、`src/gurumoji/static/analysis-storage.js:43-69`、`src/gurumoji/static/analysis-execution.js:316-325,651-655`、`src/gurumoji/static/analysis-content.js:45-72,76-122`
- 影響: 対象バーは名前・発話数・更新時刻が中心で、固定runの入力版やIDは履歴の内側にある。研究者が過去の根拠と現在編集済み本文を往復する際に、表示物の版を読み直す負荷が高い。
- 最小案: 共通の結果コンテキスト帯に対象、表示版、算出日時、対象/除外数、fresh/stale、runを短く表示。hash等は詳細へ。完了画面からその固定runを開く入口を設計し、通常データ再集計との違いを明示する。
- 受入:
  - 旧runを開いたまま本文が更新されても、旧入力版/古い結果の標識が消えない
  - 生成時点引用と現在本文を区別し、古い引用から現在音声へ黙って飛ばない
  - CSV/JSON/ZIPのrun・入力版と画面を照合できる。legacy不明値は不明のまま表示

### DG-07 狭い画面で選択中の分析ページ名が横スクロール域外に残り得る

- 優先度: P2
- 根拠: `artifacts/ui-review/local-evidence/extracted/screenshots/analysis-statistics-390.png`、`src/gurumoji/static/analysis-visualizations.js:995-1031`、`src/gurumoji/static/style.css:1323-1326,1950-1951,2332-2334,2362`
- 影響: ページ内容は切り替わっても、現在のページ名を読み取れず戻る場所を見失う。document全体の横はみ出し検査だけでは検出できない。
- 最小案: 選択ナビ項目をnearestで表示域内へ収め、前後に項目があることを示す。320pxでは主題選択を1行select/メニューに切り替える案も実測比較。
- 受入:
  - 390px/320px/200%拡大で最右ページ選択後も選択された項目のラベル全体とfocusを視認できる。全nav項目の同時表示は要求しない
  - 選択後の自動スクロールはナビ領域だけ。本文・入力中の位置を不用意に動かさない
  - 戻る/進む、根拠から復帰、画面幅変更でページとナビ選択が一致する

### DG-08 作成・分析以外の文字サイズと密度を共通役割へ揃える

- 優先度: P2
- 根拠: `src/gurumoji/static/style.css:12-35,209-228,785-794,837-858,1049-1056,1590-1605,2305-2341`、`src/gurumoji/templates/views/speakers.html:16-34`
- 影響: rootの--text-min=.7rem、会話話者表入力=.72rem、作成のラベル=.9375rem、分析本文=.875remと役割基準が分かれる。長い日本語や頻繁な照合作業で読み直しが生じる可能性。
- 最小案: 本文/操作label/補助/数値/コードを定義し、まず通常本文16px相当、操作label14〜15px相当、補助13px相当を候補として実画面比較。これは製品方針でありWCAGの最低font-size要求ではない。密度は一律拡大せず、入力表の列優先順位と詳細開閉で調整。
- 受入:
  - 日本語長文、長い氏名、長いファイル名を100/200%で確認し、主操作・必要情報を失わない
  - 本文行間1.6〜1.8の候補比較。固定heightで文字が切れず、text-spacingの上書きで機能喪失なし
  - Windows Yu Gothic UIと代替font環境で同じ役割階層が成立する
