'use strict';
// Real saved-summary projection -> real HTML/scripts -> actual fixed-run lookup.
// This is offline DOM integration, not browser layout, native keyboard, or AT QA.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {createHarness} = require('./harness.cjs');
const root = path.resolve(process.env.GURUMOJI_DOM_SOURCE_ROOT || path.join(__dirname, '../..'));
const attack = '<img src=x onerror="alert(1)"><script>alert(2)</script><a href="javascript:alert(3)">version</a>';
const plain = value => JSON.parse(JSON.stringify(value));
const method = (version = 'saved-engine-4', registry = 'saved-registry-8') => ({
  method_id: 'participation', title: '保存した参加バランス', status: 'completed', analysis_unit: '発話',
  method_version: registry, engine: {version}, summaries: [{title: '保存値', text: '保存時の固定集計'}],
  findings: [], limitations: ['保存時の限界']
});
const result = (entry = method(), algorithms = {automatic: 'saved-algorithm-6'}) => ({
  parameters: {}, methods: [entry], algorithms
});
const fixtures = {};
for (const version of ['focus-group-local-4', 'focus-group-local-5', 'focus-group-local-6']) {
  fixtures[version] = result(method(version), {automatic: version});
}
fixtures.conflict = result(method('SAVED-METHOD-v4', 'SAVED-REGISTRY-v8'), {
  automatic: 'SAVED-GLOBAL-v6', unrelated: 'SAVED-UNRELATED-v1'
});
fixtures.missing = result(method(null, null));
fixtures.empty = result(method('', ''));
fixtures.whitespace = result(method(' \t\n ', ' \t\n '));
fixtures.absent = result(method()); delete fixtures.absent.methods[0].engine; delete fixtures.absent.methods[0].method_version;
fixtures.numeric = result(method(0, 7.5), {zero: 0, numeric: 7.5});
fixtures.object = result(method({nested: 'NOT-A-VERSION'}, {nested: 'NOT-A-REGISTRY'}), {automatic: {nested: 'NOT-A-VERSION'}});
fixtures.array = result(method(['NOT-A-VERSION'], ['NOT-A-REGISTRY']), {automatic: ['NOT-A-VERSION']});
fixtures.boolean = result(method(false, true), {automatic: false});
fixtures.hostile = result(method(attack, attack), Object.fromEntries([[attack, attack], ['__proto__', attack], ['constructor', attack]]));
fixtures.long = result(method('版'.repeat(10000), '登録'.repeat(10000)), {['算法'.repeat(10000)]: '計算'.repeat(10000)});
fixtures.algorithmOnly = {parameters: {}, methods: [], algorithms: {automatic: 'GLOBAL-ONLY-v3'}};
fixtures.manyAlgorithms = {parameters: {}, methods: [], algorithms: Object.fromEntries(Array.from({length: 40}, (_, i) => [`algorithm-${i}`, `saved-${i}`]))};
fixtures.budget = {parameters: {definitions: Array.from({length: 30}, () => ({definition_id: 'd', version: 7, name: '定義'.repeat(10000)}))},
  methods: Array.from({length: 20}, () => ({...method('計算'.repeat(10000), '形式'.repeat(10000)), title: '手法'.repeat(10000),
    summaries: Array.from({length: 10}, () => ({title: '集計'.repeat(10000), text: '本文'.repeat(10000)})),
    findings: Array.from({length: 10}, () => ({title: '見解'.repeat(10000), text: '本文'.repeat(10000)})),
    limitations: Array.from({length: 10}, () => '制約'.repeat(10000))})),
  algorithms: Object.fromEntries(Array.from({length: 40}, (_, i) => [`算法-${i}`, '計算'.repeat(10000)]))};
// Use the exact target source root for Python and JS. No application/server import.
const projected = JSON.parse(execFileSync(process.env.GURUMOJI_TEST_PYTHON || 'python3',
  [path.join(__dirname, 'project_saved_summary.py'), root], {
    input: JSON.stringify(fixtures), encoding: 'utf8', maxBuffer: 16 * 1024 * 1024,
    env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}
  }));

function latest(h, url) {
  const request = h.requests.findLast(entry => entry.url === url); assert(request, url); return request;
}
async function setup(t) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture({itemId: 'A', data: {item: {id: 'A', revision_count: 9, analysis_revision: 9},
    algorithm_version: 'CURRENT-DO-NOT-USE', automatic: {algorithm_version: 'CURRENT-DO-NOT-USE'}, segments: []}});
  h.evaluate('Object.assign(analysisState,window.fixture);document.querySelector("#analysis-card").append(buildAnalysisStorage());refreshAnalysisStorage()');
  return h;
}
async function open(h, summary, run = 'saved') {
  const form = h.document.querySelector('.analysis-fixed-lookup');
  form.querySelector('input').value = run; form.requestSubmit();
  const payload = {run: {id: run, item_id: 'A', kind: 'milestone_analysis', status: 'completed',
    created_at: 'synthetic-date', source_revision: 1, analysis_revision: 1,
    artifacts: [{id: 'saved-result', name: 'result.json', media_type: 'application/json', bytes: 1}]},
    integrity: 'verified', provenance: {method_version: 'SAVED-PACKAGE-REGISTRY-v9'},
    current_input: {stale: true}, saved_summary: summary};
  const copy = plain(summary); h.reply(latest(h, `/api/library/A/analysis/runs/${run}`), payload); await h.flush();
  assert.deepEqual(summary, copy, 'Rendering must not mutate the saved-summary fixture');
  assert.equal(h.document.querySelector('.analysis-fixed-dialog').open, true);
  const host = h.document.querySelector('.analysis-fixed-summary'); assert(host);
  assert(!host.textContent.includes('CURRENT-DO-NOT-USE'));
  assert(h.requests.every(request => !request.options.method || request.options.method === 'GET'));
  assert.equal(h.requests.filter(request => /\/analysis\//.test(request.url)).length, 1,
    'Version labels must require only the fixed saved-run read');
  return host;
}
function versionLine(card) {
  const line = [...card.querySelectorAll('p')].find(node => node.textContent.includes('保存した計算版'));
  assert(line, 'Each saved method must visibly identify its saved calculation version'); return line;
}
function noExecutableMarkup(host) {
  assert.equal(host.querySelector('script,iframe,object,embed,img,svg'), null);
  for (const node of host.querySelectorAll('*')) for (const attr of node.attributes) {
    assert(!/^on/i.test(attr.name));
    if (['href', 'src', 'action'].includes(attr.name)) assert(!/^\s*(javascript|data|vbscript):/i.test(attr.value));
  }
}

for (const version of ['focus-group-local-4', 'focus-group-local-5', 'focus-group-local-6']) {
  test(`saved ${version} is visible through the actual lookup without recomputation`, async t => {
    const summary = projected[version]; const h = await setup(t); const host = await open(h, summary);
    assert.equal(summary.methods[0].engine_version, version);
    assert.equal(summary.methods[0].engine_version_status, 'recorded');
    const card = host.querySelector('.analysis-fixed-method');
    assert(versionLine(card).textContent.includes(version));
    assert(card.textContent.includes('手法registry版')); assert(card.textContent.includes('saved-registry-8'));
    assert(host.textContent.includes('保存した算法一覧')); assert(host.textContent.includes('automatic'));
    assert(card.textContent.includes('保存時の固定集計')); assert(card.textContent.includes('保存時の限界'));
  });
}

test('conflicting saved engine, method registry, package registry and global algorithms remain separate facts', async t => {
  const h = await setup(t); const host = await open(h, projected.conflict); const card = host.querySelector('.analysis-fixed-method');
  assert(versionLine(card).textContent.includes('SAVED-METHOD-v4'));
  assert(card.textContent.includes('SAVED-REGISTRY-v8'));
  for (const value of ['SAVED-GLOBAL-v6', 'SAVED-UNRELATED-v1']) {
    assert(host.textContent.includes(value)); assert(!card.textContent.includes(value), 'Global algorithms must not be guessed onto a method');
  }
  assert(!card.textContent.includes('SAVED-PACKAGE-REGISTRY-v9'));
  assert(h.document.querySelector('.analysis-fixed-body').textContent.includes('SAVED-PACKAGE-REGISTRY-v9'));
});

for (const name of ['missing', 'empty', 'whitespace', 'absent']) test(`saved ${name} engine version is explicit and never filled from global or current values`, async t => {
  const h = await setup(t); const summary = projected[name]; const host = await open(h, summary);
  assert.equal(summary.methods[0].engine_version_status, 'missing');
  assert.equal(summary.methods[0].method_version_status, 'missing');
  const card = host.querySelector('.analysis-fixed-method');
  assert.match(versionLine(card).textContent, /記録なし/);
  assert(!card.textContent.includes('saved-algorithm-6'));
  assert(host.textContent.includes('saved-algorithm-6'), 'A separately saved global version must remain inspectable');
});

test('finite numeric saved versions preserve zero and fractional values', async t => {
  const summary = projected.numeric; const h = await setup(t); const host = await open(h, summary);
  assert.equal(summary.methods[0].engine_version, '0'); assert.equal(summary.methods[0].method_version, '7.5');
  assert.equal(summary.methods[0].engine_version_status, 'recorded');
  const line = versionLine(host.querySelector('.analysis-fixed-method')).textContent;
  assert.match(line, /保存した計算版[^/]*0/); assert(!line.includes('記録なし'));
  assert.deepEqual(summary.algorithms.map(entry => entry.version), ['0', '7.5']);
});

for (const name of ['object', 'array', 'boolean']) test(`unsupported ${name} version is disclosed without stringifying a fake version`, async t => {
  const summary = projected[name]; const h = await setup(t); const host = await open(h, summary);
  assert.equal(summary.methods[0].engine_version, null); assert.equal(summary.methods[0].engine_version_status, 'unsupported');
  assert.equal(summary.methods[0].method_version, null); assert.equal(summary.methods[0].method_version_status, 'unsupported');
  assert.match(versionLine(host.querySelector('.analysis-fixed-method')).textContent, /表示できない形式/);
  assert(!host.textContent.includes('NOT-A-VERSION')); assert(!host.textContent.includes('NOT-A-REGISTRY')); assert(!host.textContent.includes('[object Object]'));
  assert.equal(summary.algorithms[0].status, 'unsupported');
});

test('hostile saved versions and algorithm names remain literal text in the real DOM', async t => {
  const h = await setup(t); const host = await open(h, projected.hostile);
  assert.equal(projected.hostile.methods[0].engine_version, attack);
  assert(versionLine(host.querySelector('.analysis-fixed-method')).textContent.includes(attack));
  assert(host.textContent.includes('constructor')); assert(host.textContent.includes('__proto__')); noExecutableMarkup(host);
});

test('long saved version strings are clipped with disclosure and retain the full-file reading route', async t => {
  const summary = projected.long; const h = await setup(t); const host = await open(h, summary);
  assert.equal(summary.truncated, true); assert(summary.methods[0].engine_version.length > 0);
  assert(summary.methods[0].engine_version.length <= 256); assert(summary.methods[0].method_version.length <= 256);
  assert(summary.algorithms.every(entry => entry.name.length <= 256 && entry.version.length <= 256));
  assert(versionLine(host.querySelector('.analysis-fixed-method')).textContent.includes(summary.methods[0].engine_version));
  assert.match(host.textContent, /省略/); assert(host.textContent.includes('result.json'));
  const button = [...h.document.querySelectorAll('.analysis-fixed-file button')].find(node => node.textContent === 'result.json を読む'); assert(button);
  h.click(button); const raw = JSON.stringify(fixtures.long);
  const excerpt = new TextDecoder('utf-8').decode(Buffer.from(raw).subarray(0, 16384), {stream: true});
  assert(Buffer.byteLength(excerpt) <= 16384);
  h.reply(latest(h, '/api/library/A/analysis/runs/saved/previews/saved-result'), {preview: {
    run_id: 'saved', artifact_id: 'saved-result', format: 'text', text: excerpt, truncated: true
  }}); await h.flush();
  assert.equal(h.document.querySelector('.analysis-fixed-preview pre').textContent, excerpt);
  assert(h.document.querySelector('.analysis-fixed-preview pre').textContent.includes('登録'.repeat(300)));
  assert(h.document.querySelector('.analysis-fixed-body a[download]'));
});

test('saved algorithm list is inspectable even without method summaries', async t => {
  const h = await setup(t); const host = await open(h, projected.algorithmOnly);
  assert.equal(host.querySelectorAll('.analysis-fixed-method').length, 0);
  assert(host.textContent.includes('保存した算法一覧')); assert(host.textContent.includes('GLOBAL-ONLY-v3'));
});

test('large saved algorithm inventory is bounded and visibly disclosed as partial', async t => {
  const summary = projected.manyAlgorithms; const h = await setup(t); const host = await open(h, summary);
  assert(summary.algorithms.length > 0 && summary.algorithms.length <= 20);
  assert.equal(summary.truncated, true); assert.match(host.textContent, /省略/);
  assert(host.textContent.includes(summary.algorithms[0].version));
});

test('method, definition and algorithm projection share the 16 KiB text budget', async t => {
  const summary = projected.budget; const h = await setup(t); const host = await open(h, summary);
  assert.equal(summary.text_byte_limit, 16384); assert.equal(summary.truncated, true);
  const bytes = value => typeof value === 'string' ? Buffer.byteLength(value) : Array.isArray(value)
    ? value.reduce((n, item) => n + bytes(item), 0) : value && typeof value === 'object'
    ? Object.entries(value).reduce((n, [key, item]) => n + (['engine_version_status', 'method_version_status'].includes(key) ? 0 : bytes(item)), 0) : 0;
  const algorithmBytes = (summary.algorithms || []).reduce((n, entry) => n + bytes(entry.name) + bytes(entry.version), 0);
  assert(bytes(summary.methods) + bytes(summary.definitions) + algorithmBytes <= 16384);
  assert(summary.methods.length <= 12); assert(summary.definitions.length <= 20); assert(summary.algorithms.length <= 20);
  assert.match(host.textContent, /省略/); assert(host.textContent.includes('result.json'));
  noExecutableMarkup(host);
});

test('a recorded version clipped to empty by the shared budget is labelled omitted rather than missing', async t => {
  // This is the explicit API status contract at budget exhaustion, not a legacy
  // absent field. The full raw version remains available in the saved file.
  const summary = {methods: [{...method(), engine_version: '', engine_version_status: 'recorded',
    method_version: '', method_version_status: 'recorded'}],
    algorithms: [{name: 'automatic', version: '', status: 'recorded'}],
    definitions: [], truncated: true, text_byte_limit: 16384, total_methods: 1};
  delete summary.methods[0].engine;
  const h = await setup(t); const host = await open(h, summary);
  const line = versionLine(host.querySelector('.analysis-fixed-method')).textContent;
  assert.match(line, /省略/); assert(!line.includes('記録なし'));
  assert(host.textContent.includes('result.json'));
});
