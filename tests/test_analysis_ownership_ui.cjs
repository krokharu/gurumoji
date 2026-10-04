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
    analysisExecutionState:{id:'pipeline-A',itemId:'A',status:'running',active:true,resuming:false,cancelRequested:false,logs:[],settings:{allowedActions:['retry_failed']},generation:0},
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
  ctx.analysisExecutionRequestJson=async(url,options)=>{const r=await ctx.apiFetch(url,options);if(!r.ok)throw Error(r.payload.error||'synthetic error');return r.payload;};
  vm.createContext(ctx);
  const load=(f,...names)=>names.forEach(n=>vm.runInContext(extract(f,n),ctx));
  load('app.js','captureAnalysisContext','isAnalysisContextCurrent','segmentClassificationBusy');
  load('analysis-execution.js','captureAnalysisDialog','captureAnalysisRun','invalidateAnalysisDialog','closeAnalysisExecutionDialog','analysisExecutionPublicationEvidence','analysisExecutionRetryAction');
  load('analysis-content.js','contentAnalysisState');
  const navigate=(id,origin,rev=2,executed=true)=>{ctx.analysisNavigationGeneration++;ctx.analysisState.itemId=id;ctx.analysisState.data=data(origin,rev,executed);};
  const reply=(i,payload,ok=true)=>requests[i].resolve({ok,payload,status:ok?200:500});
  return {ctx,load,navigate,reply,requests,effects,storage,nodes};
}

const assert = require('node:assert/strict');
const tick=()=>new Promise(r=>setImmediate(r));
const passed=[];
async function check(name, work) { const timer=setTimeout(()=>{console.error('Unresolved test: '+name);process.exit(1);},2000);try {await work();passed.push(name);} finally {clearTimeout(timer);} }
(async()=>{
for (const route of ['B','ABA']) for (const failure of [false,true]) {
 await check(`classification-${route}-${failure}`,async()=>{
  const p=make();p.load('analysis-method-view.js','runSegmentClassification');
  const a=p.ctx.runSegmentClassification({useJev:false});
  p.navigate('B','B-new');if(route==='ABA')p.navigate('A','A-new');
  const origin=p.ctx.analysisState.data.segment_classification.origin, before=p.effects.length;
  p.reply(0,failure?{error:'old error'}:{segment_classification:{origin:'old'}},!failure);await a;
  assert.equal(p.ctx.analysisState.data.segment_classification.origin,origin);
  assert(p.effects.slice(before).every(effect => route === 'ABA' && effect[0] === 'render-workspace'));
 });
}
await check('classification-per-item-and-double-click',async()=>{
 const p=make();p.load('analysis-method-view.js','runSegmentClassification');
 const a=p.ctx.runSegmentClassification({useJev:false});await p.ctx.runSegmentClassification({useJev:false});assert.equal(p.requests.length,1);
 p.navigate('B','B-new');const b=p.ctx.runSegmentClassification({useJev:false});assert.equal(p.requests.length,2);
 p.reply(0,{segment_classification:{origin:'old'}});await a;assert(p.ctx.segmentClassificationBusy());
 p.reply(1,{segment_classification:{origin:'new'}});await b;assert(!p.ctx.segmentClassificationBusy());
});
await check('overview-new-data-replaces-loading-owner',async()=>{
 const p=make();p.load('analysis-method-view.js','analysisMethodState','invalidateAnalysisMethodOverview','loadAnalysisMethodOverview');
 const a=p.ctx.loadAnalysisMethodOverview();p.navigate('A','new');p.ctx.invalidateAnalysisMethodOverview();const b=p.ctx.loadAnalysisMethodOverview();
 p.reply(0,{origin:'old',methods:[]});await a;assert.equal(p.ctx.analysisState.methods.loading,true);
 p.reply(1,{origin:'new',methods:[]});await b;assert.equal(p.ctx.analysisState.methods.data.origin,'new');
});
for (const fn of ['startTransformerAnalysis','startContentInsights','cancelTransformerAnalysis','cancelContentInsights','pollTransformerAnalysis','pollContentInsights','searchTransformerSemantics','searchContentKwic']) {
 for (const failure of [false,true]) await check(`${fn}-ABA-${failure}`,async()=>{
 const p=make();p.load('analysis-content.js',fn);const state=p.ctx.contentAnalysisState();
 state.run={request_id:'run'};state.transformerRun={request_id:'run'};state.query='word';state.semanticQuery='word';
 const a=p.ctx[fn]();assert.equal(p.requests.length,1);p.navigate('B','B-new');p.navigate('A','A-new');const newer=p.ctx.contentAnalysisState(),before=p.effects.length;
 p.reply(0,failure?{error:'old'}:{run:{origin:'old'},hits:[],fingerprint:'shared-fingerprint'},!failure);await a;
 assert.equal(p.effects.length,before);assert.equal(newer.run,null);assert.equal(newer.transformerRun,null);
 });
}
await check('pipeline-preview-navigation-stops-post',async()=>{
 const p=make();p.load('analysis-execution.js','startAnalysisExecution','analysisExecutionApplyResponse');
 const a=p.ctx.startAnalysisExecution();await tick();assert.equal(p.requests.length,1);p.navigate('B','B-new');p.reply(0,{});await a;assert.equal(p.requests.length,1);
});
await check('pipeline-submitted-A-response-stays-A-without-navigation',async()=>{
 const p=make();p.ctx.analysisExecutionPoll=()=>{};p.load('analysis-execution.js','startAnalysisExecution','analysisExecutionApplyResponse');
 const a=p.ctx.startAnalysisExecution();await tick();p.reply(0,{});await tick();p.navigate('B','B-new');p.reply(1,{pipeline_id:'new-A',status:'completed',allowed_actions:[],milestones:[],events:[],generation:0});await a;
 assert.equal(p.ctx.analysisExecutionState.itemId,'A');assert.equal(p.ctx.analysisState.itemId,'B');assert(!p.effects.some(e=>e[0]==='load-item'||e[0]==='show-execution'));
});
for(const fn of ['analysisExecutionPoll','cancelAnalysisExecution','analysisExecutionReviewPlan']) for(const failure of [false,true]) await check(`${fn}-replaced-run-${failure}`,async()=>{
 const p=make();p.load('analysis-execution.js',fn,'analysisExecutionApplyResponse');const a=p.ctx[fn]();assert.equal(p.requests.length,1);
 p.ctx.analysisExecutionState.id='new-B';p.ctx.analysisExecutionState.itemId='B';const before=p.effects.length;
 p.reply(0,failure?{error:'old'}:{pipeline_id:'pipeline-A',status:'completed',allowed_actions:[],milestones:[],events:[]},!failure);await a;
 assert.equal(p.ctx.analysisExecutionState.status,'running');assert.equal(p.effects.length,before);
});
for(const change of ['ABA','close','objective']) await check(`advisor-${change}`,async()=>{
 const p=make();p.load('analysis-execution.js','analysisAdvisorPropose','analysisAdvisorClearProposal');const a=p.ctx.analysisAdvisorPropose();
 if(change==='ABA'){p.navigate('B','B');p.navigate('A','A-new');}else if(change==='close'){p.ctx.analysisRunDialog.close();p.ctx.invalidateAnalysisDialog();}else{p.ctx.analysisAdvisorObjective.value='new';p.ctx.analysisAdvisorClearProposal();}
 const before=p.effects.length;p.reply(0,{proposal:{origin:'old',provider:'transformer',checks:[]}});await a;assert.equal(p.ctx.analysisPlanningProposal,null);assert.equal(p.effects.length,before);
});
await check('same-item-user-input-preserved',async()=>{
 const p=make(),state=p.ctx.contentAnalysisState();Object.assign(state,{query:'user query',provider:'google',maxTopics:12,semanticQuery:'intent'});
 p.navigate('B','B');p.ctx.contentAnalysisState();p.navigate('A','A-new');const returned=p.ctx.contentAnalysisState();
 assert.equal(returned.query,'user query');assert.equal(returned.provider,'google');assert.equal(returned.maxTopics,12);assert.equal(returned.semanticQuery,'intent');assert.equal(returned.run,null);
});
for(const fn of ['cancelTransformerAnalysis','cancelContentInsights']) await check(`${fn}-new-run-same-context`,async()=>{
 const p=make();p.load('analysis-content.js',fn);const state=p.ctx.contentAnalysisState();const field=fn==='cancelTransformerAnalysis'?'transformerRun':'run';state[field]={request_id:'R1'};
 const a=p.ctx[fn]();await p.ctx[fn]();assert.equal(p.requests.length,1);state[field]={request_id:'R2'};const before=p.effects.length;
 p.reply(0,{error:'old R1 error'},false);await a;assert.equal(p.effects.length,before);assert.equal(state.transformerError,'');assert.equal(state.aiError,'');
});

await check('context-invalidated-by-in-place-revision-and-preparation-edits',async()=>{
 const p=make();let context=p.ctx.captureAnalysisContext();p.ctx.analysisState.data.item.analysis_revision++;assert.equal(p.ctx.isAnalysisContextCurrent(context),false);
 context=p.ctx.captureAnalysisContext();p.ctx.analysisMutationGeneration++;assert.equal(p.ctx.isAnalysisContextCurrent(context),false);
});
await check('unsaved-preparation-navigation-rejected',async()=>{
 const p=make();Object.assign(p.ctx,{resultCard:null,currentJobDirty:false,currentJob:null,speakerRegistryCard:null,speakerRegistryDirty:false,analysisCard:{hidden:false},preparationDirty:true});
 p.ctx.window.confirm=()=>false;p.load('app.js','hasUnsavedAnalysisChanges','confirmLeave');assert.equal(p.ctx.confirmLeave({target:'new'}),false);
});
await check('return-to-same-item-refreshes-controls-and-hides-old-run-pane',async()=>{
 const p=make();Object.assign(p.ctx,{analysisCard:{hidden:false},analysisCatalogLoaded:true,analysisItemSelect:{},onContentAnalysisLoaded:()=>p.effects.push(['content-loaded'])});p.ctx.document.querySelector('#analysis-execution-view').hidden=false;
 p.load('app.js','loadAnalysisView');p.ctx.loadAnalysisView('A');assert.equal(p.ctx.document.querySelector('#analysis-execution-view').hidden,true);assert(p.effects.some(e=>e[0]==='content-loaded'));assert(p.effects.some(e=>e[0]==='render-workspace'));
});
await check('result-button-opens-exact-fixed-run-without-live-load',async()=>{
 const p=make();p.ctx.analysisExecutionState.settings.resultRun={id:'saved-run-A',status:'completed'};
 p.ctx.openFixedAnalysisRun=async(item,run)=>p.effects.push(['fixed-run',item,run]);
 p.load('analysis-execution.js','analysisExecutionOpenResults');
 await p.ctx.analysisExecutionOpenResults();
 assert(p.effects.some(e=>e[0]==='fixed-run'&&e[1]==='A'&&e[2]==='saved-run-A'));
 assert(!p.effects.some(e=>['load-item','load-storage'].includes(e[0])));
});
console.log(JSON.stringify({scope:'Pure Node synthetic deferred-fetch/DOM; no browser, real API, models or user data',passed},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
