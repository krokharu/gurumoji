'use strict';
// Independent acceptance for coordinated production fixes; old source must fail.
const test=require('node:test'), assert=require('node:assert/strict');
const {createHarness}=require('./harness.cjs');
async function setup(t){const h=await createHarness();t.after(()=>h.close());return h;}
function data(label='A',profiles={}){return {id:'A',source_name:'Synthetic A',revision_count:1,files:[],segments:[{id:'s1',speaker:label,start:0,end:1,text:'Synthetic'}],speaker_profiles:profiles,speaker_names:{},session_profile:{}};}
function render(h,fixture){h.fixture(fixture);h.evaluate('renderResult(window.fixture)');}
for(const key of ['__proto__','constructor','toString','A'])test(`speaker literal key ${key} survives real render/save without mutating prototypes`,async t=>{
 const h=await setup(t);const before=h.evaluate('JSON.stringify([Object.getOwnPropertyDescriptors(Object.prototype),Object.getOwnPropertyDescriptors(Object),Object.getOwnPropertyDescriptors(Object.prototype.toString)])');render(h,data(key));
 assert.equal(h.document.querySelectorAll('.conversation-role-control').length,1);const metrics=JSON.parse(h.evaluate('JSON.stringify(speakerMetrics())'));assert.equal(metrics[key].count,1);assert.equal(metrics[key].seconds,1);assert.equal(metrics[key].characters,9);assert.equal(metrics[key].share,1);
 h.click('.conversation-role-control button');h.click('#save-button');const request=h.requests.findLast(r=>r.options.method==='PUT');const body=JSON.parse(request.options.body);assert(Object.hasOwn(body.speaker_profiles,key));assert.equal(body.speaker_profiles[key].session_role_source,'explicit');h.reply(request,{...data(key,body.speaker_profiles),revision_count:2});await h.flush();assert.equal(h.evaluate('JSON.stringify([Object.getOwnPropertyDescriptors(Object.prototype),Object.getOwnPropertyDescriptors(Object),Object.getOwnPropertyDescriptors(Object.prototype.toString)])'),before);
});

test('existing own __proto__ profile is preserved by real render and Save',async t=>{
 const h=await setup(t);const profiles=JSON.parse('{"__proto__":{"display_name":"Synthetic kept","session_role":"moderator","session_role_source":"explicit","notes":"retain"}}');render(h,data('__proto__',profiles));h.click('#save-button');const request=h.requests.findLast(r=>r.options.method==='PUT');const body=JSON.parse(request.options.body);assert.deepEqual(body.speaker_profiles.__proto__.notes,'retain');assert.equal(body.speaker_profiles.__proto__.session_role,'moderator');h.reply(request,{...data('__proto__',body.speaker_profiles),revision_count:2});await h.flush();assert(h.document.querySelector('.conversation-role-control select').getAttribute('aria-label').includes('Synthetic kept'));
});

for(const raw of ['constructor','toString','__proto__'])test(`saved summary and history kind retain unknown ${raw} as literal code`,async t=>{
 const h=await setup(t);h.fixture({itemId:'A',data:{item:{id:'A'},segments:[]}});h.evaluate('Object.assign(analysisState,window.fixture);document.querySelector("#analysis-card").append(buildAnalysisStorage())');
 h.fixture({methods:[{title:'Synthetic method',status:raw}]});h.evaluate('document.querySelector("#analysis-card").append(buildFixedAnalysisSummary(window.fixture))');const summary=h.document.querySelector('.analysis-fixed-summary');assert(summary.textContent.includes(`保存時の状態: ${raw}`));assert(!summary.textContent.includes('[native code]'));
 h.fixture([{id:'r1',item_id:'A',kind:raw,status:'completed',artifacts:[]}]);h.evaluate('analysisStorageState().runs=window.fixture;refreshAnalysisStorage()');assert(h.document.querySelector('[data-archive-history] summary').textContent.startsWith(`${raw} /`));
});

function named(element,document){return element.getAttribute('aria-label')||[...(element.getAttribute('aria-labelledby')||'').split(/\s+/)].filter(Boolean).map(id=>document.getElementById(id)?.textContent||'').join(' ')||[...(element.labels||[])].map(label=>label.textContent).join(' ');}

test('every speaker editor control has a distinct contextual name and keeps role source on name input',async t=>{
 const h=await setup(t);const fixture=data('A',{A:{display_name:'Before',session_role:'participant',session_role_source:'default'}});fixture.segments.push({id:'s2',speaker:'B',start:1,end:2,text:'Synthetic B'});fixture.speaker_profiles.B={display_name:'Second',session_role:'observer',session_role_source:'registry'};render(h,fixture);
 const rows=h.document.querySelectorAll('.conversation-speaker-sheet tbody tr');assert.equal(rows.length,2);
 for(const [index,row]of [...rows].entries()){const names=[...row.querySelectorAll('input,select,textarea,button')].map(element=>named(element,h.document));assert(names.every(name=>name.includes(index?'Second':'Before')),JSON.stringify(names));assert.equal(new Set(names).size,names.length);}
 const row=rows[0],input=row.querySelector('input[type=text]');input.value='After';input.dispatchEvent(new h.w.Event('input',{bubbles:true}));for(const element of row.querySelectorAll('input,select,textarea,button'))assert(named(element,h.document).includes('After'),named(element,h.document));assert.equal(h.evaluate('currentJob.speaker_profiles.A.session_role_source'),'default');assert.equal(h.requests.filter(r=>r.options.method==='PUT').length,0);
 h.click('#save-button');const request=h.requests.findLast(r=>r.options.method==='PUT');const body=JSON.parse(request.options.body);assert.equal(body.speaker_profiles.A.display_name,'After');assert.equal(body.speaker_profiles.A.session_role_source,'default');assert.equal(body.speaker_profiles.B.session_role_source,'registry');h.reply(request,{...fixture,speaker_profiles:body.speaker_profiles,revision_count:2});await h.flush();
});

test('speaker registry relink restores the corresponding select after DOM replacement',async t=>{
 const h=await setup(t);render(h,data('A',{A:{display_name:'Before',session_role:'participant',session_role_source:'default'}}));h.fixture([{id:'registry1',display_name:'Registered name',default_role:'moderator',active:true}]);h.evaluate('speakerRegistry=window.fixture;renderSpeakerEditor()');const old=h.document.querySelector('.conversation-speaker-sheet tbody tr select');old.focus();h.change(old,'registry1');const replacement=h.document.querySelector('.conversation-speaker-sheet tbody tr select');assert.notEqual(replacement,old);assert.equal(h.document.activeElement,replacement);assert.equal(replacement.value,'registry1');assert.equal(h.evaluate('currentJob.speaker_profiles.A.session_role'),'moderator');assert.equal(h.evaluate('currentJob.speaker_profiles.A.session_role_source'),'registry');assert.equal(h.requests.filter(r=>r.options.method==='PUT').length,0);
});

async function openRun(h){h.fixture({itemId:'A',data:{item:{id:'A'},segments:[]}});h.evaluate('Object.assign(analysisState,window.fixture);document.querySelector("#analysis-card").append(buildAnalysisStorage());document.body.dataset.view="analysis";analysisCard.hidden=false;analysisCatalogLoaded=true');const form=h.document.querySelector('.analysis-fixed-lookup');form.querySelector('input').value='r1';form.requestSubmit();return h.requests.findLast(r=>r.url==='/api/library/A/analysis/runs/r1');}

test('accepted real navigation closes fixed modal and invalidates inflight result',async t=>{
 const h=await setup(t);const pending=await openRun(h);assert.equal(h.document.querySelector('.analysis-fixed-dialog').open,true);h.click('#show-library-button');assert.equal(h.w.location.hash,'#/data');assert.equal(h.document.querySelector('.analysis-fixed-dialog').open,false);h.reply(pending,{run:{id:'r1',item_id:'A',artifacts:[]},integrity:'verified'});await h.flush();assert.equal(h.document.querySelector('.analysis-fixed-dialog').open,false);assert.equal(h.document.querySelector('.analysis-fixed-body').children.length,0);
});

for(const href of ['javascript:alert(1)','data:text/html,<script>alert(2)</script>','https://untrusted.invalid/','//untrusted.invalid/'])test(`history rejects malformed URI ${href.split(':')[0]} without clicking links`,async t=>{
 const h=await setup(t);const pending=await openRun(h);h.reply(pending,{run:{id:'r1',item_id:'A',artifacts:[]},integrity:'verified'});await h.flush();h.fixture([{id:'r1',item_id:'A',kind:'text_analysis',status:'completed',obsidian_uri:href,artifacts:[{id:'f1',name:'result.json',url:href}]}]);h.evaluate('analysisStorageState().runs=window.fixture;refreshAnalysisStorage()');const links=[...h.document.querySelectorAll('[data-archive-history] a')].map(n=>n.getAttribute('href'));assert(!links.includes(href));assert(links.every(url=>url.startsWith('/api/')||url.startsWith('obsidian://open?')));assert.equal(h.requests.filter(r=>r.url.includes('untrusted')).length,0);
});

test('history retains approved Obsidian open link and derives fixed artifact endpoint',async t=>{
 const h=await setup(t);const pending=await openRun(h);h.reply(pending,{run:{id:'r1',item_id:'A',artifacts:[]},integrity:'verified'});await h.flush();const uri='obsidian://open?path=%2Fsynthetic%2FResearch%2Ftest.md';h.fixture([{id:'r1',item_id:'A',kind:'text_analysis',status:'completed',obsidian_uri:uri,artifacts:[{id:'f1',name:'result.json',url:'/api/analysis/artifacts/f1'}]}]);h.evaluate('analysisStorageState().runs=window.fixture;refreshAnalysisStorage()');const links=[...h.document.querySelectorAll('[data-archive-history] a')].map(n=>n.getAttribute('href'));assert(links.includes(uri));assert(links.includes('/api/analysis/artifacts/f1'));
});

test('rejected unsaved navigation keeps fixed modal owner and allows its response',async t=>{
 const h=await setup(t);const pending=await openRun(h);h.evaluate('analysisState.dirty=true;analysisCard.hidden=false');h.w.confirm=()=>false;h.click('#show-library-button');assert.equal(h.document.querySelector('.analysis-fixed-dialog').open,true);h.reply(pending,{run:{id:'r1',item_id:'A',artifacts:[]},integrity:'verified'});await h.flush();assert(h.document.querySelector('.analysis-fixed-body').children.length>0);
});

test('accepted navigation invalidates an already pending fixed file preview',async t=>{
 const h=await setup(t);const pending=await openRun(h);h.reply(pending,{run:{id:'r1',item_id:'A',artifacts:[{id:'f1',name:'result.json',bytes:1}]},integrity:'verified'});await h.flush();h.click([...h.document.querySelectorAll('.analysis-fixed-dialog button')].find(b=>b.textContent==='result.json を読む'));const preview=h.requests.findLast(r=>r.url.endsWith('/previews/f1'));h.click('#show-library-button');assert.equal(h.document.querySelector('.analysis-fixed-dialog').open,false);h.reply(preview,{preview:{run_id:'r1',artifact_id:'f1',format:'text',text:'LATE PRIVATE FIXTURE'}});await h.flush();assert(!h.document.querySelector('.analysis-fixed-body').textContent.includes('LATE PRIVATE FIXTURE'));
});

test('duplicate display names remain distinguishable by stable speaker label',async t=>{
 const h=await setup(t);const fixture=data('A',{A:{display_name:'Same',session_role:'participant'},B:{display_name:'Same',session_role:'participant'}});fixture.segments.push({id:'s2',speaker:'B',start:1,end:2,text:'Synthetic B'});render(h,fixture);const rows=h.document.querySelectorAll('.conversation-speaker-sheet tbody tr');const first=[...rows[0].querySelectorAll('input,select,textarea,button')],second=[...rows[1].querySelectorAll('input,select,textarea,button')];assert.equal(first.length,second.length);first.forEach((element,index)=>assert.notEqual(named(element,h.document),named(second[index],h.document)));
});

test('same-context analysis navigation retains fixed viewer and its pending response',async t=>{
 const h=await setup(t);const pending=await openRun(h);const generation=h.evaluate('analysisNavigationGeneration');h.evaluate('showView("analysis")');assert.equal(h.evaluate('analysisNavigationGeneration'),generation);assert.equal(h.document.querySelector('.analysis-fixed-dialog').open,true);h.reply(pending,{run:{id:'r1',item_id:'A',artifacts:[]},integrity:'verified'});await h.flush();assert(h.document.querySelector('.analysis-fixed-body').children.length>0);
});

function timingJob(segments){return {...data(),segments:segments.map((segment,index)=>({id:`s${index}`,speaker:'A',text:'Synthetic',...segment})),speaker_profiles:{A:{display_name:'Synthetic A',session_role:'participant'},B:{display_name:'Synthetic B',session_role:'participant'}}};}
const metricCells=h=>[...h.document.querySelectorAll('.speaker-metric-cell')].map(n=>n.textContent);
const uncertain=text=>/不明|未確定|算出不可|算出でき|利用不可/.test(text);

test('all-missing speaker time is unknown rather than measured zero and leaves source values intact',async t=>{
 const h=await setup(t);const fixture=timingJob([{start:null,end:null},{},{start:0,end:100,time_unknown:true}]);render(h,fixture);const cells=metricCells(h);assert.equal(cells.length,1);assert(uncertain(cells[0]),cells[0]);assert(!cells[0].includes('0.0%'));assert(!h.document.querySelector('#speaker-insights').textContent.includes('参加者内50%以上'));assert.deepEqual(JSON.parse(h.evaluate('JSON.stringify(currentJob.segments)')),fixture.segments);
});

test('real zero-duration speaker time stays zero but has no defined population share',async t=>{
 const h=await setup(t);render(h,timingJob([{start:0,end:0}]));const cell=metricCells(h)[0];assert(/0:00/.test(cell),cell);assert(!cell.includes('0.0%'));assert(uncertain(cell),cell);
});

test('mixed valid and invalid time retains known subtotal with missing coverage and no share warning',async t=>{
 const h=await setup(t);const fixture=timingJob([{start:0,end:10},{start:'invalid',end:12},{speaker:'B',start:0,end:6}]);render(h,fixture);const cells=metricCells(h);assert(/0:10/.test(cells[0]),cells[0]);assert(/1\/2発話/.test(cells[0]),cells[0]);assert(/時刻不明1発話/.test(cells[0]),cells[0]);assert(!/確認済み/.test(cells[0]),cells[0]);assert(cells.every(cell=>!/[0-9]+\.[0-9]+%/.test(cell)),cells.join('; '));assert(cells.every(uncertain),cells.join('; '));assert(!h.document.querySelector('#speaker-insights').textContent.includes('参加者内50%以上'));assert.deepEqual(JSON.parse(h.evaluate('JSON.stringify(currentJob.segments)')),fixture.segments);
});

test('time_unknown long duration cannot dominate measured participant time',async t=>{
 const h=await setup(t);render(h,timingJob([{start:0,end:10},{speaker:'B',start:0,end:100,time_unknown:true}]));const cells=metricCells(h);assert(/0:10/.test(cells[0]),cells[0]);assert(uncertain(cells[1]),cells[1]);assert(!cells.some(cell=>cell.includes('90.9%')));assert(!h.document.querySelector('#speaker-insights').textContent.includes('参加者内50%以上'));
});

test('same-run history refresh removes stale URI and refuses malformed artifact IDs',async t=>{
 const h=await setup(t);const pending=await openRun(h);h.reply(pending,{run:{id:'r1',item_id:'A',artifacts:[]},integrity:'verified'});await h.flush();
 const uri='obsidian://open?path=%2Fsynthetic%2Fnote.md';
 function history(url,id){h.fixture([{id:'r1',item_id:'A',kind:'text_analysis',status:'completed',obsidian_uri:url,artifacts:[{id,name:'Synthetic artifact',url:'javascript:alert(1)'}]}]);h.evaluate('analysisStorageState().runs=window.fixture;refreshAnalysisStorage()');return [...h.document.querySelectorAll('[data-archive-history] a')].map(n=>n.getAttribute('href'));}
 assert(history(uri,'f1').includes(uri));
 for(const url of ['javascript:alert(1)','obsidian://open?path=','obsidian://open?path=%ZZ','obsidian://open?path=%0Asecret','obsidian://open?path=x&command=run','obsidian://other?path=x','obsidian://open?path=x#fragment'])assert(!history(url,'f1').includes(url),url);
 for(const id of ['',null,42,'.','..','line\nbreak']){const links=history(uri,id);assert(!links.some(url=>url.startsWith('/api/analysis/artifacts/')),JSON.stringify({id,links}));}
 const links=history(uri,'a/b?c#d');assert(links.includes('/api/analysis/artifacts/a%2Fb%3Fc%23d'));assert(!links.some(url=>/^(javascript|data):/.test(url)));
});
