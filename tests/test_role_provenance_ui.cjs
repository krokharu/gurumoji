// Actual localized speaker-editor handlers; synthetic objects only, no browser.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../src/gurumoji/static/app.js'), 'utf8').replace(/\r\n/g, '\n');
const context = {profile: {session_role: 'participant', session_role_source: 'default'},
  globalSelect: {value: 'registry-id'}, speakerRegistry: [{id: 'registry-id', default_role: 'observer', pseudonym: 'Synthetic'}],
  label: 'A', currentJob: {speaker_names: {}, speaker_profiles: {}}, metrics: {},
  speakerLabels: () => ['A'], speakerThemeColors: ['#000000'], renderSpeakerEditor() {}, renderSpeakerInsights() {}, updateSpeakerBadges() {}, setCurrentJobDirty() {}, attributesToText: () => ''};
context.activeProfile = () => context.profile;
context.document = {activeElement: null};
vm.createContext(context);
function actualArrow(startMarker, endMarker, arrow) {
  const start = source.indexOf(startMarker);
  assert(start >= 0, startMarker);
  const begin = source.indexOf(arrow, start);
  const end = source.indexOf(endMarker, begin);
  assert(end > begin);
  return vm.runInContext(`(${source.slice(begin, end)}\n})`, context);
}
const registryChange = actualArrow("globalSelect.addEventListener('change',", '\n    });', '() => {');
registryChange();
assert.equal(context.profile.session_role, 'observer');
assert.equal(context.profile.session_role_source, 'registry');
const roleBegin = source.indexOf('function conversationRoleControl(');
const roleEnd = source.indexOf('\n}', roleBegin);
vm.runInContext(source.slice(roleBegin, roleEnd + 2), context);
context.currentJobId = 'synthetic';
context.currentJob.speaker_profiles.A = context.profile;
context.speakerRoleLabels = {participant: '参加者', observer: '観察者'};
context.fallbackSpeaker = () => 'Synthetic';
context.Option = function(text, value) { this.text = text; this.value = value; };
context.document = {createElement() { return {isConnected: true, children: [], events: {},
  add() {}, setAttribute() {}, append(...items) { this.children.push(...items); },
  addEventListener(type, handler) { this.events[type] = handler; }}; }};
const role = context.conversationRoleControl(context.profile, 'A', {}, 0);
role.children[0].value = 'participant';
role.children[0].events.change();
assert.equal(context.profile.session_role, 'participant');
assert.equal(context.profile.session_role_source, 'explicit');
const begin = source.indexOf('function ensureConversationSpeakerProfiles()');
const end = source.indexOf('\n}', begin);
vm.runInContext(source.slice(begin, end + 2), context);
for (const marker of ['explicit', 'registry', 'default', 'legacy_unknown']) {
  context.currentJob.speaker_profiles = {A: {session_role: 'participant', session_role_source: marker}};
  vm.runInContext('ensureConversationSpeakerProfiles()', context);
  assert.equal(context.currentJob.speaker_profiles.A.session_role_source, marker);
}
console.log(JSON.stringify({passed: ['registry_selection', 'explicit_participant_override', 'opening_preserves_all_markers'],
  scope: 'Original handlers with synthetic objects; no browser, network, model or user data'}));
