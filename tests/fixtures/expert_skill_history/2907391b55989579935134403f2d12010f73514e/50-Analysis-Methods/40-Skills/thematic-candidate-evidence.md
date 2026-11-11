---
note_id: skill-thematic-candidate-evidence
note_type: executable-skill
title: テーマ候補と固定根拠の整理手順（提案）
summary: ta-p2/p3の根拠・履歴・未読と人待ちを固定する。
status: proposed
schema_version: 1
skill_id: thematic-candidate-evidence
skill_version: 1
proposal_revision: 2
expert_ids: [exp-thematic-analysis]
stage: candidate_generation
review_state: draft
runtime_state: planned
required_note_ids: [data-analysis-asset-connection-v1, expert-thematic-analysis-definition, expert-thematic-analysis-procedure, expert-thematic-analysis-quality, expert-thematic-analysis-agent-contract, expert-thematic-analysis-skill-hook-binding, analysis-common-evidence-and-claims, analysis-common-source-classification, analysis-common-group-interview-data]
optional_note_ids: []
guards_block_id: tce-guards
procedure_block_id: tce-procedure
output_block_id: tce-output
updated: 2026-10-08
tags: [gurumoji/skill, gurumoji/analysis]
---

# テーマ候補と固定根拠の整理手順（提案）

[[90-Templates/skill-definition]]準拠、型:[[30-Data/analysis-asset-connection-v1]]。TA01 D2/07 S1/C1/7string草案、採否notanswered。

## 条件・取得・停止

問い/用途/1会話、頻度≠重要性。AI ta-p2/p3、人ta-p1/p4–6代行不可。

必須:01入力/actor/禁止、02「手順と各段階の確認事項」全表/前提、03人判断、07、08 ^ta-stages/^ta-slots/^ta-hooks、共通3知識/本票3block/型票各block。whole-stage-table-block=全行/actor/必須/停止＋直後ID。02現行heading、版1/hash固定。

部分reader未接続/Pack00–06。上限3資料×2巡/8,000文字、全表不可は停止。現行read_evidence=3要求×2巡/12,000文字≠全読了。

停止:unknown/nonallowed/actor/hash不一致→rejected、参照/未配信/期限/予算不足→needs_input、section/embedding/任意表非対応→unsupported、ta-p1/p4–6未回答/意味未判定→draft/human_pending停止。callback未登録blocked。能力=Handler→C0/G4、方法/命名/採否=人。再開は版/世代/予算/期限/用途再照合、変更は新plan、再通知≠生成。

^tce-guards

## 研究質問別の代表手順

| 段階 | 必須条件・actor | 入力→出力／本人判断 |
| --- | --- | --- |
| 準備 | 全枝、R ta-p1 | 問い/流派・snapshot→全体精読。未回答は採否保留 |
| 候補 | 意味パターンを問う枝、AI ta-p2/p3＋R | 許可原文→code/theme/支持/反例/代替/未読。構造code案/意味は人 |
| manual interaction | 応答/対立/変化を問う枝、R | interaction_links/メモ→両端/順序/文脈、媒体なしunknown |
| comparison | 差/数量を問う枝、R＋登録code | claim+関係+原文。採用表/QA-04/06別task、不適合hold |
| 反例 | 主張/報告の枝、R ta-p4 | 撤回/反例→split/merge/reject理由、AI補助は新ta-p2/p3 |
| 報告 | 確定報告、R ta-p5/p6 | 定義/命名/根拠/履歴/限界/採否→本人、未回答停止 |

^tce-procedure

相互作用=exp-focus-group-interaction人手順、数値=[[50-Analysis-Methods/10-Experts/correlation/08-Skill-Hook-Binding]]・[[50-Analysis-Methods/10-Experts/correlation/07-Agent-Contract]]、[[50-Analysis-Methods/10-Experts/group-comparison-statistics/08-Skill-Hook-Binding]]・[[50-Analysis-Methods/10-Experts/group-comparison-statistics/07-Agent-Contract]]。新3phase/人格0、数値省略可。

## 出力：候補補助schema

HC/domain: [[30-Data/analysis-asset-connection-v1#^asset-hash]]。閉鎖object,全R/C外禁止。Envelope:schema_id literal gurumoji.thematic-candidate,schema_version literal 1,content:CandidateContent,content_hash:H,themes:ThemeSnapshot[],coverage:Coverage,human_status literal human_pending,human_record_state enum(not_entered,entered,changed),human_records:HumanRecord[],history:Change[]。content_hash=HC(ta-candidate-content-v1,content)。payload_hash禁止,wrapper=Asset.raw_byte_hash。

CandidateContent全R: candidate_set_id:I,version:N,input_refs:SourceRef[1..n],scope:Scope,producer:Actor,theme_refs:ThemeTarget[]。ThemeSnapshot全R: content:ThemeContent,content_hash:H,status enum(draft,merged,split,rejected,superseded),meaning_review enum(undetermined,human_pending),search_state:{support/counterexamples/alternatives:enum(not_searched,partial,recorded)},memo_refs:SourceRef[],receipt_bindings:{evidence_ref:EvidenceRef,read_receipt_ids:I[],delivery_receipt_ids:I[]}[]。content_hash=HC(ta-theme-content-v1,content),theme_refs/themes同順1:1。state/検索/memo/receipt/review/history外。

| ThemeContent全Rprojection | type |
| --- | --- |
| candidate_set_id / theme_id / version / claim_id | I / I / N / I |
| input_refs / scope / producer | SourceRef[1..n] / Scope / Actor（CandidateContentと一致） |
| name / definition | Iまたはnull / Iまたはnull。draft未定義/本人命名未回答は確定不可 |
| code_refs | {code_id:I,version:N,definition_hash:H,source_ref:SourceRef}[] |
| support / counterexamples | EvidenceRef[] / EvidenceRef[]（空≠不存在） |
| alternatives | {alternative_id:I,description:I,evidence_refs:EvidenceRef[],reason:I}[] |

EvidenceRef全R: library_id:I,snapshot_ref:SourceRef,input_version:I,input_hash:H,utterance_id:I,utterance_hash:H,context_ids:I[],relation enum(support,counterexample,alternative)。C episode_ref:SourceRef（episode選択時のみ,他は禁止）。utterance_hash=utf8-text-v1,input_hash=snapshot_ref.content_hash/同domain。ID/版/hash/context/scope照合,receipt外。構造validator候補/意味は人,未読≠反証。

Target閉鎖union。CandidateTarget全R: domain literal ta-candidate-content-v1,candidate_set_id:I,version:N,content_hash:H。ThemeTarget=CandidateTarget＋theme_id:I/domain literal ta-theme-content-v1（全R）。HC/ID/版/input/scope不一致拒否,未知domain/旧版欠落hold。候補→theme_refs,Themeに候補hash禁止。

HumanRecord全R: record_id:I,revision:N,supersedes_record_ref:RecordRefまたはnull,actor:{kind literal researcher,actor_id:I},decision enum(adopt,reject,defer),target:Target,allowed_step_ids:I[1..n],scope:Scope,recorded_at:T,reason:I,record_ref:SourceRef。record_ref=本人原記録,自己wrapper禁止。RecordRef全R: domain literal human-record-v1,record_id:I,revision:N,content_hash:H=HC(human-record-v1,旧HumanRecord全fields)。revision1=null,以後同IDのrevision-1参照必須。訂正は旧record/target保持＋新revision。旧target_hash禁止。本人/権限/step/scope照合,AI/7string parse不可,p1/p4/p5/p6別record。not_entered=[]/notanswered,entered=本人入力,changed=履歴必須,human_pending。

Change全R: change_id:I,operation enum(create,update,merged,split,rejected,supersedes),from_themes:ThemeTarget[],to_themes:ThemeTarget[],reason:I,actor:Actor,recorded_at:T,affected_code_refs:SourceRef[]。不変ThemeContent参照。createはfrom空/to1以上,update/supersedesはfrom1/to1（同IDの新版）,mergedはfrom2以上/to1,splitはfrom1/to2以上,rejectedはfrom1以上/to空。同target/逆辺/循環拒否,同ID版増加,historyはHC外,未解決hold/旧hash置換不可。

Coverage全R: dataset_ids:I[],required_ids:I[],excluded_ids:I[],read_receipts/delivery_receipts/processing_receipts:Receipt[],human_read_record_refs:SourceRef[],unread_sets:UnreadSets。Receipt全R: receipt_id:I,receipt_type enum(read,delivery,processing),task_id:I,actor:Actor,input_hash:H,ids:I[],status enum(recorded,partial,unknown,not_run),payload_ref:SourceRefまたはnull,payload_hash:Hまたはnull。recorded/partial=固定payload/hash,unknown/not_run=null。payload_hash=参照実byte SHA256,payload_ref.hash_domain=raw-bytes-v1。read=tool返却/delivery=実配信context/processing=実処理入力bytes,現receiptを含むwrapper禁止。再serialize推測不可,list/type一致,配信/処理≠精読。

UnreadSets全Rはretrieval/delivery/processing/human:{status enum(measured,unknown,not_run),ids:I[]またはnull}。unknown/not_run=null,measuredはdatasetとの差集合。required/excluded別,input/scope照合,count代替不可。receipt追記≠採否。

^tce-output

## G3正常・不足・反例

未実行G2-TA-01=合成1会話/全ID/ta-p2/p3/7string+候補→保存/reload/human_pending。02=hash/actor偽装rejected（G1B-TA-02/05）。03=未配信/反例未探索/本人未回答needs_input/human_pending（G1B-TA-04/06）。04=split/merge旧履歴・子孫stale（QA-05）。05=wrongunit/section/embedding unsupported（G1B-TA-03）。06=optional待機/再送発注0/採用前取消hold（ASSET-03〜05）。本人record捏造禁止。

| GI case ID | 対入力/期待 |
| --- | --- |
| GI-01・02・03 | 準備hold/名簿≠話者/司会文脈 |
| GI-04・05 | 反論/撤回再取得、媒体unknown/時刻順序/抜粋≠全読了 |
| GI-06・07 | 再利用/別kind、同名異義/同label対応未確認→未比較 |
| GI-08・09 | 本人memo/旧解釈、共同発話/episode重複/入れ子/欠測/0/分母、未対応推論blocked |
| GI-10・11 | 用途/未読/失敗/誤数値/因果/step/無根拠、技術/意味/人別評価 |

REUSE01–12/CONN01–06/QA01–07/ASSET01–08は共通票。

## 出典・確認範囲

| 出典note_id | 版・確認範囲 | raw SHA-256 |
| --- | --- | --- |
| expert-thematic-analysis-definition | D2 入力/actor/procedure | 26dfcdfe87323ed33fe232c8c36489f24453adb58c2b2feaa48083996147ecdc |
| expert-thematic-analysis-agent-contract | S1/C1 7string | 453adefd17b23e289352affafc4ae85d61afa1a6f094a34e774c806772050a65 |
| expert-thematic-analysis-procedure | 2026-09-16 段階表/前提 | 2df79e2b69385ccf8a2dbad744d1a91cb7e02c305b873642a18c81284fab2bc4 |
| expert-thematic-analysis-quality | 2026-09-16 人判断 | 84dd97a7f50d30485975148d8a48270055ddf890d1dd7dc5f7a291e8e57e235e |

他出典=共通契約。文献読了/方法採用0。独立review→G3/G4保存/validator、意味/精読/命名は人、G2〜G4/モデル未完。
