// Synthetic DOM/network contracts, not browser rendering or assistive-technology acceptance.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../src/gurumoji/static/ai-effort.js'), 'utf8');
class Element {
  constructor(tag, doc) { this.tagName = tag; this.doc = doc; this.children = []; this.attrs = {}; this.dataset = {}; this.listeners = {}; this.disabled = false; this.hidden = false; this.open = false; this._checked = false; this.value = ''; }
  append(child) { this.children.push(child); child.parentElement = this; }
  setAttribute(k,v) { this.attrs[k] = String(v); if (k === 'class') this.className = v; if (k === 'name') this.name = v; if (k === 'value') this.value = v; if (k === 'hidden') this.hidden = true; if (k === 'checked') this._checked = true; if (k.startsWith('data-')) this.dataset[k.slice(5)] = v; }
  getAttribute(k) { return this.attrs[k] ?? null; }
  get checked() { return this._checked; }
  set checked(v) { if (v && this.name) this.doc.querySelectorAll(`[name="${this.name}"]`).forEach(e => { e._checked = false; }); this._checked = v; }
  get options() { return this.children.filter(e => e.tagName === 'option'); }
  set innerHTML(html) {
    this.children = []; const stack = [this];
    for (const item of html.matchAll(/<\/?([\w-]+)([^>]*)>|([^<]+)/g)) {
      if (item[3]) continue;
      if (item[0].startsWith('</')) { if (stack.length > 1) stack.pop(); continue; }
      const child = new Element(item[1], this.doc);
      for (const a of item[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g)) child.setAttribute(a[1], a[2] ?? '');
      stack.at(-1).append(child);
      if (!['input', 'path', 'circle', 'rect'].includes(child.tagName) && !item[0].endsWith('/>')) stack.push(child);
    }
  }
  matches(selector) {
    if (selector.includes(':checked') && !this.checked) return false;
    selector = selector.replace(':checked', '');
    const tag = selector.match(/^[\w-]+/); if (tag && this.tagName !== tag[0]) return false;
    const id = selector.match(/#([\w-]+)/); if (id && this.attrs.id !== id[1]) return false;
    const cls = selector.match(/\.([\w-]+)/); if (cls && !(this.className || '').split(' ').includes(cls[1])) return false;
    for (const a of selector.matchAll(/\[([\w-]+)(\^=|=)?(?:"([^"]*)")?\]/g)) {
      const val = this.attrs[a[1]];
      if (val === undefined || (a[2] === '=' && val !== a[3]) || (a[2] === '^=' && !val.startsWith(a[3]))) return false;
    }
    return true;
  }
  querySelectorAll(s) { return this.children.flatMap(c => [...(c.matches(s) ? [c] : []), ...c.querySelectorAll(s)]); }
  querySelector(s) { return this.querySelectorAll(s)[0] || null; }
  addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
  dispatchEvent(event) { event.target ||= this; event.currentTarget = this; (this.listeners[event.type] || []).forEach(f => f(event)); if (event.bubbles && !event.stopped) this.parentElement?.dispatchEvent(event); return true; }
  focus() { this.doc.activeElement = this; }
}
class SyntheticEvent { constructor(type, options={}) { Object.assign(this, options); this.type=type; } stopPropagation(){this.stopped=true;} preventDefault(){this.prevented=true;} }
function setup(saved, storageFails=false) {
  const doc = new Element('document'); doc.doc = doc; doc.createElement = tag => new Element(tag, doc); doc.getElementById = id => doc.querySelector(`#${id}`);
  doc.innerHTML = '<div id="ai-effort-settings"></div><button id="effort-detail-toggle" aria-pressed="false"></button><button id="effort-capability-retry"></button><select id="ai-provider"></select><input id="finish-in-obsidian"><input id="clean-transcript" checked><input id="detect-names" checked><input id="create-outline" checked><input name="transcript_finishing_mode" value="recommended" checked><input name="transcript_finishing_mode" value="advanced"><input name="transcript_finishing_mode" value="off"><input name="transcript_finishing_mode" value="custom"><input id="jev-compare"><small id="clean-transcript-mode-note" hidden></small><small id="detect-names-mode-note" hidden></small>';
  doc.getElementById('ai-provider').value='openai';
  const writes=[], calls=[];
  const ctx=vm.createContext({document:doc, Event:SyntheticEvent, AbortSignal, localStorage:{getItem(){if(storageFails)throw Error();return saved;},setItem(k,v){if(storageFails)throw Error();writes.push([k,v]);}}, tokenConfigSnapshot:{lmstudio_model:'A'}, apiFetch(url){return new Promise((resolve,reject)=>calls.push({url,resolve,reject}));},setInterval(){}, updateCreateSummary(){}});
  vm.runInContext(source,ctx);
  return {ctx,doc,writes,calls, values:()=>JSON.parse(JSON.stringify(ctx.readAiEfforts())), card:key=>doc.querySelector(`[data-stage="${key}"]`), sync:()=>ctx.syncAiEffortSettings(), change(key,value){const s=this.card(key).querySelector('select');s.value=value;s.dispatchEvent(new SyntheticEvent('change',{bubbles:true}));}};
}
const keys=['outline','cleanup','name_extract','name_verify'];
const snapshot={outline:'high',cleanup:'low',name_extract:'off',name_verify:'medium'};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function capability(s, cap, model='A') { s.doc.getElementById('ai-provider').value='lmstudio'; s.ctx.tokenConfigSnapshot.lmstudio_model=model; s.sync(); s.calls.at(-1).resolve({ok:true,json:async()=>({model,reasoning:cap})});await flush(); }
function assertState(s,expected) { assert.deepEqual(s.values(),expected);keys.forEach(key=>{assert.equal(s.card(key).querySelector('input[type="hidden"]').value,expected[key]);assert.equal(s.card(key).dataset.effort,expected[key]);}); }
test('E01 storage absent/corrupt/null/unknown/unavailable/legacy auto retains independent defaults',()=>{
  for(const saved of [null,'broken','null','[]','{"outline":"unknown"}','{"outline":"\"]"}']) {const s=setup(saved); assertState(s,Object.fromEntries(keys.map(k=>[k,'medium'])));assert.equal(s.writes.length,0);}
  assertState(setup(null,true),Object.fromEntries(keys.map(k=>[k,'medium'])));
  assert.equal(setup('{"outline":"auto","cleanup":"off"}').values().outline,'medium');
  assertState(setup(JSON.stringify(snapshot)),snapshot);
});
test('E02–04 all values both directions, independent settings, legacy cleanup, one change path and no request',()=>{
 const s=setup(JSON.stringify(snapshot));
 for(const key of keys) for(const value of ['off','low','medium','high','ultra']) {
   const before=s.values(), count=s.writes.length; s.change(key,value);assertState(s,{...before,[key]:value});assert.equal(s.writes.length,count+1);
   s.ctx.setAiEffortChoice(key,'medium');
   const card=s.card(key), mode=card.querySelector(`[name="ai_thinking_mode_${key}"][value="${value==='off'&&key!=='cleanup'?'off':'on'}"]`);mode.checked=true;
   const radio=card.querySelector(`[name="ai_effort_choice_${key}"][value="${value}"]`);if(radio)radio.checked=true;
   (radio||mode).dispatchEvent(new SyntheticEvent('change',{bubbles:true}));assert.equal(s.values()[key],value);
 }
 s.card('cleanup').querySelector('[name="ai_thinking_mode_cleanup"][value="off"]').checked=true;s.change('cleanup','high');assert.equal(s.values().cleanup,'high');
 assert.equal(s.calls.length,0);
});
test('E03 compact initially closed, display/close/Escape preserve values and focus without requests',()=>{
 const s=setup(JSON.stringify(snapshot)), toggle=s.doc.getElementById('effort-detail-toggle');
 const before=s.values(); for(let n=0;n<5;n++) {toggle.dispatchEvent(new SyntheticEvent('click'));keys.forEach(key=>{const d=s.card(key).parentElement;assert.equal(d.open,false);d.open=true;d.querySelector('.effort-close').dispatchEvent(new SyntheticEvent('click'));assert.equal(d.open,false);assert.equal(s.doc.activeElement,d.querySelector('summary'));d.open=true;d.dispatchEvent(new SyntheticEvent('keydown',{key:'Escape'}));assert.equal(d.open,false);});}
 assertState(s,before);assert.equal(s.calls.length,0);assert.equal(s.writes.length,0);
});
test('E05 temporary disable never overwrites OFF or latent intensity; all four payload fields remain enabled',()=>{
 const s=setup();keys.forEach(k=>{s.change(k,'ultra');s.change(k,'off');});
 for(const action of [()=>s.doc.getElementById('ai-provider').value='none',()=>{s.doc.getElementById('ai-provider').value='openai';s.doc.getElementById('clean-transcript').checked=false;s.doc.getElementById('detect-names').checked=false;s.doc.getElementById('create-outline').checked=false;},()=>s.doc.getElementById('ai-provider').disabled=true]) {
 action();s.sync();assertState(s,Object.fromEntries(keys.map(k=>[k,'off'])));keys.forEach(k=>{assert.equal(s.card(k).querySelector('input[type="hidden"]').disabled,false);assert.equal(s.card(k).disabled,false);if(k!=='cleanup')assert.equal(s.card(k).querySelector('[name^="ai_effort_choice_"]:checked').value,'ultra');});}
});
test('E06 A→B→A generation guard ignores stale success and stale failure',async()=>{
 const s=setup();const p=s.doc.getElementById('ai-provider');p.value='lmstudio';s.sync();const a1=s.calls[0];s.ctx.tokenConfigSnapshot.lmstudio_model='B';s.sync();const b=s.calls[1];s.ctx.tokenConfigSnapshot.lmstudio_model='A';s.sync();const a2=s.calls[2];
 a2.resolve({ok:true,json:async()=>({model:'A',reasoning:{allowed_options:['off','high']}})});await flush();const status=s.card('outline').parentElement.querySelector('.effort-status').textContent;
 a1.resolve({ok:true,json:async()=>({model:'A',reasoning:{allowed_options:['on','off'],default:'on'}})});b.reject(Error());await flush();assert.equal(s.card('outline').parentElement.querySelector('.effort-status').textContent,status);assert.equal(s.ctx.localEffortSupport('medium'),false);
 p.value='openai';s.sync();p.value='lmstudio';s.sync();assert.equal(s.calls.length,4);
});
test('E06 response mismatch/error/empty/malformed capabilities remain visibly uncertain, without coercion',async()=>{
 for(const kind of ['mismatch','error','empty','malformed']) {
 const s=setup(JSON.stringify(snapshot));s.doc.getElementById('ai-provider').value='lmstudio';s.sync();assert.ok(s.ctx.aiEffortReadiness().blockers.length);
 if(kind==='error')s.calls[0].reject(Error());else s.calls[0].resolve({ok:true,json:async()=>({model:kind==='mismatch'?'B':'A',reasoning:kind==='malformed'?{allowed_options:'off'}:{}})});
 await flush();assertState(s,snapshot);assert.ok(s.ctx.aiEffortReadiness().notes.length);assert.ok(s.card('outline').querySelector('select').disabled);assert.equal(s.card('cleanup').querySelector('select').disabled,false);assert.equal(s.writes.length,0);
 }
});
test('E07 binary default ON/OFF/unknown hides grades without changing intensity; cleanup stays independent',async()=>{
 for(const defaultValue of ['on','off',undefined]) {const s=setup(JSON.stringify(snapshot));await capability(s,{allowed_options:['off','on'],default:defaultValue});assertState(s,snapshot);assert.equal(s.card('outline').querySelector('.effort-grades').hidden,true);assert.equal(s.card('cleanup').querySelector('.effort-grades').hidden,false);assert.equal(s.card('outline').querySelector('select').options.find(o=>o.value==='on').disabled,defaultValue!=='on');assert.equal(s.ctx.aiEffortReadiness().blockers.length>0,defaultValue!=='on');s.change('outline','off');assert.equal(s.card('outline').querySelector('[name^="ai_effort_choice_"]:checked').value,'high');if(defaultValue==='on'){s.change('outline','on');assert.equal(s.values().outline,'high');}assert.equal(s.values().cleanup,'low');}
});
test('E07 normal/minimal/xhigh/high-only mappings follow backend; unsupported preserved and readiness blocks',async()=>{
 for(const [allowed,support] of [[['off','low','medium','high'],[true,true,true,true,true]],[['minimal'],[false,true,true,true,true]],[['xhigh'],[false,false,false,true,true]],[['high'],[false,false,false,true,true]]]) {
 const s=setup(JSON.stringify(snapshot));await capability(s,{allowed_options:allowed});assertState(s,snapshot);['off','low','medium','high','ultra'].forEach((v,i)=>assert.equal(s.ctx.localEffortSupport(v),support[i]));assert.equal(s.card('cleanup').querySelector('select').options.filter(o=>o.value!=='on').some(o=>o.disabled),false);
 }
});
test('E08 no proxy submit name, unique original hidden fields, simple/detail produce identical settings',()=>{
 const s=setup(JSON.stringify(snapshot));const payload=()=>s.doc.querySelectorAll('input[type="hidden"]').map(n=>[n.name,n.value]);const first=payload();assert.equal(first.length,4);assert.equal(new Set(first.map(([n])=>n)).size,4);keys.forEach(k=>assert.equal(s.card(k).querySelector('select').name,undefined));s.doc.getElementById('effort-detail-toggle').dispatchEvent(new SyntheticEvent('click'));assert.deepEqual(payload(),first);
});
test('readiness hook included and inner disclosure barrier removed; CSS responsive, no fixed card height',()=>{
 const base=path.join(__dirname,'../../src/gurumoji');const app=fs.readFileSync(path.join(base,'static/app.js'),'utf8');const template=fs.readFileSync(path.join(base,'templates/views/create.html'),'utf8');const css=fs.readFileSync(path.join(base,'static/ai-effort.css'),'utf8');assert.ok(app.includes('const effortReadiness = aiEffortReadiness();'));assert.ok(template.includes('<section class="effort-details"'));assert.ok(!template.includes('<details class="effort-details"'));assert.ok(css.includes('@media (max-width: 600px)'));assert.ok(css.includes(':focus-visible'));assert.ok(css.includes('min-height: 44px'));
});
test('recommended high/MAX require outline support; cleanup OFF does not activate its context outline',async()=>{
 const s=setup();s.doc.getElementById('create-outline').checked=false;s.doc.getElementById('clean-transcript').checked=false;s.ctx.tokenConfigSnapshot.typesafe=true;
 for(const v of ['low','medium','off']) {s.change('cleanup',v);assert.equal(Boolean(s.ctx.aiEffortStageEnabled('outline','create-outline')),false);}
 for(const v of ['high','ultra']) {s.change('cleanup',v);assert.equal(Boolean(s.ctx.aiEffortStageEnabled('outline','create-outline')),true);}
 await capability(s,{allowed_options:['off','on'],default:'off'});assert.ok(s.ctx.aiEffortReadiness().blockers.some(x=>x.includes('会話の流れ')));s.change('cleanup','off');assert.equal(s.ctx.aiEffortReadiness().blockers.some(x=>x.includes('会話の流れ')),false);
});
test('high-only model can recover a stored OFF through detailed native controls without automatic coercion',async()=>{
 const s=setup('{"outline":"off"}');s.doc.querySelector('[name="transcript_finishing_mode"][value="custom"]').checked=true;await capability(s,{allowed_options:['high']});const card=s.card('outline');const on=card.querySelector('[name="ai_thinking_mode_outline"][value="on"]');assert.equal(on.disabled,false);assert.equal(s.values().outline,'off');on.checked=true;on.dispatchEvent(new SyntheticEvent('change',{bubbles:true}));const high=card.querySelector('[name="ai_effort_choice_outline"][value="high"]');assert.equal(high.disabled,false);high.checked=true;high.dispatchEvent(new SyntheticEvent('change',{bubbles:true}));assert.equal(s.values().outline,'high');
});
test('inactive recommended cleanup without TypeSafe causes no capability readiness blocker',()=>{
 const s=setup();s.doc.getElementById('create-outline').checked=false;s.doc.getElementById('clean-transcript').checked=false;s.doc.getElementById('detect-names').checked=false;s.doc.getElementById('ai-provider').value='lmstudio';s.sync();assert.equal(s.ctx.aiEffortReadiness().blockers.length,0);
});
function setMode(s,mode) { s.doc.querySelector(`[name="transcript_finishing_mode"][value="${mode}"]`).checked=true;s.sync(); }
function deactivate(s) { for(const id of ['clean-transcript','detect-names','create-outline','finish-in-obsidian','jev-compare'])s.doc.getElementById(id).checked=false;s.sync(); }
test('P14 advanced forces both name stages despite unchecked preferences, and shows mandatory controls honestly',async()=>{
 const s=setup('{"outline":"high","cleanup":"off","name_extract":"medium","name_verify":"medium"}');deactivate(s);setMode(s,'advanced');await capability(s,{allowed_options:['high']});
 for(const key of ['name_extract','name_verify']){assert.equal(s.ctx.aiEffortStageEnabled(key),true);assert.equal(s.card(key).getAttribute('aria-disabled'),'false');assert.match(s.card(key).parentElement.querySelector('.effort-status').textContent,/全文方式の対象/);}
 assert.equal(s.ctx.aiEffortReadiness().blockers.length,2);for(const id of ['clean-transcript','detect-names']){const input=s.doc.getElementById(id);assert.equal(input.checked,false);assert.equal(input.hidden,true);assert.equal(input.disabled,true);assert.equal(s.doc.getElementById(`${id}-mode-note`).hidden,false);}
 assert.equal(s.calls.length,1);assert.equal(s.writes.length,0);
});
test('P15 advanced full cleanup requires context outline even with both checkbox preferences off',async()=>{
 const s=setup('{"outline":"medium","cleanup":"high","name_extract":"high","name_verify":"high"}');deactivate(s);setMode(s,'advanced');await capability(s,{allowed_options:['high']});
 assert.equal(s.ctx.aiEffortStageEnabled('outline'),true);assert.match(s.card('outline').parentElement.querySelector('.effort-status').textContent,/校正の参照用も対象/);assert.equal(s.ctx.aiEffortReadiness().blockers.length,1);assert.match(s.ctx.aiEffortReadiness().blockers[0],/会話の流れ/);
 for(const level of ['low','medium','high','ultra']){s.change('cleanup',level);assert.equal(s.ctx.aiEffortStageEnabled('outline'),true);}
 s.change('cleanup','off');assert.equal(s.ctx.aiEffortStageEnabled('outline'),false);assert.equal(s.ctx.aiEffortReadiness().blockers.length,0);
 s.doc.getElementById('create-outline').checked=true;s.sync();assert.equal(s.ctx.aiEffortReadiness().blockers.length,1);assert.equal(s.ctx.aiEffortStageEnabled('name_extract'),true);
});
test('off/custom inactive preferences remain inactive; advanced roundtrip never rewrites them or settings',async()=>{
 const s=setup(JSON.stringify(snapshot));deactivate(s);setMode(s,'custom');await capability(s,{allowed_options:['high']});const values=s.values();assert.equal(s.ctx.aiEffortReadiness().blockers.length,0);
 for(const mode of ['advanced','off','custom']){setMode(s,mode);for(const id of ['clean-transcript','detect-names']){assert.equal(s.doc.getElementById(id).checked,false);assert.equal(s.doc.getElementById(id).hidden,mode==='advanced');assert.equal(s.doc.getElementById(id).disabled,mode==='advanced');}assertState(s,values);if(mode!=='advanced')assert.equal(s.ctx.aiEffortReadiness().blockers.length,0);}
 s.doc.getElementById('create-outline').checked=true;s.doc.getElementById('detect-names').checked=true;setMode(s,'off');assert.equal(s.ctx.aiEffortReadiness().blockers.length,0);assert.equal(s.ctx.aiEffortStageEnabled('outline'),false);assert.equal(s.ctx.aiEffortStageEnabled('name_extract'),false);
});
test('custom checked full cleanup/Jev requires outline; recommended ignores stale advanced checkboxes',async()=>{
 const s=setup('{"outline":"medium","cleanup":"low","name_extract":"high","name_verify":"high"}');deactivate(s);setMode(s,'custom');await capability(s,{allowed_options:['high']});
 for(const id of ['clean-transcript','jev-compare']){s.doc.getElementById(id).checked=true;s.sync();assert.equal(s.ctx.aiEffortReadiness().blockers.length,1);s.doc.getElementById(id).checked=false;}
 s.doc.getElementById('clean-transcript').checked=true;s.doc.getElementById('create-outline').checked=true;s.doc.getElementById('jev-compare').checked=true;setMode(s,'recommended');assert.equal(s.ctx.aiEffortStageEnabled('outline'),false);assert.equal(s.ctx.aiEffortReadiness().blockers.length,0);
});
function installActualModeHandler(s) {
 const app=fs.readFileSync(path.join(__dirname,'../../src/gurumoji/static/app.js'),'utf8');
 const presets=app.slice(app.indexOf('function selectedTranscriptFinishingMode('),app.indexOf('function selectDefaultAiOptions('));
 const event=app.slice(app.indexOf("transcriptFinishingModeInputs.forEach(input => listen(input, 'change'"),app.indexOf('[modelName, languageSelect, audioPreprocess, writeSrt, burnSubtitledVideo].forEach'));
 Object.assign(s.ctx,{transcriptFinishingModeInputs:s.doc.querySelectorAll('[name="transcript_finishing_mode"]'),aiProvider:s.doc.getElementById('ai-provider'),cleanTranscript:s.doc.getElementById('clean-transcript'),detectNames:s.doc.getElementById('detect-names'),createOutline:s.doc.getElementById('create-outline'),jevCompare:s.doc.getElementById('jev-compare'),finishInObsidian:s.doc.getElementById('finish-in-obsidian'),finishingModeHint:null,listen(node,event,callback){node.addEventListener(event,callback);},syncAiFields(){s.sync();}});
 vm.runInContext(presets+event,s.ctx);s.ctx.applyTranscriptFinishingPreset();
 return mode=>{const input=s.doc.querySelector(`[name="transcript_finishing_mode"][value="${mode}"]`);input.checked=true;input.dispatchEvent(new SyntheticEvent('change',{bubbles:true}));};
}
test('P18 actual app mode-change handler restores recommended name opt-out and all per-mode preferences',()=>{
 const s=setup(JSON.stringify(snapshot));const change=installActualModeHandler(s);const ids=['clean-transcript','detect-names','create-outline','jev-compare','finish-in-obsidian'];
 const apply=values=>ids.forEach((id,i)=>{s.doc.getElementById(id).checked=values[i];});const read=()=>ids.map(id=>s.doc.getElementById(id).checked);
 const rec=[false,false,false,false,true],advanced=[false,false,false,true,false],custom=[true,false,true,false,true];apply(rec);const efforts=s.values();
 change('advanced');apply(advanced);s.sync();assert.equal(s.ctx.aiEffortStageEnabled('name_extract'),true);assert.equal(s.doc.getElementById('detect-names').hidden,true);
 change('recommended');assert.deepEqual(read(),rec);assert.equal(s.ctx.aiEffortStageEnabled('name_extract'),false);assert.equal(s.doc.getElementById('detect-names').hidden,false);
 change('advanced');assert.deepEqual(read(),advanced);change('custom');apply(custom);change('off');change('custom');assert.deepEqual(read(),custom);change('recommended');assert.deepEqual(read(),rec);change('advanced');assert.deepEqual(read(),advanced);
 assertState(s,efforts);assert.equal(s.calls.length,0);assert.equal(s.writes.length,0);
});
test('actual handler applies defaults only to new modes, keeps repeated events inert, and never invents Jev consent',()=>{
 const s=setup();const change=installActualModeHandler(s);s.doc.getElementById('detect-names').checked=false;
 change('recommended');assert.equal(s.doc.getElementById('detect-names').checked,false);assert.equal(s.doc.getElementById('jev-compare').checked,false);
 for(const mode of ['advanced','recommended','off','advanced','recommended']){change(mode);assert.equal(s.doc.getElementById('jev-compare').checked,false);}
 assert.equal(s.doc.getElementById('detect-names').checked,false);
});
