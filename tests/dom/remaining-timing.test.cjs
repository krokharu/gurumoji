'use strict';
// Static projections of synthetic Flask output, through actual project DOM/mode/scope handlers.
// Only executed=true is presentation scaffolding. The manifest records the unmodified API source.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
const fixtures = require('./fixtures/remaining-timing-v7.json');
const plain = value => JSON.parse(JSON.stringify(value));
const text = node => node.textContent.replace(/\s+/g, ' ').trim();
function panel(h, title) {
  const result = [...h.document.querySelectorAll('.analysis-panel')].find(node => node.querySelector('h3')?.textContent === title);
  assert(result, title); return result;
}
function metric(host, label) {
  const result = [...host.querySelectorAll('.analysis-overview-metric')].find(node => label.test(node.querySelector('span')?.textContent || ''));
  assert(result, String(label)); return result;
}
async function setup(t, source) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture({itemId: source.item.id, data: source, config: source.config, annotations: source.annotations,
    mode: 'automatic', automaticScope: 'overall', automaticPage: 'overview', dirty: false});
  h.evaluate('Object.assign(analysisState,window.fixture);analysisCard.hidden=false;document.body.dataset.view="analysis";renderAnalysisWorkspace()');
  return h;
}
const scenarios = [
  {name: 'all_unknown', count: 1, seconds: null, endpoint: null, timed: 0, missing: 1, timeText: /時刻不明1発話/},
  {name: 'partial', count: 2, seconds: 10, endpoint: 10, timed: 1, missing: 1, timeText: /時刻あり00:10.*1\/2発話.*時刻不明1発話/},
  {name: 'true_zero', count: 1, seconds: 0, endpoint: 0, timed: 1, missing: 0, timeText: /00:00/},
  {name: 'true_zero_at_ten', count: 1, seconds: 0, endpoint: 10, timed: 1, missing: 0, timeText: /00:00/},
  {name: 'empty', count: 0, seconds: 0, endpoint: null, timed: 0, missing: 0, timeText: /00:00/},
  {name: 'positive', count: 1, seconds: 10, endpoint: 10, timed: 1, missing: 0, timeText: /00:10/}
];
for (const scenario of scenarios) test(`remaining timing ${scenario.name}: endpoint, emotion, code, and temporal events keep their meanings`, async t => {
  const source = fixtures.cases[scenario.name].analysis;
  assert.equal(source.algorithm_version, 'focus-group-local-7');
  const overview = source.automatic.overview;
  assert.equal(overview.session_duration, scenario.endpoint);
  assert.equal(overview.session_timed_turn_count, scenario.timed);
  assert.equal(overview.session_missing_time_turn_count, scenario.missing);
  const code = source.manual.code_metrics.find(row => row.id === 'c'); assert(code);
  assert.equal(code.speaking_seconds, scenario.seconds);
  assert.equal(code.timed_turn_count, scenario.timed); assert.equal(code.missing_time_turn_count, scenario.missing);
  assert.equal(code.segment_count, scenario.count);
  const bins = source.automatic.time_bins;
  if (!scenario.timed) assert.deepEqual(bins, []);
  else {
    assert.equal(bins.reduce((sum, bin) => sum + bin.turn_count, 0), scenario.timed, 'Zero-duration turns remain observed events');
    assert.equal(Math.max(...bins.map(bin => bin.end)), scenario.endpoint, 'No invented 300-second tail');
  }
  const h = await setup(t, source);
  const endpoint = metric(h.document, /^(会話時間|時刻ありの最終終了位置)$/);
  assert.match(text(endpoint), /時刻ありの最終終了位置/, 'Observed endpoint must not be labeled elapsed conversation duration');
  if (scenario.endpoint === null) {
    assert.match(endpoint.querySelector('strong').textContent, /不明|算出不可|—/);
    assert(!endpoint.querySelector('strong').textContent.includes('00:00'));
  } else assert.match(endpoint.querySelector('strong').textContent, scenario.endpoint === 0 ? /00:00/ : /00:10/);
  if (scenario.missing) assert.match(text(endpoint), new RegExp(`時刻不明${scenario.missing}発話`));
  h.click('[data-analysis-jump="conversation"]');
  const emotions = panel(h, '声から推定した感情の分布');
  const emotionRows = [...emotions.querySelectorAll('.analysis-list-row')];
  if (scenario.count) {
    assert.equal(emotionRows.length, 1); assert.match(text(emotionRows[0]), new RegExp(`${scenario.count}件`));
    assert.match(text(emotionRows[0]), scenario.timeText);
    if (scenario.seconds === null) assert(!text(emotionRows[0]).includes('00:00'));
    if (!scenario.missing) assert(!text(emotionRows[0]).includes('時刻不明'));
  } else {
    assert.equal(emotionRows.length, 0); assert.match(text(emotions), /利用できる推定値がありません/);
  }
  for (const title of ['発話量の変化（時間別）', '盛り上がりと議題・話題（時間別）']) {
    const host = panel(h, title);
    if (!scenario.timed) assert.equal(host.querySelector('svg'), null, `${title}: empty or unobserved time is not a measured zero graph`);
    else if (scenario.endpoint > 0) assert(host.querySelector('svg'), title);
  }
  h.click('[data-analysis-mode="manual"]');
  const codeRow = panel(h, '手動コードの集計').querySelector('[data-qualitative-code="c"]'); assert(codeRow);
  assert.match(text(codeRow), new RegExp(`${scenario.count}発言`));
  assert.match(text(codeRow), scenario.timeText);
  if (scenario.seconds === null) assert(!text(codeRow).includes('00:00'));
  const bar = codeRow.querySelector('[role="img"]'); assert(bar);
  assert.match(bar.getAttribute('aria-label'), new RegExp(`Synthetic code: ${scenario.count}発言`), 'Code bar stays a count scale');
  h.click('[data-analysis-mode="automatic"]');
  assert.deepEqual(plain(h.evaluate('analysisState.data')), source, 'Render/mode changes must not recalculate API values');
  assert.equal(h.requests.filter(request => ['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.options.method)).length, 0);
});

test('excluded untimed source affects the observed endpoint coverage but not included speaking-time coverage', async t => {
  const source = fixtures.cases.excluded_unknown.analysis;
  const overview = source.automatic.overview;
  assert.equal(overview.session_timed_turn_count, 1); assert.equal(overview.session_missing_time_turn_count, 1);
  assert.equal(overview.timed_turn_count, 1); assert.equal(overview.missing_time_turn_count, 0);
  assert.equal(overview.included_segment_count, 1); assert.equal(overview.segment_count, 2);
  const h = await setup(t, source);
  const endpoint = metric(h.document, /^時刻ありの最終終了位置$/);
  assert.match(text(endpoint), /00:10/); assert.match(text(endpoint), /時刻不明1発話/);
  const speaking = metric(h.document, /^(総発話時間|発話時間（時刻あり）)$/);
  assert.match(speaking.querySelector('strong').textContent, /00:10/);
  assert(!speaking.querySelector('strong').textContent.includes('時刻不明'), text(speaking));
  h.click('[data-analysis-jump="conversation"]');
  const emotion = panel(h, '声から推定した感情の分布').querySelector('.analysis-list-row'); assert(emotion);
  assert.match(text(emotion), /1件.*00:10/); assert(!text(emotion).includes('時刻不明'));
  assert.deepEqual(plain(h.evaluate('analysisState.data')), source);
});
