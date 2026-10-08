'use strict';
// V2 uses the actual Flask GET/POST and temporary typed Handler/Store fixture.
// Optional V3 serves production templates/styles in Edge on loopback only.
const test=require('node:test'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),readline=require('node:readline');
const crypto=require('node:crypto'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const {createHarness}=require('./dom/harness.cjs');
const node=(h,id)=>h.document.getElementById(`orchestration-human-${id}`);
const pending=(h,method='GET')=>{const r=h.requests.findLast(r=>!r.settled&&r.url.includes('/human-records')&&(r.options.method||'GET')===method);assert(r,`human-records ${method}`);return r;};
const python=String.raw`
import sys,json,sqlite3,copy,threading,subprocess,pathlib
from contextlib import contextmanager
sys.path[:0]=['src','tests']
from flask import Flask,jsonify
from werkzeug.serving import make_server
from test_analysis_human_records import HumanRecordTests
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.analysis_store import AnalysisStore,canonical
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
import test_analysis_typed_assets as typed
h=HumanRecordTests();h.setUp();server=None
try:
 @contextmanager
 def ro_connect():
  db=sqlite3.connect(h.fixture.path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
  db.execute('PRAGMA query_only=ON')
  try:yield db
  finally:db.close()
 reader=AnalysisOrchestrationService(connect=ro_connect,find_item=h.service.find_item,
  source_fingerprint=h.service.source_fingerprint,snapshot_builder=None,agent_runner=None,
  method_runner=None,schedule=False,table_store=AnalysisStore(h.fixture.path,ro_connect))
 app=Flask(__name__,static_folder=str(pathlib.Path('src/gurumoji/static').resolve()))
 calls=[]
 def no_compute(*args,**kwargs):calls.append('unexpected');raise AssertionError('Human UI must not compute/model')
 h.service.agent_runner=no_compute;h.service.method_runner=no_compute
 register_orchestration_routes(app,lambda:h.service,no_compute,table_reader=lambda:reader)
 client=app.test_client();url=h.url
 def inspect():
  packages,_=h.fresh()._human_packages();sources=[]
  for p in packages:
   _,result,_,files=h.fresh().verified_package(p['run_id'])
   assert json.loads(files['human/record.json'])==p['record']
   assert files['human/source.txt'].decode('utf-8')==result['human_submission']['source_text']
   assert json.loads(files['human/submission.json'])['record']==p['record']
   sources.append(files['human/source.txt'].decode('utf-8'))
  return dict(count=len(packages),sources=sources,computations=len(calls))
 run=h.service.status('TEST-conversation',h.run_id)
 base=None
 if len(sys.argv)>1 and sys.argv[1]=='browser':
  html=subprocess.check_output([sys.executable,'tests/dom/render_fixture.py',str(pathlib.Path.cwd())]).decode('utf-8')
  @app.get('/')
  def index():return html
  @app.get('/api/<path:unused>')
  def startup(unused):
   if unused=='jobs/active':return jsonify(job=None)
   if unused=='config':return jsonify(ok=True,runtime=dict(browser_upload=True))
   return jsonify(items=[],speakers=[],terms=[],runs=[],event_count=0,ready_count=0)
  server=make_server('127.0.0.1',0,app,threaded=True)
  threading.Thread(target=server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(server.server_port)
 print(json.dumps(dict(run=run,url=url,base=base),ensure_ascii=False),flush=True)
 for line in sys.stdin:
  command=json.loads(line)
  if command[0]=='request':
   _,method,target,body=command
   response=client.open(target,method=method,data=canonical(body) if body is not None else None,content_type='application/json')
   print(json.dumps(dict(status=response.status_code,data=response.get_json(),cache=response.headers.get('Cache-Control'),inspection=inspect()),ensure_ascii=False),flush=True)
  elif command[0]=='competing':
   response=h.post(h.payload(h.steps[1],decision='defer'))
   print(json.dumps(dict(status=response.status_code,data=response.get_json())),flush=True)
  elif command[0]=='foreign':
   body=command[1];body['asset_key']['library_id']='FOREIGN'
   response=client.post(url,data=canonical(body),content_type='application/json')
   print(json.dumps(dict(status=response.status_code,data=response.get_json(),inspection=inspect())),flush=True)
  elif command[0]=='cancel':
   # Persist an adversarial cancelled producer, as in the S2 Store tests.
   # The completed seed cannot be cancelled a second time via service.cancel.
   with h.fixture.connect() as db:
    run=json.loads(db.execute('SELECT state_json FROM orchestration_runs WHERE run_id=?',(h.run_id,)).fetchone()[0])
    run.update(status='cancelled',cancel_requested=True)
    db.execute('UPDATE orchestration_runs SET state_json=? WHERE run_id=?',(canonical(run).decode(),h.run_id))
   print(json.dumps(dict(run=h.service.status('TEST-conversation',h.run_id))),flush=True)
  elif command[0]=='revoke':
   state=command[1];state.update(revoked=True,state_revision=state['state_revision']+1,policy_revision=state['policy_revision']+1)
   h.fixture.register(states=[state]);print(json.dumps(dict(ok=True)),flush=True)
  elif command[0]=='inspect':print(json.dumps(inspect(),ensure_ascii=False),flush=True)
finally:
 if server:server.shutdown();server.server_close()
 h.doCleanups()
`;
async function bridge(t,browser=false){
 const child=spawn(process.env.GURUMOJI_TEST_PYTHON||'python',['-u','-c',python,...(browser?['browser']:[])],{cwd:root,env:{...process.env,PYTHONIOENCODING:'utf-8'},stdio:['pipe','pipe','pipe']});
 let stderr='';child.stderr.on('data',d=>stderr+=d);const lines=readline.createInterface({input:child.stdout})[Symbol.asyncIterator]();
 const read=async()=>{const line=await lines.next();assert(!line.done,stderr);return JSON.parse(line.value);};
 const ready=await read();t.after(async()=>{child.stdin.end();await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));});
 return {...ready,async send(command){child.stdin.write(JSON.stringify(command)+'\n');return read();},stderr:()=>stderr};
}
async function setup(t){
 const b=await bridge(t),h=await createHarness();t.after(()=>h.close());
 Object.defineProperty(h.w.crypto,'subtle',{value:crypto.webcrypto.subtle});h.w.TextEncoder=TextEncoder;
 h.fixture(b.run);h.evaluate('orchestrationAdopt(window.fixture,"TEST-conversation");orchestrationNode("live").showModal()');
 const respond=async r=>{const response=await b.send(['request',r.options.method||'GET',r.url,r.options.body?JSON.parse(r.options.body):null]);h.reply(r,response.data,response.status);await h.flush();return response;};
 h.click('#orchestration-human-load');const metadata=await respond(pending(h));assert.equal(metadata.status,200,JSON.stringify(metadata.data));
 return {h,b,metadata:metadata.data,respond};
}
function fill(h,step,decision='adopt',source='TEST ONLY 研究者が原文を確認した記録。\n空行と日本語をそのまま保持。'){
 h.change(node(h,'step'),step);h.change(node(h,'actor'),'TEST-ui-researcher');
 h.change(node(h,'source'),source);h.change(node(h,'decision'),decision);h.change(node(h,'reason'),'TEST ONLY この段階の独立した判断');return source;
}
async function review(h){
 h.click('#orchestration-human-review');
 for(let i=0;i<100&&node(h,'confirmation').hidden;i++)await new Promise(resolve=>setTimeout(resolve,5));
 assert.equal(node(h,'confirmation').hidden,false,node(h,'message').textContent);
}
async function save({h,respond}){
 h.click('#orchestration-human-save');const response=await respond(pending(h,'POST'));
 await respond(pending(h));return response;
}
test('actual GET shows frozen independent stages; one intentional record survives fresh Store reload',async t=>{
 const f=await setup(t),{h,b,metadata}=f,option=metadata.options[0];
 assert.equal(node(h,'decision').value,'');assert.equal(node(h,'step').value,'');
 assert.equal(node(h,'stages').children.length,4);assert.equal(node(h,'review').disabled,true);
 assert.match(node(h,'asset').selectedOptions[0].textContent,new RegExp(option.label));
 assert.match(node(h,'stages').textContent,/データに精通.*テーマの開発.*定義と命名.*報告書の作成/);
 assert.equal(node(h,'stages').textContent.includes('\uFFFD'),false);
 assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);assert.equal((await b.send(['inspect'])).computations,0);
 const source=fill(h,option.human_steps[0].step_id);await review(h);
 assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
 assert.match(node(h,'summary').textContent,/候補全体.*版 1/);assert.match(node(h,'summary').textContent,/この一つの段階だけ/);assert.equal(h.document.activeElement,node(h,'save'));
 const response=await save(f);assert.equal(response.status,201);assert.equal(response.inspection.count,1);assert.deepEqual(response.inspection.sources,[source]);
 assert.equal(response.inspection.computations,0);assert.match(node(h,'message').textContent,/他の段階の判断は変更/);
 assert.equal(Array.from(node(h,'stages').children).filter(n=>n.textContent.includes('記録済み')).length,1);
 assert.equal(node(h,'source').value,source);assert.equal(node(h,'author-confirm').checked,false);
});
test('candidate/theme selection and four separate adopt/reject/defer records never claim numeric eligibility',async t=>{
 const f=await setup(t),{h,metadata}=f,option=metadata.options.find(o=>o.target_kind==='candidate');
 h.change(node(h,'target'),node(h,'target').options[metadata.options.findIndex(o=>o.target_kind==='theme')].value);
 assert.match(node(h,'target').selectedOptions[0].textContent,/テーマ/);
 fill(h,option.human_steps[0].step_id,'defer');await review(h);assert.equal((await save(f)).status,201);
 h.change(node(h,'target'),Array.from(node(h,'target').options).find(o=>o.textContent.startsWith('候補全体')).value);
 for(const [i,decision] of ['adopt','adopt','defer','reject'].entries()){
  fill(h,option.human_steps[i].step_id,decision,`TEST ONLY stage ${i} ${decision}`);await review(h);const response=await save(f);assert.equal(response.status,201);
 }
 assert.match(node(h,'stages').textContent,/採用.*保留.*不採用/);
 assert.match(h.document.querySelector('.orchestration-human-record').textContent,/数量分析の入力として利用できるとは限りません/);
 assert.equal(h.requests.filter(r=>r.options.method==='POST').length,5);
});
test('lost reply retains exact request; double submit and retry create only one immutable record',async t=>{
 const f=await setup(t),{h,b,metadata}=f;fill(h,metadata.options[0].human_steps[0].step_id);await review(h);
 h.click('#orchestration-human-save');h.click('#orchestration-human-save');const first=pending(h,'POST');
 assert.equal(h.requests.filter(r=>r.options.method==='POST').length,1);
 const saved=await b.send(['request','POST',first.url,JSON.parse(first.options.body)]);assert.equal(saved.status,201);
 h.fail(first,'TEST lost response after successful commit');await h.flush();
 assert.equal(node(h,'source').disabled,true);assert.equal(node(h,'load').disabled,true);assert.match(node(h,'message').textContent,/同じ内容/);
 h.click('#orchestration-human-save');const repeated=pending(h,'POST');assert.equal(repeated.options.body,first.options.body);
 const response=await f.respond(repeated);assert.equal(response.status,200);assert.equal(response.data.duplicate,true);assert.equal(response.inspection.count,1);
 await f.respond(pending(h));assert.match(node(h,'message').textContent,/重複して記録していません/);assert.equal(node(h,'source').disabled,false);
});
test('real stale revision conflict refreshes safely and preserves source draft for explicit reconfirmation',async t=>{
 const f=await setup(t),{h,b,metadata}=f;const source=fill(h,metadata.options[0].human_steps[0].step_id);await review(h);
 assert.equal((await b.send(['competing'])).status,201);
 const rejected=await save(f);assert.equal(rejected.status,409);assert.equal(rejected.inspection.count,1);
 assert.equal(node(h,'source').value,source);assert.equal(node(h,'confirmation').hidden,true);assert.match(node(h,'message').textContent,/保持/);
 const foreign=await b.send(['foreign',JSON.parse(h.requests.findLast(r=>r.options.method==='POST').options.body)]);assert.equal(foreign.status,409);assert.equal(foreign.inspection.count,1);
 await review(h);assert.equal((await save(f)).status,201);
});
test('correction requires explicit same-author confirmation and immutable previous revision',async t=>{
 const f=await setup(t),{h,metadata}=f;fill(h,metadata.options[0].human_steps[0].step_id);await review(h);const first=await save(f);
 assert.equal(node(h,'actor').readOnly,true);assert.equal(node(h,'author-field').hidden,false);assert.equal(node(h,'author-confirm').required,true);
 h.change(node(h,'source'),'TEST ONLY 訂正する研究者原文');h.change(node(h,'decision'),'defer');h.click('#orchestration-human-review');await h.flush();assert.equal(node(h,'confirmation').hidden,true);
 node(h,'author-confirm').checked=true;node(h,'author-confirm').dispatchEvent(new h.w.Event('change',{bubbles:true}));await review(h);
 h.click('#orchestration-human-save');const request=pending(h,'POST'),payload=JSON.parse(request.options.body);
 assert.equal(payload.record.record_id,first.data.record.record_id);assert.equal(payload.record.revision,2);assert.deepEqual(payload.record.actor,first.data.record.actor);
 assert.equal(payload.record.supersedes_record_ref.content_hash,first.data.record_ref.content_hash);
 assert.equal((await f.respond(request)).status,201);await f.respond(pending(h));assert.match(node(h,'stages').textContent,/保留を記録済み（第2版）/);
});
test('current permission revocation rejects a prepared record and retains the explicit memo',async t=>{
 const f=await setup(t),{h,b,metadata}=f;fill(h,metadata.options[0].human_steps[0].step_id);await review(h);const first=await save(f);
 const source=fill(h,metadata.options[0].human_steps[1].step_id,'defer','TEST ONLY 許可変更前の未保存メモ');await review(h);
 await b.send(['revoke',first.data.state]);const rejected=await save(f);
 assert.equal(rejected.status,409);assert.equal(rejected.inspection.count,1);assert.equal(node(h,'source').value,source);assert.equal(node(h,'review').disabled,true);
 assert.equal(node(h,'confirmation').hidden,true);assert.match(node(h,'message').textContent,/保持|対象版/);
});
test('unknown schema, cancelled run and closed/late read fail honestly without losing a draft',async t=>{
 const f=await setup(t),{h,b,metadata}=f;const source=fill(h,metadata.options[0].human_steps[0].step_id);
 h.click('#orchestration-human-load');const r=pending(h);h.reply(r,{...metadata,schema_version:99});await h.flush();assert.equal(node(h,'review').disabled,true);assert.equal(node(h,'source').value,source);assert.match(node(h,'message').textContent,/未対応/);
 h.click('#orchestration-human-load');const late=pending(h);h.click('#orchestration-live-close');h.reply(late,metadata);await h.flush();assert.equal(node(h,'review').disabled,true);
 h.document.getElementById('orchestration-live').showModal();h.click('#orchestration-human-load');await f.respond(pending(h));
 const cancelled=await b.send(['cancel']);h.fixture(cancelled.run);h.evaluate('orchestrationState.run=window.fixture;renderAnalysisOrchestration()');assert.equal(node(h,'review').disabled,true);assert.equal(node(h,'source').value,source);
 h.click('#orchestration-human-load');const read=await f.respond(pending(h));assert.equal(read.data.enabled,false);assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
});

const rawTargetsPython=String.raw`
import sys,json,hashlib
sys.path[:0]=['src','tests']
from flask import Flask
import test_analysis_typed_assets as typed
from test_analysis_qualitative_assets import QualitativeAssetTests
from test_table_pilot_routes import TablePilotFactoryTests
from gurumoji.analysis_store import AnalysisStore,canonical
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
# Give the existing invented fixture its real Handler source revisions before
# publication. Never change library revisions after immutable packages exist.
original_setup=typed.TypedHandlerIntegrationTests.setUp
def setup_versions(self):
 original_setup(self)
 with self.fixture.connect() as db:db.execute("UPDATE library_items SET revision_count=1,analysis_revision=1 WHERE id='TEST-conversation'")
typed.TypedHandlerIntegrationTests.setUp=setup_versions
q=QualitativeAssetTests()
try:q.setUp()
finally:typed.TypedHandlerIntegrationTests.setUp=original_setup
try:
 kind=sys.argv[1]
 if kind=='qualitative_bundle':
  scope={key:q.ta['scope'][key] for key in ('scope_id','manifest_hash')}
  plan=dict(version='asset-plan-1',plan_id='TEST-UI-qualitative-seed',plan_version=1,steps=[dict(step_id='comparison',method_id='qualitative_compare',parameters=dict(proposals=[]),scope=scope,inputs=[q.ref('candidate',q.ta),q.ref('original',q.original,role='evidence_context',original=True)])])
  q.service.register_asset_plan('TEST-conversation',q.run['run_id'],plan);q.service._drain_tasks(q.run['run_id'])
  with q.t.fixture.connect() as db:
   task=q.service._tasks(db,q.run['run_id'])[0]
  assert task['status']=='succeeded',task
  asset=AnalysisStore(q.t.fixture.path,q.t.fixture.connect).connected_output_descriptor(task['table_store_run_id'])
 else:asset=q.graph
 namespace,traces,connections=TablePilotFactoryTests().reader_namespace(q.t.fixture.path,source_hash=q.run['input_hash'],driver=q.service)
 calls=[]
 def no_execution(*a,**k):calls.append(True);raise AssertionError('Human record UI does not execute a model or method')
 q.service.method_runner=no_execution;q.service.agent_runner=no_execution
 app=Flask(__name__);register_orchestration_routes(app,lambda:q.service,no_execution,table_reader=namespace['analysis_table_pilot_reader']);client=app.test_client()
 def inspect():
  fresh=AnalysisStore(q.t.fixture.path,q.t.fixture.connect);packages,_=fresh._human_packages();sources=[]
  for package in packages:
   files=fresh.verified_package(package['run_id'])[3];sources.append(files['human/source.txt'].decode('utf-8'))
  return dict(count=len(packages),sources=sources,computations=len(calls),db_hash=hashlib.sha256(q.t.fixture.path.read_bytes()).hexdigest())
 print(json.dumps(dict(run=q.service.status('TEST-conversation',q.run['run_id']),url=f'/api/library/TEST-conversation/analysis/orchestration/{q.run["run_id"]}/human-records',asset_key=asset['asset_key'],inspection=inspect())),flush=True)
 for line in sys.stdin:
  method,url,body=json.loads(line);before=inspect();response=client.open(url,method=method,data=canonical(body) if body is not None else None,content_type='application/json')
  print(json.dumps(dict(status=response.status_code,data=response.get_json(),cache=response.headers.get('Cache-Control'),before=before,after=inspect()),ensure_ascii=False),flush=True)
finally:q.doCleanups()
`;
async function rawTargetsBridge(t,kind){
 const child=spawn(process.env.GURUMOJI_TEST_PYTHON||'python',['-u','-c',rawTargetsPython,kind],{cwd:root,env:{...process.env,PYTHONIOENCODING:'utf-8'},stdio:['pipe','pipe','pipe']});let stderr='';child.stderr.on('data',bytes=>stderr+=bytes);const lines=readline.createInterface({input:child.stdout})[Symbol.asyncIterator]();
 const read=async()=>{const line=await lines.next();assert(!line.done,stderr);return JSON.parse(line.value);};const ready=await read();t.after(async()=>{child.stdin.end();await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));});return {...ready,send:async command=>{child.stdin.write(JSON.stringify(command)+'\n');return read();}};
}
for(const kind of ['relation_graph','qualitative_bundle'])test(`actual generic Human GET -> normal ${kind} form -> POST/source Store/fresh reload and exact duplicate`,async t=>{
 const b=await rawTargetsBridge(t,kind),h=await createHarness();t.after(()=>h.close());Object.defineProperty(h.w.crypto,'subtle',{value:crypto.webcrypto.subtle});h.w.TextEncoder=TextEncoder;h.fixture(b.run);h.evaluate('orchestrationAdopt(window.fixture,"TEST-conversation");orchestrationNode("live").showModal()');
 const respond=async request=>{const result=await b.send([request.options.method||'GET',request.url,request.options.body?JSON.parse(request.options.body):null]);h.reply(request,result.data,result.status);await h.flush();return result;};
 h.click('#orchestration-human-load');const catalogue=await respond(pending(h));assert.equal(catalogue.status,200,JSON.stringify(catalogue.data));assert.equal(catalogue.before.db_hash,catalogue.after.db_hash);assert.equal(catalogue.before.count,catalogue.after.count);assert.equal(catalogue.after.computations,0);assert.equal(catalogue.cache,'no-store');
 const option=catalogue.data.options.find(option=>option.target_kind===kind&&Object.entries(b.asset_key).every(([key,value])=>option.asset_key[key]===value));assert(option,JSON.stringify(catalogue.data));h.change(node(h,'asset'),JSON.stringify(option.asset_key));assert.equal(node(h,'stages').children.length,1);h.change(node(h,'step'),option.human_steps[0].step_id);
 if(option.human_steps[0].latest_record){node(h,'author-confirm').checked=true;node(h,'author-confirm').dispatchEvent(new h.w.Event('change',{bubbles:true}));}else h.change(node(h,'actor'),'TEST-ui-researcher');
 const source='TEST ONLY 研究者が原文に照らした独立した記録\n  日本語と空白を保存する\n';h.change(node(h,'source'),source);h.change(node(h,'decision'),'defer');h.change(node(h,'reason'),'TEST ONLY 解釈を確定せず保留する');await review(h);h.click('#orchestration-human-save');h.click('#orchestration-human-save');const request=pending(h,'POST'),body=JSON.parse(request.options.body);assert.deepEqual(body.record.target,option.target);assert.deepEqual(body.record.allowed_step_ids,[option.human_steps[0].step_id]);assert.equal(body.record.actor.kind,'researcher');assert.equal(body.source_text,source);assert.equal(body.expected_state_revision,option.expected_state_revision);
 const saved=await respond(request);assert.equal(saved.status,201,JSON.stringify(saved.data));assert.equal(saved.after.count,b.inspection.count+1);assert(saved.after.sources.includes(source));assert.equal(saved.after.computations,0);await respond(pending(h));assert.equal(node(h,'source').value,source);
 const duplicate=await b.send(['POST',request.url,body]);assert.equal(duplicate.status,200);assert.equal(duplicate.data.duplicate,true);assert.equal(duplicate.after.count,saved.after.count);
});

// C0 agreed extension proposal only; these are UI fixtures, not Store adoption
// or a proof of the pending backend GET implementation.
for(const [kind,stepId,title] of [['relation_graph','manual-interaction-review','関係を原文に照らして確認'],['qualitative_bundle','qualitative-interpretation-review','比較・再利用の質的解釈を確認']])test(`proposal DOM ${kind}: one exact raw-byte target and original memo, no automatic save`,async t=>{
 const f=await setup(t),{h,metadata}=f,option=structuredClone(metadata.options[0]);
 option.asset_key={...option.asset_key,artifact_id:`TEST-${kind}`,output_name:kind==='relation_graph'?'relation_graph':'claim_set'};
 option.target_kind=kind;option.label=kind==='relation_graph'?'保存された関係グラフ':'保存された質的比較';
 option.target={domain:'raw-bytes-v1',...option.asset_key,version:1,content_hash:'sha256:'+('c'.repeat(64))};
 option.human_steps=[{step_id:stepId,label:title,latest_record:null,next_revision:1,next_supersedes_record_ref:null}];
 h.click('#orchestration-human-load');h.reply(pending(h),{...metadata,options:[...metadata.options,option]});await h.flush();
 h.change(node(h,'asset'),JSON.stringify(option.asset_key));
 assert.equal(node(h,'stages').children.length,1);assert.equal(node(h,'step').value,'');assert.match(node(h,'availability').textContent,/一つの確認/);
 const source=fill(h,stepId,'defer','TEST ONLY 元の記録\n  日本語と空白をそのまま保持\n');await review(h);
 const payload=JSON.parse(h.evaluate('JSON.stringify(orchestrationHumanDraft().payload)'));
 assert.deepEqual(payload.record.target,option.target);assert.deepEqual(payload.asset_key,option.asset_key);assert.deepEqual(payload.record.allowed_step_ids,[stepId]);
 assert.equal(payload.source_text,source);assert.equal(payload.record.actor.kind,'researcher');assert.equal(payload.record.decision,'defer');
 assert.equal(payload.record.record_ref.content_hash,'sha256:'+crypto.createHash('sha256').update(source,'utf8').digest('hex'));
 assert.equal(payload.expected_state_revision,option.expected_state_revision);assert.match(node(h,'summary').textContent,new RegExp(title));
 assert.equal(h.requests.filter(request=>request.options.method==='POST').length,0);
 for(const bad of [{...option,target_kind:'unknown'},{...option,target:{...option.target,artifact_id:'other'}},{...option,human_steps:[{...option.human_steps[0],step_id:'ta-p1'}]}]){
  h.click('#orchestration-human-load');h.reply(pending(h),{...metadata,options:[bad]});await h.flush();
  assert.equal(node(h,'review').disabled,true);assert.equal(node(h,'source').value,source);assert.match(node(h,'message').textContent,/未対応/);
 }
});
test('proposal DOM dedicated participant table creates exact source bytes; TA memo is never converted, 409 retains assignments',async t=>{
 const f=await setup(t),{h,metadata}=f,option=structuredClone(metadata.options[0]);
 const taMemo=fill(h,metadata.options[0].human_steps[0].step_id,'defer','TEST ONLY 原文メモを対応表に変換しない');
 option.asset_key={...option.asset_key,artifact_id:'TEST-unit-table',output_name:'tables/table.json'};option.target_kind='participant_mapping';option.label='TEST ONLY 保存した単位表';
 option.target={domain:'raw-bytes-v1',...option.asset_key,version:1,content_hash:'sha256:'+('d'.repeat(64))};option.owner_item_id='TEST-conversation';option.owner_run_id=metadata.run_id;
 option.human_steps=[{step_id:'participant-mapping-review',label:'話者と参加者の対応を確認',latest_record:null,next_revision:1,next_supersedes_record_ref:null}];
 const context={enabled:false,reason_code:'participant_mapping_missing',human_record_option:option,speakers:[{conversation_id:'TEST-conversation',speaker_id:'TEST-A'},{conversation_id:'TEST-conversation',speaker_id:'TEST-B'}],known_participants:[],confirmed_mapping:null};
 h.fixture({generation:metadata.generation,participant_context:context});h.evaluate('orchestrationAssetState.options=window.fixture;orchestrationParticipantRender()');
 const inputs=h.document.querySelectorAll('#orchestration-participant-assignments input');assert.equal(inputs.length,2);assert.equal(inputs[0].value,'');assert.equal(node(h,'source').value,taMemo);
 h.change(inputs[0],'参加者A');h.change(inputs[1],'参加者A');h.change(h.document.getElementById('orchestration-participant-actor'),'TEST-mapping-researcher');h.change(h.document.getElementById('orchestration-participant-decision'),'adopt');h.change(h.document.getElementById('orchestration-participant-reason'),'TEST ONLY 同一人物であると明示して記録');
 h.click('#orchestration-participant-review');for(let i=0;i<100&&h.document.getElementById('orchestration-participant-confirmation').hidden;i++)await new Promise(resolve=>setTimeout(resolve,5));
 assert.equal(h.document.getElementById('orchestration-participant-confirmation').hidden,false);h.click('#orchestration-participant-save');h.click('#orchestration-participant-save');
 const request=pending(h,'POST'),body=JSON.parse(request.options.body),assignments=[{conversation_id:'TEST-conversation',speaker_id:'TEST-A',participant_id:'参加者A'},{conversation_id:'TEST-conversation',speaker_id:'TEST-B',participant_id:'参加者A'}];
 assert.equal(body.source_text,JSON.stringify({participant_mapping:assignments}));assert.equal(body.record.record_ref.content_hash,'sha256:'+crypto.createHash('sha256').update(body.source_text,'utf8').digest('hex'));assert.deepEqual(body.record.target,option.target);assert.deepEqual(body.record.allowed_step_ids,['participant-mapping-review']);assert.equal(body.record.actor.kind,'researcher');assert.equal(body.expected_state_revision,option.expected_state_revision);assert.equal(h.requests.filter(r=>r.options.method==='POST').length,1);
 h.reply(request,{error:'対応対象の保存版が更新されています',reason_code:'revision_conflict',field:'expected_state_revision'},409);await h.flush();assert.equal(inputs[0].value,'参加者A');assert.equal(h.document.getElementById('orchestration-participant-reason').value,'TEST ONLY 同一人物であると明示して記録');assert.equal(h.document.getElementById('orchestration-participant-review').disabled,true);assert.match(h.document.getElementById('orchestration-participant-message').textContent,/保持/);assert.equal(node(h,'source').value,taMemo);
});
test('proposal DOM participant target is routed to structured form; unknown or multiple-conversation context is unavailable',async t=>{
 const f=await setup(t),{h,metadata}=f,option=structuredClone(metadata.options[0]);option.asset_key={...option.asset_key,artifact_id:'TEST-projection',output_name:'tables/table.json'};option.target_kind='participant_mapping';option.target={domain:'raw-bytes-v1',...option.asset_key,version:1,content_hash:'sha256:'+('e'.repeat(64))};option.human_steps=[{step_id:'participant-mapping-review',label:'参加者対応',latest_record:null,next_revision:1,next_supersedes_record_ref:null}];
 h.click('#orchestration-human-load');h.reply(pending(h),{...metadata,options:[...metadata.options,option]});await h.flush();assert.equal(node(h,'target').options.length,2);assert.equal(node(h,'stages').children.length,4);
 const context={human_record_option:{...option,owner_item_id:'TEST-conversation',owner_run_id:metadata.run_id},speakers:[{conversation_id:'TEST-conversation',speaker_id:'TEST-A'},{conversation_id:'OTHER-conversation',speaker_id:'TEST-B'}],known_participants:[]};h.fixture({generation:metadata.generation,participant_context:context});h.evaluate('orchestrationAssetState.options=window.fixture;orchestrationParticipantRender()');assert.equal(h.document.getElementById('orchestration-participant-form').hidden,true);assert.match(h.document.getElementById('orchestration-participant-status').textContent,/確認できません/);assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
});

test('V3 real loopback Flask API, production CSS, Edge 1440/390 pointer and Tab/Enter', {skip:process.env.GURUMOJI_RUN_UI_BROWSER!=='1'},async t=>{
 const {chromium}=require('playwright'),browser=await chromium.launch({channel:'msedge',headless:true});t.after(()=>browser.close());
 for(const width of [1440,390]){
  const b=await bridge(t,true),context=await browser.newContext({viewport:{width,height:width===390?844:900}}),page=await context.newPage(),errors=[],posts=[],postStatuses=[],blocked=[];
  await context.route('**/*',route=>new URL(route.request().url()).origin===b.base?route.continue():(blocked.push(route.request().url()),route.abort()));
  t.after(()=>context.close());page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/human-records'))posts.push(r.postDataJSON());});
  page.on('response',r=>{if(r.request().method()==='POST'&&r.url().endsWith('/human-records'))postStatuses.push(r.status());});
  await page.addInitScript("sessionStorage.setItem('gurumoji.bootSplashSeen','1')");await page.goto(b.base);
  await page.waitForFunction('typeof orchestrationAdopt === "function"');await page.evaluate(run=>{orchestrationAdopt(run,'TEST-conversation');orchestrationNode('live').showModal();},b.run);
  await page.getByRole('button',{name:'保存対象と研究者記録を確認',exact:true}).click();await page.locator('#orchestration-human-form').waitFor({state:'visible'});
  await page.locator('#orchestration-human-stages li').filter({hasText:/データに精通する/}).waitFor();
  if(process.env.GURUMOJI_UI_ARTIFACT_DIR){fs.mkdirSync(process.env.GURUMOJI_UI_ARTIFACT_DIR,{recursive:true});await page.locator('#orchestration-human-title').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.GURUMOJI_UI_ARTIFACT_DIR,`human-record-fields-${width}.png`)});}
  const step=page.getByLabel('今回記録する段階',{exact:true});const first=await step.locator('option').nth(1).getAttribute('value');await step.selectOption(first);
  await page.getByLabel('記録者の名前',{exact:true}).fill('TEST-browser-researcher');
  await page.getByLabel('この段階の確認・判断を記した原文メモ',{exact:true}).fill('TEST ONLY 日本語の原文を読んだ独立記録。これは合成受入試験です。');
  await page.getByLabel('この対象・段階の判断',{exact:true}).selectOption('adopt');await page.getByLabel('判断の理由',{exact:true}).fill('TEST ONLY 対象と段階を確認したため');
  const reviewButton=page.getByRole('button',{name:'この段階の記録内容を確認',exact:true});
  await page.getByLabel('判断の理由',{exact:true}).focus();await page.keyboard.press('Tab');assert(await reviewButton.evaluate(n=>n===document.activeElement));await page.keyboard.press('Enter');
  const saveButton=page.getByRole('button',{name:'確認した研究者記録を保存',exact:true});await saveButton.waitFor({state:'visible'});await page.waitForFunction('document.activeElement===orchestrationNode("human-save")');
  const form=page.locator('#orchestration-human-form');assert(await form.evaluate(n=>n.getBoundingClientRect().width<=window.innerWidth));
  assert(await page.locator('#orchestration-human-source').evaluate(n=>getComputedStyle(n).lineHeight!=='normal'));
  if(process.env.GURUMOJI_UI_ARTIFACT_DIR){fs.mkdirSync(process.env.GURUMOJI_UI_ARTIFACT_DIR,{recursive:true});await saveButton.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.GURUMOJI_UI_ARTIFACT_DIR,`human-record-review-${width}.png`)});}
  await page.keyboard.press('Enter');await page.getByText('この段階の研究者記録を保存しました。他の段階の判断は変更していません。',{exact:true}).waitFor();
  await page.locator('#orchestration-human-author-field').waitFor({state:'visible'});assert.equal(posts.length,1);
  const inspection=await b.send(['inspect']);assert.equal(inspection.count,1);assert.equal(inspection.computations,0);assert.equal(inspection.sources[0],posts[0].source_text);
  await page.getByLabel('この段階の確認・判断を記した原文メモ',{exact:true}).fill('TEST ONLY 研究者本人による訂正');await page.getByLabel('この対象・段階の判断',{exact:true}).selectOption('defer');
  await page.getByLabel('私は表示された記録者本人として、この訂正を記録します',{exact:true}).check();await reviewButton.click();await saveButton.waitFor({state:'visible'});await saveButton.click();
  await page.getByText(/保留を記録済み（第2版）/).waitFor();assert.equal(posts.length,2);assert.equal(posts[1].record.revision,2);assert.equal(posts[1].record.record_id,posts[0].record.record_id);
  if(process.env.GURUMOJI_UI_ARTIFACT_DIR){await page.locator('#orchestration-human-stages').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.GURUMOJI_UI_ARTIFACT_DIR,`human-record-saved-${width}.png`)});}
  assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);assert.deepEqual(postStatuses,[201,201]);assert.equal((await b.send(['inspect'])).count,2);
  if(process.env.GURUMOJI_UI_ARTIFACT_DIR)fs.writeFileSync(path.join(process.env.GURUMOJI_UI_ARTIFACT_DIR,`human-record-${width}-receipt.json`),JSON.stringify({base:b.base,viewport:{width,height:width===390?844:900},post_statuses:postStatuses,records:(await b.send(['inspect'])).count,source_hashes:Object.fromEntries(['static/analysis-orchestration.js','static/analysis-orchestration.css','templates/views/analysis-orchestration.html'].map(p=>[p,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'src/gurumoji',p))).digest('hex')])),errors,blocked},null,2));
  await context.close();
 }
});
