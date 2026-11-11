---
note_id: skill-group-comparison-exploratory-evidence
note_type: executable-skill
title: 探索的群間比較と固定根拠の手順（提案）
summary: 初期発話の比較計画・正式表・本人の前提確認を結ぶ。
status: proposed
schema_version: 1
skill_id: group-comparison-exploratory-evidence
skill_version: 1
expert_ids: [exp-group-comparison-statistics]
stage: analysis_plan_and_result_explanation
review_state: draft
runtime_state: planned
required_note_ids: [data-analysis-asset-connection-v1, expert-group-comparison-statistics-definition, expert-group-comparison-statistics-procedure, expert-group-comparison-statistics-quality, expert-group-comparison-statistics-limits, expert-group-comparison-statistics-agent-contract, expert-group-comparison-statistics-skill-hook-binding, analysis-common-evidence-and-claims, analysis-common-source-classification, analysis-common-group-interview-data]
optional_note_ids: []
guards_block_id: gcee-guards
procedure_block_id: gcee-procedure
output_block_id: gcee-output
updated: 2026-10-08
tags: [gurumoji/skill, gurumoji/analysis]
---

# 探索的群間比較と固定根拠の手順（提案）

[[90-Templates/skill-definition]]準拠。stageは既存2phaseの文書分類。01 D2/07 S2/C2を維持しreader/callback/executor追加0、限定parser≠本票接続。

## 入力・能力・停止

1会話、発話単位、scope=all_included_initial。比較軸/群/変数/定義版/除外/欠測/分母・入力hash・用途/送信方針を固定。required noteは末尾指定節、02/本票段階表はactor/全行/必須/停止を一括取得、不足needs_input。08 B2は凍結、未来B3 wrapper hash逆参照なし。

| slot・readiness | kind / role | schema・unit・scope・actor・adapter |
| --- | --- | --- |
| 目的/前提・対象必須 | 原本parameter_source/data_input、別ref evidence_context | 07 string/null、SourceRef入力版。発話/固定会話、R指定/Handler固定 |
| 説明の正式結果必須、計画は0 | observation_table / data_input | 07 datasets/manifest/9キー、発話/allinitial、code grp-p2、statistical-tools-1 |
| 選択根拠は条件選択任意 | claim_set/relation_graph/observation_table / selection_basis | 共通SchemaRef/Meaning/Scope/Actor照合。汎用resolver未接続 |
| 確定に本人record/定義必要 | SourceRef / parameter_source | R本人/step/入力・結果hash、取得未対応はhuman_pending |
| 媒体は問いが要求時必須 | 原本SourceRef / evidence_context | 固定媒体版/用途/配信、なければ依存枝needs_input |
| 順序・系列を選択時 | event_sequence / evidence_context | 会話内順序/valid_time、任意series→統計変換非対応 |
| 埋込を選択時 | embedding_matrix / data_input | 本手順の対応slot/adapterなし、unsupported |

5kind/4roleは[[30-Data/analysis-asset-connection-v1#^asset-types]]の型を再利用。原本/receiptを研究kindへ潰さない。表が同kindでもschema/尺度/unit/scope/actor/adapter版・実capability・consumer目的/全親policyが一致しなければ実行不可。required未解決、optionalでもselectedなら待機、omitted理由を固定。用途/送信先intersectionが空、世代/取消/期限/残予算不一致は依存consumer保留。発注前＋採用前に再照合。未知method/偽hash/actorはrejected、section/採用ラベル新表/任意式/独立参加者推論はunsupported。未配信needs_input、意味/本人未回答human_pending。能力はHandler/G4、人判断は研究者へ。旧bundle読取のみ、強制resumeなし。

^gcee-guards

## 全段階表（必須ブロック）

| phase | step / actor | 必須証拠・手順 | 不足・停止 |
| --- | --- | --- | --- |
| analysis_plan | grp-ai-plan / ai_draft | 01/02/03/04/07/08＋共通知識・profile/input/knowledge hash→許可計算の計画/前提 | 未取得needs_input、結果未実行 |
| analysis_plan | grp-p1 / researcher | 比較目的/群/変数/コード定義/除外の本人record | 未回答human_pending、AI代行不可 |
| analysis_plan | code stepなし | result IDs/bindings/claims空 | grp-p2実行を申告しない |
| result_explanation | grp-ai-report / ai_draft | 同じ知識版＋提供済み固定表→探索的説明/未読/限界 | 空/別phase step・未配信は未完了 |
| result_explanation | grp-p2 / code | 正式Handler task・同run/版/許可method・保存原行hash | stale/隔離/不一致拒否 |
| result_explanation | grp-p1 / researcher | 計画recordを同入力/対象へ再照合 | 旧版record流用不可 |
| result_explanation | grp-p3 / researcher | 期待度数/群の大きさ/分散差の本人確認 | code警告だけで完了不可 |
| result_explanation | grp-p4 / researcher | 探索性/入れ子/多重比較/解釈の本人判断 | 未判定human_pending、因果/一般化禁止 |

^gcee-procedure

AI必須集合は計画[grp-ai-plan]/説明[grp-ai-report]、01許可2step内。required<=performed<=allowed、重複不可。AI申告≠実code/本人確認。本人recordはID/確認者/日時/step/入力版hash/結果hash/判断/原記録参照のみ、架空record不可。grp-a1〜a6/q1〜q4の閾値・警告・actorを維持。

## 出力・数値・将来入力の境界

07 S2/C2の5必須string=analysis_plan/prerequisite_review/result_explanation/quality_record/limitations。計画needs_calculationはcalculation_result_ids=[]/numeric_bindings=[]/claims=[]、説明draftは正式提供結果のみ。needs_input/not_applicableは具体的不足/理由を保持、不適用bindings=[]。semantic undeterminedをCore採用で確定化しない。

numeric_bindingsは厳密9キーのみ：result_id,dataset,row_id,column,variables,target,dataset_version,computation_input_hash,rows_hash。value/表示文/丸め桁禁止。crosstabsはvariables=[row_variable,column_variable]、target={scope,selectors:{table_id,row_value,column_value}}。testsはvariables=[outcome]、selectors={family,test,group_variable}。同run/版/raw表/全原行hashとN/groups/missing/unit/assumption_note/effect_name/p_value_adjustmentを同じ行へ照合し、抜粋でhashを再作成しない。

statistical-cells-v1は原値を変更せずcode描画：N/度数整数、統計量/効果量等Decimal(str(value))/ROUND_HALF_EVEN 3桁・丸め負ゼロ0.000、p4桁（0.0000≠厳密0）、percent2桁%で二重100倍禁止。null/非有限/列欠落/未計算は理由表示、partialとnot_computedを区別し0で埋めない。observed 0は有効観測、missing null/excluded/unprocessed/unknownは別状態、空集合とも異なる。自由文数値は未検証下書き。CI/補正/効果量欠落は未提供。

実capabilityはstatistical-tools-1のcrosstabs/anova/kruskal_wallis/chi_square。標準ANOVAは既存f_oneway(*samples)、equal_var=False指定なし。Welch/paired/nestedや任意式を実装済みとしない。多数検定から有意なものだけ選ぶ、因果/重要性/安定個人差/参加者母集団へ一般化する結論は禁止。期待度数警告・話者未確認を人p3へ戻す。

G4c案は後日の承認済み採用定義/参加者対応を入力に、登録projection→aggregate(unit/分母/欠測)→join(キー/多重度/件数)を別stepとする。code所有式だけ、現行allinitial adapterには任意の採用後表を渡さない。未対応の共同発話配分・反復参加・入れ子推論は当consumerのみblocked。

^gcee-output

## case対応・文書trace

G1B-GRP-01〜06の同aliasを維持：01正常計画/正式表/説明・human_pending、02 unknown/Welch/非許可拒否、03 section/wrongunit unsupported、04未review label/採用後表保留、05セルhash/actor偽装拒否、06未配信/null0化/禁止一般化停止。正常traceは初期版→grp-ai-plan→登録grp-p2表→正しい提供セル→grp-ai-report、人p1/p3/p4未回答。隔離負例はrow_valueのみ別群へ→rejected、原値修正なし。

規範行で実fixture実行0。共通44（REUSE12+CONN6+QA7+ASSET8+GI11）＋TA6の先行G3 50とは別、新手順の分母に転用しない。元COR6/GRP6も各alias集合で維持。独立文書review・実モデル・人採否・全G2〜G4未完。

## 固定source manifest

note読取≠原文読了。abstractは要旨、implementationはcode判断、[整理]はsynthesis、未取得unread。Delacreの2群tをANOVAへ拡張しない。新研究主張0、共通source8旧aggregateは歴史値のみ。

Read scope: 01 D2 input/procedure; 02 whole stage table; 03 quality; 04 limits (2026-09-16; GRP02 corrected); 07 S2/C2 phases/cells/status; 08 B2 stages/slots/hooks. 07/08 commit 5c40a0d3065f77039bad87a88eac91cbf6020d55.

| note_id | raw SHA-256 |
| --- | --- |
| expert-group-comparison-statistics-definition | 15ac2cd8ffd7c02a9ffd8d99215a6a2a31fc1b776d3702da23e73b05f3fc9906 |
| expert-group-comparison-statistics-procedure | 61b70f55d5be860a88554f1ed51437dce3f5e3039eff780fe01ebbc97f068f14 |
| expert-group-comparison-statistics-quality | de1017b055957be6137ea7915cfce736236e18d75b5acebe47e5ed6f6b5c3709 |
| expert-group-comparison-statistics-limits | 71f3ca8c3438b523efc0edb4541f85314c12990debe44afc29a0559e9f294a3a |
| expert-group-comparison-statistics-agent-contract | a1ed398b0e6f759448fd4b327eccb1d672f5bada923a4f377e82f98a16ed0c5a |
| expert-group-comparison-statistics-skill-hook-binding | b92757b66b85ebf640ce6bf5869c80c3fc2a95525c70d8b8d1fae24e18fe98c4 |

Shared manifest: data-analysis-asset-connection-v1 S1/rev2, raw 438fd973660016ee1ab1c4150ee6c914792bbf3ce3f3f77f88cd49ebfe09e986, commit 2907391b55989579935134403f2d12010f73514e. Inherit its source-table E/SC/GI/PR/T note IDs and raw hashes. Read scope: E evidence/human review; SC access scope; GI all cautions; PR preparation/version; T mandatory fields. E/SC/GI version 2026-09-15, PR v1, T 2026-10-08. Read ^asset-types/hash/binding/measures; note sections only, no original literature read.
