---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-microcopy-state-catalog-section-07
title: Gurumoji 日本語UI文言と状態の仕様案：8 実装前の判断チェックリスト
summary: 8 実装前の判断チェックリスト。出典ノート「Gurumoji 日本語UI文言と状態の仕様案」の分割本文。
parent_note_id: design-ui-microcopy-state-catalog
source_path: 40-Design/ui-microcopy-state-catalog.md
source_sha256: a380e655813a51346e817cb6f36f5fea46e2e56045e8019aa10d9ef5c0b64d29
source_body_lines:
- 199
- 232
split_on: '2026-10-11'
---

# Gurumoji 日本語UI文言と状態の仕様案：8 実装前の判断チェックリスト

親索引・状態・確認版：[[40-Design/30-Interface/ui-microcopy-state-catalog/00-Index]]。必要な本文だけを取得する。

## 8 実装前の判断チェックリスト

- [ ] この文は「保存」「計算」「採用」「人の確認」「通信」のどの事実を伝えるかを1つに絞ったか。2つ伝えるなら別の行にしたか
- [ ] 操作名と実際のhandlerが一致するか。「見る」で再実行、「試す」で採用、「再試行」で設定画面を開いていないか
- [ ] 状態はサーバー応答で分岐し、`active`、spinner、経過時間、ボタンのenabledだけから推測していないか
- [ ] 中止の送信中・受付済み・完了を分けたか。応答不明を「中止済み」にしていないか
- [ ] waitingの理由とallowed_actionsを照合したか。unknown値を英語のまま通常UIへ出していないか
- [ ] 「保存済み」と言う対象を挙げられるか。追加編集、保存先別の失敗・競合・未確認を隠していないか
- [ ] 保存競合で今の編集を残せるか。退避機能のない定義editorに「ダウンロード」を約束していないか
- [ ] 0、欠測、対象外、未実行、全欠測を分けたか。「有効」は計算可能なのか研究上妥当なのか曖昧でないか
- [ ] 数の単位、分母、除外後の先頭N、現在の版と試行版が読み取れるか
- [ ] 採用を人のレビュー済み、hash一致を意味の正しさ、固定ファイルを定義の不変履歴へ置き換えていないか
- [ ] 送る内容・選んだ送信先・今回の操作が近くにあるか。「このPC」「送信なし」は経路限定で正しいか
- [ ] 必要モデルの未取得・未確認・ファイルあり・読込成功を分けたか。利用許諾や接続の確認を省いていないか
- [ ] 保存済み結果を開けないとき、現在データを黙って代用していないか。再取得の副作用を確認したか
- [ ] エラーは具体的で可逆な次操作を示すか。根拠なく「すべて保持」「安全」「いつでも復元」を付けていないか
- [ ] 狭幅で短くした結果、AI下書き、限界、欠測、版、保存先、主張が消えていないか
- [ ] 読み上げは1遷移1回か。350ms polling、秒時計、log、重複live領域で同じ内容を連読しないか

### 最小の受入例

1. running→failedで見出し・chip・操作が一致する。failedのreviewは「設定を見直す」で、そのクリックを再試行と記録しない
2. 中止POSTの応答を保留し、送信中を確認。cancelling応答後も中止完了にしない。通信断とcancelled応答を別fixtureで確認
3. 本体成功＋ResearchVault成功＋InputVault失敗を表示し、InputVaultの失敗を総合成功文で消さない。3生成Vault成功＋ResearchVault conflict＋全体completedも別fixtureで確認する。OFF＋ResearchVault pendingはこの実行の対象外。限定先だけの再試行と案内しない
4. 保存開始後に編集を追加し、成功後も追加分の未保存表示が残る。409では入力と退避手段が残る。timeoutでは成功・失敗を断定しない
5. durationの60／2／0／欠測で平均20.7、分母3。全欠測は「算出できる値がありません」、対象0は「対象の発話がありません」、未実行は「未実行」。3状態を0秒へ集約しない
6. 同じ定義名でdurationから文字数へ変え、古い試行を採用できない。試行応答が遅れて返っても変更後の版と取り違えない。永続レビューgate未導入ならその保証を表示しない
7. stale、来歴不明、artifact404、hash409、元発話なし、時刻欠測を別fixtureで確認。保存済み結果の閲覧から現在値の再計算や外部AIを呼ばない
8. モデルmissing／unknown／cachedを同じ「準備完了」にしない。閲覧端末と実行環境が別でも送信先説明が正しい。モデル・実データは動かさずstubで検証
9. 1実行の同状態pollを繰り返し、実ATで開始・工程変更・待機・中止・完了の短い通知を確認。実AT未実施ならV4未実施と記録
10. 「内容・文脈検索から実行」の案内先へ、production CSSと通常pointer／keyboardで到達する。hidden要素のJS clickを代替合格にしない

上記は実装後の受入設計であり、このUI受入は実行していない。現行の保存先経路と失敗時の契約については独立した合成probeの確認を引用した。V1/V2/V3/V4/V5の区別を既存受入方法に従って維持する。
