---
note_id: test-ui-design-acceptance
note_type: test-plan
title: Gurumoji デザイン受入試験の検証範囲
summary: 設計資料v0.3の作業用正本。設計提案の採用・アプリ実装・UI受入は未完了。
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
---

# Gurumoji デザイン受入試験の検証範囲

対象 `ddc23ab` / 2026-10-02。これは現行テストの読解と次の受入条件案。ソース・テスト編集なし。sandboxを維持したブラウザー起動が制約で失敗したため、この巡回で実ブラウザー試験は実行していない。

## 最も重要な結論

「ブラウザー内でJavaScriptが通った」「DOMに文字列がある」「ポインターとキーボードで人がその操作へ到達できる」は別の証明。既存のhandler/描画回帰テストは残してよいが、人向けUIの受入には可視操作の層が必要。

## 現行fixtureの区分と迂回箇所

### 1. `tests/test_content_browser.py`

- `exercise_browser:37–262` は一時DB・合成音声・serverとブラウザーを組み合わせた広いintegration fixture。実stylesheetを読み込むことに価値がある
- `:71–91` はrun buttonのDOM `.click()`、radioの`.checked=true`、4欄の直接`.value`代入、form `.requestSubmit()`、result buttonのDOM `.click()`でmanual pipelineを試す。M0–M7のAPI/state/描画統合は検証できるが、controlが見える・重ならない・tabで着くことは保証しない。手動定義は文字数に整合する1例だけなので、誤ったルールfallbackを見逃す
- `:114–120` tab切替もDOM click。`hidden===false`はその要素の属性しか見ず、祖先非表示・CSS非表示・覆い被さりを判定しない
- `:131,147–148` detailsを`.open=true`にし、`[data-insight-generate]`へDOM clickを2回。**現行CSSでdisplay:noneの実行buttonでも通り得る具体的な見逃し**
- `:171–196` はKWIC入力を直接代入＋requestSubmit、証拠detailsを直接open、引用/戻るbuttonをDOM click。検索・元画面復帰のstateは試せるが、可視の検索/引用/戻る操作は未証明
- named tests: desktop/mobile evidence return、AI generation deduplication、unified execution、Vault link matching。全て同じdriverに依存する

### 2. `tests/test_browser_e2e.py`

- `test_real_browser_restores_the_active_job:45` は起動時復旧をDOMから確認する。復旧ロジックの試験として有効。操作到達性の試験ではない
- `test_ai_review_displays_reason_safely_and_restores_original_text:164` はprovider値/checkedを直接設定し、effort・復元buttonをDOM click。復元状態やescapeの試験と区別する
- `test_comparison_and_unsaved_navigation_regressions:256`、`:294–309`: 履歴retry、比較target、実行、保存、更新をDOM clickし、detailsを直接open。外側の比較detailsが初期閉でも人の展開導線を検証しない
- 同`:320–325`: `analysisCard.hidden=false`として、`aria-hidden=true`/`tabindex=-1`/CSS非表示の旧refresh buttonをDOM click。これは互換handlerのguard回帰であり、現行UI操作の受入に数えない
- `test_registered_ui_ux_fixes_work_in_a_real_browser:474`
  - `:494–530`: mode/fixed-speaker controlsへ直接代入、DOM click、イベント合成
  - `:532–575`: analysisStateとfetchを書き換え、dialogをshowModalしていないままadvisorの値を設定し`:549`でDOM click。**閉じたdialog内でも計画相談の描画は検証できる**。計画相談UIが利用できる証拠とは別
  - `:578–597`: Transformer進捗は任意のhostをbodyへappendしstateをrunning/completedへ変更。実データ取得・実行入口・正しいpanel上の進捗を検証しない
  - `:611–639`: cancelのdisabledをfalseにしてconfirmとfetchをstubしDOM click。確認分岐は検証、実running UIからのキャンセル導線は未証明
  - `:641–658`: keyboard eventをdispatch、focusを直接設定、showViewを直接呼ぶ。roving tabindex handlerは検証するがブラウザーTab順やnative Enter/Space activationは証明しない。現行4上部tabのうち配列は3つだけ
  - `:677–696`: loaded CSSとoutlineStyleを確認する良い補助試験。しかしsolidの有無だけでcontrast、clip、fixed barに隠れないことは証明しない
  - `:715–741`: dialog/model/settings展開のDOM click。寸法を確認している部分は描画の補助になるが、trigger自体のhit testingはない

### 3. `tests/test_transformer_content_browser.py`

- opt-in。`test_unverified_stale_truncation_invalid_candidate_and_kwic_mode_are_visible`
- `:41–64` はapp state、card helper、fetchをsynthetic stubに置き換える
- `:68–89` はpanelを直接bodyへappend、refresh関数を呼び、textContent・disabled・modeを検証。KWICも`runKwicSearch`を直接呼ぶ
- `:95–98`のHTMLはscriptだけで、**production style.cssを読み込まない**。警告文字列・属性・URL引数のcomponent contractは試せるが、可視性・layout・実panel位置を証明しない。H1のCSS非表示を発見できないfixture

### 4. `tests/test_ui_safety_browser.py`

- opt-in、synthetic network routing、production HTML/CSS、`chromium_sandbox=True`。独立した次段階の可視操作試験の良い基礎
- `:129–160` は実keyboard Tab/Enter/type、locator click/fillでedit/save/delete/undoする。`:191–236`のconflict/download、失敗表示、CSV preview/apply/saveもlocator操作で、DOM clickと同列に扱わない
- ただし`:120–123`の初期画面は`renderResult`を直接呼ぶため、libraryから対象を探して開く導線はcoverage外。`:143`の再読込も`openLibraryItem`直呼び
- `:162–177` のconfig/destinationは`setMobileStep(3)`、provider/checked直代入、internal summary関数をevaluateする。通信状態に応じた表示は試せるが、mobile wizardやAI設定の選択操作は未証明
- `:179–189`のdiagnosticsは`openSettingsPanel`直呼び、profile injection後のselect/resetはlocator経由。遅延responseの注入は妥当なfixtureだが、設定を開く入口は別に試す
- `set_input_files`はsynthetic fileを渡す安全なfixtureとして妥当。ただしファイル選択buttonのkeyboard/ポインター動作そのものは別coverage

### 5. `tests/test_ui_defaults.py`

- `:259–269`等はID、label文字列、script参照の存在をassertする。機能保持の小さなguardとして有効
- 手動測定の5つの欠落selector、computed style、accessible name、実操作を検証しない。static passをUI acceptance passへ繰り上げない

## 実行環境について

旧 `test_browser_e2e.py` に5箇所、`test_content_browser.py`に1箇所の `--no-sandbox` がある。この監査ではそれらを実行していない。既存の起動flagを理由にsandboxを解除しない。安全なbrowser-capable executorでproduction stylesheetを維持し、sandbox有効のtest runnerを使う。

## 修正後の受入シナリオ案

各テストはsynthetic source・保存済み状態・stub responseだけを使い、モデル実行や実私有データを必要としない。初期データとサーバーエラーの注入は許すが、**測定対象のユーザー操作の代わりに内部stateやDOM visibilityを書き換えない**。

### A. 個別実行の3入口

1. データ一覧から合成会話を開き、画面上の分析リンク、正しいsection/tabを実ポインターで選ぶ
2. 画面の案内文どおりにTransformer・AI見解・分類の各入口を発見できること。実際のAI panelが概要に残るなら案内もそれに一致すること
3. visible/enabled、非ゼロrect、祖先の非表示なしを確認し、通常locator clickを使う。force click、evaluate `.click()`、属性解除を使わない
4. route spyで想定APIが1回だけ、provider/対象版が正しいことをassert。二重操作、dirty状態、実行中、retry時もテスト
5. 同じ操作をkeyboardのみで行い、明瞭なfocus、button名、Enter/Spaceを確認。生成・中止のcontrolを実際のrunning画面で確認

### B. 手動測定の意味

1. 見える「基礎分析」→手動、labelで各欄へ到達
2. 文字数の正例に加え、duration/nominal frequencyの対応例を使う。出力名・説明・rule・type・scale・単位が表示とPOSTで一致すること
3. durationの本文文字数3/10、実時間60/2という対照データで、60/2を出力するか、限定文字数機能として明確に拒否・説明すること
4. 少数試行の個別値と欠測理由を確認し、採用が必要な設計ならその明示操作前にadopt/pipelineが発生しないこと
5. close/cancel/back後に同じ値が残る範囲、実行中二重submit、別definition ID・別itemへ変更後のrevision衝突、尺度とmethodの非互換を確認

### C. 実行状態と部分成果

1. UIの実行入口から開始し、stub APIのstatusを accepted → running → waiting/failed/cancelled/completedへ進める
2. failedを「実行中」と表示しない。cancelledで計画が進行中のような説明を残さない
3. 計算済み/公開だけ失敗のケースを分け、保存済み成果への可視導線とretry範囲を確認
4. 背景へ移動、job chip復帰、再読込、Back/Forward、別対象navigationをユーザー入力で行う。何を保持・何を再試行したかAPI spyで確認

### D. 履歴境界

1. 99/100/101/105件の合成一覧、日時同値のIDをseed
2. 現行の上限仕様を維持するなら「直近100件」の表示があること。総数/次pageを実装する場合は101件目へ通常操作で到達できること
3. 同じデータでcomparison historyとitem historyを別確認。前のページへ戻る、reload、並び順を確認
4. 一覧から省かれたIDの既知artifactリンクは取得可能であり、保存物が削除されていないことをAPI層で確認

### E. 名前・contrast・focus

1. 対象発話と関係selectはgetByRole/label相当で目的名から選べること。選択後も名前が現在値へ置換されないこと
2. 根拠memoは入力後もvisible labelが残り、accessible nameが適切。実ATで発話・role・valueを確認した場合のみAT検証済みと記録
3. computed foreground/background、祖先透明度、gradient、overlayを採取。初期・hover・focus・dirty状態別にcontrastを評価
4. focusはoutline単独でなくcontrol全体の有効指標を評価。global淡緑ringだけのlink/button、濃緑border、青outlineを分ける。fixed header/footerの下へ隠れないことも確認
5. 390/959/960/1440pxとzoom200%を最低の代表ケースとし、問題の出る境界には320px相当・400%も追加。見えていることと操作できることの双方を記録

## 成果報告の区分

- contract/unit: 純粋計算、入力検証、API payload、保存状態
- component rendering: synthetic DOM、警告文、属性、指定style
- browser operability: full production CSS +通常pointer/keyboard、外側のnavigationからの到達
- assistive technology: 実際のaccessibility treeとAT発話の確認

各項目にpassed/failed/not-runを別記し、環境理由で実行できなかったbrowser操作はstatic/Node成功で代替合格にしない。


## 2026-11-03 開始前の注意文と段落表示

- 対象: `krokharu/transcription-finish-20261102`、開始時HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。既存の多数の未コミット変更を保持し、警告文とその表示だけを編集。
- 判断: 注意文の句点連結をやめ、「設定が必要な項目」「開始時の確認事項」を箇条書きで表示。同じ内容の話者確認の注意はラベルをまとめる。「有効OFF」を平易な説明に置換し、OFFの注意はOFF選択時に限定。Hugging FaceとCUDAの案内、確認チェックの日本語も修正。
- 表示: 項目間の余白・行間を追加。PCの警告欄を0.82rem、上限50vh/480pxに調整。外部由来の文面はtextContentで表示。
- 検証: JavaScript 2ファイルのnode --check、Pythonのcompile、CRLFを考慮したgit diff --checkに合格。`GURUMOJI_EFFORT_SOURCE_ROOT`を対象作業先に設定し、既存effort-cards試験24件に合格。既存試験の照合文を今回の表示に更新。
- Edge検証: `tests/ui/finishing-readiness-browser.py --source-root <対象作業先> --output <対象作業先>/output/validation/readiness-copy-20261103`に合格。モデル・接続は合成応答で、ネットワーク要求は遮断。二重フォームを除いて本番テンプレートと同じ構造を使用。実CSSで1360px/390pxの見出し、重複統合、OFF条件、横はみ出しを確認し、両幅の警告画像を目視確認。ページエラーなし。
- 未実施: アプリ全体の実運用起動、実モデル・CUDA推論、Hugging Face認証・利用条件・ダウンロード、実支援技術。実データ・DB・Vault・認証設定は使用せず、ポートは開いていない。コミット・pushなし。


## 2026-11-03 ヘッダーの1行化と指定SVG

- 対象: `krokharu/transcription-finish-20261102`、HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。既存変更を保持し、`stitch-theme.css`のヘッダー規則と新規静的SVGのみ変更。
- 利用者指定により、ロゴ・ナビ・ツールを折り返さず1行に配置。狭い領域は横スクロールで項目を保持。スマートフォン幅ではロゴを縮小して版表示を省略。
- 指定元の`gurumoji-animated.svg`を同名の静的アセットとしてバイト一致で取り込み、ヘッダーロゴの背景画像から参照。アニメーションと元SVGの内容を保持。
- 検証: 実ヘッダーのJinja描画と実CSSをEdgeで読み込み、2550/1360/959/390/320pxの全幅で高さ61px・折返しなし・ページ横はみ出しなし。最終タブへのキーボードフォーカスとスクロール到達、指定SVGの読み込みに合格。PC・スマートフォンの画像を目視確認。SVGのXML構文と指定元とのSHA256一致を確認。
- 証跡: 作業先`output/validation/header-single-row-20261103`に画像とbrowser-result.jsonを保存。外部通信は遮断しローカル静的ファイルのみ応答。実アプリ全体の起動・認証・実モデル・実支援技術は未検証。DB・実Vault・資格情報の変更なし。コミット・pushなし。


## 2026-11-03 実行状況画面の独立とホームからの復帰

- 対象: 作業先`C:/Users/kurok/Downloads/mojiokosi/mojiokosi`、ブランチ`krokharu/transcription-finish-20261102`、開始時HEAD`d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。既存の多数の未コミット変更を保持。
- 利用者要件: 新規作成と実行中の画面を分離し、ホームに戻っても実行状況を再び開けるようにする。
- 実装: 既存progress-cardを`views/running.html`へ移し、`#/running`を独立ルートに追加。開始時は実行状況へ移動。ホームのフォームは表示し、実行中案内と復帰ボタンをフォームの外に置く。既存の同時実行制限は維持。上部通知と案内ボタンから同じジョブへ戻れる。空状態・失敗・中止にも案内を用意。
- 継続動作: ホーム等で進捗更新・バックグラウンド完了・キュー自動継続が発生しても画面を奪わない。実行状況を見ている場合のみ完了時に結果へ移る。未保存結果の確認を維持し、完了後の案内は「結果を開く」に切り替える。送信拒否・再送確認終了時は新規作成でエラーを表示し、受付中の通知を残さない。
- 検証: `GURUMOJI_DOM_SOURCE_ROOT`を対象作業先、`GURUMOJI_TEST_PYTHON`を対象作業先の`.venv/Scripts/python.exe`へ明示。開発資料ブランチの`tests/dom/running-view.test.cjs`と既存`navigation.test.cjs`の計17件に合格。開始・ホーム復帰・背景更新/完了・失敗/中止・接続失敗・再読込復元・履歴・未保存編集・送信拒否・キュー自動継続を合成データで確認。既存effort-cards 24件も合格。
- Edge: `tests/ui/running-view-browser.py --source-root <対象作業先> --output <対象作業先>/output/validation/running-view-20261103`に合格。実テンプレート・全出荷JavaScript・実CSSを1360px/390pxで操作し、開始・ホーム・ロゴ/通知からの復帰・進捗更新・背景完了・再読込・失敗・空状態を検証。開始POSTは1回、ページエラー0、外部接続0。両幅の実行中画面とホーム画像を目視確認。実APIは全てローカルの合成応答、ポートは開いていない。
- 既存失敗: 追加の既存integration/boundaries確認で、integrationの`real mode handler preserves four independent efforts and FormData across simple/detail/advanced/off transitions`（outlineの期待値medium/実値ultra）と`actual mode changes restore optional choices and serialize each effort exactly once`（checked参照先null）の2件が失敗。開始前に保存したUIファイルだけの隔離baselineで両件の同一失敗を再現し、今回の変更とは分離。別件として未修正。
- 構文/差分: app.js・create-dashboard.jsのnode --check、CRLFを考慮したgit diff --checkに合格。進捗カードが新規作成内に残らず専用テンプレートに1つだけあることを確認。
- 未実施: 実APIサーバーでの実運用、実モデル/CUDA、実認証、実支援技術。DB・runtime・実Vault・資格情報を使用/変更せず、保存契約・SQL・モデル設定に変更なし。コミット・pushなし。


## 2026-11-03 処理画面から複数ファイルを待機登録

- 対象: `krokharu/transcription-finish-20261102`、開始時HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。既存変更を保持し、app.js・create-dashboard.js・stitch-theme.css・views/running.htmlのキュー関連箇所を変更。
- 要件と判断: 処理画面から実行中にも複数ファイルを待機させ、現在の設定で登録順に1件ずつ実行する。既存のブラウザー内複数ファイルキューを拡張し、APIの同時実行制限、SQL・保存形式・同期・認証設定は変更しない。登録は履歴を含め最大30件。待機は同じタブ内のメモリー保持で、再読込・タブを閉じた場合は解除されるため画面に明記。
- UI: 独立した処理キュー欄に追加ボタン・件数・一覧・個別解除・待機一括解除・自動実行の一時停止/再開を追加。実行中の解除は不可。ヘッダーとホームに待機件数を反映し、処理完了後も待機があれば処理画面へ戻れる。
- 実行制御: 実行中と受付応答待ちのファイルを保護し、待機追加で入力ファイルや実行ジョブを差し替えない。既存の復元ジョブは元のFileがなくても現在処理の行として扱い、後続を追加可能。完了後に次の待機ファイルを選び直し、重複タイマーを防いで順次開始。ホーム等の表示先は自動継続で切り替えない。失敗・中止・受付拒否では自動継続を停止して残りを保持し、受付拒否分は再び待機へ戻す。重複と非対応拡張子、上限超過を案内する。
- 操作性: キュー状態が変わらない進捗更新では一覧を作り直さず、キーボードのフォーカスを保持。一括解除で選択中の待機ファイルも解除された場合は入力欄から外す。
- 検証: `tests/ui/processing-queue-browser.py --source-root <対象作業先> --output <対象作業先>/output/validation/processing-queue-20261103`をEdgeで実行して合格。合成音声と合成APIのみ使用し、8回の開始POST（うち1回は合成受付拒否）で、受付応答待ちの保護・実行中追加・順序・解除・一時停止/再開・失敗/中止停止・背景完了・復元ジョブへの追加・受付拒否からの再開・30件上限・重複・拡張子除外を確認。進捗更新後の解除ボタンへのフォーカス保持も確認。ページエラー0、外部接続0。1360px/390pxで横はみ出しなし、画像を目視確認。
- 回帰: 対象作業先を`GURUMOJI_DOM_SOURCE_ROOT`、対象先の`.venv/Scripts/python.exe`を`GURUMOJI_TEST_PYTHON`に指定し、running-view.test.cjsとnavigation.test.cjsの17件に合格。既存running-view-browser.pyの開始・復帰・完了・再読込・失敗検証にも合格。app.jsとcreate-dashboard.jsのnode --check、CRLFを考慮したgit diff --checkに合格。
- 未実施: 実APIサーバー、実モデル/CUDA、実認証、実支援技術、タブを閉じた後の待機永続化。実データ・DB・runtime・実Vault・資格情報を使用/変更せず、ポートなし。前タスクで変更前から確認済みのAI設定統合試験2件は今回再実行せず、別件のまま保持。コミット・pushなし。


## 2026-11-03 現在工程のアニメーションと完了表示

- 対象: `krokharu/transcription-finish-20261102`、開始時HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。既存の多数の未コミット変更を保持。
- 利用者要件: 現在行っている処理に対応するアニメーションを動かし、終わった処理を分かるようにする。
- デザイン: 環境確認・音声処理・文字起こし・時刻補正・話者分離・文章/AI仕上げ・保存の7系統のSVG/CSSアニメーションを新規progress-journey.jsで表示。工程が切り替わったときだけ絵を入れ替え、通常の進捗更新では再生成・再スタートしない。完了・失敗・中止で動きを停止し、動きを減らす設定にも対応。
- 完了: 工程の履歴をチェック付きで表示。処理画面を見ている場合も完了表示を残し、明示的な「結果を開く」で結果へ移動するよう変更。背景での完了は引き続き利用者の画面を変えない。キュー内の完了は緑のチェック、処理中は動くバッジ、待機は破線、失敗は赤、中止は黄系の状態として区別。復元ジョブの完了行が自動解除されないよう保持。
- データ: JobRecordにプロセスメモリー内のstage_historyを追加し、TranscriptionReporter.stageが既存jobs_lock内で更新。RuntimeState.update_jobの引数契約は保持し、同じロック内で履歴を設定する。公開時は独立コピーと診断文のパス保護を適用。工程が100%と通知された場合に完了を記録し、途中の繰り返し・中断は完了へ推測変換しない。通知されていない任意工程を履歴へ足さない。DB・SQL・結果ファイル保存形式・Vault契約には変更なし。
- 単体: 開発資料ブランチのtest_progress_stage_history.pyに7件を追加。対象srcの実JobRecord・TranscriptionReporter・RuntimeState・RLock・update_jobを使い、工程完了通知、繰り返し、失敗/中止、未実行工程、公開コピー/パス保護、別ジョブ分離が合格。実DB・実モデルなし。
- Edge: tests/ui/progress-animation-browser.pyが合格。実工程記録コードからの公開データで7系統の稼働アニメーション、同一工程更新時のSVGノード/アニメーション継続、完了7工程のチェック、結果ボタン、失敗/中止の停止、動きを減らす設定を確認。1360px/390pxの実行中・完了画像を目視確認し、横はみ出しなし。ページエラー0、外部接続0。API/推論は合成応答。
- 回帰: 対象作業先のsrcとPythonを明示し、running-view.test.cjs/navigation.test.cjsの17件に合格（完了表示を残す期待値へ更新）。effort-cards 24件に合格。processing-queue-browser.pyの受付保護・追加・順次実行・停止再開・失敗中止・復元・上限等も合格し、開始POST8回（うち1回は合成受付拒否）。状態バッジの追加に合わせて行セレクターをliへ限定。
- 静的確認: JavaScript4ファイルのnode --check、Python2ファイルのcompile、CRLFを考慮したgit diff --checkに合格。既存行の改行を保持。証跡はoutput/validation/progress-animation-20261103。
- 未実施: 実APIサーバー起動・実推論/CUDA・実認証・実支援技術。実データ・runtime・実DB・実Vault・資格情報は使用/変更せず、ポートを開いていない。工程履歴はサーバープロセス内の進捗で、再起動をまたぐ永続化は対象外。以前に変更前から確認済みのAI設定統合試験2件は別件として未再実行。コミット・pushなし。


## 2026-11-04 太線の共通テーマとモーションの流れ

- 対象: `krokharu/transcription-finish-20261102`、開始時HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。既存変更を保持し、出荷側はprogress-journey.jsとstitch-theme.cssだけを編集。
- 利用者要件: 全アニメーションで共通するテーマを作り、細い線を見やすくし、起動・変化・繰り返しの動きを挟む。
- テーマ: 深緑の太い丸線、ミントの面、黄色のアクセント、共通の吹き出し外枠。主線は3から6.5へ変更し、完了チェックは8、補助構造の透明度も引き上げ。処理画面の描画領域はPC200px/スマートフォン260pxを基準に拡大。既存の提供ロゴSVGは変更せず保持。
- 制御: 初回startup640ms→loop。工程が変わる場合は共通の外枠を保持し、前の絵の退出と次の絵の登場をtransition360msで挟んでloopへ。完了/失敗/中止はsettling280ms後にsettledとして停止。工程名だけ変わり絵が共通のケースも切り替えを表示。通常の割合更新ではSVG・ループ・タイマーを再作成しない。
- 境界: WeakMapで表示要素ごとに制御し、古いタイマーを破棄・世代照合して速い連続変更でも新しい工程を上書きしない。受付IDから実ジョブIDへの引き継ぎでstartupを繰り返さない。動きを減らす設定では起動/変化を待たず確定し、設定変更時にも退出中の絵を除去する。
- 試験: 開発資料ブランチのmotion-theme.test.cjsに9件追加。running-view.test.cjs/navigation.test.cjsと合わせて26件に合格。開始/繰り返し、同一工程更新、工程切替、連続切替、3種類の終了、動きを減らす設定、受付ID引継ぎを確認。対象作業先のsrcとPythonを環境変数で明示。
- Edge: 既存progress-animation-browser.pyを着地/ループ到達を待つ検証に更新し合格。7系統の動き・継続更新・完了表示・失敗中止・動きを減らす設定を実CSS/出荷コードで確認。1360px/390pxの実行中・完了画像を目視確認し、横はみ出しなし、ページエラー0、外部接続0。
- プレビュー: motion-theme-preview.pyで出荷コードから181フレーム、約18秒のGIFを生成。起動・繰り返し・切替・完了への着地・停止の各状態を実際に通過して記録。output/validation/motion-theme-20261104/preview/gurumoji-common-motion.gifと静止画を保持し、太線と共通テーマを目視確認。
- 検証範囲: node --checkとCRLFを考慮したgit diff --checkに合格。実モデル・実APIサーバー起動・実認証・実支援技術は未実施。API/推論は合成応答のみ。DB・runtime・実Vault・資格情報・保存契約・SQLに変更なし。ポートなし。コミット・pushなし。

## 2026-11-10 ローカル開発版の起動・画面確認

- 対象: `krokharu/transcription-finish-20261102`、HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486` と既存の未コミット変更。表示版 `β0.46.1`。アプリソースの編集なし。
- 起動: 対象の `.venv/Scripts/python.exe`（3.12.9）で実アプリの `main()` を起動。ObusSQL・MAFをrun.bat同様に有効化。一時DB・出力・バックアップ・アップロード・認証設定・ロックを分離し、専用ループバックポートを使用。実runtime・実DB・実Vault・資格情報を使用せず、確認後サーバーを停止。
- Chrome（headless、応答の差し替えなし）: HTTP 200、起動画面の終了、最新のドロップ領域と登録状態、データ・分析・話者・プリセット・内部データ・新規作成への可視クリック、通常設定ダイアログを確認。JavaScript例外0、HTTP 400以上0。HTMLは `no-store, no-cache, must-revalidate, max-age=0`。
- 画像: 1440×1050と390×844を目視確認。モバイルの文書幅390pxで横はみ出しなし。証跡は `../artifacts/transcription-finish-20261102-20261110/development-ui-check/` の結果JSON、PC・モバイル画像と確認スクリプト。
- 起動依存: agent-framework-core 1.22.0、obusql-agent 0.1.0、ctranslate2 4.8.1、numpy 2.2.6、torch 2.8.0+cu128、whisperx 3.8.6、openai-whisper 20250625を確認。`python -m pip check` 合格。
- 未実行: run.bat全体（Git更新・ライブラリー更新・初期導入）、実音声の文字起こし、実モデル推論、実認証、実Vault同期、利用者の既存ブラウザープロファイルでの表示。UI表示の成功をこれらの合格とは扱わない。コミット・pushなし。

## 2026-11-10 開発版の公開コミット収録範囲

- 同じ作業先・HEADを対象に、`git fetch --no-tags origin`、`git ls-remote` とGitHub CLIの読み取りで最新リモート・公開状態・Releaseを照合。公開リポジトリの既定ブランチはmain、先端 `e02ab60483031b517528f2c8069308df6b9512b4`（2026-11-03）。公開Releaseは `v0.47.0-beta`。このコミットは親を持たない独立した公開スナップショット。
- 結論: 開発版由来の変更は一部すでに公開済み。新規作成ダッシュボード・緑のテーマ・アイコン・事前データ画面・ObusSQL・MAF接続などを収録。`features.py` は開発版と同一でObsidian有効。公開run.batではObusSQL・MAFの既定値は0、手元は1。
- 対象作業先のHEADから変更・追加された対象ファイルを、Gitの改行変換を適用したblob hashで公開mainと照合。427ファイル一致、30ファイル差分、14ファイル未収録。画像・アイコンも件数に含む。全開発差分の未公開を意味せず、全最新版の公開も意味しない。
- 最新の未収録例: `progress-journey.js`、話者タイムラインCSS/JS、`views/running.html`、再分析・context_delivery・metric_delivery・Core制御群。画面CSS・app.js・create-dashboard.js・テンプレートにも追加差分が残る。
- ブランチ: `origin/public/develop` は `6fd6f890`（2026-11-02）の旧公開スナップショットのまま。リモートの `public/release` は存在しない。mainとReleaseを現在の公開実体として判定。
- 公開範囲検査: 旧public/developにある既存 `check_public_boundary.py` を、履歴対象だけorigin/mainに向けて実行し終了コード1。`src/gurumoji/templates/index.html.recovered` を公開対象外のファイルとして検出。tokens.example.jsonのキー検知は、値を表示せず確認し、検知対象は例示用文字列であることを確認。実キー流出とは判定しない。境界検査スクリプト自体は現在の公開mainに未収録。
- 証跡: `../artifacts/transcription-finish-20261102-20261110/public-commit-audit/comparison.json`。今回の作業ではコミット・push・公開内容の変更を実行していない。差分照合と公開範囲の静的検査であり、公開版の実音声処理・実モデル・実Vault同期は未検証。

## 2026-11-10 開発版mainの保存と公開専用リポジトリの分離確認

- 前節の対象訂正: `krokharu/gurumoji` は開発元。実際の公開専用リポジトリは `krokharu/Gurumoji-public`、既定ブランチは `public/release`。前節で開発元mainを公開版として報告した判断は誤りで、この節の結果を優先する。公開専用リポジトリと開発元はいずれもGitHub上の可視性はpublicであり、今回privateへ変更していない。
- 利用者指定: 最新版を開発元mainへ先にpushし、公開版は公開専用ブランチの内容に限定する。既存画面を保持し、解析・ObusSQL・MAF等の開発用機能を公開版へ含めない。
- 開発版: 元作業先の未コミット変更を保持し、別clone `../gurumoji-development-main-20261110` に最新ソースを明示選択で保存。`92f38c7bca2b0c144468996b9c9392484d68a9b7` と `1ec2d226433b8dade45450bf31d70a4f3b902c3b` を `krokharu/gurumoji/main` へ通常push。実runtime・実DB・資格情報・ObusSQL本体・個人設定は含めず、復旧用index.html.recoveredは現行treeから除去。旧履歴は書き換えていない。
- 開発版からの誤配布防止: 自動版上げ・タグ・Release作成workflowを削除し、読み取り権限の構文・版表記検査へ置換。README・AGENTS・開発手順に公開先との責務を明記し、個人設定・別管理ソース等をgitignoreへ追加。専用cloneのremoteは開発元だけとし、元作業先へ今回一時追加した公開remoteも削除。
- 公開版: 専用clone `../Gurumoji-public-release-20261110` で全リモートブランチと到達可能な履歴を確認。最新開発版のMAF・ObusSQLファイルは現行各ブランチになし。履歴のfeatures.pyは公開機能をFalseにする旧設定であり、最新版の混入ではない。公開版の既存境界検査は864 blobを検査して合格。
- 公開版の再混入防止: 既存check_public_boundary.pyの現行tree検査にMAF・ObusSQL・開発版機能フラグ・接続依存等を追加。禁止例15パスを拒否し、公開用の代表6パスを許可することを確認。公開用手順とAGENTSも明確化。`b7d29a7dc84b809717a77b3b2a85837299f0bbdc` を `public/develop` と `public/release` の両方へatomicな通常push。既定ブランチをpublic/releaseとして確認。
- 検証: 開発版Python183ファイルのAST、変更JavaScript7ファイルのnode --check、版表記、現行treeの禁止パス・秘密値パターン、CRLFを考慮したdiff --checkが合格。元作業先のアプリ・起動・設定・ノートブック631ファイルと保存先のbytes一致を確認。公開アプリのsrc・scripts・config・run.bat・notebooksは既存β0.47.2の6517fddと同一。
- GitHub CI: 開発元最終mainのdevelopment（42650839162）成功。公開側の読取専用検査2件と版管理2件（42650711966、42650711772、42650711986、42650711978）すべて成功。公開版の版はβ0.47.2のまま。
- 削除範囲: 公開専用側に今回の最新開発ソースの誤プッシュは確認できなかったため、正規の公開Release・タグ・既存ブランチを推測で削除していない。ユーザーの実データ、認証設定、実Vault、元作業先の既存変更も変更しない。実音声処理・実モデル・実Vault同期は未検証。
- 証跡: `../artifacts/transcription-finish-20261102-20261110/repository-separation/` のソースmanifestと結果JSON。上記2cloneを開発版・公開版それぞれの独立した作業先として残す。

## 2026-11-10 公開版ブランチをpublic/releaseへ一本化

- 利用者指示で公開専用 `krokharu/Gurumoji-public` を `public/release` の1ブランチへ統合。開始時 `b7d29a7`、未コミット変更なし。開発元gurumoji/mainは `1ec2d226433b8dade45450bf31d70a4f3b902c3b` のまま変更しない。
- 開始時6ブランチのうち、Colab改善のDraft PR #7だけ5コミットが未統合。実Colab未確認のため退避と統合の選択を確認し、利用者が「統合する」と指定。公開版の既存履歴だけを通常mergeし、開発版の履歴は混ぜていない。
- `72f020a093c99a5fa4c2359467f2c09b33d8dc6d` でPR #7と単一ブランチ運用の手順・AGENTS・CI設定を統合しpush。PR #7の統合先をpublic/releaseへ変更、MERGEDを確認。自動版管理が `53557fccc121bc3fdf14100cf7bf11156977a78d`（β0.48.0）を作成し、公開タグ・Releaseも作成。
- 独立した一時Python環境（Python 3.12、site-packages共有なし）でColab依存分離・秘密値・LLM選択・資源モニター78件、AI応答境界14件、計92件成功。実データ・実認証・実モデルなし。Notebook全7コードセルのASTと実行結果なしを確認。公開範囲検査は統合後892 blobで成功。CI 42654189688・42654189436が成功。
- program-vaultは入口3ノートのブランチ案内と更新日だけを変更し、Catalogのsha256・文字数・summary・updatedを照合更新。専門家・文献・スライド定義のbytes・版は変更しない。
- 削除直前に全6先端commitがpublic/releaseの祖先であることと、リモート先端が確認時から不変であることを確認。atomicな通常pushでdocs/public-readme-20261103、fix/colab-isolated-environment-20261104、fix/haas-model-picker-20261104、fix/remove-public-analysis-20261103、public/developの5ブランチを削除。全変更は公開ブランチの履歴に保持され、force push・reset・cleanは使わない。
- 最終GitHub APIとls-remoteでpublic/releaseの1ブランチ、既定ブランチ、先端53557fc、未解決PRなしを確認。統合後の作業ブランチ自動削除も有効化。専用cloneの追跡設定と古いリモート追跡参照も整理。作業先はclean。
- 未実行: Google Colab実セッション・Driveマウント・実キー認証・GPU別のモデル推論と品質評価。単体試験・CI合格を実Colabの合格とは扱わない。実利用者DB・runtime・Vault・資格情報には接触していない。
- 証跡: `../artifacts/transcription-finish-20261102-20261110/public-branch-unification/` のbranches-before.json、result.json。試験資産は公開リポジトリへ追加していない。
