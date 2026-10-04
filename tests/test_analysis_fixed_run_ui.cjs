// Original JS with synthetic DOM and deferred fetch only. GUI/AT is not tested.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'src/gurumoji/static/analysis-storage.js'),'utf8');
function node(tag='div') {
 return {tag,children:[],attrs:{},listeners:{},dataset:{},open:false,disabled:false,_text:'',
  set innerHTML(_){throw Error('Saved data must not become HTML');},
  set textContent(v){this._text=String(v??'');this.children=[];},get textContent(){return this._text+this.children.map(n=>n.textContent??'').join(' ');},
  append(...n){this.children.push(...n);},replaceChildren(...n){this._text='';this.children=n;},
  setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,f){this.listeners[k]=f;},
  showModal(){this.open=true;},close(){this.open=false;this.listeners.close?.();},focus(){this.focused=true;},
  classList:{add(){}},
 };
}
function make(){
 const requests=[],effects=[],ctx={analysisState:{itemId:'A',data:{id:'A'},dirty:false},analysisNavigationGeneration:0,
 document:{body:node('body'),querySelectorAll(){return[];}},Map,URLSearchParams,crypto:{randomUUID:()=> 'uuid'},
 captureAnalysisContext(){return {itemId:ctx.analysisState.itemId,data:ctx.analysisState.data,navigation:ctx.analysisNavigationGeneration};},
 isAnalysisContextCurrent(c){return c.itemId===ctx.analysisState.itemId&&c.data===ctx.analysisState.data&&c.navigation===ctx.analysisNavigationGeneration;},
 analysisElement(tag,cls='',text=''){const n=node(tag);n.className=cls;n.textContent=text;return n;},
 contentButton(label,action,cls){const n=ctx.analysisElement('button',cls,label);n.type='button';n.listeners.click=action;return n;},
 apiFetch(url,options){let resolve,reject;const p=new Promise((a,b)=>{resolve=a;reject=b;});requests.push({url,options,resolve,reject});return p;},
 readJsonResponse:async r=>r.payload,loadAnalysisItem(){throw Error('live calculation');},loadAnalysisStorage(){throw Error('history is not the result');}
 };
 vm.createContext(ctx);vm.runInContext(source,ctx);
 return {ctx,requests,effects,view:()=>ctx.analysisFixedViewerElements(),
  navigate(item){ctx.analysisState={itemId:item,data:{id:item}};ctx.analysisNavigationGeneration++;},
  reply(i,payload,ok=true){requests[i].resolve({ok,payload});}};
}
function payload(item='A',id='r1'){return {run:{id,item_id:item,kind:'milestone_analysis',status:'completed',created_at:'saved-date',source_revision:2,analysis_revision:3,artifacts:[]},integrity:'verified',provenance:{},current_input:{stale:true}};}
function publication(){const roles=['research','input','orchestrator','visualization'];return {id:'r1',kind:'milestone_analysis',status:'completed',fingerprint:'fp',publication_attempts:[{attempt_id:'attempt',package_hash:'fp',status:'completed',requested:['input','orchestrator','visualization'],effective:roles,executed:roles,outcomes:Object.fromEntries(roles.map(r=>[r,{status:'published'}]))}],publication_records:roles.map(target_role=>({target_role,status:'published',result_run_id:'r1',package_hash:'fp'}))};}
const passed=[];async function check(name,fn){await fn();passed.push(name);}
(async()=>{
 await check('exact-readonly-get-safe-render',async()=>{const p=make();const done=p.ctx.openFixedAnalysisRun('A','r1');assert(p.view().dialog.open);assert(p.view().close.focused);assert.equal(p.requests[0].url,'/api/library/A/analysis/runs/r1');assert(!p.requests[0].options.method);p.reply(0,payload());await done;assert(p.view().body.textContent.includes('元データ 2版'));assert(p.view().body.textContent.includes('現在入力は保存時と異なります'));assert(p.view().identity.textContent.includes('固定run r1'));});
 for(const path of ['B','ABA','run-change','close-reopen'])for(const failure of [false,true])await check(`${path}-late-${failure?'failure':'success'}`,async()=>{
  const p=make();const first=p.ctx.openFixedAnalysisRun('A','r1');let second;
  if(path==='B'||path==='ABA'){p.navigate('B');if(path==='ABA')p.navigate('A');second=p.ctx.openFixedAnalysisRun(p.ctx.analysisState.itemId,'r2');}
  else if(path==='run-change')second=p.ctx.openFixedAnalysisRun('A','r2');
  else {p.view().dialog.close();second=p.ctx.openFixedAnalysisRun('A','r2');}
  p.reply(1,payload(p.ctx.analysisState.itemId,'r2'));await second;const before=p.view().body.textContent;
  p.reply(0,failure?{error:'OLD ERROR'}:payload(),!failure);await first;
  assert.equal(p.view().body.textContent,before);assert(p.view().identity.textContent.includes('r2'));assert(!p.view().status.textContent.includes('OLD'));
 });
 await check('close-in-flight-never-reopens',async()=>{const p=make();const first=p.ctx.openFixedAnalysisRun('A','r1');p.view().dialog.close();p.reply(0,payload());await first;assert(!p.view().dialog.open);assert.equal(p.view().body.children.length,0);});
 await check('cancel-invalidates-in-flight',async()=>{const p=make();const first=p.ctx.openFixedAnalysisRun('A','r1');p.view().dialog.listeners.cancel();p.reply(0,payload());await first;assert.equal(p.view().body.children.length,0);});
 await check('synchronous-close-and-late-close-event-do-not-invalidate-reopen',async()=>{
  const p=make();const first=p.ctx.openFixedAnalysisRun('A','r1');
  assert.equal(p.ctx.closeFixedAnalysisViewer(),true);assert.equal(p.ctx.closeFixedAnalysisViewer(),false);
  const second=p.ctx.openFixedAnalysisRun('A','r2');
  p.view().dialog.listeners.close(); // A queued native close event from the previous opening.
  p.reply(1,payload('A','r2'));await second;assert(p.view().body.textContent.includes('元データ 2版'));
  const current=p.view().body.textContent;p.reply(0,payload());await first;assert.equal(p.view().body.textContent,current);
 });
 for(const phase of ['lookup','preview','button'])await check(`same-context-live-save-${phase}`,async()=>{
  const p=make(),saved=payload();saved.run.artifacts=[{id:'f1',name:'result.json',media_type:'application/json',bytes:1}];
  const loading=p.ctx.openFixedAnalysisRun('A','r1');
  if(phase==='lookup')p.ctx.analysisState.data={id:'A',revision:2};
  p.reply(0,saved);await loading;assert(p.view().body.textContent.includes('元データ 2版'));
  const find=n=>n.tag==='button'&&n.textContent==='result.json を読む'?n:n.children.map(find).find(Boolean);
  const button=find(p.view().body);assert(button);
  if(phase==='button')p.ctx.analysisState.data={id:'A',revision:2};
  const reading=button.listeners.click();assert.equal(p.requests.length,2);
  if(phase==='preview')p.ctx.analysisState.data={id:'A',revision:2};
  p.reply(1,{preview:{artifact_id:'f1',run_id:'r1',format:'text',text:'SAVED-ONLY'}});await reading;
  assert(p.view().body.textContent.includes('SAVED-ONLY'));assert(!p.view().body.textContent.includes('読み取っています'));
 });
 await check('wrong-run-response-is-error-not-fallback',async()=>{const p=make();const first=p.ctx.openFixedAnalysisRun('A','r1');p.reply(0,payload('A','wrong'));await first;assert(p.view().status.textContent.includes('確認できません'));assert.equal(p.requests.length,1);});
 await check('broken-package-no-fallback-or-downloads',async()=>{const p=make();const first=p.ctx.openFixedAnalysisRun('A','r1');p.reply(0,{error:'欠落・停止'},false);await first;assert.equal(p.view().status.textContent,'欠落・停止');assert.equal(p.view().body.children.length,0);assert.equal(p.requests.length,1);});
 await check('saved-json-is-text-with-null-zero-empty',async()=>{const p=make(),host=node();p.ctx.renderFixedAnalysisPreview(host,{name:'result.json'},{run_id:'r1',format:'text',text:'{"missing":null,"zero":0,"empty":"","text":"<script>alert(1)</script>"}',truncated:false});assert(host.textContent.includes('<script>'));assert(host.textContent.includes('"missing":null'));assert(host.textContent.includes('"zero":0'));assert(host.textContent.includes('"empty":""'));});
 await check('table-labels-count-truncation-and-ambiguous-blank',async()=>{const p=make(),host=node();p.ctx.renderFixedAnalysisPreview(host,{name:'tables/data.csv'},{run_id:'r1',format:'table',columns:['id','value'],rows:[['missing',''],['zero','0']],total_rows:100,shown_rows:2,total_columns:30,truncated:true});assert(host.textContent.includes('全100行中2行'));assert(host.textContent.includes('一部を省略'));assert(host.textContent.includes('nullと空文字を区別できません'));});
 for (const scenario of ['complete','legacy','missing-executed','research-conflict','wrong-package','wrong-record','empty','blocked'])await check('four-writers-'+scenario,async()=>{
  const p=make(),run=publication();const latest=run.publication_attempts[0];
  if(scenario==='legacy')delete run.publication_attempts;
  if(scenario==='missing-executed')delete latest.executed;
  if(scenario==='research-conflict'){latest.status='incomplete';latest.outcomes.research={status:'conflict',error:'saved conflict'};}
  if(scenario==='wrong-package')latest.package_hash='wrong';
  if(scenario==='wrong-record')run.publication_records[0].package_hash='wrong';
  if(scenario==='empty')Object.assign(latest,{status:'not_selected',requested:[],effective:[],executed:[],outcomes:{}});
  if(scenario==='blocked')Object.assign(latest,{status:'blocked',executed:[]});
  const result=p.ctx.analysisSavedPublicationEvidence(run);assert.equal(result.complete,['complete','wrong-record'].includes(scenario));
  assert.equal(result.notSelected,scenario==='empty');assert.equal(result.blocked,scenario==='blocked');
  if(['legacy','empty','blocked','wrong-record','wrong-package'].includes(scenario))assert(!result.retryable);
  if(scenario==='wrong-record')assert(result.workflowDisagrees);
  const text=p.ctx.buildSavedPublicationEvidence(run).textContent;
  for(const name of ['ResearchVault','InputVault','OrchestratorVault','VisualizationVault'])assert(text.includes(name));
  assert(!text.includes('ResearchVaultは保存済み'));
 });
 for(const scenario of ['wrong-hash','missing-hash','matching-hash'])await check('attempt-empty-scope-'+scenario,async()=>{
  const p=make(),run=publication();run.publication_records=[];const latest=run.publication_attempts[0];
  Object.assign(latest,{status:'not_selected',requested:[],effective:[],executed:[],outcomes:{}});
  if(scenario==='wrong-hash')latest.package_hash='other';
  if(scenario==='missing-hash'){delete run.fingerprint;delete latest.package_hash;}
  const evidence=p.ctx.analysisSavedPublicationEvidence(run);
  assert.equal(evidence.notSelected,scenario==='matching-hash');assert(!evidence.complete);assert(!evidence.retryable);
 });
 for(const scenario of ['verified-empty','ledger-empty','missing','partial','wrong-run','wrong-hash'])await check('empty-scope-'+scenario,async()=>{
  const p=make(),run=publication();delete run.publication_attempts;run.publication_records.forEach(r=>r.status='not_selected');
  if(scenario==='verified-empty'){run.saved_publication_targets=[];run.publication_records=[];}
  if(scenario==='missing')run.publication_records=[];
  if(scenario==='partial')run.publication_records.pop();
  if(scenario==='wrong-run')run.publication_records[0].result_run_id='other';
  if(scenario==='wrong-hash')run.publication_records[0].package_hash='other';
  const evidence=p.ctx.analysisSavedPublicationEvidence(run);
  assert.equal(evidence.notSelected,['verified-empty','ledger-empty'].includes(scenario));
  assert(!evidence.complete);assert(!evidence.retryable);
  const text=p.ctx.buildSavedPublicationEvidence(run).textContent;
  if(scenario==='ledger-empty')assert(text.includes('台帳上'));
 });
 await check('readable-saved-summary-and-definition-version',async()=>{
  const p=make();const host=p.ctx.buildFixedAnalysisSummary({methods:[{title:'保存手法',status:'not_run',analysis_unit:null,summaries:[{title:'保存集計',text:'有効N=0'}],findings:[],limitations:['保存時の制約']}],definitions:[{definition_id:'fixed-id',version:'7',name:'固定定義',output_column:'column',measurement_rule:'text_length',method:'descriptive'}],truncated:true});
  assert(host.textContent.includes('未実行'));assert(host.textContent.includes('分析単位: 不明'));assert(host.textContent.includes('有効N=0'));assert(host.textContent.includes('保存時の制約'));assert(host.textContent.includes('ID fixed-id / 7版'));assert(host.textContent.includes('一部を省略'));
 });
 await check('unknown-saved-method-state-never-completed',async()=>{
  const p=make();const host=p.ctx.buildFixedAnalysisSummary({methods:[{title:'Unknown',status:null,analysis_unit:null}]});assert(host.textContent.includes('保存時の状態: 不明'));assert(!host.textContent.includes('計算済み'));
 });
 await check('saved-computation-registry-and-global-versions-remain-independent',async()=>{
  const p=make();const summary={methods:[{title:'A',method_version:'registry-v9',method_version_status:'recorded',engine_version:'engine-v4',engine_version_status:'recorded'}],algorithms:[{name:'automatic',version:'global-v6',status:'recorded'}],algorithms_status:'recorded'};
  const before=JSON.stringify(summary);const host=p.ctx.buildFixedAnalysisSummary(summary);
  assert(host.textContent.includes('保存した計算版: engine-v4'));assert(host.textContent.includes('手法registry版: registry-v9'));
  assert(host.textContent.includes('保存した算法一覧'));assert(host.textContent.includes('automatic: global-v6'));assert.equal(JSON.stringify(summary),before);
 });
 for(const [status,value,expected] of [['missing',null,'記録なし'],['recorded','0','0'],['recorded',0,'0'],['unsupported',null,'表示できない形式'],['recorded','','省略（全ファイルで確認）']])await check(`saved-version-${status}-${value}`,async()=>{
  const p=make(),host=p.ctx.buildFixedAnalysisSummary({methods:[{method_version:value,method_version_status:status,engine_version:value,engine_version_status:status}],algorithms:[{name:'__proto__',version:value,status}]});
  assert(host.textContent.includes(`保存した計算版: ${expected}`));assert(host.textContent.includes(`手法registry版: ${expected}`));assert(host.textContent.includes(`__proto__: ${expected}`));
 });
 await check('global-version-does-not-fill-missing-method-and-hostile-text-is-literal',async()=>{
  const p=make(),host=p.ctx.buildFixedAnalysisSummary({methods:[{method_version:'<img src=x onerror=1>'}],algorithms:[{name:'automatic',version:'saved-only',status:'recorded'}]});
  assert(host.textContent.includes('保存した計算版: 記録なし'));assert(host.textContent.includes('手法registry版: <img src=x onerror=1>'));
  assert(host.textContent.includes('automatic: saved-only'));assert(!host.textContent.includes('保存した計算版: saved-only'));
 });
 await check('file-catalog-page-bounded-and-full-zip',async()=>{const p=make(),data=payload();data.run.artifacts=Array.from({length:101},(_,i)=>({id:'f'+i,name:'tables/t'+i+'.csv',rows:500,bytes:100,sha256:'abc'}));const host=node();p.ctx.renderFixedAnalysisRun(host,data,{itemId:'A',runId:'r1',current:()=>true});const buttons=[];function visit(n){if(n.tag==='button')buttons.push(n);n.children.forEach(visit);}visit(host);assert.equal(buttons.filter(b=>b.textContent.endsWith('を読む')).length,20);assert(host.textContent.includes('全101ファイル'));assert(host.textContent.includes('全ファイルをZIP'));});
 console.log(JSON.stringify({scope:'Node synthetic DOM/deferred fetch; no GUI, AT, browser or network',passed},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
