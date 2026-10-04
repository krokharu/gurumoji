'use strict';
// Real HTML, selectors, input/change/click/submit handlers; synthetic APIs only.
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHarness} = require('./harness.cjs');
const plain = value => JSON.parse(JSON.stringify(value));
const find = (h, selector) => { const value = h.document.querySelector(selector); assert(value, selector); return value; };
const pending = (h, suffix, method) => {
  const value = h.requests.findLast(r => !r.settled && r.url.endsWith(suffix) && (!method || (r.options.method || 'GET') === method));
  assert(value, `${method || ''} ${suffix}`); return value;
};
function input(h, selector, value) { const element = find(h, selector); element.value = value; element.dispatchEvent(new h.w.Event('input', {bubbles: true})); element.dispatchEvent(new h.w.Event('change', {bubbles: true})); }
async function setup(t) {
  const h = await createHarness(); t.after(() => h.close());
  h.fixture({itemId: 'A', data: {executed: false, item: {id: 'A', source_name: 'Synthetic A', revision_count: 1, analysis_revision: 1}, segments: []}, config: {}, annotations: {}, dirty: false});
  h.evaluate('Object.assign(analysisState,window.fixture);analysisCard.hidden=false;document.body.dataset.view="analysis"');
  h.click('#analysis-run-settings-button');
  assert.equal(find(h, '#analysis-run-dialog').open, true);
  assert.equal(find(h, '#analysis-manual-definition').hidden, false);
  return h;
}
function definitionResponse(request, revision = 1, status = 'draft', trial = null) {
  const draft = JSON.parse(request.options.body); delete draft.expected_revision; delete draft.expected_trial;
  return {definition: {...draft, version: 1, revision, status, ...(trial ? {last_trial: trial} : {})}};
}
async function saved(h) {
  h.click('#analysis-definition-save');
  const request = pending(h, find(h, '#analysis-definition-id').value, 'PUT');
  const result = definitionResponse(request); h.reply(request, result); await h.flush(); return result.definition;
}
function trialFor(definition, overrides = {}) {
  const column = definition.output_column;
  return {trial_id: 'synthetic-trial', definition_id: definition.definition_id, definition_version: 1, definition_revision: definition.revision,
    definition_hash: 'synthetic-definition-hash', input_hash: 'synthetic-input-hash', source_revision: 1, analysis_revision: 1,
    total_count: 3, excluded_count: 1, sample_size: 2, valid_count: 1, missing_count: 1, values: [0, null],
    rows: [{segment_id: 's1', speaker: 'A', [column]: 0, [`${column}__missing_reason`]: ''}, {segment_id: 's2', speaker: 'B', [column]: null, [`${column}__missing_reason`]: 'time_unknown'}], external_calls: 0, ...overrides};
}
async function tried(h) {
  const definition = await saved(h);
  h.click('#analysis-definition-trial');
  const trial = trialFor(definition); h.reply(pending(h, '/trials', 'POST'), {trial}); await h.flush();
  return {definition, trial};
}
function beginAdoption(h) { h.click('#analysis-definition-confirm'); assert.equal(find(h, '#analysis-definition-confirm').checked, true); h.click('#analysis-definition-adopt'); return pending(h, find(h, '#analysis-definition-id').value, 'PUT'); }
function mutationRequests(h) { return h.requests.filter(r => ['PUT', 'POST'].includes(r.options.method)); }

for (const storage of ['available', 'unavailable-after-startup']) test(`manual duration definition reaches fixed plan via real simple/detail controls with storage ${storage}`, async t => {
  const h = await setup(t);
  if (storage !== 'available') for (const method of ['getItem', 'setItem', 'removeItem']) h.w.Storage.prototype[method] = () => { throw new h.w.DOMException('Synthetic storage denied', 'SecurityError'); };
  input(h, '#analysis-definition-preset', 'duration');
  assert.equal(find(h, '#analysis-run-start').disabled, true);
  const {definition, trial} = await tried(h);
  assert.equal(definition.source_columns[0], 'duration'); assert.equal(definition.measurement_rule, 'duration');
  const table = find(h, '#analysis-definition-trial-result table');
  assert(table.textContent.includes('null（欠測）')); assert(table.textContent.includes('time_unknown')); assert([...table.querySelectorAll('td')].some(cell => cell.textContent === '0'));
  assert([...table.querySelectorAll('th')].every(cell => cell.scope === 'col'));
  const before = plain(h.evaluate('analysisExecutionDefinitionFromForm()'));
  h.click('input[name=analysis_display_mode][value=detail]'); h.click('input[name=analysis_display_mode][value=simple]');
  assert.deepEqual(plain(h.evaluate('analysisExecutionDefinitionFromForm()')), before);
  assert.deepEqual(plain(h.evaluate('analysisMeasurement.trial')), trial);
  assert.equal(find(h, '#analysis-definition-adopt').disabled, true);
  const request = beginAdoption(h); h.click('#analysis-definition-adopt');
  assert.equal(mutationRequests(h).length, 3, 'Double click may not submit another adoption');
  const adoptedBody = JSON.parse(request.options.body); assert.equal(adoptedBody.expected_revision, 1); assert.deepEqual(adoptedBody.expected_trial, trial);
  h.reply(request, definitionResponse(request, 2, 'adopted', trial)); await h.flush();
  assert.equal(find(h, '#analysis-run-start').disabled, false);
  h.click('#analysis-run-start'); h.click('#analysis-run-start'); await h.flush();
  const preview = pending(h, '/plans/preview', 'POST'); const payload = JSON.parse(preview.options.body);
  assert.equal(payload.mode, 'manual'); assert.equal(payload.provider_policy, 'local_only'); assert.deepEqual(payload.publication_targets, []);
  assert.deepEqual(payload.definition_ids, [definition.definition_id]); assert.equal(payload.expected_input_hash, trial.input_hash);
  assert.equal(payload.expected_definition_versions[definition.definition_id], 1);
  h.reply(preview, {}); await h.flush();
  const execution = pending(h, '/pipelines', 'POST'); assert.deepEqual(JSON.parse(execution.options.body), payload);
  h.reply(execution, {pipeline_id: 'synthetic-pipeline', status: 'completed', allowed_actions: [], milestones: [], events: []}); await h.flush();
  assert.equal(mutationRequests(h).length, 5); assert.equal(find(h, '#analysis-run-dialog').open, false);
  assert.equal(h.evaluate('analysisExecutionState.id'), 'synthetic-pipeline'); assert.equal(h.w.location.hash, '#/analysis/A/run');
});

test('retrial click immediately clears prior confirmation and failed trial cannot be adopted', async t => {
  const h = await setup(t); await tried(h); h.click('#analysis-definition-confirm');
  h.click('#analysis-definition-trial'); h.click('#analysis-definition-trial');
  assert.equal(find(h, '#analysis-definition-confirm').checked, false); assert.equal(find(h, '#analysis-definition-confirm').disabled, true);
  assert.equal(find(h, '#analysis-definition-trial-result').children.length, 0);
  h.reply(pending(h, '/trials', 'POST'), {error: 'Synthetic retrial failure'}, 500); await h.flush();
  h.click('#analysis-definition-adopt'); assert.equal(mutationRequests(h).length, 3);
  assert.equal(h.evaluate('analysisMeasurement.trial'), null); assert.equal(find(h, '#analysis-definition-trial').disabled, false);
  assert(find(h, '#analysis-run-dialog-message').textContent.includes('Synthetic retrial failure'));
});

for (const action of ['save', 'trial']) test(`closing and reopening while ${action} is pending releases the new dialog controls after the old response`, async t => {
  const h = await setup(t); const definition = action === 'trial' ? await saved(h) : null;
  h.click(`#analysis-definition-${action}`); const request = pending(h, action === 'trial' ? '/trials' : find(h, '#analysis-definition-id').value);
  h.click('#close-analysis-run-dialog'); h.click('#analysis-run-settings-button');
  h.reply(request, action === 'trial' ? {trial: trialFor(definition)} : definitionResponse(request)); await h.flush();
  assert.equal(h.evaluate('analysisMeasurement.operation'), null);
  assert.equal(find(h, '#analysis-definition-save').disabled, false, 'The reopened dialog must leave busy state when its old operation settles');
  assert.equal(find(h, '#analysis-definition-preset').disabled, false);
  assert.equal(find(h, '#analysis-definition-confirm').checked, false);
});

test('close/reopen during uncertain adoption reads its saved status before another PUT', async t => {
  const h = await setup(t); const {trial} = await tried(h); const adoption = beginAdoption(h);
  h.click('#close-analysis-run-dialog'); h.click('#analysis-run-settings-button');
  assert.equal(mutationRequests(h).length, 3);
  h.fail(adoption, 'Synthetic lost adoption response'); await h.flush();
  const inspect = pending(h, find(h, '#analysis-definition-id').value, 'GET');
  h.reply(inspect, definitionResponse(adoption, 2, 'adopted', trial)); await h.flush();
  assert.equal(mutationRequests(h).length, 3); assert.equal(h.evaluate('analysisMeasurement.pendingAdoption'), null);
  assert.equal(h.evaluate('analysisMeasurement.adopted.status'), 'adopted'); assert.equal(find(h, '#analysis-run-start').disabled, false);
});

test('adoption rejected with a changed saved definition blocks writes until the user supplies a new identity', async t => {
  const h = await setup(t); const {trial} = await tried(h); const adoption = beginAdoption(h);
  h.reply(adoption, {error: 'Synthetic revision conflict', reason_code: 'revision_conflict'}, 409); await h.flush();
  const response = definitionResponse(adoption, 3, 'adopted', trial); response.definition.description = 'Another synthetic version';
  h.reply(pending(h, find(h, '#analysis-definition-id').value, 'GET'), response); await h.flush();
  assert.equal(h.evaluate('analysisMeasurement.blocked'), true); assert.equal(find(h, '#analysis-definition-save').disabled, true);
  h.click('input[name=analysis_display_mode][value=detail]'); input(h, '#analysis-definition-id', 'synthetic_new_definition');
  assert.equal(find(h, '#analysis-definition-save').disabled, false); assert.equal(h.evaluate('analysisMeasurement.adopted'), null);
  assert.equal(mutationRequests(h).length, 3);
});

test('accepted history navigation closes a measurement dialog while its adoption completes in the old context', async t => {
  const h = await setup(t); const {trial} = await tried(h); const adoption = beginAdoption(h);
  h.w.history.replaceState(null, '', '#/data'); h.w.dispatchEvent(new h.w.PopStateEvent('popstate'));
  h.reply(adoption, definitionResponse(adoption, 2, 'adopted', trial)); await h.flush();
  assert.equal(h.document.body.dataset.view, 'library'); assert.equal(h.w.location.hash, '#/data');
  assert.equal(find(h, '#analysis-run-dialog').open, false, 'A modal from the former analysis context must not cover the library');
  assert.equal(h.requests.filter(r => r.url.endsWith('/pipelines')).length, 0);
});

test('generated ID conflict enables another draft without silently submitting or overwriting it', async t => {
  const h = await setup(t); const old = find(h, '#analysis-definition-id').value;
  h.click('#analysis-definition-save'); h.click('#analysis-definition-save');
  h.reply(pending(h, old, 'PUT'), {error: 'Synthetic ID collision', reason_code: 'revision_conflict'}, 409); await h.flush();
  assert.notEqual(find(h, '#analysis-definition-id').value, old); assert.equal(find(h, '#analysis-definition-save').disabled, false);
  assert.equal(mutationRequests(h).length, 1); assert.equal(h.evaluate('analysisMeasurement.saved'), null);
});
