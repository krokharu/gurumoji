// 実利用者データやネットワークを使わず、RE-USEの選択と準備確認を検証する。
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = process.env.GURUMOJI_REUSE_SOURCE_ROOT || process.cwd();
const {JSDOM} = require(path.join(root, 'tests/dom/node_modules/jsdom'));
const dashboard = fs.readFileSync(path.join(root,'src/gurumoji/static/create-dashboard.js'),'utf8');
const app = require('../app_source.cjs')(path.join(root,'src/gurumoji/static/app.js'),'utf8');
const template = fs.readFileSync(path.join(root,'src/gurumoji/templates/views/create.html'),'utf8');
const select = template.match(/<select name="audio_preprocess">[\s\S]*?<\/select>/)[0];

test('音声前処理の高からRE-USEを選び、従来の強めと区別できる',()=>{
  const dom = new JSDOM(select,{runScripts:'outside-only'});
  const w = dom.window;
  w.audioPreprocess = w.document.querySelector('select');
  w.LEVEL_TEXT = {high:'高',mid:'中',low:'低',none:'無'};
  w.setSelect = (field,value)=>{field.value=value;field.dispatchEvent(new w.Event('change'));};
  const begin = dashboard.indexOf('  const volumeLevel =');
  const end = dashboard.indexOf('  let openBubbleName',begin);
  assert(begin>=0 && end>begin);
  w.eval(dashboard.slice(begin,end)+'\nwindow.menu = BUBBLES.volume;');
  assert.equal(w.audioPreprocess.value,'standard');
  assert.equal(w.menu.options().find(row=>row[0]==='reuse')[2],'高');
  w.menu.apply('reuse');
  assert.equal(w.audioPreprocess.value,'reuse');
  assert.equal(w.menu.current(),'reuse');
  w.menu.apply('strong');
  assert.equal(w.menu.current(),'strong');
  w.menu.apply('standard');
  assert.equal(w.menu.current(),'standard');
  dom.window.close();
});

test('RE-USE未準備なら開始を止め、準備後と他の前処理は開始できる',()=>{
  const dom = new JSDOM(select+'<select id="transcription-device"><option value="cpu">CPU</option></select><input type="checkbox" id="model-readiness-ack" checked>',{runScripts:'outside-only'});
  const w = dom.window;
  w.audioPreprocess = w.document.querySelector('select');
  w.transcriptionBackend = {value:'whisperx'};
  w.modelName = {value:'base'};
  w.configLoadState = 'loaded';
  w.tokenConfigSnapshot = {huggingface:true,transcription_readiness:{
    whisperx:{blockers:[],notes:[],models:{cpu:{base:{status:'cached',message:'準備済み'}}}},
    audio_preprocess:{reuse:{blockers:['RE-USEの専用環境が未準備です'],notes:[]}}
  }};
  w.enabledTextDestinations = ()=>[];
  w.selectedTranscriptFinishingMode = ()=>'off';
  w.readSeenNotices = ()=>new Set();
  w.hasSelectedSource = ()=>true;
  const begin = app.indexOf('function createReadiness() {');
  const end = app.indexOf('\nfunction ',begin+1);
  w.eval(app.slice(begin,end));
  w.audioPreprocess.value = 'reuse';
  assert.equal(w.createReadiness().ready,false);
  assert.match(w.createReadiness().blockers.join(' '),/RE-USE/);
  w.tokenConfigSnapshot.transcription_readiness.audio_preprocess.reuse.blockers = [];
  assert.equal(w.createReadiness().ready,true);
  delete w.tokenConfigSnapshot.transcription_readiness.audio_preprocess;
  assert.equal(w.createReadiness().ready,false);
  w.audioPreprocess.value = 'standard';
  assert.equal(w.createReadiness().ready,true);
  dom.window.close();
});
