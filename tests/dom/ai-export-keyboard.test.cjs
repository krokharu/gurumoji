'use strict';
// Component focus/notification contracts only; native Edge keyboard evidence is separate.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');

async function setup(t) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture({itemId: 'keyboard', data: {executed: false, segments: [], config: {}, annotations: {},
    manual: {preparation: {revision: 1, source_hash: 'synthetic-keyboard', rows: [], status: 'draft'}}},
    config: {}, annotations: {}, mode: 'manual', dirty: false});
  h.evaluate('Object.assign(analysisState,window.fixture);renderAnalysisWorkspace()');
  h.panel = h.document.querySelector('[data-ai-data-export]');
  h.panel.open = true;
  h.start = h.panel.querySelector('[data-ai-export-download]');
  h.cancel = h.panel.querySelector('[data-ai-export-cancel]');
  h.begin = () => { h.start.focus(); h.click(h.start); return h.requests.findLast(r => r.url.endsWith('/ai-export.zip')); };
  return h;
}

test('focused start hands focus to enabled cancel; HTTP failure returns focus to enabled retry', async t => {
  const h = await setup(t); const request = h.begin();
  assert.equal(h.document.activeElement, h.cancel);
  assert.equal(h.start.disabled, true); assert.equal(h.cancel.disabled, false);
  assert.match(h.panel.querySelector('[role="status"]').textContent, /ZIPを作成しています/);
  h.reply(request, {frames: {status: 'unavailable'}}, 422); await h.flush();
  assert.equal(h.document.activeElement, h.start);
  assert.equal(h.start.disabled, false); assert.equal(h.cancel.disabled, true);
  assert.match(h.panel.querySelector('[role="status"]').textContent, /ZIPはダウンロードされていません/);
});

test('failure does not steal focus from summary after inline close or from another control', async t => {
  const h = await setup(t);
  for (const destination of [h.panel.querySelector('summary'), h.document.querySelector('#analysis-item-select')]) {
    h.panel.open = true; const request = h.begin();
    h.panel.open = false; destination.focus();
    h.reply(request, {}, 409); await h.flush();
    assert.equal(h.document.activeElement, destination);
    assert.equal(h.panel.open, false);
  }
});

test('transport failure restores retry; explicit cancellation retains existing retry focus and stale reply cannot steal it', async t => {
  const h = await setup(t); let request = h.begin();
  h.fail(request); await h.flush(); assert.equal(h.document.activeElement, h.start);
  request = h.begin(); h.click(h.cancel);
  assert.equal(h.document.activeElement, h.start); assert.equal(request.options.signal.aborted, true);
  h.panel.querySelector('summary').focus();
  h.reply(request, {}, 422); await h.flush();
  assert.equal(h.document.activeElement, h.panel.querySelector('summary'));
});

test('ZIP completion restores focused cancel; an unfocused start never moves focus into export', async t => {
  const h = await setup(t);
  h.w.URL.createObjectURL = () => 'blob:synthetic-keyboard';
  h.w.URL.revokeObjectURL = () => {};
  h.w.HTMLAnchorElement.prototype.click = () => {};
  const request = h.begin();
  request.settled = true;
  request.resolve({ok: true, headers: new h.w.Headers({'Content-Type': 'application/zip'}),
    blob: async () => new h.w.Blob(['PK synthetic'])});
  await h.flush(); assert.equal(h.document.activeElement, h.start);
  const summary = h.panel.querySelector('summary'); summary.focus(); h.click(h.start);
  assert.equal(h.document.activeElement, summary);
  const unfocused = h.requests.findLast(r => r.url.endsWith('/ai-export.zip'));
  h.reply(unfocused, {}, 422); await h.flush(); assert.equal(h.document.activeElement, summary);
});

test('focus obscured by another surface scrolls into view; later focus is not scrolled by stale callback', async t => {
  const h = await setup(t); let scrolls = 0;
  h.start.getBoundingClientRect = () => ({left: 10, top: 800, width: 100, height: 46});
  h.start.scrollIntoView = () => { scrolls++; };
  h.document.elementFromPoint = () => h.document.querySelector('#analysis-item-select');
  h.start.focus(); const pending = h.timers.at(-1); pending.callback(); assert.equal(scrolls, 1);
  h.start.blur(); h.start.focus(); const stale = h.timers.at(-1);
  h.panel.querySelector('summary').focus(); stale.callback(); assert.equal(scrolls, 1);
});
