// Source-isolated function test, synthetic DOM/network only. Not a browser or API call.
const fs=require('fs'), vm=require('vm'), path=require('path');
const app=path.resolve(__dirname,'../../app');
const source=fs.readFileSync(path.join(app,'src/gurumoji/static/analysis-method-view.js'),'utf8');
const start=source.indexOf('async function runSegmentClassification(');
if(start<0)throw Error('Function missing');
const fn=source.slice(start); // function is last in this file at audited HEAD
let resolveFetch;
const requests=[], alerts=[];
const ctx={analysisState:{itemId:'synthetic-A',dirty:false,data:{item:{revision_count:1,analysis_revision:1},segment_classification:{origin:'A-old'}}},
 segmentClassificationInProgress:false,renderAnalysisWorkspace(){},invalidateAnalysisMethodOverview(){},
 document:{querySelector(){return {}}},setAlert(_,message){alerts.push(message)},createSubmissionId(){return 'synthetic-submission'},
 apiFetch(url,options){requests.push({url,body:JSON.parse(options.body)});return new Promise(r=>{resolveFetch=r})},readJsonResponse:async r=>r.payload};
vm.createContext(ctx);vm.runInContext(fn,ctx);
(async()=>{
 const pending=vm.runInContext('runSegmentClassification({useJev:false})',ctx);
 ctx.analysisState.itemId='synthetic-B';
 ctx.analysisState.data={item:{revision_count:8,analysis_revision:3},segment_classification:{origin:'B-current'}};
 resolveFetch({ok:true,payload:{segment_classification:{origin:'A-late',result:{segments:[{segment_id:'A1'}]}}}});
 const result=await pending;
 if(ctx.analysisState.itemId!=='synthetic-B'||ctx.analysisState.data.segment_classification.origin!=='A-late')throw Error('Expected boundary issue not reproduced');
 process.stdout.write(JSON.stringify({method:'original function with synthetic deferred fetch and target change; no browser or real HTTP',
  requested_item:'synthetic-A',visible_item_at_response:ctx.analysisState.itemId,current_data_classification_origin:ctx.analysisState.data.segment_classification.origin,
  current_data_revision:ctx.analysisState.data.item.revision_count,result,requests,alerts,
  caveat:'Current run control is CSS-hidden; this is a latent handler regression exposed by restoring W01. No persistence corruption or live UI reproduction is claimed.'},null,2)+'\n');
})();
