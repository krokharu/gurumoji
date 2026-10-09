'use strict';
// Trusted real templates/scripts; every API response is synthetic. No AI calls.
const test=require('node:test');
const assert=require('node:assert/strict');
const {createHarness}=require('./harness.cjs');
const node=(h,id)=>h.document.getElementById(`orchestration-${id}`);
const pending=(h,suffix,method='GET')=>{const request=h.requests.findLast(r=>!r.settled&&r.url.endsWith(suffix)&&(r.options.method||'GET')===method);assert(request,`${method} ${suffix}`);return request;};
const plain=value=>JSON.parse(JSON.stringify(value));

test('Obsidian management is a separate new-run default, with honest legacy state',async t=>{
 const h=await setup(t);
 assert.equal(node(h,'memory-enabled').checked,true);
 assert.equal(h.evaluate('orchestrationPayload().obsidian_management'),true);
 assert.deepEqual(plain(h.evaluate('orchestrationPayload().publication_targets')),[]);
 h.click('#orchestration-memory-enabled');
 assert.equal(h.evaluate('orchestrationPayload().obsidian_management'),false);
 await started(h,snapshot());
 assert.match(node(h,'memory-status').textContent,/無効/);
 assert.equal(node(h,'memory-note').hidden,true);
 assert.equal(node(h,'memory-retry').hidden,true);
 assert.match(h.document.querySelector('[data-role="obsidian_manager"]').textContent,/CODE/);
 assert.doesNotMatch(h.document.querySelector('[data-role="obsidian_manager"]').textContent,/割当 0/);
});

test('management links are local generated routes and display text cannot inject HTML',async t=>{
 const h=await setup(t);
 await started(h,snapshot({obsidian_management:{enabled:true,status:'linked',note_id:'<img src=x onerror=alert(1)>',note_path:'javascript:alert(1)'}}));
 assert.equal(node(h,'memory-note').getAttribute('href'),'/api/library/A/analysis/orchestration/R1/memory/note');
 assert.equal(node(h,'memory-note').hidden,false);
 assert.equal(node(h,'memory-location').querySelector('img'),null);
 assert.equal(node(h,'memory-retry').hidden,true);
 assert.match(node(h,'memory-status').textContent,/参照を保存済み/);
 assert.equal(posts(h).length,1);
});

test('management retry sends an empty body once and never resumes analysis',async t=>{
 const h=await setup(t),run=snapshot({status:'cancelled',allowed_actions:[],obsidian_management:{enabled:true,status:'edited',note_id:'memory-R1'}});
 await started(h,run);
 assert.match(node(h,'memory-warning').textContent,/履歴/);
 h.click('#orchestration-memory-retry');h.click('#orchestration-memory-retry');
 const request=pending(h,'/R1/memory/retry','POST');
 assert.deepEqual(JSON.parse(request.options.body),{});
 assert.equal(posts(h).length,2);
 h.reply(request,{run:{...run,obsidian_management:{enabled:true,status:'linked',note_id:'memory-R1'}}});await h.flush();
 assert.equal(node(h,'memory-retry').hidden,true);
 assert.equal(h.requests.filter(r=>r.url.endsWith('/resume')).length,0);
});
function input(h,id,value){node(h,id).value=value;node(h,id).dispatchEvent(new h.w.Event('input',{bubbles:true}));}
function snapshot(overrides={}) {
 return {run_id:'R1',item_id:'A',status:'running',phase:'specialists',iteration:1,source_revision:2,
  config:{question:'Synthetic research question',provider:'lmstudio',model:'local-test',provider_policy:'local_only',stop_mode:'iterations',max_iterations:3,max_calls:24,max_tasks:48},
  usage:{calls:2,total_tokens:null,measured_calls:0,measurement_status:'unavailable'},allowed_actions:['cancel'],
  roles:[{id:'core',kind:'ai',status:'idle',provider:'lmstudio',model:'local-test',assigned:1,completed:1,failed:0},{id:'handler',kind:'code',status:'running',assigned:3,completed:1,failed:0}],
  tasks:[{task_id:'T1',role:'interpretation',title:'Check evidence',status:overrides.status==='completed'?'succeeded':['cancelled','stopped','failed'].includes(overrides.status)?'cancelled':'running',model:'local-test'},{task_id:'T2',role:'statistics',title:'Count turns',status:'succeeded'}],
  events:[{seq:1,type:'task_started',from:'handler',to:'interpretation',message:'Synthetic task registered'}],results:[],...overrides};
}
async function setup(t) {
 const h=await createHarness();t.after(()=>h.close());
 h.fixture({itemId:'A',data:{item:{id:'A',source_name:'Synthetic A',revision_count:2,analysis_revision:3},segments:[]},config:{},annotations:{},dirty:false});
 h.evaluate('Object.assign(analysisState,window.fixture);analysisCard.hidden=false;document.body.dataset.view="analysis"');
 h.click('#analysis-run-settings-button');h.click('#orchestration-open');input(h,'question','Synthetic research question');
 return h;
}
async function started(h,run=snapshot()) {
 h.click('#orchestration-start');const request=pending(h,'/analysis/orchestration','POST');h.reply(request,{run});await h.flush();return request;
}
function posts(h){return h.requests.filter(r=>r.options.method==='POST');}
function publication(overrides={}) {
 return {save_status:'saved',publication_status:'incomplete',publication_targets:['input','orchestrator','visualization'],effective_writers:['research','input','orchestrator','visualization'],
  result_run_id:'fixed-R1',result_run:{id:'fixed-R1',artifacts:[{name:'result.json',url:'/api/analysis/artifacts/fixed-artifact-1'}]},can_retry:true,
  outcomes:{input:{status:'published'},orchestrator:{status:'failed',error:'Synthetic write failure'},visualization:{status:'unknown'},research:{status:'conflict',error:'Synthetic note conflict'}},...overrides};
}
function initialRun(overrides={}) {
 return snapshot({phase:'initial',iteration:0,tasks:[],results:[],usage:{calls:0,total_tokens:null,measurement_status:'unavailable'},
  initial:{status:'building',completed_stages:1,total_stages:3},
  initial_stages:[{stage_id:'base',label:'入力整理',status:'completed',attempt_count:1,output_hash:'synthetic-hash',completed_at:'2026-10-04T00:00:00Z'},
   {stage_id:'linguistics',label:'言語情報',status:'running',attempt_count:2},{stage_id:'statistics',label:'数量集計',status:'pending',attempt_count:0}],...overrides});
}
test('autonomous settings are opt-in, local by default; explicit flat stop contract',async t=>{
 const h=await setup(t);assert.equal(node(h,'settings').open,true);assert.equal(h.document.querySelector('#analysis-run-dialog').open,false);
 let payload=plain(h.evaluate('orchestrationPayload()'));assert.equal(payload.provider_policy,'local_only');assert.equal(payload.cloud_consent,false);assert.equal(payload.max_calls,24);assert.equal(payload.max_tasks,48);assert.equal(payload.stop_mode,'auto');assert.equal(payload.max_iterations,null);assert.equal(payload.time_limit_seconds,null);assert.match(node(h,'stop-explanation').textContent,/最低3回/);
 h.click('input[name="orchestration_stop"][value="auto"]');input(h,'iterations','');input(h,'time','');payload=plain(h.evaluate('orchestrationPayload()'));assert.equal(payload.max_iterations,null);assert.equal(payload.time_limit_seconds,null);
 input(h,'iterations','2');assert.throws(()=>h.evaluate('orchestrationPayload()'),/最低3回/);input(h,'iterations','');
 h.click('input[name="orchestration_stop"][value="iterations"]');input(h,'iterations','1');assert.equal(h.evaluate('orchestrationPayload().max_iterations'),1);
 h.click('input[name="orchestration_stop"][value="time"]');assert.throws(()=>h.evaluate('orchestrationPayload()'),/時間上限/);input(h,'time','2');payload=plain(h.evaluate('orchestrationPayload()'));assert.equal(payload.time_limit_seconds,120);
 h.click('input[name="orchestration_stop"][value="importance"]');assert.equal(h.evaluate('orchestrationPayload().importance_threshold'),'medium');assert.match(node(h,'stop-explanation').textContent,/未校正/);assert.equal(posts(h).length,0);
});
test('cloud overrides require source-data consent and reset it when recipient changes',async t=>{
 const h=await setup(t);input(h,'provider-critic','openai');assert.equal(node(h,'cloud-disclosure').hidden,false);assert.match(node(h,'cloud-targets').textContent,/OpenAI/);assert.throws(()=>h.evaluate('orchestrationPayload()'),/同意/);
 h.click('#orchestration-cloud-consent');const p=plain(h.evaluate('orchestrationPayload()'));assert.equal(p.cloud_consent,true);assert.equal(p.provider_policy,'cloud_allowed');assert.equal(p.roles.critic.provider,'openai');
 input(h,'provider-critic','google');assert.equal(node(h,'cloud-consent').checked,false);assert.throws(()=>h.evaluate('orchestrationPayload()'),/同意/);assert.equal(posts(h).length,0);
});
test('start, rendering and reopening never add AI work; code roles and unknown usage are honest',async t=>{
 const h=await setup(t);const request=await started(h);const payload=JSON.parse(request.options.body);assert.equal(payload.source_revision,2);assert.equal(payload.analysis_revision,3);assert.equal(node(h,'live').open,true);
 assert.match(node(h,'metrics').textContent,/未計測/);assert.match(node(h,'role-handler').textContent,/CODE/);assert.match(node(h,'role-handler').textContent,/LLM呼出しなし/);assert.match(node(h,'specialists').textContent,/Python集計/);
 h.evaluate('renderAnalysisOrchestration();renderAnalysisOrchestration()');assert.equal(posts(h).length,1);
 h.click('#orchestration-live-close');assert.equal(node(h,'live').open,false);assert.equal(h.evaluate('orchestrationState.run.status'),'running');
 h.click('#orchestration-chip');assert.equal(node(h,'live').open,true);h.reply(pending(h,'/orchestration/R1'),{run:snapshot()});await h.flush();assert.equal(posts(h).length,1);
 assert.equal(node(h,'export-json').getAttribute('href'),'/api/library/A/analysis/orchestration/R1/export.json');
});
test('late status cannot undo a stop; snapshot ownership survives navigation without reopening',async t=>{
 const h=await setup(t);await started(h);h.click('#orchestration-refresh');const late=pending(h,'/orchestration/R1');h.click('#orchestration-stop');const stop=pending(h,'/R1/cancel','POST');
 h.reply(stop,{run:snapshot({status:'cancelled',phase:'stopped',stop_reason:'user_stop',allowed_actions:[]})});await h.flush();h.reply(late,{run:snapshot()});await h.flush();assert.equal(h.evaluate('orchestrationState.run.status'),'cancelled');assert.equal(node(h,'stop').hidden,true);
 h.click('#show-library-button');assert.equal(node(h,'live').open,false);assert.equal(h.w.location.hash,'#/data');h.evaluate('void pollAnalysisOrchestration()');h.reply(pending(h,'/orchestration/R1'),{run:snapshot({status:'cancelled',allowed_actions:[]})});await h.flush();assert.equal(node(h,'live').open,false);assert.equal(h.document.body.dataset.view,'library');
});
test('server-approved manual resume and recovery blockers are distinct from completion',async t=>{
 const h=await setup(t);await started(h,snapshot({status:'recovery_required',allowed_actions:['resume'],error:'Interrupted worker'}));assert.equal(node(h,'resume').hidden,false);assert.match(node(h,'status').textContent,/手動復旧待ち/);
 h.click('#orchestration-resume');h.reply(pending(h,'/R1/resume','POST'),{run:snapshot()});await h.flush();assert.equal(node(h,'resume').hidden,true);assert.equal(h.evaluate('orchestrationState.run.status'),'running');
});
test('result request latest-wins and closing prevents late private content publication',async t=>{
 const h=await setup(t);await started(h);h.evaluate('void orchestrationReadResults("result-a")');const a=pending(h,'/results/result-a');h.evaluate('void orchestrationReadResults("result-b")');const b=pending(h,'/results/result-b');
 h.reply(b,{metadata:{result_id:'result-b'},raw:{summary:'NEWEST SYNTHETIC'}});await h.flush();h.reply(a,{metadata:{result_id:'result-a'},raw:{summary:'OLDER SYNTHETIC'}});await h.flush();assert.match(node(h,'result-content').textContent,/NEWEST SYNTHETIC/);assert.doesNotMatch(node(h,'result-content').textContent,/OLDER SYNTHETIC/);
 h.click('#orchestration-results');const all=pending(h,'/R1/results');h.click('#orchestration-live-close');h.reply(all,{initial:{snapshot:{private:'LATE SYNTHETIC'}}});await h.flush();assert.doesNotMatch(node(h,'result-content').textContent,/LATE SYNTHETIC/);
});
test('ambiguous start reuses request identity and refuses changed-payload duplicate',async t=>{
 const h=await setup(t);h.click('#orchestration-start');const first=pending(h,'/analysis/orchestration','POST');h.fail(first);await h.flush();assert.match(node(h,'settings-message').textContent,/受付状態は未確定/);
 input(h,'question','Changed question');h.click('#orchestration-start');assert.equal(posts(h).length,1);assert.match(node(h,'settings-message').textContent,/設定を変更して再送せず/);
 input(h,'question','Synthetic research question');h.click('#orchestration-start');const second=pending(h,'/analysis/orchestration','POST');assert.equal(JSON.parse(second.options.body).request_id,JSON.parse(first.options.body).request_id);h.reply(second,{run:snapshot()});await h.flush();
});
test('persisted evidence, critique disposition and model text are safely rendered',async t=>{
 const h=await setup(t);await started(h,snapshot({usage:{calls:3,total_tokens:51,measured_calls:1,measurement_status:'reported'},current_view:{summary:'Synthetic synthesis'},
  issues:[{severity:'high',reason:'Contradictory evidence',evidence_ids:['s1']}],critique_responses:[{disposition:'defer',reason:'Need another sample',impact:'Conclusion limited'}],
  tasks:[{task_id:'T1',role:'interpretation',title:'<img src=x onerror=alert(1)>',model:'<svg onload=alert(1)>',status:'succeeded'}],results:[{result_id:'result-1',task_id:'T1'}]}));
 assert.match(node(h,'metrics').textContent,/一部計測/);assert.match(node(h,'review-content').textContent,/Need another sample/);assert.match(node(h,'review-content').textContent,/s1/);assert.equal(node(h,'tasks').querySelectorAll('img,svg').length,0);assert.equal(node(h,'tasks').querySelectorAll('button').length,1);
 h.click('#orchestration-reduced-motion');assert.equal(node(h,'live').classList.contains('reduce-motion'),true);
});
test('late start remains bound to its original item and does not reopen after navigation',async t=>{
 const h=await setup(t);h.click('#orchestration-start');const start=pending(h,'/analysis/orchestration','POST');h.click('#show-library-button');assert.equal(node(h,'settings').open,false);
 h.reply(start,{run:snapshot()});await h.flush();assert.equal(h.evaluate('orchestrationState.itemId'),'A');assert.equal(node(h,'live').open,false);assert.equal(h.document.body.dataset.view,'library');assert.equal(node(h,'chip').hidden,false);
});
test('unchanged polls preserve focused result controls; uncertain work blocks normal resume',async t=>{
 const h=await setup(t),run=snapshot({status:'recovery_required',error:'Unknown external outcome',uncertain_tasks:['T1'],allowed_actions:['cancel'],results:[{task_id:'T2',result_id:'R2'}]});await started(h,run);
 assert.equal(node(h,'resume').hidden,true);assert.match(node(h,'live-message').textContent,/二重実行/);const button=node(h,'tasks').querySelector('button');button.focus();h.evaluate('renderAnalysisOrchestration()');assert.equal(h.document.activeElement,button);
});
test('unknown calls require individual selection and confirmation before explicit abandon',async t=>{
 const h=await setup(t);await started(h,snapshot({status:'recovery_required',allowed_actions:['cancel'],uncertain_tasks:['T1','T2']}));
 assert.equal(node(h,'recovery').hidden,false);assert.equal(node(h,'abandon').disabled,true);assert.equal(posts(h).length,1);
 h.click('#orchestration-recovery-tasks input[value="T1"]');assert.equal(node(h,'abandon').disabled,false);h.w.confirm=()=>false;h.click('#orchestration-abandon');assert.equal(posts(h).length,1);
 let confirmation='';h.w.confirm=text=>{confirmation=text;return true;};h.click('#orchestration-abandon');const request=pending(h,'/R1/resume','POST');assert.deepEqual(JSON.parse(request.options.body),{recovery:{T1:'abandon'}});assert.match(confirmation,/費用は不明/);assert.match(confirmation,/再送もしません/);
 h.reply(request,{run:snapshot({status:'recovery_required',allowed_actions:['cancel'],uncertain_tasks:['T2']})});await h.flush();assert.equal(node(h,'recovery-tasks').querySelectorAll('input').length,1);assert.equal(node(h,'abandon').disabled,true);assert.equal(node(h,'resume').hidden,true);
});
test('four Vault output is one explicit new-run choice, default off and reset for the next opening',async t=>{
 const h=await setup(t);assert.equal(node(h,'publication-all').checked,false);assert.deepEqual(plain(h.evaluate('orchestrationPayload().publication_targets')),[]);
 assert.equal(h.document.querySelectorAll('.orchestration-output-settings input[type="checkbox"]').length,1);
 for(const text of ['Input','Orchestrator','Visualization','Research','発話本文','手動編集','履歴','削除済み'])assert.match(node(h,'publication-disclosure').textContent,new RegExp(text));
 h.click('#orchestration-publication-all');const start=await started(h,snapshot({status:'completed',allowed_actions:[],publication:publication()}));
 assert.deepEqual(JSON.parse(start.options.body).publication_targets,['input','orchestrator','visualization']);
 h.click('#orchestration-live-close');h.evaluate('openAnalysisOrchestrationSettings()');assert.equal(node(h,'publication-all').checked,false);assert.deepEqual(plain(h.evaluate('orchestrationPayload().publication_targets')),[]);
 assert.equal(posts(h).length,1);
});
test('old run without output fields stays off on read, render, reopen and resume',async t=>{
 const h=await setup(t);await started(h,snapshot({status:'recovery_required',allowed_actions:['resume']}));
 assert.match(node(h,'publication-status').textContent,/OFF/);assert.equal(node(h,'publication-retry').hidden,true);assert.equal(node(h,'output-artifacts').children.length,0);
 h.click('#orchestration-publication-all');h.evaluate('renderAnalysisOrchestration();renderAnalysisOrchestration()');
 h.click('#orchestration-live-close');h.click('#orchestration-chip');h.reply(pending(h,'/orchestration/R1'),{run:snapshot({status:'recovery_required',allowed_actions:['resume']})});await h.flush();assert.equal(posts(h).length,1);
 h.click('#orchestration-resume');const request=pending(h,'/R1/resume','POST');assert.deepEqual(JSON.parse(request.options.body),{});
 h.reply(request,{run:snapshot()});await h.flush();assert.match(node(h,'publication-status').textContent,/OFF/);assert.equal(posts(h).length,2);
});
test('saved output, four writer outcomes and server artifact URLs remain distinct from analysis completion',async t=>{
 const h=await setup(t),run=snapshot({status:'completed',allowed_actions:[],publication:publication({result_run:{artifacts:[
  {name:'全量 result.json',url:'/api/analysis/artifacts/fixed-artifact-1?version=saved'},
  {name:'invalid URL',url:'javascript:alert(1)'},{name:'local path only',path:'/private/never-link.json'}],vault_notes:{missing:[{vault:'research',path:'synthetic-deleted-note'}]}}})});
 await started(h,run);assert.match(node(h,'status').textContent,/処理終了/);assert.match(node(h,'save-status').textContent,/保存済み/);assert.match(node(h,'publication-status').textContent,/一部未完了/);
 const outcomes=node(h,'publication-outcomes');assert.equal(outcomes.children.length,4);for(const status of ['published','failed','unknown','conflict'])assert(outcomes.querySelector(`[data-status="${status}"]`));
 assert.match(outcomes.textContent,/Synthetic note conflict/);assert.match(node(h,'publication-retry-note').textContent,/4つの保存先を再訪/);assert.match(node(h,'publication-retry-note').textContent,/AI・統計の再計算は行いません/);
 assert.equal(node(h,'publication-note-policy').hidden,false);assert.match(node(h,'publication-note-policy').textContent,/全ノートの存在を保証するものではありません/);
 const link=node(h,'output-artifacts').querySelector('a');assert.equal(link.getAttribute('href'),'/api/analysis/artifacts/fixed-artifact-1?version=saved');assert.equal(node(h,'output-artifacts').querySelectorAll('a').length,1);
 link.focus();h.evaluate('renderAnalysisOrchestration()');assert.equal(h.document.activeElement,link);
 h.click('#orchestration-live-close');h.click('#orchestration-chip');h.reply(pending(h,'/orchestration/R1'),{run});await h.flush();assert.equal(posts(h).length,1);
});
test('publication retry is empty, double-click protected and bound to the saved item after editing context changes',async t=>{
 const h=await setup(t),run=snapshot({status:'completed',allowed_actions:[],publication:publication()});await started(h,run);
 h.click('#orchestration-refresh');const stale=pending(h,'/orchestration/R1');
 h.fixture({itemId:'B',data:{item:{id:'B',source_name:'Synthetic B',revision_count:7,analysis_revision:8}},config:{keep:'B draft'},dirty:true});h.evaluate('Object.assign(analysisState,window.fixture)');
 h.click('#orchestration-publication-retry');h.click('#orchestration-publication-retry');const request=pending(h,'/R1/publication/retry','POST');assert.equal(request.url,'/api/library/A/analysis/orchestration/R1/publication/retry');assert.deepEqual(JSON.parse(request.options.body),{});assert.equal(posts(h).length,2);assert.equal(node(h,'publication-retry').disabled,true);
 h.reply(request,{run:{...run,publication:publication({publication_status:'published',can_retry:false})}});await h.flush();h.reply(stale,{run});await h.flush();
 assert.equal(h.evaluate('orchestrationState.run.publication.publication_status'),'published');assert.equal(h.evaluate('analysisState.itemId'),'B');assert.equal(h.evaluate('analysisState.config.keep'),'B draft');assert.equal(node(h,'publication-retry').hidden,true);
});
test('publication response after route change cannot reopen the view or overwrite another run',async t=>{
 const h=await setup(t);await started(h,snapshot({status:'completed',allowed_actions:[],publication:publication()}));h.click('#orchestration-publication-retry');const old=pending(h,'/R1/publication/retry','POST');
 h.click('#show-library-button');assert.equal(node(h,'live').open,false);
 h.fixture(snapshot({run_id:'R2',item_id:'B',status:'completed',allowed_actions:[],publication:publication({result_run_id:'fixed-R2'})}));h.evaluate('orchestrationAdopt(window.fixture,"B")');
 assert.equal(h.evaluate('orchestrationState.operation'),'');h.reply(old,{run:snapshot({status:'completed',publication:publication({publication_status:'published'})})});await h.flush();
 assert.equal(h.evaluate('orchestrationState.runId'),'R2');assert.equal(h.evaluate('orchestrationState.run.publication.result_run_id'),'fixed-R2');assert.equal(node(h,'live').open,false);assert.equal(h.document.body.dataset.view,'library');assert.equal(posts(h).length,2);
});
test('uncertain publication retry only refreshes status, never automatically retries or recomputes',async t=>{
 const h=await setup(t),run=snapshot({status:'completed',allowed_actions:[],publication:publication()});await started(h,run);h.click('#orchestration-publication-retry');h.fail(pending(h,'/R1/publication/retry','POST'));await h.flush();
 assert.match(node(h,'live-message').textContent,/保存・出力の再試行の受付を確認できません/);assert.equal(posts(h).length,2);
 h.reply(pending(h,'/orchestration/R1'),{run});await h.flush();assert.equal(posts(h).length,2);assert.equal(node(h,'publication-retry').disabled,false);
});
test('fixed-save-only retry cannot gain Vault scope; failed or cancelled analysis cannot retry output',async t=>{
 const h=await setup(t),off=publication({save_status:'failed',publication_status:'not_selected',publication_targets:[],effective_writers:[],outcomes:{},result_run:null,result_run_id:''});
 await started(h,snapshot({status:'completed',allowed_actions:[],publication:off}));assert.equal(node(h,'publication-retry').textContent,'固定成果物の保存を再試行');h.click('#orchestration-publication-all');h.click('#orchestration-publication-retry');
 const request=pending(h,'/R1/publication/retry','POST');assert.deepEqual(JSON.parse(request.options.body),{});h.reply(request,{run:snapshot({status:'completed',allowed_actions:[],publication:{...off,save_status:'saved',can_retry:false}})});await h.flush();assert.match(node(h,'publication-status').textContent,/OFF/);
 for(const status of ['cancelled','stopped','failed']){h.fixture(snapshot({status,allowed_actions:[],publication:publication({publication_status:'pending'})}));h.evaluate('orchestrationAdopt(window.fixture,"A");void orchestrationAction("publication/retry")');assert.equal(node(h,'publication-retry').hidden,true);const timers=h.timers.length;h.evaluate('orchestrationSchedule()');assert.equal(h.timers.length,timers);}
 assert.equal(posts(h).length,2);
});
test('initial checkpoints show persisted code-only progress and keep saved details open on unchanged polls',async t=>{
 const h=await setup(t);await started(h,initialRun());assert.match(node(h,'status').textContent,/初期分析（コード処理）/);assert.equal(node(h,'initial').hidden,false);assert.match(node(h,'initial-summary').textContent,/1 \/ 3/);assert.match(node(h,'initial').textContent,/LLMを呼び出しません/);
 assert.equal(node(h,'initial-stages').children.length,3);assert.match(node(h,'initial-stages').textContent,/保存済み（再開時に再利用）/);assert.match(node(h,'initial-stages').textContent,/実行回数 2/);assert.doesNotMatch(node(h,'initial-stages').textContent,/local-test|トークン/);
 const details=node(h,'initial-stages').querySelector('details');details.open=true;h.evaluate('renderAnalysisOrchestration()');assert.equal(node(h,'initial-stages').querySelector('details'),details);assert.equal(details.open,true);assert.equal(posts(h).length,1);
});
test('initial recovery follows server resume and cancel permissions without altering saved scope',async t=>{
 const h=await setup(t),stages=initialRun().initial_stages;stages[1]={...stages[1],status:'failed',error:'<img src=x> Synthetic checkpoint failure'};
 await started(h,initialRun({status:'recovery_required',allowed_actions:['resume','cancel'],initial_stages:stages}));assert.equal(node(h,'resume').hidden,false);assert.equal(node(h,'stop').hidden,false);assert.equal(node(h,'initial-stages').querySelectorAll('img').length,0);assert.match(node(h,'initial-stages').textContent,/Synthetic checkpoint failure/);
 h.click('#orchestration-resume');const resume=pending(h,'/R1/resume','POST');assert.deepEqual(JSON.parse(resume.options.body),{});h.reply(resume,{run:initialRun()});await h.flush();assert.equal(node(h,'resume').hidden,true);
 h.click('#orchestration-stop');h.reply(pending(h,'/R1/cancel','POST'),{run:initialRun({status:'cancelled',allowed_actions:[]})});await h.flush();assert.equal(node(h,'stop').hidden,true);assert.equal(node(h,'publication-retry').hidden,true);assert.match(node(h,'initial-stages').textContent,/保存済み/);assert.equal(posts(h).length,3);
});
test('accepted initial run can close, reopen and cancel before its first stage completes',async t=>{
 const h=await setup(t),run=initialRun({status:'accepted',initial_stages:[],initial:{status:'building'},allowed_actions:['cancel']});await started(h,run);assert.equal(node(h,'stop').hidden,false);assert.match(node(h,'initial-summary').textContent,/確認しています/);
 h.click('#orchestration-live-close');h.click('#orchestration-chip');h.reply(pending(h,'/orchestration/R1'),{run});await h.flush();assert.equal(posts(h).length,1);
 h.click('#orchestration-stop');h.reply(pending(h,'/R1/cancel','POST'),{run:initialRun({status:'cancelled',allowed_actions:[]})});await h.flush();assert.equal(posts(h).length,2);
});
test('completed run keeps polling a pending publication without starting output from its viewer',async t=>{
 const h=await setup(t),run=snapshot({status:'completed',allowed_actions:[],publication:publication({publication_status:'publishing',can_retry:false})});await started(h,run);
 const timer=h.timers.findLast(timer=>timer.callback===h.evaluate('pollAnalysisOrchestration'));assert(timer);timer.callback();h.reply(pending(h,'/orchestration/R1'),{run:{...run,publication:{...run.publication,publication_status:'published'}}});await h.flush();assert.equal(posts(h).length,1);assert.match(node(h,'publication-status').textContent,/出力処理成功/);
});
test('initial recovery with unsafe checkpoint never offers a forbidden resume or invents success',async t=>{
 const h=await setup(t);await started(h,initialRun({status:'recovery_required',allowed_actions:['cancel'],error:'Synthetic checkpoint hash mismatch'}));
 assert.equal(node(h,'resume').hidden,true);assert.match(node(h,'initial-summary').textContent,/再開は許可されていません/);h.evaluate('void orchestrationAction("resume")');assert.equal(posts(h).length,1);
});
test('ambiguous opt-in start keeps the approved scope on reopen and rejects a changed scope',async t=>{
 const h=await setup(t);h.click('#orchestration-publication-all');h.click('#orchestration-start');const first=pending(h,'/analysis/orchestration','POST');h.fail(first);await h.flush();
 h.click('#orchestration-settings-close');h.evaluate('openAnalysisOrchestrationSettings()');assert.equal(node(h,'publication-all').checked,true);
 h.click('#orchestration-publication-all');h.click('#orchestration-start');assert.equal(posts(h).length,1);assert.match(node(h,'settings-message').textContent,/設定を変更して再送せず/);
 h.click('#orchestration-publication-all');h.click('#orchestration-start');const retry=pending(h,'/analysis/orchestration','POST');assert.equal(retry.options.body,first.options.body);h.reply(retry,{run:snapshot()});await h.flush();
});

test('cancelled initial run keeps read-only polling until its current code stage commits',async t=>{
 const h=await setup(t),run=initialRun({status:'cancelled',allowed_actions:[]});await started(h,run);
 assert.match(node(h,'status').textContent,/残処理の終了待ち/);assert.equal(h.evaluate('isAnalysisOrchestrationActive()'),true);
 const timer=h.timers.findLast(timer=>timer.callback===h.evaluate('pollAnalysisOrchestration'));assert(timer);timer.callback();
 const settled={...run,initial_stages:run.initial_stages.map(stage=>stage.status==='running'?{...stage,status:'completed'}:stage)};
 h.reply(pending(h,'/orchestration/R1'),{run:settled});await h.flush();assert.equal(h.evaluate('isAnalysisOrchestrationActive()'),false);
 const timers=h.timers.length;h.evaluate('orchestrationSchedule()');assert.equal(h.timers.length,timers);assert.equal(posts(h).length,1);
});
test('cancelled AI task polls for late usage while uncertain recovered tasks do not poll forever',async t=>{
 const h=await setup(t),run=snapshot({status:'cancelled',allowed_actions:[],tasks:[{task_id:'T1',role:'interpretation',status:'cancel_requested'}]});await started(h,run);
 assert.equal(h.evaluate('orchestrationPendingCompletion(orchestrationState.run)'),true);
 const timer=h.timers.findLast(timer=>timer.callback===h.evaluate('pollAnalysisOrchestration'));timer.callback();
 h.reply(pending(h,'/orchestration/R1'),{run:{...run,tasks:[{task_id:'T1',role:'interpretation',status:'quarantined'}],usage:{calls:1,total_tokens:15,measured_calls:1,measurement_status:'reported'}}});await h.flush();
 assert.match(node(h,'metrics').textContent,/15/);assert.equal(h.evaluate('orchestrationPendingCompletion(orchestrationState.run)'),false);
 h.fixture({...run,status:'recovery_required',tasks:[{task_id:'T1',role:'interpretation',status:'uncertain'}]});h.evaluate('orchestrationAdopt(window.fixture,"A")');
 const count=h.timers.length;h.evaluate('orchestrationSchedule()');assert.equal(h.timers.length,count);assert.equal(posts(h).length,1);
});
