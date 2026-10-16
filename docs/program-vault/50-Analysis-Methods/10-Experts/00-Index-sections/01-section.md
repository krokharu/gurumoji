---
note_type: reference-section
status: current
updated: 2026-09-25
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: analysis-experts-index-section-01
title: 分析手法ごとの専門家定義：分析手法ごとの専門家定義
summary: 分析手法ごとの専門家定義。出典ノート「分析手法ごとの専門家定義」の分割本文。
parent_note_id: analysis-experts-index
source_path: 50-Analysis-Methods/10-Experts/00-Index.md
source_sha256: 6835e27a046b96994777b408f3d69461316d4bc1dc03b458398a4fc19d8d8466
source_body_lines:
- 1
- 41
split_on: '2026-10-11'
---

# 分析手法ごとの専門家定義：分析手法ごとの専門家定義

親索引・状態・確認版：[[50-Analysis-Methods/10-Experts/00-Index]]。必要な本文だけを取得する。


# 分析手法ごとの専門家定義

専門家定義は、分析手法ごとの目的、流派、分析単位、手順、判断基準、禁止事項、出力形式、限界を、実行時に読み込める形で書いたもの。LLMを再学習させるものではない。専門家（人格）とモデルは別であり、同じモデルを使う場合も、読み込む定義・入力・出力・実行状態を専門家ごとに分ける。

選び方は [[50-Analysis-Methods/00-Method-Selection-Guide]]、全専門家に共通する規則は [[50-Analysis-Methods/08-Common-Knowledge/00-Index]]、文献は [[50-Analysis-Methods/20-Literature/00-Index]]。書式は [[90-Templates/30-Knowledge/expert-definition|expert-definition]]。

## 実行時の読み込み

実装：`src/gurumoji/method_experts.py`。

1. 分析設定の「主となる分析手法」から主の専門家を選ぶ。未選択（`auto`）の場合は、既存の分析方針が暫定で示す主手法の専門家を「暫定」として選ぶ。
2. 既存の分析方針（`build_focus_group_analysis_plan`）が補助として挙げた手法の専門家を加える。それ以外の専門家は読み込まない。
3. 選んだ専門家の `01-Expert.md` の「実行定義」だけを解析し、適用条件をコードで判定する。
4. 同じフォルダーの知識ノートと、実行定義が参照する文献ノートは、知識hashの計算にだけ使う。内容をAIへ送らない。
5. 手法の結果を保存するときは、結果を出した手法の専門家の確認結果を付ける。保存する手法ノートの「限界と追加確認」にも、担当専門家の判定と文献IDを書く。
6. 分析画面の「手法別」タブを開いたときは、一覧に出る手法の担当専門家を読み込む。結果がある手法には結果への判定を、結果がない手法には実行前に満たす条件を示す（ADR-116）。
7. Gitで共有するこのベースとは別に、実行環境ごとの `<data>/local_knowledge/50-Analysis-Methods/…` があれば同じ相対パスで解決を上書きする（ADR-120、[[40-Design/50-Governance/method-rules/03-section#ローカル限定の知識（ADR-120）|method-rules#ローカル限定の知識（ADR-120）]]）。一覧の `source` でベース／ローカル追加／ローカル上書きを区別する。

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
