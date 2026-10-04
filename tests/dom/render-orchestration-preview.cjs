'use strict';
// Static visual review artifact only: synthetic state, no live API or AI calls.
const fs=require('node:fs');
const path=require('node:path');
const {createHarness}=require('./harness.cjs');
(async()=>{
 const h=await createHarness();
 const run={run_id:'synthetic-review-run',item_id:'synthetic-conversation',item_name:'評価用の架空の会話',source_revision:1,status:'completed',phase:'stopped',iteration:3,
  config:{question:'意見が変わった場面と、その根拠を確かめたい',provider:'lmstudio',model:'local-demo（表示用fixture）',provider_policy:'local_only',stop_mode:'iterations',max_iterations:3,max_calls:24,max_tasks:48},
  usage:{calls:7,code_executions:2,total_tokens:null,cost:null,measured_calls:0,measurement_status:'unavailable'},allowed_actions:[],stop_reason:'iteration_limit',
  initial:{status:'ready',completed_stages:5,total_stages:5},initial_stages:['入力整理','言語情報','数量集計','内容整理','初期版の固定'].map((label,index)=>({stage_id:`synthetic-stage-${index}`,label,status:'completed',attempt_count:1,output_hash:`synthetic-hash-${index}`})),
  publication:{save_status:'saved',publication_status:'incomplete',publication_targets:['input','orchestrator','visualization'],effective_writers:['research','input','orchestrator','visualization'],result_run_id:'synthetic-fixed-run',can_retry:true,
   result_run:{artifacts:[{name:'result.json（全量台帳・合成表示）',url:'/api/analysis/artifacts/synthetic-only'}]},outcomes:{input:{status:'published'},orchestrator:{status:'published'},visualization:{status:'failed',error:'表示用の出力失敗'},research:{status:'conflict',error:'表示用の競合。既存ノートの確認が必要です。'}}},
  roles:[{id:'core',status:'idle',assigned:2,completed:2,failed:0},{id:'handler',status:'idle',assigned:7,completed:7,failed:0},{id:'interpretation',status:'succeeded',assigned:2,completed:2,failed:0},
   {id:'statistics',status:'succeeded',assigned:1,completed:1,failed:0},{id:'verification',status:'succeeded',assigned:1,completed:1,failed:0},{id:'critic',status:'succeeded',assigned:1,completed:1,failed:0}],
  tasks:[{task_id:'task-003',role:'interpretation',title:'合意が変わった場面の比較',status:'succeeded',model:'local-demo'},{task_id:'task-004',role:'statistics',title:'全範囲の参加量を集計',status:'succeeded'},
   {task_id:'task-005',role:'verification',title:'引用と発話IDの照合',status:'succeeded',model:'local-demo'},{task_id:'task-006',role:'critic',title:'別の説明を検討',status:'succeeded',model:'local-demo'}],
  events:[{seq:9,type:'completed',message:'固定成果物を保存し、4 Vaultのうち2先の出力を確認しました（表示用の架空イベント）'}],
  current_view:{summary:'提案の採用前に複数の懸念が示されています。懸念が解消したという説明は、元の発話との照合待ちです。'},review_status:'not_reviewed',
  issues:[{issue_id:'issue-demo',severity:'medium',reason:'沈黙を同意と解釈していないか、確認が必要です。',evidence_ids:['synthetic-segment-04']}],results:[{task_id:'task-004',result_id:'result-demo'}]};
 h.fixture(run);h.evaluate('orchestrationAdopt(window.fixture,"synthetic-conversation")');
 const live=h.document.querySelector('#orchestration-live');live.setAttribute('open','');live.querySelectorAll('details').forEach(e=>e.open=false);
 h.fixture({itemId:'synthetic-conversation',data:{item:{source_name:'評価用の架空の会話',revision_count:1,analysis_revision:1}},config:{},dirty:false});
 h.evaluate('Object.assign(analysisState,window.fixture);orchestrationState.run={...orchestrationState.run,status:"stopped",tasks:[],initial_stages:[]};openAnalysisOrchestrationSettings()');
 h.document.querySelector('#orchestration-question').textContent='意見が変わった場面と、その根拠を確かめたい';
 const settings=h.document.querySelector('#orchestration-settings');settings.setAttribute('open','');
 for(const dialog of [live,settings]){dialog.querySelectorAll('button,input,select,textarea').forEach(e=>e.disabled=true);dialog.querySelectorAll('a').forEach(e=>e.removeAttribute('href'));}
 const root=path.resolve(__dirname,'../..'),css=['style.css','analysis-orchestration.css'].map(f=>fs.readFileSync(path.join(root,'src/gurumoji/static',f),'utf8')).join('\n');
 const html=`<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Gurumoji 自律分析 · 合成状態プレビュー</title><style>${css}\nbody{padding:24px 12px}.preview-note{max-width:1080px;margin:10px auto 24px;font:14px/1.8 sans-serif}dialog.orchestration-live,dialog.orchestration-settings{position:relative;inset:auto;max-height:none;margin:24px auto;box-shadow:var(--shadow);border:1px solid var(--line)}*{animation:none!important;transition:none!important}button:disabled,input:disabled,select:disabled,textarea:disabled{opacity:1}.orchestration-settings{margin-top:48px!important}</style><body><p class="preview-note"><strong>合成状態の静的プレビュー</strong><br>実際のテンプレートと描画関数から作成。表示内容はすべて架空です。ブラウザー実操作・実AI実行の証拠ではありません。操作は無効で、通信・モデル呼出し・保存をしません。</p>${live.outerHTML}${settings.outerHTML}</body></html>`;
 const output=path.resolve(process.argv[2]||path.join(root,'../artifacts/orchestration-ui-preview.html'));fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,html);h.close();process.stdout.write(`${output}\n`);
})().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
