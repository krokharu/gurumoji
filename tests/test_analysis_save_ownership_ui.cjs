// Real analysis save/load handlers with synthetic deferred API responses.
// Pure Node contract test; no browser, server, network, model, or user data.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../src/gurumoji/static/app.js'),'utf8').replace(/\r\n/g,'\n');
function extract(name){const match=new RegExp(`^(?:async )?function ${name}\\(`,'m').exec(source);assert(match,name);return source.slice(match.index,source.indexOf('\n}',match.index)+2);}
const data=(id,revision=1,question=id)=>({item:{id,revision_count:revision,analysis_revision:revision},config:{research_question:question},annotations:{}});
function fixture(){
 const requests=[],effects=[];
 const node={hidden:false};
 const ctx={analysisState:{itemId:'A',data:data('A'),config:{research_question:'draft'},annotations:{},dirty:true,mode:'manual'},
  analysisSaveInProgress:false,analysisSaveOwner:null,analysisTermRunRequested:false,analysisMutationGeneration:1,analysisNavigationGeneration:1,
  analysisRequestSequence:1,analysisRequestController:null,analysisCard:{hidden:false},analysisItemSelect:null,
  preparationDirty:false,preparationDraft:null,AbortController,deepCopy:structuredClone,window:{confirm:()=>true},
  document:{querySelector:()=>node},hasUnsavedAnalysisChanges:()=>ctx.analysisState.dirty,
  setAnalysisDirty(dirty,track=true){ctx.analysisState.dirty=!!dirty;if(dirty&&track)ctx.analysisMutationGeneration++;effects.push(['dirty',ctx.analysisState.itemId,!!dirty]);},
  setAlert(_node,message,error){effects.push(['alert',ctx.analysisState.itemId,message,!!error]);},
  invalidateAnalysisMethodOverview(){effects.push(['invalidate',ctx.analysisState.itemId]);},
  renderAnalysisWorkspace(){effects.push(['render',ctx.analysisState.itemId]);},
  onContentAnalysisLoaded(){effects.push(['loaded',ctx.analysisState.itemId]);},
  updateAnalysisTarget(){},syncRouteHash(){},routeHash:()=>'',setAnalysisLoading(){},
  apiFetch(url,options={}){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});requests.push({url,options,resolve,reject});return promise;},
  readJsonResponse:async response=>response.payload,
 };
 vm.createContext(ctx);for(const name of ['captureAnalysisContext','isAnalysisContextCurrent','saveAnalysis','loadAnalysisItem'])vm.runInContext(extract(name),ctx);
 return {ctx,requests,effects,reply(index,payload,ok=true){requests[index].resolve({ok,status:ok?200:500,payload});},
  async load(id,revision=1,question=id){const task=ctx.loadAnalysisItem(id,{discardDirty:true});requests.at(-1).resolve({ok:true,payload:data(id,revision,question)});await task;},
  edit(question){ctx.analysisState.config.research_question=question;ctx.setAnalysisDirty(true);},
 };
}
const passed=[];
(async()=>{
 for(const change of ['B','ABA','reload'])for(const response of ['success','failure','rejection']){
  const h=fixture(),saving=h.ctx.saveAnalysis();
  if(change==='B'||change==='ABA')await h.load('B',3);
  if(change==='ABA'||change==='reload')await h.load('A',3,'newer-server');
  const before=structuredClone(h.ctx.analysisState);const effects=h.effects.length;
  if(response==='rejection')h.requests[0].reject(Error('old network error'));
  else h.reply(0,response==='success'?data('A',2,'old-server'):{error:'old failure'},response==='success');
  await saving;
  assert.deepEqual(h.ctx.analysisState,before,`${change}/${response}: current state changed`);
  assert(!h.effects.slice(effects).some(([kind])=>['alert','render','loaded'].includes(kind)));
  assert.equal(h.ctx.analysisSaveInProgress,false);passed.push(`${change}-${response}`);
 }
 {
  const h=fixture(),saving=h.ctx.saveAnalysis();await h.ctx.saveAnalysis();assert.equal(h.requests.length,1);
  h.reply(0,data('A',2,'saved'));await saving;
  assert.equal(h.ctx.analysisState.config.research_question,'saved');assert.equal(h.ctx.analysisState.dirty,false);
  assert.equal(h.ctx.analysisSaveInProgress,false);passed.push('current-success-and-double-click');
 }
 for(const success of [true,false]){
  const h=fixture(),saving=h.ctx.saveAnalysis();h.edit('later-draft');
  h.reply(0,success?data('A',2,'submitted-draft'):{error:'current failure'},success);await saving;
  assert.equal(h.ctx.analysisState.config.research_question,'later-draft');assert.equal(h.ctx.analysisState.dirty,true);
  assert.equal(h.ctx.analysisState.data.item.analysis_revision,success?2:1);assert.equal(h.ctx.analysisSaveInProgress,false);
  passed.push(`later-edit-${success}`);
 }
 {
  const h=fixture(),old=h.ctx.saveAnalysis();await h.load('B',3);h.edit('B-draft');
  const fresh=h.ctx.saveAnalysis();assert.equal(h.requests.length,3,'new view must be able to save while old request is pending');
  h.reply(0,{error:'old failure'},false);await old;assert.equal(h.ctx.analysisSaveInProgress,true);
  assert.equal(h.ctx.analysisState.dirty,true);assert(!h.effects.some(e=>e[0]==='alert'&&e[2]==='old failure'));
  h.reply(2,data('B',4,'B-saved'));await fresh;assert.equal(h.ctx.analysisSaveInProgress,false);
  assert.equal(h.ctx.analysisState.config.research_question,'B-saved');passed.push('old-finally-does-not-release-new-save');
 }
 for(const change of ['navigation','revision','data']){
  const h=fixture(),saving=h.ctx.saveAnalysis();
  if(change==='navigation')h.ctx.analysisNavigationGeneration++;
  else if(change==='revision')h.ctx.analysisState.data.item.analysis_revision=8;
  else h.ctx.analysisState.data=data('A',9,'fresh');
  const before=structuredClone(h.ctx.analysisState);h.reply(0,data('A',2,'old'));await saving;
  assert.deepEqual(h.ctx.analysisState,before);assert.equal(h.ctx.analysisSaveInProgress,false);passed.push(`same-item-${change}-guard`);
 }
 console.log(JSON.stringify({scope:'Original handlers, synthetic transport/DOM; browser and AT not tested',passed}));
})().catch(error=>{console.error(error);process.exitCode=1;});
