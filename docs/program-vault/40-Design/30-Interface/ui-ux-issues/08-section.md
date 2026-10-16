---
note_type: reference-section
status: current
verified: 2026-09-16
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/ui
note_id: design-ui-ux-issues-section-08
title: Web UI デザイン・UX 問題点一覧：追加調査：動画処理・確認画面のUI/UX（2026-09-22）
summary: 追加調査：動画処理・確認画面のUI/UX（2026-09-22）。出典ノート「Web UI デザイン・UX 問題点一覧」の分割本文。
parent_note_id: design-ui-ux-issues
source_path: 40-Design/ui-ux-issues.md
source_sha256: c6f0bc30d41c6d90a9c75e220f625e969a0b285260197965f43858ce5d0a0c54
source_body_lines:
- 117
- 130
split_on: '2026-10-11'
---

# Web UI デザイン・UX 問題点一覧：追加調査：動画処理・確認画面のUI/UX（2026-09-22）

親索引・状態・確認版：[[40-Design/30-Interface/ui-ux-issues/00-Index]]。必要な本文だけを取得する。

## 追加調査：動画処理・確認画面のUI/UX（2026-09-22）

利用者の「動画処理画面のUIが非常に見づらい」という指摘に基づき、動画処理・実行画面（`#/new`）と動画確認・編集作業画面（`#/data/<id>`）のコード・レイアウト・スタイルを精査した。詳細な改善案・設計図は [[40-Design/30-Interface/video-ui-redesign-plan|video-ui-redesign-plan]]。

| ID | 重要度 | 問題 | 根拠（コード） | 影響 | 改善案・受け入れ条件 | 状態 | 選別（追加調査） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UX-35 | 高 | 動画プレビュー領域が横幅300〜380pxに固定され、映像やスライドの文字が小さすぎて読めない | `static/style.css:363`: `.transcript-layout` | 会議スライドの文字、話者の表情・口元の動きが潰れ、動画を見ながらの文字起こし確認・修正が極めて困難 | 動画領域の横幅をminmax(380px, 480px)に拡大し動画の視認性を確保 | 対応済み（[[40-Design/30-Interface/video-ui-redesign-plan\|video-ui-redesign-plan]]） | P0：最優先 |
| UX-36 | 中高 | ライトテーマの中に動画領域だけ真っ黒な枠（#17201c）があり、視線移動時のコントラスト差で目が疲れる | `static/style.css:679`: `.media-review` | 左の暗色ボックスと右の白背景エディタを交互に見るため、明暗差が激しく長時間の確認作業で疲労が大きい | 動画プレイヤーのコンテナ配色を全体のライトカードスタイルに統合 | 対応済み（[[40-Design/30-Interface/video-ui-redesign-plan\|video-ui-redesign-plan]]） | P1：優先 |
| UX-37 | 高 | 発話（セグメント）1件ごとの縦幅が約250pxと巨大で、1画面に2〜3件しか入らず会話全体の文脈が見通せない | `static/style.css:803`: `.segment` | チャットや字幕のように文脈を一望できず、頻繁なスクロールを強いられ、全体の会話の流れの把握や校正が困難 | 通常時はタイムライン形式でコンパクト表示、選択・フォーカス時に詳細編集フォームを展開 | 対応済み（[[40-Design/30-Interface/video-ui-redesign-plan\|video-ui-redesign-plan]]） | P0：最優先 |
| UX-38 | 中 | 上部のアウトライン・リザルト情報が巨大で、ファーストビューで動画プレイヤーとテキストが画面外に見切れる | `src/gurumoji/templates/index.html:701`: `<details id="session-outline">` | 画面を開いた直後に作業対象の動画と発話リストが見えず、毎回下へスクロールする手間が生じる | アウトラインを既定で折りたたみ、ファーストビューに動画と発話冒頭が収まる配置に改善 | 対応済み（[[40-Design/30-Interface/video-ui-redesign-plan\|video-ui-redesign-plan]]） | P1：優先 |
| UX-39 | 中 | 動画の再生位置と発話リストの連動・追従（オートスクロール）が弱く、現在位置を見失いやすい | `static/app.js:renderMedia`: 再生連動 | 「今、動画のどの発話を喋っているか」が視覚的に追えず、長時間の動画で迷子になりやすい | `timeupdate` に連動して再生中の発話をハイライト、スムーズ追従する自動追従トグルを導入 | 対応済み（[[40-Design/30-Interface/video-ui-redesign-plan\|video-ui-redesign-plan]]） | P1：優先 |
| UX-40 | 中 | 処理中画面（Progress Card）のアニメーション・システム計器・点滅ランプが過剰で視覚的ノイズが大きい | `index.html:85-162`: 過密計器 | 視覚的疲労・圧迫感を軽減 | 主要進捗に絞り、システムモニタやトークン詳細・ログを「詳細システム情報とログ」アコーディオンに格納、波形アニメをマイルド化 | 対応済み（[[40-Design/30-Interface/video-ui-redesign-plan\|video-ui-redesign-plan]]） | P1：優先 |
| UX-41 | 中 | 設定項目が5つのアコーディオンに埋もれ、フォントサイズが極小（約11px）で漢字が潰れて可読性が低い | `static/style.css`: フォントサイズと行間 | 日本語の可読性低下 | フォントサイズ・余白・行間を調整し、漢字潰れを解消し可読性を向上 | 対応済み（[[40-Design/30-Interface/video-ui-redesign-plan\|video-ui-redesign-plan]]） | P2：後続 |
| UX-42 | 低中 | カードと背景の境界線・明度差が小さく、視覚的な階層（ビジュアルヒエラルキー）が曖昧で画面が散漫に見える | `static/style.css`: カード境界 | 画面が散漫に見える | カードのシャドウ・コントラスト・ボーダー色を調整しメリハリを向上 | 対応済み（[[40-Design/30-Interface/video-ui-redesign-plan\|video-ui-redesign-plan]]） | P2：後続 |
