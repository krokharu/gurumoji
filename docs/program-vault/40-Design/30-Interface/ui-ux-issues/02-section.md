---
note_type: reference-section
status: current
verified: 2026-09-16
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/ui
note_id: design-ui-ux-issues-section-02
title: Web UI デザイン・UX 問題点一覧：確認範囲と方法
summary: 確認範囲と方法。出典ノート「Web UI デザイン・UX 問題点一覧」の分割本文。
parent_note_id: design-ui-ux-issues
source_path: 40-Design/ui-ux-issues.md
source_sha256: c6f0bc30d41c6d90a9c75e220f625e969a0b285260197965f43858ce5d0a0c54
source_body_lines:
- 24
- 50
split_on: '2026-10-11'
---

# Web UI デザイン・UX 問題点一覧：確認範囲と方法

親索引・状態・確認版：[[40-Design/30-Interface/ui-ux-issues/00-Index]]。必要な本文だけを取得する。

## 確認範囲と方法

| 項目 | 内容 |
| --- | --- |
| 対象 | `src/gurumoji/templates/index.html`, `src/gurumoji/static/app.js`, `static/style.css`, `static/ai-effort.css`, `static/ai-effort.js` |
| 版 | ブランチ `agent/expand-analysis-ai-workflows` の作業ツリー（2026-09-14、`1b8fe41`に収録済み変更を含む） |
| 方法 | コードとCSSを読んで確認した。加えて、起動中のアプリの「新規作成」画面を、ヘッドレスEdge（幅1440px）で撮影して目視確認した |
| 未確認 | 幅390pxのスマホ表示は正しく撮影できなかった（ヘッドレスブラウザーの最小ウィンドウ幅の制約と、iframe埋め込みの拒否による）。モバイルの項目はCSSを読んで判断した。横はみ出しの有無は実機で確認が必要 |
| 関連テスト | `tests/test_browser_e2e.py`, `tests/test_ui_defaults.py`, `tests/test_content_browser.py` |

重要度の目安：**高**＝データ損失・誤操作・主な導線の妨げ、**中**＝迷い・非効率・アクセシビリティ上の欠落、**低**＝見た目の一貫性・保守性。

## A. 情報設計・ナビゲーション

| ID | 重要度 | 問題 | 根拠（コード） | 影響 | 改善案 | 状態（2026-09-26） | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UX-01 | 高 | 表示中の画面がURLに反映されない | `app.js`: `showView`, `showProcessedDataSection` は表示を切り替えるだけ。`pushState`／`location.hash`／`popstate` を使っていない | 再読み込みすると必ず「新規作成」に戻る。ブラウザーの「戻る」でアプリの外に出てしまう。特定のデータや分析画面をブックマーク・共有できない | `#library`, `#analysis/<id>`, `#result/<id>` などのハッシュルーティングを導入し、`popstate` で `showView` を呼ぶ | 対応済み（UI再設計、2026-09-16に実装、HEAD 2f13f98に収録。[[20-Modules/40-Interface/ui-screens/00-Index\|ui-screens]]）：画面ごとのハッシュURLと `popstate` | P2：後続 |
| UX-02 | 高 | 結果画面（`#result-card`）が縦に非常に長い1ページになっている | `index.html`: 見出し → 関連画面ナビ → トークン使用量 → 出力先 → メディア → 議事録 → アウトライン → 感情 → 会話プロファイル → 絞り込み → 発話一覧、の順に並ぶ | 主な作業である発話の修正に着くまで長くスクロールする。プレイヤーは画面に固定されず、下の方の発話で再生すると `mediaReview.scrollIntoView` で上に戻される | 「発話編集／議事録・アウトライン／会話プロファイル」のタブに分ける。デスクトップではプレイヤーを横か上に固定する | 対応済み（UI再設計、2026-09-16に実装、HEAD 2f13f98に収録。[[20-Modules/40-Interface/ui-screens/00-Index\|ui-screens]]）：作業画面を4タブに分割し、デスクトップはプレイヤーを左に固定 | 保留：編集導線を観察してから。タブ分割は未採用 |
| UX-03 | 中 | 同じ移動ボタンが2か所にある | `.result-context-nav` の「データ一覧」「分析・可視化」と、`.sticky-actions` の「一覧へ戻る」「このデータを分析・可視化」 | どちらを押せばよいか迷う。固定バーが混み合う | 移動は関連画面ナビにまとめ、固定バーは保存などの操作だけにする | 対応済み（UI再設計、2026-09-16に実装、HEAD 2f13f98に収録。[[20-Modules/40-Interface/ui-screens/00-Index\|ui-screens]]）：移動は見出しと上部バーだけ。保存バーは保存とObsidianの2つ | P2：後続。一部対応（2026-09-14、`1b8fe41`に収録済み）：540px以下は固定バーから移動ボタン2つを外した。デスクトップは、上部ナビが固定されず長い画面で戻りにくくなるため、UX-02と合わせて判断 |
| UX-04 | 中 | ~~同じものを指す用語がそろっていない~~ 対応（2026-09-14、`1b8fe41`に収録済み）：「ライブラリ」「TRANSCRIPT LIBRARY」を「処理済みデータ」「PROCESSED DATA」に、「認識設定」「認識と話者分離」を「認識・話者分離」に統一。UI-02（保存ボタン名）は未対応 | 「処理済みデータ」「データ一覧」「ライブラリ」（削除確認の文言）「TRANSCRIPT LIBRARY」が混在。「認識設定」（サイドバー・`quick-flow`）と「認識と話者分離」（見出し・会話モードのヒント文）も不一致 | ヒント文にある「認識と話者分離で変更」が、ナビ上のどの項目か分かりにくい | 用語集を決め、`index.html` と `app.js` の文言を統一する | 対応済み（`1b8fe41`） | P2：後続 |
| UX-05 | 中 | 新規作成の手順表示が3種類あり、互いに一致しない | デスクトップの `quick-flow` は4段階、`desktop-step-nav` は6項目、モバイルウィザードは別の区切りの4ステップ。`updateCreateSummary` はファイルを選ぶと1段目を完了にし、いきなり「開始」を現在地にする（途中の段は変化しない）。サイドバーは現在表示中の節を強調しない（`IntersectionObserver` なし） | 進み具合が正しく伝わらない。飾りの表示に見える | 手順の区切りを1つに統一する。デスクトップはスクロール位置に連動して現在の節を強調する | 対応済み（UI再設計、2026-09-16に実装、HEAD 2f13f98に収録。[[20-Modules/40-Interface/ui-screens/00-Index\|ui-screens]]）：全幅で3ステップの手順表示を1つだけ使う | 保留：新規作成画面を改修する際に対応 |
| UX-06 | 中 | ~~分析タブで、比較カードが単一データの分析より先に表示される~~ 対応（2026-09-14、`1b8fe41`に収録済み）：比較カードを `#analysis-shell` の後ろへ移し、閉じた `<details id="interview-comparison-details">` に入れた | `#interview-comparison-card` が `#analysis-empty` や `#analysis-shell` より上に常に表示される | データを選ぶ前から大きな比較UIが見え、1件を分析するという主な導線が下に押し出される | 比較は「分析・可視化」内の別サブタブにするか、折りたたみにする | 対応済み（`1b8fe41`） | P2：後続 |
| UX-07 | 中 | ~~話者管理で、事前アンケート分析が話者表より上にある~~ 対応（2026-09-14、`1b8fe41`に収録済み）：アンケート分析を話者表・カード一覧の後ろ、保存バーの前へ移した | `#speaker-survey-analysis` が `.registry-toolbar-shell` と `.spreadsheet-shell` より前にある | 主な作業である話者の登録・編集が下に押し出される | 表を先に置き、アンケート分析はサブタブか折りたたみにする | 対応済み（`1b8fe41`） | P2：後続 |
| UX-08 | 中 | ~~起動時に毎回、約2.4秒の固定スプラッシュが表示される~~ 対応（2026-09-14、`1b8fe41`に収録済み）：表示をブラウザーのセッションごとに1回（`sessionStorage`）、待ち時間を約1.25秒に短縮。文言を「STARTING · LOADING WORKSPACE」、`aria-label` を日本語にした | `app.js`: `startBootSequence` が固定の待ち時間（200＋1500＋720ms）を使う。`style.css`: `.page-shell` の登場アニメーションは1.35秒遅れて始まる。表示文言は「CHECKING FOR UPDATES」だが、実際の更新確認とは連動していない | 起動のたびに待たされる。実態と異なる表示になっている | 設定の読み込み完了で閉じる。初回だけ表示するか、短縮する。文言を実態に合わせる | 対応済み（`1b8fe41`） | P2：後続 |
| UX-09 | 低 | デスクトップの見出し領域が大きく、CPU/GPU表示が重複している | `.hero` は min-height 275px（960px以上）。CPU/GPUのランプはヒーロー、マシン診断パネル、モバイルヘッダーの3か所にある | 作業エリアが画面の下に下がる（撮影画像では、作業カードの開始位置が約440px） | ヒーローを細いヘッダーにまとめる。ランプの表示は1か所にする | 対応済み（UI再設計、2026-09-16に実装、HEAD 2f13f98に収録。[[20-Modules/40-Interface/ui-screens/00-Index\|ui-screens]]）：ヒーローを高さ60pxの上部バーにし、CPU/GPU表示を接続ボタンとダイアログにまとめた | 保留：装飾変更は後回し |
| UX-10 | 中 | ~~モバイルでは、APIトークンの状態とモデル選択への導線がない~~ 対応（2026-09-14、`1b8fe41`に収録済み）：モバイルの新規作成ヘッダーにOpenAI／Google／ローカルLLMの状態ボタンを追加。`loadConfig` が `[data-status-provider]` も更新し、タップでモデル選択ダイアログを開く | `style.css`（max-width 959px）: `.hero { display: none; }`。モデル選択ダイアログは `.hero` 内の `[data-model-provider]` ボタンからしか開けない | スマホからはモデルを変更できず、トークン未設定にも気づけない | 設定用のボタンかメニューをモバイルのヘッダーに置く | 対応済み（`1b8fe41`） | P2：後続 |
