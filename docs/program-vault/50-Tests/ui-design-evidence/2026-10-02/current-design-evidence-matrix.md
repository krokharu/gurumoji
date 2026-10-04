---
note_id: "ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix"
note_type: "design-evidence"
title: "Gurumoji デザイン監査・証拠対応表"
summary: "2026-10-02の研究・設計・検証記録の保存版。提案や静止図を実装・操作合格へ置き換えない。"
status: "current"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
tags: ["gurumoji/design", "gurumoji/ui"]
---

# Gurumoji デザイン監査・証拠対応表

対象: `ddc23abe` / code `59ebd24`。原25件の受入表は変更しない。S=局所、M=複数部品、L=段階導入。日数は概算であり約束ではない。

| ID | 優先度 | 分類 | 結論 | 確度・規模 | 既存指摘との関係 |
|---|---|---|---|---|---|
| DG-01 | P1 | 現行コードで確認した導線不整合 | 個別のTransformer・AI見解・発話分類の実行入口がCSSで非表示 | 高（ソース。現行実ブラウザー未確認）／S〜M：1〜2日＋既存送信確認・取消の回帰 | 原25件とは別。旧統合実行UIと新しい基礎pipelineの境界 |
| DG-02 | P1 | 現行コード＋分離関数再現 | 手動測定の規則・試行採用・固定した定義版の保証が不足 | 高（Node合成DOM。実UI未確認）／M〜L：UI 2〜4日＋定義版/試行契約/競合回帰3〜5日の再見積り候補。単純な前面改修だけでは閉じない | 原25件とは別。M0〜M7の手入力定義フロー |
| DG-03 | P2 | 現行コード＋分離関数再現 | 失敗した分析の主見出しが「分析を実行しています」のまま | 高（Node合成DOM。実UI未確認）／S：半日〜1日＋状態別回帰 | 原25件とは別。新pipelineの状態表現 |
| DG-04 | P2 | 既知未対応の再確認 | 保存履歴の直近100件上限がUIに出ず、古いrunへ進めない | 高（ソース。今回のDB再実行なし）／S：上限説明／M：1〜3日でcursor付き履歴 | 既存UX-34。新しい発見として数えない |
| DG-05 | P2 | 既存設計の段階導入提案 | 分析の入口が作業目的と分類方式を混在させている | 高（現行構造）／改善効果は要利用者検証／M〜L：1〜2週、互換維持し段階導入 | ADR-118 accepted未実装。旧UI課題の再命名ではなく実装計画へ接続 |
| DG-06 | P2 | 表示設計の改善提案 | 現在データと固定runの由来を主画面で継続表示する | 高（表示場所）／誤認発生率は未測定／M：2〜4日。既存revision/run情報を利用 | A04/A05/A11/A12は修正済み。来歴欠落/誤出力の再指摘ではない |
| DG-07 | P2 | 旧版視覚所見＋現行コードの確認候補 | 狭い画面で選択中の分析ページ名が横スクロール域外に残り得る | 中。旧4b311df画像では確認、現行実画面は未確認／S：半日〜1日＋幅/拡大回帰 | 旧UI評価のS5改善候補。原UI-01〜10に追加していなかった項目 |
| DG-08 | P2 | 既知可読性課題の残存範囲整理 | 作成・分析以外の文字サイズと密度を共通役割へ揃える | 高（CSS指定値）。現行描画の可読性は未測定／M：2〜4日、画面単位で検証 | UX-17/41の改善を維持。全て小さい/未修正とはしない |
| DG-09 | P2 | CSS指定値の数値検証 | 補助文字・未保存色・共通focusのコントラストを用途別に補正する | 高（指定色の計算）／適合判定はcomputed styleと実画面待ち／S：半日〜1日＋全state回帰 | UX-19は既知未対応。UX-24のfocus有無修正は維持 |
| DG-10 | P2 | 現行ソースで確認したaccessible name不足 | 相互作用リンクの対象・関係selectに名称がない | 高（生成コード）。支援技術実測は未実施／S：半日＋名前/キーボード回帰 | 原UI-10（保存通知/tabpanel）とは別の部品 |
| DG-11 | P2 | 現行UI文言の境界不足 | 「結果を公開する」の保存先と含むデータを明示する | 高（template/payload）／S：半日〜1日＋公開OFF/競合回帰 | 原UI-09のOS/保存先修正は維持。新pipeline公開optionの補足 |
| DG-12 | P3 | 設計整備と回帰基準 | motion低減とfocus/scroll復元を共通の操作契約にする | 高（呼出混在）。体感/支援技術は未測定／S〜M：1〜2日＋入力/ナビ横断回帰 | 既存reduced-motion、focus-visible、根拠位置復元は実装済み |
| DG-13 | P2 | 設計文書の現行差分 | 6段階/client説明とM0〜M7/server実装を同期する | 高（文書・コードの直接比較）／S：半日。実装変更なし | DESIGN.md作成の前提。設計書のcurrentラベルを実装の証明にしない |
| DG-14 | P3 | 旧画像からの改善仮説 | 空状態・概要・詳細の縦方向密度を主作業に合わせる | 中。旧4b311df画像の所見。現行比較待ち／S〜M：1〜2日で試作・現行比較 | UX-07/35〜42の既存改善を保護。全面レイアウト不良とはしない |

## 項目別の証拠・最小変更・受入

### DG-01 個別のTransformer・AI見解・発話分類の実行入口がCSSで非表示

- 優先度: P1
- 根拠: `src/gurumoji/templates/index.html:235-236`、`src/gurumoji/static/style.css:2088-2093`、`src/gurumoji/static/analysis-content.js:184-187,561-564`、`src/gurumoji/static/analysis-method-view.js:254-264`、`src/gurumoji/static/analysis-execution.js:560-594`、`src/gurumoji/analysis_core.py:80-100,314-330`、`src/gurumoji/static/app.js:6760-6769`、`artifacts/design-sprint-20261003/adversarial-checks.md:H1`
- 影響: 画面の説明に従って移動しても実行ボタンが見つからず、設定やモデルの問題と誤認する。保存済み結果の表示やAPIの存在と、利用者が新規実行できることは別。
- 最小案: 基礎分析・テーマ分析・AI見解・分類それぞれの入口、実行条件、送信先、取消、現在の状態を能力表にする。まず対応済みの個別入口を明示復帰させるか、同じ確認パネルへ接続。実装していない統合runnerへ誘導しない。
- 受入:
  - 実DOMで通常表示・computed visibility・操作可能領域を確認する。role/nameからマウスとTab/Enterで入口へ到達できる。JS評価によるhidden要素.click()を合格根拠にしない
  - 条件不足では理由と設定入口を表示する。適格fixtureでは個別処理の確認まで進み、未承認の外部送信を行わず取消できる
  - 基礎分析ボタンだけでTransformer等も実行されたと表示しない。API/mock・CPU実モデル・外部API実行の受入を分ける

### DG-02 手動測定の規則・試行採用・固定した定義版の保証が不足

- 優先度: P1
- 根拠: `src/gurumoji/templates/index.html:243-249`、`src/gurumoji/static/analysis-execution.js:50-64,80-92,542-557`、`src/gurumoji/analysis_core.py:151-187`、`artifacts/design-sprint-20261003/static-design-probes.json`、`artifacts/design-sprint-20261003/adversarial-contract-probes.json`、`src/gurumoji/analysis_pipeline.py:45-50,209-280,332-365,494-499,635-644`、`src/gurumoji/analysis_core.py:346-369`、`artifacts/design-sprint-20261003/definition-lifecycle-probe.py`、`artifacts/design-sprint-20261003/definition-lifecycle-probe.json`、`artifacts/design-sprint-20261003/definition-full-pipeline-probe.py`、`artifacts/design-sprint-20261003/definition-full-pipeline-probe.json`、`artifacts/design-sprint-20261003/definition-lifecycle-evidence-manifest.json`
- 影響: 名前・説明を任意に書ける一方、測定対象はtext、規則text_length、数値・比率尺度・記述統計へ固定される。利用者が説明文を実行ルールとして受け取ると研究上の測定内容を誤認し得る。試行件数の表示後に採用へ直行するため、判断の区切りも見えない。 追加確認では、同じIDのdraft保存が旧adopted行を置換し、受付bindingにv1があってもworkerは同ID最新v2を読み得る。実UIの明示採用だけでは固定版保証が成立しない。
- 最小案: 入力列・規則・型・尺度・手法を対応範囲内で選択または読取専用要約として明示。『少数で試す→例と欠測・限界を確認→この定義を採用→全件実行』を分離。説明文は計算規則ではないことを示す。未提供のLLM尺度生成を装わない。 技術依存として、試行個票/欠測理由/定義版、編集中draftと旧adopted版の分離、受付したdefinition version/hashによる厳密な解決を追加する。最小安全策は版不一致時に計算前で停止し、将来のsnapshot/不変版方式を別途設計する。既存SQLの破壊的変更はしない。
- 受入:
  - 4入力だけを変更したときも、実際の規則が文字数であると開始前に読める
  - durationとtext_length、名義尺度+frequency等の対応組合せを正確に送信し、不適合は該当欄へ具体的理由を関連付ける
  - 試行終了時はdraft/trial-reviewed相当の表示に止まる。明示採用前にadopted PUT・pipeline POSTを送らない
  - 採用済み定義のrevisionと画面の測定要約が一致し、変更後の再試行・取消で旧採用版を壊さない
  - 同ID adopted v1→draft v2保存→取消/試行失敗でもv1を引き続き選択・再現でき、v2は未採用のまま分離される
  - 受付binding v1(text_length)→実行前に同ID v2(duration)へ更新する競合fixtureで、v1値3を使うか計算前に明示停止する。v2値60をv1としてcommitしない
  - trial結果にsampleのsegment ID/入力例/測定値/欠測理由/definition versionまたはhash/input hashが揃い、定義か入力の変更後に旧trialを採用根拠として流用しない
  - 採用・固定版のUI受入、API/SQLite競合回帰、全pipeline再開/再試行/公開を別々に検証する。分離manual stepの成功を全pipeline合格へ拡大しない

### DG-03 失敗した分析の主見出しが「分析を実行しています」のまま

- 優先度: P2
- 根拠: `src/gurumoji/static/analysis-execution.js:393-476`、`artifacts/design-sprint-20261003/static-design-probes.json`
- 影響: 失敗理由と再試行は存在するが、最大の見出しは継続中を示す。waitingも一律「再開できます」で、利用者の入力が必要な理由と処理回復を区別しにくい。通常結果への背景導線があるため、全結果へ到達不能とは判断しない。
- 最小案: 実行状態の文言表を1つ持ち、見出し・現在段階・チップ・操作・live通知を同じstateから導出。failed=停止/失敗、waiting=必要条件、cancelling=中止要求済み、cancelled=中止済み。完了済み成果と未完成部分を別枠で示す。
- 受入:
  - accepted/running/waiting/failed/cancelling/cancelled/completedをすべてfixtureで表示し、相互に矛盾する見出しや主操作がない
  - 公開だけ失敗なら公開のみ再試行。既存計算・外部AIを再実行しない
  - 停止後の完了済み結果へ到達でき、再試行・設定変更・確認待ち解除の違いを説明できる

### DG-04 保存履歴の直近100件上限がUIに出ず、古いrunへ進めない

- 優先度: P2
- 根拠: `src/gurumoji/analysis_store.py:274-296`、`src/gurumoji/static/analysis-storage.js:27-85`、`docs/program-vault/40-Design/ui-ux-issues.md:127`
- 影響: 100件を全保存数と解釈しやすい。過去の研究結果をUIで探し直せない。成果物削除ではない。
- 最小案: 短期は『直近100件を表示』と明示。次に総件数・次ページ・日付/手法/状態絞込を既存履歴へ追加し、安定したcreated_at+id順序で全runに到達させる。
- 受入:
  - 0/1/100/101件で上限・総数・ページ境界を区別する
  - 同時刻を含む201件でページ間重複/取りこぼしなし。選択したrunのID・入力版・出力が一致する
  - 比較履歴にも同じ上限表示・ページング契約を適用する

### DG-05 分析の入口が作業目的と分類方式を混在させている

- 優先度: P2
- 根拠: `src/gurumoji/templates/index.html:46-50,79-81`、`src/gurumoji/templates/views/analysis.html:111-139`、`src/gurumoji/static/app.js:1156-1206,5920-5959`、`src/gurumoji/static/analysis-visualizations.js:1014-1031`、`docs/program-vault/40-Design/decisions.md:401-407`
- 影響: 上部とサブナビに同じ分析入口があり、その下に自動/手動/手法別、全体/話者、概要〜出力が重なる。『結果を見る』『定義を変える』『比較する』の仕事から入口を予測しにくい。
- 最小案: 上部4入口は当面維持し、処理済みデータの重複サブナビを文脈ナビへ整理。分析内はADR-118の結果/比較/計画/データ・出力へ段階移行し、手法別は結果のfilter、手動コードは解釈作業として配置。
- 受入:
  - 既存#/new,#/data/<id>,#/analysis/<id>,#/speakersとquery形式の根拠リンクを維持
  - 保存済み結果を見るだけで計算/外部送信なし。以前のタブに戻って検索語・選択対象・未保存draftを保持
  - 初見テストで5代表タスクの最初のクリック、戻り回数、完遂/失敗を比較し、提案の優位性を実測する

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

### DG-09 補助文字・未保存色・共通focusのコントラストを用途別に補正する

- 優先度: P2
- 根拠: `src/gurumoji/static/style.css:14-32,41,535,941-945,1052-1055,1580-1582,1635,2274,2313`、`artifacts/design-sprint-20261003/specified-color-contrast.json`
- 影響: cascade確認後の通常drop-zoneは背景white（1635/2274）で、#8a948fとの比率3.128:1。登録話者概要の未保存orangeはgradient上2.627〜2.759:1。保存バーは半透明のため実背景計算が必要。35%緑focus outlineは明背景との合成例で約1.7:1。一方、analysis sidebarの未保存#97451dは#f2f5ef上5.992:1であり同列に問題扱いしない。
- 最小案: 既存green/ink/paperを保ち、warning-text、muted-text、focus-ringを用途別にする。装飾のorangeを重要な文字へそのまま流用しない。focusは不透明で十分識別できる色を使う。
- 受入:
  - 通常の必要な小文字は実背景上4.5:1、必要な非テキスト状態表示は3:1を基準に測定する。disabledなど例外を通常文字と混同しない
  - hover/selected/stale/unsaved/error/high-contrast等を個別に確認。色だけで状態を区別しない
  - focusの境界と隣接背景、stickyで隠れないことをキーボード実操作で確認し、outlineの存在だけで合格にしない

### DG-10 相互作用リンクの対象・関係selectに名称がない

- 優先度: P2
- 根拠: `src/gurumoji/static/app.js:7317-7347`
- 影響: 2つのselectがlabel/aria-labelなしでdivへ追加される。対象発話と関係のどちらを選んでいるか、支援技術で区別しにくい。根拠メモinputはplaceholderの名前fallbackがあり得るため無名と断定せず、見えるlabelの改善対象とする。
- 最小案: 対象発話・関係・根拠メモを見えるlabelで結び、同じ発話のfield groupとして伝える。追加後はリンク一覧の新規行へ適切に通知し、入力を勝手に失わない。
- 受入:
  - Accessibility treeで各select/inputに一意で内容の分かるnameがあり、現在の発話文脈を確認できる
  - Tab/矢印/Enterのみで対象と関係を選び、追加・取消・削除できる
  - NVDA/Edge等の実読み上げを記録し、DOM属性だけを音声受入の代わりにしない

### DG-11 「結果を公開する」の保存先と含むデータを明示する

- 優先度: P2
- 根拠: `src/gurumoji/templates/index.html:267-268`、`src/gurumoji/static/analysis-execution.js:569-578`、`src/gurumoji/analysis_core.py:290-292,321-328`
- 影響: 利用者はWeb公開、外部AI送信、設定済みVaultへの書出しのいずれかを短いラベルから判断できない。実際のpayloadはinput/orchestrator/visualizationの3生成Vaultを対象とする。
- 最小案: 『設定済みの3つのVaultにも保存する』のような実態に即すラベルと、Vault名/実行環境/含む成果物/失敗時の回復を表示。保存先が未確認なら不明・未設定を明示する。
- 受入:
  - OFFではpublication_targets=[]、ONでは選択された実際の保存先が画面とpayloadで一致
  - 外部AI送信とVault書出しを別の確認として理解できる
  - 本体保存成功+Vault conflict/failed時に二軸の状態を出し、公開のみ再試行できる

### DG-12 motion低減とfocus/scroll復元を共通の操作契約にする

- 優先度: P3
- 根拠: `src/gurumoji/static/style.css:41-43,2079-2085`、`src/gurumoji/static/app.js:2212,5562,5579,8155-8156`、`src/gurumoji/static/analysis-content.js:76-122`
- 影響: CSS htmlのsmoothと直接smooth指定、motion-aware helperが混在する。画面再描画・根拠復帰でscrollとfocusを別々に扱っており、視点の復元品質を一括確認する必要がある。
- 最小案: 位置復元は対象ID+選択ページ+scroll+focus起点を記録し、reduced-motion下はscrollも即時。focusが消えたときは同じ項目/節の意味ある位置へ戻す。
- 受入:
  - motion低減ONでもナビ・削除undo・根拠遷移・発話追加に必要な位置移動は行うが、smoothなスクロールanimationは行わない
  - 根拠を開いて閉じると同じrun/ページ/引用とfocus起点へ戻る
  - 320px・200%拡大・ソフトキーボード表示中に入力focusや保存feedbackを固定バーが完全に覆わない

### DG-13 6段階/client説明とM0〜M7/server実装を同期する

- 優先度: P2
- 根拠: `docs/program-vault/20-Modules/ui-screens.md:20,28-43`、`docs/program-vault/40-Design/analysis-execution-ux-plan.md`、`docs/program-vault/40-Design/analysis-milestone-visualization-design.md:19-34`、`src/gurumoji/static/analysis-execution.js:1-12,439`、`src/gurumoji/analysis_core.py:80-101`
- 影響: 後続開発で既存pipelineを再実装したり、基礎pipelineがTransformer/推測統計まで扱うと誤解する危険。現行URL/入口の説明も3タブと4タブで差がある。
- 最小案: DESIGN.md冒頭にcommit付き現行能力・実装済み・未提供・受入待ちを置く。古い計画は経緯として残し、現行節へリンク。UI-10件partialを未実装へ戻さない。
- 受入:
  - M0–M7、基礎2手法+手動測定、JSON/CSV/ZIP、3生成Vaultと未提供出力の境界がコードと一致
  - 既存APIからのXLSXとpipeline固定packageのXLSX未提供を区別する
  - 旧25件と新DG項目が重複計上されず、各提案にsource/decision/testのリンクがある

### DG-14 空状態・概要・詳細の縦方向密度を主作業に合わせる

- 優先度: P3
- 根拠: `artifacts/ui-review/local-evidence/extracted/screenshots/speakers-390.png`、`artifacts/ui-review/local-evidence/extracted/screenshots/analysis-statistics-390.png`、`src/gurumoji/templates/views/speakers.html:16-34`、`src/gurumoji/static/style.css:938-958,2337-2346`
- 影響: 旧390px画像では話者の入力カードより前に概要・案内・検索が並び、統計はデータ不足の大きなカードが連続する。重要な安全説明を削らず、作業開始までの距離を減らす余地がある。
- 最小案: 話者の追加後は追加カードを表示域/focusへ。概要は必要な件数と未保存状態を短くまとめる。空の分析は理由・必要条件・次の行動を1つのコンパクトな状態部品で表現し、空カードを単純羅列しない。
- 受入:
  - 0件/1件/多数件、検索0件、全データ欠測を別fixtureにし、次操作が具体的
  - 警告と分母・欠測条件を折りたたみ過ぎて隠さない
  - 同一viewportのbefore/afterで主作業到達スクロール量・行動数を比較し、改善を測定する

## DG-02の内訳と数え方

上位監査IDは14件のまま。DG-02-U1/U2は元のUI指摘を分解したもの、T1は必要な試行契約、T2/T3は独立に再現したP1技術課題。原25件へ合算せず、T2/T3をUI文言問題だけに埋めて過小報告もしない。

### DG-02-U1 / P1 / 既存DG-02のUI意味不整合

構造化規則の5selectorがなくtext_length/number/ratio/descriptiveへ暗黙固定

根拠: `static-design-probes.json`, `adversarial-contract-probes.json`

### DG-02-U2 / P1 / 既存DG-02の採用操作不足

少数試行後に研究者の値レビュー待ちなしでadoptedへ進む

根拠: `src/gurumoji/static/analysis-execution.js:542-557`, `static-design-probes.json`

### DG-02-T1 / P2 / 試行レビュー実装に必要なAPI契約拡張

trialはinput_hash/values/件数のみ。segment ID付き個票・欠測理由・定義revision/hashがなく、根拠付き試行レビューを現APIだけで完全には作れない

根拠: `src/gurumoji/analysis_pipeline.py:258-280`

検証範囲: ソース確認。豊かなレビュー表示の依存であり、個票UIが既に存在するという主張ではない

### DG-02-T2 / P1 / 独立再現した採用版保全の技術課題

同IDのadopted v1→draft v2で同じDB行のpayload/statusを置換。旧adopted版をこの定義台帳から選べなくなる

根拠: `src/gurumoji/analysis_pipeline.py:45-50,227-256`, `definition-lifecycle-probe.json:existing_adoption_after_draft_save`

検証範囲: 合成in-memory SQLite。row count1、status draft、adopted lookup definition_not_adopted。既存出力や全履歴が消失したとは判断しない

### DG-02-T3 / P1 / 独立再現した固定定義版の実行不整合

binding v1受付後に同IDをv2へ更新するとworkerは最新v2を読み、v1の3文字ではなくv2の60秒を算出。合成adapters付き元M0〜M7でもcompletedとなり、save adapterへbinding v1とdefinitions v2が混在したpackageを渡す

根拠: `src/gurumoji/analysis_pipeline.py:209-225,332-365,494-499,635-644`, `src/gurumoji/analysis_core.py:346-369`, `definition-lifecycle-probe.json:definition_version_race`, `definition-full-pipeline-probe.json`

検証範囲: 第1証拠は元worker prefix+manual stepの分離実行。第2証拠は受付後scheduleを停止して定義を更新し、元M0〜M7オーケストレーター全体を実行。全段committed・pipeline completed、save adapterへbinding v1/definition v2/値60のpackage。method/save/publication adaptersは合成、SQLiteは一時領域。実保存ファイル/Vault/実手法/GUIは未実施
