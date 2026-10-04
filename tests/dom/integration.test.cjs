'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {createHarness}=require('./harness.cjs');
const stages=['outline','cleanup','name_extract','name_verify'];
const plain=value=>JSON.parse(JSON.stringify(value));
async function setup(t){const h=await createHarness();t.after(()=>h.close());return h;}
function job(id='A',text='Synthetic transcript') {return {id,source_name:`Synthetic ${id}`,revision_count:1,files:[],segments:[{id:'s1',speaker:'A',start:0,end:1,text},{id:'s2',speaker:'B',start:1,end:2,text:'Synthetic second'}],speaker_names:{},speaker_profiles:{A:{display_name:'Synthetic A',session_role:'participant',session_role_source:'default'},B:{display_name:'Synthetic B',session_role:'observer',session_role_source:'registry'}},session_profile:{session_type:'focus_group'}};}
function render(h,data=job()){h.fixture(data);h.evaluate('renderResult(window.fixture)');}
function latest(h,url,method='GET'){const request=h.requests.findLast(r=>r.url===url&&(r.options.method||'GET')===method);assert(request,`${method} ${url}`);return request;}
function unsafeMarkupAbsent(host){assert.equal(host.querySelector('script,iframe,object,embed,img,svg'),null);for(const node of host.querySelectorAll('*'))for(const attr of node.attributes){assert(!/^on/i.test(attr.name));if(['href','src','action'].includes(attr.name))assert(!/^\s*(javascript|data|vbscript):/i.test(attr.value));}}
function role(h,index=0){return h.document.querySelectorAll('.conversation-role-control')[index];}
function analysisPanel(h,item='A') {h.fixture({itemId:item,data:{item:{id:item,revision_count:1,analysis_revision:1},segments:[]}});h.evaluate('Object.assign(analysisState, window.fixture); document.querySelector("#analysis-card").append(buildAnalysisStorage()); refreshAnalysisStorage()');}
function fixed(run='r1',item='A',artifacts=[]){return {run:{id:run,item_id:item,kind:'milestone_analysis',status:'completed',created_at:'synthetic-date',source_revision:1,analysis_revision:1,artifacts},integrity:'verified',provenance:{},current_input:{stale:true}};}
function lookup(h,id){const form=h.document.querySelector('.analysis-fixed-lookup');form.querySelector('input').value=id;form.requestSubmit();}

test('real HTML and all scripts initialize offline with four uniquely labelled effort cards',async t=>{
 const h=await setup(t);assert.equal(h.document.querySelectorAll('.effort-card').length,4);
 const ids=[...h.document.querySelectorAll('[id]')].map(n=>n.id);assert.equal(new Set(ids).size,ids.length);
 for(const card of h.document.querySelectorAll('.effort-card')){assert.equal(card.closest('details').open,false);for(const element of card.querySelectorAll('[aria-describedby],label[for]'))for(const id of (element.getAttribute('aria-describedby')||element.htmlFor).split(' '))assert(h.document.getElementById(id));}
 assert.equal(h.evaluate('configLoadState'),'loaded');assert.equal(h.blocked.length,0);
});

test('real mode handler preserves four independent efforts and FormData across simple/detail/advanced/off transitions',async t=>{
 const h=await setup(t);h.change(h.document.querySelector('#ai-provider'),'openai');const expected={outline:'ultra',cleanup:'low',name_extract:'off',name_verify:'high'};
 for(const [key,value]of Object.entries(expected))h.change(h.document.querySelector(`#effort-select-${key}`),value);
 const assertValues=()=>{assert.deepEqual(plain(h.evaluate('readAiEfforts()')),expected);const data=new h.w.FormData(h.document.querySelector('#job-form'));for(const key of stages){assert.equal(data.get(`ai_effort_${key}`),expected[key]);assert.equal(h.document.querySelector(`#effort-select-${key}`).value,expected[key]);}};
 assertValues();h.click('#effort-detail-toggle');assertValues();h.click('#effort-detail-toggle');
 for(const value of ['advanced','off','recommended','advanced','recommended']){const mode=h.document.querySelector(`input[name="transcript_finishing_mode"][value="${value}"]`);h.click(mode);assertValues();assert.equal(mode.checked,true);}
 for(const key of stages){const on=h.document.querySelector(`[name="ai_thinking_mode_${key}"][value="on"]`);if(on)h.click(on);const radio=h.document.querySelector(`[name="ai_effort_choice_${key}"][value="medium"]`);h.click(radio);expected[key]='medium';assertValues();}
 h.evaluate('setRunning(true); setRunning(false)');assertValues();
 assert.equal(h.requests.filter(r=>r.options.method && r.options.method!=='GET').length,0);
});

test('real speaker editor confirms one role once without saving; DOM rerender remains unique',async t=>{
 const h=await setup(t);render(h);const other=plain(h.evaluate('currentJob.speaker_profiles.B'));const generation=h.evaluate('currentJobMutationGeneration');
 h.click(role(h).querySelector('button'));h.click(role(h).querySelector('button'));
 assert.equal(h.evaluate('currentJobMutationGeneration'),generation+1);assert.equal(h.evaluate('currentJobDirty'),true);assert.equal(h.evaluate('currentJob.speaker_profiles.A.session_role_source'),'explicit');assert.deepEqual(plain(h.evaluate('currentJob.speaker_profiles.B')),other);
 assert(role(h).textContent.includes('まだ保存されていません'));assert.equal(h.requests.filter(r=>r.options.method==='PUT').length,0);
 h.evaluate('renderSpeakerEditor(); renderSpeakerEditor()');assert.equal(h.document.querySelectorAll('#conversation-role-help').length,1);assert.equal(h.document.querySelectorAll('#conversation-role-status-0').length,1);
 const detached=role(h).querySelector('button');render(h,job('B'));detached.click();assert.equal(h.evaluate('currentJob.speaker_profiles.A.session_role_source'),'default');
});

for(const status of [200,409,500])test(`actual Save click preserves role ownership on ${status}`,async t=>{
 const h=await setup(t);render(h);h.click(role(h).querySelector('button'));h.click('#save-button');const request=latest(h,'/api/library/A','PUT');assert.equal(JSON.parse(request.options.body).speaker_profiles.A.session_role_source,'explicit');
 h.reply(request,status===200?{...job(),speaker_profiles:{...job().speaker_profiles,A:{...job().speaker_profiles.A,session_role_source:'explicit'}},revision_count:2}:{error:'synthetic failure',current_revision:2},status);await h.flush();assert.equal(h.evaluate('currentJobDirty'),status!==200);assert.equal(h.document.querySelector('#save-button').disabled,false);if(status===409)assert.equal(h.document.querySelector('#result-draft-recovery').hidden,false);
});

test('late Save response cannot erase newer local role change',async t=>{
 const h=await setup(t);render(h);h.click('#save-button');const request=latest(h,'/api/library/A','PUT');h.change(role(h).querySelector('select'),'moderator');h.reply(request,{...job(),revision_count:2});await h.flush();assert.equal(h.evaluate('currentJob.speaker_profiles.A.session_role'),'moderator');assert.equal(h.evaluate('currentJobDirty'),true);assert.equal(h.evaluate('currentJob.revision_count'),2);
});

for(const status of [200,409,500])test(`Save ${status} during actual item navigation cannot take over newer result`,async t=>{
 const h=await setup(t);render(h);h.click('#save-button');const save=latest(h,'/api/library/A','PUT');h.evaluate('openLibraryItem("B")');const open=latest(h,'/api/library/B');h.reply(open,job('B'));await h.flush();const before=h.document.querySelector('#save-message').textContent;
 h.reply(save,status===200?{...job(),revision_count:2}:{error:'OLD FAILURE'},status);await h.flush();assert.equal(h.evaluate('currentJobId'),'B');assert.equal(h.document.querySelector('#result-title').textContent,'Synthetic B');assert.equal(h.document.querySelector('#save-message').textContent,before);assert.equal(h.document.querySelector('#save-button').disabled,false);
});

test('malicious transcript and display names remain literal DOM text/value',async t=>{
 const h=await setup(t);const attack='<img src=x onerror="alert(1)"><script>alert(2)</script><a href="javascript:alert(3)">payload</a>';const data=job('A',attack);data.speaker_profiles.A.display_name=attack;data.source_name=attack;render(h,data);
 assert.equal(h.document.querySelector('#result-title').textContent,attack);assert([...h.document.querySelectorAll('#segment-editor textarea')].some(n=>n.value===attack));unsafeMarkupAbsent(h.document.querySelector('#speaker-editor'));unsafeMarkupAbsent(h.document.querySelector('#segment-editor'));assert(role(h).querySelector('select').getAttribute('aria-label').includes(attack));
});

test('actual run lookup and file preview handlers render hostile JSON as literal text',async t=>{
 const h=await setup(t);analysisPanel(h);lookup(h,'r1');const dialog=h.document.querySelector('.analysis-fixed-dialog');assert.equal(dialog.open,true);const attack='<img src=x onerror=alert(1)><script>alert(2)</script>';const artifact={id:'f1',name:'result.json',bytes:123};h.reply(latest(h,'/api/library/A/analysis/runs/r1'),fixed('r1','A',[artifact]));await h.flush();h.click([...dialog.querySelectorAll('button')].find(b=>b.textContent==='result.json を読む'));h.reply(latest(h,'/api/library/A/analysis/runs/r1/previews/f1'),{preview:{run_id:'r1',artifact_id:'f1',format:'text',text:JSON.stringify({missing:null,zero:0,empty:'',attack})}});await h.flush();const preview=dialog.querySelector('.analysis-fixed-preview');assert(preview.textContent.includes(attack));assert(preview.textContent.includes('"missing":null'));assert(preview.textContent.includes('"zero":0'));unsafeMarkupAbsent(preview);assert(h.requests.every(r=>!r.options.method||r.options.method==='GET'));
});

test('actual close and reopen reject an old fixed-run response',async t=>{
 const h=await setup(t);analysisPanel(h);lookup(h,'old');const old=latest(h,'/api/library/A/analysis/runs/old');h.click('.analysis-fixed-header button');assert.equal(h.document.querySelector('.analysis-fixed-dialog').open,false);lookup(h,'new');h.reply(latest(h,'/api/library/A/analysis/runs/new'),fixed('new'));await h.flush();const body=h.document.querySelector('.analysis-fixed-body'),before=body.textContent;h.reply(old,fixed('old'));await h.flush();assert.equal(body.textContent,before);assert(h.document.querySelector('.analysis-fixed-header').textContent.includes('固定run new'));
});

test('actual history reload/open handlers preserve fixed item and run IDs',async t=>{
 const h=await setup(t);analysisPanel(h);h.click([...h.document.querySelectorAll('.analysis-storage button')].find(b=>b.textContent==='保存履歴を更新'));h.reply(latest(h,'/api/library/A/analysis/runs'),{runs:[fixed('saved').run]});await h.flush();h.click([...h.document.querySelectorAll('[data-archive-history] button')].find(b=>b.textContent==='この保存済み結果を読む'));h.reply(latest(h,'/api/library/A/analysis/runs/saved'),fixed('saved'));await h.flush();assert(h.document.querySelector('.analysis-fixed-header').textContent.includes('固定run saved'));assert.equal(h.requests.filter(r=>r.options.method==='POST').length,0);
});

test('Save double click dispatches once; A-B-A navigation rejects old owner even on same item ID',async t=>{
 const h=await setup(t);render(h);h.click('#save-button');h.click('#save-button');assert.equal(h.requests.filter(r=>r.options.method==='PUT').length,1);const save=latest(h,'/api/library/A','PUT');
 for(const id of ['B','A']){h.evaluate(`openLibraryItem('${id}')`);h.reply(latest(h,`/api/library/${id}`),{...job(id),source_name:`New ${id}`});await h.flush();}
 h.reply(save,{...job(),source_name:'Old saved A'});await h.flush();assert.equal(h.document.querySelector('#result-title').textContent,'New A');assert.equal(h.evaluate('currentJobDirty'),false);
});

test('actual editor navigation ignores out-of-order older item response',async t=>{
 const h=await setup(t);h.evaluate('openLibraryItem("A");openLibraryItem("B")');const old=latest(h,'/api/library/A');h.reply(latest(h,'/api/library/B'),job('B'));await h.flush();h.reply(old,job('A'));await h.flush();assert.equal(h.evaluate('currentJobId'),'B');
});

test('fixed preview switches refuse stale file data; table headers and cells remain literal',async t=>{
 const h=await setup(t);analysisPanel(h);lookup(h,'r1');const artifacts=[{id:'f1',name:'first.json',bytes:1},{id:'f2',name:'second.json',bytes:2}];h.reply(latest(h,'/api/library/A/analysis/runs/r1'),fixed('r1','A',artifacts));await h.flush();
 const dialog=h.document.querySelector('.analysis-fixed-dialog');for(const name of ['first.json','second.json'])h.click([...dialog.querySelectorAll('button')].find(b=>b.textContent===`${name} を読む`));
 const attack='<svg onload=alert(1)><a href="javascript:alert(2)">unsafe</a></svg>';
 h.reply(latest(h,'/api/library/A/analysis/runs/r1/previews/f2'),{preview:{run_id:'r1',artifact_id:'f2',format:'table',columns:[attack,'value'],rows:[[attack,'0']],total_rows:99,shown_rows:1,total_columns:2,truncated:true}});await h.flush();
 const preview=dialog.querySelector('.analysis-fixed-preview'),before=preview.textContent;assert.equal(preview.querySelector('th').textContent,attack);assert.equal(preview.querySelector('td').textContent,attack);assert(before.includes('全99行中1行'));unsafeMarkupAbsent(preview);
 h.reply(latest(h,'/api/library/A/analysis/runs/r1/previews/f1'),{preview:{run_id:'r1',artifact_id:'f1',format:'text',text:'OLD CONTENT'}});await h.flush();assert.equal(preview.textContent,before);
});

for(const scenario of ['wrong-run','wrong-item','unverified','malformed-artifacts'])test(`fixed lookup rejects ${scenario} without live fallback`,async t=>{
 const h=await setup(t);analysisPanel(h);lookup(h,'r1');const payload=fixed();if(scenario==='wrong-run')payload.run.id='other';if(scenario==='wrong-item')payload.run.item_id='B';if(scenario==='unverified')payload.integrity='unknown';if(scenario==='malformed-artifacts')payload.run.artifacts={bad:true};
 const count=h.requests.length;h.reply(latest(h,'/api/library/A/analysis/runs/r1'),payload);await h.flush();assert.equal(h.document.querySelector('.analysis-fixed-body').children.length,0);assert.equal(h.requests.length,count);assert(h.document.querySelector('.analysis-fixed-header [role=status]').textContent.length>0);
});

test('fixed-run metadata and encoded artifact URLs do not create executable attributes',async t=>{
 const h=await setup(t);analysisPanel(h);lookup(h,'r1');const attack='\"><img src=x onerror=alert(1)><script>alert(2)</script>';const artifact={id:'javascript:alert(3)/../',name:attack,bytes:0,rows:null,sha256:attack};const payload=fixed('r1','A',[artifact]);payload.run.created_at=attack;payload.provenance={fingerprint:attack};payload.saved_summary={methods:[{title:attack,status:attack,analysis_unit:attack,summaries:[{title:attack,text:attack}],findings:[{title:attack,text:attack}],limitations:[attack]}]};h.reply(latest(h,'/api/library/A/analysis/runs/r1'),payload);await h.flush();const body=h.document.querySelector('.analysis-fixed-body');assert(body.textContent.includes(attack));unsafeMarkupAbsent(body);const download=body.querySelector('.analysis-fixed-file a');assert.equal(download.getAttribute('href'),'/api/analysis/artifacts/javascript%3Aalert(3)%2F..%2F');
});

test('Save cannot commit an old result while a newer navigation request is still pending',async t=>{
 const h=await setup(t);render(h);h.click('#save-button');const save=latest(h,'/api/library/A','PUT');h.evaluate('openLibraryItem("B")');const opening=latest(h,'/api/library/B');h.reply(save,{...job(),revision_count:2,source_name:'Old response'});await h.flush();assert.equal(h.document.querySelector('#result-title').textContent,'Synthetic A');assert.equal(h.evaluate('currentJob.revision_count'),1);h.reply(opening,job('B'));await h.flush();assert.equal(h.evaluate('currentJobId'),'B');assert.equal(h.document.querySelector('#save-button').disabled,false);
});

test('actual mode changes restore optional choices and serialize each effort exactly once',async t=>{
 const h=await setup(t);h.change(h.document.querySelector('#ai-provider'),'openai');const cleanup=h.document.querySelector('#clean-transcript'),outline=h.document.querySelector('#create-outline');if(!cleanup.checked)h.click(cleanup);if(outline.checked)h.click(outline);
 const before={cleanup:cleanup.checked,outline:outline.checked,finish:h.document.querySelector('#finish-in-obsidian').checked};h.click('input[name=transcript_finishing_mode][value=advanced]');h.click('input[name=transcript_finishing_mode][value=recommended]');assert.deepEqual({cleanup:cleanup.checked,outline:outline.checked,finish:h.document.querySelector('#finish-in-obsidian').checked},before);
 for(const mode of ['recommended','advanced','off']){h.click(`input[name=transcript_finishing_mode][value=${mode}]`);const form=new h.w.FormData(h.document.querySelector('#job-form'));assert.equal(form.get('transcript_finishing_mode'),mode);for(const key of stages){assert.equal(form.getAll(`ai_effort_${key}`).length,1);assert.equal(form.get(`ai_effort_${key}`),h.evaluate('readAiEfforts()')[key]);}assert.equal(h.document.querySelector('#jev-compare').checked,false);}
});

for(const source of ['default','legacy_unknown'])test(`ordinary actual Save never certifies ${source} role provenance`,async t=>{
 const h=await setup(t);const fixture=job();fixture.speaker_profiles.A.session_role_source=source;render(h,fixture);h.click('#save-button');const request=latest(h,'/api/library/A','PUT');assert.equal(JSON.parse(request.options.body).speaker_profiles.A.session_role_source,source);h.reply(request,{...fixture,revision_count:2});await h.flush();assert.equal(h.evaluate('currentJob.speaker_profiles.A.session_role_source'),source);assert.equal(h.evaluate('currentJobDirty'),false);
});
