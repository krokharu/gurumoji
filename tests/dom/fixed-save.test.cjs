'use strict';
// Read-only saved results must not become a permanently waiting/dead dialog after a live Save.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
function data(revision = 1) { return {executed: true, item: {id: 'A', source_name: 'Synthetic A', revision_count: revision, analysis_revision: revision}, segments: [], config: {}, annotations: {}}; }
async function setup(t) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture({itemId: 'A', data: data(), config: {}, annotations: {}, mode: 'manual', dirty: true});
  h.evaluate('Object.assign(analysisState,window.fixture);renderAnalysisWorkspace();analysisCard.hidden=false;document.body.dataset.view="analysis"');
  h.click('[data-analysis-save]');
  const save = h.requests.findLast(r => r.options.method === 'PUT'); assert(save);
  h.click('[data-analysis-mode="automatic"]');
  h.click('[data-analysis-jump="exports"]');
  const lookup = h.document.querySelector('.analysis-fixed-lookup'); assert(lookup);
  assert.equal(lookup.closest('[hidden]'), null, 'The lookup must be in the selected visible DOM page');
  lookup.querySelector('input').value = 'r1'; lookup.requestSubmit();
  const run = h.requests.findLast(r => r.url === '/api/library/A/analysis/runs/r1'); assert(run);
  return {h, save, run};
}
async function saved(h, request) {
  h.reply(request, data(2)); await h.flush();
  for (const suffix of ['runs', 'insights', 'transformer']) {
    const request = h.requests.findLast(r => !r.settled && r.url === `/api/library/A/analysis/${suffix}`);
    if (request) h.reply(request, suffix === 'runs' ? {runs: []} : {run: null});
  }
  await h.flush();
}
const payload = {run: {id: 'r1', item_id: 'A', artifacts: [{id: 'f1', name: 'synthetic.json', bytes: 1}]}, integrity: 'verified'};
const preview = {preview: {run_id: 'r1', artifact_id: 'f1', format: 'text', text: 'SYNTHETIC SAVED RESULT'}};
function previewButton(h) { return [...h.document.querySelectorAll('.analysis-fixed-dialog button')].find(button => button.textContent === 'synthetic.json を読む'); }
function previewRequest(h) { return h.requests.findLast(r => !r.settled && r.url === '/api/library/A/analysis/runs/r1/previews/f1'); }

test('same-item live Save cannot strand a pending fixed-run lookup', async t => {
  const {h, save, run} = await setup(t);
  await saved(h, save);
  h.reply(run, payload); await h.flush();
  const dialog = h.document.querySelector('.analysis-fixed-dialog');
  assert(!dialog.open || dialog.querySelector('.analysis-fixed-body').children.length > 0,
    'An open dialog must finish reading its fixed run rather than retain its loading message forever');
});

test('same-item live Save cannot strand a pending fixed-file preview', async t => {
  const {h, save, run} = await setup(t);
  h.reply(run, payload); await h.flush(); h.click(previewButton(h));
  const reading = previewRequest(h); assert(reading);
  await saved(h, save);
  h.reply(reading, preview); await h.flush();
  const dialog = h.document.querySelector('.analysis-fixed-dialog');
  assert(!dialog.open || dialog.querySelector('.analysis-fixed-preview').textContent.includes('SYNTHETIC SAVED RESULT'),
    'An open preview must not retain its loading message after live data is saved');
});

test('same-item live Save cannot leave a displayed fixed-run file control inert', async t => {
  const {h, save, run} = await setup(t);
  h.reply(run, payload); await h.flush();
  await saved(h, save);
  const dialog = h.document.querySelector('.analysis-fixed-dialog');
  if (!dialog.open) return; // A deliberate close is acceptable; a silently dead open modal is not.
  h.click(previewButton(h));
  const reading = previewRequest(h);
  assert(reading, 'An open fixed-file control must still dispatch its read after the same item is saved');
  h.reply(reading, preview); await h.flush();
  assert(dialog.querySelector('.analysis-fixed-preview').textContent.includes('SYNTHETIC SAVED RESULT'));
});

test('fixed metadata describes matching, stale and unknown input comparisons as fetch-time evidence', async t => {
  for (const stale of [false, true, null]) {
    const {h, save, run} = await setup(t);
    h.reply(run, {...payload, current_input: {stale}}); await h.flush();
    const body = h.document.querySelector('.analysis-fixed-body');
    const comparison = [...body.children].find(node => node.textContent.includes('取得時点'));
    assert(comparison, 'A later live Save must not make a prior comparison read as a current guarantee');
    if (stale === null) assert(comparison.textContent.includes('不明'));
    else if (stale) assert(comparison.textContent.includes('異なります'));
    else assert(comparison.textContent.includes('一致しています'));
    const original = comparison.textContent;
    await saved(h, save);
    assert.equal(comparison.textContent, original);
  }
});
