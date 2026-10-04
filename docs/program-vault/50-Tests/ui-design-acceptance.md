---
note_id: "test-ui-design-acceptance"
note_type: "test-plan"
title: "Gurumoji デザイン受入試験の検証範囲"
summary: "設計資料v0.3の作業用正本。設計提案の採用・アプリ実装・UI受入は未完了。"
status: "proposed"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
tags: ["gurumoji/design", "gurumoji/ui"]
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
