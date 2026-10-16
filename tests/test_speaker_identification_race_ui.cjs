const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../src/gurumoji/static/app.js'), 'utf8').replace(/\r\n/g, '\n');
const start = source.indexOf('async function rerunSpeakerIdentification(');
const fn = source.slice(start, source.indexOf('\n}', start) + 2);

for (const scenario of ['edited', 'navigated', 'returned', 'unchanged']) {
  test(`speaker identification preserves ownership: ${scenario}`, async () => {
    let resolve, renders = 0, recoveries = 0;
    const ctx = {
      currentJobId: 'a', currentJob: {id: 'a', revision_count: 1}, currentJobDirty: false,
      currentJobMutationGeneration: 0, resultRequestSequence: 1, resultSaveConflict: false,
      rerunSpeakerIdentificationButton: {disabled: false}, speakerIdentityProvider: {value: 'lmstudio'},
      speakerIdentityStatus: {}, speakerRegistryDirty: false, document: {querySelector: () => ({})},
      setAlert() {}, showDraftRecovery() {recoveries++;}, loadSpeakerRegistry: async () => {},
      apiFetch: () => new Promise(r => {resolve = r;}), readJsonResponse: async r => r.data,
      renderResult() {renders++; ctx.currentJobDirty = false; ctx.resultRequestSequence++; ctx.currentJob = {id: 'a'};},
    };
    vm.createContext(ctx); vm.runInContext(fn, ctx);
    const pending = ctx.rerunSpeakerIdentification();
    if (scenario === 'edited') {ctx.currentJobDirty = true; ctx.currentJobMutationGeneration++;}
    if (scenario === 'navigated') {ctx.currentJobId = 'b'; ctx.resultRequestSequence++;}
    if (scenario === 'returned') {ctx.currentJob = {id: 'a'}; ctx.resultRequestSequence += 2;}
    resolve({ok: true, data: {id: 'a', speaker_identity: {applied_count: 1}}});
    await pending;
    assert.equal(renders, scenario === 'unchanged' ? 1 : 0);
    assert.equal(recoveries, scenario === 'edited' ? 1 : 0);
    if (scenario === 'edited') assert.equal(ctx.currentJobDirty, true);
    if (scenario === 'unchanged') assert.equal(ctx.rerunSpeakerIdentificationButton.disabled, false);
  });
}
