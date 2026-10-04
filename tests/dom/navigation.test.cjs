'use strict';
// Synthetic browser events invoke the shipped route listener; not native history/GUI evidence.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
async function setup(t) { const h = await createHarness(); t.after(() => h.close()); return h; }
function job(id) { return {id, source_name: `Synthetic ${id}`, revision_count: 1, files: [], segments: [{id: 's1', speaker: 'A', start: 0, end: 1, text: 'Synthetic'}], speaker_profiles: {}, speaker_names: {}, session_profile: {}}; }
function route(h, hash) { h.w.history.replaceState(null, '', hash); h.w.dispatchEvent(new h.w.PopStateEvent('popstate')); }
function request(h, id) { const value = h.requests.findLast(r => r.url === `/api/library/${id}`); assert(value); return value; }

for (const order of ['older-first', 'newer-first']) test(`real popstate routing keeps newest item with ${order} response order`, async t => {
  const h = await setup(t);
  route(h, '#/data/A'); const older = request(h, 'A');
  route(h, '#/data/B'); const newer = request(h, 'B');
  if (order === 'older-first') {
    h.reply(older, job('A')); await h.flush();
    assert.equal(h.w.location.hash, '#/data/B');
    h.reply(newer, job('B')); await h.flush();
  } else {
    h.reply(newer, job('B')); await h.flush();
    h.reply(older, job('A')); await h.flush();
  }
  assert.equal(h.evaluate('currentJobId'), 'B');
  assert.equal(h.document.body.dataset.view, 'item');
  assert.equal(h.w.location.hash, '#/data/B');
  assert.equal(h.document.querySelector('#result-card').hidden, false);
  assert.equal(h.document.querySelector('#result-title').textContent, 'Synthetic B');
});

for (const status of [200, 500]) test(`old route ${status} cannot navigate away after the real New button is clicked`, async t => {
  const h = await setup(t);
  route(h, '#/data/A'); const opening = request(h, 'A');
  h.click('#show-new-button');
  h.reply(opening, status === 200 ? job('A') : {error: 'Synthetic old failure'}, status);
  await h.flush();
  assert.equal(h.document.body.dataset.view, 'new');
  assert.equal(h.w.location.hash, '#/new');
  assert.equal(h.document.querySelector('#create-view').hidden, false);
});

test('rejected history navigation preserves dirty result and does not fetch the rejected item', async t => {
  const h = await setup(t);
  h.fixture(job('A')); h.evaluate('renderResult(window.fixture)');
  h.click('.conversation-role-control button');
  h.w.confirm = () => false;
  route(h, '#/data/B'); await h.flush();
  assert.equal(h.evaluate('currentJobId'), 'A');
  assert.equal(h.evaluate('currentJobDirty'), true);
  assert.equal(h.w.location.hash, '#/data/A');
  assert.equal(h.requests.filter(r => r.url === '/api/library/B').length, 0);
});

test('item tab keyboard handler moves focus without activating a different panel', async t => {
  const h = await setup(t);
  h.fixture(job('A')); h.evaluate('renderResult(window.fixture)');
  const tabs = [...h.document.querySelectorAll('[data-item-tab]')];
  assert(tabs.length >= 2);
  tabs[0].focus();
  tabs[0].dispatchEvent(new h.w.KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true, cancelable: true}));
  assert.equal(h.document.activeElement, tabs[1]);
  assert.equal(tabs[0].getAttribute('aria-selected'), 'true');
  h.click(tabs[1]); await h.flush();
  assert.equal(tabs[1].getAttribute('aria-selected'), 'true');
  assert.equal(tabs[1].getAttribute('tabindex'), '0');
  assert.equal(tabs.filter(tab => tab.getAttribute('tabindex') === '0').length, 1);
  assert.equal(h.document.querySelector(`[data-item-panel="${tabs[1].dataset.itemTab}"]`).hidden, false);
});
