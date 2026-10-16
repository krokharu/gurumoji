---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-reference-patterns-section-06
title: Gurumoji の研究作業に使う公式 UI 参照パターン：7 最小の試作単位と未検証仮説
summary: 7 最小の試作単位と未検証仮説。出典ノート「Gurumoji の研究作業に使う公式 UI 参照パターン」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-reference-patterns
source_path: 40-Design/ui-design-research/2026-10-02/reference-patterns.md
source_sha256: f1334e394b188d0ff4c52216c8a7ff37e52789869513174579c3868d7764a702
source_body_lines:
- 191
- 225
split_on: '2026-10-11'
---

# Gurumoji の研究作業に使う公式 UI 参照パターン：7 最小の試作単位と未検証仮説

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/reference-patterns]]。必要な本文だけを取得する。

## 7 最小の試作単位と未検証仮説

この調査によるアプリ改修は行っていない。次に試すなら、機能追加や全面レイアウト変更より、現在の保護を使った狭い比較を優先する。

| ID | 変更する一点 | 成功を判断する観察 | 失敗・撤回条件 |
|---|---|---|---|
| H01 | 根拠pane＋復帰情報 | 結果→原音→戻るを正しいrunで完了、位置喪失が減る | paneが本文やfocusを隠す、旧版と現在版を混同 |
| H02 | 提案と適用差分の分離 | 意図的な誤提案を採用前に発見、既存編集を保持 | checkbox操作だけ増え、誤採用が減らない |
| H03 | 処理・保存・確認の短い別表示 | 公開だけ失敗した状態を正しく説明し復旧できる | 状態ラベルが多すぎて次の操作を選べない |
| H04 | 選択と再生追従の分離 | 長文修正中に選択が保たれ、再生位置へ戻れる | 現在どこが再生されているか分からなくなる |
| H05 | 原文近くの限定再生・巻戻し | 誤変換／話者誤りの検出と修正が改善 | 再生制限で前後文脈を聞かず誤解する |
| H06 | 出力範囲と来歴の要約 | previewとファイルの対象・引用元を照合できる | 形式選択時だけ説明し、実ファイルが欠ける |

合成fixtureは、同名話者・短い相槌・重なり・音声なし・古い引用・本文再編集・filter 0件・部分失敗・公開だけ失敗を含める。初学者と経験者は別に観察し、時間短縮だけでなく誤りの残存・取り消し・根拠確認・日本語IME・focus復帰を確認する。手法上の解釈の妥当性を「AIと一致した件数」では測らない。

## 8 公式画像の画素確認記録

画像は比較研究のため一時取得して閲覧した。アプリ、mockup、出力画面へ画像・ロゴ・UI部品を取り込んでいない。下記は原掲載先と原画像へのリンクであり、競合の視覚資産をGurumojiに複製する指示ではない。

| ID | 実際に確認した静止表示 | 原掲載ページと原画像 | 画像から判断できないこと |
|---|---|---|---|
| S01 | 抜粋の下に文書名・位置・コード、上に対象件数 | [R03本文](https://www.maxqda.com/help/segment-retrieval/the-retrieved-segments-window)／[原PNG](https://www.maxqda.com/wp/wp-content/uploads/sites/2/13-EN-ListRetrievedSegments.png) | クリック後のfocus、戻る操作、狭幅 |
| S02 | 本文左の時刻column、下部playbar、code範囲のmargin | [R01本文](https://www.maxqda.com/help/transcription-audio-video/timestamps-to-link-transcripts-with-sound)／[原PNG](https://www.maxqda.com/wp/wp-content/uploads/sites/2/09-EN-Timestamps-In-Document-Browser.png) | 再生中の追従、編集との競合。青い大きな矢印はマニュアル注釈 |
| S03 | 原文・既存・AI提案の4列、未選択checkbox、緑の一致、理由tooltip、無効に見える適用button | [R06本文](https://www.maxqda.com/help/ai-assist/ai-coding/ai-coding-segments)／[原PNG](https://www.maxqda.com/wp/wp-content/uploads/sites/2/31-EN-Survey-AICoding-Suggestions.png) | 適用の実挙動。英語ページ内だが画像UIはドイツ語。色の意味は本文と照合した |
| S04 | 動画、波形、時間に対応する複数の引用帯とcode label | [R08本文](https://manuals.atlasti.com/Win/en/manual/Multimedia/MultimediaWorkingWith.html)／[原PNG](https://manuals.atlasti.com/Win/en/manual/Multimedia/Images/W_CodedVideo.png) | 本文編集、時間調整の精度、keyboard代替 |

取得bytesのSHA-256（再取得時の比較用。製品のbuild識別子ではない）:

- S01: `ad189c4e810cd5c3609c9c4209d4bf51ff874bce144b710a42adcd191f4b5230`
- S02: `fe8a73876ba55a35c7dd4aa9765523f9d19689bdca21be5936dc7e167be1c544`
- S03: `dd52115bc7cb35e6950d0cd9439eef95c791f6d2708532b0d0201944d4d8ce0c`
- S04: `7ee5ea74ed924ae85a07fe50917356f44dd45ea356d04eaff5a1152f21364205`

Dovetail highlightsのhero画像、Descriptのalignmentエラー画像は、公式ヘルプから辿った画像取得が403で終わった。別経路で回避していない。alt textだけから配色・密度・操作性を評価していない。MAXQDA／ATLAS.tiの画像取得で一部検索ツールのcache errorがあったが、公開の同一原画像を通常HTTPで取得して上記4枚を画素閲覧した。これらは製品のライブ画面ではない。
