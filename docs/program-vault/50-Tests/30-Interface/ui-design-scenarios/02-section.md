---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: test-ui-design-scenarios-section-02
title: Gurumoji 研究作業シナリオと受入条件：S02 定義したつもりの測定と実際の値を照合する
summary: S02 定義したつもりの測定と実際の値を照合する。出典ノート「Gurumoji 研究作業シナリオと受入条件」の分割本文。
parent_note_id: test-ui-design-scenarios
source_path: 50-Tests/ui-design-scenarios.md
source_sha256: 9f71d53a14ce91325066d6751cab56455b58336565bdb774708972b1304959db
source_body_lines:
- 37
- 63
split_on: '2026-10-11'
---

# Gurumoji 研究作業シナリオと受入条件：S02 定義したつもりの測定と実際の値を照合する

親索引・状態・確認版：[[50-Tests/30-Interface/ui-design-scenarios/00-Index]]。必要な本文だけを取得する。

## S02 定義したつもりの測定と実際の値を照合する

**研究者の仕事:** 各発話の長さを秒数で測る変数を作り、少数例を見てから全件へ適用する。

**入力:** e1本文「あいう」＝3文字・0〜60秒、e2本文「abcdefghij」＝10文字・70〜72秒、e3はstart/end欠測またはtime_unknown=true（durationの保存値が0でも欠測）、e4はstart=end=80・duration=0・time_unknown=falseの真の0秒。本文文字数とdurationの順位を逆にする。手動測定の名称・説明は「発話の長さ」「各発話の持続時間を秒数で測る」。対応: DG-02、W02、PR:T11、UX:K03/UX:K06/UX:K09。

1. 手動測定を開き、名称だけでなく入力列・規則・型・尺度・単位・手法を確認する
2. durationの定義で少数試行を行い、e1=60、e2=2、e3=欠測理由付き、e4=0の個別値を見る
3. 一度閉じる／取り消す。採用や全件実行が発生していないことを確認する
4. 再度開き、文字数へ変更して試す。e1=3、e2=10となり、秒数を意味しない説明へ変わることを確かめる
5. durationへ戻し、試行値を確認して明示採用する。その定義revisionで全件実行する
6. 別条件として名義尺度のまま平均を求める手法を選び、fieldに紐付いた拒否理由を見る

**受入:** 説明文だけを変更して規則が変わったように見せない。限定文字数案を採る場合はduration作成を明示的に利用不可とし、このシナリオは機能限定として記録する。対応版では採用前のadopted PUT／pipeline POSTが0回、採用後のpayload・固定版・結果が一致。受付後に版が変わった場合は旧固定内容で実行するか理由付きで安全停止し、別版の値を正常確定しない。名義尺度に平均を出さず、欠測を0にしない。

**追加の競合:** 試行後に定義変更、別itemへ移動、入力revision更新、二重submit、保存409、別definition IDへ変更を行う。古い試行をそのまま新定義の採用証拠にせず、未保存入力と旧採用版を保護する。既adopted IDの編集試行は別draft ID等へ分離し、取消後に旧採用payloadが変わらないことをDBで確認する。受付後に別タブで定義を変える／処理を再起動・retryする条件でも、固定した定義内容と実結果を照合する。

**v2から引き継ぐ条件:** 試行した定義版・入力版、全体→除外→試行数、測定の限界が採用前に見える。補助失効図は状態の要約であり、編集面を置換する指示ではない。定義変更後も入力とfocusを保ち、古い結果を前回の試行と明示して確認／採用を失効させる。遅い旧試行は現在の結果へ反映しない。欠測の確認linkは発話IDを含む名前で固定入力を開き、現在入力を直したら再試行する。採用応答不明では成功・失敗を推測せず正式状態を確認する。PNGでこれらが動いたとは扱わない。

**理解の問い:** 「説明欄を書き換えると計算も変わりますか」「この列の単位は何ですか」「いつ研究者が採用しましたか」。試行件数だけ見て無自覚に全件へ進んでいないかを観察する。

**実装前提:** 現行trial responseにはinput_hashはあるが、発話ID付きの個票・欠測理由・定義revisionがない。W02のresponse拡張を先に行う。試行版rと同内容を採用する版r+1を追跡し、画面が古いvaluesと現在発話を推測で結ばない。個票に添える本文／時刻も同じtrial snapshot由来であることを確認し、入力変更後の現在値で表示を埋めない。受付後の版ずれは[隔離probe](../../ui-design-evidence/2026-10-02/definition-lifecycle-probe.json)で再現済みのため、W02の実行境界対策が受入の前提。[全pipeline合成probe](../../ui-design-evidence/2026-10-02/definition-full-pipeline-probe.json)でも保存adapter入力の不整合を確認したが、実ディスク保存／GUIでの再現済みとはしない。

**保存互換のgate:** W02の固定payload提案は実装前。旧manual／旧automatic／新形式、受付前後の並行編集、restart/retryを分ける。旧binaryへのdowngradeはDB初期化前のcompat guardと復元dry runが必要で、pending=0だけで許可しない。

**証拠:** 画面要約、trial個票、definition revision、API順序、固定run。これは研究上の妥当性を証明するテストではなく、宣言した計算と実行の一致のテスト。
