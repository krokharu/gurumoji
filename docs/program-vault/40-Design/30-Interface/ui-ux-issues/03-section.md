---
note_type: reference-section
status: current
verified: 2026-09-16
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/ui
note_id: design-ui-ux-issues-section-03
title: Web UI デザイン・UX 問題点一覧：B. 操作の安全性・フィードバック
summary: B. 操作の安全性・フィードバック。出典ノート「Web UI デザイン・UX 問題点一覧」の分割本文。
parent_note_id: design-ui-ux-issues
source_path: 40-Design/ui-ux-issues.md
source_sha256: c6f0bc30d41c6d90a9c75e220f625e969a0b285260197965f43858ce5d0a0c54
source_body_lines:
- 51
- 61
split_on: '2026-10-11'
---

# Web UI デザイン・UX 問題点一覧：B. 操作の安全性・フィードバック

親索引・状態・確認版：[[40-Design/30-Interface/ui-ux-issues/00-Index]]。必要な本文だけを取得する。

## B. 操作の安全性・フィードバック

| ID | 重要度 | 問題 | 根拠（コード） | 影響 | 改善案 | 状態（2026-09-26） | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UX-11 | 高 | ~~削除ボタンが保存ボタンと同じ固定バーに並んでいる。狭い画面では固定バーが本文を覆う~~ 対応（2026-09-14、`1b8fe41`に収録済み）：削除を固定バーの外の `.result-danger-zone` へ移した。540px以下の固定バーは「保存」「Obsidianで仕上げ」の1行（2列）にした | `.sticky-actions` に「保存」「Obsidianで仕上げ」「分析」「削除」「一覧へ戻る」の5つが並ぶ。540px以下では `flex-direction: column` になり、画面下に固定されたまま約300pxの高さになる | 削除の誤操作を招く。スマホでは発話一覧の大部分が隠れる | 削除は「その他」メニューか、画面最下部の危険操作エリアに移す。モバイルの固定バーは保存と主な操作1つだけにする | 対応済み（`1b8fe41`） | P1：優先 |
| UX-12 | 中 | ~~「処理を中止」を押すと確認なしで中止する~~ 対応（2026-09-14、`1b8fe41`に収録済み）：中止要求の前に `window.confirm` で確認する（共通ダイアログ化はUX-13のため保留のまま） | `app.js`: `cancelButton` のクリック処理は、すぐに `/api/jobs/<id>/cancel` を送る | 長い文字起こしやAI処理を、誤タップで失う | 確認ダイアログを出すか、長押しなど2段階の操作にする | 対応済み（`1b8fe41`） | P1：優先 |
| UX-13 | 中 | 確認・入力のダイアログが、ブラウザー標準のものと独自のものに分かれている | `window.confirm`（削除や未保存時の移動）、`window.alert`（`openAiModelDialog`）、`window.prompt`（データ追加の代替手段）と、独自の `<dialog class="app-dialog">` が混在する | 見た目や文言がそろわない。ブラウザー標準のダイアログは説明を足しにくく、危険な操作を強調できない | 共通の確認用 `app-dialog` 部品を作り、置き換える | 未対応 | 保留：共通ダイアログ化を安全対策の前提にしない |
| UX-14 | 中 | ~~会話モードを切り替えると、手動で調整した詳細設定が知らせなく上書きされる~~ 対応（2026-09-14、`1b8fe41`に収録済み）：手で変えた項目（`manuallyEditedModeFields`）はモード切替で上書きせず、ヒント文で保持した項目名を知らせる。「このモードの推奨値に戻す」で推奨値に戻せる | `app.js`: `applyConversationMode` が最少／最多話者数、前処理、VAD onset/offset、小声対策、詳細処理を上書きする | 詳細設定を調整した後にモードに触れると、調整内容が消える | 手動で変えた項目は保持するか、上書き前に知らせる（トーストや差分表示） | 対応済み（`1b8fe41`） | P1：優先 |
| UX-15 | 低 | 無効なボタンの見た目が不適切 | `.primary-button:disabled` と `.secondary-button:disabled` が `cursor: wait`（読み込み中に見える）。無効時の「文字起こしを開始」は opacity .55 で文字のコントラストが下がる | 押せない理由が伝わりにくい | 無効時は `not-allowed` にする。ボタンの近くに無効の理由を表示する | 一部対応 | 保留：開始ボタンのcursorは対応済み。残りは保留 |
| UX-16 | 低 | 処理中に別のタブへ移っても、進捗カードが表示され続ける | `showView` は `jobRunning` の間、`progressCard` を隠さない。`#progress-card` はどのタブパネルにも属していない | 話者管理などの下に、どこに属するのか分からない進捗表示が出る | 共通の処理中バー（小さい固定表示）にし、詳細は新規作成タブで表示する | 対応済み（UI再設計、2026-09-16に実装、HEAD 2f13f98に収録。[[20-Modules/40-Interface/ui-screens/00-Index\|ui-screens]]）：進捗は新規作成画面だけ。ほかの画面では上部バーのチップ | 保留：処理状況の継続表示には用途がある |
