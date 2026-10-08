---
note_id: analysis-skills-index
note_type: method-group
title: 分析スキルの入口
summary: 作業段階から必要な知識と登録書式へ進む。実行接続の状態は別に確認する。
status: proposed
review_state: draft
runtime_state: planned
updated: 2026-10-08
tags: [gurumoji/analysis, gurumoji/skill]
---

# 分析スキルの入口

G1bで整える登録書式と作業別入口。配信方式はcurrentPackを暫定維持し、スキルノートの存在で取得方式や実行許可を変更しない。現行実行定義は [[50-Analysis-Methods/10-Experts/00-Index]]、共通知識は [[50-Analysis-Methods/08-Common-Knowledge/00-Index]]。

## 作業から辿る

|作業|最初に確認するもの|次の入口|
|---|---|---|
|方法・専門家を選ぶ|研究質問、分析単位、媒体、実在する能力と未対応理由|[[50-Analysis-Methods/00-Method-Selection-Guide]]、専門家の01・04|
|スキルを登録する|条件、許可procedure・actor、必須知識、出力、停止・引継ぎ|[[90-Templates/skill-definition]]|
|専門家へ対応する|01の許可集合、07の出力とphase、既存adapter、scope|[[90-Templates/skill-hook-binding]]|
|取得・受領・復旧を確認する|実配信範囲、固定参照、上限、callbackの実在と版|[[50-Analysis-Methods/40-Skills/80-Hooks/00-Index]]|
|充足・不足を確かめる|対象ID・版・hash、確認済み範囲、未読・未実行|[[50-Analysis-Methods/50-Knowledge-Evaluation/00-Index]]|

## 登録と実行の境界

登録候補は一意のID、短いsummary、単純な前付、必要節と安定したブロックIDを持つ。必須知識・出力・停止条件を外さず、任意の補足と区別する。テンプレート、研究ログ、自由な全文探索を実行命令として取り込まない。

08対応ノートのreader、汎用skill／hook登録、任意成果物の入力bindingはG4の対象。ここでは`planned`／理由付き`blocked`を保ち、接続済み能力へ数えない。共通Handler、AnalysisStore、既存の非LLM Obsidian管理担当を再利用する。研究者の採否・個人上書き・利用目的と送信権限を文書登録で変更しない。

固定参照（提案・runtime未登録）：[[30-Data/analysis-asset-connection-v1|data-analysis-asset-connection-v1]] proposal_revision 3 @17c3bcf4d9b4c0f41d8cd9ac6cc83fe6086ed925 / `00c42234f95ab433542432cddaf61b29191e0b9f00ae645127d882230bd5e9a5`、[[50-Analysis-Methods/40-Skills/thematic-candidate-evidence|thematic-candidate-evidence]] skill_version 1・proposal_revision 3 / `8f7860af502ba9dd6e33da259309284bd53f2fa64c9d91a5d0754c66c82b5527`、[[50-Analysis-Methods/40-Skills/correlation-exploratory-evidence|correlation-exploratory-evidence]] skill_version 1・proposal_revision 3 / `3d29a901c8fc64c7d0822310bb8e97e7137e661431dcd0851e25a766eb7eb2ec`、[[50-Analysis-Methods/40-Skills/group-comparison-exploratory-evidence|group-comparison-exploratory-evidence]] skill_version 1・proposal_revision 3 / `eb1475f67af863bd232ef3b0701c7bea71c7405c7ce95b8a0fa854544574729d`、[[50-Analysis-Methods/40-Skills/group-interview-evidence-workflow|workflow-group-interview-evidence]] workflow_version 1・proposal_revision 3 / `1a8ed0b31076f5ade8ddb30ca953ac00debf022a3b08b20b4544221a096a2a32`。全て提案・draft・planned。08から固定手順を参照しても、文書skill IDの存在は実行runtime登録を意味しない。工程と受入条件は [[40-Design/obsidian-skill-knowledge-work-plan#13. 目標と進行順序]] を参照する。

## 固定ブロックの取得範囲（提案）

上記hashの文書でquote全体・table全行を取得。IDは外側・空行区切り。見出し自動拡張なし、reader未接続/GUI未確認。

|skill|guards（全条件）|procedure（全行）|output（全出力・停止）|
|---|---|---|---|
|correlation-exploratory-evidence|[[50-Analysis-Methods/40-Skills/correlation-exploratory-evidence#^cee-guards\|cee-guards]]|[[50-Analysis-Methods/40-Skills/correlation-exploratory-evidence#^cee-procedure\|cee-procedure]]|[[50-Analysis-Methods/40-Skills/correlation-exploratory-evidence#^cee-output\|cee-output]]|
|group-comparison-exploratory-evidence|[[50-Analysis-Methods/40-Skills/group-comparison-exploratory-evidence#^gcee-guards\|gcee-guards]]|[[50-Analysis-Methods/40-Skills/group-comparison-exploratory-evidence#^gcee-procedure\|gcee-procedure]]|[[50-Analysis-Methods/40-Skills/group-comparison-exploratory-evidence#^gcee-output\|gcee-output]]|

取得単位は[Obsidian公式のブロック参照仕様](https://obsidian.md/help/links)に従う提案。旧reviewの不足は履歴として保持し、本修正の独立確認で別に判定する。

|文書|必須の取得範囲・native型|
|---|---|
|data-analysis-asset-connection-v1|quote: ^asset-types=SourceRef/SchemaRef/Scope/Actor/Adapter/AssetKey/Asset/AssetState全表・規則、^asset-hash=domain/canonical/vector/負例、^asset-binding=Slot/InputRef/Binding/依存・採用前照合、^asset-measures=単位/出所/分母/null|
|thematic-candidate-evidence|quote: ^tce-guards=全条件、^tce-output=分岐/全Subschema/CandidateContent/ThemeContent/HumanRecord/Receipt/UnreadSets。table: ^tce-procedure=全行|
|workflow-group-interview-evidence|quote: ^giew-units=単位/分母全体、^giew-binding=接続/配信/停止全体、^giew-procedure-guards=FGI注意段落。table: ^giew-purpose/^giew-procedure/^giew-cases=各全行。procedureは表＋注意quoteの両方必須|

履歴:0485b3e=旧author5票format、2907391=旧限定norm/hash。独立block受入なし、必須取得は現r3。

02追加必須節:TA/COR/GRP/FGIの「判断に迷いやすい点」「典型的な失敗と修正」「結果のまとめ方」、TA02の前提/Byrne実務、FGI02の記録（元見出し）。表外・安定IDなし、section指定・未取得needs_input。native table IDで全節取得を推測しない。
