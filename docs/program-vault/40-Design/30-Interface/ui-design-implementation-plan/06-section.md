---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-implementation-plan-section-06
title: Gurumoji UI改善の実装計画：W05 ラベルとcontrastを用途ごとに修正する
summary: W05 ラベルとcontrastを用途ごとに修正する。出典ノート「Gurumoji UI改善の実装計画」の分割本文。
parent_note_id: design-ui-implementation-plan
source_path: 40-Design/ui-design-implementation-plan.md
source_sha256: 6521f18593584f6fc5ac64f5d4918b2ec5a9d29c9644cae72ab010ef731f00c2
source_body_lines:
- 134
- 152
split_on: '2026-10-11'
---

# Gurumoji UI改善の実装計画：W05 ラベルとcontrastを用途ごとに修正する

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-implementation-plan/00-Index]]。必要な本文だけを取得する。

### W05 ラベルとcontrastを用途ごとに修正する

- 対象: `app.js:7317–7347`、`style.css`のroot／drop zone／registry unsaved／focusと各上書き
- 作業: 相互作用の対象select・関係select・根拠memoに見えるlabelと関連付け。memoを絶対無名とは扱わない。指定色ではなくcomputed foreground/backgroundを採取して、必要なテキスト・状態・focusの役割色を調整する
- 新しい測定／根拠UIでは、採用不可の理由とdisabled状態、mobile main navの現在地を色以外と役割・状態で示す。静止批評MC-07は実UIでの残留確認事項であり、現行アプリの新規欠陥数やAT失敗数へ加算しない
- 合格: シナリオS06。role/nameから通常操作、accessibility treeで目的名、実ATをした場合のみ音声確認済み。文字4.5:1／該当する非テキスト3:1、focusが完全に隠れない。濃色sidebar等の良い既存箇所を改悪しない
- 出典: DG-09/10、反証第2巡、UX:S22/UX:S25/UX:S28/UX:S29/UX:S30a
- 移行／rollback: 局所CSS／labelを小さく分割。全ブランド色一括置換を避け、state別before/afterを保持する

### W06 履歴を探し直せるようにする

- 対象: `analysis_store.py:274–297`、`handlers/analysis_queries.py:58–79`、`analysis-storage.js:27–85`、比較履歴
- 第1段階: 既存上限なら「直近100件を表示」と明示し、保存総数と呼ばない
- 出力説明: 固定runか現在filterか、本文／時刻／話者／コード／ノート／来歴のどれを含み、どれを含まない形式かを表示する。これは[公式参照パターン](../../ui-design-research/2026-10-02/reference-patterns.md)A04からの適用案で、既存exportを無断に拡張する要求ではない
- 第2段階: 安定した`created_at + id`降順のkeyset cursor、次ページ有無を加える。初期案はlive一覧で、次ページはcursorより古い範囲を取得する。走査中にcursorより新しいrunが加わった場合は現在の走査へ割り込ませず、更新で先頭から見せる。初回時点の全件固定snapshotとは呼ばない。総数を出すなら取得時点を付ける。既存responseを壊さず、通常runと比較runへ同じ契約。厳密なsnapshot一覧が必要になった場合は別のserver境界tokenを設計する
- 合格: シナリオS05。変更なしの0/1/99/100/101/105/201件と同時刻fixtureで全件到達・重複／欠落なし。並行追加では既出IDの重複なし、新しいrunは更新後に通常操作で見つかる。101件目へ到達し、既知のartifactリンクは引き続き読め、保存件数は減らない
- 出典: DG-04＝UX-34、反証第2巡、UX:S08/UX:S13/UX:S20
- 移行／rollback: 原則schema変更なし。index等の追加時も削除・型変更なし。旧clientの既定100件応答を保持し、全件取得をブラウザーへ無制限転送しない
