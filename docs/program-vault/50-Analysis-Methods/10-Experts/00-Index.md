---
note_id: analysis-experts-index
note_type: method-group
title: 分析手法ごとの専門家定義
status: current
updated: 2026-09-25
tags:
  - gurumoji/analysis
  - gurumoji/expert
---

# 分析手法ごとの専門家定義

専門家定義は、分析手法ごとの目的、流派、分析単位、手順、判断基準、禁止事項、出力形式、限界を、実行時に読み込める形で書いたもの。LLMを再学習させるものではない。専門家（人格）とモデルは別であり、同じモデルを使う場合も、読み込む定義・入力・出力・実行状態を専門家ごとに分ける。

選び方は [[50-Analysis-Methods/00-Method-Selection-Guide]]、全専門家に共通する規則は [[50-Analysis-Methods/08-Common-Knowledge/00-Index]]、文献は [[50-Analysis-Methods/20-Literature/00-Index]]。書式は [[90-Templates/expert-definition]]。

## 実行時の読み込み

実装：`src/gurumoji/method_experts.py`。

1. 分析設定の「主となる分析手法」から主の専門家を選ぶ。未選択（`auto`）の場合は、既存の分析方針が暫定で示す主手法の専門家を「暫定」として選ぶ。
2. 既存の分析方針（`build_focus_group_analysis_plan`）が補助として挙げた手法の専門家を加える。それ以外の専門家は読み込まない。
3. 選んだ専門家の `01-Expert.md` の「実行定義」だけを解析し、適用条件をコードで判定する。
4. 同じフォルダーの知識ノートと、実行定義が参照する文献ノートは、知識hashの計算にだけ使う。内容をAIへ送らない。
5. 手法の結果を保存するときは、結果を出した手法の専門家の確認結果を付ける。保存する手法ノートの「限界と追加確認」にも、担当専門家の判定と文献IDを書く。
6. 分析画面の「手法別」タブを開いたときは、一覧に出る手法の担当専門家を読み込む。結果がある手法には結果への判定を、結果がない手法には実行前に満たす条件を示す（ADR-116）。
7. Gitで共有するこのベースとは別に、実行環境ごとの `<data>/local_knowledge/50-Analysis-Methods/…` があれば同じ相対パスで解決を上書きする（ADR-120、[[40-Design/method-rules#ローカル限定の知識（ADR-120）]]）。一覧の `source` でベース／ローカル追加／ローカル上書きを区別する。

## 専門家の一覧

| 専門家ID | 手法 | 役割 | アプリの手法ID |
| --- | --- | --- | --- |
| [[50-Analysis-Methods/10-Experts/qualitative-content-analysis/01-Expert\|exp-qualitative-content-analysis]] | 質的内容分析 | 方法論 | `qualitative_content` |
| [[50-Analysis-Methods/10-Experts/thematic-analysis/01-Expert\|exp-thematic-analysis]] | テーマ分析 | 方法論 | `thematic` |
| [[50-Analysis-Methods/10-Experts/framework-method/01-Expert\|exp-framework-method]] | フレームワーク法 | 方法論 | `framework` |
| [[50-Analysis-Methods/10-Experts/scat/01-Expert\|exp-scat]] | SCAT | 方法論 | `scat` |
| [[50-Analysis-Methods/10-Experts/m-gta/01-Expert\|exp-m-gta]] | M-GTA | 方法論 | `mgta` |
| [[50-Analysis-Methods/10-Experts/kj-method/01-Expert\|exp-kj-method]] | KJ法 | 方法論 | `kj` |
| [[50-Analysis-Methods/10-Experts/quantitative-text-analysis/01-Expert\|exp-quantitative-text-analysis]] | 計量テキスト分析 | 方法論（補助） | `quantitative_text`、`lexical_frequency`、`cooccurrence`、`speaker_characteristics`、`kwic` |
| [[50-Analysis-Methods/10-Experts/focus-group-interaction/01-Expert\|exp-focus-group-interaction]] | フォーカスグループの相互作用分析 | 方法論 | `interaction` |
| [[50-Analysis-Methods/10-Experts/participation-balance/01-Expert\|exp-participation-balance]] | 発話量・参加バランス | 計算 | `participation` |
| [[50-Analysis-Methods/10-Experts/conversation-timing/01-Expert\|exp-conversation-timing]] | 会話の時間構造 | 計算 | `conversation_dynamics` |
| [[50-Analysis-Methods/10-Experts/descriptive-statistics/01-Expert\|exp-descriptive-statistics]] | 記述統計・度数 | 計算 | `descriptive_statistics` |
| [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert\|exp-group-comparison-statistics]] | クロス集計・群間比較 | 計算 | `group_statistics` |
| [[50-Analysis-Methods/10-Experts/correlation/01-Expert\|exp-correlation]] | 相関 | 計算 | `correlation` |
| [[50-Analysis-Methods/10-Experts/embedding-topic-exploration/01-Expert\|exp-embedding-topic-exploration]] | 埋め込みによるテーマ探索 | 計算 | `transformer_topics` |
| [[50-Analysis-Methods/10-Experts/speech-emotion-recognition/01-Expert\|exp-speech-emotion-recognition]] | 音声感情推定 | 計算 | `audio_emotion` |
| [[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/01-Expert\|exp-japanese-text-preprocessing]] | 日本語テキストの前処理 | 前処理 | `morphology`、`syntax` |
| [[50-Analysis-Methods/10-Experts/cross-session-comparison/01-Expert\|exp-cross-session-comparison]] | 会話間比較 | 比較 | `interview_comparison` |

## 準備状況（2026-09-16）

- 根拠文献確認済み：実行定義が参照する文献すべてに文献ノートを作り、確認範囲と査読状態を記録した。すべての文献を本文で確認したという意味ではない。
- サンプル検証済み：架空のサンプルで確かめた範囲と、確かめていないことは [[50-Tests/method-expert-sample-verification]]。
- 未確認事項：内容は各専門家の `06-Open-Issues.md`。件数は実行定義の `open_issues` の数。

| 専門家 | 根拠文献確認済み | 手順整理済み | 組み込み済み | サンプル検証済み | 未確認事項 | 文献（本文／要旨／書誌のみ／公式ページ） | 査読確認済みの文献 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 質的内容分析 | ✓ | ✓ | ✓ | ✓ | 5件 | 1／5／2／0 | 8件中6件 |
| テーマ分析 | ✓ | ✓ | ✓ | ✓ | 4件 | 2／4／0／0 | 6件中4件 |
| フレームワーク法 | ✓ | ✓ | ✓ | ✓ | 4件 | 2／2／1／0 | 5件中3件 |
| SCAT | ✓ | ✓ | ✓ | ✓ | 5件 | 1／1／1／1 | 4件中1件 |
| M-GTA | ✓ | ✓ | ✓ | ✓ | 4件 | 1／1／0／1 | 3件中1件 |
| KJ法 | ✓ | ✓ | ✓ | ✓ | 4件 | 2／0／2／0 | 4件中0件 |
| 計量テキスト分析 | ✓ | ✓ | ✓ | ✓ | 5件 | 2／4／2／2 | 10件中2件 |
| フォーカスグループの相互作用分析 | ✓ | ✓ | ✓ | ✓ | 5件 | 2／9／0／0 | 11件中8件 |
| 発話量・参加バランス | ✓ | ✓ | ✓ | ✓ | 3件 | 2／3／1／0 | 6件中3件 |
| 会話の時間構造 | ✓ | ✓ | ✓ | ✓ | 4件 | 1／5／0／0 | 6件中5件 |
| 記述統計・度数 | ✓ | ✓ | ✓ | ✓ | 3件 | 0／2／0／0 | 2件中0件 |
| クロス集計・群間比較 | ✓ | ✓ | ✓ | ✓ | 3件 | 2／4／5／0 | 11件中2件 |
| 相関 | ✓ | ✓ | ✓ | ✓ | 3件 | 0／4／2／0 | 6件中0件 |
| 埋め込みによるテーマ探索 | ✓ | ✓ | ✓ | ✓（推論は未実行） | 4件 | 1／5／2／0 | 8件中3件 |
| 音声感情推定 | ✓ | ✓ | ✓ | ✓（推論は未実行） | 6件 | 1／2／3／1 | 7件中2件 |
| 日本語テキストの前処理 | ✓ | ✓ | ✓ | ✓ | 3件 | 0／0／5／1 | 6件中1件 |
| 会話間比較 | ✓ | ✓ | ✓ | ✓ | 3件 | 2／3／0／0 | 5件中2件 |

- KJ法は、本文を確認できたのがインタビュー記事と研究会の手引きで、原典の書籍は未入手。
- 記述統計・相関・日本語テキストの前処理は、本文を確認した文献がなく、手順と数値の根拠の多くを実装（SciPy・GiNZAの仕様）に置いている。
- 「査読確認済み」は、掲載誌・会議の査読方針を確認できた文献の数。古典的な統計文献の多くは、査読方針を確認できず「未確認」にしている。

## 担当の統合・分割と、専門家を置かない機能

- 形態素解析と係り受けは、同じGiNZAの解析結果を後段の分析に渡す前処理で、確認すべき事項（解析器・版・簡易解析への切り替え・書き言葉で評価された精度）も共通のため、1人の専門家にまとめた。
- 語彙頻度、共起、話者別特徴語、文脈検索（KWIC）は、計量テキスト分析の方法論（[[50-Analysis-Methods/20-Literature/LIT-higuchi-2017-khcoder|樋口 2017]]）の中で、探索と原文への往復に使う道具として扱うため、計量テキスト分析の専門家1人が担当する。
- 手動コード・重要引用（`qualitative_coding`）は、質的分析の各専門家が共通に使う記録の道具で、手法ではないため専門家を置かない。
- 専門家を置かない機能：`local_insights`（アプリ固有の入口の要約）、`ai_insights`（方法論の専門家の手順を実行する手段）、`outline`・`ai_finishing`・`meeting_minutes`（研究手法ではない補助・編集の機能）。
- 計画中の手法（[[40-Design/quantification-statistics-plan]]）は、実装されるまで専門家を置かない。

## 各専門家のフォルダーの構成

| ファイル | 内容 |
| --- | --- |
| `00-Overview.md` | 答えられる問い・答えられない問い、流派の違い、既存の手法ノートへのリンク |
| `01-Expert.md` | 専門家定義と実行定義（アプリが読む） |
| `02-Procedure.md` | 手順、各段階の確認事項、迷いやすい点、典型的な失敗と修正、結果のまとめ方 |
| `03-Quality.md` | 判断基準と品質確認 |
| `04-Applicability-and-Limits.md` | 入力の条件、適用できない条件、言えないこと、グループインタビューでの注意 |
| `05-Cases.md` | 文献で確認できた適用例 |
| `06-Open-Issues.md` | 知識が不足している点、文献間で意見が分かれる点 |
