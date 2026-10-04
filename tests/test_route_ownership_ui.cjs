// Original route and request handlers with synthetic deferred responses only.
// No browser, real HTTP, server, models, or user data.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../src/gurumoji/static/app.js'), 'utf8').replace(/\r\n/g, '\n');
function extract(name) {
  const match = new RegExp(`^(?:async )?function ${name}\\(`, 'm').exec(source);
  assert(match, name);
  return source.slice(match.index, source.indexOf('\n}', match.index) + 2);
}
function fixture() {
  const requests = [], effects = [];
  const ctx = {currentJob: null, currentRouteHash: '#/data', resultRequestSequence: 0,
    window: {location: {hash: '#/data'}, history: {
      replaceState(_state, _title, hash) {ctx.window.location.hash = hash;},
      pushState(_state, _title, hash) {ctx.window.location.hash = hash;}}},
    requestedParameters: new URLSearchParams(), confirmLeave: () => true,
    document: {querySelector: () => ({})},
    apiFetch(url) {let resolve; const promise = new Promise(yes => {resolve = yes;}); requests.push({url, resolve}); return promise;},
    readJsonResponse: async response => response.data,
    setAlert: (_node, message) => effects.push(['alert', message]),
    showView(view, {itemId = '', replace = false} = {}) {
      ++ctx.resultRequestSequence;
      ctx.view = view;
      ctx.syncRouteHash(view === 'item' ? `#/data/${itemId}` : view === 'library' ? '#/data' : `#/${view}`, {replace});
      effects.push(['view', view, itemId]);
      return true;
    },
    renderResult(data) {ctx.currentJob = data; ctx.showView('item', {itemId: data.id});},
  };
  vm.createContext(ctx);
  for (const name of ['parseRouteHash', 'syncRouteHash', 'openLibraryItem', 'applyRouteFromLocation']) vm.runInContext(extract(name), ctx);
  return {ctx, requests, effects,
    route(id) {ctx.window.location.hash = `#/data/${id}`; ctx.applyRouteFromLocation({fromHistory: true});},
    reply(index, id, ok = true) {requests[index].resolve({ok, data: ok ? {id} : {error: 'synthetic failure'}});},
  };
}
const tick = () => new Promise(resolve => setImmediate(resolve));
const passed = [];
(async () => {
  for (const order of ['old-first', 'new-first']) for (const oldOk of [true, false]) {
    const h = fixture(); h.route('A'); h.route('B');
    const orderIds = order === 'old-first' ? [[0, 'A', oldOk], [1, 'B', true]] : [[1, 'B', true], [0, 'A', oldOk]];
    for (const args of orderIds) {h.reply(...args); await tick();}
    assert.equal(h.ctx.currentJob?.id, 'B'); assert.equal(h.ctx.view, 'item');
    assert.equal(h.ctx.window.location.hash, '#/data/B');
    assert(!h.effects.some(([kind, view]) => kind === 'view' && view === 'library'));
    passed.push(`${order}-${oldOk ? 'success' : 'failure'}`);
  }
  for (const destination of ['new', 'library', 'speakers', 'analysis']) {
    const h = fixture(); h.route('A'); h.ctx.showView(destination); const before = h.effects.length;
    h.reply(0, 'A'); await tick(); assert.equal(h.ctx.view, destination); assert.equal(h.effects.length, before);
    passed.push(`leave-${destination}`);
  }
  {
    const h = fixture(); h.route('A'); h.route('B'); h.route('A');
    h.reply(0, 'A'); await tick(); h.reply(1, 'B'); await tick(); h.reply(2, 'A'); await tick();
    assert.equal(h.ctx.currentJob.id, 'A'); assert.equal(h.ctx.window.location.hash, '#/data/A');
    assert.deepEqual(h.effects, [['view', 'item', 'A']]); passed.push('ABA-keeps-newest-owner');
  }
  {
    const h = fixture(); h.route('A'); h.reply(0, 'A', false); await tick();
    assert.equal(h.ctx.view, 'library'); assert.equal(h.ctx.window.location.hash, '#/data');
    assert(h.effects.some(([kind]) => kind === 'alert')); passed.push('current-failure-retains-library-fallback');
  }
  console.log(JSON.stringify({scope: 'Original handlers, synthetic deferred transport; native history/browser not tested', passed}));
})().catch(error => {console.error(error); process.exitCode = 1;});
