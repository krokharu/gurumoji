---
note_id: analysis-knowledge-evaluation-index
note_type: method-group
title: 知識充足と評価の入口
summary: 専門家と作業段階ごとの根拠・不足・接続・検証を区別して辿る。
status: proposed
review_state: draft
runtime_state: planned
updated: 2026-10-08
tags: [gurumoji/analysis, gurumoji/evaluation]
---

# 知識充足と評価の入口

G1aの読取棚卸しをG1bの登録書式と入口へ渡す。専門家17定義、AI下書き許可9／非許可8という件数は、知識の研究的充足や実行可能な全手法数を意味しない。棚卸しの詳細・取得hashは既存実行packet、工程の区切りは [[40-Design/obsidian-skill-knowledge-work-plan#13. 目標と進行順序]] と [[60-Operations/gurumoji-improvement-session]] に戻る。

## 評価する対象

一行の単位は「専門家×作業段階」。定義・契約の版、実装method／tool・adapter、許可actor・scope、必要入力・根拠位置、文献の確認範囲、未対応・不足、次担当を対応する。base知識hash、個人上書き、実run固定hashを混同しない。統計3契約はG0.5aの受入後に変更対象行だけを更新し、全17定義の再調査を前提にしない。

| 状態 | 何が確認されたか |
| --- | --- |
| 文書なし／不足 | 必須の記録がない、参照できない、または能力未対応 |
| 記載あり・出典未確認 | 前付・存在・hashを確認しただけ。本文・方法論を確認済みにしない |
| 文書レビュー済み | 指定hashと確認範囲に対して独立レビューがある |
| 合成検証済み | 固定fixture・独立期待値と技術結果がある。実データ品質とは別 |
| 実モデル評価済み | 固定モデル・入力・配信・使用量・失敗を含む方法別の実返答を評価した |
| 研究者の採否 | 人の記録に戻れる確定解釈。未回答は未評価 |

これらは確認範囲の説明で、単一の成功フラグではない。ノートやfileの数を分母にして能力充足率を作らない。知識の未読と入力の未読、技術的未対応と研究上の未判定は別欄にする。

## 登録・表示・後続

評価caseの書式は [[90-Templates/knowledge-evaluation]]、対応登録は [[90-Templates/skill-hook-binding]]。既存の方法別サンプルは [[50-Tests/method-expert-sample-verification]]、不足は各専門家の06へ戻す。新しい評価で既存の成功範囲を広げない。

一覧は [[50-Analysis-Methods/50-Knowledge-Evaluation/knowledge-readiness.base]]。既存expert定義、今後の08対応、登録スキルと評価ノートの前付を見る補助で、Markdown内の充足表の一行ごとの集計ではない。空欄は未記録であり、確認済みやゼロではない。PythonのID・参照・YAML検査とObsidian本体の表示確認を別に記録する。1.13.7で利用できるtable形式を用い、kanbanやコミュニティプラグインを前提にしない。

17定義の充足表、試行3専門家の対応、仮書式の独立レビューと表示確認はG1bの後続。G2はG1bとF04の技術結果後、G3／G4はそれぞれの受入後に進む。F03の配信比較保留を知識整理の合格や新方式採用に換算しない。
