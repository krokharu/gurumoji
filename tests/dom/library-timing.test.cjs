'use strict';
// Existing library cards/overview and real analysis selector, with projected synthetic API jobs.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
const fixtures = require('./fixtures/remaining-timing-v7.json');
const plain = value => JSON.parse(JSON.stringify(value));
const text = node => node.textContent.replace(/\s+/g, ' ').trim();
async function setup(t, records) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture(records);
  h.evaluate('analysisCatalog=window.fixture;analysisCatalogLoaded=true;analysisState.itemId="";analysisState.data=null;analysisState.dirty=false;analysisCard.hidden=false;document.body.dataset.view="analysis";analysisItemSelect.replaceChildren(...analysisCatalog.map(item=>new Option(item.source_name,item.id)));analysisItemSelect.value="";renderLibraryOverview(analysisCatalog);renderLibraryItems(analysisCatalog)');
  return h;
}
function assertEndpoint(value, {endpoint, missing, timed}) {
  assert.match(value, /最終時刻/);
  if (endpoint === null) { assert.match(value, /不明|算出不可|—/); assert(!value.includes('00:00'), value); }
  else assert.match(value, endpoint === 0 ? /00:00/ : /00:10/);
  if (missing) {
    assert.match(value, new RegExp(`時刻不明${missing}発話`));
    if (timed) assert.match(value, new RegExp(`${timed}/${timed + missing}発話`));
  } else if (timed) assert(!value.includes('時刻不明'), value);
}
const scenarios = [
  {name: 'all_unknown', endpoint: null, timed: 0, missing: 1},
  {name: 'partial', endpoint: 10, timed: 1, missing: 1},
  {name: 'true_zero', endpoint: 0, timed: 1, missing: 0},
  {name: 'true_zero_at_ten', endpoint: 10, timed: 1, missing: 0},
  {name: 'empty', endpoint: null, timed: 0, missing: 0},
  {name: 'positive', endpoint: 10, timed: 1, missing: 0}
];
for (const scenario of scenarios) test(`library ${scenario.name} keeps a nullable observed endpoint on its card and selected analysis target`, async t => {
  const fixture = fixtures.cases[scenario.name]; const record = fixture.job;
  assert.equal(record.duration, scenario.endpoint);
  assert.equal(record.timed_turn_count, scenario.timed); assert.equal(record.missing_time_turn_count, scenario.missing);
  const h = await setup(t, [record]);
  const card = h.document.querySelector('.library-item'); assert(card);
  assertEndpoint(text(card.querySelector('.library-meta')), scenario);
  h.change(h.document.querySelector('#analysis-item-select'), record.id);
  const request = h.requests.findLast(item => item.url === `/api/library/${record.id}/analysis`); assert(request);
  assertEndpoint(text(h.document.querySelector('#analysis-target-meta')), scenario);
  h.reply(request, {...fixture.analysis, executed: false}); await h.flush();
  assertEndpoint(text(h.document.querySelector('#analysis-target-meta')), scenario);
  assert.equal(h.document.querySelector('#analysis-target-name').textContent, record.source_name);
  assert.deepEqual(plain(h.evaluate('analysisCatalog')), [record], 'Rendering may not repair or overwrite API timestamps');
  assert.equal(h.requests.filter(item => ['POST', 'PUT', 'PATCH', 'DELETE'].includes(item.options.method)).length, 0);
});

for (const names of [['all_unknown'], ['all_unknown', 'positive'], ['partial']]) test(`library total ${names.join('+')} identifies missing records rather than presenting a complete sum`, async t => {
  const records = names.map((name,index) => ({...fixtures.cases[name].job, id: `synthetic-${index}`}));
  const h = await setup(t, records);
  const total = text(h.document.querySelector('#library-duration-metric'));
  assert.match(total, /不明|欠測/);
  if (names.some(name => ['positive', 'partial'].includes(name))) {
    assert.match(total, /00:10/); assert.match(total, /既知|時刻あり/);
  } else assert(!total.includes('00:00'), total);
  assert.deepEqual(plain(h.evaluate('analysisCatalog')), records);
});

test('library complete positive plus true-zero keeps the known total and no missing-data warning', async t => {
  const records = ['positive', 'true_zero'].map((name,index) => ({...fixtures.cases[name].job, id: `synthetic-${index}`}));
  const h = await setup(t, records); const total = text(h.document.querySelector('#library-duration-metric'));
  assert.match(total, /00:10/); assert(!/不明|欠測/.test(total), total);
});
