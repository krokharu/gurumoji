'use strict';
// Bound, read-only backend time projections; actual result/editor/Save DOM handlers.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
const fixtures = require('./fixtures/timing-projection.json');
const plain = value => JSON.parse(JSON.stringify(value));
const cells = h => [...h.document.querySelectorAll('.speaker-metric-cell')].map(node => node.textContent);
const unknown = value => /不明|未確定|算出不可|算出でき|利用不可/.test(value);
function source(name) { return plain(fixtures.cases[name].job); }
async function setup(t, job) {
  const h = await createHarness(); t.after(() => h.close()); h.fixture(job); h.evaluate('renderResult(window.fixture)'); return h;
}
function assertKnown(h, seconds, count = 1) {
  const metric = plain(h.evaluate('speakerMetrics().A'));
  assert.equal(metric.seconds, seconds); assert.equal(metric.timedCount, count); assert.equal(metric.missingTimeCount, 0);
  assert.equal(metric.share, seconds ? 1 : null);
  assert.match(cells(h)[0], new RegExp(seconds === 20 ? '0:20' : seconds === 0 ? '0:00' : '0:10'));
}
function assertUnknown(h, count = 1) {
  const metric = plain(h.evaluate('speakerMetrics().A'));
  assert.equal(metric.seconds, null); assert.equal(metric.timedCount, 0); assert.equal(metric.missingTimeCount, count);
  assert.equal(metric.share, null); assert(unknown(cells(h)[0]), cells(h)[0]);
  assert(!/\d+\.\d+%/.test(cells(h)[0]), cells(h)[0]);
  assert(!h.document.querySelector('#speaker-insights').textContent.includes('参加者内50%以上'));
}
async function saveRaw(h, job, expectedSegments = job.segments) {
  h.click('#save-button'); const request = h.requests.findLast(item => item.options.method === 'PUT'); assert(request);
  const body = JSON.parse(request.options.body);
  assert(!Object.hasOwn(body, 'segment_timings'), 'Derived projection is read-only and not written as user data');
  const withoutImplicitEmotion = body.segments.map((segment, index) => {
    if (!Object.hasOwn(expectedSegments[index], 'kushinada_label')) { const result = {...segment}; delete result.kushinada_label; return result; }
    return segment;
  });
  assert.deepEqual(withoutImplicitEmotion, expectedSegments, 'Raw values/types must survive Save unless the user explicitly edited them');
  h.reply(request, {...job, segments: expectedSegments, revision_count: Number(job.revision_count || 0) + 1}); await h.flush();
}
for (const name of ['numeric_ascii', 'numeric_fullwidth', 'numeric_arabic', 'numeric_underscore']) test(`backend-bound ${name} times display ten seconds without changing raw input or Save`, async t => {
  const job = source(name); assert.equal(job.segment_timings[0].valid, true);
  const h = await setup(t, job); assertKnown(h, 10);
  assert.deepEqual(plain(h.evaluate('currentJob.segments')), job.segments);
  h.fixture(job.segments[0]);
  assert.equal(h.evaluate('analysisEvidenceTimeValid(window.fixture)'), false, 'Measurement compatibility must not loosen the separate audio/evidence guard');
  await saveRaw(h, job);
});

test('other accepted numeric strings and observed zero use the saved projection', async t => {
  for (const [name, seconds] of [['numeric_padded', 10], ['numeric_exponent', 10], ['numeric_zero', 0], ['true_zero', 0]]) {
    const job = source(name); const h = await setup(t, job); assertKnown(h, seconds);
    assert.deepEqual(plain(h.evaluate('currentJob.segments')), job.segments);
  }
});

test('real timestamp edits invalidate the old projection and refresh visible speaker measurements', async t => {
  const job = source('numeric_ascii'); const h = await setup(t, job); assertKnown(h, 10);
  h.click('.segment-edit');
  h.change(h.document.querySelector('[data-segment-field="start"]'), '0');
  assertUnknown(h); // Start is now numeric while unchanged end remains a string.
  h.change(h.document.querySelector('[data-segment-field="end"]'), '20');
  h.click('[data-item-tab="conversation"]'); assertKnown(h, 20);
  const edited = plain(h.evaluate('currentJob.segments'));
  assert.equal(edited[0].start, 0); assert.equal(edited[0].end, 20);
  assert.deepEqual(plain(h.evaluate('currentJob.segment_timings')), job.segment_timings, 'Local edit does not forge a replacement backend projection');
  await saveRaw(h, job, edited);
});

test('stale ID, raw timing, unknown flag, order, count, and duplicate bindings fall back conservatively', async t => {
  const mutations = [
    job => { job.segments[0].id = 'different-id'; },
    job => { job.segments[0].start = '1'; },
    job => { job.segments[0].end = '11'; },
    job => { job.segments[0].time_unknown = true; },
    job => { job.segment_timings.reverse(); },
    job => { job.segment_timings.pop(); },
    job => { job.segments[1].id = job.segments[0].id; job.segment_timings[1].segment_id = job.segment_timings[0].segment_id; }
  ];
  for (const mutate of mutations) {
    const job = source('two'); mutate(job); const h = await setup(t, job);
    // Binding failure of one row may conservatively invalidate the entire array; it must never keep both rows.
    const metric = plain(h.evaluate('speakerMetrics().A'));
    assert(metric.timedCount < 2, JSON.stringify(metric)); assert(metric.missingTimeCount > 0);
    assert.equal(metric.share, null); assert(!/\d+\.\d+%/.test(cells(h)[0]));
    assert.deepEqual(plain(h.evaluate('currentJob.segments')), job.segments);
  }
});

test('malformed normalized projection rows cannot supply seconds or percentage warnings', async t => {
  const mutations = [
    row => { row.valid = 'true'; }, row => { row.start = '0'; }, row => { row.end = '10'; },
    row => { row.start = null; }, row => { row.end = 2678401; }, row => { row.start = 11; row.end = 10; },
    row => { row.source_start = 0; }
  ];
  for (const mutate of mutations) {
    const job = source('numeric_ascii'); mutate(job.segment_timings[0]); const h = await setup(t, job); assertUnknown(h);
    assert.deepEqual(plain(h.evaluate('currentJob.segments')), job.segments);
  }
});

test('real delete and Undo invalidate and restore the original two-row binding', async t => {
  const job = source('two'); const h = await setup(t, job); assertKnown(h, 20, 2);
  h.click('.segment-delete'); assertUnknown(h, 1);
  h.click('#undo-segment-delete'); assertKnown(h, 20, 2);
  assert.deepEqual(plain(h.evaluate('currentJob.segments')), job.segments);
  await saveRaw(h, job);
});

test('legacy numeric rows retain strict numeric fallback while missing or invalid projections stay unknown', async t => {
  const job = source('number'); delete job.segment_timings;
  const h = await setup(t, job); assertKnown(h, 10); await saveRaw(h, job);
  for (const name of ['numeric_ascii', 'unknown', 'bad', 'above_limit']) {
    const candidate = source(name); delete candidate.segment_timings; const alternate = await setup(t, candidate); assertUnknown(alternate);
  }
});

test('ordinary numeric time editing also refreshes the visible speaker cell without requiring a projection', async t => {
  const job = source('number'); delete job.segment_timings;
  const h = await setup(t, job); assertKnown(h, 10);
  h.click('.segment-edit'); h.change(h.document.querySelector('[data-segment-field="end"]'), '20');
  h.click('[data-item-tab="conversation"]'); assertKnown(h, 20);
  const edited = plain(h.evaluate('currentJob.segments')); assert.equal(edited[0].end, 20);
  await saveRaw(h, job, edited);
});

// Normal output-JSON import admits Python-false [] / {} markers. These are full DTOs,
// parsed independently from the source-binding containers, not hand-authored metric inputs.
const importedMarkers = require('./fixtures/import-timing-markers.json');
function importedSource(id) {
  const found = importedMarkers.cases.find(item => item.id === id); assert(found, id); return plain(found);
}
async function settleImportedStatus(h, job) {
  for (const request of h.requests.filter(item => !item.settled)) {
    assert.equal(request.url, `/api/library/${job.id}/meeting-obsidian`);
    assert.equal(request.options.method || 'GET', 'GET');
    h.reply(request, {status: 'unprepared', message: 'Synthetic offline status'});
  }
  await h.flush();
}
async function setupImported(t, job) {
  const h = await setup(t, job); await settleImportedStatus(h, job); return h;
}
function importedCell(h, speaker) {
  const row = [...h.document.querySelectorAll('.conversation-speaker-sheet tbody tr')]
    .find(node => node.querySelector('.speaker-label-cell')?.title === `話者ID: ${speaker}`);
  assert(row, speaker); return row.querySelector('.speaker-metric-cell').textContent;
}
function assertImportedMetrics(h, expected) {
  const actual = plain(h.evaluate('speakerMetrics()'));
  assert.deepEqual(actual, expected);
  for (const [speaker, metric] of Object.entries(expected)) {
    const cell = importedCell(h, speaker);
    if (metric.seconds === null) {
      assert(unknown(cell), cell); assert(!/\d+\.\d+%/.test(cell), cell);
    } else {
      const secondsText = {0: '00:00', 5: '00:05', 10: '00:10', 20: '00:20'}[metric.seconds]; assert(secondsText);
      assert(cell.includes(secondsText), cell); assert(!cell.includes('時刻不明'), cell);
    }
    if (metric.share !== null) assert(cell.includes(`${(metric.share * 100).toFixed(1)}%`), cell);
  }
}
for (const kind of ['array', 'object']) for (const bounds of ['positive', 'string', 'zero']) {
  test(`imported empty ${kind} marker with ${bounds} bounds preserves measured time, raw Save and the separate audio guard`, async t => {
    const fixture = importedSource(`marker-${kind}-${bounds}`); const job = fixture.job;
    const h = await setupImported(t, job); assertImportedMetrics(h, fixture.expected.metrics);
    assert.equal(h.evaluate('currentJob.segments[0].time_unknown === currentJob.segment_timings[0].source_time_unknown'), false,
      'A real parsed DTO has distinct marker containers; object identity cannot be its binding');
    assert.deepEqual(plain(h.evaluate('currentJob.segments')), job.segments);
    assert.deepEqual(plain(h.evaluate('currentJob.segment_timings')), job.segment_timings);
    assert.equal(h.evaluate('analysisEvidenceTimeValid(currentJob.segments[0])'), false, 'Measurement compatibility does not change audio/evidence validity');
    await saveRaw(h, job); await settleImportedStatus(h, job);
    assert.deepEqual(plain(h.evaluate('currentJob.segments')), job.segments);
  });
}
for (const kind of ['array', 'object']) test(`imported empty ${kind} marker survives real time edits while the old binding expires and the visible cells update`, async t => {
  const fixture = importedSource(`marker-${kind}-string`); const job = fixture.job;
  const h = await setupImported(t, job); assertImportedMetrics(h, fixture.expected.metrics);
  const candidateRow = () => [...h.document.querySelectorAll('.segment')].find(node => node.dataset.segmentId === 'candidate');
  h.click(candidateRow().querySelector('.segment-edit'));
  h.change(candidateRow().querySelector('[data-segment-field="start"]'), '0');
  assert.equal(h.evaluate('speakerMetrics().A.seconds'), null);
  assert(unknown(importedCell(h, 'A'))); assert(!/\d+\.\d+%/.test(importedCell(h, 'B')));
  h.change(candidateRow().querySelector('[data-segment-field="end"]'), '20');
  h.click('[data-item-tab="conversation"]');
  const expected = plain(fixture.expected.metrics);
  Object.assign(expected.A, {seconds: 20, timedSeconds: 20, share: .8}); expected.B.share = .2;
  assertImportedMetrics(h, expected);
  const edited = plain(h.evaluate('currentJob.segments'));
  assert.deepEqual(edited[0].time_unknown, job.segments[0].time_unknown);
  assert.equal(Array.isArray(edited[0].time_unknown), kind === 'array');
  assert.equal(edited[0].start, 0); assert.equal(edited[0].end, 20);
  assert.deepEqual(plain(h.evaluate('currentJob.segment_timings')), job.segment_timings);
  assert.equal(h.evaluate('analysisEvidenceTimeValid(currentJob.segments[0])'), false);
  await saveRaw(h, job, edited); await settleImportedStatus(h, job);
});
for (const kind of ['array', 'object']) test(`nonempty or type-changed ${kind} import markers cannot reuse a stale string-timing projection`, async t => {
  for (const changed of [kind === 'array' ? ['unknown'] : {unknown: true}, kind === 'array' ? {} : []]) {
    const fixture = importedSource(`marker-${kind}-string`); const job = fixture.job;
    job.segments[0].time_unknown = changed;
    const h = await setupImported(t, job);
    const metric = plain(h.evaluate('speakerMetrics()'));
    assert.equal(metric.A.seconds, null); assert.equal(metric.A.timedCount, 0); assert.equal(metric.A.missingTimeCount, 1);
    assert.equal(metric.A.share, null); assert.equal(metric.B.seconds, 5); assert.equal(metric.B.share, null);
    assert(unknown(importedCell(h, 'A'))); assert(!/\d+\.\d+%/.test(importedCell(h, 'B')));
    assert(!h.document.querySelector('#speaker-insights').textContent.includes('参加者内50%以上'));
    assert.deepEqual(plain(h.evaluate('currentJob.segments')), job.segments);
    assert.equal(h.evaluate('analysisEvidenceTimeValid(currentJob.segments[0])'), false);
    await saveRaw(h, job); await settleImportedStatus(h, job);
  }
});
