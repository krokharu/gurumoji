// Original editor summary renderer; synthetic provenance, no persistence or browser.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../src/gurumoji/static/app.js'),'utf8').replace(/\r\n/g,'\n');
function extract(name){const start=source.indexOf(`function ${name}(`);assert(start>=0);return source.slice(start,source.indexOf('\n}',start)+2);}
const host={children:[],replaceChildren(){this.children=[];},append(child){this.children.push(child);}};
const ctx={currentJob:{speaker_profiles:{},session_profile:{session_type:'focus_group'}},document:{querySelector:selector=>selector==='#speaker-insights'?host:null,createElement:()=>({})}};
vm.createContext(ctx);for(const name of ['renderSpeakerInsights','moderatorCountText'])vm.runInContext(extract(name),ctx);
const metrics=Object.fromEntries(['A','B','C','D','E','F'].map((speaker,index)=>[speaker,{count:1,timedCount:1,missingTimeCount:0,seconds:index?1:95,timedSeconds:index?1:95}]));
function render(sources,roles={}){
 ctx.currentJob.speaker_profiles=Object.fromEntries(Object.entries(sources).map(([speaker_label,session_role_source])=>[speaker_label,{speaker_label,session_role:roles[speaker_label]||'participant',session_role_source}]));
 const before=structuredClone(ctx.currentJob);ctx.renderSpeakerInsights(metrics);assert.deepEqual(ctx.currentJob,before);return host.children.map(row=>row.textContent).join('\n');
}
for(const source of ['default','legacy_unknown',undefined,'future']){
 const text=render(Object.fromEntries(Object.keys(metrics).map(speaker=>[speaker,source])));
 assert(text.includes('役割未設定・記録元不明 6人'));assert(text.includes('仮集計'));assert(text.includes('参加者（仮） 6人'));
 assert(!text.includes('50%以上'));assert(text.includes('割合は判定できません'));
}
for(const source of ['explicit','registry']){
 const text=render(Object.fromEntries(Object.keys(metrics).map(speaker=>[speaker,source])));
 assert(text.includes('参加者 6人'));assert(text.includes('A の発言が参加者内50%以上'));assert(!text.includes('仮集計'));
}
let text=render({A:'explicit',B:'legacy_unknown'},{B:'observer'});assert(!text.includes('50%以上'));assert(text.includes('役割未設定・記録元不明 1人'));
ctx.currentJob.session_profile.session_type='meeting';text=render({A:'default',B:'explicit'},{A:'chair',B:'decision_maker'});
assert(text.includes('進行・議長（仮） 1人'));assert(text.includes('意思決定者（仮） 1人'));assert(text.includes('仮集計'));
console.log('PASS uncertain role summaries are provisional, known provenance stays definite, ratios suppressed, source profiles unchanged');
