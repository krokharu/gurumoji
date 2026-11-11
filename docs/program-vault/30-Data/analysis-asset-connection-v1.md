---
note_id: data-analysis-asset-connection-v1
note_type: data-contract
title: 分析資産の最小接続契約 v1（提案）
summary: 固定参照・候補content・停止を既存保存へ結ぶG2案。
status: proposed
schema_version: 1
review_state: draft
runtime_state: planned
source_commit: e6b2e7e75eb2a8d5ea018e2656d3007e4c881aca
proposal_revision: 3
updated: 2026-10-08
tags: [gurumoji/program, gurumoji/analysis]
---

# 分析資産の最小接続契約 v1（提案）

run_9bb051ea8c4b / [[50-Analysis-Methods/40-Skills/thematic-candidate-evidence|候補手順]]。TA07 S1/C1・7string/統計専用S2/C2/Pack00–06/08未接続、実行変更0。

## 現行の接続先と狭い初期経路

AnalysisStore input/parameters/result/manifest/list/artifacts/read_artifact、orchestration raw/claims/label_versions/audit/export、interaction_links再利用。Handler _validate_result/_commit_labels≠本人TA採否。typed/未読slot/resolver未接続。

初期G4案:1会話→ta-p2/p3→照合→result.json新保存→人待ち/reload。result.orchestration.thematic_candidates_v1をraw/claims/historyと一正本、exportは投影。新DB/scheduler0、現行raw追加不可。07変更は別版/parser/旧版回帰票、source/SQL変更0。

## 型の表記と固定参照

> R必須/O省略可/C条件付き（他禁止）。追加キー不可,欠落/null/[]別。I非空string,H /^sha256:[0-9a-f]{64}$/,N厳密int>=1,Z厳密int>=0（bool不可）,T UTC RFC3339。ID重複/未知enum拒否。hash規則は下記。
>
> | 型／field | 要否・type・規則 |
> | --- | --- |
> | SourceRef | R target_type enum(snapshot,utterance,raw_text,media,researcher_memo,definition,artifact),target_id:I,version:I,content_hash:H,hash_domain:HashDomain。C library_id:I（会話由来）,utterance_id:I（utterance）。O locator:I（固定資料位置）,現在版代替不可 |
> | SchemaRef | R schema_id:I,version:N,schema_hash:H |
> | Scope | R scope_id:I,manifest_hash:H,mode enum(dataset,selection,section,episode),input_refs:SourceRef[1..n],conversation_ids:I[1..n],member_ids:I[],context_ids:I[]。主対象/文脈を固定,section/episode能力なしはunsupported |
> | Actor | R kind enum(ai,code,researcher,system),actor_id:I,step_ids:I[]。C model_id/revision/provider:I（aiのみ,他禁止）。自己申告≠実施 |
> | Adapter | R adapter_id:I,version:I。実登録照合,noteコード実行不可 |
> | AssetKey | R library_id:I,store_run_id:I,artifact_id:I,output_name:I。保存run≠実行run,latest不可 |
>
> 原本/媒体/本人メモ/定義=SourceRef,receipt研究kind外。library/版/hash別。
>
> ## 成果物と意味・利用状態
>
> | Asset field | 要否・type |
> | --- | --- |
> | contract_id / contract_version | R literal gurumoji.analysis-asset-connection / literal integer 1 |
> | asset_key / raw_byte_hash / content_hash / content_domain / schema | R AssetKey / H / H / enum(raw-bytes-v1,ta-candidate-content-v1,ta-theme-content-v1) / SchemaRef |
> | kind | R enum(observation_table,claim_set,relation_graph,event_sequence,embedding_matrix) |
> | source_refs / scope | R SourceRef[1..n] / Scope |
> | method_id / method_version / producer | R I / I / Actor |
> | adapter | R Adapter またはnull（研究者手作業のみ）。未登録はunsupported |
> | execution_run_id / producer_task_id | C I（別実行台帳あり時,他は禁止） |
> | meaning / variables / parent_refs | R Meaning / Variable[] / SourceRef[]（派生時1以上） |
> | supersedes | O SourceRef[1..n]。新asset,旧版保持 |
>
> Meaning全R:definition_refs:SourceRef[],description:I/null,status enum(declared,unknown),unit enum(utterance,conversation_speaker,participant,conversation,episode,dataset_claim,event,vector_row,report_claim)。unknown=null/hold,theme=dataset_claim。
>
> Variable全R:variable_id:I,version:N,definition_hash:H,value_type enum(string,number,integer,boolean),scale enum(nominal,ordinal,interval,ratio),unit:I,value_domain:I,generation:Actor,validity enum(candidate,structural_checked,human_reviewed,unknown),definition_ref:SourceRef。表列Variable必須,observed_types≠意味/尺度,AI未評価は確認利用不可。
>
> | kind | schemaの条件／境界 |
> | --- | --- |
> | observation_table | unit/版/定義/欠測/分母/階層,名義ID≠測定 |
> | claim_set | ID/版/区分/支持/反例/採否/限界,初期TA |
> | relation_graph | 両端/方向/種別/根拠,類似≠応答/同意 |
> | event_sequence | 会話/順序/valid_time/観察/欠区間,会話間連結不可 |
> | embedding_matrix | 元行/次元/encoder版/入力種別/空間ID,TA unsupported |
>
> AssetState（内容外）全R: asset_key:AssetKey,target_content_hash:H,target_domain:Asset.content_domain,state_revision:N,policy_revision:N,status enum(draft,candidate,adopted,rejected,retired,stale,unavailable),allowed_purposes enum[](exploratory,descriptive,qualitative_compare,confirmatory),send_policy enum(local_only,permitted_destinations,prohibited),destinations:I[],revoked:boolean,review_refs:SourceRef[],reason:I,updated_at:T。adopted=必要actorのtarget/用途/scope採否（人stepは本人）。用途不明hold,新草案≠失効。多親用途/scope/送信先intersection,禁止/local_only維持,空blocked,権限拡大不可。

^asset-types

## hash domainとcanonical化（FIX01）

> schema1草案訂正。C(x):canonicalization_id=gurumoji-python-json/version=1（analysis_store.canonical/analysis_core.canonical）:
> ```python
> json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
> ```
> 型:null/bool/int/有限binary64 float/string/list/string-key object。重複/非string key,孤立surrogate,NaN/Inf拒否。Unicode正規化なし,Python Unicode key順/配列順維持。CPython3.13 json数値,1≠1.0,0.0≠-0.0。依存追加0。
>
> HashDomain enum=raw-bytes-v1/canonical-json-v1/utf8-text-v1/ta-candidate-content-v1/ta-theme-content-v1/human-record-v1。未知/未宣言hold。raw_byte_hashは実byte SHA256（decode/canonical化禁止）,utf8-textは原文そのままUTF8 SHA256,canonical-jsonはSHA256(C(不変本体))。旧source_hash推測変換不可。
>
> HC(d,x)=SHA256(C({"domain":d,"content":x})),xは固定content。AssetStateは同keyでtarget_domain=Asset.content_domain/target_content_hash=Asset.content_hash。rawはcontent_hash=raw_byte_hash,TAはHC。metadataでwrapper raw変更/本文HC不変,wrapper hash欄なし、追記は新保存版/旧wrapper保持。
>
> Scope.manifest_hash=SHA256(C({scope_id,mode,input_refs,conversation_ids,member_ids,context_ids}))。schema_hash=SHA256(C(固定schema定義本体/SchemaRef欄なし)),definition_hash=definition_ref.content_hash/同domain,selection_hash=SHA256(C(selector,自己欄除外))。入力/定義/scope/code/根拠/意味変更→新content版/hash,旧採否流用不可。state/レビュー/history/receiptはHC外,旧版保持,自己参照/内容DAG/改訂循環拒否。
>
> C全hex/hash,LFなし。
> | ID | hex / hash |
> | --- | --- |
> | H01 {"語":"テーマ"} | 7b22e8aa9e223a22e38386e383bce3839e227d / 6021cb228be0d308a9ae5e8c70d488cacb659f9f3fb2eea29e611b9c6cfe3980 |
> | H02 {"z":1e-06,"β":-0.0,"あ":1.5} | 7b227a223a31652d30362c22ceb2223a2d302e302c22e38182223a312e357d / 74fae2c175b9e8a74f5463062627f6237f8e881199f58eef0e8ff1d1f735210e |
>
> H03 ensure_ascii=True≠H01,H04 NFC/NFD・1/1.0・±0.0区別。M01 record/status/history/receipt追記→HC不変/raw変更。M02内容変更→HC変更/旧target拒否。M03未知domain/self/cycle/旧版置換拒否。メモリ内のみ,本人採否/runtime/44fixture未実行。

^asset-hash

## slot・未解決参照・解決済みbinding

> Slot全R: slot_id:I,required:boolean,min_items:Z,max_items:N,roles:Role[1..4],accept_kinds:Kind[],accept_schemas:SchemaRef[],accept_units:I[],scope_modes:I[],actors:I[],adapter:Adapter,purposes:I[],max_bytes:N。Role enum=data_input/selection_basis/evidence_context/parameter_source,Kind=5種。原本slotはaccept_kinds=[],C accept_source_types:SourceRef.target_type[1..n]（原本のみ,他禁止）。accept_unitsはMeaning.unit,scope_modesはScope.mode,actorsはActor.kind,purposesはAssetState用途のenum集合。max>=min,requiredならmin>=1。全能力/用途照合,ID一致だけ不可。
>
> | InputRef field | 要否・type |
> | --- | --- |
> | plan_id / plan_version / plan_hash / generation | R I / N / H / N |
> | consumer_task_id / slot_id / input_ref_id / role | R I / I / I / Role。別行選択は別ref |
> | selection / omission_reason | R enum(selected,omitted) / Iまたはnull。omitted時理由必須,required slotは省略不可 |
> | source | C selected時 tagged union。from_step:{type literal from_step,producer_task_id:I,output_name:I} ,frozen:{type literal frozen,asset_key:AssetKey,content_hash:H,content_domain:Asset.content_domain},original:{type literal original,source_ref:SourceRef}。omitted時存在禁止 |
> | selector | C selected時 {row_ids:I[],column_ids:I[],range_ref:SourceRefまたはnull,selection_hash:H}。全件もmanifest固定 |
>
> selectedは全role/optionalで依存。from_stepは能力/DAG確認・親採用/保存までunresolved,frozenは同resolver/親待機なし。slot/min/max固定。親失敗blocked,省略変更は新plan/task。
>
> Binding全R fields: source_type enum(artifact,original),binding_id:I,input_ref_id:I,source:AssetKey,content_hash:H,content_domain:HashDomain,selection_hash:H,schema:SchemaRef,checked_state_revision:N,checked_policy_revision:N,checked_at:T,decision enum(eligible,needs_input,human_pending,unsupported,rejected),reason:I。source_type=originalはsource:SourceRef,schemaは原本形式。InputRef照合,unknown/hash/actor不一致/新版置換eligible不可。
>
> 発注/採用前hash/state/policy/全親許可intersection/世代/取消/期限/予算/能力版照合,相違hold/stale。file/DB transaction不可,既存lock/commit guard/保存回復。
>
> 通知キー:(event_id,hook_id,hook_version,plan_id,plan_version,plan_hash,consumer_task_id,slot_id,input_ref_id),hook/plan版N,他I。binding前宛先,同キー再送はreceiptのみ,逆順/旧世代拒否,未受領先だけ再送。欠落は永続親再照合/子発注一度。過去run旧通知不要。callback未実装。
>
> producer/consumer/配送/投影/planは別state,投影失敗≠producer失敗,再公開推論0。未実行統合blocked/成功枝plan partial。子孫だけstale。A1→B1→A2は新task/版/予算,A2→A1拒否。旧run read互換,意味欠落hold,補完は新metadata版。

^asset-binding

## テーマ候補の補助schema

[[50-Analysis-Methods/40-Skills/thematic-candidate-evidence#^tce-output|候補出力]]正本,7string自動確定不可。

^ta-metadata

## 数値化に渡す入力仕様（QA-04／06）

> 採用ラベル/定義済指標→登録projection(行/列)→aggregate(unit/分母/欠測)→join(キー/多重度/件数)の別step案,未実装/任意式禁止。記述/クロス/探索相関は07/08/正式adapter照合,all_included_initialは新表不可。
>
> 表R:qualified_unit_id:I,conversation_id:I,input_version:I,input_hash:H,source_utterance_ids:I[],variable_id:I,definition_ref:SourceRef,adoption_record_ref:SourceRef,value（Variable.value_typeまたはnull）,value_status enum(observed,missing,excluded,unprocessed,unknown),denominator_ref:SourceRef,participant_refs:SourceRef[],episode_refs:SourceRef[]。率の分子/分母/規則版,尺度/出所/群/対応/探索/確認/比較族固定。
>
> 発話/独立人数/会話/名簿のみ/unknown別計数。反復参加/共同発話0..n/episode重複を独立行に増殖不可。司会は除外でも文脈保持,無発言/未観察≠賛否/0。観測0/欠測null/空集合別。valid_time=falseはstart/end/duration=null,placeholder/0秒計算/verification不可,順序のみ。一部欠測は有効小計＋timed/missing数。未対応入れ子/共同発話配分/比較は当consumerだけblocked。

^asset-measures

## G3の期待設計一覧

未実行、G3で正常/異常対・入力/hash固定。
| case ID | 期待状態 |
| --- | --- |
| REUSE-01・02・05・12 | frozen共有、wrongunit/旧domain hold、未採用/共通親≠独立証拠 |
| REUSE-03・04 | 元行/join多重度/分母、全件≠抜粋、null≠0 |
| REUSE-06・07・08 | 両結果対照/不一致/原文role、新A2 |
| REUSE-09・10・11 | 親blocked/再送冪等/子孫stale |
| CONN-01・02・03 | 5kind/adapter/新method（初期外）、from_step/frozen照合 |
| CONN-04・05・06 | 変換/別空間拒否、claim+relation+原文、共通guard/取消/回復/旧run |
| ASSET-01・02・03・04 | 別run選択/hash≠state/optional待機/slot通知 |
| ASSET-05・06・07・08 | 採用前取消/別state/子孫影響/intersection |
| QA-01・02・03 | セル/step照合、意味undetermined、actor偽装拒否 |
| QA-04・05・06・07 | unit/分母/theme履歴/採用表、技術/モデル/人の別評価 |
| GI-01〜11 | 手順票の対入力/不足/反例 |

## 出典固定と保留

raw=91697d8固定byte、P=当時C0追記後G2/QA04–06、B=案。trace合成mock/再実行0。

| 出典ID / note_id | 版・確認範囲 | raw SHA-256 |
| --- | --- | --- |
| P / plan-obsidian-skill-knowledge-work | r5 §13/QA04–06 | 821f86ef155c48f876cc4a04ac7b0059ca24abfaa5f0dd7895d62456a2867693 |
| B / design-obsidian-skill-knowledge-blueprint | 2026-10-08 §15–18 | 40380edce6f39105c83e07d97a0a8b05a15557ffcb29ef2f21dfe3d196eba7b5 |
| ST / program-analysis-storage-v1 | v1 保存/履歴 | 31b48be809af0922124aea608b12aec7e8f935b513ca61743fecd5d9e06bc885 |
| PR / transcript-preparation-v1 | v1 準備/版 | d28d51f6c1232c0577d8d368da7396535f7ac161b756ca3cd43a0ab833e9d2cb |
| R / analysis-expert-stage-readiness | S1 不足/人待ち | 7c9bc4bbbc11011d936d4572da9fdbf579787cc4d0dbdd914564c045a58ccbd7 |
| TA08 / expert-thematic-analysis-skill-hook-binding | B1 表/slot/hook | a63674d30bfafeeffbebcfe92a36caadf57d727daf68e5ebb1a00c36ecd345e4 |
| COR08 / expert-correlation-skill-hook-binding | B2 単位/計算 | 3115a75cff595496990e739f531c64ba3ac5f1f75aff35eed06770944dbaf9e6 |
| GRP08 / expert-group-comparison-statistics-skill-hook-binding | B2 単位/計算 | b92757b66b85ebf640ce6bf5869c80c3fc2a95525c70d8b8d1fae24e18fe98c4 |
| T / template-skill-definition | 2026-10-08 書式 | 85f171179e3bae2cca3950153e2cd7617539dfbefff68ed6f72ad1eda4b9398f |
| E / analysis-common-evidence-and-claims | 2026-09-15 根拠 | 4bc68200e3461d3bd406d907fde972fec2b6be13969b86026b6b50a200247a14 |
| SC / analysis-common-source-classification | 2026-09-15 出典 | 3b88a99e9b5d3965f8e4f0c1c5c0445c993cc893dd2656fc7a1f3d8a787e7564 |
| GI / analysis-common-group-interview-data | 2026-09-15 unit | 2e373a185b9a11729b5b3411cfa555dd8aa41fc5dec075c61818795d8450b95a |

source_commitの保存/採用/receipt節:analysis_store.py/analysis_orchestration.py/services/{analysis_orchestration_{publication,methods,adapters},analysis_annotations,expert_agents,expert_data_hooks}.py。path+NUL+hex+LF順source8: 2dc1f60b6809a7e275d57580f2d844ec4b51a2423524c106d75231a34d1b1bb3（個票Orca）。F04 README raw: a62c3d477ebefea3d1838a20d18c6ee5b201b7eb1db93c2a6db9340715db5d96。新trace execution-20261008T000330Z-d02107/trace-result.json raw: f4ca825553af4805402228e3e6db421cc62d0beaf683b2606ab109da3f6a67e9（時刻/未読/population/conditions）。

F04 e6b2e7e:msg_b1d33bd65fa4→T02 msg_bf4d69901e35/msg_424f2f2cad1a/Dot0908 partial、unacceptedは履歴。u06 UNKNOWN/u07未配信/名簿C/11残件/typed・本人record不足/モデル未測定。

C0独立review→G3/G4。問い/流派/解釈/採否/権限は人、G2〜G4/接続/通知/reader/モデル/Web/VIZ未完。

canonical追加:analysis-core-canonical / analysis_core.py:128–136、19c3198 raw 8ed4784243980acaaba0530227583a48c0d8281666efa00bdcc0aafc550563c2。analysis_store.py:38–39はsource8内。R01/R02独立再review待ち。
