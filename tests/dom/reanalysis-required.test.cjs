'use strict';
// 画面と応答は合成データだけで検証する。
const test=require('node:test');
const assert=require('node:assert/strict');
const {createHarness}=require('./harness.cjs');
const node=(h,id)=>h.document.getElementById(`orchestration-${id}`);
const pending=(h,suffix,method='GET')=>{const r=h.requests.findLast(x=>!x.settled&&new URL(x.url,"https://gurumoji.invalid").pathname.endsWith(suffix)&&(x.options.method||'GET')===method);assert(r,`${method} ${suffix}`);return r;};
const source=(id,summary='保存済みの所見')=>({source:{source_analysis_id:id,source_run_id:'run_original',source_result_id:id.startsWith('result_')?id:'result_original',original_question:'元の問い',source_revision:2,analysis_revision:3,input_hash:'input_hash',raw_hash:'raw_hash',content:{summary}}});
const run=(overrides={})=>({run_id:'run_original',analysis_result_id:'result_original',item_id:'A',status:'completed',phase:'completed',iteration:1,source_revision:2,config:{question:'元の問い'},usage:{calls:1},allowed_actions:[],roles:[],tasks:[],results:[],events:[],...overrides});
function input(h,id,value){node(h,id).value=value;node(h,id).dispatchEvent(new h.w.Event('input',{bubbles:true}));}
async function setup(t){
 const h=await createHarness();const originalReply=h.reply;h.reply=(request,data,status=200)=>{const cursor=new URL(request.url,"https://gurumoji.invalid").searchParams.get("events_after");if(cursor!==null&&data.run&&!data.run.events_reset)data={...data,run:{...data.run,events:(data.run.events||[]).filter(event=>event.seq>Number(cursor))}};return originalReply(request,data,status);};t.after(()=>h.close());
 h.fixture({itemId:'A',data:{item:{id:'A',source_name:'合成会話A',revision_count:2,analysis_revision:3},segments:[]},config:{},annotations:{},dirty:false});
 h.evaluate('Object.assign(analysisState,window.fixture);analysisCard.hidden=false;document.body.dataset.view="analysis"');
 h.click('#analysis-run-settings-button');h.click('#orchestration-open');input(h,'question','新しい問い');return h;
}
function load(h,id){input(h,'source-analysis-id',id);h.click('#orchestration-source-load');return pending(h,`/reanalysis/source/${id}`);}

test('実行と結果IDを表示・コピーし、参照結果と追加指示・必須手法を新規runへ送る',async t=>{
 const h=await setup(t);let copied=[];Object.defineProperty(h.w.navigator,'clipboard',{value:{writeText:async value=>copied.push(value)}});
 h.fixture(run());h.evaluate('orchestrationAdopt(window.fixture,"A");showAnalysisOrchestration()');
 h.reply(pending(h,'/orchestration/run_original'),{run:run()});await h.flush();
 assert.match(node(h,'run-identity').textContent,/run_original/);assert.match(node(h,'result-identity').textContent,/result_original/);
 h.click('#orchestration-copy-run');h.click('#orchestration-copy-result');await h.flush();assert.deepEqual(copied,['run_original','result_original']);
 h.click('#orchestration-reanalyze');const lookup=pending(h,'/reanalysis/source/result_original');h.reply(lookup,source('result_original'));await h.flush();
 assert.equal(node(h,'source-analysis-id').value,'result_original');assert.equal(node(h,'source-preview').hidden,false);
 for(const text of ['元の問い','run_original','result_original','保存済みの所見'])assert.ok(node(h,'source-preview').textContent.includes(text));
 input(h,'question','新しい問い');input(h,'human-prompt','追加で反例を確認');
 const methods=[...h.document.querySelectorAll('input[name="orchestration_required_method"]')];assert.deepEqual(methods.map(x=>x.value),['participation','conversation_dynamics','label_frequency','cross_tabulation']);
 methods.forEach(x=>h.click(x));h.click('#orchestration-start');const post=pending(h,'/analysis/orchestration','POST'),body=JSON.parse(post.options.body);
 assert.equal(body.source_analysis_id,'result_original');assert.equal(body.human_prompt,'追加で反例を確認');assert.equal(body.question,'新しい問い');assert.deepEqual(body.required_methods,methods.map(x=>x.value));
 h.reply(post,{run:run({run_id:'run_new',analysis_result_id:null,status:'running'})});await h.flush();
 assert.match(node(h,'run-identity').textContent,/run_new/);assert.equal(h.evaluate('orchestrationState.runId'),'run_new');
});

test('別IDへの変更と応答逆転では最後に選んだIDだけが有効',async t=>{
 const h=await setup(t),a=load(h,'result_a'),b=load(h,'result_b');
 h.reply(b,source('result_b','新しい所見'));await h.flush();h.reply(a,source('result_a','古い所見'));await h.flush();
 assert.match(node(h,'source-preview').textContent,/新しい所見/);assert.doesNotMatch(node(h,'source-preview').textContent,/古い所見/);
 input(h,'human-prompt','追加');input(h,'source-analysis-id','result_c');assert.equal(node(h,'source-preview').hidden,true);
 assert.throws(()=>h.evaluate('orchestrationPayload()'),/参照結果を確認/);
});

test('対象会話切替後の旧応答は表示も送信もできない',async t=>{
 const h=await setup(t),old=load(h,'result_a');
 h.fixture({itemId:'B',data:{item:{id:'B',source_name:'合成会話B',revision_count:1,analysis_revision:1},segments:[]},config:{},annotations:{},dirty:false});
 h.evaluate('Object.assign(analysisState,window.fixture)');h.reply(old,source('result_a','旧会話'));await h.flush();
 assert.equal(node(h,'source-preview').hidden,true);assert.throws(()=>h.evaluate('orchestrationPayload()'),/対象が変わりました/);
});

test('同じIDを再確認した応答が逆転しても後の確認を維持する',async t=>{
 const h=await setup(t),a=load(h,'result_a');h.click('#orchestration-source-load');const b=pending(h,'/reanalysis/source/result_a');assert.notEqual(a,b);
 h.reply(b,source('result_a','新しい確認'));await h.flush();h.reply(a,source('result_a','古い確認'));await h.flush();
 assert.match(node(h,'source-preview').textContent,/新しい確認/);assert.doesNotMatch(node(h,'source-preview').textContent,/古い確認/);
});

test('クロス表は件数・行内割合・欠測を表示し、ラベル内HTMLを実行しない', async t=>{
 const h=await setup(t),host=node(h,'result-content');
 h.fixture({raw_results:[{validation_status:'valid',result_id:'cross',raw:{method_id:'cross_tabulation',label_field:'codes',annotation_version:1,availability:'partial',denominator:3,observed_count:2,missing_count:1,missing_speaker_count:0,missing_label_count:1,row_totals:[{speaker:'A',denominator:3,missing_count:1}],column_totals:[{label:'<img src=x onerror=alert(1)>'}],rows:[{speaker:'A',label:'<img src=x onerror=alert(1)>',count:2,row_proportion:2/3}],limitations:['複数ラベルは合計100%超の場合あり']}}]});
 h.evaluate('orchestrationRenderCrosstabs(document.getElementById("orchestration-result-content"),window.fixture)');
 assert.equal(host.querySelectorAll('table').length,1);assert.equal(host.querySelectorAll('img').length,0);
 assert.match(host.textContent,/2（66.7%）/);assert.match(host.textContent,/欠測 1発話/);assert.match(host.textContent,/結果ID: cross/);
 h.fixture({raw_results:[{validation_status:'valid',result_id:'empty',raw:{method_id:'cross_tabulation',availability:'unavailable',rows:[],limitations:[]}}]});
 host.replaceChildren();h.evaluate('orchestrationRenderCrosstabs(document.getElementById("orchestration-result-content"),window.fixture)');
 assert.match(host.textContent,/集計不可/);assert.equal(host.querySelectorAll('table').length,0);
});
