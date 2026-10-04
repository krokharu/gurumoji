'use strict';
// Minimal synthetic v6 backend projections. Real rendered HTML/all scripts and actual scope handlers.
// V2 DOM integration only; not browser layout, native keyboard, or assistive-technology acceptance.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
const plain = value => JSON.parse(JSON.stringify(value));
const text = node => node.textContent.replace(/\s+/g, ' ').trim();
function panel(h, title) {
  const node = [...h.document.querySelectorAll('.analysis-panel')].find(n => n.querySelector('h3')?.textContent === title);
  assert(node, title); return node;
}
function metric(host, label) {
  const node = [...host.querySelectorAll('.analysis-overview-metric')].find(n => n.querySelector('span')?.textContent === label);
  assert(node, label);
  return {value: node.querySelector('strong').textContent, note: node.querySelector('small')?.textContent || ''};
}
async function setup(t, source) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture({itemId: source.item.id, data: source, config: source.config, annotations: source.annotations,
    mode: 'automatic', automaticScope: 'overall', automaticPage: 'overview', dirty: false});
  h.evaluate('Object.assign(analysisState,window.fixture);analysisCard.hidden=false;document.body.dataset.view="analysis";renderAnalysisWorkspace()');
  return h;
}
function noMutationRequests(h) {
  assert.equal(h.requests.filter(r => ['POST', 'PUT', 'PATCH', 'DELETE'].includes(r.options.method)).length, 0);
}
for (const scope of ['participant', 'all']) test(`mixed role v6 ${scope} preserves role ambiguity and observed time through actual scope controls`, async t => {
  const source = require(`./fixtures/mixed-role-${scope}-v6.json`);
  assert.equal(source.algorithm_version, 'focus-group-local-6');
  assert.equal(source.config.exclude_moderator, scope === 'participant');
  const h = await setup(t, source);
  assert.equal(metric(h.document, '実際の参加者').value, '6人');
  const observed = metric(h.document, '観測された参加発言者');
  assert.equal(observed.value, '不明'); assert.match(observed.note, /役割が混在/);
  assert.equal(metric(h.document, '発話時間（時刻あり）').value, '00:20');

  h.click('[data-analysis-jump="conversation"]');
  assert.equal(h.evaluate('analysisState.automaticPage'), 'conversation');
  const moderator = panel(h, '司会者と参加者の発言関係');
  for (const label of ['司会発話比率', '質問候補']) assert.equal(metric(moderator, label).value, '役割混在で算出不可');
  const groups = panel(h, '話者グループの比較');
  const groupText = text(groups);
  assert(groupText.includes('役割混在（話者単位）'));
  assert.equal(source.automatic.groups.length, 2);
  assert(source.automatic.groups.every(row => row.speaking_seconds === null && row.role_aggregation_status === 'mixed'));
  assert.equal((groupText.match(/役割混在で算出不可/g) || []).length, 2);
  assert(!groupText.includes('時刻不明')); assert(!groupText.includes('00:00')); assert(!groupText.includes('0.0%'));
  for (const chart of groups.querySelectorAll('[role="img"]')) assert(!/0\.0%/.test(chart.getAttribute('aria-label') || ''));

  const title = scope === 'all' ? '全観測話者の発言バランス' : '参加者の発言バランス';
  const balance = panel(h, title);
  if (scope === 'all') {
    assert.equal(metric(balance, 'Gini係数').value, '0.000');
    assert.equal(metric(balance, '最大比率').value, '50.0%');
    assert.equal(metric(balance, '均等度').value, '100.0%');
    assert(text(balance).includes('分母 2人'));
  } else {
    assert.equal(metric(balance, 'Gini係数').value, '—');
    assert.equal(metric(balance, '最大比率').value, '—');
    assert.equal(metric(balance, '均等度').value, '未計算');
    assert.match(text(balance), /役割が混在.*割合・均等度は算出できません/);
  }
  const speakerPanel = panel(h, '話者ごとの発話量');
  assert.equal((text(speakerPanel).match(/50\.0% \/ 00:10/g) || []).length, 2);

  h.click('[data-analysis-scope="speakers"]');
  assert.equal(h.evaluate('analysisState.automaticScope'), 'speakers');
  for (const id of ['A', 'B']) {
    h.click(`.analysis-speaker-list [data-analysis-speaker-id="${id}"]`);
    const detail = h.document.querySelector('.analysis-speaker-detail');
    assert.equal(detail.querySelector('h2').textContent, id);
    assert.deepEqual(metric(detail, '発話時間'), {value: '00:10', note: '50.0%'});
    if (id === 'A') {
      assert.match(text(h.document.querySelector('.analysis-speaker-list [data-analysis-speaker-id="A"]')), /役割混在（司会・モデレーター・参加者）/);
      assert.match(text(detail.querySelector('.analysis-speaker-detail-header')), /役割混在（司会・モデレーター・参加者）/);
    }
  }
  h.change(h.document.querySelector('.analysis-speaker-sort-controls select'), 'attribute:role');
  assert.match(text(h.document.querySelector('.analysis-speaker-list')), /役割混在（司会・モデレーター・参加者）/);
  h.click('[data-analysis-scope="overall"]');
  assert.equal(h.evaluate('analysisState.automaticScope'), 'overall');
  assert.equal(metric(h.document, '発話時間（時刻あり）').value, '00:20');
  assert.deepEqual(plain(h.evaluate('analysisState.data')), source, 'Rendering must not normalize role-dependent nulls or change observed roles');
  noMutationRequests(h);
});

test('mixed is analysis-only and never becomes an editable speaker role enum option', async t => {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture({id: 'synthetic-role-enum', source_name: 'Synthetic role enum', revision_count: 1, files: [],
    segments: [{id: 'a', speaker: 'A', start: 0, end: 10, text: 'Synthetic'}], speaker_names: {},
    speaker_profiles: {A: {display_name: 'Synthetic A', session_role: 'participant', session_role_source: 'explicit'}},
    session_profile: {session_type: 'focus_group'}});
  h.evaluate('renderResult(window.fixture)');
  const role = h.document.querySelector('.conversation-role-control select'); assert(role);
  const options = [...role.options].map(option => ({value: option.value, label: option.textContent}));
  assert(!options.some(option => option.value === 'mixed' || option.label.includes('役割混在')));
  assert(options.some(option => option.value === 'participant'));
  assert(options.some(option => option.value === 'moderator'));
  noMutationRequests(h);
});

test('nonmixed synthetic role control keeps ordinary labels, numeric moderator metrics, and measured group time', async t => {
  const source = require('./fixtures/nonmixed-role-all-control.json');
  const h = await setup(t, source);
  const observed = metric(h.document, '観測された参加発言者');
  assert.equal(observed.value, '1人'); assert(!observed.note.includes('混在'));
  assert.equal(metric(h.document, '実際の参加者').value, '6人');
  assert.equal(metric(h.document, '発話時間（時刻あり）').value, '00:20');
  h.click('[data-analysis-jump="conversation"]');
  const moderator = panel(h, '司会者と参加者の発言関係');
  assert.equal(metric(moderator, '司会発話比率').value, '50.0%');
  assert.equal(metric(moderator, '質問候補').value, '0件');
  const groups = panel(h, '話者グループの比較');
  assert.equal((text(groups).match(/00:10/g) || []).length, 2);
  assert(!/役割混在|時刻不明|算出不可/.test(text(groups)));
  const balance = panel(h, '全観測話者の発言バランス');
  assert.equal(metric(balance, 'Gini係数').value, '0.000');
  assert.equal(metric(balance, '最大比率').value, '50.0%');
  h.click('[data-analysis-scope="speakers"]');
  h.click('.analysis-speaker-list [data-analysis-speaker-id="A"]');
  const detail = h.document.querySelector('.analysis-speaker-detail');
  assert.match(text(detail.querySelector('.analysis-speaker-detail-header')), /司会・モデレーター/);
  assert(!text(detail).includes('役割混在'));
  assert.deepEqual(metric(detail, '発話時間'), {value: '00:10', note: '50.0%'});
  assert.deepEqual(plain(h.evaluate('analysisState.data')), source);
  noMutationRequests(h);
});
