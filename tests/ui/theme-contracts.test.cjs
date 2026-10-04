// Synthetic element contracts only; these do not substitute for browser/visual QA.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../src/gurumoji/static/analysis-content.js'), 'utf8').replace(/\r\n/g, '\n');
function context(names, values) {
  const ctx = vm.createContext(values);
  for (const name of names) {
    const start = source.search(new RegExp(`(?:async )?function ${name}\\(`));
    assert.notEqual(start, -1, name);
    vm.runInContext(source.slice(start, source.indexOf('\n}', start) + 2), ctx);
  }
  return ctx;
}
function node(tag = '', className = '', text = '') {
  return {tag, className, ownText: text, children: [], dataset: {}, disabled: false,
    classList: {add(){}, toggle(){}},
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) {this.children = items;},
    get textContent() { return this.ownText + this.children.map(item => item.textContent || '').join(''); },
    set textContent(value) {this.ownText = value; this.children = [];},
  };
}
function flatten(root) { return [root, ...root.children.flatMap(flatten)]; }
test('A13 invalid cardinality candidates remain visible, unscored and disabled', () => {
  const state = {topicCount: 2};
  const ctx = context(['transformerCandidates', 'buildTransformerCandidateList'], {
    analysisElement: node, document: {createElement: tag => node(tag), querySelectorAll: () => []},
    contentButton: (label, action) => Object.assign(node('button', '', label), {action}),
    refreshTransformerControls(){},
  });
  const root = ctx.buildTransformerCandidateList({quality: {cluster_candidates: [
    {topic_count: 2, actual_topic_count: 2, status: 'valid', silhouette_cosine: -.2},
    {topic_count: 3, actual_topic_count: 2, status: 'invalid_topic_count', silhouette_cosine: null},
  ]}}, state);
  const buttons = flatten(root).filter(item => item.tag === 'button');
  assert.equal(buttons[0].disabled, false);
  assert.equal(buttons[1].disabled, true);
  assert.match(root.textContent, /不成立（実際2件）/);
  assert.match(root.textContent, /テーマの意味の妥当性ではありません/);
  const invalidRow = flatten(root).find(item => item.dataset.transformerCandidate === '3');
  assert.doesNotMatch(invalidRow.textContent, /自動の選択/);
});
test('AI old and new findings always display candidate and semantic-validation limits', () => {
  const host = node();
  const state = {};
  const ctx = context(['insightRunActive', 'refreshInsightControls'], {
    analysisState: {itemId: 'synthetic', data: {insights: {stale: true, ai: {
      model: 'fixture', request_id: 'mock', findings: [{title: '候補', text: '検証用', segment_ids: ['s1']}],
      evidence: {s1: {text: '合成入力'}},
    }}}},
    contentAnalysisState: () => state, analysisElement: node, analysisSaveInProgress: false,
    document: {querySelectorAll: query => query === '[data-insight-output]' ? [host] : []},
    formatDate: () => 'mock', insightCategoryLabels: {}, evidenceDetails: () => node('details'),
  });
  ctx.refreshInsightControls();
  assert.match(host.textContent, /未確認の解釈候補/);
  assert.match(host.textContent, /真偽や「全員」の範囲を検証するものではありません/);
  assert.match(host.textContent, /研究者レビューが必要/);
  assert.match(host.textContent, /生成時点の見解/);
});
test('A08 cross-tab to KWIC preserves explicit match mode and synchronizes controls', () => {
  const state = {}, query = {}, mode = {}, speaker = {};
  let searches = 0;
  const ctx = context(['runKwicSearch'], {
    contentAnalysisState: () => state, jumpToContentSearch(){},
    document: {querySelectorAll: selector => ({'[data-kwic-query]': [query], '[data-kwic-mode]': [mode], '[data-kwic-speaker]': [speaker]})[selector]},
    searchContentKwic: () => { searches++; },
  });
  ctx.runKwicSearch({query: 'cat', matchMode: 'literal', speaker: 'A', offset: 10});
  assert.deepEqual(state, {query: 'cat', mode: 'literal', speaker: 'A', offset: 10});
  assert.equal(mode.value, 'literal'); assert.equal(query.value, 'cat'); assert.equal(speaker.value, 'A');
  ctx.runKwicSearch({query: 'cat'});
  assert.equal(state.mode, 'normalized'); assert.equal(mode.value, 'normalized'); assert.equal(searches, 2);
});
