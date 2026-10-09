'use strict';
// Shipped template + all production scripts; same-origin API and download fixtures only.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
function data(id, revision = 7) {
  return {executed: false, item: {id, revision_count: revision, analysis_revision: revision},
    segments: [], config: {}, annotations: {}, manual: {preparation: {
      revision, source_hash: `synthetic-${id}-${revision}`, status: 'draft', rows: [],
      content_ready_count: 0, interaction_ready_count: 0, original_status: 'unavailable'
    }}};
}
async function setup(t) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture({itemId: 'A', data: data('A'), config: {}, annotations: {}, mode: 'manual', dirty: false});
  h.evaluate('Object.assign(analysisState,window.fixture);renderAnalysisWorkspace();analysisCard.hidden=false;document.body.dataset.view="analysis";analysisItemSelect.replaceChildren(new Option("Synthetic A","A"),new Option("Synthetic B","B"));analysisItemSelect.value="A"');
  h.downloads = []; h.created = []; h.revoked = [];
  h.w.URL.createObjectURL = blob => { h.created.push(blob); return `blob:synthetic-${h.created.length}`; };
  h.w.URL.revokeObjectURL = url => h.revoked.push(url);
  h.w.HTMLAnchorElement.prototype.click = function() { h.downloads.push({href: this.href, name: this.download}); };
  h.panels = () => [...h.document.querySelectorAll('[data-ai-data-export]')];
  h.panel = () => h.panels()[0];
  h.input = (selector, value) => {
    const input = h.panel().querySelector(selector); assert(input);
    if (input.type === 'checkbox') input.checked = value; else input.value = value;
    input.dispatchEvent(new h.w.Event('input', {bubbles: true}));
  };
  h.start = () => {
    h.click(h.panel().querySelector('[data-ai-export-download]'));
    const request = h.requests.findLast(r => r.url.endsWith('/ai-export.zip')); assert(request); return request;
  };
  h.zip = (request, {type = 'application/zip', blob = new h.w.Blob(['PK synthetic ZIP'], {type}), disposition = 'attachment; filename="../../unsafe.zip"'} = {}) => {
    assert.equal(request.settled, false); request.settled = true;
    request.resolve({ok: true, status: 200, headers: new h.w.Headers({'Content-Type': type, 'Content-Disposition': disposition}), blob: async () => blob});
  };
  return h;
}
const status = h => h.panel().querySelector('[data-ai-export-status]').textContent;
const exportsFor = h => h.requests.filter(r => r.url.endsWith('/ai-export.zip'));
async function select(h, id) {
  h.change(h.document.querySelector('#analysis-item-select'), id);
  const request = h.requests.findLast(r => r.url === `/api/library/${id}/analysis` && !r.settled);
  assert(request); h.reply(request, data(id)); await h.flush();
}

test('default request excludes names, attributes and frames, and leaves existing preparation export intact', async t => {
  const h = await setup(t);
  assert.equal(h.panels().length, 2);
  for (const panel of h.panels()) {
    assert.equal(panel.querySelector('[data-ai-export-names]').checked, false);
    assert.equal(panel.querySelector('[data-ai-export-frames]').checked, false);
    assert.equal(panel.querySelector('[data-ai-export-frame-options]').disabled, true);
    assert.equal(panel.querySelector('[data-ai-export-status]').getAttribute('role'), 'status');
    assert.match(panel.textContent, /本文・自由記述や動画/);
    assert.match(panel.textContent, /外部AIへ自動送信しません/);
    for (const input of panel.querySelectorAll('input')) assert(input.closest('label')?.textContent.trim());
    for (const key of ['organization', 'department', 'job_title', 'session_role', 'session_role_source']) assert(!panel.textContent.includes(key));
  }
  const json = h.document.querySelector('a[href$="/preparation/export.json"]');
  assert.equal(json.getAttribute('href'), '/api/library/A/preparation/export.json');
  assert(json.hasAttribute('download'));
  const request = h.start();
  assert.equal(request.url, '/api/library/A/ai-export.zip');
  assert.equal(request.options.method, 'POST');
  assert.equal(request.options.headers.get('Content-Type'), 'application/json');
  assert.equal(request.options.headers.get('X-Gurumoji-Request'), '1');
  assert.deepEqual(JSON.parse(request.options.body), {include_names: false, speaker_attributes: [],
    expected_source_hash: 'synthetic-A-7', expected_revision: 7, frames: {enabled: false}});
  for (const panel of h.panels()) {
    assert.equal(panel.getAttribute('aria-busy'), 'true');
    assert.equal(panel.querySelector('[data-ai-export-download]').disabled, true);
    assert.equal(panel.querySelector('[data-ai-export-names]').disabled, true);
    assert.equal(panel.querySelector('[data-ai-export-cancel]').disabled, false);
  }
  h.click(h.panel().querySelector('[data-ai-export-download]'));
  assert.equal(exportsFor(h).length, 1);
  h.zip(request); await h.flush();
  assert.deepEqual(h.downloads, [{href: 'blob:synthetic-1', name: 'gurumoji-ai-data.zip'}]);
  assert.deepEqual(h.revoked, ['blob:synthetic-1']);
  assert.equal(h.created[0].type, 'application/zip');
  assert.match(status(h), /ダウンロードを開始/);
  assert.equal(h.panel().querySelector('[data-ai-export-download]').disabled, false);
  assert.equal(h.panel().querySelector('[data-ai-export-frame-options]').disabled, true);
});

test('responsive controls share explicit selection, only allowlisted attributes and bounded frame defaults are sent', async t => {
  const h = await setup(t);
  h.input('[data-ai-export-names]', true);
  for (const key of ['organization', 'session_role_source', 'department']) h.input(`[data-ai-export-attribute="${key}"]`, true);
  h.input('[data-ai-export-attribute="department"]', false);
  h.input('[data-ai-export-attribute="organization"]', true); // repeated events cannot duplicate an attribute
  h.input('[data-ai-export-frames]', true);
  assert.equal(h.panels()[1].querySelector('[data-ai-export-names]').checked, true);
  assert.equal(h.panels()[1].querySelector('[data-ai-export-frame-options]').disabled, false);
  h.evaluate('renderAnalysisWorkspace()');
  assert.equal(h.panel().querySelector('[data-ai-export-frames]').checked, true);
  const request = h.start();
  assert.deepEqual(JSON.parse(request.options.body), {include_names: true,
    speaker_attributes: ['organization', 'session_role_source'], expected_source_hash: 'synthetic-A-7', expected_revision: 7,
    frames: {enabled: true, start: 0, end: 20, interval: 1, max_frames: 24, max_dimension: 1280}});
  h.zip(request); await h.flush();
  assert.equal(h.panel().querySelector('[data-ai-export-frame-options]').disabled, false);
});

test('invalid frame ranges, overflow, fractions, blank and nonfinite values send no request', async t => {
  const h = await setup(t); h.input('[data-ai-export-frames]', true);
  for (const [field, value] of [['start', '-1'], ['start', ''], ['end', '-1'], ['end', '601'], ['end', '24'],
    ['interval', '0.5'], ['interval', '1e309'], ['max_frames', '0'], ['max_frames', '25'], ['max_frames', '23.5'],
    ['max_dimension', '15'], ['max_dimension', '1281'], ['max_dimension', '16.5']]) {
    const input = h.panel().querySelector(`[data-ai-export-frame="${field}"]`); const before = input.value;
    h.input(`[data-ai-export-frame="${field}"]`, value);
    h.click(h.panel().querySelector('[data-ai-export-download]'));
    assert.equal(exportsFor(h).length, 0, `${field}=${value}`);
    assert.match(status(h), /条件を確認/);
    h.input(`[data-ai-export-frame="${field}"]`, before);
  }
  h.input('[data-ai-export-frame="end"]', '600');
  h.input('[data-ai-export-frame="interval"]', '30');
  const request = h.start();
  assert.equal(JSON.parse(request.options.body).frames.end, 600);
  h.zip(request); await h.flush();
});

for (const code of [400, 404, 409, 422, 408, 500]) test(`HTTP ${code} safely reports structured failure, downloads nothing and enables retry`, async t => {
  const h = await setup(t); const request = h.start();
  h.reply(request, {error: {code: 'synthetic', message: '<img src=x onerror=alert(1)> C:/private/media.mp4'},
    frames: {status: 'partial', reason: 'C:/private/media.mp4'}}, code); await h.flush();
  assert.match(status(h), /ZIPはダウンロードされていません/);
  assert(!status(h).includes('C:/private')); assert(!status(h).includes('<img'));
  assert.equal(h.downloads.length, 0); assert.equal(h.created.length, 0);
  assert.equal(h.panel().querySelector('[data-ai-export-download]').disabled, false);
  assert.equal(h.panel().querySelector('[data-ai-export-cancel]').disabled, true);
  const retry = h.start(); h.zip(retry); await h.flush(); assert.equal(h.downloads.length, 1);
});

test('non-JSON errors, wrong success MIME and network failure never become ZIP downloads', async t => {
  const h = await setup(t); let request = h.start();
  request.settled = true; request.resolve({ok: false, status: 422, json: async () => {throw Error('HTML error');}}); await h.flush();
  assert.match(status(h), /抽出できません/);
  request = h.start(); h.zip(request, {type: 'application/json'}); await h.flush();
  assert.match(status(h), /ZIP形式の応答/);
  request = h.start(); h.fail(request); await h.flush(); assert.match(status(h), /通信に失敗/);
  assert.equal(h.downloads.length, 0); assert.equal(h.created.length, 0);
});

test('cancel aborts owner; replacement download survives stale success and cleanup', async t => {
  const h = await setup(t); const stale = h.start();
  h.click(h.panels()[1].querySelector('[data-ai-export-cancel]'));
  assert.equal(stale.options.signal.aborted, true);
  assert.equal(h.document.activeElement, h.panels()[1].querySelector('[data-ai-export-download]'));
  assert.match(status(h), /取り消しました/); assert.match(status(h), /停止は確認していません/);
  const current = h.start(); h.zip(stale); await h.flush();
  assert.equal(h.downloads.length, 0);
  assert.equal(h.panel().querySelector('[data-ai-export-download]').disabled, true);
  assert.equal(current.options.signal.aborted, false);
  h.zip(current); await h.flush(); assert.equal(h.downloads.length, 1);
});

test('cancel while reading the Blob also blocks stale download', async t => {
  const h = await setup(t); const request = h.start(); let finishBlob;
  request.settled = true; request.resolve({ok: true, status: 200, headers: new h.w.Headers({'Content-Type': 'application/zip'}),
    blob: () => new Promise(resolve => {finishBlob = resolve;})});
  await h.flush(); assert(finishBlob);
  h.click(h.panel().querySelector('[data-ai-export-cancel]'));
  finishBlob(new h.w.Blob(['PK'])); await h.flush();
  assert.equal(h.downloads.length, 0); assert.equal(h.created.length, 0);
});

test('actual item selector B/ABA aborts download and resets sensitive selections', async t => {
  const h = await setup(t); h.input('[data-ai-export-names]', true); h.input('[data-ai-export-frames]', true);
  const stale = h.start(); await select(h, 'B'); await select(h, 'A');
  assert.equal(stale.options.signal.aborted, true);
  assert.equal(h.panel().querySelector('[data-ai-export-names]').checked, false);
  assert.equal(h.panel().querySelector('[data-ai-export-frames]').checked, false);
  h.zip(stale); await h.flush(); assert.equal(h.downloads.length, 0);
  assert.equal(h.panel().querySelector('[data-ai-export-download]').disabled, false);
});

test('changed input revision invalidates in-flight response without silently downloading', async t => {
  const h = await setup(t); const stale = h.start();
  h.evaluate('analysisState.data.manual.preparation.revision += 1; renderAnalysisWorkspace()');
  assert.equal(stale.options.signal.aborted, true);
  h.zip(stale); await h.flush(); assert.equal(h.downloads.length, 0);
  const request = h.start(); assert.equal(JSON.parse(request.options.body).expected_revision, 8);
  h.zip(request); await h.flush(); assert.equal(h.downloads.length, 1);
});

test('in-place source update without rerender still rejects the old source snapshot', async t => {
  const h = await setup(t); const stale = h.start();
  h.evaluate('analysisState.data.manual.preparation.source_hash = "updated-source"');
  h.zip(stale); await h.flush();
  assert.equal(h.downloads.length, 0); assert.equal(h.created.length, 0);
  assert.match(status(h), /入力版が変わったため/);
  assert.equal(h.panel().querySelector('[data-ai-export-download]').disabled, false);
});
