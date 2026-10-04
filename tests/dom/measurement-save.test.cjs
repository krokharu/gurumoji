'use strict';
// Adjacent ownership boundaries: Settings opened around an in-flight live analysis Save.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
const data = revision => ({executed: false, item: {id: 'A', source_name: 'Synthetic A', revision_count: revision, analysis_revision: revision}, segments: [], config: {research_question: 'Synthetic'}, annotations: {}});
const node = (h, selector) => { const value = h.document.querySelector(selector); assert(value, selector); return value; };
const definitionRequests = h => h.requests.filter(request => request.url.includes('/definitions/'));
function input(h, selector, value) { const field = node(h, selector); field.value = value; field.dispatchEvent(new h.w.Event('input', {bubbles: true})); field.dispatchEvent(new h.w.Event('change', {bubbles: true})); }
async function setup(t, dirty = true) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture({itemId: 'A', data: data(1), config: {research_question: 'Synthetic draft'}, annotations: {}, dirty, mode: 'manual'});
  h.evaluate('Object.assign(analysisState,window.fixture);analysisCard.hidden=false;document.body.dataset.view="analysis";renderAnalysisWorkspace()');
  return h;
}
function metadata(h) { return Object.fromEntries(['name', 'description', 'id', 'output', 'preset'].map(key => [key, node(h, `#analysis-definition-${key}`).value])); }
function editMetadata(h) {
  h.click('input[name=analysis_display_mode][value=detail]');
  input(h, '#analysis-definition-preset', 'duration');
  for (const [key, value] of Object.entries({name: 'Synthetic preserved name', description: 'Synthetic preserved description', id: 'synthetic_measure', output: 'synthetic_seconds'})) input(h, `#analysis-definition-${key}`, value);
  return metadata(h);
}
function definitionPayload(request, revision = 1, status = 'draft', trial = null) {
  const draft = JSON.parse(request.options.body); delete draft.expected_revision; delete draft.expected_trial;
  return {definition: {...draft, version: 1, revision, status, ...(trial ? {last_trial: trial} : {})}};
}
async function saveNewDefinition(h) {
  const before = definitionRequests(h).length;
  h.click('#analysis-definition-save');
  assert.equal(definitionRequests(h).length, before + 1, 'An enabled recovered Save must invoke the real definition handler');
  const request = definitionRequests(h).at(-1); const body = JSON.parse(request.options.body);
  assert.equal(body.expected_revision, 0);
  const result = definitionPayload(request); h.reply(request, result); await h.flush(); return result.definition;
}

test('a live Save completing after Settings opens preserves editable metadata and resumes the real definition Save', async t => {
  const h = await setup(t);
  h.click('[data-analysis-save]'); const save = h.requests.findLast(request => request.options.method === 'PUT'); assert(save);
  h.click('#analysis-run-settings-button'); const before = editMetadata(h);
  const dialog = node(h, '#analysis-run-dialog'); assert.equal(dialog.open, true);
  h.reply(save, data(2)); await h.flush();
  assert.equal(h.evaluate('analysisState.data.item.analysis_revision'), 2); assert.equal(h.evaluate('analysisState.dirty'), false);
  assert.equal(dialog.open, true); assert.equal(h.evaluate('Boolean(analysisMeasurementCurrent())'), true);
  assert.deepEqual(metadata(h), before, 'Unsubmitted identity and metadata must survive the live input update');
  assert(node(h, '#analysis-definition-state').textContent.includes('入力版が更新'));
  assert(!node(h, '#analysis-run-dialog-message').textContent.includes('未保存の分析設定'));
  assert.equal(definitionRequests(h).length, 0, 'The live Save must not submit a definition automatically');
  const definition = await saveNewDefinition(h); assert.equal(definition.name, before.name); assert.equal(definition.output_column, before.output);
  assert.equal(definition.measurement_rule, 'duration');
});

test('a previously adopted definition is preserved under a new draft identity when its live analysis input changes', async t => {
  const h = await setup(t, false); h.click('#analysis-run-settings-button'); const original = editMetadata(h);
  const definition = await saveNewDefinition(h);
  h.click('#analysis-definition-trial');
  const trial = {trial_id: 'synthetic-trial', definition_id: definition.definition_id, definition_version: 1, definition_revision: 1,
    definition_hash: 'synthetic-definition', input_hash: 'synthetic-input', source_revision: 1, analysis_revision: 1,
    total_count: 1, excluded_count: 0, sample_size: 1, valid_count: 1, missing_count: 0, rows: [{segment_id: 's1', synthetic_seconds: 0}]};
  h.reply(definitionRequests(h).at(-1), {trial}); await h.flush(); h.click('#analysis-definition-confirm'); h.click('#analysis-definition-adopt');
  const adoption = definitionRequests(h).at(-1); h.reply(adoption, definitionPayload(adoption, 2, 'adopted', trial)); await h.flush();
  assert.equal(h.evaluate('analysisMeasurement.adopted.status'), 'adopted');
  h.click('#close-analysis-run-dialog'); input(h, '[data-analysis-config="research_question"]', 'Synthetic changed live question');
  h.click('[data-analysis-save]'); const save = h.requests.findLast(request => request.url === '/api/library/A/analysis' && request.options.method === 'PUT'); assert(save);
  h.click('#analysis-run-settings-button');
  const refreshedId = node(h, '#analysis-definition-id').value; assert.notEqual(refreshedId, original.id);
  assert(node(h, '#analysis-definition-state').textContent.includes('別の下書きID'));
  const writes = definitionRequests(h).length;
  h.reply(save, data(2)); await h.flush();
  assert.equal(definitionRequests(h).length, writes); assert.equal(node(h, '#analysis-definition-id').value, refreshedId);
  for (const key of ['name', 'description', 'output', 'preset']) assert.equal(metadata(h)[key], original[key]);
  assert.equal(h.evaluate('analysisMeasurement.trial'), null); assert.equal(h.evaluate('analysisMeasurement.adopted'), null);
  assert.equal(node(h, '#analysis-definition-confirm').checked, false); assert.equal(node(h, '#analysis-run-start').disabled, true);
  const fresh = await saveNewDefinition(h); assert.equal(fresh.definition_id, refreshedId);
});

test('later unsaved live edits keep recovered measurement actions disabled and retain an explicit warning', async t => {
  const h = await setup(t); h.click('[data-analysis-save]'); const save = h.requests.findLast(request => request.options.method === 'PUT'); assert(save);
  input(h, '[data-analysis-config="research_question"]', 'Synthetic later unsaved edit');
  h.click('#analysis-run-settings-button'); editMetadata(h);
  h.reply(save, data(2)); await h.flush();
  assert.equal(h.evaluate('Boolean(analysisMeasurementCurrent())'), true);
  assert.equal(h.evaluate('analysisState.config.research_question'), 'Synthetic later unsaved edit'); assert.equal(h.evaluate('analysisState.dirty'), true);
  for (const id of ['analysis-definition-save', 'analysis-definition-trial', 'analysis-definition-adopt', 'analysis-run-start']) assert.equal(node(h, `#${id}`).disabled, true, id);
  assert(node(h, '#analysis-run-dialog-message').textContent.includes('未保存'));
  h.click('#analysis-definition-save'); assert.equal(definitionRequests(h).length, 0);
});
