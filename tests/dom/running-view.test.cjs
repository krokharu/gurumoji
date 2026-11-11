'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
const job = (id='run-1', status='running') => ({id, status, progress: status==='completed'?100:37, source_name:'合成音声', revision_count:1, files:[], segments:[{id:'s1',speaker:'A',start:0,end:1,text:'合成発話'}], speaker_profiles:{}, speaker_names:{}, session_profile:{}});
async function setup(t) {
  const h=await createHarness();
  t.after(()=>{for(const r of h.requests.filter(r=>!r.settled && r.url==='/api/system/activity'))h.reply(r,{});h.close();});
  return h;
}
async function resume(h, value, open=false) {
  h.fixture(value);h.evaluate(`resumeJob(window.fixture);${open?'showProgressCard({open:true});':''}`);await h.flush();
}
function view(h, name) { assert.equal(h.document.body.dataset.view,name);assert.equal(h.w.location.hash,`#/${name}`); }

test('実行状況は新規作成の外にあり、開始・ホーム・通知・復帰で処理を維持する',async t=>{
  const h=await setup(t);
  assert.equal(h.document.querySelector('#create-view #progress-card'),null);
  assert(h.document.querySelector('#running-view #progress-card'));
  h.evaluate("sourcePath.value='/synthetic/input.wav';createReadiness=()=>({ready:true,notes:[],blockers:[]});form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))");
  await h.flush();view(h,'running');
  const submit=h.requests.find(r=>r.url==='/api/jobs' && r.options.method==='POST');assert(submit);
  h.reply(submit,job());await h.flush();
  h.click('[data-job-home]');view(h,'new');
  assert.equal(h.document.querySelector('#job-form').hidden,false);
  assert.equal(h.document.querySelector('#running-view').hidden,true);
  assert.equal(h.document.querySelector('#job-resume-notice').hidden,false);
  assert.equal(h.document.querySelector('#start-button').disabled,true);
  h.click('[data-open-job]');view(h,'running');
  h.click('#show-new-button');view(h,'new');h.click('#job-chip');view(h,'running');
  assert.equal(h.evaluate('activeJobId'),'run-1');
  assert.equal(h.requests.filter(r=>r.options.method==='POST').length,1);
});

test('ホームでは進捗更新と完了で画面を奪わず、通知から結果を開ける',async t=>{
  const h=await setup(t);await resume(h,job(),true);h.click('[data-job-home]');
  await resume(h,{...job(),progress:65});view(h,'new');
  await resume(h,job('run-1','completed'));view(h,'new');
  assert.equal(h.document.querySelector('#job-form').hidden,false);
  assert.equal(h.document.querySelector('#job-chip').hidden,false);
  assert.match(h.document.querySelector('#job-chip-label').textContent,/完了/);
  h.click('[data-open-job]');assert.equal(h.document.body.dataset.view,'item');
  assert.equal(h.evaluate('currentJobId'),'run-1');
});

test('実行状況では完了を表示し、結果を開く操作で結果へ移る',async t=>{
  const h=await setup(t);await resume(h,job(),true);await resume(h,job('run-1','completed'));
  view(h,'running');assert.equal(h.document.querySelector('#progress-open-result').hidden,false);
  h.click('#progress-open-result');assert.equal(h.document.body.dataset.view,'item');assert.equal(h.document.querySelector('#running-view').hidden,true);
});

for(const status of ['failed','cancelled'])test(`${status}の状況はホームから再確認でき、表示を閉じるとホームへ戻る`,async t=>{
  const h=await setup(t);await resume(h,job(),true);await resume(h,job('run-1',status));
  view(h,'running');assert.equal(h.document.querySelector('#progress-dismiss').hidden,false);
  h.click('[data-job-home]');view(h,'new');h.click('#job-chip');view(h,'running');
  h.click('#progress-dismiss');view(h,'new');assert.equal(h.document.querySelector('#job-chip').hidden,true);
});

test('再読み込みのジョブ復元はホームを保ち、専用ルート・履歴から進捗へ戻れる',async t=>{
  const h=await setup(t);h.w.sessionStorage.setItem('gurumoji.activeJobId','reload-job');
  h.evaluate('void restoreActiveJob()');await h.flush();
  const r=h.requests.findLast(r=>r.url==='/api/jobs/reload-job');h.reply(r,job('reload-job'));await h.flush();view(h,'new');
  h.w.history.replaceState(null,'','#/running');h.w.dispatchEvent(new h.w.PopStateEvent('popstate'));view(h,'running');
  h.w.history.replaceState(null,'','#/new');h.w.dispatchEvent(new h.w.PopStateEvent('popstate'));view(h,'new');
  h.click('#job-chip');view(h,'running');assert.equal(h.evaluate('activeJobId'),'reload-job');
});

test('接続失敗でジョブ情報がまだない場合も通知から再接続画面へ戻れる',async t=>{
  const h=await setup(t);h.w.sessionStorage.setItem('gurumoji.activeJobId','offline-job');
  h.evaluate('void restoreActiveJob()');await h.flush();h.fail(h.requests.findLast(r=>r.url==='/api/jobs/offline-job'));await h.flush();
  view(h,'new');assert.equal(h.document.querySelector('#job-chip').hidden,false);
  h.click('#job-chip');view(h,'running');assert.match(h.document.querySelector('#progress-message').textContent,/再接続/);
});

test('実行ジョブがない専用画面には案内と新規作成への導線を表示する',async t=>{
  const h=await setup(t);h.evaluate("showView('running')");view(h,'running');
  assert.equal(h.document.querySelector('#job-empty-state').hidden,false);
  h.click('[data-job-home]');view(h,'new');
});

test('別の結果の未保存編集はバックグラウンド完了と通知クリックで失わない',async t=>{
  const h=await setup(t);h.fixture(job('editing','completed'));h.evaluate('renderResult(window.fixture);setCurrentJobDirty(true)');
  await resume(h,job('background'));await resume(h,job('background','completed'));
  assert.equal(h.evaluate('currentJobId'),'editing');assert.equal(h.evaluate('currentJobDirty'),true);
  h.w.confirm=()=>false;h.click('#job-chip');assert.equal(h.evaluate('currentJobId'),'editing');
  assert.equal(h.evaluate('completedJob.id'),'background');
  h.w.confirm=()=>true;h.click('#job-chip');assert.equal(h.evaluate('currentJobId'),'background');
});


test('送信が拒否された場合は新規作成へ戻り、エラーを表示する',async t=>{
  const h=await setup(t);
  h.evaluate("sourcePath.value='/synthetic/input.wav';createReadiness=()=>({ready:true,notes:[],blockers:[]});form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))");
  await h.flush();view(h,'running');
  h.reply(h.requests.find(r=>r.url==='/api/jobs' && r.options.method==='POST'),{error:'合成受付エラー'},400);
  await h.flush();view(h,'new');assert.match(h.document.querySelector('#form-error').textContent,/合成受付エラー/);
  assert.equal(h.document.querySelector('#job-chip').hidden,true);
});

test('キューの自動継続はホームを維持し、前の完了結果を通知に残さない',async t=>{
  const h=await setup(t);await resume(h,job('previous','completed'));
  h.evaluate("sourcePath.value='/synthetic/input.wav';createReadiness=()=>({ready:true,notes:[],blockers:[]});startButton.dataset.queueAutoStart='true';form.dispatchEvent(new SubmitEvent('submit',{bubbles:true,cancelable:true,submitter:startButton}));delete startButton.dataset.queueAutoStart");
  await h.flush();view(h,'new');assert.equal(h.evaluate('completedJob'),null);
  h.reply(h.requests.find(r=>r.url==='/api/jobs' && r.options.method==='POST'),job('next'));await h.flush();view(h,'new');
  h.click('#job-chip');view(h,'running');assert.equal(h.evaluate('activeJobId'),'next');
});
