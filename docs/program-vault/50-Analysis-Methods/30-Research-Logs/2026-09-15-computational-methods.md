---
note_id: research-log-2026-09-15-computational-methods
note_type: research-log
title: 計算系の手法の調査記録
status: current
updated: 2026-09-16
tags:
  - gurumoji/research-log
  - gurumoji/analysis
---

# 計算系の手法の調査記録（2026-09-15〜16）

## 目的と範囲

登録済みの計算系の手法（`analysis_method_registry.METHODS`）について、専門家定義に必要な判断基準と限界の根拠を集めた。対象：発話量・参加バランス、会話の時間構造、記述統計、クロス集計・群間比較、相関、Transformerによるテーマ探索、音声感情推定、日本語の形態素・係り受け（前処理）、グループインタビューの横断比較。AI補助の境界に使う文献（LLMによる注釈）もここに記録する。

既存の手法ノートと [[50-Analysis-Methods/99-Peer-Reviewed-References]] にある文献は、本調査で改めて書誌を確認し、要旨を取得できたものは確認範囲を「要旨」にした。

## 検索・取得の方法

Crossref API（書誌・要旨欄・更新情報）、Semantic Scholar API（一括取得と題名検索）、Europe PMC API、ACL AnthologyのBibTeX、NeurIPSの会議録サイト、Hugging FaceのPapers API（arXiv APIが429を返したため）とモデルAPI、GiNZAの公式ドキュメント。検索語に分析対象のデータを含めていない。DBLPは自動アクセスの確認画面を返したため、回避せずに取得を中止した。

## 確認した資料と確認範囲

| 文献ID | 取得経路 | 確認範囲 | 備考 |
| --- | --- | --- | --- |
| LIT-stivers-2009-turn-taking、LIT-sacks-1974-turn-taking | Crossref | 要旨 | |
| LIT-levinson-torreira-2015-timing | Semantic Scholar | 要旨 | |
| LIT-heldner-edlund-2010-pauses | Semantic Scholar | 要旨の一部 | 既存ノートの記述は裏付けられなかった |
| LIT-park-2022-diarization-review | arXiv版のPDF、Crossref | 本文（arXiv版） | 掲載版との同一性は未確認 |
| LIT-woolley-2010-collective-intelligence | Europe PMC | 要旨 | Crossrefの要旨欄は編集部の紹介文 |
| LIT-stephan-mishler-1952-participation | Crossref | 書誌 | 終頁はCrossrefにない |
| LIT-delacre-2017-welch | 掲載誌の記事ページ（HTML） | 本文 | 2026-09-16に再取得。訂正記事の案内を確認（IRSP 35(1), 2022、内容は未読） |
| LIT-appelbaum-2018-jars-quant | Europe PMC、Crossrefの更新情報 | 要旨 | 訂正記事（American Psychologist 73(7), 947）を確認、内容は未読 |
| LIT-bishara-hittner-2012-correlation、LIT-aarts-2014-nested-data | Europe PMC | 要旨 | |
| LIT-benjamini-hochberg-1995-fdr | Crossref | 要旨 | |
| LIT-jaeger-2008-logit-mixed、LIT-rousseeuw-1987-silhouette、LIT-reimers-gurevych-2019-sbert、LIT-hsu-2021-hubert | Semantic Scholar | 要旨 | Reimers & Gurevychの頁はCrossrefとACL Anthologyで2頁ずれる |
| LIT-rasch-2011-pretest、LIT-cochran-1952-chi-square、LIT-cochran-1954-chi-square、LIT-kruskal-wallis-1952、LIT-spearman-1904-rank、LIT-lloyd-1982-kmeans | Crossref | 書誌 | 要旨は取得できず |
| LIT-holm-1979-multiple-testing | 検索結果とJSTORの安定URL | 書誌 | CrossrefのDOIの記録なし。JSTORのページ本体は未取得 |
| LIT-chang-2009-reading-tea-leaves | Semantic Scholarの題名検索、会議録サイト | 書誌 | 要旨を取り出せず、DBLPは確認画面のため中止 |
| LIT-grootendorst-2022-bertopic、LIT-wang-2024-multilingual-e5 | Hugging FaceのPapers API | 要旨 | プレプリント |
| LIT-baevski-2020-wav2vec2 | NeurIPSの会議録サイト | 書誌 | 題名のみ確認 |
| LIT-kosaka-2024-emotional-speech-recognition | Crossref | 書誌 | 発行年は2024。既存の一覧の年（2023）・位置づけと食い違う |
| LIT-barrett-2019-emotional-expressions | Crossref、更新情報 | 要旨 | 訂正記事（PSPI 20(3), 165–166）を確認、内容は未読 |
| LIT-schuller-2018-ser | Crossref | 書誌 | 1文の紹介文と副題のみ |
| RES-kushinada-hubert-jtes-er-model-card | Hugging Faceのモデルページとモデル API | 公式ページ | ゲート付きのためREADMEの直接取得は401。回避していない |
| LIT-kudo-2004-japanese-morphology、LIT-omura-asahara-2018-ud-japanese、LIT-nivre-2020-ud-v2、LIT-takaoka-2018-sudachi | ACL AnthologyのBibTeX | 書誌 | |
| LIT-matsuda-2020-ginza | Crossref | 書誌 | 記事の区分は未確認 |
| RES-ginza-official | GiNZAの公式ドキュメント | 公式ページ | 2026-09-16に再取得 |
| LIT-gilardi-2023-llm-annotation | Europe PMC | 要旨 | |

## 取得できなかった資料

- 統計の古典的文献の本文（有料）。書誌だけを確認し、手順・数値の根拠にはSciPyの実装と既存の手法ノートの記述を使った。
- JTES（日本語感情音声コーパス）の論文本文と、いざなみのモデルカード。
- 日本語の相づち・ターン間の間の研究（Maynard 1986など）は、今回は検索・確認していない。

## 照合で見つかった食い違い

- 既存の一覧のKosaka et al.（2023、「JTESを用いた日本語感情音声認識」）は、Crossrefでは2024年発行で、題名からは感情を含む音声の音声認識（文字起こし）の論文と読める。既存の記載は書き換えず、該当ノートに注意を追記した。
- 既存の手法ノートのHeldner & Edlund（2010）についての記述（閾値・統計処理の方法論的問題の報告）は、要旨の一部からは確認できなかった。

## 次回に調査すること

- 日本語の会話における相づち・応答の間の研究（相づち検出の妥当性のため）。
- 日本語音声感情認識の、対話データ・複数話者条件での評価と、JTESの収録条件。
- 話者分離の誤りが会話分析の指標（遷移数、重なり）に与える影響を扱った研究。
- 訂正記事（Delacre et al. 2017、Appelbaum et al. 2018、Barrett et al. 2019）の内容。
