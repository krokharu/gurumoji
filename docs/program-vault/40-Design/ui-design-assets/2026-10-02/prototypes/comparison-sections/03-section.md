---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-assets-2026-10-02-prototypes-comparison-section-03
title: Gurumoji：2案の低忠実度フロー比較：4 状態遷移と守る条件
summary: 4 状態遷移と守る条件。出典ノート「Gurumoji：2案の低忠実度フロー比較」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-assets-2026-10-02-prototypes-comparison
source_path: 40-Design/ui-design-assets/2026-10-02/prototypes/comparison.md
source_sha256: e1e1cb01403af93a48b0bcef230d4b0336546f52a6ba6173e48ca7a30c9887a9
source_body_lines:
- 67
- 101
split_on: '2026-10-11'
---

# Gurumoji：2案の低忠実度フロー比較：4 状態遷移と守る条件

親索引・状態・確認版：[[40-Design/ui-design-assets/2026-10-02/prototypes/comparison]]。必要な本文だけを取得する。

## 4 状態遷移と守る条件

### 測定：両案で共通

1. 定義編集：ID、規則、型、尺度、手法、単位、欠測規則を明示。descriptionは測定命令ではない。使用可能な組合せはvalidatorから確認する
2. 別draftを保存：既採用IDのpayloadを上書きしない。保存競合なら両方を保持し、旧payloadへの逆PUTをしない
3. 試行：上限は現行1〜100、例は4件。連打で重複送信を作らない。対象・draftが変わった後の遅い応答を今の試行として表示しない
4. レビュー：値・欠測・入力対応・限界を読む。失敗や個票不足は「確認できない」状態。0件や全欠測は平均0にしない
5. 採用：明示操作が必要。定義revisionまたはinput_hashが変われば古いレビューは無効。r1を採用PUTするとr2になる現行仕様を表示し、同じ内容のstatus更新と規則変更を区別する
6. 全件実行確認：採用とは別操作。対象、採用版、含む基礎処理、外部送信なし、保存先の実態を表示。O01、Transformer、AI見解をこの操作で一括実行できるとは示さない
7. 実行：受付時payloadを実行・再開・保存で固定するか、不一致で安全停止。最新版を自動採用して続行しない

「画面でチェックされた」をサーバーの永続レビュー記録にするには、定義revision・入力fingerprint・trial IDを結ぶ別契約が必要。採用応答が不明なときは操作成功を推測せず、正式状態を確かめてから表示する。

### 結果と根拠：両案で共通

- 保存済み結果の表示だけで推論や外部送信を始めない。pipeline status GETが自動回復を起こす場合と固定artifact読取を分離する
- 開く前にitem、run、result card、page、filter、selectedEvidence、scroll、focusOriginを保持。新しい永続session storeを前提にしない
- 原資料は生成時本文・話者・時刻・segment ID・入力版。現在の引用と不一致なら自動音声接続を止める
- 元segment削除、音声なし、入力版不明でも、保存引用があればその本文と取得できる来歴を残す。未知を現在版で補わない
- 再生中の発話、編集中の選択、保存引用を同じ選択状態に統合しない。この静止図は再生状態を実装していない
- 戻る／閉じる時は同じ結果へ。Bのmobileの戻る操作は結果を再計算する機能ではない
- 版照合が成功して音声がある別fixtureでは、通常の音声確認→戻るを検証する。今回の画面は意図的に不一致例を示す

### 実行・保存状態を画面案が上書きしない

| 状態 | 期待する表示 | 禁止する解釈 |
|---|---|---|
| accepted / running | 受付済み／処理中を分ける | 受付したから計算完了 |
| waiting | 理由とbackendが許す操作 | 任意の再開buttonを有効化 |
| failed | 失敗箇所、保存済み結果への入口 | 大見出しを「実行中」のままにする |
| cancelling / cancelled | 中止要求中／中止済み | 要求しただけで止まったことにする |
| 通信取得失敗 | 最終取得時刻と状態不明 | backendも失敗したと推測する |
| 計算完了・Vault書出し失敗 | 本体と保存先別の結果 | 全保存成功、計算から全再実行 |
