// Original renderer/review handler in synthetic DOM. No browser or HTTP.
const fs=require('fs'),vm=require('vm'),path=require('path');
const src=fs.readFileSync(path.resolve(__dirname,'../../app/src/gurumoji/static/analysis-execution.js'),'utf8');
const extract=(a,b)=>src.slice(src.indexOf(a),src.indexOf(b,src.indexOf(a)+a.length));
function el(){return{textContent:'',hidden:false,disabled:false,style:{},classList:{toggle(){}},replaceChildren(){},append(){},setAttribute(){},querySelector(){return el()}}}
const nodes=new Map(),calls=[];
const state={status:'failed',active:false,stages:[],currentIndex:-1,settings:{allowedActions:[]},logs:[],mode:'automatic',itemId:'synthetic-A',id:'synthetic-pipeline'};
const context={analysisExecutionState:state,document:{querySelector(s){if(!nodes.has(s))nodes.set(s,el());return nodes.get(s)},createElement:el},
 analysisExecutionView:{hidden:true},analysisRunButton:el(),analysisExecutionChip:el(),analysisExecutionChipLabel:el(),analysisExecutionPercent:()=>0,
 renderAnalysisExecutionFlow(){},analysisExecutionElapsedText:()=>'',analysisExecutionStatusLabel:s=>s,
 hideAnalysisExecutionView(){calls.push('hide_execution')},openAnalysisExecutionDialog(){calls.push('open_settings')},
 async analysisExecutionRequestJson(url){calls.push(url);return{}},analysisExecutionApplyResponse(){},analysisExecutionPoll(){}};
vm.createContext(context);
vm.runInContext(extract('function renderAnalysisExecution()','function analysisExecutionSetWorkspaceVisibility('),context);
vm.runInContext(extract('async function analysisExecutionReviewPlan()','function analysisExecutionBind('),context);
(async()=>{
 const rows=[];
 for(const [status,actions]of[['failed',[]],['waiting',['cancel']],['waiting',['cancel','retry_failed']],['waiting',['cancel','retry_publication']]]){
  state.status=status;state.settings.allowedActions=actions;calls.length=0;
  vm.runInContext('renderAnalysisExecution()',context);
  await vm.runInContext('analysisExecutionReviewPlan()',context);
  rows.push({status,allowedActions:actions,button_hidden:nodes.get('#analysis-execution-review').hidden,label:nodes.get('#analysis-execution-review').textContent,effect:[...calls]});
 }
 process.stdout.write(JSON.stringify({method:'original JS render/review functions with synthetic DOM; backend allowed_actions statically verified in analysis_pipeline.py823-831',cases:rows},null,2)+'\n');
})();
