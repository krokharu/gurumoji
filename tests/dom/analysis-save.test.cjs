'use strict';
// Real DOM controls and shipped Save/item-change handlers with synthetic deferred APIs.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
const plain = value => JSON.parse(JSON.stringify(value));
function data(id, revision = 1, question = '') {
  return {executed: false, item: {id, source_name: `Synthetic ${id}`, revision_count: revision, analysis_revision: revision}, segments: [], config: {research_question: question}, annotations: {}};
}
async function setup(t) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture({itemId: 'A', data: data('A'), config: {research_question: 'Synthetic draft'}, annotations: {}, mode: 'manual', dirty: true});
  h.evaluate('Object.assign(analysisState,window.fixture);renderAnalysisWorkspace();analysisCard.hidden=false;document.body.dataset.view="analysis";analysisItemSelect.replaceChildren(new Option("Synthetic A","A"),new Option("Synthetic B","B"));analysisItemSelect.value="A"');
  return h;
}
function save(h) {
  h.click('[data-analysis-save]');
  const request = h.requests.findLast(r => r.options.method === 'PUT'); assert(request); return request;
}
async function select(h, id, revision = 3) {
  h.change(h.document.querySelector('#analysis-item-select'), id);
  const request = h.requests.findLast(r => r.url === `/api/library/${id}/analysis` && (r.options.method || 'GET') === 'GET');
  assert(request); h.reply(request, data(id, revision, `New loaded ${id}`)); await h.flush();
}

for (const route of ['B', 'ABA']) for (const status of [200, 409, 500]) test(`analysis Save ${status} cannot take ownership after ${route} item selector navigation`, async t => {
  const h = await setup(t); const request = save(h);
  await select(h, 'B'); if (route === 'ABA') await select(h, 'A');
  const before = plain(h.evaluate('({itemId:analysisState.itemId,data:analysisState.data,config:analysisState.config,dirty:analysisState.dirty})'));
  const message = h.document.querySelector('#analysis-message').textContent;
  h.reply(request, status === 200 ? data('A', 2, 'Old saved A') : {error: 'Old save failure'}, status); await h.flush();
  assert.deepEqual(plain(h.evaluate('({itemId:analysisState.itemId,data:analysisState.data,config:analysisState.config,dirty:analysisState.dirty})')), before);
  assert.equal(h.document.querySelector('#analysis-message').textContent, message);
  assert.equal(h.evaluate('analysisSaveInProgress'), false);
});

test('analysis Save still commits a normal current-owner response', async t => {
  const h = await setup(t); const request = save(h);
  h.reply(request, data('A', 2, 'Synthetic saved')); await h.flush();
  assert.equal(h.evaluate('analysisState.data.item.analysis_revision'), 2);
  assert.equal(h.evaluate('analysisState.config.research_question'), 'Synthetic saved');
  assert.equal(h.evaluate('analysisState.dirty'), false);
  assert.equal(h.evaluate('analysisSaveInProgress'), false);
});

test('analysis Save keeps edits made after the request and advances only returned revision', async t => {
  const h = await setup(t); const request = save(h);
  const question = h.document.querySelector('[data-analysis-config="research_question"]'); assert(question);
  question.value = 'Synthetic later edit'; question.dispatchEvent(new h.w.Event('input', {bubbles: true}));
  h.reply(request, data('A', 2, 'Old saved question')); await h.flush();
  assert.equal(h.evaluate('analysisState.config.research_question'), 'Synthetic later edit');
  assert.equal(h.evaluate('analysisState.data.item.analysis_revision'), 2);
  assert.equal(h.evaluate('analysisState.dirty'), true);
  assert.equal(h.evaluate('analysisSaveInProgress'), false);
});
