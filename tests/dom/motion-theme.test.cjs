'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {createHarness}=require('./harness.cjs');
async function setup(t){const h=await createHarness();t.after(()=>{for(const r of h.requests.filter(r=>!r.settled&&r.url==='/api/system/activity'))h.reply(r,{});h.close();});return h;}
function job(stage='transcription',status='running',id='motion-theme'){return {id,status,progress:30,stage,stage_label:stage,stage_progress:30,source_name:'合成音声',logs:[]};}
function render(h,value){h.fixture(value);h.evaluate('resumeJob(window.fixture);showProgressCard({open:true})');return h.document.querySelector('#progress-motion');}
function finish(h,duration){const timer=h.timers.findLast(item=>item.delay===duration);assert(timer);timer.callback();return timer;}

test('初回は共通の太線・吹き出しで起動し、その後に繰り返しへ進む',async t=>{
 const h=await setup(t),motion=render(h,job());
 assert.equal(motion.dataset.cycle,'startup');assert.equal(motion.querySelector('svg').getAttribute('stroke-width'),'6.5');
 assert(motion.querySelector('.motion-shell'));assert(motion.querySelector('.motion-accent'));assert.equal(motion.querySelector('svg').getAttribute('viewBox'),'0 0 260 156');
 finish(h,640);assert.equal(motion.dataset.cycle,'loop');assert.equal(motion.querySelectorAll('.motion-entering').length,0);
});

test('同じ工程の進捗更新ではSVG・ループ・タイマーを再作成しない',async t=>{
 const h=await setup(t),motion=render(h,job());finish(h,640);const svg=motion.querySelector('svg'),symbol=motion.querySelector('.motion-symbol'),timers=h.timers.filter(x=>[640,360,280].includes(x.delay)).length;
 render(h,{...job(),progress:40,stage_progress:55});assert.equal(motion.querySelector('svg'),svg);assert.equal(motion.querySelector('.motion-symbol'),symbol);assert.equal(motion.dataset.cycle,'loop');assert.equal(h.timers.filter(x=>[640,360,280].includes(x.delay)).length,timers);
});

test('工程変更では共通の外枠を保ち、切替を挟んで次のループへ進む',async t=>{
 const h=await setup(t),motion=render(h,job());finish(h,640);const svg=motion.querySelector('svg');render(h,job('diarization'));
 assert.equal(motion.dataset.cycle,'transition');assert.equal(motion.querySelector('svg'),svg);assert.equal(motion.querySelectorAll('.motion-symbol').length,2);assert.equal(motion.querySelectorAll('.motion-outgoing').length,1);
 finish(h,360);assert.equal(motion.dataset.cycle,'loop');assert.equal(motion.querySelectorAll('.motion-symbol').length,1);
 render(h,job('speaker_assignment'));assert.equal(motion.dataset.cycle,'transition');
});

test('速い連続切替では古い完了コールバックが新しい工程を上書きしない',async t=>{
 const h=await setup(t),motion=render(h,job()),startup=h.timers.findLast(x=>x.delay===640);render(h,job('alignment'));const first=h.timers.findLast(x=>x.delay===360);render(h,job('diarization'));const last=h.timers.findLast(x=>x.delay===360);
 startup.callback();first.callback();assert.equal(motion.dataset.cycle,'transition');assert.equal(motion.dataset.scene,'speakers');assert.equal(motion.querySelectorAll('.motion-symbol').length,2);
 last.callback();assert.equal(motion.dataset.cycle,'loop');assert.equal(motion.querySelectorAll('.motion-symbol').length,1);
});

for(const status of ['completed','failed','cancelled'])test(`${status}では着地の動きの後に停止する`,async t=>{
 const h=await setup(t),motion=render(h,job());finish(h,640);render(h,job(status,status));assert.equal(motion.dataset.cycle,'settling');finish(h,280);assert.equal(motion.dataset.cycle,'settled');assert.equal(motion.dataset.state,status);assert.equal(motion.querySelectorAll('.motion-symbol').length,1);
});

test('動きを減らす設定では起動・切替を待たずに状態を確定する',async t=>{
 const h=await setup(t);h.w.matchMedia=()=>({matches:true});const motion=render(h,job());assert.equal(motion.dataset.cycle,'loop');assert.equal(motion.querySelectorAll('.motion-entering,.motion-outgoing').length,0);render(h,job('completed','completed'));assert.equal(motion.dataset.cycle,'settled');
});

test('受付から実ジョブへのID変更で起動を繰り返さない',async t=>{
 const h=await setup(t),motion=render(h,job('admitting','admitting','submission'));const svg=motion.querySelector('svg');render(h,job('queued','queued','accepted'));assert.equal(motion.querySelector('svg'),svg);assert.equal(motion.dataset.cycle,'transition');finish(h,360);assert.equal(motion.dataset.cycle,'waiting');
});
