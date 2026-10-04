// Original metric/insight functions; synthetic timing fixtures, no data mutation or browser.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.join(__dirname,'../src/gurumoji/static');
function extract(file,name){const s=fs.readFileSync(path.join(root,file),'utf8').replace(/\r\n/g,'\n');const start=s.indexOf(`function ${name}(`);assert(start>=0);return s.slice(start,s.indexOf('\n}',start)+2);}
const insights={children:[],replaceChildren(){this.children=[];},append(n){this.children.push(n);}};
const ctx={currentJob:{segments:[],speaker_profiles:{},session_profile:{session_type:'focus_group'}},document:{querySelector:s=>s==='#speaker-insights'?insights:null,createElement:()=>({})}};
vm.createContext(ctx);
for(const [file,name] of [['analysis-content.js','analysisEvidenceTimeValid'],['app.js','speakerMetrics'],['app.js','renderSpeakerInsights'],['app.js','moderatorCountText']])vm.runInContext(extract(file,name),ctx);
const text=()=>insights.children.map(n=>n.textContent).join('\n');
const segment=(speaker,start,end,extra={})=>({speaker,start,end,text:'abc',...extra});
function run(segments,roles={A:'participant',B:'participant'}){
 ctx.currentJob.segments=segments;ctx.currentJob.speaker_profiles=Object.fromEntries(Object.entries(roles).map(([speaker_label,session_role])=>[speaker_label,{speaker_label,session_role,session_role_source:'explicit'}]));
 const before=structuredClone(ctx.currentJob);const metrics=ctx.speakerMetrics();ctx.renderSpeakerInsights(metrics);assert.deepEqual(ctx.currentJob,before);return metrics;
}
for(const bad of [undefined,null,'','0','bad',NaN,Infinity,-1]){
 for(const side of ['start','end']){
  const invalid=segment('A',0,5,{[side]:bad});const m=run([segment('A',0,5),invalid,segment('B',0,2)]);
  assert.equal(m.A.seconds,5);assert.equal(m.A.timedCount,1);assert.equal(m.A.missingTimeCount,1);assert.equal(m.A.count,2);assert.equal(m.A.characters,6);
  assert.equal(m.A.share,null);assert.equal(m.B.share,null);assert(!text().includes('50%以上'));assert(text().includes('時刻不明'));
 }
}
for(const invalid of [segment('A',5,2),segment('A',0,8,{time_unknown:true}),{speaker:'A',text:'abc'}]){
 const m=run([invalid]);assert.equal(m.A.seconds,null);assert.equal(m.A.timedSeconds,0);assert.equal(m.A.timedCount,0);assert.equal(m.A.missingTimeCount,1);assert.equal(m.A.share,null);assert(!text().includes('50%以上'));
}
let m=run([segment('A',0,0)]);assert.equal(m.A.seconds,0);assert.equal(m.A.timedCount,1);assert.equal(m.A.missingTimeCount,0);assert.equal(m.A.share,null);assert(text().includes('総時間が0秒'));
m=run([segment('A',0,0),segment('B',0,5)]);assert.equal(m.A.share,0);assert.equal(m.B.share,1);assert(text().includes('B の発言が参加者内50%以上'));
m=run([segment('A',0,5),segment('B',0,8,{time_unknown:true})],{A:'participant',B:'observer'});assert.equal(m.A.share,null);assert(text().includes('A の発言が参加者内50%以上'));assert(!text().includes('参加者の時刻不明'));
m=run([segment('A',0,8,{time_unknown:true}),segment('B',0,5)],{A:'participant',B:'observer'});assert(!text().includes('50%以上'));assert(text().includes('参加者の時刻不明'));
m=run([]);assert.equal(Object.keys(m).length,0);assert(text().includes('発話なし'));assert(!text().includes('0秒'));assert(!text().includes('時刻不明'));
m=run([segment('A',0,Number.MAX_VALUE),segment('A',0,Number.MAX_VALUE)]);assert.equal(m.A.seconds,null);assert.equal(m.A.share,null);assert(!text().includes('50%以上'));
// Execute the editor's real metric-cell formatter; counts name their utterance unit.
const editor=extract('app.js','renderSpeakerEditor');
const start=editor.indexOf('    const timeText ='),end=editor.indexOf('    row.append(metricCell);',start);
assert(start>=0&&end>start);
ctx.metricCell={};ctx.formatTime=seconds=>`00:${String(seconds).padStart(2,'0')}`;
function metricText(metric){ctx.metric=metric;vm.runInContext(`(()=>{${editor.slice(start,end)}})()`,ctx);return ctx.metricCell.textContent;}
m=run([segment('A',0,10),segment('A',null,null)]);
assert.equal(metricText(m.A),'2回 / 時刻あり00:10（1/2発話、時刻不明1発話） / 割合は算出不可');
assert(!metricText(m.A).includes('確認済み'));
m=run([segment('A',0,0)]);assert.equal(metricText(m.A),'1回 / 00:00 / 割合は算出不可');
for(const invalid of [segment('A',2678400,2678401),segment('A',2678401,2678401),segment('A',0,1e308)]){
 const value=run([invalid]);assert.equal(value.A.timedCount,0);assert.equal(value.A.missingTimeCount,1);assert.equal(value.A.seconds,null);assert.equal(value.A.share,null);
}
m=run([segment('A',2678399,2678400)]);assert.equal(m.A.seconds,1);assert.equal(m.A.share,1);
m=run([segment('A',2678400,2678400)]);assert.equal(m.A.seconds,0);assert.equal(m.A.timedCount,1);assert.equal(m.A.share,null);
console.log('PASS speaker time validity, partial known subtotal, nullable seconds/share, true zero, participant-only coverage, empty and overflow; raw data unchanged');
