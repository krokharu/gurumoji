// Original editor + save handlers in a synthetic DOM. No browser/network/user data.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../src/gurumoji/static/app.js'), 'utf8').replace(/\r\n/g, '\n');
function extract(name) {
  const start = source.indexOf(`function ${name}(`), end = source.indexOf('\n}', start);
  assert(start >= 0 && end > start); return source.slice(start, end + 2);
}
function make(marker = 'default') {
  const requests = [], effects = [], nodes = new Map();
  let ctx;
  const node = () => ({children: [], events: {}, attributes: {}, isConnected: true, classList: {toggle() {}},
    add(option) {this.children.push(option);}, append(...items) {this.children.push(...items);},
    setAttribute(k,v) {this.attributes[k]=v;}, addEventListener(k,f) {this.events[k]=f;},
    focus() {ctx.document.activeElement=this;}});
  const profile = {speaker_label:'A', display_name:'Synthetic A', session_role:'participant', notes:'retain',
    ...(marker === undefined ? {} : {session_role_source:marker})};
  ctx = {currentJobId:'A', currentJobDirty:false, currentJobMutationGeneration:0, resultRequestSequence:0,
    currentJob:{speaker_profiles:{A:profile,B:{session_role:'observer',session_role_source:'registry'}},
      speaker_names:{},segments:[],session_profile:{},revision_count:1, preparation:{role:'moderator',speaker_verified:false}},
    speakerRoleLabels:{participant:'参加者',observer:'観察者',moderator:'司会者'},speakerThemeColors:['#000000'],
    speakerLabels:()=>['A','B'],fallbackSpeaker:()=> 'Synthetic',
    Option:function(text,value){this.text=text;this.value=value;},
    document:{createElement:node,querySelector(s){if(!nodes.has(s))nodes.set(s,node());return nodes.get(s);}},
    renderSpeakerInsights:()=>effects.push('insights'),resultCard:node(),saveButton:node(),
    captureSessionProfile(){},kushinadaEmotion(){return '';},
    setAlert(_,text){effects.push(text);},showDraftRecovery(){effects.push('conflict');},
    renderDownloads(){},loadTrainingStatus(){},
    renderResult(data){ctx.currentJob=data;ctx.currentJobDirty=false;ctx.resultRequestSequence++;ctx.saveButton.disabled=false;effects.push('renderResult');},
    readJsonResponse:async response=>response.data,
    apiFetch(url,options){let resolve;const promise=new Promise(r=>resolve=r);requests.push({url,options,resolve});return promise;},
    listen(_,event,callback){ctx.save=callback;}};
  vm.createContext(ctx);
  for(const name of ['setCurrentJobDirty','ensureConversationSpeakerProfiles','conversationRoleControl'])vm.runInContext(extract(name),ctx);
  const saveStart=source.indexOf("listen(saveButton, 'click', async () => {");
  vm.runInContext(source.slice(saveStart,source.indexOf('\n});',saveStart)+4),ctx);
  const render = () => ctx.conversationRoleControl(ctx.currentJob.speaker_profiles.A,'A',{},0);
  const control = render();
  return {ctx,profile,control,render,requests,effects,select:control.children[0],button:control.children[1],status:control.children[2]};
}
const passed=[];
function check(name,fn){return Promise.resolve().then(fn).then(()=>passed.push(name));}
(async()=>{
await check('render_preserves_default_legacy_registry_explicit_and_invalid',()=>{
  const labels={default:'初期表示',legacy_unknown:'設定元不明',registry:'話者管理から設定',explicit:'この会話で明示設定',bad:'設定元不明',toString:'設定元不明'};
  for(const [marker,text] of Object.entries(labels)) {
    const p=make(marker), before=JSON.stringify(p.ctx.currentJob);p.render();
    assert.equal(JSON.stringify(p.ctx.currentJob),before);assert(p.status.textContent.includes(text));
    assert.equal(p.ctx.currentJobMutationGeneration,0);assert.equal(p.requests.length,0);
  }
  const p=make('legacy_unknown');delete p.profile.session_role_source;
  assert(p.render().children[2].textContent.includes('設定元不明'));assert.equal(p.profile.session_role_source,undefined);
});
await check('display_name_refresh_updates_role_names_without_certifying_or_dirtying',()=>{
  const p=make('legacy_unknown');p.profile.display_name='Renamed';p.control.refreshAccessibleName();
  assert.equal(p.select.attributes['aria-label'],'Renamed（話者ID A）の会話役割');
  assert(p.button.attributes['aria-label'].startsWith('Renamed（話者ID A）'));
  assert.equal(p.profile.session_role_source,'legacy_unknown');assert.equal(p.ctx.currentJobMutationGeneration,0);
  assert.equal(p.requests.length,0);
});
let explicitProfile;
await check('same_value_click_sets_only_target_once_without_autosave_and_preserves_focus',()=>{
  for(const marker of ['default','legacy_unknown','registry']){
    const p=make(marker), other=JSON.stringify(p.ctx.currentJob.speaker_profiles.B), prep=JSON.stringify(p.ctx.currentJob.preparation);
    p.button.focus();p.button.events.click();p.button.events.click();
    assert.equal(p.profile.session_role,'participant');assert.equal(p.profile.session_role_source,'explicit');
    assert.equal(p.ctx.currentJobMutationGeneration,1);assert.equal(p.ctx.currentJobDirty,true);
    assert.equal(p.ctx.document.activeElement,p.button);assert.equal(p.requests.length,0);
    assert.equal(JSON.stringify(p.ctx.currentJob.speaker_profiles.B),other);assert.equal(JSON.stringify(p.ctx.currentJob.preparation),prep);
    assert(p.status.textContent.includes('まだ保存されていません'));explicitProfile=structuredClone(p.profile);
  }
});
await check('select_change_uses_same_handler_and_semantic_controls',()=>{
  const p=make();assert.equal(p.select.events.change,p.button.events.click);
  assert.equal(p.button.type,'button');assert.equal(p.status.attributes.role,'status');assert.equal(p.status.attributes['aria-live'],'polite');
  assert.equal(p.select.attributes['aria-describedby'],'conversation-role-status-0 conversation-role-help');
  assert.equal(p.select.attributes['aria-label'],'Synthetic A（話者ID A）の会話役割');
  p.select.focus();p.select.value='observer';p.select.events.change();
  assert.equal(p.ctx.document.activeElement,p.select);assert.equal(p.profile.session_role,'observer');
  assert.equal(p.profile.session_role_source,'explicit');assert.equal(p.ctx.currentJobMutationGeneration,1);
  assert(p.button.attributes['aria-label'].includes('観察者'));assert.equal(p.requests.length,0);
});
await check('stale_detached_profile_and_navigation_handlers_are_noops',()=>{
  for(const invalidate of [p=>p.control.isConnected=false,p=>p.ctx.currentJobId='B',p=>p.ctx.currentJob={...p.ctx.currentJob},p=>delete p.ctx.currentJob.speaker_profiles.A]){
    const p=make();invalidate(p);p.button.events.click();p.select.value='observer';p.select.events.change();
    assert.equal(p.profile.session_role_source,'default');assert.equal(p.ctx.currentJobMutationGeneration,0);assert.equal(p.requests.length,0);
  }
});
await check('ordinary_save_does_not_certify_default_or_legacy',async()=>{
  for(const marker of ['default','legacy_unknown']){
    const p=make(marker);const saving=p.ctx.save();const payload=JSON.parse(p.requests[0].options.body);
    assert.equal(payload.speaker_profiles.A.session_role_source,marker);
    p.requests[0].resolve({ok:true,data:{...p.ctx.currentJob,revision_count:2}});await saving;
    assert.equal(p.ctx.currentJob.speaker_profiles.A.session_role_source,marker);
  }
});
await check('explicit_save_success_failure_conflict_and_later_mutations',async()=>{
  for(const status of [200,409,500]){
    const p=make();p.button.events.click();const saving=p.ctx.save();
    const payload=JSON.parse(p.requests[0].options.body);assert.equal(payload.speaker_profiles.A.session_role_source,'explicit');
    p.requests[0].resolve({ok:status===200,status,data:{...p.ctx.currentJob,revision_count:2}});await saving;
    assert.equal(p.ctx.currentJobDirty,status!==200);if(status!==200)assert(p.status.textContent.includes('まだ保存されていません'));
  }
  const p=make();const saving=p.ctx.save();p.button.events.click();
  p.requests[0].resolve({ok:true,data:{speaker_profiles:{A:{session_role_source:'default'}},revision_count:2}});await saving;
  assert.equal(p.ctx.currentJob.speaker_profiles.A.session_role_source,'explicit');assert.equal(p.ctx.currentJobDirty,true);assert.equal(p.ctx.currentJobMutationGeneration,1);
  assert(!p.effects.includes('renderResult'));assert.equal(p.requests.length,1);
});
await check('old_save_success_error_and_finally_reject_other_job_and_aba',async()=>{
  for(const status of [200,409,500,'network'])for(const aba of [false,true]){
    const p=make();const saving=p.ctx.save();
    p.ctx.currentJobId='B';p.ctx.currentJob={...structuredClone(p.ctx.currentJob),revision_count:3};
    if(aba)p.ctx.currentJobId='A';
    p.ctx.currentJob.speaker_profiles.A.session_role_source='registry';p.ctx.currentJobDirty=false;
    const before=JSON.stringify(p.ctx.currentJob);p.effects.length=0;
    // The newly displayed view may already have its own save pending.
    p.ctx.saveButton.disabled=true;
    p.requests[0].resolve(status==='network'?{ok:true,get data(){throw Error('old request decode failure');}}:{ok:status===200,status,data:{revision_count:2}});
    await saving;
    assert.equal(JSON.stringify(p.ctx.currentJob),before);assert.equal(p.ctx.currentJobDirty,false);
    assert.equal(p.effects.length,0);assert.equal(p.ctx.saveButton.disabled,true);
  }
});
await check('navigation_generation_rejects_same_object_and_protects_new_save',async()=>{
  const p=make();const first=p.ctx.save();await p.ctx.save();assert.equal(p.requests.length,1);
  // showView invalidates the earlier save even if the same object stays loaded.
  p.ctx.resultRequestSequence++;p.ctx.saveButton.disabled=false;
  const second=p.ctx.save();assert.equal(p.requests.length,2);p.effects.length=0;
  p.requests[0].resolve({ok:false,status:409,data:{error:'old conflict'}});await first;
  assert.equal(p.effects.length,0);assert.equal(p.ctx.saveButton.disabled,true);assert.equal(p.ctx.currentJobDirty,false);
  p.requests[1].resolve({ok:true,data:{...p.ctx.currentJob,revision_count:3}});await second;
  assert.equal(p.ctx.saveButton.disabled,false);assert.equal(p.ctx.currentJob.revision_count,3);
  const show=extract('showView');assert(show.includes('resultRequestSequence += 1;'));
  assert(show.includes('if (saveButton) saveButton.disabled = false;'));
});
console.log(JSON.stringify({passed,explicitProfile,scope:'Synthetic DOM + original handlers; native keyboard/AT and real browser not tested'}));
})().catch(error=>{console.error(error);process.exitCode=1;});
