// Pure DOM stub for the existing usage renderer; no browser, model or app start.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('reported zero and missing measurements stay different in the existing UI', () => {
  const source = fs.readFileSync(path.join(__dirname, '../src/gurumoji/static/app.js'), 'utf8');
  const start = source.indexOf('function renderAiTokenUsage(');
  assert.ok(start >= 0);
  const end = source.indexOf('\nfunction ', start + 1);
  assert.ok(end > start);
  const nodes = new Map();
  const root = {querySelector(selector) {
    if (!nodes.has(selector)) nodes.set(selector, {hidden: false, textContent: '', querySelector: () => ({})});
    return nodes.get(selector);
  }};
  const context = vm.createContext({document: {querySelector: () => root}, tokenConfigSnapshot: {}});
  vm.runInContext(source.slice(start, end), context);
  context.renderAiTokenUsage('#synthetic', {provider: 'openai', request_count: 1,
    input_tokens: 0, output_tokens: null, total_tokens: null, reported: true});
  assert.equal(nodes.get('[data-ai-input]').textContent, '0');
  assert.equal(nodes.get('[data-ai-output]').textContent, '未計測');
  assert.equal(nodes.get('[data-ai-total]').textContent, '未計測');
  assert.equal(nodes.get('[data-ai-unreported]').hidden, false);
  context.renderAiTokenUsage('#synthetic', {provider: 'openai', request_count: 1,
    input_tokens: 0, output_tokens: 0, total_tokens: 0, reported: true});
  assert.equal(nodes.get('[data-ai-total]').textContent, '0');
  assert.equal(nodes.get('[data-ai-unreported]').hidden, true);
});

test('ready cache version conflict replaces the reusable state without changing saved stages', () => {
  const source = fs.readFileSync(path.join(__dirname, '../src/gurumoji/static/analysis-orchestration.js'), 'utf8');
  const start = source.indexOf('function orchestrationRenderInitial(');
  const end = source.indexOf('\nfunction ', start + 1);
  assert.ok(start >= 0 && end > start);
  const nodes = new Map();
  const element = (tag, text) => ({tag, text, dataset: {}, children: [], append(...values) { this.children.push(...values); }});
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {replaceChildren() { this.children = []; }, children: [], append(value) { this.children.push(value); }});
    return nodes.get(id);
  };
  const messages = new Map();
  const context = vm.createContext({orchestrationNode: node, orchestrationText: (id, text) => messages.set(id, text),
    orchestrationState: {}, orchestrationElement: element, orchestrationNumber: String, orchestrationLabel: String});
  vm.runInContext(source.slice(start, end), context);
  const stages = [{stage_id: 'synthetic', label: 'Synthetic', status: 'completed', attempt_count: 1}];
  const run = {run_id: 'synthetic', phase: 'core', initial_stages: stages, initial: {status: 'ready'}, allowed_actions: ['resume']};
  context.orchestrationRenderInitial(run);
  assert.match(nodes.get('initial-stages').children[0].children[2].text, /再開時に再利用/);
  context.orchestrationRenderInitial({...run, initial: {status: 'revalidation_required', recovery_error: 'initial_revalidation_required'}, allowed_actions: []});
  assert.match(messages.get('initial-summary'), /再評価が必要/);
  assert.match(nodes.get('initial-stages').children[0].children[2].text, /再利用は未確認/);
  assert.deepEqual(stages, [{stage_id: 'synthetic', label: 'Synthetic', status: 'completed', attempt_count: 1}]);
});
