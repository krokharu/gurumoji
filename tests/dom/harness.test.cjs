'use strict';
// Verify the offline test boundary independently of application assertions.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');

test('harness startup settles only synthetic API fixtures and runs every declared project script', async () => {
  const h = await createHarness();
  try {
    assert(h.requests.length > 0);
    assert(h.requests.every(request => request.settled && request.url.startsWith('/api/')));
    const sources = [...h.document.querySelectorAll('script[src]')].map(node => node.getAttribute('src'));
    assert(sources.length > 1);
    assert.equal(new Set(sources).size, sources.length);
    assert.equal(h.evaluate('typeof renderResult'), 'function');
    assert.equal(h.evaluate('typeof openFixedAnalysisRun'), 'function');
    assert.equal(h.evaluate('configLoadState'), 'loaded');
  } finally { h.close(); }
});

test('harness parses fixture strings as data in its own realm without executing text', async () => {
  const h = await createHarness();
  try {
    const text = '\"); window.fixtureExecuted = true; //<script>window.fixtureExecuted=true</script>';
    h.fixture({text, values: [null, 0, false, '']});
    assert.equal(h.evaluate('window.fixture.text'), text);
    assert.equal(h.evaluate('window.fixtureExecuted'), undefined);
    assert.equal(h.evaluate('Object.getPrototypeOf(window.fixture) === Object.prototype'), true);
    assert.equal(h.evaluate('Array.isArray(window.fixture.values)'), true);
    assert.equal(h.evaluate('window.fixture.values instanceof Array'), true);
  } finally { h.close(); }
});

test('harness queues same-origin APIs until the test supplies a response', async () => {
  const h = await createHarness();
  try {
    const result = h.w.fetch('/api/synthetic-proof');
    const request = h.requests.at(-1);
    assert.equal(request.settled, false);
    h.reply(request, {text: 'Synthetic only'}, 409);
    const response = await result;
    assert.equal(response.status, 409);
    assert.equal(response.ok, false);
    assert.equal((await response.json()).text, 'Synthetic only');
    assert.throws(() => h.reply(request, {}), /fixture already answered/);
    const failed = h.w.fetch('/api/synthetic-transport-failure');
    const failingRequest = h.requests.at(-1);
    h.fail(failingRequest, 'Synthetic lost response');
    await assert.rejects(failed, /Synthetic lost response/);
    assert.throws(() => h.fail(failingRequest), /fixture already answered/);
  } finally { h.close(); }
});

test('harness refuses external and non-API fetches and teardown reports the attempted escape', async () => {
  const h = await createHarness();
  for (const url of ['https://untrusted.invalid/api/test', '//untrusted.invalid/api/test', '/static/app.js', '/api/../private', 'data:text/plain,synthetic']) {
    await assert.rejects(h.w.fetch(url), /Only offline same-origin API fixtures/);
  }
  assert.equal(h.blocked.length, 5);
  assert(h.requests.every(request => request.settled));
  assert.throws(() => h.close(), {name: 'AssertionError'});
});

test('harness refuses alternate network constructors and beacon', async () => {
  const h = await createHarness();
  for (const api of ['XMLHttpRequest', 'WebSocket', 'EventSource']) {
    assert.throws(() => new h.w[api]('https://untrusted.invalid'), /forbidden/);
  }
  assert.throws(() => h.w.navigator.sendBeacon('https://untrusted.invalid', 'Synthetic'), /forbidden/);
  assert.deepEqual(h.blocked, ['XMLHttpRequest', 'WebSocket', 'EventSource', 'sendBeacon']);
  assert.throws(() => h.close(), {name: 'AssertionError'});
});

test('harness teardown fails rather than silently accepting an unanswered API request', async () => {
  const h = await createHarness();
  void h.w.fetch('/api/intentionally-unanswered');
  assert.throws(() => h.close(), /Every intercepted request must receive a test-owned fixture/);
});

test('harness timers are inert and semantic dialog shim does not claim browser modality', async () => {
  const h = await createHarness();
  try {
    h.evaluate('window.timerExecuted=false;setTimeout(()=>window.timerExecuted=true,0)');
    await h.flush();
    assert.equal(h.evaluate('window.timerExecuted'), false);
    const dialog = h.document.createElement('dialog');
    h.document.body.append(dialog);
    let closeEvents = 0;
    dialog.addEventListener('close', () => closeEvents++);
    dialog.showModal();
    assert.equal(dialog.open, true);
    dialog.close();
    assert.equal(dialog.open, false);
    assert.equal(closeEvents, 1);
    dialog.close();
    assert.equal(closeEvents, 1);
  } finally { h.close(); }
});
