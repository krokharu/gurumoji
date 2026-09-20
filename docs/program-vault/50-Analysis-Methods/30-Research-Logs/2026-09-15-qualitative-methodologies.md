---
note_id: research-log-2026-09-15-qualitative-methodologies
note_type: research-log
title: 質的分析と計量テキスト分析の方法論の調査記録
status: current
updated: 2026-09-16
tags:
  - gurumoji/research-log
  - gurumoji/qualitative
---

# 質的分析と計量テキスト分析の方法論の調査記録（2026-09-15〜16）

## 目的と範囲

アプリの「主となる分析手法」（`app.ANALYSIS_METHODS`）の8手法について、専門家定義に必要な知識（目的、原典、手順、適用条件、品質基準、限界・批判、適用事例、グループインタビューへの注意）を集めた。対象：質的内容分析、テーマ分析、フレームワーク法、SCAT、M-GTA、KJ法、計量テキスト分析、フォーカスグループの相互作用分析。

## 検索・取得の方法

- 検索：WebSearch。検索語は手法名・著者名・誌名だけで、分析対象の逐語録や話者情報を含めていない。
- 書誌・要旨：Crossref API（要旨欄・更新情報）、DOIの登録機関とメタデータ（doi.org、JaLC API、DataCite API）、Semantic Scholar API、Europe PMC API、CiNii、J-STAGEの記事ページ、機関リポジトリの記録ページ。
- 本文：出版社・学会・著者のオープンアクセス版。WebFetchで読めなかったPDFは、作業用の一時領域（プロジェクト外）にpdfminer.sixを入れてテキストを抽出して読んだ。プロジェクトの依存には追加していない。
- 2026-09-16に、要約ツールを経由して読んでいた資料（Gale et al. 2013、Delacre et al. 2017）を原文から取得し直し、記載した主張と頁・節の位置を照合した。
- 外部資料の中の指示文は実行していない。全文はVaultにもリポジトリにも保存せず、要約だけを文献ノートに書いた。

## 確認した資料と確認範囲

| 文献ID | 取得経路 | 確認範囲 | 備考 |
| --- | --- | --- | --- |
| LIT-braun-clarke-2006-thematic | University of the West of EnglandのWebサイトの公開PDFをテキスト抽出 | 本文 | 抽出で語間の空白が失われた。PDFの頁と掲載誌の頁の対応は未確認 |
| LIT-braun-clarke-2021-one-size | Semantic Scholar | 要旨 | 大学リポジトリは403 |
| LIT-byrne-2022-reflexive-ta | Crossref | 要旨 | 出版社の本文は認証画面へ転送 |
| LIT-oka-2022-reflexive-ta-ja | J-STAGEのPDF、JaLC | 本文 | 総説 |
| LIT-mayring-2000-qca | FQSの英語PDF・HTML、DataCite | 本文 | 手順図（Fig.1, 2）は画像 |
| LIT-hsieh-shannon-2005-qca | Crossref | 要旨 | |
| LIT-elo-kyngas-2008-qca | Crossref | 要旨 | 出版社のPDFは403 |
| LIT-elo-2014-qca-trustworthiness | Crossref | 要旨 | 出版社サイトは403 |
| LIT-graneheim-lundman-2004-qca | Europe PMC | 要旨 | |
| LIT-krippendorff-2004-reliability、LIT-hayes-krippendorff-2007-alpha | Crossref | 書誌 | 要旨は取得できず |
| LIT-gale-2013-framework | Europe PMCの全文XML（CC BY 2.0） | 本文 | 2026-09-16に直接取得して再確認 |
| LIT-goldsmith-2021-framework | Crossref、DOIの転送先URL | 要旨 | 特集号の論文。頁は未確認 |
| LIT-ritchie-spencer-framework-chapter | Crossref | 書誌 | 出版年・編者はCrossrefにない |
| LIT-otani-2008-scat | JaLC、CiNii、名古屋大学リポジトリ | 書誌 | PDFが画像でテキストを取り出せなかった |
| LIT-otani-2011-scat | J-STAGEのPDF、JaLC | 本文 | 連載記事。PDFにテキスト抽出を許可しない設定があり、読解のためだけに一時領域で抽出した。当初想定したDOI（巻号なし）は存在せず、正しいDOIは 10.5057/kansei.10.3_155 |
| RES-otani-scat-official | 公式ページ | 公式ページ | 2026-09-16に再取得（最終修正2022-03-31） |
| LIT-kinoshita-2007-mgta | 富山大学リポジトリのPDF、JaLC | 本文 | 講演に基づく紀要論文 |
| RES-mgta-society-official | M-GTA研究会のページ | 公式ページ | 2026-09-16に再取得 |
| LIT-kawakita-2003-kj-interview | J-STAGEのPDF、JaLC | 本文 | インタビュー記事 |
| LIT-kawakita-1967-hassoho | CiNii Books | 書誌 | 書籍本文は未入手 |
| LIT-tanaka-kj-quick-manual | mizumot.comで公開されているPDF | 本文 | 研究会の報告論集。発行年は未確認 |
| LIT-scupin-1997-kj | Crossref | 書誌 | 要旨は取得できず |
| LIT-higuchi-2004-quantitative-text | J-STAGEのPDF、JaLC | 本文 | 原著論文 |
| LIT-higuchi-2017-khcoder | J-STAGEのPDF、Crossref | 本文 | |
| RES-khcoder-official | KH Coderの公式サイト | 公式ページ | トップページのみ |
| LIT-salton-buckley-1988-term-weighting、LIT-callon-1983-coword | Crossref | 書誌 | 要旨は取得できず |
| LIT-kilgarriff-2001-comparing-corpora、LIT-grimmer-stewart-2013-text-as-data | Crossref | 要旨 | |
| LIT-kitzinger-1994-focus-groups | Crossref | 要旨 | 出版社のPDFは403 |
| LIT-duggleby-2005-fg-interaction | Europe PMC | 要旨 | |
| LIT-onwuegbuzie-2009-fg-analysis | Crossref | 要旨 | 出版社サイトは403 |
| LIT-hermann-2024-fg-interaction-coding | Semantic Scholar、Crossref | 要旨 | 出版社サイトは403 |
| LIT-gronkjaer-2011-fg-interaction | 学術誌サイト（tidsskrift.dk）のPDF | 本文 | Crossrefの発行日の記録（1970）は誤り |
| LIT-nicholson-shrives-2022-fg-interaction | Semantic Scholar、Crossref | 要旨 | |
| LIT-kidd-parshall-2000-fg-rigor | Europe PMC | 要旨 | 取得した要旨は末尾が欠けている |
| LIT-morgan-1996-focus-groups | Crossref | 要旨 | |

## 取得できなかった資料

- 原典の書籍：川喜田『発想法』（1967）『KJ法』（1986）『KJ法入門コーステキスト』（1997）、木下のM-GTA関連の書籍、Braun & Clarkeの書籍、Ritchie & Spencerの章、樋口（2014）。手順は読めた論文・公式ページ・二次資料の範囲で書き、原典未確認と明記した。
- 出版社サイトが403を返した本文（Kitzinger 1994、Elo & Kyngäs 2008、Elo et al. 2014、Onwuegbuzie et al. 2009、Hermann et al. 2024）。アクセス制限は回避していない。
- SCATの原典論文（大谷 2008）の本文（画像のPDF）。
- 日本語で書かれた、フレームワーク法と質的内容分析の方法論文献は、今回の検索では見つからなかった。

## 照合で修正した記載

- 共通知識の「同質性の高いグループでは同意が生じやすい」という記載は、Grønkjær et al.（2011）の本文で確認できなかったため、本文で確認できた内容（年齢を同質性の要因としつつ対立する意見が出る程度の多様性、司会者の役割）に書き直した。
- 岡ほか（2022）の書き起こしの推奨は、本文（p.149）で確認して頁を付けた。

## 見解が分かれた点

- テーマ分析のコーディングの信頼性：再帰的TAは評定者間一致の計算を行わないとされる一方、コーディングの信頼性型のTAがある（岡ほか 2022）。質的内容分析ではMayring（2000）がコーダー間の一致の確認を手順に含める。手法と流派ごとに品質基準を分けて保存した。
- M-GTAと他のグラウンデッド・セオリー：M-GTAは切片化をしない（木下 2007、M-GTA研究会）。
- KJ法の版：田中の手引きは、複数の流派・版があり、川喜田（1997）版に基づくと明記している。
- 相互作用の分析：会話の連鎖として読む（Grønkjær et al. 2011）、コーディング枠組みでコード化する（Hermann et al. 2024）、非言語を含めて記録する（Onwuegbuzie et al. 2009）。

## 次回に調査すること

- 原典書籍の入手（大学図書館等）と、手順の記述の照合。
- Kitzinger（1994）、Elo & Kyngäs（2008）の本文。
- 日本語のフレームワーク法・質的内容分析の方法論文献と、国内の適用事例。
- Braun & Clarkeの書籍での6フェーズの記述と、2006年の論文との違い。
