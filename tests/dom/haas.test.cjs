// 利用者データを読み込まず、Haas選択時の装置と日本語設定を確認する。
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = process.env.GURUMOJI_HAAS_SOURCE_ROOT;
const {JSDOM} = require(path.join(root, 'tests/dom/node_modules/jsdom'));
const source = require('../app_source.cjs')(path.join(root, 'src/gurumoji/static/app.js'), 'utf8');
const start = source.indexOf('function syncTranscriptionBackend() {');
const end = source.indexOf('\nfunction ', start + 1);
function setup() {
  const dom = new JSDOM('<select id="backend"><option value="whisperx">WhisperX</option><option value="haas_ja">Haas</option></select><select id="transcription-device"><option value="cpu">CPU</option><option value="cuda">GPU</option></select><select id="language"><option value="en">English</option><option value="ja">日本語</option></select>', {runScripts:'outside-only'});
  const w = dom.window;
  for (const name of ['modelName','triplePass','boostQuietSpeech','vadOnset','vadOffset','speakerCountFixButton','minSpeakersField','maxSpeakersField','minSpeakersInput','maxSpeakersInput','qwenBackendNote','haasBackendNote','qwenVocabularyNote']) w[name] = null;
  w.transcriptionBackend = w.document.querySelector('#backend');
  w.languageSelect = w.document.querySelector('#language');
  w.isSpeakerCountFixed = () => false;
  w.setSpeakerCountFixed = () => {};
  w.eval(source.slice(start,end));
  return dom;
}
test('Haasを選ぶとGPUと日本語へ切り替わる', () => {
  const dom = setup();
  const w = dom.window;
  w.transcriptionBackend.value = 'haas_ja';
  w.syncTranscriptionBackend();
  assert.equal(w.document.querySelector('#transcription-device').value,'cuda');
  assert.equal(w.document.querySelector('option[value="cpu"]').disabled,true);
  assert.equal(w.languageSelect.value,'ja');
  dom.window.close();
});
test('WhisperXへ戻すとCPUを選べる', () => {
  const dom = setup();
  const w = dom.window;
  w.transcriptionBackend.value = 'haas_ja';
  w.syncTranscriptionBackend();
  w.transcriptionBackend.value = 'whisperx';
  w.syncTranscriptionBackend();
  assert.equal(w.document.querySelector('option[value="cpu"]').disabled,false);
  w.document.querySelector('#transcription-device').value = 'cpu';
  assert.equal(w.document.querySelector('#transcription-device').value,'cpu');
  dom.window.close();
});