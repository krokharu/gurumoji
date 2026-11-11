'use strict';
// 合成APIだけで生成条件の表示・送信・履歴を確認する。
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');

async function setup(t) {
  const h = await createHarness();
  t.after(() => h.close());
  h.fixture({itemId:'TEST-A',data:{item:{id:'TEST-A',source_name:'合成の会話',revision_count:1,analysis_revision:1},segments:[]},config:{research_question:'合成の問い'},annotations:{},dirty:false});
  h.evaluate('Object.assign(analysisState,window.fixture);analysisCard.hidden=false;document.body.dataset.view="analysis"');
  h.click('#pipeline-open');
  return h;
}

for (const [reasoning,limit] of [['off',4096], ['auto',2048]]) {
  test(`ローカル生成条件 ${reasoning} を明示して保存し、履歴に表示する`, async t => {
    const h = await setup(t);
    assert.equal(h.document.querySelector('#pipeline-local-reasoning').value,'off');
    h.change(h.document.querySelector('#pipeline-local-reasoning'),reasoning);
    h.change(h.document.querySelector('#pipeline-local-max-output'),String(limit));
    h.click('#pipeline-start');
    const request = h.requests.findLast(r => r.options.method === 'POST' && r.url.endsWith('/core-pipeline'));
    assert(request);
    const payload = JSON.parse(request.options.body);
    assert.equal(payload.local_reasoning,reasoning);
    assert.equal(payload.local_max_output_tokens,limit);
    h.reply(request,{run:{run_id:'TEST-run',item_id:'TEST-A',status:'stopped',phase:'stopped',iteration:3,
      config:payload,roles:[],tasks:[],events:[],results:[],usage:{calls:0},allowed_actions:[],stop_reason:'human_review_required'}});
    await h.flush();
    assert.match(h.document.querySelector('#pipeline-local-generation').textContent,
                 new RegExp(`追加推論 ${reasoning === 'off' ? 'OFF' : 'モデル既定'} / 1回の出力上限 ${limit}`));
    assert.match(h.document.querySelector('#pipeline-stop-reason').textContent,/人の確認待ち/);
    assert.equal(h.requests.filter(r => r.options.method === 'POST').length,1);
  });
}
