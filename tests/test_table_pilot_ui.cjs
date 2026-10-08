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
 print(json.dumps(dict(options=t.options(),run=t.run,seed_projection=seed_projection)))
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
