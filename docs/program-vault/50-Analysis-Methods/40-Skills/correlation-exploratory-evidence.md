---
note_id: skill-correlation-exploratory-evidence
note_type: executable-skill
title: 探索的相関と固定根拠の手順（提案）
summary: 初期発話の相関計画・正式計算表・人の確認待ちを結ぶ。
status: proposed
schema_version: 1
skill_id: correlation-exploratory-evidence
skill_version: 1
proposal_revision: 3
expert_ids: [exp-correlation]
stage: analysis_plan_and_result_explanation
review_state: draft
runtime_state: planned
required_note_ids: [data-analysis-asset-connection-v1, expert-correlation-definition, expert-correlation-procedure, expert-correlation-quality, expert-correlation-limits, expert-correlation-agent-contract, expert-correlation-skill-hook-binding, analysis-common-evidence-and-claims, analysis-common-source-classification, analysis-common-group-interview-data]
optional_note_ids: []
guards_block_id: cee-guards
procedure_block_id: cee-procedure
output_block_id: cee-output
updated: 2026-10-08
tags: [gurumoji/skill, gurumoji/analysis]
---

# 探索的相関と固定根拠の手順（提案）

[[90-Templates/skill-definition]]準拠。新phaseを登録しない。stageは既存のanalysis_planとresult_explanationを包む文書上の分類。01 D2、07 S2/C2を維持し、汎用reader・callback・executor追加0。統計限定parserの既存受入と本票の接続は別。

## 条件・取得・停止

> 問いは1会話の発話単位の数値変数間の探索的関連。scope=all_included_initial、固定入力版/hash・除外集合・変数定義/尺度/単位・用途・送信許可を必要とする。話者ラベルを独立参加者IDにしない。変数対の選択、分布、解釈は人の未回答として保持する。
>
> 必須取得は下表の全required note IDの指定位置。02「手順と各段階の確認事項」は全行を取得し、actor・必須集合・停止を含む本票の全段階表も一ブロックとして渡す。部分取得失敗を全文自由取得で補わない。08 B2は凍結source snapshotであり、将来D2 B3のwrapper hashは参照しない。
>
> 共通型/slot/hash/binding/多親intersection/世代/取消/発注前・採用前照合は[[30-Data/analysis-asset-connection-v1#^asset-binding]]を再利用。必須未解決・任意でもselectedなら待機、omittedは理由を固定。用途不明、全親許可の共通部分が空、未配信、期限/残予算不足は依存consumer保留。unknown method/actor/hash偽装はrejected、section/採用ラベル/任意表・参加者推論はunsupported。本人記録欠落・意味未判定はhuman_pending。能力不足はHandler/G4、人の判断は研究者へ渡す。旧bundleは元hashの読取のみ、強制再開しない。
>
> AI必須集合は計画[cor-ai-plan]、説明[cor-ai-report]、許可集合も01のこの2stepのみ。required_ai_steps <= performed_step_ids <= allowed_ai_steps、重複不可。自己申告は実code/本人record証拠ではない。研究者recordは本人ID・日時・step・入力版/hash・結果hash・判断・原record参照へ戻るものだけ。取得経路未対応なら架空recordを作らない。cor-a1〜a4/q1〜q3の既存条件・警告を保持し閾値を変えない。

^cee-guards

## 全段階表（必須ブロック）

| phase | step / actor | 必須入力→出力・確認 | 不足・停止 |
| --- | --- | --- | --- |
| analysis_plan | cor-ai-plan / ai_draft | 01/02/03/04/07/08＋共通知識、固定profile/input/knowledge hash→計画・前提・pearson/spearman提案 | 未取得needs_input、計算済みとしない |
| analysis_plan | cor-p1 / researcher | 変数対/種類・目的・欠測を本人が決めたrecord | 未回答human_pending、AI代行不可 |
| analysis_plan | code stepなし | result IDs/bindings/claimsは空、計算未実行 | cor-p2完了申告を受理しない |
| result_explanation | cor-ai-report / ai_draft | 同じ知識版＋提供済み正式結果→探索的説明・未読・限界 | 別phase/空step/未配信は未完了 |
| result_explanation | cor-p2 / code | Handler正式task、同run/版/許可method保存表、原全行hash→セル状態 | stale/隔離/参照不一致拒否 |
| result_explanation | cor-p1 / researcher | 計画recordを同じ入力/対象へ再照合 | 旧版record流用不可 |
| result_explanation | cor-p3 / researcher | 歪み/外れ値/同順位と元発話IDの本人確認 | 推測補完不可、human_pending |
| result_explanation | cor-p4 / researcher | 探索的扱い、入れ子/多重比較/解釈の本人判断 | 因果・方向・独立参加者推論禁止 |

^cee-procedure

## 出力と原セル

> 07 S2/C2の5必須string=analysis_plan/prerequisite_review/result_explanation/quality_record/limitations。計画はneeds_calculation、calculation_result_ids=[]/numeric_bindings=[]/claims=[]。説明はdraft、検証済みresult参照のみ。不足needs_input、不適用not_applicableは理由とbindings=[]を保持。semantic undeterminedをCore採用や確定解釈へ昇格させない。
>
> numeric_bindingsは厳密9キーのみ：result_id, dataset, row_id, column, variables, target, dataset_version, computation_input_hash, rows_hash。value/表示文/丸め桁追加禁止。dataset=correlations、variables=[variable_a,variable_b]の順序、target={scope,selectors:{method}}を原manifest/行に照合。result/table/raw hash・全原行rows_hash・入力/定義版・対象集合/分母を固定し、抜粋からhashを再作成しない。N/missing/unit_a/unit_b/coefficient/p_value/status/p_value_adjustmentは同じ原行からコード表示する。
>
> statistical-cells-v1：N/欠測は整数、係数等はDecimal(str(value))/ROUND_HALF_EVEN小数3桁、負の丸めゼロは0.000。pは4桁（0.0000≠厳密0）、既存percentは2桁%で二重100倍禁止。null/非有限/列欠落/未計算は数値表示しない。partialは計算済みセルとnot_computedを分け、欠測を0/p=1で埋めない。自由文数値は未検証下書き、コードで黙って修正しない。CI・補正・変換/並べ替え検定は原結果にない限り未提供/未実行。
>
> 正式capabilityはstatistical-tools-1のpearson/spearman、固定snapshotの既存統計エンジンのみ。新採用指標はG4c案として、承認済み定義→登録projection→aggregate(unit/分母/欠測)→join(キー/多重度)を別stepで準備する。式はcode所有のみ。参加者対応・独立性・本人採否を確認しても現行allinitial adapterが新表に接続済みとはしない。

^cee-output

## case対応と文書trace

G1B-COR-01〜06を別名で拡張しない：01=正常計画→正式表→説明・human_pending、02=未知/非許可method拒否、03=wrongunit/section unsupported、04=未review/採用後表保留、05=9キー/hash/actor偽装拒否、06=未配信/未計算0化/因果断定停止。正常traceは固定初期発話→cor-ai-plan→正式cor-p2→正しい提供セル→cor-ai-report、p1/p3/p4未回答のまま。隔離負例は同traceのrows_hashだけ差替え→rejected、数値や人recordを補完しない。

これらは規範行でruntime fixture実行0。共通44（REUSE12+CONN6+QA7+ASSET8+GI11）とTA6のG3先行50とは別で、新手順をその50で試験済みとしない。元G1b COR6/GRP6も別alias集合、分母を拡大しない。独立文書review、実モデル品質、人の採用、全G2〜G4は未完。

## 固定source manifest

以下はnote byteを読んだ範囲であり文献原文読了ではない。01/02/03の文献由来説明は既存abstract等の確認範囲に限定、implementationはコード判断、[整理]はsynthesis。書誌のみ/未取得原典を読了扱いせず、新研究主張を追加しない。共通契約のsource8旧aggregate 2dc1f60b6809a7e275d57580f2d844ec4b51a2423524c106d75231a34d1b1bb3は歴史値で、現在source全体の検証値ではない。

Read scope: 01 D2 input/procedure; 02 whole stage table; 03 quality; 04 limits (2026-09-16; GRP02 corrected); 07 S2/C2 phases/cells/status; 08 B2 stages/slots/hooks. 07/08 commit 5c40a0d3065f77039bad87a88eac91cbf6020d55.

| note_id | raw SHA-256 |
| --- | --- |
| expert-correlation-definition | 5a499ea69a38f176a1212ab52d4fe85b8237aaf80ba6fd1b5deed148a14642bb |
| expert-correlation-procedure | 77bb9f85f528dec64e7c3605252f34fd55e962fa698a12e602349f7892bc909e |
| expert-correlation-quality | fa8dcd1c4121132552e17d2991b4469ece84d9c1f86cd6621eabab3149fea49e |
| expert-correlation-limits | fe7aaaeab6959575ce7924353730f2d5592fd11fe86b942786525ed1e95e0a14 |
| expert-correlation-agent-contract | 92c02db1e1db0f68ed2ff0febd3b5d5615149a748bf0b2a7a534dc06478bb3d2 |
| expert-correlation-skill-hook-binding | 3115a75cff595496990e739f531c64ba3ac5f1f75aff35eed06770944dbaf9e6 |

Shared manifest: data-analysis-asset-connection-v1 S1/rev3, raw 00c42234f95ab433542432cddaf61b29191e0b9f00ae645127d882230bd5e9a5, commit 17c3bcf4d9b4c0f41d8cd9ac6cc83fe6086ed925. Inherit its source-table E/SC/GI/PR/T note IDs and raw hashes. Read scope: E evidence/human review; SC access scope; GI all cautions; PR preparation/version; T mandatory fields. E/SC/GI version 2026-09-15, PR v1, T 2026-10-08. Read ^asset-types/hash/binding/measures; note sections only, no original literature read.
