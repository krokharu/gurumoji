// Real display helpers with synthetic nodes; native layout/browser/AT are separate.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.join(__dirname,'../src/gurumoji/static');
const files=Object.fromEntries(['app.js','analysis-visualizations.js'].map(name=>[name,fs.readFileSync(path.join(root,name),'utf8').replace(/\r\n/g,'\n')]));
function extract(file,name){const source=files[file],start=source.indexOf(`function ${name}(`);assert(start>=0,name);return source.slice(start,source.indexOf('\n}',start)+2);}
function node(tag='div',cls='',text=''){return {tag,className:cls,children:[],attributes:{},style:{},textContent:text,
 append(...items){this.children.push(...items);},setAttribute(k,v){this.attributes[k]=String(v);}};}
const ctx={analysisElement:node,safeAnalysisColor:value=>value,formatTime:seconds=>`00:${String(seconds).padStart(2,'0')}`};vm.createContext(ctx);
for(const [file,name] of [['app.js','boundedAnalysisPercent'],['analysis-visualizations.js','appendAnalysisBar']])vm.runInContext(extract(file,name),ctx);
for(const value of [null,undefined,'',NaN,Infinity,'bad']){
 const host=node();ctx.appendAnalysisBar(host,'Synthetic',value,'missing');
 const row=host.children[0];assert(!row.children.some(n=>n.attributes?.role==='img'),'missing percent must not draw a zero-percent image');
 assert(row.children.some(n=>n.textContent==='割合は算出不可'));
}
for(const value of [0,25,'25']){
 const host=node();ctx.appendAnalysisBar(host,'Synthetic',value);const track=host.children[0].children.find(n=>n.attributes?.role==='img');
 assert(track);assert.equal(track.attributes['aria-label'],`Synthetic ${Number(value).toFixed(1)}%`);
}
vm.runInContext(extract('app.js','analysisObservedTimeText'),ctx);
for(const value of [null,undefined,'',NaN,Infinity])assert.equal(ctx.analysisObservedTimeText({speaking_seconds:value}),'時刻不明');
assert.equal(ctx.analysisObservedTimeText({speaking_seconds:null,timed_turn_count:0,missing_time_turn_count:2}),'時刻不明2発話');
assert.equal(ctx.analysisObservedTimeText({speaking_seconds:10,timed_turn_count:1,missing_time_turn_count:1}),'時刻あり00:10（1/2発話、時刻不明1発話）');
assert.equal(ctx.analysisObservedTimeText({speaking_seconds:0,timed_turn_count:1,missing_time_turn_count:0}),'00:00');
assert.equal(ctx.analysisObservedTimeText({total_speaking_seconds:null,timed_turn_count:0,missing_time_turn_count:2},'total_speaking_seconds'),'時刻不明2発話');
assert.equal(ctx.analysisObservedTimeText({speaking_seconds:10}),'00:10');
assert.equal(ctx.analysisObservedTimeText({speaking_seconds:null,role_aggregation_status:'mixed',timed_turn_count:2,missing_time_turn_count:0}),'役割混在で算出不可');
ctx.speakerRoleLabels={moderator:'司会者',participant:'参加者'};
vm.runInContext(extract('app.js','analysisSpeakerRoleText'),ctx);
const mixed={role:'mixed',role_status:'mixed',observed_roles:['moderator','participant']};
const before=structuredClone(mixed);assert.equal(ctx.analysisSpeakerRoleText(mixed),'役割混在（司会者・参加者）');assert.deepEqual(mixed,before);
assert.equal(ctx.analysisSpeakerRoleText({role:'participant',role_status:'single'}),'参加者');
assert.equal(ctx.analysisSpeakerRoleText({role:'constructor'}),'constructor');

assert(!/formatTime\((?:metric|selected|item)\.speaking_seconds\s*\|\|\s*0\)/.test(files['app.js']));
assert(!files['app.js'].includes('formatTime(overview.total_speaking_seconds || 0)'));
const automatic=files['app.js'];
const graphStart=automatic.indexOf("  const timelinePanel = analysisCardPanel('発話量の変化（時間別）'");
const graphEnd=automatic.indexOf('  grid.append(excitementPanel.panel);',graphStart)+'  grid.append(excitementPanel.panel);'.length;
assert(graphStart>=0&&graphEnd>graphStart);
ctx.analysisCardPanel=()=>({panel:node(),body:node()});ctx.data={};ctx.speakers=[];
let graphCalls=0;ctx.buildAnalysisTimelineChart=ctx.buildAnalysisExcitementChart=()=>{graphCalls++;return node('svg');};
for(const [timed,missing,expected] of [[0,2,0],[1,1,2],[1,0,2]]){
 ctx.overview={timed_turn_count:timed,missing_time_turn_count:missing};ctx.automatic={time_bins:[{start:0,end:60,speaking_seconds:0}]};ctx.grid=node();graphCalls=0;
 vm.runInContext(`(()=>{${automatic.slice(graphStart,graphEnd)}})()`,ctx);assert.equal(graphCalls,expected);
}
vm.runInContext(extract('app.js','analysisEndpointText'),ctx);
assert.equal(ctx.analysisEndpointText(null,0,1),'時刻不明1発話');assert.equal(ctx.analysisEndpointText(null,0,0),'時刻不明');
assert.equal(ctx.analysisEndpointText(0,1,0),'00:00（時刻あり1/1発話）');
assert.equal(ctx.analysisEndpointText(10,1,1),'00:10（時刻あり1/2発話、時刻不明1発話）');
const libraryNodes=new Map();ctx.document={querySelector:selector=>{if(!libraryNodes.has(selector))libraryNodes.set(selector,node());return libraryNodes.get(selector);}};ctx.formatDate=value=>value;
vm.runInContext(extract('app.js','renderLibraryOverview'),ctx);
for(const [items,known] of [[[{duration:null,missing_time_turn_count:1}],false],[[{duration:10,missing_time_turn_count:1}],true],[[{duration:10},{duration:null}],true]]){
 const before=JSON.stringify(items);ctx.renderLibraryOverview(items);const text=libraryNodes.get('#library-duration-metric').textContent;
 assert(/不明|欠測/.test(text));assert.equal(text.includes('00:10'),known);assert(!text.includes('00:00'));assert.equal(JSON.stringify(items),before);
}
ctx.renderLibraryOverview([{duration:10},{duration:0}]);assert.equal(libraryNodes.get('#library-duration-metric').textContent,'00:10');
console.log('PASS nullable time display, partial coverage, true zero, legacy values, missing percentage image suppression');
