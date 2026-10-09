'use strict';
// V2 DOM contracts; optional V3 browser interaction. All APIs are synthetic.
const test=require('node:test'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const {createHarness}=require('./dom/harness.cjs');
// Obtain metadata from the actual GET route using existing temporary SQLite.
const fixture=JSON.parse(execFileSync(process.env.GURUMOJI_TEST_PYTHON||'python',['-c',`
import sys,json
sys.path[:0]=['src','tests']
from test_table_pilot_routes import TablePilotRouteTests
t=TablePilotRouteTests(); t.setUp()
try:
 task,raw=t.fixture.execute('table_projection'); p=t.fixture.reusable(task)
 task,a=t.fixture.execute('table_aggregate',t.fixture.request('table_aggregate',[p])); t.fixture.reusable(task)
 print(json.dumps(dict(options=t.options(),run=t.run,raw=raw),ensure_ascii=False))
finally: t.doCleanups()
`],{cwd:root,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}}));
const node=(h,id)=>h.document.getElementById(`orchestration-${id}`);
const pending=(h,suffix,method='GET')=>{const r=h.requests.findLast(r=>!r.settled&&r.url.endsWith(suffix)&&(r.options.method||'GET')===method);assert(r,`${method} ${suffix}`);return r;};
const run={...fixture.run,status:'running',phase:'specialists',tasks:[],events:[],roles:[],allowed_actions:['cancel']};
async function setup(t){const h=await createHarness();t.after(()=>h.close());h.fixture(run);h.evaluate('orchestrationAdopt(window.fixture,"TEST-conversation");orchestrationNode("live").showModal()');return h;}
async function load(h,options=fixture.options){h.click('#orchestration-table-load');h.reply(pending(h,'/table-pilot?offset=0'),options);await h.flush();}
test('real GET metadata builds five opt-in methods; reading/rendering sends no POST',async t=>{
 const h=await setup(t);assert.equal(node(h,'table-form').hidden,true);await load(h);
 assert.equal(node(h,'table-method').options.length,5);assert.equal(node(h,'table-asset').options.length,fixture.options.inputs.length);
 assert.match(node(h,'table-scope').textContent,/固定入力版.*対象.*除外/);
 assert.equal(node(h,'table-confirmation').hidden,true);h.evaluate('renderAnalysisOrchestration();renderAnalysisOrchestration()');
 assert.equal(h.document.getElementById('orchestration-human-form').hidden,true);
 assert.equal(h.requests.filter(r=>r.url.includes('/human-records')).length,0,'table opt-in and polling must not create researcher records or fetch them implicitly');
 assert.match(h.document.querySelector('.orchestration-human-record').textContent,/数量分析の入力として利用できるとは限りません/);
 assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
 assert.equal(node(h,'table-form').querySelector('textarea'),null);
 assert.equal(node(h,'table-parameters').querySelectorAll('input:disabled:checked').length,3);
});
test('five method submissions retain server binding/context and require review; no double submit',async t=>{
 const h=await setup(t);await load(h);const captured=[];
 for(const method of fixture.options.methods){
  h.change(node(h,'table-method'),method.method_id);
  if(method.method_id==='table_join')h.change(node(h,'table-second'),'1');
  h.click('#orchestration-table-execute');assert.equal(h.requests.filter(r=>r.options.method==='POST').length,captured.length);
  h.click('#orchestration-table-review');assert.equal(node(h,'table-confirmation').hidden,false,node(h,'table-message').textContent);
  h.click('#orchestration-table-execute');h.click('#orchestration-table-execute');
  const r=pending(h,'/table-pilot/'+method.method_id,'POST'),body=JSON.parse(r.options.body);captured.push([method.method_id,body]);
  assert.deepEqual(body.bindings.context,fixture.options.inputs[0].projection_request.bindings.context);
  assert.deepEqual(body.bindings.slot,method.slot);assert.equal(body.actor,'code');
  assert.equal(body.bindings.inputs.length,method.method_id==='table_join'?2:1);
  h.reply(r,{task:{registration_duplicate:method.method_id==='table_frequency'}},method.method_id==='table_frequency'?200:202);await h.flush();
  h.reply(pending(h,'/'+run.run_id),{run});await h.flush();assert.equal(node(h,'table-confirmation').hidden,true);
 }
 assert.equal(h.requests.filter(r=>r.options.method==='POST').length,5);
 execFileSync(process.env.GURUMOJI_TEST_PYTHON||'python',['-c',`import sys,json;sys.path.insert(0,'src');from gurumoji.analysis_core import validate_table_pilot_request;[validate_table_pilot_request(m,r) for m,r in json.load(sys.stdin)]`],{cwd:root,input:JSON.stringify(captured),env:{...process.env,PYTHONIOENCODING:'utf-8'}});
});
test('changed selections invalidate review; bounded rows and join same-source are rejected',async t=>{
 const h=await setup(t);await load(h);h.click('#orchestration-table-review');h.change(node(h,'table-param-row_ids'),'2');assert.equal(node(h,'table-confirmation').hidden,true);
 h.click('#orchestration-table-review');assert.equal(h.evaluate('orchestrationTableState.reviewed.request.parameters.row_ids.length'),2);
 h.change(node(h,'table-param-row_ids'),'0');h.evaluate('orchestrationTableReview({preventDefault(){}})');assert.equal(node(h,'table-confirmation').hidden,true);
 h.change(node(h,'table-method'),'table_join');h.click('#orchestration-table-review');assert.match(node(h,'table-message').textContent,/別の保存表/);
 assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
});
test('server conflicts are attached to field; stopped/generation changes disable execution',async t=>{
 const h=await setup(t);await load(h);h.change(node(h,'table-method'),'table_frequency');h.click('#orchestration-table-review');h.click('#orchestration-table-execute');
 h.reply(pending(h,'/table-pilot/table_frequency','POST'),{error:'利用許可が失効しました',reason_code:'permission_revoked',field:'bindings'},400);await h.flush();
 assert.match(node(h,'table-message').textContent,/保存表・利用許可.*失効/);assert.equal(node(h,'table-asset').getAttribute('aria-invalid'),'true');assert.equal(node(h,'table-confirmation').hidden,true);
 h.fixture({...run,generation:run.generation+1});h.evaluate('orchestrationState.run=window.fixture;renderAnalysisOrchestration()');h.click('#orchestration-table-review');
 assert.equal(node(h,'table-confirmation').hidden,true);
 h.fixture({...run,status:'cancelled'});h.evaluate('orchestrationState.run=window.fixture;renderAnalysisOrchestration()');assert.equal(node(h,'table-load').disabled,true);assert.equal(node(h,'table-execute').disabled,true);assert.match(node(h,'table-availability').textContent,/停止/);
});
test('empty, loading, late/closed responses and failed GET do not invent usable tables',async t=>{
 const h=await setup(t);await load(h,{...fixture.options,inputs:[]});assert.equal(node(h,'table-form').hidden,true);assert.match(node(h,'table-message').textContent,/ありません/);
 h.click('#orchestration-table-load');const r=pending(h,'/table-pilot?offset=0');assert.equal(node(h,'table-load').disabled,true);h.click('#orchestration-live-close');h.reply(r,fixture.options);await h.flush();assert.equal(node(h,'table-form').hidden,true);
 node(h,'live').showModal();h.click('#orchestration-table-load');h.reply(pending(h,'/table-pilot?offset=0'),{error:'固定入力の版が更新されています',field:'context'},409);await h.flush();assert.match(node(h,'table-message').textContent,/固定入力・実行状態/);assert.equal(node(h,'table-form').hidden,true);
});
test('actual saved output is a table; zero, missing and unprocessed remain distinct',async t=>{
 const h=await setup(t);h.evaluate('void orchestrationReadResults("saved")');h.reply(pending(h,'/results/saved'),{raw:fixture.raw});await h.flush();
 const host=node(h,'result-content');assert.equal(host.querySelectorAll('tbody tr').length,fixture.raw.datasets.table.rows.length);assert.equal(host.querySelector('pre'),null);
 assert.match(host.textContent,/計算の分母.*欠測.*未処理.*観測ゼロ/);assert.match(host.textContent,/欠測/);assert(host.querySelectorAll('td').length>0);assert(Array.from(host.querySelectorAll('td')).some(n=>n.textContent==='0'));
 assert.match(host.querySelector('button').textContent,/履歴ビューアー/);assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
});
test('category rendering preserves boolean, numeric, string and null values without HTML injection',async t=>{
 const h=await setup(t);const raw={...fixture.raw,method_id:'table_frequency',datasets:{table:{
  fields:['category','count','source_utterance_ids'],
  rows:[false,0,'0',null,'<img src=x>'].map(category=>({category,count:0,source_utterance_ids:[]}))}}};
 h.evaluate('void orchestrationReadResults("typed")');h.reply(pending(h,'/results/typed'),{raw});await h.flush();
 const host=node(h,'result-content'),cells=Array.from(host.querySelectorAll('tbody tr'),tr=>tr.cells[0].textContent);
 assert.deepEqual(cells,['false（真偽）','0（数値）','「0」（文字列）','null（保存値）','「<img src=x>」（文字列）']);assert.equal(host.querySelector('img'),null);
});

test('connected unit output reads actual kernel denominators and sources without inventing zero or adoption',async t=>{
 const result=JSON.parse(execFileSync(process.env.GURUMOJI_TEST_PYTHON||'python',['-c',String.raw`
import sys,json
sys.path[:0]=['src','tests']
from test_analysis_table_units import UnitKernelTests
from gurumoji.research_analysis import run_connected_table
t=UnitKernelTests().table()
t['rows']=t['rows'][2:4]
result=run_connected_table('unit_aggregate',[t],dict(value_column='x',operation='count',unit='conversation',participant_mapping=None))
print(json.dumps(dict(method_id='unit_aggregate',datasets=dict(table=dict(fields=result['fields'],rows=result['rows'])),population=result['population'],unit_contract=result['unit_contract'],limitations=['TEST ONLY 探索用・意味妥当性は未評価。'])))
`],{cwd:root,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}}));
 const h=await setup(t);h.evaluate('void orchestrationReadResults("unit-result")');h.reply(pending(h,'/results/unit-result'),{raw:result});await h.flush();
 const host=node(h,'result-content');assert.equal(host.querySelector('pre'),null);assert.equal(host.querySelectorAll('tbody tr').length,1);
 assert.match(host.textContent,/対象の分母 1.*計算の分母 0/);assert.match(host.textContent,/分析単位：会話/);
 assert.match(host.querySelector('details').textContent,/対象 2.*観測 0.*欠測 1.*未処理 1.*不明 0.*除外 0/);
 assert.match(host.querySelector('details').textContent,/TEST-u2.*TEST-u3/);
 const cells=[...host.querySelectorAll('td')].map(cell=>cell.textContent);assert(cells.includes('null（保存値）'));assert(cells.includes('未処理'));assert(!cells.includes('0'));
 assert.match(host.textContent,/測定の妥当性.*認定とは別/);assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
});

test('proposal DOM qualitative comparison/reuse keeps semantic proposals, roles and independent-validation boundaries visible',async t=>{
 const h=await setup(t),bundle={version:'qualitative-evidence-1',stage:'B1_comparison',producer_task_id:'TEST-task',human_status:'human_pending',same_parent_evidence:true,independent_validation:false,
  inputs:[{input_ref_id:'fixed-theme',kind:'thematic_candidates',role:'data_input'},{input_ref_id:'fixed-memory',kind:'claim_set',role:'selection_basis'},{input_ref_id:'fixed-context',kind:'snapshot',role:'evidence_context'}],
  omitted_inputs:[{input_ref_id:'missing-parent',omission_reason:'unavailable'}],
  relations:['support','counter','complement','conflict','incomparable'].map((relation,index)=>({relation_id:`relation-${index}`,left:{input_ref_id:'fixed-theme'},right:{input_ref_id:'fixed-memory'},relation,reason:`TEST ONLY 明示理由 ${index} <img src=x>`,actor:{kind:'researcher',actor_id:'TEST-researcher'},actor_evidence:'declared_unverified',semantic_status:'human_pending'})),limitations:[]};
 const show=async(method,bundle)=>{h.evaluate('void orchestrationReadResults("qualitative")');h.reply(pending(h,'/results/qualitative'),{raw:{method_id:method,datasets:{table:{fields:['bundle_json'],rows:[{bundle_json:JSON.stringify(bundle)}]}}}});await h.flush();return node(h,'result-content');};
 let host=await show('qualitative_compare',bundle);assert.equal(host.querySelector('pre'),null);assert.equal(host.querySelectorAll('tbody tr').length,5);
 assert.match(host.textContent,/支持.*反例.*補完.*競合.*比較できない/);assert.match(host.textContent,/作成時の採否：研究者記録待ち/);
 assert.match(host.textContent,/選択の根拠.*根拠の文脈/);assert.match(host.textContent,/別の再分析タスクや予算による独立検証を行った結果ではありません/);assert.equal(host.querySelector('img'),null);
 host=await show('qualitative_reuse',{...bundle,stage:'A2_rereading'});assert.match(host.textContent,/同じ親根拠を用いた再読/);assert.match(host.textContent,/省略した参照.*unavailable/);
 host=await show('qualitative_reuse',{...bundle,stage:'A2_rereading',independent_validation:true});assert.equal(host.querySelector('table'),null);assert.match(host.textContent,/状態を確認できません/);
 assert.equal(h.requests.filter(request=>request.options.method==='POST').length,0);
});

test('UI emitted POST traverses real Flask route, Handler, temporary Store and fresh reload for five methods',async t=>{
 const {spawn}=require('node:child_process'),readline=require('node:readline');
 const worker=spawn(process.env.GURUMOJI_TEST_PYTHON||'python',['-u','-c',`
import sys,json
sys.path[:0]=['src','tests']
from test_table_pilot_routes import TablePilotRouteTests
from gurumoji.analysis_store import AnalysisStore
t=TablePilotRouteTests();t.setUp()
try:
 task,raw=t.fixture.execute('table_projection');p=t.fixture.reusable(task);seed_projection=task['task_id']
 task,raw=t.fixture.execute('table_aggregate',t.fixture.request('table_aggregate',[p]));t.fixture.reusable(task)
 calls=[];saves=[];real_method=t.service.method_runner;real_save=t.f.store.save
 def compute(method,snapshot):
  calls.append(method);return real_method(method,snapshot)
 def save(**kwargs):
  if kwargs.get('request_id','').startswith('table-pilot:'):saves.append(kwargs['request_id'])
  return real_save(**kwargs)
 t.service.method_runner=compute;t.f.store.save=save
 print(json.dumps(dict(options=t.options(),run=t.run,seed_projection=seed_projection,seed_source=t.fixture.asset['asset_key'])))
 for line in sys.stdin:
  calls.clear();saves.clear()
  method,body=json.loads(line);response=t.client.post(t.url+'/'+method,json=body);data=response.get_json()
  if response.status_code in (200,202):
   task=data['task'];t.service._execute(t.run['run_id'],task['task_id']);state=t.fixture.state_of(task)
   if state['status']=='succeeded':
    raw=t.fixture.raw_of(task);fresh=AnalysisStore(t.f.path,t.f.connect).verified_package(state['table_store_run_id'])[1]
    data.update(saved_ok=fresh['datasets']==raw['datasets'] and fresh['population']==raw['population'],raw=raw)
   data['state']=state['status'];data['state_error']=state.get('error')
  print(json.dumps(dict(status=response.status_code,data=data,computations=len(calls),saves=len(saves))))
finally:t.doCleanups()
`],{cwd:root,env:{...process.env,PYTHONIOENCODING:'utf-8'},stdio:['pipe','pipe','pipe']});
 let stderr='';worker.stderr.on('data',data=>stderr+=data);
 const lines=readline.createInterface({input:worker.stdout})[Symbol.asyncIterator]();
 const read=async()=>{const line=await lines.next();assert.equal(line.done,false,stderr);return JSON.parse(line.value);};
 t.after(()=>{worker.stdin.end();});
 const live=await read(),h=await setup(t);h.fixture(live.run);h.evaluate('orchestrationAdopt(window.fixture,"TEST-conversation")');await load(h,live.options);
 // Option order is not source identity: reusable aggregate/projection assets
 // may sort ahead of the immutable original. Select the actual seeded input.
 const seedIndex=live.options.inputs.findIndex(input=>Object.entries(live.seed_source).every(([key,value])=>input.source.asset_key[key]===value));
 assert(seedIndex>=0,'GET must expose the seeded immutable original');h.change(node(h,'table-asset'),String(seedIndex));
 for(const method of live.options.methods){
  h.change(node(h,'table-method'),method.method_id);
  if(method.method_id==='table_join')h.change(node(h,'table-second'),String(live.options.inputs.findIndex(a=>!a.fields.includes('n'))));
  if(method.method_id==='table_aggregate'||method.method_id==='table_frequency')h.change(node(h,'table-param-value_column'),'n');
  if(method.method_id==='table_crosstab'){h.change(node(h,'table-param-row_column'),'n');h.change(node(h,'table-param-column_column'),'category');}
  h.click('#orchestration-table-review');h.click('#orchestration-table-execute');const r=pending(h,'/table-pilot/'+method.method_id,'POST');
  worker.stdin.write(JSON.stringify([method.method_id,JSON.parse(r.options.body)])+'\n');const response=await read();
  const duplicate=method.method_id==='table_projection';
  assert.equal(response.status,duplicate?200:202,JSON.stringify(response.data));assert.equal(response.data.task.registration_duplicate,duplicate);
  if(duplicate)assert.equal(response.data.task.task_id,live.seed_projection);
  assert.equal(response.computations,duplicate?0:1);assert.equal(response.saves,duplicate?0:1);
  assert.equal(response.data.state,'succeeded',response.data.state_error);assert.equal(response.data.saved_ok,true);
  h.reply(r,response.data,response.status);await h.flush();h.reply(pending(h,'/'+live.run.run_id),{run:live.run});await h.flush();
  h.evaluate('void orchestrationReadResults("saved")');h.reply(pending(h,'/results/saved'),{raw:response.data.raw});await h.flush();assert(node(h,'result-content').querySelector('table'));
  worker.stdin.write(JSON.stringify([method.method_id,JSON.parse(r.options.body)])+'\n');const repeated=await read();
  assert.equal(repeated.status,200);assert.equal(repeated.data.task.task_id,response.data.task.task_id);assert.equal(repeated.computations,0);assert.equal(repeated.saves,0);
 }
 h.change(node(h,'table-method'),'table_projection');h.change(node(h,'table-param-row_ids'),'2');h.click('#orchestration-table-review');h.click('#orchestration-table-execute');
 const distinct=pending(h,'/table-pilot/table_projection','POST');worker.stdin.write(JSON.stringify(['table_projection',JSON.parse(distinct.options.body)])+'\n');const response=await read();
 assert.equal(response.status,202);assert.notEqual(response.data.task.task_id,live.seed_projection);assert.equal(response.computations,1);assert.equal(response.saves,1);assert.equal(response.data.raw.datasets.table.rows.length,2);
 h.reply(distinct,response.data,202);await h.flush();h.reply(pending(h,'/'+live.run.run_id),{run:live.run});await h.flush();
});

// Catalogue proposal DOM checks stay separate from the real HTTP integration
// below. These rows are invented, never a claim that a Store input is eligible.
function connectedProposal(){
 const parameters={theme_evidence_table:['theme_id'],unit_projection:['columns','unit_ids'],unit_aggregate:['value_column','operation','unit','participant_mapping'],unit_join:['keys'],unit_correlation:['x_column','y_column','statistic'],qualitative_compare:['proposals'],qualitative_reuse:['relation_ids']};
 const source=fixture.options.inputs[0],scope=source.scope;
 const input={option_id:'TEST-connected-0',input_ref_id:'TEST-connected-0',label:'TEST ONLY 宣言済み単位表',enabled:true,reason_code:null,source:source.source,scope,
  kind:'observation_table',schema:{schema_id:'gurumoji.analysis-table'},unit:'utterance',fields:['unit_id','conversation_id','value_status','n','y'],unit_ids:['TEST-u1','TEST-u2'],theme_ids:['TEST-theme'],relation_ids:['TEST-relation'],
  numeric_columns:['n','y'],aggregate_columns:['n','y'],variables:['n','y'].map(variable_id=>({variable_id,value_type:'integer',scale:'ratio'})),roles:['data_input','selection_basis','evidence_context'],semantic_targets:[{input_ref_id:'TEST-connected-0',target_kind:'asset',target_id:source.source.asset_key.artifact_id,version:1,content_hash:source.source.content_hash}],compatible_methods:Object.keys(parameters),confirmed_participant_mapping:null};
 const methods=Object.entries(parameters).map(([method_id,parameter_fields])=>({method_id,title:method_id,parameter_fields,parameter_choices:{operation:['count','sum','mean'],unit:['conversation_speaker','conversation','participant'],statistic:['pearson','spearman'],relation:['support','counter','complement','conflict','incomparable']},parameter_defaults:{},omission_reason_choices:method_id.startsWith('qualitative')?[{value:'unavailable',label:'元資料を現在利用できない'}]:[],roles:method_id.startsWith('qualitative')?input.roles:['data_input'],min_inputs:method_id==='unit_join'?2:method_id==='qualitative_compare'?2:method_id==='qualitative_reuse'?3:1,max_inputs:method_id.startsWith('qualitative')?32:method_id==='unit_join'?2:1,output_kind:method_id.startsWith('qualitative')?'claim_set':'observation_table',output_name:'tables/table.json',output_fields:input.fields,compatible_methods:['unit_aggregate'],output_variables:input.variables,output_units:['conversation']}));
 const second={...structuredClone(input),option_id:'TEST-connected-1',input_ref_id:'TEST-connected-1',label:'TEST ONLY 二つ目の固定根拠'};second.semantic_targets[0].input_ref_id=second.input_ref_id;
 return {schema_id:'gurumoji.asset-plan-options',schema_version:1,version:'asset-plan-options-1',item_id:'TEST-conversation',run_id:run.run_id,library_id:'TEST-library',generation:run.generation,enabled:true,reason_code:null,offset:0,limit:20,next_offset:null,plan_template:{version:'asset-plan-1',plan_id:'TEST-explicit-ui-plan',plan_version:1},methods,inputs:[input,second],omission_reason_choices:[{code:'unavailable',label:'元資料を現在利用できない'}]};
}
async function loadConnected(h,options=connectedProposal()){
 h.w.TextEncoder=TextEncoder;h.click('#orchestration-asset-load');h.reply(pending(h,'/asset-plans/options?offset=0'),options);await h.flush();return options;
}
function selectConnected(h,index=0){h.document.getElementById(`orchestration-asset-choice-${index}`).checked=true;h.document.getElementById(`orchestration-asset-choice-${index}`).dispatchEvent(new h.w.Event('change',{bubbles:true}));}
function addConnected(h){h.click('#orchestration-asset-add');assert.equal(h.evaluate('orchestrationAssetState.steps.length')>0,true,node(h,'asset-message').textContent);}
test('proposal DOM connected opt-in guards: current catalogue, seven methods, bounded selection, no GET computation',async t=>{
 const h=await setup(t);await loadConnected(h);assert.equal(node(h,'asset-method').options.length,7);assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
 assert.equal(h.requests.filter(r=>r.url.includes('/human-records')).length,0);h.change(node(h,'asset-method'),'unit_projection');selectConnected(h);
 const columns=[...node(h,'asset-parameters').querySelectorAll('input[name="asset-columns"]:disabled:checked')];assert.equal(columns.length,3);
 h.click('#orchestration-asset-add');assert.match(node(h,'asset-message').textContent,/列・単位・関係/);
 for(const n of node(h,'asset-parameters').querySelectorAll('input[name="asset-unit_ids"]'))n.checked=true;
 addConnected(h);h.click('#orchestration-asset-execute');assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
 h.click('#orchestration-asset-review');h.click('#orchestration-asset-execute');h.click('#orchestration-asset-execute');const r=pending(h,'/asset-plans','POST'),body=JSON.parse(r.options.body);
 assert.equal(body.plan_id,'TEST-explicit-ui-plan');assert.equal(body.steps.length,1);assert.deepEqual(body.steps[0].parameters.unit_ids,['TEST-u1','TEST-u2']);assert.equal(body.steps[0].inputs[0].role,'data_input');
 h.reply(r,{duplicate:false,identity:{plan_id:body.plan_id,plan_version:1},tasks:{'local-step-1':'TEST-task'}},202);await h.flush();h.reply(pending(h,'/'+run.run_id),{run});await h.flush();
 assert.match(node(h,'asset-message').textContent,/処理|計画/);assert.equal(node(h,'asset-review').disabled,true);
});
test('proposal DOM qualitative explicit target/reason/actor, role separation and source-free omissions',async t=>{
 const h=await setup(t),options=connectedProposal();options.inputs.push({...structuredClone(options.inputs[0]),option_id:'TEST-omitted',input_ref_id:'TEST-omitted',enabled:false,reason_code:'human_pending',semantic_targets:[]});await loadConnected(h,options);
 h.change(node(h,'asset-method'),'qualitative_compare');selectConnected(h,0);selectConnected(h,1);h.change(node(h,'asset-role-1'),'evidence_context');
 const omitted=node(h,'asset-inputs').querySelector('input[data-omit="2"]');omitted.checked=true;omitted.dispatchEvent(new h.w.Event('change',{bubbles:true}));
 h.change(node(h,'asset-param-right'),'1');h.change(node(h,'asset-param-relation'),'counter');h.change(node(h,'asset-param-actor'),'TEST-researcher');h.change(node(h,'asset-param-reason'),'TEST ONLY 少数意見を反例として検討 <img src=x>');addConnected(h);
 const step=JSON.parse(h.evaluate('JSON.stringify(orchestrationAssetState.steps[0])'));assert.deepEqual(step.parameters.proposals[0].left,options.inputs[0].semantic_targets[0]);assert.deepEqual(step.parameters.proposals[0].right,options.inputs[1].semantic_targets[0]);
 assert.equal(step.parameters.proposals[0].actor.kind,'researcher');assert.equal(step.inputs[1].role,'evidence_context');assert.equal(step.inputs[2].selection,'omitted');assert.equal(step.inputs[2].source,undefined);assert.equal(step.inputs[2].omission_reason,'unavailable');assert.equal(node(h,'asset-steps').querySelector('img'),null);
 execFileSync(process.env.GURUMOJI_TEST_PYTHON||'python',['-c','import json,sys;sys.path.insert(0,"src");from gurumoji.analysis_core import validate_asset_plan;validate_asset_plan(json.load(sys.stdin))'],{cwd:root,input:JSON.stringify({...options.plan_template,steps:[step]}),encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}});
 assert.match(node(h,'asset-steps').textContent,/反例.*少数意見/);assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
});
test('proposal DOM participant unit is unavailable without exact input-bound record; 409 preserves request and requires refresh',async t=>{
 const h=await setup(t);await loadConnected(h);h.change(node(h,'asset-method'),'unit_aggregate');selectConnected(h);h.change(node(h,'asset-param-unit'),'participant');h.click('#orchestration-asset-add');assert.match(node(h,'asset-message').textContent,/対応記録/);assert.equal(h.evaluate('orchestrationAssetState.steps.length'),0);
 h.change(node(h,'asset-param-unit'),'conversation');addConnected(h);h.click('#orchestration-asset-review');h.click('#orchestration-asset-execute');const r=pending(h,'/asset-plans','POST');h.reply(r,{error:'現在の入力許可が失効',reason_code:'permission_revoked',field:'inputs'},409);await h.flush();assert.match(node(h,'asset-message').textContent,/保持/);assert.equal(node(h,'asset-inputs').getAttribute('aria-invalid'),'true');assert.equal(node(h,'asset-confirmation').hidden,true);assert.equal(h.evaluate('orchestrationAssetState.steps.length'),1);
 h.click('#orchestration-asset-execute');assert.equal(h.requests.filter(r=>r.options.method==='POST').length,1);
});
test('proposal DOM aggregate count keeps declared category while mean uses only server numeric fields',async t=>{
 const h=await setup(t),options=connectedProposal();options.inputs[0].fields.push('category');options.inputs[0].aggregate_columns.push('category');await loadConnected(h,options);h.change(node(h,'asset-method'),'unit_aggregate');selectConnected(h);
 assert([...node(h,'asset-param-value_column').options].some(option=>option.value==='category'));h.change(node(h,'asset-param-value_column'),'category');h.change(node(h,'asset-param-operation'),'mean');assert(![...node(h,'asset-param-value_column').options].some(option=>option.value==='category'));assert.deepEqual([...node(h,'asset-param-value_column').options].map(option=>option.value),options.inputs[0].numeric_columns);
 h.change(node(h,'asset-param-operation'),'count');h.change(node(h,'asset-param-value_column'),'category');addConnected(h);assert.equal(h.evaluate('orchestrationAssetState.steps[0].parameters.value_column'),'category');assert.equal(h.evaluate('orchestrationAssetState.steps[0].parameters.operation'),'count');assert.equal(h.requests.filter(request=>request.options.method==='POST').length,0);
});
test('proposal DOM unknown or revoked metadata, stopped generation, late close and unknown future capability fail closed',async t=>{
 const h=await setup(t);const options=connectedProposal();await loadConnected(h,{...options,schema_version:99});assert.equal(node(h,'asset-form').hidden,true);
 await loadConnected(h,{...options,enabled:false,reason_code:'human_pending'});assert.equal(node(h,'asset-add').disabled,true);assert.match(node(h,'asset-availability').textContent,/研究者記録/);
 await loadConnected(h,options);h.change(node(h,'asset-method'),'unit_aggregate');selectConnected(h);addConnected(h);h.change(node(h,'asset-method'),'qualitative_compare');assert.equal(node(h,'asset-inputs').querySelectorAll('input[data-choice]').length,2,'undeclared future semantic targets cannot be offered');
 h.fixture({...run,generation:run.generation+1});h.evaluate('orchestrationState.run=window.fixture;renderAnalysisOrchestration()');assert.equal(node(h,'asset-add').disabled,true);
 h.click('#orchestration-asset-load');const r=pending(h,'/asset-plans/options?offset=0');h.click('#orchestration-live-close');h.reply(r,options);await h.flush();assert.equal(node(h,'asset-add').disabled,true);assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
});
test('proposal DOM declared dependency retains exact from_step and uncertain replay executes the identical request',async t=>{
 const h=await setup(t),options=connectedProposal();options.methods.find(m=>m.method_id==='unit_aggregate').output_fields=['unit_id','conversation_id','value_status','value'];await loadConnected(h,options);
 h.change(node(h,'asset-method'),'unit_aggregate');selectConnected(h);addConnected(h);
 selectConnected(h,2);h.change(node(h,'asset-param-operation'),'mean');assert.equal(node(h,'asset-param-value_column').value,'');assert.match(node(h,'asset-param-value_column').textContent,/未取得/);h.click('#orchestration-asset-add');assert.equal(h.evaluate('orchestrationAssetState.steps.length'),1);h.change(node(h,'asset-param-operation'),'count');h.change(node(h,'asset-param-value_column'),'value');addConnected(h);
 const steps=JSON.parse(h.evaluate('JSON.stringify(orchestrationAssetState.steps)'));assert.equal(steps.length,2);assert.deepEqual(steps[1].inputs[0].source,{type:'from_step',step_id:steps[0].step_id,output_name:'tables/table.json'});assert.match(node(h,'asset-steps').textContent,/保存後に実行/);
 h.click('#orchestration-asset-review');h.click('#orchestration-asset-execute');const first=pending(h,'/asset-plans','POST');h.fail(first);await h.flush();assert.match(node(h,'asset-execute').textContent,/確認・再送/);assert.equal(node(h,'asset-clear').disabled,true);
 h.click('#orchestration-asset-execute');const repeat=pending(h,'/asset-plans','POST');assert.equal(repeat.options.body,first.options.body);h.reply(repeat,{duplicate:true,identity:{plan_id:options.plan_template.plan_id,plan_version:1},tasks:{'local-step-1':'TEST-parent','local-step-2':'TEST-child'}},200);await h.flush();h.reply(pending(h,'/'+run.run_id),{run});await h.flush();assert.match(node(h,'asset-message').textContent,/重複して実行していません/);
 execFileSync(process.env.GURUMOJI_TEST_PYTHON||'python',['-c','import json,sys;sys.path.insert(0,"src");from gurumoji.analysis_core import validate_asset_plan;validate_asset_plan(json.load(sys.stdin))'],{cwd:root,input:first.options.body,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}});
});

// The connected tests below require the actual registered catalogue route.
// No writer/Handler/Store behaviour is replaced by a frontend success fixture.
const connectedPython=String.raw`
import sys,json,sqlite3,hashlib,threading,subprocess,pathlib
sys.path[:0]=['src','tests']
from flask import Flask,jsonify
from werkzeug.serving import make_server
from test_table_pilot_routes import TablePilotRouteTests,TablePilotFactoryTests
import test_analysis_asset_bindings as bindings
from gurumoji.analysis_store import AnalysisStore,canonical
from gurumoji.services.analysis_history import AnalysisHistoryService
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
# Match source versions before the existing fixture publishes immutable bytes.
original_init=bindings.SyntheticStore.__init__
def current_versions(self,**kwargs):
 original_init(self,**kwargs)
 with self.connect() as db:db.execute("UPDATE library_items SET revision_count=1,analysis_revision=1 WHERE id='TEST-conversation'")
bindings.SyntheticStore.__init__=current_versions
t=TablePilotRouteTests()
try:t.setUp()
finally:bindings.SyntheticStore.__init__=original_init
server=None
try:
 t.fixture.item.update(revision_count=1,analysis_revision=1)
 t.service.source_fingerprint=lambda _:t.run['input_hash']
 namespace,traces,connections=TablePilotFactoryTests().reader_namespace(t.f.path,source_hash=t.run['input_hash'],driver=t.service)
 calls=[];saves=[];writers=[];real_method=t.service.method_runner;real_save=t.f.store.save
 def compute(method,snapshot):calls.append(method);return real_method(method,snapshot)
 def save(**kw):
  if kw.get('request_id','').startswith('table-pilot:'):saves.append(kw['request_id'])
  return real_save(**kw)
 def writer():writers.append(True);return t.service
 def no_model(*a,**k):raise AssertionError('No actual model/provider in connected UI tests')
 t.service.method_runner=compute;t.service.agent_runner=no_model;t.f.store.save=save
 app=Flask(__name__,static_folder=str(pathlib.Path('src/gurumoji/static').resolve()))
 history=AnalysisHistoryService(connect=namespace['analysis_history_connection'],find_item=t.service.find_item)
 register_orchestration_routes(app,writer,no_model,table_reader=namespace['analysis_table_pilot_reader'],history_viewer=lambda:history)
 client=app.test_client();basepath=f'/api/library/TEST-conversation/analysis/orchestration/{t.run["run_id"]}'
 def inspection():
  fresh=AnalysisStore(t.f.path,t.f.connect);packages,_=fresh._human_packages()
  human_sources=[]
  for p in packages:
   files=fresh.verified_package(p['run_id'])[3]
   human_sources.append(files['human/source.txt'].decode('utf-8'))
  with t.f.connect() as db:
   tasks=t.service._tasks(db,t.run['run_id']);result_ids={row['task_id']:row['result_id'] for row in db.execute('SELECT task_id,result_id FROM orchestration_results WHERE run_id=?',(t.run['run_id'],))};table_count=db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
  saved=[]
  for task in tasks:
   if task.get('table_store_run_id'):
    _,result,_,files=fresh.verified_package(task['table_store_run_id'])
    saved.append(dict(task_id=task['task_id'],method_id=task['method_id'],status=task['status'],result_id=task.get('result_id') or result_ids.get(task['task_id']),raw=result,artifact_hashes={p:hashlib.sha256(b).hexdigest() for p,b in files.items()}))
  return dict(saved=saved,human_sources=human_sources,human_count=len(packages),computations=len(calls),table_saves=len(saves),writers=len(writers),tables=table_count,db_hash=hashlib.sha256(t.f.path.read_bytes()).hexdigest())
 browser_base=None
 if len(sys.argv)>1 and sys.argv[1]=='browser':
  html=subprocess.check_output([sys.executable,'tests/dom/render_fixture.py',str(pathlib.Path.cwd())]).decode('utf-8')
  @app.get('/')
  def index():return html
  @app.get('/api/<path:unused>')
  def startup(unused):
   if unused=='jobs/active':return jsonify(job=None)
   if unused=='config':return jsonify(ok=True,runtime=dict(browser_upload=True))
   return jsonify(items=[],speakers=[],terms=[],runs=[],event_count=0,ready_count=0)
  server=make_server('127.0.0.1',0,app,threaded=True);threading.Thread(target=server.serve_forever,daemon=True).start();browser_base='http://127.0.0.1:'+str(server.server_port)
 print(json.dumps(dict(run=t.run,path=basepath,base=browser_base,inspection=inspection())),flush=True)
 for line in sys.stdin:
  command=json.loads(line)
  if command[0]=='request':
   _,method,url,body=command;before=inspection();trace_start=len(traces)
   response=client.open(url,method=method,data=canonical(body) if body is not None else None,content_type='application/json')
   print(json.dumps(dict(status=response.status_code,data=response.get_json(),cache=response.headers.get('Cache-Control'),before=before,after=inspection(),readonly_statements=traces[trace_start:]),ensure_ascii=False),flush=True)
  elif command[0]=='settle':t.service._drain_tasks(t.run['run_id']);print(json.dumps(dict(run=t.service.status('TEST-conversation',t.run['run_id']),inspection=inspection()),ensure_ascii=False),flush=True)
  elif command[0]=='inspect':print(json.dumps(inspection(),ensure_ascii=False),flush=True)
  elif command[0]=='cancel':t.service.cancel('TEST-conversation',t.run['run_id']);print(json.dumps(dict(ok=True)),flush=True)
  elif command[0]=='revoke':t.fixture.revoke();print(json.dumps(dict(ok=True)),flush=True)
finally:
 if server:server.shutdown();server.server_close()
 t.doCleanups()
`;
async function connectedBridge(t,browser=false){
 const {spawn}=require('node:child_process'),readline=require('node:readline'),worker=spawn(process.env.GURUMOJI_TEST_PYTHON||'python',['-u','-c',connectedPython,...(browser?['browser']:[])],{cwd:root,env:{...process.env,PYTHONIOENCODING:'utf-8'},stdio:['pipe','pipe','pipe']});
 let stderr='';worker.stderr.on('data',d=>stderr+=d);const lines=readline.createInterface({input:worker.stdout})[Symbol.asyncIterator](),read=async()=>{const line=await lines.next();assert(!line.done,stderr);return JSON.parse(line.value);};
 const ready=await read();t.after(async()=>{worker.stdin.end();await new Promise(resolve=>worker.exitCode!==null?resolve():worker.once('exit',resolve));});return {...ready,send:async command=>{worker.stdin.write(JSON.stringify(command)+'\n');return read();}};
}
test('actual connected GET -> UI preparation plan -> real dependency pool/Store -> dedicated Human POST -> participant aggregate/fresh reload',async t=>{
 const b=await connectedBridge(t),h=await setup(t);h.w.TextEncoder=TextEncoder;Object.defineProperty(h.w.crypto,'subtle',{value:require('node:crypto').webcrypto.subtle});h.fixture(b.run);h.evaluate('orchestrationAdopt(window.fixture,"TEST-conversation")');
 const respond=async r=>{const out=await b.send(['request',r.options.method||'GET',r.url,r.options.body?JSON.parse(r.options.body):null]);h.reply(r,out.data,out.status);await h.flush();return out;};
 h.click('#orchestration-asset-load');const read=await respond(pending(h,'/asset-plans/options?offset=0'));assert.equal(read.status,200,JSON.stringify(read.data));assert.equal(read.before.db_hash,read.after.db_hash);assert.equal(read.before.tables,read.after.tables);assert.equal(read.before.computations,read.after.computations);assert.equal(read.before.writers,read.after.writers);assert.equal(read.cache,'no-store');assert(!read.readonly_statements.some(sql=>/^\s*(CREATE|INSERT|UPDATE|DELETE|BEGIN IMMEDIATE)\b/i.test(sql)));
 h.click('#orchestration-participant-prepare');assert.equal(h.evaluate('orchestrationAssetState.steps.length'),1,node(h,'asset-message').textContent);h.click('#orchestration-asset-review');h.click('#orchestration-asset-execute');h.click('#orchestration-asset-execute');const registered=await respond(pending(h,'/asset-plans','POST'));assert.equal(registered.status,202,JSON.stringify(registered.data));const exactPlan=JSON.parse(h.requests.findLast(r=>r.url.endsWith('/asset-plans')&&r.options.method==='POST').options.body);
 await respond(pending(h,'/'+b.run.run_id));let settled=await b.send(['settle']);assert.equal(settled.inspection.table_saves,1);assert.equal(settled.inspection.computations,1);assert.equal(settled.inspection.saved[0].status,'succeeded');assert.equal(settled.inspection.saved[0].raw.datasets.table.rows.length,read.data.inputs.find(i=>i.option_id===read.data.participant_context.preparation_option_id).unit_ids.length);
 const dup=await b.send(['request','POST',b.path+'/asset-plans',exactPlan]);assert.equal(dup.status,200);assert.equal(dup.data.duplicate,true);assert.deepEqual(dup.data.tasks,registered.data.tasks);settled=await b.send(['settle']);assert.equal(settled.inspection.computations,1);assert.equal(settled.inspection.table_saves,1);
 h.click('#orchestration-asset-load');const prepared=await respond(pending(h,'/asset-plans/options?offset=0'));assert.equal(prepared.status,200);assert.equal(prepared.data.participant_context.human_record_option.target_kind,'participant_mapping');
 const expected=prepared.data.participant_context.human_record_option;assert.equal(h.document.getElementById('orchestration-participant-form').hidden,false);
 for(const input of h.document.querySelectorAll('#orchestration-participant-assignments input'))h.change(input,'TEST-person');
 h.change(h.document.getElementById('orchestration-participant-actor'),'TEST-ui-mapping');h.change(h.document.getElementById('orchestration-participant-decision'),'adopt');h.change(h.document.getElementById('orchestration-participant-reason'),'TEST ONLY 固定話者の対応を明示');h.click('#orchestration-participant-review');
 for(let i=0;i<100&&h.document.getElementById('orchestration-participant-confirmation').hidden;i++)await new Promise(resolve=>setTimeout(resolve,5));h.click('#orchestration-participant-save');h.click('#orchestration-participant-save');const humanRequest=h.requests.findLast(r=>!r.settled&&r.url.endsWith('/human-records')),body=JSON.parse(humanRequest.options.body);assert.deepEqual(body.record.target,expected.target);assert.equal(body.expected_state_revision,expected.expected_state_revision);
 const human=await respond(humanRequest);assert.equal(human.status,201,JSON.stringify(human.data));assert.equal(human.after.human_count,1);assert.equal(human.after.human_sources[0],body.source_text);
 const humanDup=await b.send(['request','POST',humanRequest.url,body]);assert.equal(humanDup.status,200);assert.equal(humanDup.data.duplicate,true);assert.equal(humanDup.after.human_count,1);
 const foreign=structuredClone(body);foreign.asset_key.library_id=foreign.record.target.library_id=foreign.record.record_ref.library_id='FOREIGN-library';const foreignReply=await b.send(['request','POST',humanRequest.url,foreign]);assert([400,403,404,409].includes(foreignReply.status),JSON.stringify(foreignReply.data));assert.equal(foreignReply.after.human_count,1);assert.equal(foreignReply.after.computations,1);
 h.click('#orchestration-asset-load');const mapped=await respond(pending(h,'/asset-plans/options?offset=0'));assert.equal(mapped.status,200);h.click('#orchestration-asset-clear');h.change(node(h,'asset-method'),'unit_aggregate');const mappedIndex=mapped.data.inputs.findIndex(i=>i.source.type==='frozen'&&Object.entries(expected.asset_key).every(([key,value])=>i.source.asset_key[key]===value));assert(mappedIndex>=0);selectConnected(h,mappedIndex);h.change(node(h,'asset-param-value_column'),'n');h.change(node(h,'asset-param-operation'),'mean');h.change(node(h,'asset-param-unit'),'participant');addConnected(h);h.click('#orchestration-asset-review');h.click('#orchestration-asset-execute');const aggregate=await respond(pending(h,'/asset-plans','POST'));assert.equal(aggregate.status,202,JSON.stringify(aggregate.data));await respond(pending(h,'/'+b.run.run_id));settled=await b.send(['settle']);
 const saved=settled.inspection.saved.find(s=>s.method_id==='unit_aggregate');assert.equal(saved.status,'succeeded');assert.equal(saved.raw.unit_contract.unit,'participant');assert.equal(saved.raw.datasets.table.rows[0].participant_id,'TEST-person');assert.equal(saved.raw.datasets.table.rows[0].value,1);assert.equal(settled.inspection.computations,2);assert.equal(settled.inspection.table_saves,2);
 h.evaluate(`void orchestrationReadResults(${JSON.stringify(saved.result_id)})`);const result=await respond(pending(h,'/results/'+saved.result_id));assert.equal(result.status,200);assert(node(h,'result-content').querySelector('table'));assert.match(node(h,'result-content').textContent,/参加者.*測定の妥当性/);
});

for(const action of ['cancel','revoke'])test(`actual connected API ${action}: prepared plan is rejected and explicit selections are retained`,async t=>{
 const b=await connectedBridge(t),h=await setup(t);h.w.TextEncoder=TextEncoder;h.fixture(b.run);h.evaluate('orchestrationAdopt(window.fixture,"TEST-conversation")');
 const respond=async request=>{const response=await b.send(['request',request.options.method||'GET',request.url,request.options.body?JSON.parse(request.options.body):null]);h.reply(request,response.data,response.status);await h.flush();return response;};
 h.click('#orchestration-asset-load');assert.equal((await respond(pending(h,'/asset-plans/options?offset=0'))).status,200);h.click('#orchestration-participant-prepare');h.click('#orchestration-asset-review');
 const exact=h.evaluate('JSON.stringify(orchestrationAssetState.steps)');await b.send([action]);h.click('#orchestration-asset-execute');const rejected=await respond(pending(h,'/asset-plans','POST'));assert.equal(rejected.status,action==='cancel'?409:400,JSON.stringify(rejected.data));assert.equal(rejected.data.reason_code,action==='cancel'?'table_run_stopped':'asset_plan_input_unavailable');assert.equal(rejected.after.computations,0);assert.equal(rejected.after.table_saves,0);assert.equal(h.evaluate('JSON.stringify(orchestrationAssetState.steps)'),exact);assert.equal(node(h,'asset-confirmation').hidden,true);assert.equal(node(h,'asset-execute').disabled,true);assert.match(node(h,'asset-message').textContent,/保持/);
 h.click('#orchestration-asset-load');const refresh=await respond(pending(h,'/asset-plans/options?offset=0'));assert.equal(refresh.status,action==='cancel'?409:200);assert.equal(node(h,'asset-review').disabled,true);assert.equal(h.evaluate('JSON.stringify(orchestrationAssetState.steps)'),exact);
});

test('V3 actual connected API, production CSS, Edge 1440/390: prepare, researcher mapping, aggregate and fixed evidence back', {skip:process.env.GURUMOJI_RUN_UI_BROWSER!=='1'},async t=>{
 const {chromium}=require('playwright'),browser=await chromium.launch({channel:'msedge',headless:true});t.after(()=>browser.close());
 for(const width of [1440,390]){
  const b=await connectedBridge(t,true),context=await browser.newContext({viewport:{width,height:width===390?844:900}}),page=await context.newPage(),errors=[],blocked=[],statuses=[],requests=[];
  t.after(()=>context.close());await context.route('**/*',route=>new URL(route.request().url()).origin===b.base?route.continue():(blocked.push(route.request().url()),route.abort()));
  page.on('pageerror',error=>errors.push(error.message));page.on('response',response=>{if(response.request().method()==='POST'&&/\/(asset-plans|human-records)$/.test(new URL(response.url()).pathname))statuses.push(response.status());});page.on('request',request=>{if(request.method()==='POST'&&/\/(asset-plans|human-records)$/.test(new URL(request.url()).pathname))requests.push({url:request.url(),body:request.postDataJSON()});});
  const shot=async label=>{if(process.env.GURUMOJI_UI_ARTIFACT_DIR){fs.mkdirSync(process.env.GURUMOJI_UI_ARTIFACT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.GURUMOJI_UI_ARTIFACT_DIR,`connected-${label}-${width}.png`)});}};
  await page.addInitScript("sessionStorage.setItem('gurumoji.bootSplashSeen','1')");await page.goto(b.base);await page.waitForFunction('typeof orchestrationAdopt === "function"');
  // Only startup navigation is seeded. Catalogue, registrations, records,
  // saved results and fixed evidence below use the real Flask routes.
  await page.evaluate(run=>{orchestrationAdopt(run,'TEST-conversation');orchestrationNode('live').showModal();},b.run);
  const load=page.getByRole('button',{name:'利用できる保存根拠を確認',exact:true});await load.click();await page.locator('#orchestration-asset-form').waitFor({state:'visible'});
  await page.locator('#orchestration-participant summary').click();await page.getByRole('button',{name:'対応を記録する単位表の保存を、計画に追加',exact:true}).click();await page.getByRole('button',{name:'計画全体を確認',exact:true}).click();
  await page.waitForFunction('document.activeElement===orchestrationNode("asset-execute")');await shot('preparation-review');await page.keyboard.press('Enter');await page.getByText('計画を受け付けました。未処理・失敗・保存済み結果はタスク台帳で確認してください。',{exact:true}).waitFor();
  let settled=await b.send(['settle']);assert.equal(settled.inspection.computations,1);assert.equal(settled.inspection.table_saves,1);assert.equal(settled.inspection.saved[0].status,'succeeded');
  await page.evaluate(()=>pollAnalysisOrchestration());await page.locator(`[data-orchestration-result="${settled.inspection.saved[0].result_id}"]`).click();await page.locator('#orchestration-result-content table').waitFor();const projectionText=await page.locator('#orchestration-result-content').innerText();assert.match(projectionText,/欠測/);assert.match(projectionText,/未処理/);assert.match(projectionText,/不明/);assert(await page.locator('#orchestration-result-content td').filter({hasText:/^0$/}).count()>0);await page.locator('#orchestration-result-content').scrollIntoViewIfNeeded();await shot('projection-zero-missing');
  await load.click();await page.locator('#orchestration-participant-form').waitFor({state:'visible'});
  for(const input of await page.locator('#orchestration-participant-assignments input').all())await input.fill('合成人物A');
  await page.getByLabel('参加者対応の記録者',{exact:true}).fill('TEST-browser-mapping');await page.getByLabel('対応の判断',{exact:true}).selectOption('adopt');await page.getByLabel('対応を判断した理由',{exact:true}).fill('TEST ONLY 固定された話者を原文に照らして同一人物として記録');
  await shot('mapping-fields');await page.getByLabel('対応を判断した理由',{exact:true}).focus();await page.keyboard.press('Tab');assert(await page.locator('#orchestration-participant-review').evaluate(node=>node===document.activeElement));await page.keyboard.press('Enter');
  await page.waitForFunction('document.activeElement===orchestrationNode("participant-save")');await shot('mapping-review');await page.keyboard.press('Enter');await page.getByText('対応表を研究者の原文記録として保存しました。派生入力の採否・現在の対応を再取得して確認してください。',{exact:true}).waitFor();
  const mapping=await b.send(['inspect']);assert.equal(mapping.human_count,1);assert.equal(mapping.human_sources[0],requests.find(request=>request.url.endsWith('/human-records')).body.source_text);
  await load.click();await page.waitForFunction('orchestrationAssetState.options?.participant_context?.confirmed_mapping');await page.getByRole('button',{name:'計画を取り消す',exact:true}).click();await page.locator('#orchestration-asset-method').selectOption('unit_aggregate');
  const choice=await page.evaluate(()=>{const key=orchestrationAssetState.options.participant_context.human_record_option.asset_key;return orchestrationAssetState.options.inputs.findIndex(input=>input.source.type==='frozen'&&Object.entries(key).every(([field,value])=>input.source.asset_key[field]===value));});assert(choice>=0);
  await page.locator(`#orchestration-asset-choice-${choice}`).check();await page.locator('#orchestration-asset-param-value_column').selectOption('n');await page.locator('#orchestration-asset-param-operation').selectOption('mean');await page.locator('#orchestration-asset-param-unit').selectOption('participant');
  await page.getByRole('button',{name:'この処理を計画に追加',exact:true}).click();await page.getByRole('button',{name:'計画全体を確認',exact:true}).click();await page.waitForFunction('document.activeElement===orchestrationNode("asset-execute")');await page.keyboard.press('Enter');await page.getByText('計画を受け付けました。未処理・失敗・保存済み結果はタスク台帳で確認してください。',{exact:true}).waitFor();
  settled=await b.send(['settle']);const saved=settled.inspection.saved.find(result=>result.method_id==='unit_aggregate');assert.equal(saved.status,'succeeded');assert.equal(saved.raw.datasets.table.rows[0].participant_id,'合成人物A');assert.equal(saved.raw.datasets.table.rows[0].value,1);assert.equal(settled.inspection.computations,2);assert.equal(settled.inspection.table_saves,2);
  // Refresh the actual task ledger before selecting its server result ID.
  await page.evaluate(()=>pollAnalysisOrchestration());await page.locator(`[data-orchestration-result="${saved.result_id}"]`).click();await page.locator('#orchestration-result-content table').waitFor();await page.locator('#orchestration-result-content').scrollIntoViewIfNeeded();
  const tableScroll=page.locator('#orchestration-result-content .orchestration-table-wrap').first();
  if(width===390){assert(await tableScroll.evaluate(node=>node.scrollWidth>node.clientWidth));await tableScroll.focus();const before=await tableScroll.evaluate(node=>node.scrollLeft);await page.keyboard.press('ArrowRight');await page.waitForFunction(before=>document.querySelector('#orchestration-result-content .orchestration-table-wrap').scrollLeft>before,before);
   const valueIndex=await page.locator('#orchestration-result-content table th').evaluateAll(nodes=>nodes.findIndex(node=>node.textContent==='value'));assert(valueIndex>=0);const valueCell=page.locator('#orchestration-result-content table tbody tr').first().locator('td').nth(valueIndex);assert.equal(await valueCell.innerText(),'1');
   for(let i=0;i<60;i++){const visible=await valueCell.evaluate(node=>{const cell=node.getBoundingClientRect(),wrap=node.closest('.orchestration-table-wrap').getBoundingClientRect();return cell.left>=wrap.left&&cell.right<=wrap.right;});if(visible)break;await page.keyboard.press('ArrowRight');await page.waitForTimeout(30);}
   assert(await valueCell.evaluate(node=>{const cell=node.getBoundingClientRect(),wrap=node.closest('.orchestration-table-wrap').getBoundingClientRect();return cell.left>=wrap.left&&cell.right<=wrap.right;}));}
  await shot('saved-table');
  assert.match(await page.locator('#orchestration-result-content').innerText(),/参加者.*測定の妥当性/s);
  assert(await page.locator('#orchestration-asset-form').evaluate(node=>node.getBoundingClientRect().width<=window.innerWidth));assert(await page.locator('#orchestration-live').evaluate(node=>node.scrollWidth<=node.clientWidth+1));
  await page.getByRole('button',{name:'固定入力・発話の根拠を履歴ビューアーで読む',exact:true}).click();await page.locator('#analysis-history-timeline [data-entry-id]').first().waitFor();
  const entry=page.locator('#analysis-history-timeline [data-entry-id]').filter({hasText:/固定された初期分析・ラベル/}).first();await entry.click();const opener=page.locator('#analysis-history-detail button').filter({hasText:/^固定原文 /}).first();await opener.waitFor();
  await opener.scrollIntoViewIfNeeded();await opener.focus();const viewerSelection=()=>({version:document.getElementById('analysis-history-version').value,role:document.getElementById('analysis-history-role').value,kind:document.getElementById('analysis-history-kind').value,selected:document.querySelector('#analysis-history-timeline [aria-pressed="true"]').dataset.entryId,scroll:['dialog','detail'].map(id=>{const node=document.getElementById('analysis-history-'+id);return [node.scrollTop,node.scrollLeft];})});
  const selectedBefore=await page.evaluate(viewerSelection);await opener.click();await page.locator('#analysis-history-source blockquote').waitFor();assert((await page.locator('#analysis-history-source blockquote').innerText()).length>0);await shot('fixed-source');await page.getByRole('button',{name:'根拠を閉じて選択位置へ戻る',exact:true}).click();assert(await opener.evaluate(node=>node===document.activeElement));
  const selectedAfter=await page.evaluate(viewerSelection);assert.deepEqual(selectedAfter,selectedBefore);
  assert.deepEqual(statuses,[202,201,202]);assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
  if(process.env.GURUMOJI_UI_ARTIFACT_DIR)fs.writeFileSync(path.join(process.env.GURUMOJI_UI_ARTIFACT_DIR,`connected-${width}-receipt.json`),JSON.stringify({base:b.base,width,statuses,inspection:settled.inspection,source_hashes:Object.fromEntries(['static/analysis-orchestration.js','static/analysis-orchestration.css','templates/views/analysis-orchestration.html'].map(file=>[file,require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(root,'src/gurumoji',file))).digest('hex')])),errors,blocked,selectedBefore,selectedAfter},null,2));
  await context.close();
 }
});

test('V3 production CSS at 1440/390: pointer and keyboard review/submit/result', {skip:process.env.GURUMOJI_RUN_UI_BROWSER!=='1'},async()=>{
 const {chromium}=require('playwright');
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{for(const width of [1440,390]){
  const context=await browser.newContext({viewport:{width,height:900}}),errors=[],posts=[];
  const html=execFileSync(process.env.GURUMOJI_TEST_PYTHON||'python',['tests/dom/render_fixture.py',root],{cwd:root,encoding:'utf8'});
  await context.route('**/*',route=>{const u=new URL(route.request().url());let data={};
   if(u.origin!=='https://gurumoji.invalid')return route.abort();
   if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
   if(u.pathname.startsWith('/static/'))return route.fulfill({contentType:u.pathname.endsWith('.css')?'text/css':'text/javascript',body:fs.readFileSync(path.join(root,'src/gurumoji',u.pathname))});
   if(u.pathname.endsWith('/table-pilot'))data=fixture.options;
   else if(route.request().method()==='POST'){posts.push(route.request().postDataJSON());data={task:{registration_duplicate:false}};}
   else if(u.pathname.endsWith('/results/saved'))data={raw:fixture.raw};
   else if(u.pathname.endsWith('/'+run.run_id))data={run};
   else if(u.pathname==='/api/jobs/active')data={job:null};
   else if(u.pathname==='/api/config')data={ok:true,runtime:{browser_upload:true}};
   else data={items:[],speakers:[],terms:[],runs:[],event_count:0,ready_count:0};
   return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.addInitScript("sessionStorage.setItem('gurumoji.bootSplashSeen','1')");await page.goto('https://gurumoji.invalid/');
  await page.waitForFunction('typeof orchestrationAdopt === "function"');await page.evaluate(run=>{orchestrationAdopt(run,'TEST-conversation');orchestrationNode('live').showModal();},run);
  await page.getByRole('button',{name:'利用できる保存表を確認',exact:true}).click();await page.locator('#orchestration-table-form').waitFor({state:'visible'});
  await page.getByLabel('処理方式',{exact:true}).selectOption('table_frequency');
  const review=page.getByRole('button',{name:'選択内容を確認',exact:true});
  await page.getByLabel('処理方式',{exact:true}).focus();
  for(let i=0;i<12&&!await review.evaluate(n=>n===document.activeElement);i++)await page.keyboard.press('Tab');
  assert(await review.evaluate(n=>n===document.activeElement));await page.keyboard.press('Enter');
  const execute=page.getByRole('button',{name:'確認した表処理をローカルで実行',exact:true});await execute.waitFor({state:'visible'});
  if(process.env.GURUMOJI_UI_ARTIFACT_DIR){fs.mkdirSync(process.env.GURUMOJI_UI_ARTIFACT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.GURUMOJI_UI_ARTIFACT_DIR,`table-pilot-confirm-${width}.png`)});}
  await page.keyboard.press('Tab');assert(await execute.evaluate(n=>n===document.activeElement));await page.keyboard.press('Enter');
  await page.getByText('表処理を受け付けました。',{exact:false}).waitFor();assert.equal(posts.length,1);
  await page.evaluate(()=>orchestrationReadResults('saved'));await page.getByRole('button',{name:'固定入力・発話の根拠を履歴ビューアーで読む'}).waitFor({state:'visible'});
  assert.equal(await page.locator('#orchestration-result-content tbody tr').count(),fixture.raw.datasets.table.rows.length);
  if(process.env.GURUMOJI_UI_ARTIFACT_DIR){await page.locator('#orchestration-result-view').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.GURUMOJI_UI_ARTIFACT_DIR,`table-pilot-${width}.png`)});}
  await page.getByRole('button',{name:'固定入力・発話の根拠を履歴ビューアーで読む'}).click();await page.locator('#analysis-history-dialog').waitFor({state:'visible'});assert.equal(await page.locator('#orchestration-live').evaluate(n=>n.open),false);
  assert(await page.locator('#orchestration-table-form').evaluate(n=>n.getBoundingClientRect().width<=window.innerWidth));assert.deepEqual(errors,[]);await context.close();
 }}finally{await browser.close();}
});
