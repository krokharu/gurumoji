// Original source functions, synthetic deferred responses and DOM only.
// No browser, application server, model inference, real HTTP or user data.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const app = path.resolve(__dirname, '..');
const files = Object.fromEntries(['analysis-method-view.js', 'analysis-execution.js', 'analysis-content.js', 'app.js', 'style.css'].map(name =>
  [name, fs.readFileSync(path.join(app, 'src/gurumoji/static', name), 'utf8')]));
function extract(file, name) {
  const src = files[file];
  const match = new RegExp(`^(?:async )?function ${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\(`, 'm').exec(src);
  if (!match) throw new Error(`Missing ${file}:${name}`);
  const firstLine = src.slice(match.index, src.indexOf('\n', match.index)).trim();
  if (firstLine.endsWith('}')) return firstLine;
  const end = src.indexOf('\n}', match.index);
  if (end < 0) throw new Error(`Unterminated ${name}`);
  return src.slice(match.index, end + 2);
}
function data(origin, rev = 1, executed = true) {
  return {origin, executed, item:{revision_count:rev, analysis_revision:rev, source_name:origin},
    segment_classification:{origin}, transformer:{result:null}, insights:{fingerprint:'shared-fingerprint', ai:{archive_id:origin}}};
}
function node(value = '') { return {value, checked:false, disabled:false, open:true, hidden:false, children:[],
  replaceChildren(...v){this.children=v;}, append(...v){this.children.push(...v);}, focus(){}, close(){this.open=false;}, showModal(){this.open=true;}}; }
function make() {
  const requests = [], effects = [], nodes = new Map(), storage = new Map();
  const ctx = {
    analysisState:{itemId:'A', data:data('A-original'), dirty:false, mode:'methods', config:{}},
    analysisExecutionState:{id:'pipeline-A',itemId:'A',status:'running',active:true,resuming:false,cancelRequested:false,logs:[],settings:{allowedActions:['retry']},generation:0},
    analysisExecutionStageDefinitions:[{id:'M0',title:'synthetic'}], analysisCatalog:[{id:'A',source_name:'A'},{id:'B',source_name:'B'}],
    segmentClassificationRequests:new Map(), analysisMutationGeneration:0, analysisNavigationGeneration:1, analysisRequestSequence:1,
    analysisPlanGeneration:1, analysisDialogGeneration:1, analysisAdvisorGeneration:1, analysisStartOwner:null, analysisRunOwner:1, analysisRunOperations:new Map(),
    structuredClone, segmentClassificationInProgress:false, analysisPlanningProposal:null, analysisPlanningItemId:'', analysisAdvisorItemId:'A',
    contentAnalysisStates:new Map(), contentAnalysisPollSequence:0, transformerAnalysisPollSequence:0,
    contentAnalysisPollTimer:null, transformerAnalysisPollTimer:null,
    analysisAdvisorObjective:node('synthetic objective'),analysisAdvisorEngine:node('transformer'),analysisAdvisorModel:node(''),
    analysisAdvisorProposeButton:node(),analysisAdvisorFlow:node(),analysisAdvisorResult:node(),analysisRunStartButton:node(),analysisRunDialog:node(),
    document:{querySelector(s){if(!nodes.has(s))nodes.set(s,node());return nodes.get(s);},querySelectorAll(){return [];},createElement(){return node();}},
    crypto:{randomUUID:()=>`synthetic-${requests.length}`}, URLSearchParams, AbortController,
    sessionStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>{effects.push(['storage-remove',k]);storage.delete(k);}},
    window:{confirm:()=>true,clearTimeout(){},setTimeout(){effects.push(['timer']);return 1;},requestAnimationFrame:f=>f()},
    clearTimeout(){},setTimeout(){effects.push(['timer']);return 1;},
    createSubmissionId:()=>`synthetic-${requests.length}`,hasUnsavedAnalysisChanges:()=>false,
    setAlert:(_,msg,error)=>effects.push(['alert',ctx.analysisState.itemId,msg,!!error]),
    renderAnalysisWorkspace:()=>effects.push(['render-workspace',ctx.analysisState.itemId]),
    renderAnalysisExecution:()=>effects.push(['render-execution',ctx.analysisExecutionState.itemId,ctx.analysisExecutionState.id]),
    invalidateAnalysisMethodOverview:()=>effects.push(['invalidate-methods',ctx.analysisState.itemId]),
    analysisExecutionMode:()=> 'automatic',analysisExecutionValidatePlan:()=>'',analysisExecutionUpdatePlanSummary:()=>effects.push(['summary',ctx.analysisState.itemId]),
    analysisExecutionSetDialogMessage:(m,e)=>effects.push(['dialog-message',ctx.analysisState.itemId,m,!!e]),
    analysisExecutionPrepareDefinition:async()=>[],
    analysisExecutionLogFromEvents:()=>[],analysisExecutionPersist:()=>effects.push(['persist-execution']),analysisExecutionClearPersisted:()=>effects.push(['clear-execution']),
    showAnalysisExecutionView:()=>effects.push(['show-execution',ctx.analysisState.itemId]),hideAnalysisExecutionView:()=>{},openAnalysisExecutionDialog:()=>{},
    renderAnalysisAdvisorFlow:x=>effects.push(['advisor-flow',ctx.analysisState.itemId,x.state,x.proposal?.origin]),
    loadAnalysisItem:async(id,options)=>effects.push(['load-item',id,options]),loadAnalysisStorage:()=>effects.push(['load-storage',ctx.analysisState.itemId]),
    refreshTransformerControls:()=>effects.push(['transformer-controls',ctx.analysisState.itemId]),refreshInsightControls:()=>effects.push(['insight-controls',ctx.analysisState.itemId]),
    renderTransformerSearchResults:()=>effects.push(['semantic-render',ctx.analysisState.itemId]),renderKwicResults:()=>effects.push(['kwic-render',ctx.analysisState.itemId]),
    transformerRunActive:r=>r&&['queued','running','cancelling'].includes(r.status),insightRunActive:r=>r&&['queued','running','cancelling'].includes(r.status),
    transformerModeValue:s=>s.transformerMode||'auto',transformerPendingKey:id=>`transformer.${id}`,insightPendingKey:id=>`insight.${id}`,
    openLinkedAnalysisEvidence(){},
    apiFetch(url,options={}){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});requests.push({url,options,resolve,reject});return promise;},
    readJsonResponse:async r=>r.payload,
  };
  ctx.analysisExecutionRequestJson=async(url,options)=>{const r=await ctx.apiFetch(url,options);if(!r.ok){const error=Error(r.payload.error||'synthetic error');error.code=r.payload.reason_code;error.status=r.status;throw error;}return r.payload;};
  vm.createContext(ctx);
  const load=(f,...names)=>names.forEach(n=>vm.runInContext(extract(f,n),ctx));
  load('app.js','captureAnalysisContext','isAnalysisContextCurrent','segmentClassificationBusy');
  load('analysis-execution.js','captureAnalysisDialog','captureAnalysisRun','invalidateAnalysisDialog','closeAnalysisExecutionDialog');
  load('analysis-content.js','contentAnalysisState');
  const navigate=(id,origin,rev=2,executed=true)=>{ctx.analysisNavigationGeneration++;ctx.analysisState.itemId=id;ctx.analysisState.data=data(origin,rev,executed);};
  const reply=(i,payload,ok=true)=>requests[i].resolve({ok,payload,status:ok?200:500});
  return {ctx,load,navigate,reply,requests,effects,storage,nodes};
}


const assert = require('node:assert/strict');
const tick=()=>new Promise(r=>setImmediate(r));
const passed=[];const presetPayloads={};
async function check(name,work){
 const timer=setTimeout(()=>{console.error('Unresolved test: '+name);process.exit(1);},2000);
 try {await work();passed.push(name);} finally {clearTimeout(timer);}
}
function measurement() {
 const p=make();let ids=0;p.ctx.crypto.randomUUID=()=>`fixture-${++ids}`;
 const source=files['analysis-execution.js'];
 vm.runInContext(source.slice(source.indexOf('const analysisMeasurementPresets ='),source.indexOf('let analysisMeasurement =')),p.ctx);
 p.ctx.analysisMeasurement=null;
 p.load('analysis-execution.js','analysisMeasurementPreset','analysisMeasurementNewIdentity','analysisMeasurementReset','analysisMeasurementFillGenerated','analysisMeasurementFingerprint','analysisMeasurementCurrent','analysisMeasurementRefreshContext','analysisMeasurementInvalidate','analysisMeasurementRender','analysisMeasurementAction','analysisMeasurementInspect','analysisExecutionDefinitionFromForm','analysisExecutionValidateDefinition','analysisExecutionValidatePlan','analysisExecutionPrepareDefinition','analysisExecutionSyncDisplay');
 p.ctx.analysisExecutionMode=()=> 'manual';
 p.ctx.analysisMeasurementReset();
 return p;
}
function definition(p, revision=1, status='draft') {return {...p.ctx.analysisExecutionDefinitionFromForm(),version:1,revision,status};}
function trial(p) {const d=p.ctx.analysisMeasurement.saved.definition;return {trial_id:'fixed-trial',definition_id:d.definition_id,definition_version:d.version,definition_revision:d.revision,definition_hash:'fixed-definition',input_hash:'fixed-input',source_revision:1,analysis_revision:1,total_count:3,excluded_count:1,sample_size:2,valid_count:1,missing_count:1,values:[0,null],rows:[{segment_id:'s1',speaker:'A',speaker_name:'Synthetic', [d.output_column]:0,[d.output_column+'__missing_reason']:''},{segment_id:'s2',speaker:'B',speaker_name:'Synthetic',[d.output_column]:null,[d.output_column+'__missing_reason']:'time_unknown'}],external_calls:0,created_at:'2026-10-03T00:00:00Z'};}
async function saved(p) {const a=p.ctx.analysisMeasurementAction('save');const i=p.requests.length-1;p.reply(i,{definition:definition(p)});await a;}
async function tried(p) {await saved(p);const a=p.ctx.analysisMeasurementAction('trial');p.reply(p.requests.length-1,{trial:trial(p)});await a;}
async function adopted(p) {await tried(p);p.ctx.document.querySelector('#analysis-definition-confirm').checked=true;const a=p.ctx.analysisMeasurementAction('adopt');p.reply(p.requests.length-1,{definition:{...definition(p,2,'adopted'),last_trial:trial(p)}});await a;}
(async()=>{
for(const key of ['text_length','duration','speaker_frequency','role_frequency']) await check(`preset-${key}`,async()=>{
 const p=measurement();p.ctx.document.querySelector('#analysis-definition-preset').value=key;p.ctx.analysisMeasurementInvalidate({target:{id:'analysis-definition-preset'}});
 const d=p.ctx.analysisExecutionDefinitionFromForm();presetPayloads[key]=d;assert.equal(d.measurement_rule,key.endsWith('frequency')?'identity':key);assert.equal(d.method,key.endsWith('frequency')?'frequency':'descriptive');assert.equal(d.source_columns[0],{text_length:'text',duration:'duration',speaker_frequency:'speaker',role_frequency:'role'}[key]);
});
await check('role-missing-reasons-localized-only-in-reason-columns',async()=>{
 const p=measurement();await tried(p);
 const rows=['role_not_recorded','role_provenance_unknown','future_reason','',false,0,null].map(value=>({ordinary:value,role__missing_reason:value}));
 p.ctx.analysisMeasurement.trial.rows=rows;const before=JSON.stringify(rows);p.ctx.analysisMeasurementRender();
 const table=p.ctx.document.querySelector('#analysis-definition-trial-result').children[1].children[0];
 const rendered=table.children.slice(2).map(row=>row.children.map(cell=>cell.textContent));
 assert.equal(rendered[0][0],'role_not_recorded');assert.equal(rendered[1][0],'role_provenance_unknown');
 assert.equal(rendered[0][1],'role_not_recorded（役割未記録：自動補完は測定に使用しません）');
 assert.equal(rendered[1][1],'role_provenance_unknown（役割の記録元不明：旧データ等）');
 for(let i=2;i<rows.length;i++)assert.equal(rendered[i][0],rendered[i][1]);
 assert.deepEqual(rendered.slice(2).map(row=>row[1]),['future_reason','','false','0','null（欠測）']);
 assert.equal(JSON.stringify(rows),before);
});
await check('save-trial-confirm-adopt-run-explicit',async()=>{
 const p=measurement();assert(p.ctx.analysisExecutionValidatePlan());assert.equal(p.requests.length,0);
 await tried(p);assert.equal(p.requests.length,2);assert.equal(p.ctx.analysisMeasurement.adopted,null);assert(p.ctx.analysisExecutionValidatePlan());
 await p.ctx.analysisMeasurementAction('adopt');assert.equal(p.requests.length,2);
 p.ctx.document.querySelector('#analysis-definition-confirm').checked=true;
 const a=p.ctx.analysisMeasurementAction('adopt');assert.equal(p.requests.length,3);
 const payload=JSON.parse(p.requests[2].options.body);assert.deepEqual(payload.expected_trial,JSON.parse(JSON.stringify(p.ctx.analysisMeasurement.trial)));assert.equal(payload.expected_revision,1);assert.equal(payload.status,'adopted');
 p.reply(2,{definition:{...definition(p,2,'adopted'),last_trial:trial(p)}});await a;assert.equal(p.ctx.analysisExecutionValidatePlan(),'');assert.equal(p.requests.length,3);
 p.load('analysis-execution.js','startAnalysisExecution','analysisExecutionApplyResponse');p.ctx.analysisExecutionPoll=()=>{};
 const run=p.ctx.startAnalysisExecution();await tick();const preview=JSON.parse(p.requests[3].options.body);
 assert.equal(preview.expected_input_hash,'fixed-input');assert.equal(preview.expected_definition_versions[p.ctx.analysisMeasurement.adopted.definition_id],1);
 p.reply(3,{});await tick();assert.deepEqual(JSON.parse(p.requests[4].options.body),preview);p.reply(4,{pipeline_id:'new',status:'completed',allowed_actions:[],milestones:[],events:[]});await run;
});
await check('metadata-explicit-empty-and-default-survive-preset',async()=>{
 const p=measurement();const name=p.ctx.document.querySelector('#analysis-definition-name');const description=p.ctx.document.querySelector('#analysis-definition-description');const original=name.value;
 p.ctx.analysisMeasurementInvalidate({target:{id:'analysis-definition-name'}});description.value='';p.ctx.analysisMeasurementInvalidate({target:{id:'analysis-definition-description'}});
 p.ctx.document.querySelector('#analysis-definition-preset').value='duration';p.ctx.analysisMeasurementInvalidate({target:{id:'analysis-definition-preset'}});
 assert.equal(name.value,original);assert.equal(description.value,'');assert(p.ctx.analysisExecutionValidateDefinition());
});
await check('display-radio-does-not-touch-values-or-trial',async()=>{
 const p=measurement();await tried(p);const state=p.ctx.analysisMeasurement,before=JSON.stringify(p.ctx.analysisExecutionDefinitionFromForm()),t=state.trial,count=p.requests.length;
 p.ctx.document.querySelector('input[name="analysis_display_mode"]:checked').value='detail';p.ctx.analysisExecutionSyncDisplay();
 p.ctx.document.querySelector('input[name="analysis_display_mode"]:checked').value='simple';p.ctx.analysisExecutionSyncDisplay();
 assert.equal(JSON.stringify(p.ctx.analysisExecutionDefinitionFromForm()),before);assert.equal(state.trial,t);assert.equal(p.requests.length,count);
});
await check('adopted-edit-forks-identity',async()=>{
 const p=measurement();await adopted(p);const original=p.ctx.analysisMeasurement.adopted.definition_id;
 p.ctx.document.querySelector('#analysis-definition-description').value='Changed explicitly';p.ctx.analysisMeasurementInvalidate({target:{id:'analysis-definition-description'}});
 assert.notEqual(p.ctx.analysisExecutionDefinitionFromForm().definition_id,original);assert.equal(p.ctx.analysisMeasurement.adopted,null);assert.equal(p.ctx.analysisMeasurement.trial,null);assert.equal(p.ctx.analysisMeasurement.saved,null);
});
await check('foreign-id-never-overwritten',async()=>{
 const p=measurement();p.ctx.document.querySelector('#analysis-definition-id').value='foreign';p.ctx.analysisMeasurementInvalidate({target:{id:'analysis-definition-id'}});
 const a=p.ctx.analysisMeasurementAction('save');assert.equal(JSON.parse(p.requests[0].options.body).expected_revision,0);p.reply(0,{error:'revision conflict'},false);await a;assert.equal(p.ctx.analysisMeasurement.saved,null);assert.equal(p.requests.length,1);
});
for(const action of ['save','trial','adopt']) for(const transition of ['ABA','close','edit']) await check(`${action}-late-${transition}`,async()=>{
 const p=measurement();if(action==='trial')await saved(p);if(action==='adopt'){await tried(p);p.ctx.document.querySelector('#analysis-definition-confirm').checked=true;}
 const a=p.ctx.analysisMeasurementAction(action);const i=p.requests.length-1;const result=action==='trial'?{trial:trial(p)}:{definition:definition(p,2,action==='adopt'?'adopted':'draft')};
 if(transition==='ABA'){p.navigate('B','B');p.navigate('A','A-new');p.ctx.analysisMeasurementReset();}else if(transition==='close'){p.ctx.analysisRunDialog.close();p.ctx.invalidateAnalysisDialog();}else{p.ctx.document.querySelector('#analysis-definition-name').value='Changed';p.ctx.analysisMeasurementInvalidate({target:{id:'analysis-definition-name'}});}
 const state=p.ctx.analysisMeasurement,before=p.effects.length;p.reply(i,result);await a;assert.equal(state.adopted,null);assert.equal(p.effects.length,before);
});
await check('uncertain-adoption-inspects-without-second-put',async()=>{
 const p=measurement();await tried(p);p.ctx.document.querySelector('#analysis-definition-confirm').checked=true;const reviewed=p.ctx.analysisMeasurement.trial;
 const a=p.ctx.analysisMeasurementAction('adopt');p.requests[2].reject(Error('lost response'));await tick();assert.equal(p.requests[3].options.method,undefined);
 p.reply(3,{definition:{...definition(p,2,'adopted'),last_trial:reviewed}});await a;assert.equal(p.ctx.analysisMeasurement.adopted.status,'adopted');assert.equal(p.requests.filter(r=>r.options.method==='PUT').length,2);
});

await check('retrial-start-invalidates-old-confirmation-even-on-failure',async()=>{
 const p=measurement();await tried(p);p.ctx.document.querySelector('#analysis-definition-confirm').checked=true;
 const a=p.ctx.analysisMeasurementAction('trial');assert.equal(p.ctx.analysisMeasurement.trial,null);assert.equal(p.ctx.document.querySelector('#analysis-definition-confirm').checked,false);
 p.reply(2,{error:'trial failed'},false);await a;await p.ctx.analysisMeasurementAction('adopt');assert.equal(p.requests.length,3);assert.equal(p.ctx.analysisMeasurement.adopted,null);
});
for(const responseLost of [true,false]) await check(`closed-adoption-inspects-before-another-write-${responseLost}`,async()=>{
 const p=measurement();await tried(p);p.ctx.document.querySelector('#analysis-definition-confirm').checked=true;const reviewed=p.ctx.analysisMeasurement.trial;
 const a=p.ctx.analysisMeasurementAction('adopt');p.ctx.analysisRunDialog.close();p.ctx.invalidateAnalysisDialog();
 if(responseLost)p.requests[2].reject(Error('lost'));else p.reply(2,{definition:{...definition(p,2,'adopted'),last_trial:reviewed}});await a;
 assert(p.ctx.analysisMeasurement.pendingAdoption);p.ctx.analysisRunDialog.showModal();p.ctx.document.querySelector('#analysis-definition-confirm').checked=true;
 const retry=p.ctx.analysisMeasurementAction('adopt');assert.equal(p.requests[3].options.method,undefined);p.reply(3,{definition:{...definition(p,2,'adopted'),last_trial:reviewed}});await retry;
 assert.equal(p.requests.filter(r=>r.options.method==='PUT').length,2);assert.equal(p.ctx.analysisMeasurement.adopted.status,'adopted');assert.equal(p.ctx.analysisMeasurement.pendingAdoption,null);
});
await check('generated-id-collision-creates-another-draft',async()=>{
 const p=measurement();const id=p.ctx.analysisExecutionDefinitionFromForm().definition_id;const a=p.ctx.analysisMeasurementAction('save');p.reply(0,{error:'conflict',reason_code:'revision_conflict'},false);await a;
 assert.notEqual(p.ctx.analysisExecutionDefinitionFromForm().definition_id,id);assert.equal(p.ctx.analysisMeasurement.saved,null);assert.equal(p.requests.length,1);assert.equal(p.ctx.document.querySelector('#analysis-definition-save').disabled,false);
});
await check('explicit-new-id-after-adoption-is-preserved',async()=>{
 const p=measurement();await adopted(p);p.ctx.document.querySelector('#analysis-definition-id').value='my_explicit_new_id';p.ctx.analysisMeasurementInvalidate({target:{id:'analysis-definition-id'}});
 assert.equal(p.ctx.analysisExecutionDefinitionFromForm().definition_id,'my_explicit_new_id');assert.equal(p.ctx.analysisMeasurement.saved,null);
});

for(const phase of ['unsaved','saved','trial','adopted','pending-save','pending-adopt'])await check(`live-save-refreshes-measurement-${phase}`,async()=>{
 const p=measurement();p.ctx.document.querySelector('#analysis-definition-name').value='My unsaved name';p.ctx.analysisMeasurement.touched.add('name');
 p.ctx.document.querySelector('#analysis-definition-description').value='My unsaved description';p.ctx.analysisMeasurement.touched.add('description');
 if(phase==='saved')await saved(p);if(phase==='trial'||phase==='pending-adopt')await tried(p);if(phase==='adopted')await adopted(p);
 let pending=null;if(phase==='pending-save')pending=p.ctx.analysisMeasurementAction('save');
 if(phase==='pending-adopt'){p.ctx.document.querySelector('#analysis-definition-confirm').checked=true;pending=p.ctx.analysisMeasurementAction('adopt');}
 const pendingIndex=p.requests.length-1;
 const oldId=p.ctx.document.querySelector('#analysis-definition-id').value;
 const oldOutput=p.ctx.document.querySelector('#analysis-definition-output').value;
 p.ctx.analysisState.data=data('A-new',2);p.ctx.analysisState.dirty=false;
 p.ctx.analysisMeasurementRefreshContext();
 assert(p.ctx.analysisMeasurementCurrent());assert.equal(p.ctx.analysisMeasurement.trial,null);assert.equal(p.ctx.analysisMeasurement.adopted,null);
 assert.equal(p.ctx.analysisMeasurement.operation,null);assert.equal(p.ctx.document.querySelector('#analysis-definition-name').value,'My unsaved name');
 assert.equal(p.ctx.document.querySelector('#analysis-definition-description').value,'My unsaved description');
 assert.equal(p.ctx.document.querySelector('#analysis-definition-output').value,oldOutput);
 const newId=p.ctx.document.querySelector('#analysis-definition-id').value;
 if(phase==='unsaved')assert.equal(newId,oldId);else assert.notEqual(newId,oldId);
 assert(p.ctx.document.querySelector('#analysis-definition-state').textContent.includes('入力版が更新'));
 assert.equal(p.ctx.document.querySelector('#analysis-definition-save').disabled,false);assert.equal(p.ctx.document.querySelector('#analysis-definition-confirm').checked,false);
 if(pending){p.reply(pendingIndex,{definition:{...definition(p),definition_id:oldId}});await pending;assert.equal(p.ctx.analysisMeasurement.saved,null);}
 const saving=p.ctx.analysisMeasurementAction('save');const request=p.requests.length-1;assert.equal(JSON.parse(p.requests[request].options.body).expected_revision,0);
 p.reply(request,{definition:definition(p)});await saving;assert.equal(p.ctx.analysisMeasurement.saved.definition.definition_id,newId);
});

await check('live-save-refresh-retains-later-unsaved-analysis-guard',async()=>{
 const p=measurement();p.ctx.hasUnsavedAnalysisChanges=()=>p.ctx.analysisState.dirty;
 p.ctx.analysisState.data=data('A-new',2);p.ctx.analysisState.dirty=true;p.ctx.analysisMeasurementRefreshContext();
 assert(p.ctx.analysisMeasurementCurrent());assert.equal(p.ctx.document.querySelector('#analysis-definition-save').disabled,true);
 assert(p.ctx.analysisExecutionValidatePlan().includes('未保存'));await p.ctx.analysisMeasurementAction('save');assert.equal(p.requests.length,0);
 assert(p.effects.some(e=>e[0]==='dialog-message'&&String(e[2]).includes('未保存')));
});

for(const action of ['save','trial'])for(const success of [true,false])await check(`reopen-${action}-releases-current-controls-${success}`,async()=>{
 const p=measurement();if(action==='trial')await saved(p);
 const saving=p.ctx.analysisMeasurementAction(action),index=p.requests.length-1;
 const result=action==='trial'?{trial:trial(p)}:{definition:definition(p)};
 p.ctx.analysisRunDialog.close();p.ctx.invalidateAnalysisDialog();p.ctx.analysisRunDialog.showModal();p.ctx.analysisMeasurementRender();
 assert.equal(p.ctx.document.querySelector('#analysis-definition-save').disabled,true);
 p.reply(index,success?result:{error:'old failure'},success);await saving;
 assert.equal(p.ctx.analysisMeasurement.operation,null);assert.equal(p.ctx.analysisMeasurement.trial,null);
 assert.equal(p.ctx.document.querySelector('#analysis-definition-save').disabled,false);
 assert(!p.effects.some(effect=>effect[0]==='dialog-message'&&effect[1]==='old failure'));
});

await check('reopened-dialog-waits-for-old-adoption-then-inspects',async()=>{
 const p=measurement();await tried(p);p.ctx.document.querySelector('#analysis-definition-confirm').checked=true;const reviewed=p.ctx.analysisMeasurement.trial;
 const a=p.ctx.analysisMeasurementAction('adopt');p.ctx.analysisRunDialog.close();p.ctx.invalidateAnalysisDialog();p.ctx.analysisRunDialog.showModal();
 const inspect=p.ctx.analysisMeasurementInspect();assert.equal(p.requests.length,3);p.requests[2].reject(Error('lost'));await a;await tick();assert.equal(p.requests.length,4);
 p.reply(3,{definition:{...definition(p,2,'adopted'),last_trial:reviewed}});await inspect;assert.equal(p.ctx.analysisMeasurement.adopted.status,'adopted');assert.equal(p.ctx.analysisMeasurement.operation,null);
});
console.log(JSON.stringify({scope:'Synthetic DOM and deferred-fetch only; no external calls, browser or user data',passed,presetPayloads},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
