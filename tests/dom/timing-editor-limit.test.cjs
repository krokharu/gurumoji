'use strict';
// Speaker measurement uses the backend's 31-day bound without changing raw edit data.
// V2: actual project DOM and Save handlers; no browser/native-input/media claim.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
const plain = value => JSON.parse(JSON.stringify(value));
const MAX_SECONDS = 2678400;
function job(segments) {
  return {id: 'timing-editor', source_name: 'Synthetic timing boundary', revision_count: 1, files: [],
    segments: segments.map((segment, index) => ({id: `s${index}`, speaker: 'A', text: 'Synthetic timing', kushinada_label: '', ...segment})),
    speaker_names: {}, speaker_profiles: {
      A: {display_name: 'Synthetic A', session_role: 'participant', session_role_source: 'explicit'},
      B: {display_name: 'Synthetic B', session_role: 'participant', session_role_source: 'explicit'}
    }, session_profile: {session_type: 'focus_group'}};
}
async function setup(t, source) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture(source); h.evaluate('renderResult(window.fixture)'); return h;
}
const cells = h => [...h.document.querySelectorAll('.speaker-metric-cell')].map(node => node.textContent);
const unknown = value => /不明|未確定|算出不可|算出でき|利用不可/.test(value);
async function saveUnchanged(h, source) {
  assert.deepEqual(plain(h.evaluate('currentJob.segments')), source.segments, 'Measurement display must leave raw values intact');
  h.click('#save-button');
  const request = h.requests.findLast(item => item.options.method === 'PUT'); assert(request);
  const body = JSON.parse(request.options.body);
  assert.deepEqual(body.segments, source.segments, 'Save may not clamp or coerce raw timestamps as a side effect of measurement');
  h.reply(request, {...source, revision_count: 2}); await h.flush();
  assert.deepEqual(plain(h.evaluate('currentJob.segments')), source.segments);
}
for (const [name, start, end] of [
  ['above maximum', MAX_SECONDS - 1, MAX_SECONDS + 1],
  ['huge finite timestamp', 0, 1e308],
  ['zero duration beyond maximum', MAX_SECONDS + 1, MAX_SECONDS + 1]
]) test(`speaker editor marks ${name} unknown and preserves the raw Save payload`, async t => {
  const source = job([{start, end}]); const h = await setup(t, source);
  const cell = cells(h)[0]; assert(unknown(cell), cell);
  assert(!/\d+\.\d+%/.test(cell), cell);
  assert(!h.document.querySelector('#speaker-insights').textContent.includes('参加者内50%以上'));
  const measured = plain(h.evaluate('speakerMetrics().A'));
  assert.equal(measured.count, 1); assert.equal(measured.timedCount, 0);
  assert.equal(measured.missingTimeCount, 1); assert.equal(measured.seconds, null); assert.equal(measured.share, null);
  await saveUnchanged(h, source);
});

test('speaker editor accepts the exact maximum and preserves one measured second', async t => {
  const source = job([{start: MAX_SECONDS - 1, end: MAX_SECONDS}]); const h = await setup(t, source);
  assert.match(cells(h)[0], /0:01/); assert.match(cells(h)[0], /100\.0%/);
  const measured = plain(h.evaluate('speakerMetrics().A'));
  assert.equal(measured.seconds, 1); assert.equal(measured.timedCount, 1); assert.equal(measured.missingTimeCount, 0);
  await saveUnchanged(h, source);
});

test('speaker editor preserves an observed zero exactly at the maximum without inventing its share', async t => {
  const source = job([{start: MAX_SECONDS, end: MAX_SECONDS}]); const h = await setup(t, source);
  assert.match(cells(h)[0], /0:00/); assert(!/\d+\.\d+%/.test(cells(h)[0]));
  const measured = plain(h.evaluate('speakerMetrics().A'));
  assert.equal(measured.seconds, 0); assert.equal(measured.timedCount, 1);
  assert.equal(measured.missingTimeCount, 0); assert.equal(measured.share, null);
  await saveUnchanged(h, source);
});

test('a speaker above the maximum cannot dominate another speaker or create a percentage warning', async t => {
  const source = job([{start: 0, end: 10}, {speaker: 'B', start: 0, end: MAX_SECONDS + 1}]);
  const h = await setup(t, source); const rendered = cells(h);
  assert.equal(rendered.length, 2); assert.match(rendered[0], /0:10/); assert(unknown(rendered[1]), rendered[1]);
  assert(rendered.every(value => !/\d+\.\d+%/.test(value)), rendered.join('; '));
  assert(!h.document.querySelector('#speaker-insights').textContent.includes('参加者内50%以上'));
  assert.deepEqual(plain(h.evaluate('currentJob.segments')), source.segments);
});
