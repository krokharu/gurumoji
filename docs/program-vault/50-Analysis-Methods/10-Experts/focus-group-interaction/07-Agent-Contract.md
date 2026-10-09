---
note_id: expert-focus-group-interaction-agent-contract
note_type: expert-agent-contract
expert_id: exp-focus-group-interaction
title: FGIエージェントの候補入出力契約
status: draft
schema_version: 1
contract_version: 2
updated: 2026-10-09
---

# FGIエージェントの候補入出力契約

Issue31のCPU限定S1。01のdefinition_version=1を正本とし、AIはfgi-p3/p5のみ。fgi-p1/p2/p4/p6/p7は研究者の段階であり、AIの自己宣言で完了にしない。方法の妥当性・人の採否・G5方法評価は未評価。

## 既定C1と明示S1

既定currentPackは従来のanalysis_premises（任意）と6string section_01〜06を維持する。既定readerはこの新07を採用しない。以下は既存profile parser用C1互換出力定義であり、S1を自動有効化しない。

```yaml
schema_version: 1
expert_id: exp-focus-group-interaction
contract_version: 1
input_fields:
  - {id: analysis_premises, title: 研究者が指定した分析前提。未指定はnull。, type: string, required: false}
output_fields:
  - {id: section_01, title: 研究質問と分析の方針（内容とは別に扱う）, type: string, required: true}
  - {id: section_02, title: 話者・順序・司会者の確認状況, type: string, required: true}
  - {id: section_03, title: 相互作用の所見（発話の連鎖と発話ID）, type: string, required: true}
  - {id: section_04, title: 不同意・少数意見・意見の変化, type: string, required: true}
  - {id: section_05, title: 司会者とグループ構成の影響, type: string, required: true}
  - {id: section_06, title: 限界, type: string, required: true}
```

expert_inputs[exp-focus-group-interaction].typed_contract=focus_group_interaction_candidates_v1を明示したrunのみ契約版2。既存skill_context readerで01〜04、07/08、共通資料の登録済み実bytes・必要sectionを固定する。文字列から関係・採否を抽出しない。

```yaml focus_group_interaction_candidates_v1
version: focus_group_interaction_candidates_v1
contract_version: 2
schema_version: 1
```

## 固定入力と実配送

同じlibrary DBを使う既存Handler/AnalysisStoreがauthority。thematic_source_packetの既存source_ref/scope/evidence形を再利用し、実library_id、conversation_id、initial_idを使う。source_ref.versionはinput_hash、content_hashはfingerprint(snapshot)で別domain。scopeはdataset・1会話・全member/context・manifest_hashを固定し、発話hashはSHA256(UTF-8原文)。時刻0を順序の根拠にせず、snapshot配列順を使う。

fgi-a1（準備記録の話者/順序確認）とfgi-a2（参加者2人以上）を既存analysis applicabilityで検査する。S1ではorder_verifiedは真のboolean true、unknown_speaker_turnsはinteger 0、participant_countはinteger 2以上を要求し、真偽値/文字列の型偽装を通さない。modelのconfirmationやmanual interaction_linksで代替しない。

Handlerは実contextをboundsと既存hookの初期抜粋処理後に照合し、delivery_coverageをtaskへ固定する。indexに存在すること、取得したこと、本人精読は配送と別。scope選択はdataset全体のみ。全発話本文の配送が不足すればneeds_input（typed=null）、確認不足は既存expert_not_applicable。除外発話は肯定根拠にならず、既存Handlerが除外context本文を配送しない場合も完全性はfalseとなる。S1では後続hookの取得だけで初期配送証拠を全量へ昇格しない。

## 閉じたreport

expert_report.focus_group_interaction_candidates_v1は必須nullable。draftだけobject、他statusはnull。objectのキーはversion、source_ref、scope、producer、coverage、human_status、human_record_state、human_records、semantic_review、eligible_as_confirmed_evidence、candidatesのみ。producerは実taskのkind=ai、actor_id=task_id、model_id、provider、revision=unverified、step_ids。step_idsはreport.performed_step_idsと完全一致し、fgi-p3/p5だけ。

human_status=human_pending、human_record_state=not_entered、human_records=[]、semantic_review=undetermined、eligible_as_confirmed_evidence=falseを固定する。任意annotation、HumanRecord、既存manual linkの採用・置換は非対応。

coverageはsource_utterance_count、included_utterance_count、excluded_utterance_count、delivered_evidence_ids、undelivered_utterance_ids、complete、statementのみ。Handlerのdelivery_coverageと完全一致し、draftは全本文配送済み・欠落空・complete=trueのみ。statementは配送状況と解釈/人精読が未検証であることを明示する。

candidatesは0〜80件、candidate_idは集合内一意。各件はcandidate_id、step_id、relation_kind、text、limitations、evidence_refsのみ。textとlimitationsは空白以外を含む1〜2000文字。relation_kindはquestion_answer、agreement_candidate、disagreement_candidate、addition_candidate、reformulation_candidate、minority_candidate、opinion_change_candidateの閉鎖列挙。fgi-p3はquestion_answerからreformulation_candidateまで、fgi-p5はdisagreement_candidate/minority_candidate/opinion_change_candidateだけを扱う。音声・沈黙・相づち・非言語の解釈種別はない。

evidence_refsは2〜16件の異なる{evidence_id, utterance_id, utterance_hash}をsnapshot順に指定する。実配送ID・report.evidence_ids・原文ID/hashの完全対応を照合し、単発・重複・逆順・未知・未配送・除外は拒否する。source/version/hash/scope/actor/steps/型/余分キーも拒否する。

空candidatesは全量配送・AI許可step実施のdraft証拠と明示limitationsがあるexamined-noneだけ。反例なし・人確認済み・方法成功を意味しない。draftを含む本契約のclaims/label_patches/analysis_requestsは空。自由文は未検証AI下書きのまま。既知の「沈黙は同意」「AI候補は人確認済み」等の肯定断定は限定deny-listで隔離するが、一般の意味・妥当性を自動検証できたとはしない。

## 保存と受入境界

既存Handlerのraw result保存と既存publication→AnalysisStoreのorchestration.raw_resultsを使う。原JSON object/hashを保持し、fresh readで一致を検査する。新asset adapter・保存先・scheduler・UI・自動manual linkはない。

合成4発話/2参加者、stub agentのHandler start/execute→Store→fresh readとmanual interaction_links不変を作者CPU試験とする。作者PASSはC0受入・Orca独立Windows QAの代替ではない。実DB/Vault/媒体/AI送信・モデル品質は未実行。PNG延期、Gemma323 HOLD、G0.5b/c未測定、G5方法と残るexpert未評価を維持する。
