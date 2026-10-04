// Pure-function / synthetic DOM contracts, not a real-browser visual verdict.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const app = fs.readFileSync(path.join(root, 'src/gurumoji/static/app.js'), 'utf8').replace(/\r\n/g, '\n');
const charts = fs.readFileSync(path.join(root, 'src/gurumoji/static/analysis-visualizations.js'), 'utf8');
function fn(name, source = app) {
  const start = source.search(new RegExp(`(?:async )?function ${name}\\(`));
  assert.notEqual(start, -1, name);
  const end = source.indexOf('\n}', start);
  return source.slice(start, end + 2);
}
function context(names, values = {}) {
  const ctx = vm.createContext({...values});
  names.forEach(name => vm.runInContext(fn(name), ctx));
  return ctx;
}
function node(value = '') {
  return {value, textContent: '', hidden: false, attributes: {}, disabled: false,
    setAttribute(k,v) { this.attributes[k] = v; }, classList: {toggle(){}, add(){}, remove(){}},
    focus() { this.focused = true; }, querySelector(){return null;}};
}
function planContext() {
  const ctx = context(['enabledTextDestinations', 'createReadiness'], {
    aiProvider: {value:'lmstudio'}, selectedOptionText: () => 'LM Studio',
    mode: 'advanced', selectedTranscriptFinishingMode() {return ctx.mode;},
    finishInObsidian: {checked:false}, detectNames: {checked:true}, createOutline: {checked:false},
    jevCompare: {checked:false}, modelName: {value:'tiny'}, transcriptionBackend: {value:'whisperx'},
    configLoadState:'loaded', tokenConfigSnapshot: {huggingface:true,typesafe:true,lmstudio:true,lmstudio_model:'synthetic-model'},
    document: {querySelector: () => ({value:'cpu',checked:false})}, hasSelectedSource: () => true,
  });
  return ctx;
}
test('UI03: only explicitly enabled destinations; recommended Jev and deferred work accounted for', () => {
  const ctx = planContext();
  assert.equal(ctx.enabledTextDestinations().map(x=>x.provider).join(','), 'lmstudio');
  ctx.jevCompare.checked = true;
  assert.equal(ctx.enabledTextDestinations().map(x=>x.provider).join(','), 'lmstudio,typesafe');
  ctx.mode = 'recommended'; ctx.jevCompare.checked = false;
  assert.equal(ctx.enabledTextDestinations().map(x=>x.provider).join(','), 'lmstudio,typesafe');
  ctx.finishInObsidian.checked = true;
  assert.equal(ctx.enabledTextDestinations().map(x=>x.provider).join(','), 'lmstudio');
  ctx.detectNames.checked = false;
  assert.equal(ctx.enabledTextDestinations().length, 0);
  ctx.mode = 'off'; ctx.jevCompare.checked = true;
  assert.equal(ctx.enabledTextDestinations().length, 0);
});
test('UI02: loading, config failure, HF and backend failures block; models are not falsely reported ready', () => {
  const ctx = planContext();
  ctx.configLoadState = 'loading'; assert.equal(ctx.createReadiness().ready, false);
  ctx.configLoadState = 'error'; assert.equal(ctx.createReadiness().ready, false);
  ctx.configLoadState = 'loaded'; ctx.tokenConfigSnapshot.huggingface = false;
  assert.equal(ctx.createReadiness().ready, false);
  ctx.tokenConfigSnapshot.huggingface = true;
  ctx.tokenConfigSnapshot.transcription_readiness = {whisperx:{blockers:['not installed'],notes:[]}};
  assert.equal(ctx.createReadiness().ready, false);
  ctx.tokenConfigSnapshot.transcription_readiness.whisperx = {blockers:[],notes:[],models:{cpu:{tiny:{message:'未取得。開始時にダウンロード'}}}};
  assert.equal(ctx.createReadiness().ready, false);
  ctx.document.querySelector = () => ({value:'cpu',checked:true});
  assert.equal(ctx.createReadiness().ready, true);
  assert.match(ctx.createReadiness().notes.join(''), /未取得/);
  ctx.transcriptionBackend.value='qwen3_nemotron'; ctx.tokenConfigSnapshot.huggingface=false;
  ctx.tokenConfigSnapshot.transcription_readiness.qwen3_nemotron = {blockers:['Qwen未準備']};
  assert.match(ctx.createReadiness().blockers.join(''), /Qwen/);
  assert.doesNotMatch(ctx.createReadiness().blockers.join(''), /Hugging/);
});
test('UI06: late and repeated diagnostics retain manually chosen model/device, reset is explicit', () => {
  const controls = Object.fromEntries(['model-name','transcription-device','diarization-device','machine-summary','machine-recommendation','machine-selection-message'].map(id => [id,node()]));
  for(const id of ['model-name','transcription-device','diarization-device']) {
    const item=controls[id]; item.id=id; item.value = id==='model-name'?'tiny':'cpu';
    item.options = ['tiny','small','cpu','cuda'].map(value=>({value}));
    item.querySelector=()=>item.options[3];
  }
  const ctx=context(['setAlert','applyMachineProfile'], {document:{querySelector:q=>controls[q.slice(1)]},manuallySelectedMachineFields:new Set(['model-name','transcription-device','diarization-device']),setHardwareLights(){},updateCreateSummary(){}});
  const machine={cpu:{available:true},gpu:{cuda_available:true},recommended:{model_name:'small',device:'cuda',diarization_device:'cuda'}};
  ctx.applyMachineProfile(machine); ctx.applyMachineProfile(machine);
  assert.equal(controls['model-name'].value,'tiny'); assert.equal(controls['transcription-device'].value,'cpu');
  ctx.applyMachineProfile(machine,{reset:true}); assert.equal(controls['model-name'].value,'small'); assert.equal(controls['transcription-device'].value,'cuda');
  ctx.applyMachineProfile({...machine,gpu:{cuda_available:false}});
  assert.equal(controls['transcription-device'].value,'cpu'); assert.match(controls['machine-selection-message'].textContent,/利用できない/);
});
test('UI01: edit is explicit, announces expanded state and focuses textarea without playing', () => {
  const edit=node(), textarea=node(), row=node(); row.dataset={segmentId:'s2'};
  row.querySelector=q=>q==='textarea'?textarea:edit;
  const ctx=context(['selectSegmentForEdit'],{selectedSegmentId:null,document:{querySelectorAll:()=>[row]}});
  ctx.selectSegmentForEdit('s2',{focus:true}); assert.equal(textarea.focused,true);
  assert.equal(edit.attributes['aria-expanded'],'true'); assert.equal(ctx.selectedSegmentId,'s2');
});
test('UI04: undo restores all attributes and preserves unrelated edits', () => {
  const edited={id:'s1',text:'edited'}; const deleted={id:'s2',text:'restored',start:3,end:5,speaker:'A',emotions:{sample:true}};
  const elements={'#segment-delete-status':node(),'#undo-segment-delete':node()};
  const ctx=context(['setAlert','undoSegmentDeletion'],{currentJobId:'j1',currentJob:{segments:[edited]},deletedSegmentUndo:[{itemId:'j1',index:1,segment:deleted}],document:{querySelector:q=>elements[q]},setCurrentJobDirty(){},renderSpeakerEditor(){},updateSegmentFilterOptions(){},renderSegments(){},selectSegmentForEdit(id,opts){assert.equal(id,'s2');assert.equal(opts.focus,true);}});
  ctx.undoSegmentDeletion(); assert.equal(ctx.currentJob.segments[0].text,'edited');
  assert.deepEqual(ctx.currentJob.segments[1],deleted); assert.equal(elements['#undo-segment-delete'].hidden,true);
});
test('UI05: failed record delete notifies current view and restores media; duplicate requests suppressed', async () => {
  const message=node(), button=node(), player={currentTime:3,src:'synthetic.mp4',pause(){},getAttribute(){return this.src;},removeAttribute(){this.src='';},load(){},addEventListener(type,cb){cb();}};
  let requests=0, resolveFetch;
  const ctx=context(['setAlert','deleteLibraryItem'],{currentJobId:'j1',resultCard:{hidden:false},deleteRecordButton:button,mediaPlayer:player,deletingLibraryItems:new Set(),window:{confirm:()=>true},document:{querySelector:()=>message},apiFetch(){requests++;return new Promise(resolve=>resolveFetch=resolve);},readJsonResponse:async()=>({error:'synthetic failure'}),deleteRecoveryNote:()=>''});
  const pending=ctx.deleteLibraryItem('j1','synthetic');
  await ctx.deleteLibraryItem('j1','synthetic'); assert.equal(requests,1); assert.equal(button.disabled,true);
  resolveFetch({ok:false}); await pending;
  assert.match(message.textContent,/synthetic failure/); assert.equal(message.attributes.role,'alert');
  assert.equal(player.src,'synthetic.mp4'); assert.equal(player.currentTime,3); assert.equal(button.disabled,false);
});
test('UI08/10: unsaved draft contains revision and edited data, statuses have live semantics', async () => {
  let blob, clicked=false;
  const link={click(){clicked=true;},remove(){}};
  const ctx=context(['downloadUnsavedDraft','setAlert'],{captureSessionProfile(){},deepCopy:x=>JSON.parse(JSON.stringify(x)),currentJobId:'j1',currentJob:{revision_count:4,segments:[{id:'s1',text:'unsaved'}]},Blob,URL:{createObjectURL:b=>(blob=b,'blob:synthetic'),revokeObjectURL(){}},document:{createElement:()=>link,body:{append(){}}},window:{setTimeout:fn=>fn()}});
  ctx.downloadUnsavedDraft('transcript');
  const data=JSON.parse(await blob.text()); assert.equal(data.base_revision,4); assert.equal(data.draft.segments[0].text,'unsaved');assert.equal(clicked,true);
  const status=node(); ctx.setAlert(status,'保存済み'); assert.equal(status.attributes.role,'status');assert.equal(status.attributes['aria-live'],'polite');
  ctx.setAlert(status,'競合',true);assert.equal(status.attributes.role,'alert');assert.equal(status.attributes['aria-live'],'assertive');
});
test('Statistics: missing p is not zero, small p keeps useful precision', () => {
  const ctx=vm.createContext({}); vm.runInContext(fn('analysisPValueText',charts),ctx);
  assert.equal(ctx.analysisPValueText(null),'未計算');
  assert.equal(ctx.analysisPValueText(0.00000000123),'p = 1.23e-9');
  assert.equal(ctx.analysisPValueText(.04),'p = 0.040');
});
