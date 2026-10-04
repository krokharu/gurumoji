'use strict';
// Consume the nullable timing/coverage API in the actual automatic UI and its scope handlers.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
const plain = value => JSON.parse(JSON.stringify(value));
function fixture(seconds, timed, missing, percent) {
  const turns = timed + missing;
  const coverage = {speaking_seconds: seconds, speaking_percent: percent, timed_turn_count: timed, missing_time_turn_count: missing, turn_count: turns};
  return {item: {id: 'A', source_name: 'Synthetic timing', revision_count: 1, analysis_revision: 1}, executed: true,
    config: {}, annotations: {}, segments: [], automatic: {
      overview: {segment_count: turns, included_segment_count: turns, speaker_count: 1, total_speaking_seconds: seconds, timed_turn_count: timed, missing_time_turn_count: missing},
      speaker_metrics: [{speaker: 'A', speaker_name: 'Synthetic A', role: 'participant', color: '#1C6B50', profile: {organization: 'Synthetic group'}, ...coverage}],
      groups: [{group: 'Synthetic group', speaker_count: 1, ...coverage}], time_bins: []
    }};
}
async function setup(t, source) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture({itemId: source.item.id, data: source, config: source.config || {}, annotations: {}, mode: 'automatic', automaticScope: 'overall', automaticPage: 'overview', dirty: false});
  h.evaluate('Object.assign(analysisState,window.fixture);analysisCard.hidden=false;document.body.dataset.view="analysis";renderAnalysisWorkspace()');
  return h;
}
function metric(host, label) {
  const result = [...host.querySelectorAll('.analysis-overview-metric')].find(node => {
    const text = node.querySelector('span')?.textContent || '';
    return label instanceof RegExp ? label.test(text) : text === label;
  });
  assert(result, `metric ${label}`); return result;
}
function panel(h, title) {
  const result = [...h.document.querySelectorAll('.analysis-panel')].find(node => node.querySelector('h3')?.textContent === title);
  assert(result, title); return result;
}
function assertNoFalseZeroRatio(host) {
  assert(host.textContent.includes('割合は算出不可'), host.textContent);
  for (const node of host.querySelectorAll('[role="img"]')) assert(!/\b0\.0%/.test(node.getAttribute('aria-label') || ''), node.outerHTML);
}
const totalTimeLabel = /^(総発話時間|発話時間（時刻あり）)$/;
function assertUnknownRatioNote(host) {
  const note = host.querySelector('small'); assert(note);
  assert(/^(—|割合は算出不可)$/.test(note.textContent.trim()), note.textContent);
}

for (const scenario of [
  {name: 'all-missing', seconds: null, timed: 0, missing: 2, percent: null, text: /時刻不明2発話/},
  {name: 'partial', seconds: 10, timed: 1, missing: 1, percent: null, text: /時刻あり00:10.*1\/2発話.*時刻不明1発話/},
  {name: 'true-zero', seconds: 0, timed: 1, missing: 0, percent: null, text: /00:00/},
  {name: 'complete', seconds: 10, timed: 1, missing: 0, percent: 100, text: /00:10/}
]) test(`automatic ${scenario.name} time keeps its meaning across overview, speaker rows, detail and attribute group`, async t => {
  const source = fixture(scenario.seconds, scenario.timed, scenario.missing, scenario.percent);
  const h = await setup(t, source);
  const overall = metric(h.document, totalTimeLabel);
  assert.match(overall.querySelector('strong').textContent, scenario.text);
  if (!scenario.missing) assert(!overall.querySelector('strong').textContent.includes('時刻不明'));
  h.click('[data-analysis-jump="conversation"]');
  const speaker = panel(h, '話者ごとの発話量'); const group = panel(h, '話者グループの比較');
  for (const host of [speaker, group]) {
    assert.match(host.textContent, scenario.text);
    if (scenario.percent === null) assertNoFalseZeroRatio(host);
    else assert([...host.querySelectorAll('[role="img"]')].some(node => node.getAttribute('aria-label')?.includes('100.0%')));
  }
  h.click('[data-analysis-scope="speakers"]');
  const list = h.document.querySelector('.analysis-speaker-list'); assert(list);
  assert.match(list.querySelector('[data-analysis-speaker-id="A"] small').textContent, scenario.text);
  const detail = h.document.querySelector('.analysis-speaker-detail'); assert(detail);
  const selected = metric(detail, '発話時間'); assert.match(selected.querySelector('strong').textContent, scenario.text);
  if (scenario.percent === null) assertUnknownRatioNote(selected);
  const sort = h.document.querySelector('.analysis-speaker-sort-controls select');
  h.change(sort, 'attribute:organization');
  assert.match(h.document.querySelector('.analysis-speaker-list [data-analysis-speaker-id="A"] small').textContent, scenario.text);
  assert(h.document.querySelector('.analysis-speaker-list').textContent.includes('Synthetic group'));
  assert.deepEqual(plain(h.evaluate('analysisState.data')), source, 'Rendering must not normalize unknown timing back to zero');
  assert.equal(h.requests.filter(request => ['POST', 'PUT'].includes(request.options.method)).length, 0);
});

test('synthetic v5 backend fixture preserves mixed known, partial, missing and zero speaker values through actual selection', async t => {
  const source = require('./fixtures/participation-time-v5.json');
  assert.equal(source.algorithm_version, 'focus-group-local-5');
  const h = await setup(t, source);
  assert.match(metric(h.document, totalTimeLabel).querySelector('strong').textContent, /時刻あり00:12.*3\/5発話.*時刻不明2発話/);
  h.click('[data-analysis-jump="conversation"]');
  const groups = panel(h, '話者グループの比較');
  assert(panel(h, '発話量の変化（時間別）').querySelector('svg'), 'Observed partial coverage must retain its known-time graph');
  assert.match(groups.textContent, /時刻あり00:12.*2\/3発話.*時刻不明1発話/);
  assert.match(groups.textContent, /時刻不明1発話/); assertNoFalseZeroRatio(groups);
  h.click('[data-analysis-scope="speakers"]');
  for (const [id, expected] of [['A', /00:10/], ['B', /時刻あり00:02.*1\/2発話.*時刻不明1発話/], ['C', /時刻不明1発話/], ['Z', /00:00/]]) {
    h.click(`.analysis-speaker-list [data-analysis-speaker-id="${id}"]`);
    const detail = h.document.querySelector('.analysis-speaker-detail');
    assert.equal(detail.querySelector('h2').textContent, id);
    const value = metric(detail, '発話時間'); assert.match(value.querySelector('strong').textContent, expected);
    assertUnknownRatioNote(value);
  }
  assert.deepEqual(plain(h.evaluate('analysisState.data')), source);
});

test('an entirely untimed backend fixture does not turn its placeholder bin into measured-zero timeline or activity graphs', async t => {
  const source = require('./fixtures/participation-all-missing-v5.json');
  assert.equal(source.automatic.overview.timed_turn_count, 0);
  assert(source.automatic.overview.missing_time_turn_count > 0);
  assert.equal(source.automatic.time_bins.length, 1); assert.equal(source.automatic.time_bins[0].speaking_seconds, 0);
  const h = await setup(t, source); h.click('[data-analysis-jump="conversation"]');
  for (const title of ['発話量の変化（時間別）', '盛り上がりと議題・話題（時間別）']) {
    const host = panel(h, title);
    assert.equal(host.querySelector('svg'), null, `${title}: an unknown interval may not be plotted as measured zero`);
    assert(/時刻|算出/.test(host.textContent), host.textContent);
  }
  h.click('[data-analysis-scope="speakers"]');
  assert.equal(panel(h, 'この話者の時間推移').querySelector('svg'), null);
  assert.deepEqual(plain(h.evaluate('analysisState.data')), source);
});

test('observed zero-duration coverage may still display a zero timeline', async t => {
  const source = fixture(0, 1, 0, null);
  source.automatic.time_bins = [{index: 0, start: 0, end: 300, speaking_seconds: 0, turn_count: 0, speakers: []}];
  const h = await setup(t, source); h.click('[data-analysis-jump="conversation"]');
  assert(panel(h, '発話量の変化（時間別）').querySelector('svg'));
  assert(panel(h, '盛り上がりと議題・話題（時間別）').querySelector('svg'));
  assert.deepEqual(plain(h.evaluate('analysisState.data')), source);
});
