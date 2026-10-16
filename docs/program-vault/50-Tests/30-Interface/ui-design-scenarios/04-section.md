---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: test-ui-design-scenarios-section-04
title: Gurumoji 研究作業シナリオと受入条件：S04 根拠を確認して編集し同じ結果へ戻る
summary: S04 根拠を確認して編集し同じ結果へ戻る。出典ノート「Gurumoji 研究作業シナリオと受入条件」の分割本文。
parent_note_id: test-ui-design-scenarios
source_path: 50-Tests/ui-design-scenarios.md
source_sha256: 9f71d53a14ce91325066d6751cab56455b58336565bdb774708972b1304959db
source_body_lines:
- 86
- 105
split_on: '2026-10-11'
---

# Gurumoji 研究作業シナリオと受入条件：S04 根拠を確認して編集し同じ結果へ戻る

親索引・状態・確認版：[[50-Tests/30-Interface/ui-design-scenarios/00-Index]]。必要な本文だけを取得する。

## S04 根拠を確認して編集し同じ結果へ戻る

**研究者の仕事:** 「全員が賛成した」というAI見解を確かめ、反対する発話を原音で確認する。必要な文字起こしを直し、元の見解へ戻る。

**入力:** 会話A revision1の固定runR1、賛成／反対／伝聞／質問の合成発話、選択filterと引用。revision2に本文または時刻・話者の変更。対応: DG-06/12、W04、UX:K01/UX:K03/UX:K05/UX:K08/UX:K13。

1. 結果で対象・run・入力版・対象集合を確認する。根拠と反例候補を開く
2. 該当発話の前後を読み、音声を聞く。生成説明と入力の証拠を区別する
3. 発話編集へ移り、合成音声に合う修正をして保存する。保存失敗の分岐ではdraftを保持する
4. 元の見解へ戻る。filter、結果ページ、引用、scroll、focus起点を確認する
5. revision1の結果がrevision2に対して古いことを確認し、旧結果を保持したまま必要に応じた再分析の入口を確認する

**受入:** 古い引用から現在音声へ黙って飛ばない。生成時本文・時刻・話者と現在内容が違えば不一致を伝える。R1へ戻ったときに現在版の来歴へ書き換わらず、stale／unknownが残る。固定成果物の閲覧・戻るだけで再分析を始めない。既存pipeline status GETには再起動後の自動回復があるため、固定結果ビューからその経路を使わない。研究者メモや確定解釈をAI再生成で上書きしない。

**理解の問い:** 「いま読んでいる結果はどの入力版ですか」「全員という見解を支持しない根拠はありますか」。採用率や信頼自己評価だけで良否を決めない。

**固定viewerのgate:** 最初はai_insights／milestone_analysisだけをW04のmanifest・input・resultのfield対応で扱う。100件外のrun lookup、未知schema、artifact409／404、quote欠落、hashは一致するがbindingとdefinitionsの版が異なる旧package、同tab Back/Forward、reload contextあり／なしを試す。reload contextが無くても同じrun概要へ戻し、現在データへfallbackしない。定義版が不整合な旧packageは正常確認済みと表示せず、自動比較を止め、元artifactを残す。全sessionを越える位置復元や他kind対応は未提供とする。

**比較案:** Aは既存details＋往復、Bはdesktop根拠pane／mobile全幅根拠。両案に照合する主張、AI下書き、取得できた確認状態、限界、選択発話IDを残す。確認記録なし／読取不能を区別し、人が未読と推定しない。B mobileの研究者メモは別状態なので、メモを読み直す課題も含める。現在発話を確実に解決できない条件ではその入口を無効にする。等価fixtureで正しい根拠への到達、誤り発見、復帰の失敗、不要な遷移を比較し、画像の短さやpaneの広さを改善点数にしない。
