'use strict';
// Synthetic selections in production templates/scripts. API/Store checks below
// must use the fixed backend wire; DOM checks alone do not certify that seam.
const test=require('node:test'),assert=require('node:assert/strict');
process.env.PYTHONIOENCODING='utf-8';
const {createHarness}=require('./dom/harness.cjs');
const {spawn}=require('node:child_process'),readline=require('node:readline'),crypto=require('node:crypto'),path=require('node:path');
const root=path.resolve(__dirname,'..'),node=(h,id)=>h.document.getElementById(`orchestration-${id}`);
const python=String.raw`
import sys,os,json,threading,hashlib,pathlib,subprocess
backend=pathlib.Path(os.environ.get('GURUMOJI_UI_BACKEND_ROOT',os.getcwd())).resolve()
sys.path[:0]=[str(backend/'src'),str(backend/'tests')]
from test_analysis_multi_conversation_units import MultiConversationUnitsTests
from gurumoji.analysis_store import _asset_key
from werkzeug.serving import make_server
from flask import jsonify
h=MultiConversationUnitsTests();h.setUp();server=None
try:
 source_root=pathlib.Path.cwd()
 h.app.static_folder=str(source_root/'src/gurumoji/static')
 html=subprocess.check_output([sys.executable,'tests/dom/render_fixture.py',str(source_root)]).decode('utf-8')
 @h.app.get('/')
 def index():return html
 @h.app.get('/api/<path:unused>')
 def startup(unused):
  if unused=='jobs/active':return jsonify(job=None)
  if unused=='config':return jsonify(ok=True,runtime=dict(browser_upload=True))
  return jsonify(items=[],speakers=[],terms=[],runs=[],event_count=0,ready_count=0)
 sealed={a['asset_key']['store_run_id']:h.store.verified_package(a['asset_key']['store_run_id'])[3] for a in h.native}
 def inspect():
  fresh=h.fresh_service();tasks=[];counts={}
  with h.connect() as db:
   tasks=fresh._tasks(db,h.run['run_id'])
   for table in ['analysis_runs','orchestration_tasks']:counts[table]=db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
  outputs=[]
  for task in tasks:
   if task.get('table_store_run_id'):
    raw=fresh.table_store.verified_package(task['table_store_run_id'])[1]
    outputs.append(dict(method=task.get('method_id',task.get('method')),rows=raw['datasets']['table']['rows'],contract=raw.get('unit_contract'),store_run_id=task['table_store_run_id']))
  return dict(counts=counts,tasks=tasks,outputs=outputs,human_count=len(fresh.table_store._human_packages()[0]),native_unchanged=all(fresh.table_store.verified_package(rid)[3]==files for rid,files in sealed.items()))
 server=make_server('127.0.0.1',0,h.app,threaded=True);threading.Thread(target=server.serve_forever,daemon=True).start()
 print(json.dumps(dict(base='http://127.0.0.1:'+str(server.server_port),api=h.base,run=h.service.status('C1',h.run['run_id']))),flush=True)
 for line in sys.stdin:
  command=json.loads(line)
  if command[0]=='inspect':print(json.dumps(inspect()),flush=True)
  elif command[0]=='drain':
   h.service=h.fresh_service();h.service._drain_tasks(h.run['run_id']);print(json.dumps(inspect()),flush=True)
  elif command[0]=='change-secondary':
   with h.connect() as db:db.execute("UPDATE library_items SET revision_count=revision_count+1 WHERE id='C2'")
   print(json.dumps(dict(ok=True)),flush=True)
  elif command[0]=='exclude-secondary':
   with h.connect() as db:
    segments=json.loads(db.execute("SELECT segments_json FROM library_items WHERE id='C2'").fetchone()[0]);segments[0]['excluded']=True
    db.execute("UPDATE library_items SET segments_json=? WHERE id='C2'",(json.dumps(segments),))
   print(json.dumps(dict(ok=True)),flush=True)
  elif command[0]=='revoke-primary':
   asset=h.native[0];states=h.store._connection_index()[2];history=states[_asset_key(asset['asset_key'])]
   state=dict(history[max(history)]);state.update(revoked=True,state_revision=state['state_revision']+1,policy_revision=state['policy_revision']+1)
   h.store.save_connection_metadata(item_id='C1',snapshot={},request_id='TEST-ui-revoke-primary',metadata=dict(version=1,assets=[],originals=[],states=[state],producer_links=[]))
   print(json.dumps(dict(ok=True)),flush=True)
finally:
 if server:server.shutdown();server.server_close()
 h.doCleanups()
`;
async function bridge(t){
 const child=spawn(process.env.GURUMOJI_TEST_PYTHON||'python',['-u','-c',python],{cwd:root,env:{...process.env,PYTHONIOENCODING:'utf-8'},stdio:['pipe','pipe','pipe']});
 let stderr='';child.stderr.on('data',d=>stderr+=d);const lines=readline.createInterface({input:child.stdout})[Symbol.asyncIterator]();
 const read=async()=>{const line=await lines.next();assert(!line.done,stderr);return JSON.parse(line.value);};
 const ready=await read();t.after(async()=>{child.stdin.end();await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));});
 return {...ready,async send(command){child.stdin.write(JSON.stringify(command)+'\n');return read();}};
}
function pending(h,suffix,method='GET'){const r=h.requests.findLast(r=>!r.settled&&r.url.includes(suffix)&&(r.options.method||'GET')===method);assert(r,`${method} ${suffix}`);return r;}
async function setup(t){
 const b=await bridge(t),h=await createHarness();t.after(()=>h.close());
 Object.defineProperty(h.w.crypto,'subtle',{value:crypto.webcrypto.subtle});h.w.TextEncoder=TextEncoder;
 h.fixture(b.run);h.evaluate('orchestrationAdopt(window.fixture,"C1");orchestrationNode("live").showModal()');
 const respond=async r=>{const response=await fetch(b.base+r.url,{method:r.options.method||'GET',headers:{'Content-Type':'application/json'},...(r.options.body?{body:r.options.body}:{})});const data=await response.json();h.reply(r,data,response.status);await h.flush();return {status:response.status,data};};
 const load=async()=>{h.click(node(h,'asset-load'));const result=await respond(pending(h,'/asset-plans/options'));assert.equal(result.status,200,JSON.stringify(result.data));assert.equal(node(h,'asset-form').hidden,false,node(h,'asset-message').textContent);return result.data;};
 return {b,h,respond,load};
}
function choosePool(h){
 h.change(node(h,'asset-method'),'unit_pool');
 for(const check of node(h,'asset-inputs').querySelectorAll('input[data-choice]'))h.click(check);
 const value=node(h,'asset-parameters').querySelector('input[name="asset-columns"][value="n"]');assert(value);h.click(value);
 h.click(node(h,'asset-add'));assert.equal(node(h,'asset-steps').children.length,1,node(h,'asset-message').textContent);
}
async function execute(f){
 const {h,b,respond}=f;h.click(node(h,'asset-review'));assert.equal(h.document.activeElement,node(h,'asset-execute'));
 h.click(node(h,'asset-execute'));const request=pending(h,'/asset-plans','POST'),response=await respond(request);
 assert.equal(response.status,202,JSON.stringify(response.data));const result=await b.send(['drain']);
 await respond(pending(h,b.api));return {request,response,result};
}
async function saveMapping(f,conversations=2){
 const {h,respond}=f;node(h,'participant').open=true;
 const target=Array.from(node(h,'participant-context').options).find(o=>o.value&&JSON.parse(o.value).at(-1).conversation_ids.length===conversations);assert(target);
 assert.equal(node(h,'participant-form').hidden,true);h.change(node(h,'participant-context'),target.value);
 assert.equal(node(h,'participant-form').hidden,false,node(h,'participant-status').textContent);
 for(const input of node(h,'participant-assignments').querySelectorAll('input'))h.change(input,input.dataset.speaker==='silent'?'TEST-silent-person':'TEST-explicit-person');
 h.change(node(h,'participant-actor'),'TEST-ui-researcher');h.change(node(h,'participant-decision'),'adopt');h.change(node(h,'participant-reason'),'TEST ONLY 明示的に二会話の同一人物を確認');
 h.click(node(h,'participant-review'));for(let i=0;i<100&&node(h,'participant-confirmation').hidden;i++)await new Promise(r=>setTimeout(r,5));
 assert.equal(node(h,'participant-confirmation').hidden,false,node(h,'participant-message').textContent);assert.equal(h.document.activeElement,node(h,'participant-save'));
 h.click(node(h,'participant-save'));const request=pending(h,'/human-records','POST'),response=await respond(request);assert.equal(response.status,201,JSON.stringify(response.data));return {request,response};
}
test('real loopback API: exact source POST, Store scope, explicit group HC and fresh sum6/mean2/observed3',async t=>{
 const f=await setup(t),{h,b,load}=f,before=await b.send(['inspect']);
 const options=await load();assert.equal(options.unit_pool.sources.length,2);assert.deepEqual((await b.send(['inspect'])).counts,before.counts);
 h.change(node(h,'asset-method'),'unit_pool');h.click(node(h,'asset-choice-0'));h.click(node(h,'asset-add'));assert.equal(node(h,'asset-steps').children.length,0);assert.match(node(h,'asset-message').textContent,/2〜16/);assert.equal(h.document.activeElement,node(h,'asset-inputs'));assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
 choosePool(h);const pool=await execute(f),body=JSON.parse(pool.request.options.body);
 assert.deepEqual(Object.keys(body).sort(),['columns','plan_id','plan_version','source_ids','version']);assert.equal(body.source_ids.length,2);assert.equal(pool.result.outputs[0].rows.length,3);
 h.click(node(h,'asset-clear'));await load();const mapping=await saveMapping(f),submission=JSON.parse(mapping.request.options.body);
 assert.deepEqual(submission.record.scope.conversation_ids,['C1','C2']);assert.equal(submission.record.allowed_step_ids.join(),'participant-mapping-review');
 const assignments=JSON.parse(submission.source_text).participant_mapping;assert.equal(assignments.filter(a=>a.participant_id==='TEST-explicit-person').length,2);
 for(const [operation,expected] of [['sum',6],['mean',2]]){
  await load();h.change(node(h,'asset-method'),'unit_aggregate');
  h.fixture(pool.result.outputs[0].store_run_id);const choice=h.evaluate('orchestrationAssetState.choices.findIndex(c=>c.input.confirmed_participant_mapping&&c.source.asset_key?.store_run_id===window.fixture)');assert(choice>=0);h.click(node(h,`asset-choice-${choice}`));
  h.change(node(h,'asset-param-operation'),operation);h.change(node(h,'asset-param-value_column'),'n');h.change(node(h,'asset-param-unit'),'participant');h.click(node(h,'asset-add'));
  const saved=await execute(f),output=saved.result.outputs.at(-1);assert.equal(output.rows.length,1);assert.equal(output.rows[0].value,expected);assert.equal(Object.values(output.contract.denominators)[0].observed,3);assert.equal(saved.result.native_unchanged,true);assert.equal(saved.result.human_count,1);
  h.click(node(h,'asset-clear'));
 }
});
test('real API revalidates secondary revision and current exclusion; input error keeps selection and focus',async t=>{
 for(const mutation of ['change-secondary','exclude-secondary']){
  const f=await setup(t),{h,b,load,respond}=f;await load();choosePool(h);h.click(node(h,'asset-review'));const before=await b.send(['inspect']);await b.send([mutation]);
  h.click(node(h,'asset-execute'));const response=await respond(pending(h,'/asset-plans','POST'));assert(response.status>=400,JSON.stringify(response));
  const after=await b.send(['inspect']);assert.deepEqual(after.counts,before.counts);assert.equal(node(h,'asset-steps').children.length,1);assert.match(node(h,'asset-message').textContent,/保持/);assert.equal(node(h,'asset-confirmation').hidden,true);assert.equal(h.document.activeElement,node(h,'asset-inputs'));
 }
});
test('real API rejects caller scope/hash, duplicate and out-of-bound source requests before saving',async t=>{
 const f=await setup(t),{b,load}=f,options=(await load()).unit_pool,before=await b.send(['inspect']);
 const request={...options.request_template,source_ids:options.sources.map(s=>s.option_id),columns:[...options.required_columns,'n']};
 for(const body of [{...request,source_ids:request.source_ids.slice(0,1)},{...request,source_ids:Array.from({length:17},(_,i)=>`caller-${i}`)},{...request,source_ids:[request.source_ids[0],request.source_ids[0]]},{...request,scope:{scope_id:'caller-authority',manifest_hash:'sha256:'+'a'.repeat(64)}},{...request,manifest_hash:'sha256:'+'a'.repeat(64)}]){
  const response=await fetch(b.base+b.api+'/asset-plans',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),error=await response.json();assert([400,409].includes(response.status),JSON.stringify(error));assert.equal(typeof error.reason_code,'string');
 }
 assert.deepEqual((await b.send(['inspect'])).counts,before.counts);
});
test('real catalogue explicitly denies pooling after secondary change and primary permission loss',async t=>{
 for(const [mutation,reason] of [['change-secondary','pool_sources_insufficient'],['revoke-primary','pool_anchor_unavailable']]){
  const f=await setup(t),{h,b,load}=f;await b.send([mutation]);const page=await load(),before=await b.send(['inspect']);
  assert.equal(page.unit_pool.enabled,false);assert.equal(page.unit_pool.reason_code,reason);h.change(node(h,'asset-method'),'unit_pool');
  assert.equal(node(h,'asset-add').disabled,true);assert.equal(node(h,'asset-review').disabled,true);assert.equal(node(h,'asset-execute').disabled,true);
  assert(Array.from(node(h,'asset-inputs').querySelectorAll('input[data-choice]')).every(n=>n.disabled));assert.match(node(h,'asset-availability').textContent,mutation==='change-secondary'?/2件以上/:/この実行の会話/);h.click(node(h,'asset-add'));
  assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);assert.deepEqual((await b.send(['inspect'])).counts,before.counts);
 }
});
test('real lost POST reply retries identical pool request and full Store scope without duplicate work',async t=>{
 const f=await setup(t),{h,b,load,respond}=f;await load();choosePool(h);h.click(node(h,'asset-review'));h.click(node(h,'asset-execute'));
 const first=pending(h,'/asset-plans','POST'),received=await fetch(b.base+first.url,{method:'POST',headers:{'Content-Type':'application/json'},body:first.options.body}),saved=await received.json();assert.equal(received.status,202,JSON.stringify(saved));
 const before=await b.send(['inspect']);h.fail(first,'TEST ONLY accepted reply lost');await h.flush();assert.match(node(h,'asset-execute').textContent,/確認・再送/);assert.equal(node(h,'asset-execute').disabled,false);
 h.click(node(h,'asset-execute'));const retry=pending(h,'/asset-plans','POST');assert.equal(retry.options.body,first.options.body);const response=await respond(retry);assert.equal(response.status,200,JSON.stringify(response.data));assert.equal(response.data.duplicate,true);assert.deepEqual(response.data.scope,saved.scope);assert.deepEqual((await b.send(['inspect'])).counts,before.counts);
 const result=await b.send(['drain']);await respond(pending(h,b.api));assert.equal(result.tasks.length,1);assert.equal(result.outputs.length,1);assert.equal(result.outputs[0].rows.length,3);
});
test('real single-conversation researcher record cannot supply group participant identity',async t=>{
 const f=await setup(t),{h,b,load}=f;await load();h.change(node(h,'asset-method'),'unit_projection');
 const first=h.evaluate('orchestrationAssetState.choices.findIndex(c=>c.input.enabled&&c.input.compatible_methods.includes("unit_projection")&&c.source.type==="frozen")');assert(first>=0);h.click(node(h,`asset-choice-${first}`));
 for(const check of node(h,'asset-parameters').querySelectorAll('input'))if(!check.checked)h.click(check);h.click(node(h,'asset-add'));await execute(f);h.click(node(h,'asset-clear'));await load();
 const single=await saveMapping(f,1);assert.deepEqual(JSON.parse(single.request.options.body).record.scope.conversation_ids,['C1']);
 await load();h.change(node(h,'asset-method'),'unit_pool');
 const pair=h.evaluate('["C1","C2"].map(cid=>orchestrationAssetState.choices.findIndex(c=>c.input.scope.conversation_ids[0]===cid&&c.source.asset_key.output_name==="tables/correlations.json"))');assert(pair.every(i=>i>=0));for(const i of pair)h.click(node(h,`asset-choice-${i}`));
 h.click(node(h,'asset-parameters').querySelector('input[name="asset-columns"][value="n"]'));h.click(node(h,'asset-add'));const pool=await execute(f);h.click(node(h,'asset-clear'));
 const page=await load(),group=page.inputs.find(i=>i.source.asset_key?.store_run_id===pool.result.outputs.at(-1).store_run_id);assert(group);assert.equal(group.confirmed_participant_mapping,null);
 assert.equal((await b.send(['inspect'])).human_count,1);
});
test('Edge 1440/390: ordinary pool and explicit mapping use live API, keyboard focus and saved fresh mean', {skip:process.env.GURUMOJI_RUN_UI_BROWSER!=='1'},async t=>{
 const {chromium}=require(process.env.GURUMOJI_PLAYWRIGHT_MODULE||'playwright'),browser=await chromium.launch({channel:'msedge',headless:true});t.after(()=>browser.close());
 for(const width of [1440,390]){
  const b=await bridge(t),context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage(),errors=[],blocked=[],posts=[];t.after(()=>context.close());
  await context.route('**/*',route=>new URL(route.request().url()).origin===b.base?route.continue():(blocked.push(route.request().url()),route.abort()));page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts.push({url:r.url(),body:r.postDataJSON()});});
  await page.addInitScript("sessionStorage.setItem('gurumoji.bootSplashSeen','1')");await page.goto(b.base);await page.waitForFunction('typeof orchestrationAdopt==="function"');
  await page.evaluate(run=>{orchestrationAdopt(run,'C1');orchestrationNode('live').showModal();},b.run);
  const load=async()=>{const response=page.waitForResponse(r=>r.url()===b.base+b.api+'/asset-plans/options?offset=0'&&r.request().method()==='GET');await page.locator('#orchestration-asset-load').click();assert.equal((await response).status(),200);await page.waitForFunction('orchestrationAssetState.options!==null&&!orchestrationAssetState.loading');await page.locator('#orchestration-asset-form').waitFor({state:'visible'});};
  await load();await page.getByLabel('保存根拠の処理方式',{exact:true}).selectOption('unit_pool');
  const checks=page.locator('#orchestration-asset-inputs input[data-choice]');assert.equal(await checks.count(),2);for(let i=0;i<2;i++)await checks.nth(i).check();
  await page.locator('input[name="asset-columns"][value="n"]').check();await page.locator('#orchestration-asset-add').click();
  const execute=async()=>{await page.locator('#orchestration-asset-review').focus();await page.keyboard.press('Enter');await page.waitForFunction('document.activeElement===orchestrationNode("asset-execute")');const response=page.waitForResponse(r=>r.url()===b.base+b.api+'/asset-plans'&&r.request().method()==='POST');await page.keyboard.press('Enter');assert.equal((await response).status(),202);return b.send(['drain']);};
  const pooled=await execute();assert.deepEqual(Object.keys(posts[0].body).sort(),['columns','plan_id','plan_version','source_ids','version']);
  await page.locator('#orchestration-asset-clear').click();await load();await page.locator('#orchestration-participant summary').first().click();
  assert.equal(await page.locator('#orchestration-participant-form').isVisible(),false);
  const selector=page.getByLabel('参加者対応を記録する固定対象',{exact:true}),target=await selector.locator('option').filter({hasText:'C1 / C2'}).getAttribute('value');assert(target);await selector.selectOption(target);
  await page.locator('#orchestration-participant-target summary').click();assert(await page.locator('#orchestration-participant-target-meta').evaluate(n=>n.scrollWidth<=n.clientWidth+1));
  const assignments=page.locator('#orchestration-participant-assignments input');for(let i=0;i<await assignments.count();i++)await assignments.nth(i).fill(await assignments.nth(i).getAttribute('data-speaker')==='silent'?'TEST-silent-person':'TEST-explicit-person');
  await page.getByLabel('参加者対応の記録者',{exact:true}).fill('TEST-browser-researcher');await page.getByLabel('対応の判断',{exact:true}).selectOption('adopt');await page.getByLabel('対応を判断した理由',{exact:true}).fill('TEST ONLY 明示的な同一人物対応');
  await page.getByLabel('対応を判断した理由',{exact:true}).focus();await page.keyboard.press('Tab');assert(await page.locator('#orchestration-participant-review').evaluate(n=>n===document.activeElement));await page.keyboard.press('Enter');await page.waitForFunction('document.activeElement===orchestrationNode("participant-save")');
  assert(await page.locator('#orchestration-participant-form').evaluate(n=>n.getBoundingClientRect().width<=window.innerWidth));assert(await selector.evaluate(n=>n.labels.length>0&&getComputedStyle(n).maxWidth==='100%'));
  const hc=page.waitForResponse(r=>r.url().endsWith('/human-records')&&r.request().method()==='POST');await page.keyboard.press('Enter');assert.equal((await hc).status(),201);await page.getByText(/対応表を研究者の原文記録として保存しました/).waitFor();
  await load();await page.getByLabel('保存根拠の処理方式',{exact:true}).selectOption('unit_aggregate');
  const index=await page.evaluate(id=>orchestrationAssetState.choices.findIndex(c=>c.input.confirmed_participant_mapping&&c.source.asset_key?.store_run_id===id),pooled.outputs[0].store_run_id);assert(index>=0);await page.locator(`#orchestration-asset-choice-${index}`).check();
  await page.getByLabel('集約方法',{exact:true}).selectOption('mean');await page.getByLabel('集約する宣言済み列',{exact:true}).selectOption('n');await page.getByLabel('集約の単位',{exact:true}).selectOption('participant');await page.locator('#orchestration-asset-add').click();
  const saved=await execute(),output=saved.outputs.at(-1);assert.equal(output.rows[0].value,2);assert.equal(Object.values(output.contract.denominators)[0].observed,3);assert.equal(saved.native_unchanged,true);assert.equal(saved.human_count,1);
  assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);assert.equal(posts.length,3);await context.close();
 }
});
async function selections(t,count=2){
 const h=await createHarness();t.after(()=>h.close());
 h.fixture(Array.from({length:count},(_,i)=>({option_id:`source-${i}`,enabled:true,scope:{conversation_ids:[`TEST-${i}`]},compatible_methods:['unit_pool'],source:{type:'frozen',asset_key:{library_id:'TEST',store_run_id:`saved-${i}`,artifact_id:`artifact-${i}`,output_name:'tables/table.json'}}})));
 h.evaluate('window.poolOptions={unit_pool:{enabled:true,sources:window.fixture}};window.poolSelected=window.fixture.map(input=>({input,source:input.source,role:"data_input",omitted:false}))');
 return h;
}
test('2 and 16 exact current Store source options can be selected',async t=>{
 for(const count of [2,16]){const h=await selections(t,count);assert.equal(h.evaluate('orchestrationPoolSelection(window.poolSelected,window.poolOptions).length'),count);assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);}
});
test('fewer than 2 and more than 16 sources are rejected without POST',async t=>{
 for(const count of [0,1,17]){const h=await selections(t,count);assert.throws(()=>h.evaluate('orchestrationPoolSelection(window.poolSelected,window.poolOptions)'),/2〜16/);assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);}
});
test('duplicate option and duplicate stored source are rejected',async t=>{
 const h=await selections(t);
 h.evaluate('window.poolSelected[1]=window.poolSelected[0]');assert.throws(()=>h.evaluate('orchestrationPoolSelection(window.poolSelected,window.poolOptions)'),/重複/);
 h.evaluate('window.poolSelected=window.poolOptions.unit_pool.sources.map(input=>({input,source:window.poolOptions.unit_pool.sources[0].source,role:"data_input"}))');assert.throws(()=>h.evaluate('orchestrationPoolSelection(window.poolSelected,window.poolOptions)'),/重複/);
 h.evaluate('window.poolSelected[1].source={type:"frozen",asset_key:Object.fromEntries(Object.entries(window.poolSelected[0].source.asset_key).reverse())}');assert.throws(()=>h.evaluate('orchestrationPoolSelection(window.poolSelected,window.poolOptions)'),/重複/);
});
test('disabled, stale-catalogue and unsaved references cannot be pooled',async t=>{
 const h=await selections(t);
 for(const mutation of ['window.poolSelected[0].input.enabled=false','window.poolOptions.unit_pool.sources=[]','window.poolSelected[0].source={type:"from_step",step_id:"future"}','window.poolSelected[0].role="evidence_context"']){
  h.evaluate('window.poolOptions.unit_pool.sources=window.fixture;window.poolSelected=window.fixture.map(input=>({input,source:input.source,role:"data_input"}));window.poolSelected[0].input.enabled=true');h.evaluate(mutation);
  assert.throws(()=>h.evaluate('orchestrationPoolSelection(window.poolSelected,window.poolOptions)'),/再取得/);
 }
});
test('a group mapping needs the exact group scope and server speaker pairs; single HC never expands',async t=>{
 const h=await selections(t);h.fixture({scope:{conversation_ids:['TEST-A','TEST-B']},speakers:[{conversation_id:'TEST-A',speaker_id:'S'},{conversation_id:'TEST-B',speaker_id:'S'}]});
 h.evaluate('window.mappingContext=window.fixture;window.mappingOption={scope:window.fixture.scope,speakers:window.fixture.speakers}');
 assert.equal(h.evaluate('orchestrationParticipantScopeValid(window.mappingContext,window.mappingOption)'),true);
 for(const mutation of ['window.mappingOption.scope={conversation_ids:["TEST-A"]}','delete window.mappingOption.speakers','window.mappingContext.speakers=window.fixture.speakers.slice(0,1)']){
  h.evaluate('window.mappingContext={scope:window.fixture.scope,speakers:window.fixture.speakers};window.mappingOption={scope:window.fixture.scope,speakers:window.fixture.speakers}');h.evaluate(mutation);
  assert.equal(h.evaluate('orchestrationParticipantScopeValid(window.mappingContext,window.mappingOption)'),false);
 }
});
test('two versions of one conversation cannot masquerade as two conversation sources',async t=>{
 const h=await selections(t);h.evaluate('window.poolSelected[1].input.scope=window.poolSelected[0].input.scope');assert.throws(()=>h.evaluate('orchestrationPoolSelection(window.poolSelected,window.poolOptions)'),/異なる会話/);
});
test('catalogue size and normal enabled cannot grant the pool permission',async t=>{
 const h=await selections(t);h.evaluate('window.poolOptions.enabled=true;window.poolOptions.unit_pool.enabled=false');assert.throws(()=>h.evaluate('orchestrationPoolSelection(window.poolSelected,window.poolOptions)'),/利用許可/);
 h.evaluate('delete window.poolOptions.unit_pool.enabled');assert.throws(()=>h.evaluate('orchestrationPoolSelection(window.poolSelected,window.poolOptions)'),/利用許可/);
});
test('compact discovery metadata is readable without inventing the full group scope',async t=>{
 const h=await selections(t),hash='sha256:'+'a'.repeat(64),fields=['unit_id','conversation_id','speaker_id','value_status','n'];
 h.fixture({version:'unit-pool-request-1',enabled:true,reason_code:null,min_sources:2,max_sources:16,request_template:{version:'unit-pool-request-1',plan_id:'TEST-plan',plan_version:1},parameter_fields:['columns'],required_columns:fields.slice(0,4),sources:[0,1].map(i=>({metadata_version:'pool-source-option-1',option_id:`TEST-${i}`,input_ref_id:`TEST-${i}`,label:`TEST conversation ${i}`,source:{type:'frozen',asset_key:{library_id:'TEST'},content_hash:hash},scope:{mode:'dataset',scope_id:`TEST-scope-${i}`,manifest_hash:hash,conversation_ids:[`TEST-${i}`]},fields,variables:fields.map(variable_id=>({variable_id,version:1,definition_hash:hash,value_type:'string',scale:'nominal',unit:'utterance',validity:'structural_checked'})),speakers:[{conversation_id:`TEST-${i}`,speaker_id:'TEST-S'}]}))});
 assert.equal(h.evaluate('orchestrationPoolOptionsValid(window.fixture,"TEST")'),true);assert.equal(h.evaluate('Object.hasOwn(window.fixture.sources[0].scope,"member_ids")'),false);
 h.evaluate('window.fixture.enabled=false;window.fixture.reason_code="pool_sources_insufficient"');assert.equal(h.evaluate('orchestrationPoolOptionsValid(window.fixture,"TEST")'),true);
 h.evaluate('delete window.fixture.sources[0].metadata_version');assert.equal(h.evaluate('orchestrationPoolOptionsValid(window.fixture,"TEST")'),false);
});
