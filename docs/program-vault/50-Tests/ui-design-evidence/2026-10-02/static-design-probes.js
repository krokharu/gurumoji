// Source-isolated synthetic probes. No browser, network, app import, DB, or real data.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const root = path.resolve(__dirname, '../../app');
const source = fs.readFileSync(path.join(root, 'src/gurumoji/static/analysis-execution.js'), 'utf8');
function sliceFunction(start, next) {
  const i=source.indexOf(start), j=source.indexOf(next, i+start.length);
  if(i<0 || j<0) throw new Error('Function boundary missing');
  return source.slice(i,j);
}
function el() { return {textContent:'', hidden:false, disabled:false, style:{}, dataset:{}, className:'', classList:{toggle(){}}, replaceChildren(){}, append(){}, setAttribute(){}, querySelector(){return el();}}; }
const fields = {
  '#analysis-definition-id': {value:'synthetic_definition'},
  '#analysis-definition-name': {value:'合成の測定定義'},
  '#analysis-definition-description': {value:'合成データ用の測定説明'},
  '#analysis-definition-output': {value:'synthetic_score'},
  '#analysis-definition-trial-result': el()
};
const missing=[];
const context={document:{querySelector:s=>{if(!(s in fields)) missing.push(s);return fields[s]||null;}}, analysisExecutionMode:()=> 'manual', analysisExecutionState:{definitionRevision:0}, analysisState:{itemId:'synthetic-only'}, requests:[]};
context.analysisExecutionRequestJson=async(url,opts)=>{const body=JSON.parse(opts.body);context.requests.push({url,method:opts.method,body}); if(url.endsWith('/trials')) return {trial:{sample_size:20,valid_count:20,missing_count:0}};return {definition:{revision:context.requests.length}};};
vm.createContext(context);
vm.runInContext(sliceFunction('function analysisExecutionDefinitionFromForm(', 'function analysisExecutionSyncManualFields('),context);
vm.runInContext(sliceFunction('async function analysisExecutionPrepareDefinition(', 'async function startAnalysisExecution('),context);
const result={method:'source-isolated Node functions with synthetic DOM stubs; not a browser or actual app runtime',manual_definition:vm.runInContext('analysisExecutionDefinitionFromForm()',context),missing_selectors:[...new Set(missing)]};
(async()=>{
  await vm.runInContext('analysisExecutionPrepareDefinition()',context);
  result.trial_adoption_requests=context.requests;
  const nodes = new Map();
  const dom={querySelector:s=>{if(!nodes.has(s))nodes.set(s,el());return nodes.get(s);},createElement:()=>el()};
  const state={status:'failed',active:false,stages:[],currentIndex:0,settings:{progress:25,error:'Synthetic execution failure',allowedActions:['retry']},logs:[],mode:'automatic'};
  const c={document:dom,analysisExecutionState:state,analysisExecutionView:{hidden:true},analysisExecutionPercent:()=>25,renderAnalysisExecutionFlow(){},analysisExecutionElapsedText:()=> '0:02',analysisExecutionStatusLabel:s=>s,analysisRunButton:el(),analysisExecutionChip:el(),analysisExecutionChipLabel:el()};
  vm.createContext(c);
  vm.runInContext(sliceFunction('function renderAnalysisExecution()','function analysisExecutionSetWorkspaceVisibility('),c);
  result.execution_states=[];
  for(const status of ['failed','waiting','cancelled','completed','cancelling','running']){
    state.status=status;state.active=['running','cancelling'].includes(status);state.settings.error = ['failed','waiting'].includes(status) ? 'Synthetic execution failure' : '';
    vm.runInContext('renderAnalysisExecution()',c);
    result.execution_states.push({status,heading:nodes.get('#analysis-execution-title').textContent,message:nodes.get('#analysis-execution-message').textContent,results_button_hidden:nodes.get('#analysis-execution-results').hidden,review_button_hidden:nodes.get('#analysis-execution-review').hidden,review_label:nodes.get('#analysis-execution-review').textContent});
  }
  console.log(JSON.stringify(result,null,2));
})();
