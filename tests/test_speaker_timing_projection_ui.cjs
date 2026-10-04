// Derived timing is usable only while its raw per-row and collection binding still matches.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.join(__dirname,'../src/gurumoji/static');
function extract(file,name){const source=fs.readFileSync(path.join(root,file),'utf8').replace(/\r\n/g,'\n');const start=source.indexOf(`function ${name}(`);assert(start>=0);return source.slice(start,source.indexOf('\n}',start)+2);}
const ctx={currentJob:null};vm.createContext(ctx);vm.runInContext(extract('analysis-content.js','analysisEvidenceTimeValid'),ctx);vm.runInContext(extract('app.js','speakerMetrics'),ctx);
function job(start='0',end='10'){
 const segments=[{id:'a',speaker:'A',text:'synthetic',start,end},{id:'b',speaker:'B',text:'synthetic',start,end}];
 return {segments,segment_timings:segments.map(segment=>({segment_id:segment.id,source_start:segment.start,source_end:segment.end,source_time_unknown:null,valid:true,start:0,end:10}))};
}
function metrics(value){ctx.currentJob=value;const before=JSON.stringify(value);const measured=ctx.speakerMetrics();assert.equal(JSON.stringify(value),before);return measured;}
for(const [start,end] of [['0','10'],['０','１０'],['٠','١٠'],['0','1_0'],[' 0 ','1e1']]){
 const value=job(start,end),measured=metrics(value);assert.equal(measured.A.seconds,10);assert.equal(measured.A.share,.5);assert.equal(measured.A.missingTimeCount,0);
 assert.equal(ctx.analysisEvidenceTimeValid(value.segments[0]),false,'Numeric string projection does not broaden the audio/evidence guard');
}
let value=job();value.segments[0].end='20';let measured=metrics(value);assert.equal(measured.A.seconds,null);assert.equal(measured.B.seconds,10);assert.equal(measured.B.share,null);
value=job();Object.assign(value.segments[0],{start:0,end:20});measured=metrics(value);assert.equal(measured.A.seconds,20);assert.equal(measured.B.seconds,10);
for(const change of ['id','order','count','duplicate','missing','wrong-shape','wrong-entry']){
 value=job();
 if(change==='id')value.segments[0].id='new';
 if(change==='order')value.segments.reverse();
 if(change==='count')value.segments.push({...value.segments[0],id:'c'});
 if(change==='duplicate'){value.segments[1].id='a';value.segment_timings[1].segment_id='a';}
 if(change==='missing')delete value.segment_timings;
 if(change==='wrong-shape')value.segment_timings={};
 if(change==='wrong-entry')value.segment_timings[1]=null;
 measured=metrics(value);assert.equal(measured.A.seconds,null,change);
}
for(const invalid of [{valid:false},{valid:1},{source_end:'9'},{source_time_unknown:true},{start:-1},{end:2678401},{end:'10'},{end:NaN},{end:Infinity},{start:11,end:10}]){
 value=job();Object.assign(value.segment_timings[0],invalid);assert.equal(metrics(value).A.seconds,null,JSON.stringify(invalid));
}
value=job();value.segments[0].time_unknown=true;assert.equal(metrics(value).A.seconds,null);
value=job(0,10);value.segment_timings[0].end=99;assert.equal(metrics(value).A.seconds,10,'A malformed projection may not change existing numeric bounds');
// Empty JSON containers are false markers in the existing backend contract. Their
// two JSON copies share values, never object identity; only the measurement path may normalize them.
for(const marker of [[],{}]) for(const [start,end,seconds] of [[0,10,10],['0','10',10],[0,0,0]]){
 value=job(start,end);
 for(const segment of value.segments)segment.time_unknown=marker;
 for(const projection of value.segment_timings){projection.source_time_unknown=marker;projection.end=Number(end);}
 value=JSON.parse(JSON.stringify(value));
 measured=metrics(value);assert.equal(measured.A.seconds,seconds);assert.equal(measured.A.timedCount,1);
 assert.equal(ctx.analysisEvidenceTimeValid(value.segments[0]),false,'Empty marker compatibility is measurement-only');
 Object.assign(value.segments[0],{start:0,end:20});
 measured=metrics(value);assert.equal(measured.A.seconds,20,'Real numeric edits use current bounds with the unchanged empty marker');
 assert.equal(measured.A.missingTimeCount,0);
}
for(const marker of [null,false,0,'',[],{}]){
 value=job(0,10);delete value.segment_timings;value.segments[0].time_unknown=marker;
 assert.equal(metrics(value).A.seconds,10,'Legacy numeric fallback follows the finite false-marker set');
}
for(const marker of [true,1,'0',[false],{known:false},NaN,new Date(0),new Map()]){
 value=job('0','10');value.segments[0].time_unknown=marker;value.segment_timings[0].source_time_unknown=marker;
 assert.equal(metrics(value).A.seconds,null,'A fabricated valid projection cannot override a true/unsupported marker');
 value.segments[0].start=0;value.segments[0].end=10;
 assert.equal(metrics(value).A.seconds,null,'Numeric fallback does not broaden to nonempty or non-JSON markers');
}
for(const [original,edited] of [[[],{}],[{},[]],[[],[false]],[{},{known:false}]]){
 value=job('0','10');value.segment_timings[0].source_time_unknown=original;value.segments[0].time_unknown=edited;
 assert.equal(metrics(value).A.seconds,null,'Marker type/value changes invalidate the string-time projection');
}
console.log('PASS backend numeric-string projection, exact raw binding, structural invalidation, malformed fallback, immutable raw and independent audio guard');
