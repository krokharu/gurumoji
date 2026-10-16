---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: test-ui-design-scenarios-section-05
title: Gurumoji 研究作業シナリオと受入条件：S05 古いrunを探し比較して同じ対象を出力する
summary: S05 古いrunを探し比較して同じ対象を出力する。出典ノート「Gurumoji 研究作業シナリオと受入条件」の分割本文。
parent_note_id: test-ui-design-scenarios
source_path: 50-Tests/ui-design-scenarios.md
source_sha256: 9f71d53a14ce91325066d6751cab56455b58336565bdb774708972b1304959db
source_body_lines:
- 106
- 141
split_on: '2026-10-11'
---

# Gurumoji 研究作業シナリオと受入条件：S05 古いrunを探し比較して同じ対象を出力する

親索引・状態・確認版：[[50-Tests/30-Interface/ui-design-scenarios/00-Index]]。必要な本文だけを取得する。

## S05 古いrunを探し比較して同じ対象を出力する

**研究者の仕事:** 前回の分析と今回の分析を探し、条件の違いを確認して比較・出力する。

**入力:** 通常runと比較runの各0/1/99/100/101/105/201件、同時刻ID、legacy来歴不明、旧入力と新入力、異なるfilter／分母。履歴閲覧中に新規runが加わる条件。対応: DG-04/06、W04/06、UX:K09/UX:K13。

1. 履歴を開き、表示件数と保存総数の違いを読む
2. 101件目以降の指定runを通常のページ操作で探し、開いて戻る
3. 2つの結果の入力版・定義版・対象集合・欠測・比較可能性を確認する
4. 不適合な比較は理由を読み、無理に共通の母集団として扱わない
5. 対応する形式を選び、本文・時刻・話者・コード・ノート・来歴のうち含む情報と省かれる情報を読む。出力を取得し、画面のrun／revision／hash／対象数と照合する

**受入:** 変更なしのfixtureではページ間の重複・取りこぼしがなく、同時刻でも順序が安定。live keysetの並行追加ではcursorより新しいkeyのrunを現在の走査へ割り込ませず、更新後に先頭から発見できる。同時刻の小さいIDや過去日時の追加は古い範囲へ入り得るため、全新規runの除外や初回時点のsnapshot固定は保証しない。上限説明だけの段階では101件目への通常到達は未対応と明記する。元保存物と既知IDリンクは保持。legacy不明値を現在値で補わない。表・CSV・JSON／ZIPで分母と欠測が一致。

**能力の確認:** 通常分析XLSXとpipeline固定packageのXLSX未提供を区別し、後者をダウンロード可能と案内しない。比較を開く操作と新しい比較runを作る操作を区別する。

**理解の問い:** 「一覧の100件は保存の全件ですか」「このCSVはどの結果を出したものですか」「分母の違う結果をそのまま比較できますか」。履歴上限をデータ削除と誤解していないかを見る。

## S06 キーボードと読み上げで相互作用を記録する

**研究者の仕事:** ある発話が前の発話への反論だと記録し、根拠メモを付け、不要なら取り消す。

**入力:** 選択発話e2と候補e1/e3、未設定select、長い関係名、入力済みmemo。通常／focus／error／disabled、固定header/footer、200%拡大。対応: DG-09/10/12、W05、UX:S22〜S30。

1. pointerを使わず対象の発話から相互作用入力へ移る
2. 「対象発話」と「関係」を目的名で見分け、値を選ぶ。根拠memoを入力する
3. 追加し、結果と通知を確認する。取消・削除・再追加を行う
4. 実ATで名前・role・value・発話文脈・保存通知を読む
5. focus中の実色・背景・遮蔽・clipを採取し、同じ箇所を狭幅でも試す

**受入:** select2つに一意で目的が分かるprogrammatic name。memoは入力後もvisible labelが残る。選択値をcontrolの目的名の代わりにしない。focusが見え、固定バーで完全に隠れない。errorは欄へ結び付き、追加後に入力文脈と通知を失わない。

**contrast:** drop補助文、registry未保存文、淡い共通ring、濃緑border、青outline、濃色sidebarを個別に測る。指定色の計算をcomputed style検証の代わりにせず、良い反例も残す。

**証拠:** 可視操作V3、accessibility tree、AT名・版と発話記録V4。ATがない場合はV4 not-run。placeholder fallbackがあるmemoを絶対無名だったと断定しない。
