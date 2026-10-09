---
note_id: analysis-g3-connection-fixtures
note_type: evaluation-fixtures
title: G3 共通接続・TA合成desk-trace（提案）
summary: 固定DOC9の50 root＋12方法alias＋5workflow対応、有限参照検証/runtime0。
status: proposed
schema_version: 1
proposal_revision: 3
review_state: draft
runtime_state: planned
fixture_only: true
source_commit: 36ac20d4c7dd1517a55a440e9afbb523507200dc
author_baseline: 36ac20d4c7dd1517a55a440e9afbb523507200dc
updated: 2026-10-08
tags: [gurumoji/program, gurumoji/analysis]
---

# G3 共通接続・TA合成desk-trace（提案）

run_9bb051ea8c4b。原50期待/TEST本文・actor架空、実人未回答/human_pending。TA07 S1/C1/7string維持。COR/GRP/workflow参照trace、runtime/G4/人採否未完、schema/parser/adapter/reader未接続。

## 固定出典とnorm記号

G/T/P/B旧記号維持、C=COR/R=GRP/W=workflow/N=入口/T8,C8,R8=08。Git36ac、common17c3bcf/未変更7票8d356289、C8/R8 B6。9norm canonical path→rawSHA=95f6115fbbea3fbe56d4e340c3882515ba0ac11b08f368666cfd77703b7d800a。G=30-Data、他=50-Analysis-Methods。schema1/draft/planned、採用なし。

|norm|note_id・確認版/範囲|raw SHA-256|
|---|---|---|
|G|data-analysis-asset-connection-v1 s1/r3/15948B; t28-67,h73-91,b97-115,m127-131 Q|00c42234f95ab433542432cddaf61b29191e0b9f00ae645127d882230bd5e9a5|
|T|skill-thematic-candidate-evidence s1/skill1/r3/9995B; g30-36Q,p42-49T6,o53-80Q|8f7860af502ba9dd6e33da259309284bd53f2fa64c9d91a5d0754c66c82b5527|
|C|skill-correlation-exploratory-evidence s1/skill1/r3/9339B; g30-36Q,p42-51T8,o57-63Q|3d29a901c8fc64c7d0822310bb8e97e7137e661431dcd0851e25a766eb7eb2ec|
|R|skill-group-comparison-exploratory-evidence s1/skill1/r3/9959B; g30-44Q,p50-59T8,o65-73Q|eb1475f67af863bd232ef3b0701c7bea71c7405c7ce95b8a0fa854544574729d|
|W|workflow-group-interview-evidence s1/flow1/r3/13928B; purpose24-31T6,p39-46T6,pg50Q,u56-62Q,b68-76Q,c84-94T9|1a8ed0b31076f5ade8ddb30ca953ac00debf022a3b08b20b4544221a096a2a32|
|N|analysis-skills-index draft/planned/5986B; explicit section35-54/no ID|e569ef34c22279c72d80cc5732a48598d42617268207b1aaf39b08470ef00364|
|T8|expert-thematic-analysis-skill-hook-binding s1/B2/16339B; st54-59T4,sl69-76T6,h84-89T4,c99-106T6|e4677c2271ff95ccdbd053119420d20c44ac1049b3c372e30c24b747037816ef|
|C8|expert-correlation-skill-hook-binding s1/B6/19511B; st61-66T4,sl80-87T6,h95-100T4,c110-117T6|4834067229ad482d05316df8d504a6cfdc17e8c652b58318801675e9560ffe66|
|R8|expert-group-comparison-statistics-skill-hook-binding s1/B6/19989B; st61-66T4,sl80-87T6,h95-100T4,c110-117T6|5080fbf445fc4668ca803ffa0cfe4ef5ad00f302786dc3644bb1d9c24f903be4|
|P13|[[40-Design/obsidian-skill-knowledge-work-plan]] / plan-obsidian-skill-knowledge-work / r5 §13 QA01–07|821f86ef155c48f876cc4a04ac7b0059ca24abfaa5f0dd7895d62456a2867693|
|B14–18|[[40-Design/obsidian-skill-knowledge-blueprint]] / design-obsidian-skill-knowledge-blueprint / 2026-10-08 §14–18,原44条件|40380edce6f39105c83e07d97a0a8b05a15557ffcb29ef2f21dfe3d196eba7b5|

source8はGit e6b2e7e歴史的アンカーのみ、並行Bの現source安定性を主張しない。path順(path+NUL+hex+LF)SHA256: 2dc1f60b6809a7e275d57580f2d844ec4b51a2423524c106d75231a34d1b1bb3。

S1=analysis_store.py,S2=analysis_orchestration.py,S3=services/analysis_orchestration_publication.py,S4=services/analysis_annotations.py,S5=services/analysis_orchestration_methods.py,S6=services/expert_agents.py,S7=services/expert_data_hooks.py,S8=services/analysis_orchestration_adapters.py（版e6b2e7e,G source8参照）。

F04 technical partial e6b2e7e/msg_b1d33bd65fa4→T02 msg_bf4d69901e35/msg_424f2f2cad1a履歴はr2(6b09941)のartifact参照へ戻る。u07 index-only未読、原文複製/再実行0、モデル/本人record/11残件未解消。

^g3-sources

## 一つの合成fixture manifest

F=JSON,u07 index-only/text=null/hashなし,false時刻数値禁止。speaker会話local,参加者TEST対応/UNKNOWN無配分/C silent/u05共同1行/episode union/媒体なし。

```json
{"fixture_only":true,"fixture_id":"TEST-G3-v1","fixture_version":1,"input":{"library_id":"TEST-L1","version":1,"row_fields":["id","conversation_id","text","speaker_ids","participant_ids","start","end","valid_time","value","value_status","role"],"rows":[["u01","TEST-c1","司会:費用の話をしましょう。",["s0"],["M"],0,1,true,null,"excluded","moderator"],["u02","TEST-c1","A:費用が障壁です。",["s1"],["A"],1,3,true,1,"observed","participant"],["u03","TEST-c1","B:私も費用で迷います。",["s2"],["B"],null,null,false,1,"observed","participant"],["u04","TEST-c1","D:費用は障壁ではありません。",["s3"],["D"],3,5,true,0,"observed","participant"],["u05","TEST-c1","AとB:共同調整で解決できそうです。",["s1","s2"],["A","B"],5,5,true,1,"observed","joint"],["u06","TEST-c1","不明:場所の話です。",[],[],null,null,false,0,"observed","unknown"],["u07","TEST-c1",null,[],[],null,null,false,null,"unprocessed","index_only"],["v00","TEST-c2","司会:別会話で費用を確認します。",["s0"],["M"],0,1,true,null,"excluded","moderator"],["v01","TEST-c2","A:ここでも費用が障壁です。",["s9"],["A"],1,4,true,1,"observed","participant"],["v02","TEST-c2","E:費用は障壁ではありません。",["s1"],["E"],4,4,true,0,"observed","participant"],["v03","TEST-c2","E:まだ判断できません。",["s1"],["E"],null,null,false,null,"unknown","participant"]],"rosters":{"TEST-c1":["A","B","D","C"],"TEST-c2":["A","E"]},"speaker_maps":{"TEST-c1":{"s0":"M","s1":"A","s2":"B","s3":"D"},"TEST-c2":{"s0":"M","s9":"A","s1":"E"}}},"coverage":{"dataset_ids":["u01","u02","u03","u04","u05","u06","u07","v00","v01","v02","v03"],"included_ids":["u02","u03","u04","u05","u06","u07","v01","v02","v03"],"required_ids":["u02","u03","u04","u05","u06","u07","v01","v02","v03"],"excluded_ids":["u01","v00"],"retrieved_ids":["u01","u02","u03","u04","u05","u06","v00","v01","v02","v03"],"delivered_ids":["u01","u02","u03","u04","u05","u06","v00","v01","v02","v03"],"processed_ids":["u01","u02","u03","u04","u05","u06","v00","v01","v02"],"human_read_ids":null,"human_read_status":"unknown"},"code_definition":{"code_id":"TEST-code-cost","version":1,"definition":"合成費用コード、1=TEST表で有、0=TEST観測無；人採否なし"},"label_definition":{"variable_id":"TEST-label-cost","version":1,"unit":"utterance","value_type":"integer","scale":"nominal","domain":[0,1],"projection_id":"TEST-projection-v1","aggregate_id":"TEST-count-v1","join_id":"TEST-join-1to1-v1"},"edges":{"A1":["F1","X1"],"F1":["B1"],"X1":["B1"],"Q1":["B1","A2"],"I1":["B1"],"T1":["B1"],"B1":["A2"],"A2":[]},"selected_optional":{"consumer":"B1","parent":"T1","slot_id":"time","input_ref_id":"TEST-time1"},"fixture_human_stub":true,"actual_human_adoption":"notanswered","scopes":{"whole":{"conversation_id":"TEST-c1","member_ids":["u01","u02","u03","u04","u05","u06","u07"],"context_ids":[]},"section_a":{"conversation_id":"TEST-c1","member_ids":["u02","u03"],"context_ids":["u01","u04"]},"section_b":{"conversation_id":"TEST-c1","member_ids":["u03","u04","u05"],"context_ids":["u02","u06"]},"episode_1":{"conversation_id":"TEST-c1","member_ids":["u02","u03"],"context_ids":["u01"]},"episode_2":{"conversation_id":"TEST-c1","member_ids":["u03","u04","u05"],"context_ids":["u02"]}}}
```

集合/配列順固定:dataset11/included=required9/excluded2/read=delivered10/processed9/human unknown,null。unread retrieval/delivery={u07}/processing={u07,v03}/human unknown,null≠空。TA c1:dataset u01–07/required u02–07/excluded u01/read,delivered,processed u01–06/3unread={u07}/human unknown。receipt≠精読。

^g3-manifest

## 不変content・target・payloadの再計算

C=G gurumoji-python-json/v1,H(bytes)='sha256:'+SHA256,HCは下記CPU式。rawbyte decode/canonical化禁止。scope自己hash後挿入,CC/TCにstatus/history/人record/receiptなし。reader/runtime serializer未実装。

```python
import json,hashlib
def C(x):
 return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def H(b): return 'sha256:' + hashlib.sha256(b).hexdigest()
def HC(d, x): return H(C({'domain': d, 'content': x}))
rows={r[0]:dict(zip(F['input']['row_fields'],r)) for r in F['input']['rows']}
snapshot={'target_type':'snapshot','target_id':'TEST-input','version':'1','content_hash':H(C(F['input'])),'hash_domain':'canonical-json-v1','library_id':'TEST-L1'}
producer={'kind':'ai','actor_id':'TEST-AI0','step_ids':['ta-p2','ta-p3'],'model_id':'TEST-NONE','revision':'1','provider':'TEST-no-call'}
scope={'scope_id':'TEST-scope-c1','mode':'dataset','input_refs':[snapshot],'conversation_ids':['TEST-c1'],'member_ids':['u02','u03','u04','u05','u06','u07'],'context_ids':['u01']}
scope['manifest_hash']=H(C(scope))
def eref(uid,rel):
 r=rows[uid]
 return {'library_id':'TEST-L1','snapshot_ref':snapshot,'input_version':'1','input_hash':snapshot['content_hash'],'utterance_id':uid,'utterance_hash':H(r['text'].encode('utf-8')),'context_ids':['u01'],'relation':rel}
coderef={'target_type':'definition','target_id':'TEST-code-cost','version':'1','content_hash':H(C(F['code_definition'])),'hash_domain':'canonical-json-v1'}
TC={'candidate_set_id':'TEST-cs1','theme_id':'TEST-theme1','version':1,'claim_id':'TEST-claim1','input_refs':[snapshot],'scope':scope,'producer':producer,'name':'費用と共同調整','definition':'合成候補、意味妥当性未判定','code_refs':[{'code_id':'TEST-code-cost','version':1,'definition_hash':coderef['content_hash'],'source_ref':coderef}],'support':[eref('u02','support'),eref('u03','support')],'counterexamples':[eref('u04','counterexample')],'alternatives':[{'alternative_id':'TEST-alt1','description':'共同調整という別説明','evidence_refs':[eref('u05','alternative')],'reason':'費用だけで説明しないTEST対照'}]}
TT={'domain':'ta-theme-content-v1','candidate_set_id':'TEST-cs1','theme_id':'TEST-theme1','version':1,'content_hash':HC('ta-theme-content-v1',TC)}
CC={'candidate_set_id':'TEST-cs1','version':1,'input_refs':[snapshot],'scope':scope,'producer':producer,'theme_refs':[TT]}
CT={'domain':'ta-candidate-content-v1','candidate_set_id':'TEST-cs1','version':1,'content_hash':HC('ta-candidate-content-v1',CC)}
```

CT/TT=Candidate/Theme Target。AssetState同key domain/hash同値。metadata新wrapper/旧bytes保持,HC不変。code/input/scope/definition/support新版/hash→旧target hold。Change固定snapshot,history HC外,self/逆辺拒否/未知domain hold/旧hash新版置換禁止。

TEST HumanRecord:record_id=TEST-HR-p4/revision1/supersedes_record_ref=null/actor={kind:researcher,actor_id:TEST-R0}/decision=defer/target=CT/allowed_step_ids=[ta-p4]/scope上記/recorded_at=2026-10-08T01:30:00Z/reason=TEST schema probe only。record_refはresearcher_memo/TEST-memo1/version"1"/utf8-text-v1/H(UTF8("TEST no actual adoption"))/library TEST-L1。revision2は同ID/rev1/HC(旧record)のRecordRef、旧target保持。p1/p5/p6各別ID TEST-HR-p1/TEST-HR-p5/TEST-HR-p6、各revision/supersedes鎖。旧4step一括は負例rejected。実human_records=[]/未回答、TEST switch≠実採用。

U=c1 u01–u06のrow配列。payload read=C(U),delivery=C({task_id:TEST-A1,ids:[u01..u06],rows:U}),processing=C({task_id:TEST-A1,input_rows:U,step_ids:[ta-p2,ta-p3]})。payload_ref=artifact/TEST-payload-{type}/version"1"/raw-bytes-v1/H(payload)。ReceiptはT全field: actor TEST-TOOL0(code)/TEST-D0(system)/TEST-AI0(ai),input_hash=snapshot.hash/status recorded/ids同6/receipt_id TEST-{type}/task_id TEST-A1。合成呼出0,unknown/not_run両payload null,現receipt含wrapper禁止,研究kind外。

|固定値|hash|
|---|---|
|fixture_hash|sha256:e7869b57042596e0c2f0456ee84c5c08f4795f3e3fc24f8adac54f7006aef764|
|input_hash|sha256:264c88b13a7c97c777370f95fe4e21af3ee619003ef094279d6d5ac9c4aaa4b1|
|scope_hash|sha256:dfd9a8e8dd85a4a346cefa9a41bbe71feff9f5bb115af775796c3763b8058745|
|code_hash|sha256:5f7828c8214cd00a2dadae39ad94f311483fdde14832993e9b34cdb3f757c5f3|
|candidate_hash|sha256:282b7b6f4d0f68e85202c168d376c5b1599ea2b859e559e24e99d01932d24b70|
|theme_hash|sha256:d6dcf9d3ebdd3074967966d3643a0c18f736554dcd427baeb8e6151b920135a5|

G H01/H02と同じbyte/hash:
- {"語":"テーマ"} = hex 7b22e8aa9e223a22e38386e383bce3839e227d / SHA256 6021cb228be0d308a9ae5e8c70d488cacb659f9f3fb2eea29e611b9c6cfe3980。
- {"z":1e-06,"β":-0.0,"あ":1.5} = hex 7b227a223a31652d30362c22ceb2223a2d302e302c22e38182223a312e357d / SHA256 74fae2c175b9e8a74f5463062627f6237f8e881199f58eef0e8ff1d1f735210e。

missing:7b7d/44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
null:7b2278223a6e756c6c7d/c6b8df5aba33a39cbdee46ffaf77fae93ea2aa7d99d66408162b05a42105bd71
array12:5b312c325d/49a64717d5d4cb19952e6eac2946415cf6879adacf9908e7d872332d32c6e684
array21:5b322c315d/af1a1fc110b6094c48582b0ef83553cb7908d7a4365424eef28e76ef6c88d630

key順不変,array順/欠落vsnull/NFCvsNFD/1vs1.0/±0.0別hash。ensure_ascii=True不一致,NaN/Inf/非string key/孤立surrogate/decode重複key拒否。CPython3.13有限binary64,依存/JCS追加0。

^g3-domains

## 数値表・分母とQA04/06

label_rows=included順の投影。fields/rowsをdict(zip(fields,row))へ展開しhash,time_tableはobject。TEST-label-cost/v1＋TEST-projection-v1/TEST-count-v1/TEST-join-1to1-v1のみ登録stub,任意AI式不可。実登録/人採用なしは数値consumerだけblocked,候補/独立Q1別state。

```json
{"label_rows":{"fields":["id","conversation_id","value","value_status"],"rows":[["u02","TEST-c1",1,"observed"],["u03","TEST-c1",1,"observed"],["u04","TEST-c1",0,"observed"],["u05","TEST-c1",1,"observed"],["u06","TEST-c1",0,"observed"],["u07","TEST-c1",null,"unprocessed"],["v01","TEST-c2",1,"observed"],["v02","TEST-c2",0,"observed"],["v03","TEST-c2",null,"unknown"]]},"conv_table":{"fields":["conversation_id","included","observed","ones","zero","unknown","unprocessed"],"rows":[["TEST-c1",6,5,3,2,0,1],["TEST-c2",3,2,1,1,1,0]]},"participant_table":{"fields":["participant_id","conversations","exclusive_observed","sum","joint_ids","unknown_ids","roster_only"],"rows":[["A",["TEST-c1","TEST-c2"],2,2,["u05"],[],false],["B",["TEST-c1"],1,1,["u05"],[],false],["D",["TEST-c1"],1,0,[],[],false],["E",["TEST-c2"],1,0,[],["v03"],false],["C",[],0,null,[],[],true]]},"time_table":{"included":9,"timed":5,"missing":4,"duration_sum":7,"zero_duration":2}}
```

|table / bytebody=C(table)|固定H|
|---|---|
|label_table_hash|sha256:0a4741142228d16e39d064e8ce2bff20cea6487b6b9a8deea9d0926b32d5af2a|
|conversation_table_hash|sha256:2f965d7f185b7d9453dffb85562284d4a3b218aa96569e64578444a63b2bb8a3|
|participant_table_hash|sha256:c8b96f2cbaf7079bc89b027a401145493727538425b3c266594f2e149c445c4a|
|time_table_hash|sha256:1d2d1224892980889d6dd7dd8711bd3eadaaa1cab1bc2841126f59ee8d1c393b|

utterance9/observed7/ones4/zero3/unprocessed1/unknown1,分母7/除外2≠0。c1 known A/B/D3/UNKNOWN1/roster4,c2 A/E2,独立既知人4/conv-speaker5/conv2/roster-only1。u05 joint/u06 UNKNOWN無配分,A2会話/E未知/C sum=null,実人数・立場補完不可。episode union4≠5。timed5/missing4/duration小計7秒/実0秒2/mean1.4秒,false start/end/duration=null。推論/確認は別能力・人待ち。

QA01 cell=TEST-NUM1/cost/coef=-0.245,p=.00485,N7,CI/corrected_p=null/input_hash/上表hash/variable_pair=[TEST-label-cost,TEST-ref]。Decimal HALF_EVEN=-0.24/.0048/57.14%。cell描画のみ,正IDの値/符号/N/row/variablepair改変・架空CI拒否。自由文step申告未確認,一般classifierなし。

^g3-measures

## 往復DAGと状態のdesk規則

F.edges=producer→consumer。A1→F1/X1→B1→新A2,Q1/I1/T1非依存。共通input由来≠独立replication。選択optional T1は待機,P2/version2だけomitted+理由で辺削除,P1暗黙省略禁止。from_stepは親採用/保存までunresolved,frozen同能力/policy照合。original=typed SourceRef,slot accept_source_types/role固定,receipt≠研究kind。

Dはdesk記号: A1=L1（2会話TESTラベル表）,key=(TEST-L1,TEST-store-r1,TEST-L1-table,labels),raw body=C(label_rows)/content_hash=raw_byte_hash=表hash/domain R。別CA1はc1 TA候補/key artifact TEST-CA1/content=CT(domain A),A1からc2の採否を推定しない。G/T schema1,adapter TEST-TA/TEST-NUM v1はstub（実登録なし）。CA1 slot=claim_set/dataset_claim/AI p2,p3,F1/X1 slot=observation_table/utterance/code,schema/用途/scope一致のTEST仮定。patch初期F/Dへ単独,H("other")=UTF8 SHA256。

plan={id:TEST-P1,version:1,generation:1,budget:2,deadline:2026-10-08T03:00:00Z}。plan_hash=H(C({edges:F.edges,selected_optional:F.selected_optional,plan:上記})),自己hash欄なし。通知key=(TEST-E1,TEST-hook,hook_version1,TEST-P1,plan_version1,plan_hash,B1,time,TEST-time1)はG順field名,別行選択は別input_ref。先着保持/重複receipt/旧世代拒否/欠落先再送,発注1。parent failure→依存consumer blocked,producer saved/投影failed/consumer待機/plan partialは別state。dispatch rev1→採用rev2取消hold。desc(A1)={F1,X1,B1,A2}だけstale/旧bytes保持,A2→A1 cycle拒否。全親scope/用途/送信intersection,local_only維持/空blocked,local_only∩{TEST-local,TEST-export}={TEST-local}。

^g3-trace

## 原44＋TA6の正常・隔離負例

source版/hashは毎行へ適用。A=ta-candidate-content-v1/T=ta-theme-content-v1/C=canonical-json-v1/J=utf8-text-v1/R=raw-bytes-v1。変異はF/Dから隔離,新content新版/hash。eligible*=TEST能力仮定の机上一致。cap P=planned未実装/U=unsupported/H=human_pending,全行runtime0。G1B TA/COR/GRP aliasesは原44へ対応,分母追加0。

|case ID|norm固定版/hash|正常patch→desk expected|隔離負例→expected/reason|domain|actual capability|
|---|---|---|---|---|---|
|REUSE-01|B14/Gtb/N|A1→F1/X1同key/hash,別ref→eligible*/再生成0|X1.binding.hash=H('other')→rejected(hash)|R|P|
|REUSE-02|B14/Gt/N|L1.unit=utterance→eligible*|L1.unit=participant,slot=utterance→rejected(unit)|R|P|
|REUSE-03|B14/Gm/N|join key=id,右1件/id→9rows|右u02を2件→rejected(multiplicity)|R|P|
|REUSE-04|B14/Gm/N|7observed/2null/3zeroを保持|u07.value=null→0置換→rejected(unprocessed)|R|P|
|REUSE-05|B14/Gb/N|frozen=TEST-store-r1/A1/hash固定→eligible*|旧run.meaning削除→hold(補完禁止)|R|P|
|REUSE-06|B14/Gt/Tp/N|B1 relation(F1,Q1)=disagreement,両ref保持→human_pending|多数決=adopt→hold(意味/本人なし)|A/R|P/H|
|REUSE-07|B14/Gb/N|A2.selection_basis=B1,evidence_context=snapshot→新task|原文を数値data_inputへ→rejected(role/kind)|C/A|P|
|REUSE-08|B14/Gb/N|A1→F1/X1→B1→A2,Q1独立→acyclic|edge A2→A1→rejected(cycle)|C|P|
|REUSE-09|B14/Gb/N|X1=failed→B1 blocked,F1/Q1保持,plan partial|B1=successに置換→rejected(未実行)|C|P|
|REUSE-10|B14/Gb/N|同event再送→delivery1/発注1,欠落先のみ|generation0→rejected(old),発注2不可|R/C|P|
|REUSE-11|B14/Ghb/N|A1基準変更→F1/X1/B1/A2のみstale,旧bytes保持|Q1もstale→rejected(非子孫)|A/C|P|
|REUSE-12|B14/Gt/N|A1候補/探索,共有親数1→human_pending|confirmatory/独立証拠2→rejected(purpose/依存)|R|P/H|
|CONN-01|B15/Gt/N|5kind＋各TEST-cap照合→TEST shape match|cap欠落→unsupported,embedding成功不可|R|U actual adapters|
|CONN-02|B15/Gt/N|TEST-newmethod+cap_stub定義→desk一致|実registry未登録→unsupported(新method未実装)|R|U|
|CONN-03|B15/Gb/N|from_step A1待機,保存後=frozen同検査|output=absent/latest代替→rejected(ref)|R|P|
|CONN-04|B15/Gm/N|TEST projection→aggregate→1:1join,3定義固定|vector.space_id=other→rejected(space),意味同名不可|R/C|U transforms|
|CONN-05|B15/Tp/Gt/N|claim+relation+原文typedref→候補対照human_pending|receipt.kind=claim_set→rejected(研究kind外)|A/C/R|P/H|
|CONN-06|B15/Gb/N|手動/AI同guard,frozen旧通知なし,投影失敗でもsaved保持|採用前cancel=true→hold,旧run意味推測不可|A/C|P|
|GI-01|B16/Tg/Gm/N/Wpu,b,pg|valid_time=false→null,順序のみ/準備human_pending|u03.start=0,end=0→rejected(placeholder)|C/R|P/H|
|GI-02|B16/Gm/N/Wpu,b,pg|TEST attendance=[A,B,D,C]→4在席/3known speaker,C無発言|attendance省略→実参加unknown,C.value=0→rejected|C/R|P/H|
|GI-03|B16/Gm/Tp/N/Wpu,b,pg|exclude=u01/v00,context u01保持,joint u05一行|u01 contextも削除→needs_input(応答元)|C/J|P|
|GI-04|B16/To,Gb/N/Wpu,b,pg|section_a→u04再取得,episode union4,u07未読|抜粋2行を全read11扱い→rejected(集合)|C/J|U section reader|
|GI-05|B16/Gtm/N/Wpu,b,pg|mediaなし→unknown,u03順序だけ|笑い/感情=confirmed→hold(根拠なし)|C/J|P/H|
|GI-06|B16/Gt/Tp/N/Wpu,b,pg|A1共有,claim/relation別kind→意味human_pending|ones4→重要性確定→hold(意味未判定)|A/R|P/H|
|GI-07|B16/Gtm/N/Wpu,b,pg|speaker c1:s1=A/c2:s1=E,確認TEST-code版で対応|local s1同一人/同名別定義join→rejected|C/R|P|
|GI-08|B16/To/N/Wpu,b,pg|TEST memo固定ref/旧Theme保持→draft|全流派に一致率必須/TEST本人採用→hold(人判断)|T/J|P/H|
|GI-09|B16/Gm/N/Wpu,b,pg|9utter/4known participant/2conv,5conv-speaker|u05を2utterへ複製→rejected；nested推論blocked|R|U nested inference|
|GI-10|B16/Gtb/N/Wpu,b,pg|全親local_only intersection,未読/失敗残す|destinations+=TEST-export→rejected(policy)|A/C|P|
|GI-11|B16/P:QA01-03/Tg/N/Wpu,b,pg|数値cell/step照合と意味holdを分離|同result_idで符号/N変更→rejected；因果断定hold|R/C|P/H|
|QA-01|P13/Ghm/N/Co,Ro,C8st,R8st|Decimal HALF_EVEN coef=-0.24,p=.0048,N7,57.14%→cell一致|同cellにcoef=+.24/架空CI→rejected(セル不一致)|R/C|P renderer|
|QA-02|P13/Tg/N/T8stslh|AI p2/p3申告は構造のみ,code receipt,人TEST stub→unverified|AI p4/actor不一致→rejected；実人未回答→draft/human_pending；参照/入力不足→needs_input；必須空→needs_input；自由文申告未確認|C/R|P/H|
|QA-03|P13/Gt/Tp/N|限定説明でもmeaning=undetermined→human_pending|相関→因果/未読全体一般化→hold(方法review)|A/T|H|
|QA-04|P13/Gm/N/Co,Ro,C8st,R8st|TEST採用stub＋3登録定義→表9/観測7/ones4,独立人4|unit/N/分母9/同人5/共同配分→rejected/blocked|R/C|U real adoption|
|QA-05|P13/To/Gh/N|Theme v1/2とcreate/update理由,metadata追記HC不変|同version定義変更/旧target新版採用→hold/hash mismatch|T/A|P/H|
|QA-06|P13/Gm/N/Co,Ro,C8st,R8st|label表hash固定,projection/aggregate/joinのみ→TEST記述|adoptionなし/definition_hash違い/AI式→blocked/rejected|R|U real adoption|
|QA-07|P13/Gt/N|desk構造/CPU/mock/realmodel/human別state→未測定を保持|CPU成功→realmodel/human成功→rejected(評価混同)|C|P/H|
|ASSET-01|B18/Gtb/N|同名r1/r2別key,選択r1,A2新版固定→eligible*|method名/latestのみ→rejected(非固定)|A/R|P|
|ASSET-02|B18/Gt,hash/N|state_revision2/新draftでもCC/TC hash同じ|stateをTCへ混入→rejected(projection)|A/T|P|
|ASSET-03|B18/Gb/N|B1選択optional T1待機,P2 omitted理由で依存なし|P1で無断省略→rejected(plan変更なし)|C|P|
|ASSET-04|B18/Gb/N|slot/ref識別,同asset別行ref1/ref2,先着/再送発注1|keyのinput_ref_id欠落→rejected(配送混同)|C/R|P callback|
|ASSET-05|B18/Gb/N|dispatch rev1→adopt rev2 revoked→hold|旧binding rev1を採否に流用→rejected(revalidate)|A/C|P|
|ASSET-06|B18/Gb/N|producer saved,投影failed,consumer waiting,plan partial|再送でproducer再計算→rejected(冪等)|C/R|P|
|ASSET-07|B18/Gb/N|desc(A1)={F1,X1,B1,A2},Q1/I1/T1保持|A2→A1逆辺→rejected(cycle),旧bytes削除不可|C/A|P|
|ASSET-08|B18/Gtb/N|用途/scope/送信先intersection→TEST-localのみ|scope/confirmatory拡大→blocked(intersection)|C/A|P|
|G2-TA-01|To/Gh/N/T8stslh|CC/TC/snapshot/code固定,7string+metadata→draft/human_pending|7string parse→本人adopt→hold(本人未回答)|A/T/J|P persistence|
|G2-TA-02|Tgo/Gh/N/T8stslh|TEST target正domain/ID/version/hash→desk一致|actor=unknown/target hash改竄→rejected|A/T|P validator|
|G2-TA-03|To/Gb/N/T8stslh|u07 unread={u07},反例=u04,本人未読unknown→human_pending|u07をcounterexampleに追加→needs_input(text/hashなし)|J/T/R|P/H|
|G2-TA-04|To/Gh/N/T8stslh|split v1→2/3,旧snapshot保存,子だけstale|from=to/self/historyをHCへ→rejected(cycle/projection)|T/A|P|
|G2-TA-05|Tg/Gt/N/T8stslh|dataset/claim_set scope→draft,section選択はunsupported|embedding/sectionを既存TA07実行許可→rejected|A/C|U|
|G2-TA-06|Tg/Gb/N/T8stslh|selected T1待機/duplicate execute1/採用前cancel hold|optional無断省略/旧generation採用→rejected|C/R|P|

^g3-cases

## FULL G3 r3参照trace

r2=6b09941、旧129履歴保持/再実行なし。root50不変、12alias/5coverage非加算。

`G3-native-fragment-ref-v1` static extractor:上表1-based原行全体。Q=全quote行/Tn=header＋全data n行、外側ID=end+2照合。G t/h/b/m=asset-types/hash/binding/measures、T/C/R g/p/o=tce/cee/gcee-guards/procedure/output、W p/pg/u/b/c=giew-procedure/procedure-guards/units/binding/cases、08 st/sl/h/c=ta/cor/grp-stages/slots/hooks/g3-cases。N明示節、heading拡張/全文fallbackなし、欠行needs_input。実08 readerでない。02全段階＋判断/失敗修正/結果節、TA前提/Byrne・FGI記録は別必須section、未取得needs_input。

M(C/R)正常：固定1会話/utterance/all_included_initial/用途/全親許可intersection→ai-plan needs_calculation（result IDs/bindings/claims空）→Core判断/Handler正式p2 code同run/全原行hash→同じ検証済セル配信→ai-report draft。R p1/p3/p4未回答human_pending/actualrecords=[]。C=pearson/spearman、R=crosstabs/anova/kruskal_wallis/chi_square、statistical-tools-1。Welch/paired/nested/任意式unsupported。AI各ai-plan/reportのみ、required<=performed<=allowed・重複禁止、p2/p3代行rejected。

S2/C2の5string=analysis_plan/prerequisite_review/result_explanation/quality_record/limitations。9keys=result_id,dataset,row_id,column,variables,target,dataset_version,computation_input_hash,rows_hash（value禁止）。C variables原順/selectors method、R crosstabs row/column＋table_id/row_value/column_value、tests outcome＋family/test/group_variable。unit/分母/対象/N/欠測/状態/hash同原行、抜粋hash不可。Decimal HALF_EVEN 3桁/負丸め0=0.000、p4桁、percent2桁/二重100倍禁止、旧QA01の2桁は別例。null/unknown/not_computed≠0、観測0有効、CI/補正なしを捏造しない。

|COR alias / GRP alias|元root|正常Mの隔離負例/不足（Cgpo+C8stslh/Rgpo+R8stslh）|
|---|---|---|
|G1B-COR-01 / G1B-GRP-01|QA-01/02,CONN-06|draft/human_pending、未配信needs_input|
|G1B-COR-02 / G1B-GRP-02|CONN-02,QA-02|C unknown/anova・R unknown/Welch/pearson→rejected|
|G1B-COR-03 / G1B-GRP-03|REUSE-02,GI-04|wrongunit/section→unsupported、数量consumerだけblocked|
|G1B-COR-04 / G1B-GRP-04|QA-04/06|未review/新採用表→human_pending/unsupported、別候補draft保持|
|G1B-COR-05 / G1B-GRP-05|REUSE-01,QA-01/02|C rows_hash差替/R row_value別群→rejected、AI p2/p3偽装拒否|
|G1B-COR-06 / G1B-GRP-06|REUSE-04,QA-03,GI-11|未配信needs_input/null0化拒否、因果断定隔離・意味人待ち|

W正常：researcher ta-p1/fgi-p1準備→許可ta-p2/p3候補→researcher link両端/context→researcher比較（数量選択時M別task）→ta-p4/p5反例/定義→ta-p6/fgi-p7 draft受渡し。who/what/permission/HC/原版/intersectionを各段階照合。TA p1/p4/p5/p6別HumanRecord/revision、正常p4=defer/[ta-p4]だけ、実records=[]。FGI本人recordをAI補助/q1リンク数へ置換不可。N＋W purpose/procedure**とprocedure-guards同時**/units/binding/cases必須、黙った再精読なし。

|workflow coverage（5行、W全block/G/T/T8）|正常 / 隔離負例 / 不足|
|---|---|
|GI-01/02/03|名簿4≠観測3/context司会。false時刻0/silent0補完拒否、本人不足needs_input/human_pending|
|GI-04/05|撤回u04再取得/media unknown。link先削除missing_targetで当interactionだけhold、全文/笑い推測なし|
|GI-06/07|claim/relation/原文別kind・local対応。共有親を独立証拠/異義joinへ→rejected、本人対応不足hold|
|GI-08/09|所有memo/旧版/joint1行/episode union4/独立人4。u05配分二重化/conv-speaker5誤用拒否、本人採否未回答|
|GI-10/11|全親許可/未読/actor照合。export拡大/attachment前取消→子hold、他draft保持、技術Handler/G4・意味採否人|

REF112事前分母12:46保持。定義を13:02:58前にOrca msg_22dc375f60ef固定：NORM9/FRAG32/HASH12/SET12/DEC8/ACTOR9/POL8/ALIAS12/FLOW5/HIST5。各1複合assertion、定義SHA e9b59331660b5803b7fa063512037e01f1b9cda550a1874123c46b2a35effb48。詳細名・式対象は同message。pure-memory referenceのみ、runtime/model/human0、wrapperはC0別票、旧129再使用なし。

13:04:23 JST最終112pass/0fail/0unexecuted、0.0036831s。結果SHA 65fd1f7a71905ddba675505b609c9be67d3e0792516ecae801d816427f64b8b3。累計336試行:初回110/2fail（ACTOR08抽出regex/HIST01 path接頭辞）、修理後112、GRP row_value負例明示後112。期待不変、msg_4fda38a8fed0/79abdab73d78。旧作者18分失敗/文字列・30321/30245/30102/29800byte guard失敗と今回誤path取得履歴保持。回復cap.15h/独立.20h別、未受入/runtime0。

## 有限CPU probeと次工程

旧CPU selfcheck成功: hash10/canonical20/set19/arithmetic15/Decimal11/domain38/DAG-policy16=129 assertions,0.0014s,failed0。縮約wrapperのhash式を含み,runtime validatorでない。formal runtime/model/human adoption=0。

50期待≠runtime50試行,構造≠意味/モデル/人有用性。旧開始10:23:49 JST/author<=.5staffh履歴。r3独立review/Dot工程採否は別、人判断留保。
