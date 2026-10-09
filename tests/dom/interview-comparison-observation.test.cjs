'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');

const known = (observed, missing) => ({status:'known', source:'analysis.segments[].emotion_details', observed_count:observed, missing_prediction_count:missing});
const observation = (value, models=[]) => ({version:1, target_scope:'included_nonempty_segments', target_count:100, any_model:value, models});

// Exercise the shipped selection and POST/render path, with offline synthetic responses.
async function render(interviews) {
  const h = await createHarness();
  const calls = [];
  h.w.fetch = async (url, options={}) => {
    calls.push({url:String(url), options});
    let data;
    if (url === '/api/library?sort=updated_desc') {
      data = {items:[{id:'a',source_name:'A',comparison_key:'same'}, {id:'b',source_name:'B',comparison_key:'same'}]};
    } else if (url === '/api/library/interview-comparison' && options.method === 'POST') {
      assert.deepEqual(JSON.parse(options.body), {item_ids:['a','b'],allow_different_content:false});
      data = {same_content:true, interviews, emotion_comparison:[{emotion:'sad',interviews:[
        {item_id:'a',count:20,rate_per_100_segments:20},{item_id:'b',count:1,rate_per_100_segments:1}
      ]}]};
    } else throw new Error(`Unplanned request: ${url}`);
    return {ok:true,json:async()=>data};
  };
  h.click('#interview-comparison-refresh');
  await h.flush();
  h.click('[data-comparison-target="b"]');
  h.click('#interview-comparison-run');
  await h.flush();
  assert.equal(h.document.querySelector('#interview-comparison-result').hidden,false);
  assert.equal(calls.length,2,'Display adds no network calls or inference');
  return h;
}
const rows = h => [...h.document.querySelectorAll('[data-emotion-observation] tbody tr')].map(row=>[...row.children].map(cell=>cell.textContent));

test('observed denominator distinguishes 100/100 from 5/100 without changing label percentages', async () => {
  const h = await render([
    {item_id:'a',source_name:'A',emotion_observation:observation(known(100,0))},
    {item_id:'b',source_name:'B',emotion_observation:observation(known(5,95))}
  ]);
  try {
    assert.deepEqual(rows(h),[['A / いずれかのモデル','100件','100件','0件'],['B / いずれかのモデル','100件','5件','95件']]);
    const text = h.document.querySelector('#interview-comparison-result').textContent;
    assert.match(text,/20件 \(20%\)/); assert.match(text,/1件 \(1%\)/);
    assert.equal(h.document.querySelector('[data-emotion-observation] th').scope,'col');
  } finally {h.close();}
});

test('legacy, unknown and malformed metadata never become zero observations', async () => {
  const cases = [undefined, observation({status:'unknown',observed_count:null,missing_prediction_count:null}),
    {...observation(known(0,100)),version:2}, {...observation(known(0,100)),target_scope:'all_timeline_segments'},
    observation(known(5,94)), observation(known(-1,101)), observation(known('0',100)),
    observation({...known(0,100),source:'unavailable'})];
  const h = await render(cases.map((value,i)=>({item_id:String(i),source_name:`S${i}`,emotion_observation:value})));
  try {for (const row of rows(h)) assert.deepEqual(row.slice(2),['不明','不明']);}
  finally {h.close();}
});

test('known zero, empty scope, same-name distinct IDs and hostile labels remain distinct', async () => {
  const h = await render([
    {item_id:'a',source_name:'<img src=x onerror=alert(1)>',emotion_observation:observation(known(0,100),[
      {...known(0,100),model_id:'m1',model_name:'same'}, {...known(5,95),model_id:'m2',model_name:'same'}])},
    {item_id:'b',source_name:'B',emotion_observation:{...observation({...known(0,0),status:'not_applicable'}),target_count:0}}
  ]);
  try {
    const actual = rows(h);
    assert.deepEqual(actual[0].slice(1),['100件','0件','100件']);
    assert.match(actual[1][0],/same \(m1\)/); assert.match(actual[2][0],/same \(m2\)/);
    assert.deepEqual(actual[3].slice(1),['0件','対象なし','対象なし']);
    assert.equal(h.document.querySelector('[data-emotion-observation] img'),null);
  } finally {h.close();}
});

test('duplicate or absent model IDs are shown as unknown', async () => {
  const h = await render([{item_id:'a',source_name:'A',emotion_observation:observation(known(5,95),[
    {...known(5,95),model_id:'dup'}, {...known(5,95),model_id:'dup'}, known(5,95)
  ])}]);
  try {for (const row of rows(h).slice(1)) assert.deepEqual(row,['A / モデル不明','100件','不明','不明']);}
  finally {h.close();}
});
