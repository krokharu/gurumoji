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
function node(value = '') { return {value, checked:false, disabled:false, open:true, hidden:false, children:[], dataset:{}, style:{}, classList:{toggle(){}}, setAttribute(){}, querySelector(){return null;},
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
  load('analysis-execution.js','captureAnalysisDialog','captureAnalysisRun','invalidateAnalysisDialog','analysisExecutionPublicationEvidence','analysisExecutionRetryAction');
  load('analysis-content.js','contentAnalysisState');
  const navigate=(id,origin,rev=2,executed=true)=>{ctx.analysisNavigationGeneration++;ctx.analysisState.itemId=id;ctx.analysisState.data=data(origin,rev,executed);};
  const reply=(i,payload,ok=true)=>requests[i].resolve({ok,payload,status:ok?200:500});
  return {ctx,load,navigate,reply,requests,effects,storage,nodes};
}


const assert=require('node:assert/strict');const passed=[];
function setup(status,settings={}) {
 const p=make();Object.assign(p.ctx.analysisExecutionState,{status,stages:[],startedAt:0,settings});
 Object.assign(p.ctx,{analysisExecutionView:null,analysisRunButton:null,analysisExecutionChip:null,analysisExecutionChipLabel:null,analysisExecutionElapsedText:()=>'',renderAnalysisExecutionFlow:()=>{}});
 p.load('analysis-execution.js','analysisExecutionPublicationEvidence','analysisExecutionRetryAction','analysisExecutionHeadline','renderAnalysisPublicationEvidence','analysisExecutionStatusLabel','analysisExecutionPercent','renderAnalysisExecution');return p;
}
const roles=['research','input','orchestrator','visualization'];
const complete={attempt_id:'attempt-1',status:'completed',effective:roles,executed:roles,outcomes:Object.fromEntries(roles.map(r=>[r,{status:'published'}])),package_hash:'fixed'};
for(const [status,label] of Object.entries({accepted:'受け付け',running:'実行しています',waiting:'待っています',failed:'失敗',cancelling:'中止を待って',cancelled:'中止しました',completed:'処理が完了',mystery:'確認できません'})) {
 const p=setup(status);p.ctx.renderAnalysisExecution();assert(p.ctx.document.querySelector('#analysis-execution-title').textContent.includes(label));assert.equal(p.ctx.document.querySelector('#analysis-execution-review').hidden,true);passed.push(`headline-${status}`);
}
for(const [name,settings,expected] of [
 ['four-writers-complete',{publications:roles.map(r=>({target_role:r,status:'published'})),resultRun:{publication_attempts:[complete]}},true],
 ['research-conflict',{publications:roles.map(r=>({target_role:r,status:r==='research'?'conflict':'published'})),resultRun:{publication_attempts:[complete]}},false],
 ['legacy-no-attempt',{publications:roles.map(r=>({target_role:r,status:'published'}))},false],
 ['three-writers-only',{publications:roles.map(r=>({target_role:r,status:'published'})),resultRun:{publication_attempts:[{...complete,executed:roles.slice(1)}]}},false]
]) {const p=setup('completed',settings);assert.equal(p.ctx.analysisExecutionPublicationEvidence().complete,expected);p.ctx.renderAnalysisExecution();passed.push(name);}
for(const [name,settings,action] of [
 ['retry-failed',{allowedActions:['retry_failed']},'retry_failed'],
 ['retry-publication',{allowedActions:['retry_publication']},'retry_publication'],
 ['unknown-action',{allowedActions:['retry_whatever']},''],
 ['blocked-recovery',{allowedActions:['retry_failed'],recovery:{mode:'blocked',reason_code:'limit'}},''],
 ['missing-package',{allowedActions:['retry_publication'],resultRun:{publication_attempts:[{status:'blocked',executed:[]}]}},'']
]) {const p=setup('waiting',settings);assert.equal(p.ctx.analysisExecutionRetryAction(),action);p.ctx.renderAnalysisExecution();assert.equal(p.ctx.document.querySelector('#analysis-execution-review').hidden,!action);passed.push(name);}

for(const [name,settings,expected] of [
 ['legacy-published-is-unverified',{publications:roles.map(r=>({target_role:r,status:'published'}))},'台帳上published（書出し未確認）'],
 ['missing-executed-is-unknown',{publications:roles.map(r=>({target_role:r,status:'pending'})),resultRun:{publication_attempts:[{status:'publishing'}]}},'writer実行記録不明'],
 ['publishing-is-known',{publications:roles.map(r=>({target_role:r,status:'publishing'}))},'書出し中']
]) {const p=setup('waiting',settings);p.ctx.renderAnalysisExecution();const list=p.ctx.document.querySelector('#analysis-execution-publications').children[1];assert(list.children.every(row=>row.textContent.includes(expected)));passed.push(name);}
for (const pipelineStatus of ['waiting','failed','completed']) for (const packageState of ['completed','writing','failed','absent']) {
 const settings={resultRun:packageState==='absent'?null:{id:'stored-run',status:packageState}};
 const p=setup(pipelineStatus,settings);p.ctx.renderAnalysisExecution();
 assert.equal(p.nodes.get('#analysis-execution-results').hidden,packageState!=='completed');
 passed.push(`saved-result-entry-${pipelineStatus}-${packageState}`);
}
console.log(JSON.stringify({scope:'Pure synthetic DOM/status fixtures; no server or browser',passed},null,2));
