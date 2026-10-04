// Original source functions with synthetic inputs. DOM integration is a separate suite.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const app = fs.readFileSync(path.join(__dirname, '../src/gurumoji/static/app.js'), 'utf8').replace(/\r\n/g, '\n');
const storage = fs.readFileSync(path.join(__dirname, '../src/gurumoji/static/analysis-storage.js'), 'utf8');
function extract(name) {
  const start = app.indexOf(`function ${name}(`), end = app.indexOf('\n}', start);
  assert(start >= 0 && end > start); return app.slice(start, end + 2);
}
const names = ['__proto__', 'constructor', 'toString', 'hasOwnProperty', 'normal'];
const ctx = {currentJob: {speaker_names: {}, speaker_profiles: {}, segments: names.flatMap(speaker => [
  {speaker, start: 1, end: 3, text: 'abc'}, {speaker, start: 4, end: 7, text: 'de'}])},
  speakerThemeColors: ['#123456'], fallbackSpeaker: label => `fallback:${label}`};
vm.createContext(ctx);
const content = fs.readFileSync(path.join(__dirname, '../src/gurumoji/static/analysis-content.js'), 'utf8').replace(/\r\n/g, '\n');
const guardStart = content.indexOf('function analysisEvidenceTimeValid(');
vm.runInContext(content.slice(guardStart, content.indexOf('\n}', guardStart) + 2), ctx);
for (const fn of ['speakerLabels', 'displaySpeakerName', 'speakerMetrics', 'ensureConversationSpeakerProfiles']) vm.runInContext(extract(fn), ctx);
vm.runInContext(`globalThis.before = [Object.prototype, Object, Object.prototype.toString, Object.prototype.hasOwnProperty].map(value => Object.getOwnPropertyDescriptors(value));`, ctx);
for (const label of names) assert.equal(ctx.displaySpeakerName(label), `fallback:${label}`);
const metrics = ctx.speakerMetrics();
assert.equal(Object.getPrototypeOf(metrics), null);
for (const label of names) {
  assert(Object.hasOwn(metrics, label));
  assert.deepEqual(JSON.parse(JSON.stringify(metrics[label])), {count: 2, timedCount: 2, missingTimeCount: 0, timedSeconds: 5, seconds: 5, characters: 5, share: .2});
}
ctx.ensureConversationSpeakerProfiles();
for (const label of names) {
  assert(Object.hasOwn(ctx.currentJob.speaker_profiles, label));
  const profile = ctx.currentJob.speaker_profiles[label];
  assert.equal(profile.speaker_label, label); assert.equal(profile.display_name, '');
  assert.equal(profile.registration_status, 'unidentified');
  ctx.currentJob.speaker_names[label] = `literal:${label}`;
  profile.display_name = `literal:${label}`;
  profile.notes = 'preserved'; profile.session_role_source = 'legacy_unknown';
}
ctx.currentJob = JSON.parse(JSON.stringify(ctx.currentJob));
ctx.ensureConversationSpeakerProfiles();
for (const label of names) {
  assert.equal(ctx.displaySpeakerName(label), `literal:${label}`);
  assert.equal(ctx.currentJob.speaker_profiles[label].notes, 'preserved');
  assert.equal(ctx.currentJob.speaker_profiles[label].session_role_source, 'legacy_unknown');
}
assert.equal(JSON.parse(JSON.stringify(ctx.currentJob)).speaker_profiles.__proto__.speaker_label, '__proto__');
vm.runInContext(`globalThis.after = [Object.prototype, Object, Object.prototype.toString, Object.prototype.hasOwnProperty].map(value => Object.getOwnPropertyDescriptors(value));`, ctx);
assert.deepEqual(ctx.after, ctx.before);
// Neither absent special keys nor hostile-looking own keys are replaced by inherited entries.
function node(tag = 'div') {return {tag, children: [], dataset: {}, _text: '',
  set textContent(v) {this._text = String(v ?? ''); this.children = [];},
  get textContent() {return this._text + this.children.map(n => n.textContent ?? '').join(' ');},
  append(...items) {this.children.push(...items);}, replaceChildren(...items) {this.children = items;}, setAttribute() {}};}
const history = node();
const store = {analysisState: {itemId: 'synthetic', data: {}}, analysisSaveInProgress: false,
  document: {querySelectorAll: selector => selector === '[data-archive-history]' ? [history] : []},
  analysisElement(tag, cls = '', text = '') {const n = node(tag); n.textContent = text; return n;},
  contentButton: text => {const n = node('button'); n.textContent = text; return n;}, formatDate: () => 'saved'};
vm.createContext(store); vm.runInContext(storage, store);
for (const status of names) {
  const summary = store.buildFixedAnalysisSummary({methods: [{title: 'saved', status}]});
  assert(summary.textContent.includes(`保存時の状態: ${status}`));
  const publication = store.buildSavedPublicationEvidence({publication_attempts: [{outcomes: {research: {status}}}]});
  assert(publication.textContent.includes(`不明（${status}）`));
  assert(!publication.textContent.includes('書出し成功'));
  store.analysisStorageState().runs = [{id: status, kind: status, status: 'completed'}];
  store.refreshAnalysisStorage(); assert(history.textContent.startsWith(`${status} / saved`));
  for (const output of [summary.textContent, publication.textContent, history.textContent]) {
    assert(!output.includes('[native code]')); assert(!output.includes('[object Object]'));
  }
}
assert(store.buildFixedAnalysisSummary({methods: [{status: 'completed'}]}).textContent.includes('計算済み'));
assert(store.buildSavedPublicationEvidence({publication_attempts: [{outcomes: {research: {status: 'failed'}}}]}).textContent.includes('失敗'));
console.log('PASS literal speaker keys, own JSON preservation, roundtrip, prototype immutability, unknown/known saved labels');
