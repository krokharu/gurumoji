---
note_id: res-ginza-official
note_type: literature
literature_id: RES-ginza-official
title: "GiNZA - Japanese NLP Library（公式ドキュメント）"
authors:
  - Megagon Labs
year: 未確認
venue: "GiNZAの公式ドキュメント（GitHub Pages）"
source_type: official_resource
peer_review: not_peer_reviewed
peer_review_basis: "ソフトウェアの公式ドキュメントで、査読を経た資料ではない。"
doi: ""
url: https://megagonlabs.github.io/ginza/
accessed: 2026-09-15
access_scope: official_page
access_detail: "公式ドキュメントのトップページを取得して読んだ。更新日はページ上で確認していない。"
correction_status: not_checked
related_experts:
  - exp-japanese-text-preprocessing
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/text
---

# GiNZAの公式ドキュメント

## 研究目的

日本語自然言語処理のライブラリGiNZAの使い方、モデル、精度、ライセンスを説明する（公式ページ）。

## 対象データと研究条件

精度の比較は、UD_Japanese-BCCWJ r2.8のテストセットで、5万ステップ学習した時点のモデルの値として示されている。

## 分析手順の要約

- 自然言語処理のフレームワークにspaCyを使い、トークン化（形態素解析）にSudachiPy、単語ベクトルにchiVeを使う。
- Transformersの事前学習モデルを使う `ja_ginza_electra` と、従来型の `ja_ginza` がある。

## 主要な知見

公式ページの精度表の例（UD_Japanese-BCCWJ r2.8）：`ja_ginza_electra` はLAS 92.3、UAS 93.7、UPOS 98.1、ENE 61.3。`ja_ginza_bert_large`（β版）はLAS 93.8、UAS 94.9、UPOS 98.3、ENE 70.8。

## 適用上の注意と限界

- GiNZAのライブラリと日本語UDモデルはMIT Licenseで公開され、依存するSudachi、SudachiDict、chiVe、spaCy、transformersにはそれぞれのライセンスがある。
- [整理] 精度は書き言葉のコーパス（BCCWJ）での評価であり、音声認識の誤りやフィラーを含む会話の逐語録での精度を示すものではない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/01-Expert|日本語テキスト前処理の専門家]]：使ったモデル名と版を結果に記録する。評価コーパスでの精度を、逐語録での解析の正しさとして示さない。GiNZAが使えない場合の簡易解析（`fallback`）の結果を、正式な解析結果と混ぜない（既存の実装契約と一致）。

## 根拠の位置情報

公式ページの「ライセンス」「Transformersモデルによる解析精度の向上」の節。

## 未確認事項

ページの更新日、Gurumojiが実際に読み込むモデル（`ja_ginza` か `ja_ginza_electra` か）の確認。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-matsuda-2020-ginza]]、[[50-Analysis-Methods/20-Literature/LIT-takaoka-2018-sudachi]]、[[50-Analysis-Methods/20-Literature/LIT-omura-asahara-2018-ud-japanese]]
